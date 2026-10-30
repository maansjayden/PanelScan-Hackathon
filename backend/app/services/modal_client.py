"""Modal adapter: Muse Spark Open quote agent.

Sends the voice transcript plus SAM 3.1 segmentation to the Modal webhook and
validates the reply against QuoteEstimate. The prompt embeds the schema itself
so the model is contract-bound. Until the webhook exists, serves demo data.
"""

import logging
import os

import httpx
from pydantic import ValidationError

from app.schemas import DamageItem, QuoteEstimate

logger = logging.getLogger("panelScan.modal")

_WEBHOOK = os.getenv("SPARK_OPEN_ENDPOINT", "")
_TOKEN = os.getenv("SPARK_OPEN_API_KEY", "")

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

_AGENT_BRIEF = (
    "You are PanelScan, a panel-shop estimator. Input: a mechanic's spoken "
    "assessment transcript and SAM 3.1 damage segmentation. Output: exactly "
    "one JSON object matching the supplied schema — vehicle_summary, "
    "damage_items[] with panel_name, damage_type, recommended_action "
    "('repair' or 'replace') and ai_confidence_score (0..1), plus "
    "total_parts_estimate_zar and total_labor_hours. JSON only, no prose."
)


class ModalServiceError(RuntimeError):
    """The quote agent call failed or broke the schema contract."""


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


async def run_quote_agent(transcript_text: str, segmentation_data: dict) -> QuoteEstimate:
    """Fuse transcript + segmentation into a validated QuoteEstimate."""
    if not _WEBHOOK:
        logger.warning("no Modal webhook configured; using demo estimate")
        return _demo_estimate()
    headers = {"Content-Type": "application/json"}
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _WEBHOOK,
                headers=headers,
                json={
                    "system": _AGENT_BRIEF,
                    "transcript": transcript_text,
                    "segmentation": segmentation_data,
                    "schema": QuoteEstimate.model_json_schema(),
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ModalServiceError(f"quote agent request failed: {exc}") from exc
    try:
        return QuoteEstimate.model_validate(resp.json())
    except (ValidationError, ValueError) as exc:
        raise ModalServiceError(f"quote agent broke schema: {exc}") from exc
