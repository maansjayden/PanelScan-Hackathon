"""Meta Model API adapter: voice transcription + damage segmentation.

Configuration comes from the environment (see .env.example). Until real
hackathon credentials land, both entry points serve deterministic demo data so
local development and the frontend stay unblocked.
"""

import logging
import os

import httpx

logger = logging.getLogger("panelScan.meta")

_KEY = os.getenv("META_MODEL_API_KEY") or os.getenv("META_API_KEY") or ""
_BASE = os.getenv("META_MODEL_API_BASE", "https://api.meta.ai/v1").rstrip("/")
_VOICE_MODEL = os.getenv("VOICE_MODEL", "muse-voice-transcribe-1.0")
_VISION_MODEL = os.getenv("SAM_MODEL", "sam-3.1")
# VERIFY against https://dev.meta.ai/docs before relying on these paths: the
# base URL + model IDs are corroborated by multiple community sources, but the
# exact endpoint paths are not yet confirmed from official Meta docs.
_VOICE_PATH = os.getenv("VOICE_ENDPOINT_PATH", "asr/transcribe").strip("/")
_SAM_PATH = os.getenv("SAM_ENDPOINT_PATH", "sam/segment").strip("/")

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class MetaServiceError(RuntimeError):
    """A Meta Model API call failed or returned an unexpected payload."""


def _auth() -> dict:
    return {"Authorization": f"Bearer {_KEY}"}


async def _post_multipart(url: str, model: str, field: str, payload: bytes) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers=_auth(),
            data={"model": model},
            files={field: ("upload", payload, "application/octet-stream")},
        )
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise MetaServiceError(f"{url} returned non-object JSON")
    return data


async def run_transcription(audio_bytes: bytes, filename: str) -> str:
    """Transcribe a voice memo with Muse Voice. Returns plain text."""
    _ = filename
    if not _KEY:
        logger.warning("no Meta API key configured; using demo transcript")
        return (
            "2021 VW T-Cross. Front bumper is gone, left fender needs panel "
            "beating, headlight assembly is cracked."
        )
    try:
        data = await _post_multipart(
            f"{_BASE}/{_VOICE_PATH}", _VOICE_MODEL, "audio", audio_bytes
        )
    except httpx.HTTPError as exc:
        raise MetaServiceError(f"transcription request failed: {exc}") from exc
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise MetaServiceError("transcription response had no usable text")
    return text


async def run_segmentation(image_bytes: bytes, filename: str) -> dict:
    """Segment vehicle damage with SAM 3.1. Returns region data."""
    _ = filename
    if not _KEY:
        logger.warning("no Meta API key configured; using demo segmentation")
        return {
            "regions": [
                {"panel": "front bumper", "finding": "missing"},
                {"panel": "left fender", "finding": "dented"},
                {"panel": "left headlight", "finding": "cracked"},
            ]
        }
    try:
        return await _post_multipart(
            f"{_BASE}/{_SAM_PATH}", _VISION_MODEL, "image", image_bytes
        )
    except httpx.HTTPError as exc:
        raise MetaServiceError(f"segmentation request failed: {exc}") from exc
