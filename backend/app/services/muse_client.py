"""Muse Spark quote agent on Meta Model API."""

import base64
import json
import logging
import os

import httpx
from pydantic import ValidationError

from app.config import load_project_env
from app.schemas import DamageItem, QuoteEstimate

load_project_env()

logger = logging.getLogger("panelScan.muse")

_KEY = (
    os.getenv("META_MODEL_API_KEY")
    or os.getenv("MODEL_API_KEY")
    or os.getenv("META_API_KEY")
    or ""
)
_BASE = os.getenv("META_MODEL_API_BASE", "https://api.meta.ai/v1").rstrip("/")
_MODEL = os.getenv("MUSE_MODEL", "muse-spark-1.3")
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
_AGENT_BRIEF = (
    "You are PanelScan, an automotive repair-estimation assistant. Combine a "
    "mechanic's voice transcript with SAM 3.1's segmentation output. Use only "
    "details supported by those inputs. Return exactly one JSON object that "
    "matches the supplied JSON schema. Do not include markdown or extra prose. "
    "Parts prices and labor hours are estimates, not verified supplier quotes."
)


class MuseServiceError(RuntimeError):
    """Muse Spark failed or returned data outside the estimate contract."""


class MuseConfigurationError(MuseServiceError):
    """Meta Model API credentials are missing."""


def _demo_estimate() -> QuoteEstimate:
    return QuoteEstimate(
        vehicle_summary="2021 VW T-Cross, front-end collision",
        damage_items=[
            DamageItem(
                panel_name="front bumper",
                damage_type="missing",
                recommended_action="replace",
                ai_confidence_score=0.97,
            ),
            DamageItem(
                panel_name="left fender",
                damage_type="dented",
                recommended_action="repair",
                ai_confidence_score=0.89,
            ),
            DamageItem(
                panel_name="left headlight",
                damage_type="cracked",
                recommended_action="replace",
                ai_confidence_score=0.93,
            ),
        ],
        total_parts_estimate_zar=8900.00,
        total_labor_hours=6.0,
    )


def _response_text(data: object) -> str:
    if not isinstance(data, dict) or data.get("status") != "completed":
        raise MuseServiceError("Muse Spark returned an unexpected response.")

    output = data.get("output")
    if not isinstance(output, list):
        raise MuseServiceError("Muse Spark returned an unexpected response.")

    parts = [
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
    text = "\n".join(parts).strip()
    if not text:
        raise MuseServiceError("Muse Spark returned no estimate.")
    return text


async def run_quote_agent(
    transcript_text: str,
    segmentation_data: dict,
    image_bytes: bytes,
    image_content_type: str,
) -> QuoteEstimate:
    """Fuse the transcript and SAM output into a validated estimate."""
    if _DEMO_MODE:
        logger.warning("PANELSCAN_DEMO_MODE is enabled; returning a demo estimate")
        return _demo_estimate()
    if not _KEY:
        raise MuseConfigurationError(
            "Meta Model API is not configured; set MODEL_API_KEY or explicitly "
            "enable PANELSCAN_DEMO_MODE."
        )
    normalized_type = (
        "image/jpeg" if image_content_type == "image/jpg" else image_content_type
    )
    if normalized_type not in _IMAGE_MIME_TYPES:
        raise MuseServiceError("Muse Spark received an unsupported image type.")

    instructions = (
        f"{_AGENT_BRIEF}\n\nRequired JSON schema:\n"
        f"{json.dumps(QuoteEstimate.model_json_schema())}"
    )
    image_data = base64.b64encode(image_bytes).decode("ascii")
    request = {
        "model": _MODEL,
        "instructions": instructions,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"MECHANIC TRANSCRIPT:\n{transcript_text}\n\n"
                            f"SAM 3.1 DAMAGE BOXES:\n"
                            f"{json.dumps(segmentation_data.get('boxes', []))}"
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
                headers={
                    "Authorization": f"Bearer {_KEY}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=request,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise MuseServiceError("Muse Spark quote request failed.") from exc
    except ValueError as exc:
        raise MuseServiceError("Muse Spark returned invalid JSON.") from exc

    try:
        result = json.loads(_response_text(data))
        return QuoteEstimate.model_validate(result)
    except (json.JSONDecodeError, ValidationError, MuseServiceError) as exc:
        raise MuseServiceError(
            "Muse Spark returned an estimate that did not match the required schema."
        ) from exc
