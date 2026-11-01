import asyncio
import json

import httpx
import pytest

from app.schemas import QuoteEstimate
from app.services import muse_client

_ESTIMATE = {
    "vehicle_summary": "2021 VW T-Cross, front-end collision",
    "damage_items": [
        {
            "panel_name": "front bumper",
            "damage_type": "missing",
            "recommended_action": "replace",
            "ai_confidence_score": 0.96,
        }
    ],
    "total_parts_estimate_zar": 4200,
    "total_labor_hours": 3.5,
}


def _client_with_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        muse_client.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )


def test_quote_agent_uses_muse_responses_and_validates_json(monkeypatch):
    def handler(request):
        assert str(request.url) == "https://meta.test/v1/responses"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "muse-spark-1.3"
        assert "Required JSON schema" in payload["instructions"]
        content = payload["input"][0]["content"]
        assert "MECHANIC TRANSCRIPT" in content[0]["text"]
        assert "SAM 3.1 DAMAGE BOXES" in content[0]["text"]
        assert content[1]["type"] == "input_image"
        assert content[1]["image_url"] == "data:image/jpeg;base64,aW1hZ2U="
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(_ESTIMATE),
                            }
                        ],
                    }
                ],
            },
        )

    _client_with_transport(monkeypatch, handler)
    monkeypatch.setattr(muse_client, "_KEY", "test-key")
    monkeypatch.setattr(muse_client, "_BASE", "https://meta.test/v1")
    monkeypatch.setattr(muse_client, "_DEMO_MODE", False)

    estimate = asyncio.run(
        muse_client.run_quote_agent(
            "2021 VW T-Cross. Front bumper is missing.",
            {"model": "sam-3.1", "boxes": ["x1=1;y1=2;x2=3;y2=4"]},
            b"image",
            "image/jpeg",
        )
    )

    assert isinstance(estimate, QuoteEstimate)
    assert estimate.vehicle_summary == _ESTIMATE["vehicle_summary"]
    assert estimate.damage_items[0].recommended_action == "replace"


def test_quote_agent_rejects_output_outside_schema(monkeypatch):
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": '{"unexpected": true}'}
                        ],
                    }
                ],
            },
        )

    _client_with_transport(monkeypatch, handler)
    monkeypatch.setattr(muse_client, "_KEY", "test-key")
    monkeypatch.setattr(muse_client, "_BASE", "https://meta.test/v1")
    monkeypatch.setattr(muse_client, "_DEMO_MODE", False)

    with pytest.raises(muse_client.MuseServiceError, match="required schema"):
        asyncio.run(muse_client.run_quote_agent("Transcript", {}, b"image", "image/jpeg"))
