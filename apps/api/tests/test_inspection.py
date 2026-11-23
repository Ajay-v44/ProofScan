import httpx
import numpy as np
import pytest

from proofscan.inspection import inspect
from proofscan.providers import MoonshotProvider
from proofscan.schemas import Claims, Hardware
from proofscan.services import fixture_hardware
from proofscan.visual import cv2, process_photo


def test_inspection_uses_actual_measurements_and_bounds_requests():
    output = inspect(
        "simulator", fixture_hardware("misrepresented"), Claims(memory_gib=16, storage_gb=1000), []
    )
    assert [item.status for item in output["findings"]] == ["MISMATCH", "MISMATCH"]
    assert output["requests"] == []
    output = inspect("windows", Hardware(memory_gib=16), Claims(battery_percent=90), ["front"])
    assert output["findings"][0].status == "UNAVAILABLE"
    requests = output["requests"]
    assert len(requests) == 3
    assert len({(item.test, item.angle) for item in requests}) == len(requests)
    assert requests[0].test == "request_battery_reading"
    assert all(item.angle != "front" for item in requests)


def sample_photo() -> bytes:
    rows, cols = np.indices((480, 640))
    checker = (40 + 150 * ((rows // 12 + cols // 12) % 2)).astype(np.uint8)
    valid, encoded = cv2.imencode(".jpg", checker)
    assert valid
    return encoded.tobytes()


def test_image_quality_and_reencoding():
    photo = process_photo(sample_photo())
    assert (photo.width, photo.height) == (640, 480)
    assert len(photo.digest) == 64
    assert photo.jpeg.startswith(b"\xff\xd8")
    _, flat = cv2.imencode(".jpg", np.full((480, 640), 127, dtype=np.uint8))
    with pytest.raises(ValueError, match="blurry"):
        process_photo(flat.tobytes())
    with pytest.raises(ValueError, match="JPEG"):
        process_photo(b"invalid media")


async def test_provider_accepts_only_structured_claims(monkeypatch):
    actual = httpx.AsyncClient

    def send(request):
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"memory_gib":16,"storage_gb":1000}'}}],
                "usage": {"prompt_tokens": 19, "completion_tokens": 11},
            },
        )

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: actual(transport=httpx.MockTransport(send), **kwargs)
    )
    result = await MoonshotProvider("https://provider.example/v1", "test-only", "fixture").suggest(
        "16GiB and 1TB"
    )
    assert result.claims.memory_gib == 16
    assert result.input_tokens == 19
