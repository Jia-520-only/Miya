"""Only one thread may be inside a camera at a time.

Measured failure: a thread dump taken while Miya's observation loop had been
silent for five minutes showed ten threads inside camera open and probe code at
once - the inventory probe, a persistent reader, one-shot captures and the
desktop panel's polling all piled onto the same USB bus. DirectShow does not fail
fast on a second open; it blocks, and the observation loop was simply queued
behind the pile until its own await never returned.

These tests pin the two things that stop that from happening again: the shared
hardware lock, and a finite deadline on one observation round.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_two_camera_opens_never_overlap(monkeypatch):
    from mcpserver.screen_vision import camera_capture

    concurrent = 0
    peak = 0
    guard = threading.Lock()

    class _Capture:
        def isOpened(self) -> bool:
            nonlocal concurrent, peak
            with guard:
                concurrent += 1
                peak = max(peak, concurrent)
            # Stand in for the device warm-up every real open pays.
            time.sleep(0.05)
            with guard:
                concurrent -= 1
            return False

        def release(self) -> None:
            pass

    class _Cv2:
        CAP_DSHOW = 700
        CAP_MSMF = 1400
        CAP_ANY = 0
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4

        def VideoCapture(self, *_args):
            return _Capture()

    monkeypatch.setattr(camera_capture, "cv2", _Cv2())

    errors: list[str] = []

    def worker() -> None:
        try:
            camera_capture.capture_camera_frame(0)
        except Exception as exc:  # noqa: BLE001 - the fake never yields a frame
            errors.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert peak == 1, f"最多同时有 {peak} 个线程在开摄像头，硬件锁没有生效"
    assert len(errors) == 4, "四个线程都应该得到「没有画面」这个结果"


def test_the_lock_is_shared_by_every_camera_entry_point():
    """A lock that only one module uses is not a lock."""
    from mcpserver.screen_vision import camera_capture, camera_devices
    from mcpserver.screen_vision.camera_hardware import HARDWARE_LOCK

    assert camera_capture.HARDWARE_LOCK is HARDWARE_LOCK
    assert camera_devices.HARDWARE_LOCK is HARDWARE_LOCK


def test_one_observation_round_has_a_deadline():
    """Source-level: an await with no deadline is what stopped her watching.

    The lock removes the pile-up that caused it; the deadline is what keeps a
    single blocked DirectShow call or a hung model request from ending her
    senses for the rest of the process.
    """
    source = (ROOT / "mcpserver" / "screen_vision" / "vision_agent.py").read_text(encoding="utf-8")

    assert "asyncio.wait_for(self.tick()" in source, "观察轮必须带超时"
    assert "TICK_TIMEOUT_SECONDS" in source
