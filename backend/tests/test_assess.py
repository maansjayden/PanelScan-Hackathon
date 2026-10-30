"""Demo-mode tests: no keys or network needed."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_assess_damage_returns_estimate():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"fake-image", "image/jpeg"),
            "audio": ("note.m4a", b"fake-audio", "audio/mp4"),
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
            "audio": ("note.m4a", b"fake-audio", "audio/mp4"),
        },
    )
    assert resp.status_code == 415


def test_assess_damage_rejects_empty_uploads():
    resp = client.post(
        "/api/assess-damage",
        files={
            "image": ("dmg.jpg", b"", "image/jpeg"),
            "audio": ("note.m4a", b"", "audio/mp4"),
        },
    )
    assert resp.status_code == 400
