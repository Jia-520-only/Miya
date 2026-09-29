"""One unopenable camera must not break the whole inventory.

Regression: on Windows, ``cv2.VideoCapture.release()`` raises "Unknown C++
exception" once the desktop preview holds the device. Because the release lived
in a ``finally``, that exception replaced the probe's result *and* escaped the
``except`` directly above it - so every scan logged a traceback and the frontend
poll behind it got nothing.

``cv2`` is injected into ``sys.modules`` rather than probed for real, so these
tests describe the machine they run on instead of depending on it.
"""

from __future__ import annotations

import sys

from mcpserver.screen_vision import camera_devices

# ``tests/conftest.py`` swaps ``camera_devices.list_camera_devices`` for a stub
# during every test, to keep the suite off the physical hardware. Capture the
# real function here, at import time, so these tests can drive it with a fake cv2
# instead of asserting against the stub.
_REAL_LIST_CAMERA_DEVICES = camera_devices.list_camera_devices


class _Cv2Error(Exception):
    """Stands in for cv2.error, which is what OpenCV really raises."""


class _Capture:
    """A device whose teardown always blows up, like DSHOW under the preview."""

    def __init__(self, *, opened: bool = True, frame=None) -> None:
        self._opened = opened
        self._frame = frame
        self.released = 0

    def isOpened(self) -> bool:
        return self._opened

    def set(self, *_args) -> bool:
        return True

    def read(self):
        return (self._frame is not None), self._frame

    def getBackendName(self) -> str:
        return "dshow"

    def release(self) -> None:
        self.released += 1
        raise _Cv2Error("Unknown C++ exception from OpenCV code")


class _Frame:
    shape = (480, 640, 3)

    def mean(self) -> float:
        return 88.0

    @property
    def size(self) -> int:
        return 480 * 640 * 3


class _FakeCv2:
    """Just enough of the cv2 surface for discovery, with a chosen device map."""

    CAP_DSHOW = 700
    CAP_MSMF = 1400
    CAP_ANY = 0
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self, devices) -> None:
        # devices: index -> "usable" | "blank" | "unopenable" | None (absent)
        self.devices = devices
        self.captures: list[_Capture] = []

    def VideoCapture(self, index, backend=None):
        kind = self.devices.get(index)
        if kind == "usable":
            capture = _Capture(frame=_Frame())
        elif kind == "blank":
            capture = _Capture(frame=None)
        else:
            capture = _Capture(opened=False)
        self.captures.append(capture)
        return capture


def _prepare(monkeypatch, fake) -> None:
    monkeypatch.setitem(sys.modules, "cv2", fake)
    monkeypatch.setattr(camera_devices, "PROBE_ATTEMPTS", 1)
    monkeypatch.setattr(camera_devices, "PROBE_INTERVAL_SECONDS", 0.0)


def test_a_release_that_raises_does_not_erase_a_successful_probe(monkeypatch):
    """The probe result must survive its own teardown."""
    fake = _FakeCv2({0: "usable"})
    _prepare(monkeypatch, fake)

    result = camera_devices._probe_index(fake, 0, 640, 480)

    assert result["available"] is True
    assert result["usable"] is True
    assert result["luminance"] == 88.0
    assert fake.captures[0].released == 1, "设备必须被真正释放"


def test_a_release_that_raises_does_not_erase_a_failed_probe(monkeypatch):
    fake = _FakeCv2({3: "unopenable"})
    _prepare(monkeypatch, fake)

    result = camera_devices._probe_index(fake, 3, 640, 480)

    assert result == {"index": 3, "available": False, "usable": False,
                      "reason": "该索引没有可用摄像头"}


def test_discovery_still_reports_the_inventory(monkeypatch):
    fake = _FakeCv2({0: "usable", 1: "blank"})
    _prepare(monkeypatch, fake)
    monkeypatch.setattr(camera_devices, "MAX_INDEX", 3)

    report = _REAL_LIST_CAMERA_DEVICES(probe=True)

    assert report["status"] == "success"
    assert [item["index"] for item in report["devices"]] == [0, 1]
    assert report["usable_count"] == 1
    assert report["default_index"] == 0


def test_the_manager_scan_keeps_a_report_instead_of_a_traceback(monkeypatch):
    """The exact symptom: a scan that failed on teardown reported nothing."""
    from mcpserver.screen_vision import camera_manager

    fake = _FakeCv2({0: "usable", 1: "blank"})
    _prepare(monkeypatch, fake)
    monkeypatch.setattr(camera_devices, "MAX_INDEX", 2)

    manager = camera_manager.CameraManager()
    sources = manager.scan(force=True)

    assert sorted(sources) == [0, 1]
    assert sources[0].usable is True
    assert sources[1].usable is False
