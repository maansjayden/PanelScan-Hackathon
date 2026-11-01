"""Adapters for Muse Voice Transcribe and SAM 3.1 on Meta Model API."""

import base64
import json
import logging
import os
import re

import httpx

from app.config import load_project_env

load_project_env()

logger = logging.getLogger("panelScan.meta")

_KEY = (
    os.getenv("META_MODEL_API_KEY")
    or os.getenv("MODEL_API_KEY")
    or os.getenv("META_API_KEY")
    or ""
)
_BASE = os.getenv("META_MODEL_API_BASE", "https://api.meta.ai/v1").rstrip("/")
_VOICE_MODEL = os.getenv("VOICE_MODEL", "muse-voice-transcribe-1.0")
_VISION_MODEL = os.getenv("SAM_MODEL", "sam-3.1")
_DEMO_MODE = os.getenv("PANELSCAN_DEMO_MODE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/x-icon",
}
_BOX_PATTERN = re.compile(r"<\|box;([^|]+)\|>")


class MetaServiceError(RuntimeError):
    """A Meta Model API call failed or returned an unexpected payload."""


class MetaConfigurationError(MetaServiceError):
    """Meta Model API credentials are missing."""


def _auth() -> dict[str, str]:
    if not _KEY:
        raise MetaConfigurationError(
            "Meta Model API is not configured; set MODEL_API_KEY or explicitly "
            "enable PANELSCAN_DEMO_MODE."
        )
    return {
        "Authorization": f"Bearer {_KEY}",
        "Accept": "application/json",
    }


def _demo_enabled() -> bool:
    if _DEMO_MODE:
        logger.warning("PANELSCAN_DEMO_MODE is enabled; returning demo model data")
        return True
    if not _KEY:
        raise MetaConfigurationError(
            "Meta Model API is not configured; set MODEL_API_KEY or explicitly "
            "enable PANELSCAN_DEMO_MODE."
        )
    return False


async def run_transcription(audio_bytes: bytes, filename: str) -> str:
    """Transcribe a WAV voice memo with Muse Voice."""
    if _demo_enabled():
        return (
            "2021 VW T-Cross. Front bumper is gone, left fender needs panel "
            "beating, headlight assembly is cracked."
        )

    request = {
        "model": _VOICE_MODEL,
        "audioEncoding": "WAV",
        "mode": "PUSH_TO_TALK",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_BASE}/asr/transcribe",
                headers=_auth(),
                files={
                    "request": (None, json.dumps(request), "application/json"),
                    "audio": (filename, audio_bytes, "audio/wav"),
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise MetaServiceError("Muse Voice transcription request failed.") from exc
    except ValueError as exc:
        raise MetaServiceError(
            "Muse Voice returned invalid JSON for the transcription."
        ) from exc

    text = data.get("transcript") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise MetaServiceError("Muse Voice returned no usable transcript.")
    return text.strip()


async def run_segmentation(
    image_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """Segment vehicle damage with SAM 3.1 and return compact box coordinates."""
    if _demo_enabled():
        return {
            "model": _VISION_MODEL,
            "boxes": [
                "front bumper: missing",
                "left fender: dented",
                "left headlight: cracked",
            ],
        }

    normalized_type = "image/jpeg" if content_type == "image/jpg" else content_type
    if normalized_type not in _IMAGE_MIME_TYPES:
        raise MetaServiceError("SAM 3.1 received an unsupported image type.")

    image_data = base64.b64encode(image_bytes).decode("ascii")
    request = {
        "model": _VISION_MODEL,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "vehicle collision damage: damaged or missing bumper, "
                            "fender, door, hood, glass, or headlight"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{normalized_type};base64,{image_data}",
                    },
                ],
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_BASE}/responses",
                headers={**_auth(), "Content-Type": "application/json"},
                json=request,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise MetaServiceError("SAM 3.1 segmentation request failed.") from exc
    except ValueError as exc:
        raise MetaServiceError("SAM 3.1 returned invalid JSON.") from exc

    output = data.get("output") if isinstance(data, dict) else None
    if not isinstance(output, list) or data.get("status") != "completed":
        raise MetaServiceError("SAM 3.1 returned an unexpected response.")

    text_parts = [
        block["text"]
        for item in output
        if isinstance(item, dict) and isinstance(item.get("content"), list)
        for block in item["content"]
        if (
            isinstance(block, dict)
            and block.get("type") == "output_text"
            and isinstance(block.get("text"), str)
        )
    ]
    output_text = "\n".join(text_parts).strip()
    return {
        "model": _VISION_MODEL,
        "filename": filename,
        "boxes": _BOX_PATTERN.findall(output_text),
    }
