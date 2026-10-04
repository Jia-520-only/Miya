"""Sharing one camera between the desktop preview and Miya's own eyes.

Only one process can hold a camera, so the pool's ownership rules are what keep
the preview smooth and the observation loop honest at the same time. These tests
pin the rules, because violating them either steals the camera from the preview
or makes Miya read stale frames.
"""

from __future__ import annotations

import time

import pytest

from mcpserver.screen_vision.camera_stream import (
    BROWSER_OWNERSHIP_GRACE_SECONDS,
    OWNER_BACKEND,
    OWNER_BROWSER,
    OWNER_IDLE,
    CameraFramePool,
    FrameBuffer,
)


@pytest.fixture()
def pool() -> CameraFramePool:
    return CameraFramePool()


def _frame():
    """A bright frame. All-zero pixels are black, and black is refused now."""
    import numpy as np

    return np.full((8, 8, 3), 120, dtype=np.uint8)


def test_a_fresh_pool_owns_nothing(pool: CameraFramePool):
    assert pool.owner(0) == OWNER_IDLE
    assert pool.latest(0) is None
    assert pool.describe()["backend_owned"] == []


def test_the_browser_frame_becomes_the_buffer_and_the_owner(pool: CameraFramePool):
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA", thumbnail="data:image/jpeg;base64,TT")
    buffer = pool.latest(0)
    assert buffer is not None
    assert buffer.owner == OWNER_BROWSER
    assert buffer.image_data.endswith("AAAA")
    assert buffer.thumbnail.endswith("TT")
    assert pool.describe()["browser_owned"] == [0]


def test_the_backend_never_starts_a_reader_on_a_browser_owned_camera(pool: CameraFramePool):
    """Doing so would steal the device out from under the preview."""
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    assert pool.start_reader(0) is False
    assert pool.describe()["readers_running"] == []


def test_browser_ownership_outlives_the_freshness_of_its_frame(pool: CameraFramePool):
    """Regression: the preview shares every 15s but a frame is only fresh for 30s.

    Gating ownership on frame freshness alone announced "the preview is gone"
    whenever two shares were missed, and the backend then opened a camera the
    browser still held. Both sides read black and reopened in a loop - the whole
    "连续 4 次全黑，释放设备" cycle. Ownership is about who holds the hardware.
    """
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    # The copy we hold has gone stale...
    pool.buffer(0).at = time.time() - 45
    assert pool.latest(0) is None, "过期的帧不该再拿去推理"
    # ...but the browser is still holding the device, so it is still the owner.
    assert pool.browser_owns(0) is True
    assert pool.start_reader(0) is False
    assert pool.describe()["readers_running"] == []


def test_browser_ownership_does_expire(pool: CameraFramePool):
    """Once the preview has really stopped, the backend must be allowed back in."""
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    pool.buffer(0).at = time.time() - (BROWSER_OWNERSHIP_GRACE_SECONDS + 30)
    pool._browser_touched[0] = time.time() - (BROWSER_OWNERSHIP_GRACE_SECONDS + 30)
    assert pool.browser_owns(0) is False


def test_the_preview_taking_over_causes_the_backend_to_stand_down(pool: CameraFramePool):
    pool.set_owner(0, OWNER_BACKEND)
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    # The buffer now belongs to the preview, and any reader was signalled away.
    assert pool.owner(0) == OWNER_BROWSER
    assert pool.describe()["readers_running"] == []


def test_a_backend_frame_is_ignored_once_the_browser_owns_the_camera(pool: CameraFramePool):
    """A reader that was mid-read when the preview claimed the device must not
    overwrite the preview's fresher frame."""
    import numpy as np

    pool.publish_browser_frame(0, "data:image/jpeg;base64,BROWSER")
    pool.publish_backend_frame(0, np.zeros((8, 8, 3), dtype=np.uint8), width=8, height=8)
    assert pool.latest(0).image_data.endswith("BROWSER")


def test_claiming_for_the_backend_releases_the_preview(pool: CameraFramePool):
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    pool.set_owner(0, OWNER_BACKEND)
    assert pool.owner(0) == OWNER_BACKEND
    # The stale preview frame is still served until it ages out, but ownership
    # has moved, so a reader may now start.
    assert pool.describe()["browser_owned"] == []


# --- freshness -------------------------------------------------------------


def test_a_stale_frame_is_not_handed_to_inference(pool: CameraFramePool):
    """Acting on a minutes-old frame would describe a moment that has passed."""
    pool.publish_browser_frame(20, "data:image/jpeg;base64,AAAA")
    buffer = pool.buffer(20)
    buffer.at = time.time() - 60
    assert pool.latest(20) is None
    assert pool.latest_for_inference(20) is None


def test_without_a_live_reader_an_old_frame_is_refused(pool: CameraFramePool):
    """With nothing keeping the camera open, an old frame is just old."""
    pool.publish_browser_frame(20, "data:image/jpeg;base64,AAAA")
    pool.buffer(20).at = time.time() - 600
    assert pool.latest_for_inference(20) is None


def test_a_reader_that_just_published_is_trusted(pool: CameraFramePool):
    """While a reader is feeding frames, its frame is current by construction.

    A fixed age limit shorter than the observation interval made every round
    reopen the device instead of using the reader - which also meant fighting the
    reader for the same camera.
    """
    pool.publish_backend_frame(0, _frame(), width=640, height=480)

    class _LiveReader:
        alive = True

    pool._readers[0] = _LiveReader()  # type: ignore[assignment]
    assert pool.latest_for_inference(0) is not None


def test_a_reader_that_stopped_publishing_is_not_trusted(pool: CameraFramePool):
    """Regression: a live thread is not proof that its frame is current.

    A reader blocked in ``read()``, or one whose device stopped delivering, stays
    alive while its last frame ages. Serving that frame is how one frozen picture
    was interpreted as the present again and again - her impressions repeated a
    posture to the decimal, minutes apart, because they were literally the same
    bytes.
    """
    pool.publish_backend_frame(0, _frame(), width=640, height=480)

    class _LiveReader:
        alive = True

    pool._readers[0] = _LiveReader()  # type: ignore[assignment]
    pool.buffer(0).at = time.time() - 300
    assert pool.latest_for_inference(0) is None, "读帧线程不再出帧时，缓存不能当成现在的画面"


def test_a_stalled_reader_gives_the_device_up(monkeypatch, pool: CameraFramePool):
    """Frames that never arrive must not leave the device held forever."""
    from mcpserver.screen_vision import camera_capture, camera_stream
    from mcpserver.screen_vision.camera_stream import _PersistentReader

    monkeypatch.setattr(camera_stream, "READER_STALL_SECONDS", 0.05)
    monkeypatch.setattr(camera_stream, "READER_SLEEP_SECONDS", 0.001)

    class _DeadCapture:
        def read(self):
            return False, None

        def release(self):
            pass

    monkeypatch.setattr(camera_capture, "open_camera",
                        lambda *a, **k: (_DeadCapture(), "dshow"), raising=False)

    _PersistentReader(pool, 0, 320, 240)._run()

    assert "没有拿到画面" in pool.buffer(0).error


def test_a_frozen_stream_is_treated_as_a_broken_device(monkeypatch, pool: CameraFramePool):
    """A picture that keeps arriving but never changes is not a live camera.

    A stalled virtual camera passes every other check - not black, not old, the
    reader alive - so this is the only thing between it and Miya describing one
    picture as the present over and over.
    """
    import numpy as np

    from mcpserver.screen_vision import camera_capture, camera_stream
    from mcpserver.screen_vision.camera_stream import _PersistentReader

    monkeypatch.setattr(camera_stream, "FROZEN_AFTER_SECONDS", 0.05)
    monkeypatch.setattr(camera_stream, "READER_SLEEP_SECONDS", 0.001)

    frame = np.full((64, 64, 3), 120, dtype=np.uint8)

    class _FrozenCapture:
        def read(self):
            return True, frame

        def release(self):
            pass

    monkeypatch.setattr(camera_capture, "open_camera",
                        lambda *a, **k: (_FrozenCapture(), "dshow"), raising=False)
    monkeypatch.setattr(camera_capture, "make_thumbnail", lambda *a, **k: "", raising=False)

    _PersistentReader(pool, 0, 320, 240)._run()

    assert "一模一样" in pool.buffer(0).error


def test_a_live_stream_is_not_mistaken_for_a_frozen_one():
    """The fingerprint is an exact subsample match, so it fails safe.

    It samples every 16th pixel: any change on a sampled position breaks the
    match, and for a frozen verdict every change would have to land off the
    subsample for half a minute straight. Sensor noise never does that, so the
    check can miss a change but cannot invent a frozen stream.
    """
    import numpy as np

    from mcpserver.screen_vision.camera_stream import _frame_fingerprint

    rng = np.random.default_rng(7)
    frame = rng.integers(100, 140, size=(64, 64, 3), dtype=np.uint8)

    assert _frame_fingerprint(frame) == _frame_fingerprint(frame.copy())
    assert _frame_fingerprint(frame) != _frame_fingerprint(rng.integers(100, 140, size=(64, 64, 3), dtype=np.uint8))

    touched_sample = frame.copy()
    touched_sample[0, 0, 0] = int(touched_sample[0, 0, 0]) + 1
    assert _frame_fingerprint(frame) != _frame_fingerprint(touched_sample)

    touched_between = frame.copy()
    touched_between[1, 1, 0] = int(touched_between[1, 1, 0]) + 1
    assert _frame_fingerprint(frame) == _frame_fingerprint(touched_between)


def test_a_dead_reader_lets_its_frame_go_stale(pool: CameraFramePool):
    """A reader that stopped publishing must not be trusted forever."""
    pool.publish_backend_frame(0, _frame(), width=640, height=480)

    class _DeadReader:
        alive = False

    pool._readers[0] = _DeadReader()  # type: ignore[assignment]
    pool.buffer(0).at = time.time() - 300
    assert pool.latest_for_inference(0) is None


def test_an_empty_buffer_reports_itself_unusable():
    buffer = FrameBuffer(index=0)
    assert buffer.is_usable() is False
    assert buffer.age() == float("inf")
    assert buffer.to_dict()["has_frame"] is False


def test_age_and_reporting_are_plain_numbers(pool: CameraFramePool):
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    described = pool.latest(0).to_dict()
    assert described["owner"] == OWNER_BROWSER
    assert described["age_seconds"] is not None and described["age_seconds"] >= 0
    assert described["has_frame"] is True


def test_a_reader_frame_is_measured_for_brightness(pool: CameraFramePool):
    """Without this, a black picture was indistinguishable from a good one."""
    import numpy as np

    pool.publish_backend_frame(0, np.full((8, 8, 3), 130, dtype=np.uint8), width=8, height=8)
    bright = pool.buffer(0)
    assert bright.luminance is not None and bright.luminance > 100
    assert bright.is_blank is False

    pool.publish_backend_frame(0, np.zeros((8, 8, 3), dtype=np.uint8), width=8, height=8)
    assert pool.buffer(0).is_blank is True


def test_a_blank_frame_is_never_served_for_inference(pool: CameraFramePool):
    """A sleeping phone must not be read as 'nobody is there'.

    The reader used to publish blackness as a valid frame, so consumers were told
    the camera was working while every observation was of a black rectangle.
    """
    import numpy as np

    class _LiveReader:
        alive = True

    pool._readers[0] = _LiveReader()  # type: ignore[assignment]
    pool.publish_backend_frame(0, np.zeros((8, 8, 3), dtype=np.uint8), width=8, height=8)
    assert pool.latest_for_inference(0) is None, "黑帧绝不能进入推理"


def test_a_blank_frame_is_kept_for_display_only(pool: CameraFramePool):
    """The panel may still show the black picture; it just must not reason on it."""
    import numpy as np

    pool.publish_backend_frame(0, np.zeros((8, 8, 3), dtype=np.uint8), width=8, height=8)
    assert pool.latest(0) is not None
    assert pool.latest_for_inference(0) is None


# --- errors and shutdown ---------------------------------------------------


def test_an_error_is_remembered_on_the_buffer(pool: CameraFramePool):
    pool.note_error(1, "无法打开摄像头")
    assert pool.buffer(1).error == "无法打开摄像头"
    assert pool.latest(1) is None


def test_publishing_a_frame_clears_a_previous_error(pool: CameraFramePool):
    pool.note_error(0, "无法打开摄像头")
    pool.publish_browser_frame(0, "data:image/jpeg;base64,AAAA")
    assert pool.buffer(0).error == ""


def test_stopping_a_reader_that_does_not_exist_is_harmless(pool: CameraFramePool):
    pool.stop_reader(3)
    pool.stop_all()
    assert pool.describe()["readers_running"] == []


@pytest.mark.parametrize("stop_all", [False, True])
def test_a_stopping_reader_keeps_ownership_until_it_exits(pool: CameraFramePool, stop_all, monkeypatch):
    import threading
    from types import SimpleNamespace

    from mcpserver.screen_vision import camera_stream

    reader = SimpleNamespace(alive=True, _stop=threading.Event())
    reader.stop = lambda: reader._stop.set()
    pool._readers[0] = reader
    if stop_all:
        pool.stop_all()
    else:
        pool.stop_reader(0)

    assert pool.reader(0) is reader
    assert pool.start_reader(0) is False

    replacement = SimpleNamespace(alive=True, start=lambda: True)
    monkeypatch.setattr(camera_stream, "_PersistentReader", lambda *_args: replacement)
    reader.alive = False

    assert pool.start_reader(0) is True
    assert pool.reader(0) is replacement


def test_reader_ready_unblocks_even_when_it_fails(pool: CameraFramePool):
    """A caller waiting on a reader must not hang forever if it cannot open."""
    from mcpserver.screen_vision.camera_stream import _PersistentReader

    reader = _PersistentReader(pool, 99, 320, 240)
    reader.ready.set()  # simulate "gave up"
    assert reader.wait_ready(0.5) is False
