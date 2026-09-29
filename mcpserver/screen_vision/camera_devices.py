"""Camera device discovery for Miya Vision.

The browser owns the live preview and the in-page device picker, but several
features need to know what the *machine* actually exposes:

* the terminal ``camera_look`` path takes an OpenCV index, not a browser id;
* the phone-as-webcam and Windows virtual cameras register as devices that can
  open successfully while delivering nothing but black frames;
* more than one camera usually means the phone is a second pair of eyes.

Nothing here captures or stores a frame: a probe reads one frame, records only
its geometry and mean luminance, and releases the device immediately.
"""

from __future__ import annotations

import os
import time
from typing import Any

# Virtual cameras and phone-bridge devices answer immediately but often return
# black until the phone app is actually streaming, so a probe needs a few tries.
PROBE_ATTEMPTS = int(os.getenv("MIYA_CAMERA_PROBE_ATTEMPTS", "4"))
PROBE_INTERVAL_SECONDS = float(os.getenv("MIYA_CAMERA_PROBE_INTERVAL", "0.12"))
MAX_INDEX = int(os.getenv("MIYA_CAMERA_MAX_INDEX", "6"))
DARK_FRAME_MEAN = float(os.getenv("MIYA_CAMERA_BLANK_MEAN", "4.0"))


def _backends() -> list[tuple[str, int]]:
    try:
        import cv2
    except ImportError:
        return []
    options: list[tuple[str, int]] = []
    if hasattr(cv2, "CAP_DSHOW"):
        options.append(("dshow", cv2.CAP_DSHOW))
    if hasattr(cv2, "CAP_MSMF"):
        options.append(("msmf", cv2.CAP_MSMF))
    options.append(("any", cv2.CAP_ANY))
    return options


def _blind_reason(frame, backend_name: str, luminance: float) -> str:
    """Say which kind of blindness this is, because the fixes differ completely.

    A device that opens, reports a live frame size, and still returns pure black
    is a device nothing is feeding - a phone whose screen slept, or a virtual
    camera whose source app stopped. That is a different problem from a camera
    blocked by a privacy switch, and telling Jia "it's dark" helps with neither.
    """
    # Take the size from the frame actually read: asking the backend for its
    # CAP_PROP size reported "unknown" on exactly the broken device that needed
    # the explanation most.
    width = height = 0
    try:
        shape = getattr(frame, "shape", ())
        if len(shape) >= 2:
            height, width = int(shape[0]), int(shape[1])
    except Exception:
        pass
    size_note = f"{width}×{height}" if width and height else "尺寸未知"
    return (
        f"设备打开了、也拿到了 {size_note} 的一帧，但内容是纯黑（亮度 {luminance:.1f}/255，后端 {backend_name}）。"
        "这说明没有程序在真的向它推流——手机息屏、手机上的摄像头 App 退出了，"
        "或者虚拟摄像头没有信号源；不是弥娅这边打不开它。"
    )


def _safe_release(capture: Any) -> None:
    """Release a capture without letting OpenCV's teardown break discovery.

    ``cv2.VideoCapture.release()`` raises "Unknown C++ exception from OpenCV code"
    on Windows once the desktop preview has taken the device (DSHOW backend).
    Because the call sat in a ``finally``, that exception replaced the probe's
    result *and* escaped the ``except`` right above it - so every scan, and every
    frontend poll behind it, logged a traceback instead of an inventory.
    """
    if capture is None:
        return
    try:
        capture.release()
    except Exception:  # noqa: BLE001 - teardown must never be the thing that fails
        pass


def _probe_index(cv2, index: int, width: int, height: int) -> dict[str, Any]:
    """Open one index, read a frame, and classify the result."""
    for backend_name, backend in _backends():
        capture = None
        try:
            capture = cv2.VideoCapture(index, backend)
            if not capture.isOpened():
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            frame = None
            for _ in range(max(1, PROBE_ATTEMPTS)):
                ok, candidate = capture.read()
                if ok and candidate is not None and getattr(candidate, "size", 0):
                    frame = candidate
                    break
                time.sleep(PROBE_INTERVAL_SECONDS)
            if frame is None:
                reported = ""
                try:
                    reported = str(capture.getBackendName() or "")
                except Exception:
                    reported = ""
                return {
                    "index": index, "available": True, "usable": False,
                    "backend": backend_name,
                    "reason": f"设备能打开但没有返回任何画面（后端 {backend_name}{'/' + reported if reported else ''}）"
                              "：通常是设备没被真正推流，或已被别的程序独占",
                }
            mean = float(frame.mean())
            usable = bool(mean >= DARK_FRAME_MEAN)
            return {
                "index": index,
                "available": True,
                "usable": usable,
                "backend": backend_name,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "luminance": round(mean, 2),
                "reason": "" if usable else _blind_reason(
                    frame, backend_name, mean),
            }
        except Exception as exc:  # noqa: BLE001 - a broken device must not break discovery
            return {"index": index, "available": False, "usable": False,
                    "backend": backend_name, "reason": f"探测失败: {exc}"}
        finally:
            _safe_release(capture)
    return {"index": index, "available": False, "usable": False, "reason": "该索引没有可用摄像头"}


def list_camera_devices(*, width: int = 640, height: int = 480, probe: bool = True) -> dict[str, Any]:
    """Enumerate OpenCV camera indices with an optional one-frame probe."""
    try:
        import cv2
    except ImportError:
        return {
            "status": "unavailable",
            "message": "终端摄像头需要 OpenCV。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\camera.txt。",
            "devices": [],
        }
    devices: list[dict[str, Any]] = []
    for index in range(max(1, MAX_INDEX)):
        if not probe:
            # Opening and releasing still goes through the same fragile teardown,
            # so one unopenable index must not end the enumeration.
            capture = None
            try:
                capture = cv2.VideoCapture(index)
                opened = bool(capture.isOpened())
            except Exception:  # noqa: BLE001 - a broken device must not break discovery
                opened = False
            finally:
                _safe_release(capture)
            if opened:
                devices.append({"index": index, "available": True, "usable": None})
            continue
        result = _probe_index(cv2, index, int(width), int(height))
        if result.get("available"):
            devices.append(result)
    usable = [item for item in devices if item.get("usable")]
    return {
        "status": "success",
        "count": len(devices),
        "usable_count": len(usable),
        "devices": devices,
        "default_index": int(usable[0]["index"]) if usable else (int(devices[0]["index"]) if devices else None),
        "message": (
            f"发现 {len(devices)} 个摄像头索引，其中 {len(usable)} 个能返回有效画面。"
            if devices else
            "没有发现任何摄像头索引。"
        ),
    }


def preferred_camera_index(call: dict[str, Any] | None = None) -> int:
    """Resolve the camera index a caller wants, falling back to configuration."""
    call = call or {}
    for key in ("camera_index", "index", "device_index"):
        value = call.get(key)
        if value is None or value == "":
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    configured = os.getenv("MIYA_CAMERA_INDEX", "").strip()
    if configured:
        try:
            return max(0, int(configured))
        except ValueError:
            pass
    return 0
