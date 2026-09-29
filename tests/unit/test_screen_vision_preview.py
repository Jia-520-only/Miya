"""The backend-angle preview must not steal the camera from its own reader.

The panel refreshes `/api/vision/preview/{index}` every three seconds. When the
pool had no cached frame the endpoint used to open the device itself - while the
persistent reader was holding it. One of the two then reads black, the other gets
"Unknown C++ exception", and they take turns releasing the device forever, which
is what the log showed as an endless "连续 4 次全黑，释放设备" cycle.
"""

from __future__ import annotations

import time

import pytest

from mcpserver.screen_vision import camera_capture
from mcpserver.screen_vision.camera_stream import OWNER_BACKEND, get_camera_pool


@pytest.fixture()
def client():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from core.web_api.miya_api import MiyaAPI

    assert fastapi is not None
    api = MiyaAPI()
    app = fastapi.FastAPI()
    app.include_router(api.router)
    return TestClient(app)


@pytest.fixture()
def pool():
    camera_pool = get_camera_pool()
    camera_pool.stop_all()
    camera_pool._buffers = {}
    yield camera_pool
    camera_pool.stop_all()
    camera_pool._buffers = {}


def _publish(pool, age_seconds: float = 0.0) -> None:
    import numpy as np

    pool.publish_backend_frame(0, np.full((8, 8, 3), 120, dtype=np.uint8), width=8, height=8)
    pool.buffer(0).at = time.time() - age_seconds


def _hold_with_a_live_reader(pool) -> None:
    """Pretend a persistent reader owns index 0 and is still feeding it."""
    import threading

    class _LiveReader:
        alive = True

        def __init__(self) -> None:
            self._stop = threading.Event()

        def stop(self) -> None:
            self._stop.set()

    pool._readers[0] = _LiveReader()  # type: ignore[assignment]


def test_a_cached_frame_is_served_as_a_jpeg(client, pool):
    _publish(pool)
    response = client.get("/api/vision/preview/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content[:2] == b"\xff\xd8", "返回的应该是 JPEG"


def test_a_stale_frame_never_makes_the_endpoint_open_the_device(client, pool, monkeypatch):
    """The regression: the preview opened the camera behind the reader's back."""
    _publish(pool, age_seconds=600)

    def _boom(*_args, **_kwargs):
        raise AssertionError("预览接口不该自己去开设备，那会和常驻读帧抢同一个摄像头")

    monkeypatch.setattr(camera_capture, "capture_camera_frame", _boom)
    pool.set_owner(0, OWNER_BACKEND)
    _hold_with_a_live_reader(pool)

    response = client.get("/api/vision/preview/0?max_age=0")

    assert response.status_code == 404
    assert "没有画面" in response.json()["detail"]


def test_a_reader_that_arrives_late_still_fills_the_view(client, pool, monkeypatch):
    """Waiting for the reader is what makes the first view work at all."""
    _publish(pool, age_seconds=600)
    monkeypatch.setattr(
        camera_capture, "capture_camera_frame",
        lambda *_a, **_k: pytest.fail("不该走直接取帧这条路"),
    )
    _hold_with_a_live_reader(pool)
    # The reader publishes a fresh frame while the request is waiting, which is
    # exactly what a warming-up reader does a second or two after being asked.
    pool.buffer(0).at = time.time()

    response = client.get("/api/vision/preview/0?max_age=5")
    assert response.status_code == 200
    assert response.content[:2] == b"\xff\xd8"
