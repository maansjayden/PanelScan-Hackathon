"""Demo-mode tests: no keys or network needed."""

import io
import wave

from fastapi.testclient import TestClient

from app.main import app
from app.services import meta_client

client = TestClient(app)


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 240)
    return buffer.getvalue()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_assess_damage_returns_estimate():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"fake-image", "image/jpeg"),
            "audio": ("note.wav", _wav_bytes(), "audio/wav"),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "T-Cross" in body["vehicle_summary"]
    assert len(body["damage_items"]) == 3
    first = body["damage_items"][0]
    assert first["recommended_action"] in ("repair", "replace")
    assert 0 <= first["ai_confidence_score"] <= 1
    assert body["total_parts_estimate_zar"] > 0
    assert body["total_labor_hours"] > 0


def test_assess_damage_rejects_wrong_mime():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("evil.txt", b"nope", "text/plain"),
            "audio": ("note.wav", _wav_bytes(), "audio/wav"),
        },
    )
    assert resp.status_code == 415


def test_assess_damage_rejects_empty_uploads():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"", "image/jpeg"),
            "audio": ("note.wav", b"", "audio/wav"),
        },
    )
    assert resp.status_code == 400


def test_assess_damage_rejects_non_wav_audio():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"fake-image", "image/jpeg"),
            "audio": ("note.m4a", b"fake-audio", "audio/mp4"),
        },
    )
    assert resp.status_code == 415


def test_assess_damage_rejects_invalid_wav():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"fake-image", "image/jpeg"),
            "audio": ("note.wav", b"not a wav file", "audio/wav"),
        },
    )
    assert resp.status_code == 400


def test_missing_credentials_fail_instead_of_returning_demo(monkeypatch):
    monkeypatch.setattr(meta_client, "_KEY", "")
    monkeypatch.setattr(meta_client, "_DEMO_MODE", False)
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"fake-image", "image/jpeg"),
            "audio": ("note.wav", _wav_bytes(), "audio/wav"),
        },
    )
    assert resp.status_code == 503
    assert "MODEL_API_KEY" in resp.json()["detail"]


def _approval_payload():
    return {
        "estimate": {
            "vehicle_summary": "2021 VW T-Cross, front-end collision",
            "damage_items": [
                {
                    "panel_name": "front bumper",
                    "damage_type": "missing",
                    "recommended_action": "replace",
                    "ai_confidence_score": 0.97,
                }
            ],
            "total_parts_estimate_zar": 8900,
            "total_labor_hours": 6,
        },
        "labour_rate_zar": 650,
    }


def test_customer_approval_flow_persists_estimate_and_records_decision(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PANELSCAN_APPROVALS_DB", str(tmp_path / "approvals.sqlite3"))

    created = client.post("/api/approvals", json=_approval_payload())
    assert created.status_code == 201, created.text
    token = created.json()["approval_token"]
    assert len(token) >= 32

    pending = client.get(f"/api/approvals/{token}")
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending"
    assert pending.json()["labour_estimate_zar"] == 3900
    assert pending.json()["total_estimate_zar"] == 12800

    approved = client.post(
        f"/api/approvals/{token}/decision",
        json={"decision": "approved"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["decision_at"] is not None
    assert client.get(f"/api/approvals/{token}").json()["status"] == "approved"

    duplicate = client.post(
        f"/api/approvals/{token}/decision",
        json={"decision": "changes_requested"},
    )
    assert duplicate.status_code == 409


def test_customer_approval_flow_records_change_request(monkeypatch, tmp_path):
    monkeypatch.setenv("PANELSCAN_APPROVALS_DB", str(tmp_path / "approvals.sqlite3"))
    created = client.post("/api/approvals", json=_approval_payload())
    token = created.json()["approval_token"]

    response = client.post(
        f"/api/approvals/{token}/decision",
        json={"decision": "changes_requested"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "changes_requested"


def test_customer_approval_flow_rejects_bad_rate_and_invalid_link(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PANELSCAN_APPROVALS_DB", str(tmp_path / "approvals.sqlite3"))

    invalid_rate = _approval_payload()
    invalid_rate["labour_rate_zar"] = 0
    assert client.post("/api/approvals", json=invalid_rate).status_code == 422
    assert client.get("/api/approvals/not-a-valid-token").status_code == 404
    assert (
        client.post(
            "/api/approvals/not-a-valid-token/decision",
            json={"decision": "approved"},
        ).status_code
        == 404
    )
