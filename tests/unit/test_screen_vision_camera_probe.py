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
        # Which indices were actually opened, in order. Separate from `captures`
        # because one probe may open a device once per capture backend, and the
        # question these tests ask is "did it touch that camera at all".
        self.opens: list[int] = []

    def VideoCapture(self, index, backend=None):
        self.opens.append(index)
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
    # Device names come from ffmpeg and describe the machine the tests run on, so
    # they are stubbed here too. Left real, the range of indices probed would
    # depend on which cameras the developer happens to have plugged in - which is
    # exactly how these tests started failing the moment a 4K camera was attached.
    monkeypatch.setattr(camera_devices, "dshow_device_names", lambda **_kwargs: [])
    camera_devices._failed_at.clear()
    camera_devices._failed_names = []


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
                      "name": "", "reason": "该索引没有可用摄像头"}


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
    monkeypatch.setattr(camera_manager, "list_camera_devices", _REAL_LIST_CAMERA_DEVICES)

    manager = camera_manager.CameraManager()
    sources = manager.scan(force=True)

    assert sorted(sources) == [0, 1]
    assert sources[0].usable is True
    assert sources[1].usable is False


def _use_names(monkeypatch, names):
    monkeypatch.setattr(camera_devices, "dshow_device_names", lambda **_kwargs: list(names))
    camera_devices._failed_at.clear()
    camera_devices._failed_names = []


def test_an_unopenable_device_is_not_hammered_on_every_scan(monkeypatch):
    """A camera that will not open is left alone for a while.

    Opening it cost seconds on every scan, and it is the one OpenCV call that has
    taken this whole process down before. It stays in the inventory - "it is here
    but will not open" is the useful answer - it is just not retried each pass.
    """
    fake = _FakeCv2({0: "usable", 1: "unopenable"})
    _prepare(monkeypatch, fake)
    _use_names(monkeypatch, ["Integrated Camera", "4K USB Camera"])

    first = _REAL_LIST_CAMERA_DEVICES(probe=True)
    assert [item["index"] for item in first["devices"]] == [0, 1]
    assert first["unopenable_count"] == 1
    assert first["devices"][1]["name"] == "4K USB Camera"

    before = len(fake.opens)
    second = _REAL_LIST_CAMERA_DEVICES(probe=True)

    reopened = fake.opens[before:]
    assert 1 not in reopened, "打不开的那一路不该在退避期内被再开一次"
    assert reopened == [0], "第二次扫描只应该去开还能用的那一路"
    skipped = next(item for item in second["devices"] if item["index"] == 1)
    assert skipped.get("backoff") is True, "退避期间仍要出现在清单里，并说明原因"
    assert "4K USB Camera" in skipped["reason"]
    camera_devices._failed_at.clear()
    camera_devices._failed_names = []


def test_replugging_a_camera_clears_the_backoff(monkeypatch):
    """The device list changing is what makes the backoff safe.

    Waiting out a timer would mean a camera that was just plugged back in - or
    moved to a port where it finally works - stays invisible for up to ten
    minutes. A change in the list clears every remembered failure at once.
    """
    fake = _FakeCv2({0: "usable", 1: "unopenable"})
    _prepare(monkeypatch, fake)
    _use_names(monkeypatch, ["Integrated Camera", "4K USB Camera"])

    _REAL_LIST_CAMERA_DEVICES(probe=True)
    before = len(fake.opens)

    # Something was plugged in: a third device appears in the list.
    monkeypatch.setattr(camera_devices, "dshow_device_names",
                        lambda **_kwargs: ["Integrated Camera", "4K USB Camera", "Phone Camera"])
    third = _REAL_LIST_CAMERA_DEVICES(probe=True)

    assert 1 in fake.opens[before:], "设备清单变了以后，之前打不开的那一路必须重新探一次"
    assert [item["index"] for item in third["devices"]] == [0, 1, 2]
    camera_devices._failed_at.clear()
    camera_devices._failed_names = []


class _BlackFrame:
    shape = (720, 1280, 3)

    def mean(self) -> float:
        return 1.4


def test_a_black_phone_camera_says_which_switch_to_flip():
    """A black frame from a phone has one specific fix, and it is not "the camera".

    Generic "it's dark" advice sent Jia looking at the camera for days while the
    actual answer was a toggle in the Phone Link app. The sentence has to name
    the toggle - that is the whole value of knowing the device's name.
    """
    reason = camera_devices._blind_reason(
        _BlackFrame(), "dshow", 1.4, "Xiaomi 15 Pro (Windows 虚拟摄像头)",
    )

    assert "手机连接" in reason, "手机虚拟摄像头全黑时必须指出「手机连接」里那个开关"
    assert "使用手机作为摄像头" in reason
    assert "用「相机」应用试一次" not in reason, "不该把物理摄像头的排查建议套到手机上"


def test_a_black_physical_camera_gets_the_hardware_advice():
    """The opposite direction: never tell him to check his phone for a UVC camera."""
    reason = camera_devices._blind_reason(_BlackFrame(), "dshow", 1.4, "4K USB Camera")

    assert "物理摄像头" in reason
    assert "相机" in reason, "物理摄像头全黑时应该建议先用系统相机应用做对照"
    assert "手机连接" not in reason
