"""PanelScan damage-assessment API.

Accepts a damage photo plus a spoken voice memo, runs them through the Meta
model clients in parallel, and returns a strictly typed QuoteEstimate.
"""

import asyncio
import io
import logging
import os
import wave

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.approvals import (
    ApprovalDecision,
    ApprovalRequest,
    CustomerEstimate,
    create_approval,
    get_customer_estimate,
    record_decision,
)
from app.schemas import QuoteEstimate
from app.services.meta_client import (
    MetaConfigurationError,
    MetaServiceError,
    run_segmentation,
    run_transcription,
)
from app.services.muse_client import (
    MuseConfigurationError,
    MuseServiceError,
    run_quote_agent,
)

logger = logging.getLogger("panelScan")

app = FastAPI(title="PanelScan", version="0.1.0")

_allowed = os.getenv("PANELSCAN_CORS_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

IMAGE_LIMIT = 15 * 1024 * 1024
AUDIO_LIMIT = 30 * 1024 * 1024
IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/x-icon",
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class ApprovalLink(BaseModel):
    approval_token: str


@app.post("/api/approvals", response_model=ApprovalLink, status_code=201)
def create_estimate_approval(request: ApprovalRequest) -> ApprovalLink:
    return ApprovalLink(approval_token=create_approval(request))


@app.get("/api/approvals/{token}", response_model=CustomerEstimate)
def read_estimate_approval(token: str) -> CustomerEstimate:
    estimate = get_customer_estimate(token)
    if estimate is None:
        raise HTTPException(status_code=404, detail="This approval link is invalid or expired.")
    return estimate


@app.post("/api/approvals/{token}/decision", response_model=CustomerEstimate)
def decide_estimate_approval(
    token: str,
    decision: ApprovalDecision,
) -> CustomerEstimate:
    if not record_decision(token, decision):
        if get_customer_estimate(token) is None:
            raise HTTPException(
                status_code=404,
                detail="This approval link is invalid or expired.",
            )
        raise HTTPException(
            status_code=409,
            detail="A response has already been recorded for this estimate.",
        )
    estimate = get_customer_estimate(token)
    if estimate is None:
        raise HTTPException(
            status_code=404,
            detail="This approval link is invalid or expired.",
        )
    return estimate


def _reject_bad_upload(upload: UploadFile, prefix: str, label: str) -> None:
    mime = (upload.content_type or "").lower()
    allowed = IMAGE_MIME_TYPES if label == "image" else {"audio/wav", "audio/x-wav"}
    if not mime.startswith(prefix) or mime not in allowed:
        raise HTTPException(
            status_code=415,
            detail=(
                f"{label} must be one of {', '.join(sorted(allowed))} "
                f"(got {upload.content_type!r})"
            ),
        )


def _validate_wav(raw_audio: bytes) -> None:
    try:
        with wave.open(io.BytesIO(raw_audio), "rb") as wav:
            valid_format = (
                wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and wav.getframerate() in {16000, 24000}
                and wav.getnframes() > 0
                and wav.getnframes() <= wav.getframerate() * 600
            )
    except (EOFError, wave.Error) as exc:
        raise HTTPException(
            status_code=400,
            detail="audio must be a valid mono 16-bit PCM WAV file.",
        ) from exc
    if not valid_format:
        raise HTTPException(
            status_code=400,
            detail="audio must be mono 16-bit PCM at 16 kHz or 24 kHz.",
        )


@app.post("/api/assess-damage", response_model=QuoteEstimate)
async def assess_damage(
    image: UploadFile = File(...),  # noqa: B008 - FastAPI dependency idiom
    audio: UploadFile = File(...),  # noqa: B008 - FastAPI dependency idiom
) -> QuoteEstimate:
    _reject_bad_upload(image, "image/", "image")
    _reject_bad_upload(audio, "audio/", "audio")

    raw_image = await image.read()
    raw_audio = await audio.read()
    if len(raw_image) > IMAGE_LIMIT:
        raise HTTPException(status_code=413, detail="image exceeds 15 MB")
    if len(raw_audio) > AUDIO_LIMIT:
        raise HTTPException(status_code=413, detail="audio exceeds 30 MB")
    if not raw_image or not raw_audio:
        raise HTTPException(status_code=400, detail="image and audio are required")
    _validate_wav(raw_audio)

    try:
        transcript, segmentation = await asyncio.gather(
            run_transcription(raw_audio, audio.filename or "memo"),
            run_segmentation(
                raw_image,
                image.filename or "damage",
                image.content_type or "image/jpeg",
            ),
        )
    except MetaConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Meta Model API credentials are not configured. Set MODEL_API_KEY "
                "or explicitly enable demo mode."
            ),
        ) from exc
    except MetaServiceError as exc:
        logger.exception("Meta model call failed")
        raise HTTPException(status_code=502, detail="Meta model processing failed.") from exc

    try:
        return await run_quote_agent(
            transcript,
            segmentation,
            raw_image,
            image.content_type or "image/jpeg",
        )
    except MuseConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Meta Model API credentials are not configured. Set MODEL_API_KEY "
                "or explicitly enable demo mode."
            ),
        ) from exc
    except MuseServiceError as exc:
        logger.exception("Muse Spark quote agent failed")
        raise HTTPException(status_code=502, detail="Muse Spark quote generation failed.") from exc
