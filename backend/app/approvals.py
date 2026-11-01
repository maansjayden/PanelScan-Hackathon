"""Private-token customer approval records for estimate handoff."""

import hashlib
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import DamageItem, QuoteEstimate

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_APPROVAL_DAYS = 30


class ApprovalRequest(BaseModel):
    estimate: QuoteEstimate
    labour_rate_zar: float = Field(..., gt=0, le=100_000)


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "changes_requested"]


class CustomerEstimate(BaseModel):
    vehicle_summary: str
    damage_items: list[DamageItem]
    total_parts_estimate_zar: float
    total_labor_hours: float
    labour_rate_zar: float
    labour_estimate_zar: float
    total_estimate_zar: float
    status: Literal["pending", "approved", "changes_requested"]
    created_at: str
    decision_at: str | None


def _database_path() -> Path:
    configured = os.getenv("PANELSCAN_APPROVALS_DB")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "approvals.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            token_hash TEXT PRIMARY KEY,
            estimate_json TEXT NOT NULL,
            labour_rate_zar REAL NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'approved', 'changes_requested')
            ),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            decision_at TEXT
        )
        """
    )
    return connection


def _hash_token(token: str) -> str:
    if not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Invalid approval token.")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_approval(request: ApprovalRequest) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO approvals (
                token_hash, estimate_json, labour_rate_zar, status, created_at, expires_at
            ) VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (
                _hash_token(token),
                request.estimate.model_dump_json(),
                request.labour_rate_zar,
                now.isoformat(),
                (now + timedelta(days=_APPROVAL_DAYS)).isoformat(),
            ),
        )
    return token


def get_customer_estimate(token: str) -> CustomerEstimate | None:
    try:
        token_hash = _hash_token(token)
    except ValueError:
        return None

    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM approvals WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
        return None

    estimate = json.loads(row["estimate_json"])
    labour_estimate = round(
        estimate["total_labor_hours"] * row["labour_rate_zar"], 2
    )
    return CustomerEstimate(
        **estimate,
        labour_rate_zar=row["labour_rate_zar"],
        labour_estimate_zar=labour_estimate,
        total_estimate_zar=round(
            estimate["total_parts_estimate_zar"] + labour_estimate, 2
        ),
        status=row["status"],
        created_at=row["created_at"],
        decision_at=row["decision_at"],
    )


def record_decision(token: str, decision: ApprovalDecision) -> bool:
    try:
        token_hash = _hash_token(token)
    except ValueError:
        return False

    now = datetime.now(timezone.utc)
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE approvals
            SET status = ?, decision_at = ?
            WHERE token_hash = ? AND status = 'pending' AND expires_at > ?
            """,
            (decision.decision, now.isoformat(), token_hash, now.isoformat()),
        )
    return cursor.rowcount == 1
