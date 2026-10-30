"""PanelScan damage-assessment API.

Accepts a damage photo plus a spoken voice memo, runs them through the Meta
model clients in parallel, and returns a strictly typed QuoteEstimate.
"""

import asyncio
import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import QuoteEstimate
from app.services.meta_client import (
    MetaServiceError,
    run_segmentation,
    run_transcription,
)
from app.services.modal_client import ModalServiceError, run_quote_agent

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
AUDIO_LIMIT = 25 * 1024 * 1024


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _reject_bad_upload(upload: UploadFile, prefix: str, label: str) -> None:
    mime = (upload.content_type or "").lower()
    if not mime.startswith(prefix):
        raise HTTPException(
            status_code=415,
            detail=f"{label} must be {prefix}* (got {upload.content_type!r})",
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
        raise HTTPException(status_code=413, detail="audio exceeds 25 MB")
    if not raw_image or not raw_audio:
        raise HTTPException(status_code=400, detail="image and audio are required")

    try:
        transcript, segmentation = await asyncio.gather(
            run_transcription(raw_audio, audio.filename or "memo"),
            run_segmentation(raw_image, image.filename or "damage"),
        )
    except MetaServiceError as exc:
        logger.exception("meta model call failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        return await run_quote_agent(transcript, segmentation)
    except ModalServiceError as exc:
        logger.exception("quote agent failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
