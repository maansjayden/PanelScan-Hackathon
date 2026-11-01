import asyncio
import base64
import json

import httpx

from app.services import meta_client


def _client_with_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        meta_client.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )


def test_transcription_uses_documented_multipart_contract(monkeypatch):
    def handler(request):
        body = request.content
        assert str(request.url) == "https://meta.test/v1/asr/transcribe"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert b'name="request"' in body
        assert b'"model": "muse-voice-transcribe-1.0"' in body
        assert b'"audioEncoding": "WAV"' in body
        assert b'"mode": "PUSH_TO_TALK"' in body
        assert b'name="audio"; filename="memo.wav"' in body
        return httpx.Response(200, json={"transcript": "A damaged front bumper."})

    _client_with_transport(monkeypatch, handler)
    monkeypatch.setattr(meta_client, "_KEY", "test-key")
    monkeypatch.setattr(meta_client, "_BASE", "https://meta.test/v1")
    monkeypatch.setattr(meta_client, "_DEMO_MODE", False)

    transcript = asyncio.run(meta_client.run_transcription(b"wav-data", "memo.wav"))

    assert transcript == "A damaged front bumper."


def test_segmentation_uses_responses_api_and_inline_image(monkeypatch):
    image = b"vehicle-photo"

    def handler(request):
        assert str(request.url) == "https://meta.test/v1/responses"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "sam-3.1"
        content = payload["input"][0]["content"]
        assert content[0]["type"] == "input_text"
        assert content[1]["type"] == "input_image"
        assert content[1]["image_url"] == (
            "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        )
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
                                "text": (
                                    "<0f>0<|box;x1=1;y1=2;x2=3;y2=4|>"
                                    "<|mask;x=0;y=0;data=large-mask|>"
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    _client_with_transport(monkeypatch, handler)
    monkeypatch.setattr(meta_client, "_KEY", "test-key")
    monkeypatch.setattr(meta_client, "_BASE", "https://meta.test/v1")
    monkeypatch.setattr(meta_client, "_DEMO_MODE", False)

    result = asyncio.run(
        meta_client.run_segmentation(image, "damage.jpg", "image/jpeg")
    )

    assert result["model"] == "sam-3.1"
    assert result["boxes"] == ["x1=1;y1=2;x2=3;y2=4"]
