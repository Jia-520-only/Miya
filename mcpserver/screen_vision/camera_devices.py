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

from .camera_hardware import HARDWARE_LOCK
from .camera_names import dshow_device_names, is_virtual_name, name_for_index

# Virtual cameras and phone-bridge devices answer immediately but often return
# black until the phone app is actually streaming, so a probe needs a few tries.
PROBE_ATTEMPTS = int(os.getenv("MIYA_CAMERA_PROBE_ATTEMPTS", "4"))
PROBE_INTERVAL_SECONDS = float(os.getenv("MIYA_CAMERA_PROBE_INTERVAL", "0.12"))
MAX_INDEX = int(os.getenv("MIYA_CAMERA_MAX_INDEX", "6"))
DARK_FRAME_MEAN = float(os.getenv("MIYA_CAMERA_BLANK_MEAN", "4.0"))
# How long a device that could not be opened at all is left alone. A camera whose
# DirectShow pins refuse to connect blocks every open attempt for seconds, and
# repeating that on each scan is both slow and the one call that has taken this
# process down before. A replug is noticed through the device list changing, not
# through this timer, so the wait never hides a camera coming back.
UNOPENABLE_BACKOFF_SECONDS = float(os.getenv("MIYA_CAMERA_UNOPENABLE_BACKOFF", "600"))

# Indices whose last open attempt failed, and the device list those failures
# belonged to. Both are process-local on purpose: they describe this machine now.
_failed_at: dict[int, float] = {}
_failed_names: list[str] = []


def _forget_failures_when_devices_change(names: list[str]) -> None:
    """Drop remembered failures whenever the set of devices changes.

    This is what makes the backoff safe to have: plugging a camera back in
    changes the list, which clears every remembered failure at once, so a camera
    that reappears - or reappears on a different USB port and starts working - is
    probed on the very next scan instead of waiting out a timer.
    """
    global _failed_names
    if list(names) != _failed_names:
        _failed_names = list(names)
        _failed_at.clear()


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


def _blind_reason(frame, backend_name: str, luminance: float, name: str = "") -> str:
    """Say which kind of blindness this is, because the fixes differ completely.

    A device that opens, reports a live frame size, and still returns pure black
    is a device nothing is feeding - a phone whose screen slept, or a virtual
    camera whose source app stopped. That is a different problem from a physical
    camera that is black because it is covered, held elsewhere, or starved of
    USB bandwidth, and telling Jia "it's dark" helps with neither.

    The device name decides which explanation is offered: naming the camera is
    what makes it possible to say "your phone is not streaming" instead of a
    generic sentence that fits every case and therefore explains none.
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
    label = f"「{name}」（索引里的这台）" if name else "这个设备"
    return (
        f"{label}打开了、也拿到了 {size_note} 的一帧，但内容是纯黑（亮度 {luminance:.1f}/255，后端 {backend_name}）。"
        + _blind_cause(name)
    )


def _blind_cause(name: str) -> str:
    """What to actually do about a device that opens and shows nothing.

    Split out because two paths need the same advice from different evidence: the
    probe, which has a frame to measure, and the observation sweep, which only
    knows that the capture failed.
    """
    if is_virtual_name(name):
        # A phone bridged through Windows is the common case here, and the fix is
        # a switch in an app rather than anything about the camera - so the
        # sentence names the switch. "It's black" sent Jia looking at the wrong
        # end of the problem for days.
        lowered = name.lower()
        if "虚拟摄像头" in name or "virtual camera" in lowered:
            remedy = (
                "如果这是手机提供的摄像头：请在电脑的「手机连接」里打开"
                "「使用手机作为摄像头」（手机端要确认已连接并允许）。"
            )
        else:
            remedy = "手机息屏、手机上的摄像头 App 退出了，或者虚拟摄像头没有信号源。"
        return f"这说明没有程序在真的向它推流——{remedy}这不是弥娅这边打不开它。"
    return (
        "这台是物理摄像头，却一直只返回黑帧：常见原因是镜头被遮挡或隐私开关关着、"
        "被别的程序独占、USB 供电或带宽不足，或者它只有 Media Foundation 那一条路能出画面"
        "（Windows 自带的「相机」应用走的就是那条路）。先用「相机」应用试一次："
        "那边如果有画面，就说明硬件没问题，是采集通道的问题。"
    )


def blank_reason(name: str, detail: str = "") -> str:
    """The same actionable sentence for a capture that failed without a frame.

    The observation sweep never holds a frame when a camera fails, so it used to
    report the raw OpenCV text - which buried the one line that says which switch
    to flip.
    """
    label = f"「{name}」" if name else "这个摄像头"
    prefix = f"{detail}。" if detail else f"{label}这次没有拿到画面。"
    return f"{prefix}{_blind_cause(name)}"


def _unopenable_reason(name: str) -> str:
    """Why a device the operating system lists could not be opened at all."""
    label = f"「{name}」" if name else "这个索引"
    return (
        f"系统里能看到{label}，但 DirectShow 打不开它："
        "常见原因是设备被别的程序独占、USB 供电或带宽不足，"
        "或者它的 DirectShow 输出引脚连不上——有些较新的摄像头只有 Media Foundation 这一条路能出画面，"
        "而当前安装的 OpenCV 没有编译 Media Foundation 支持。"
        "用 Windows 自带的「相机」应用试一次可以区分这两种情况。"
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


def _probe_index(cv2, index: int, width: int, height: int, name: str = "") -> dict[str, Any]:
    """Probe one index, serialized against every other camera operation.

    Opening a camera is not a safe thing to do concurrently: a second attempt
    while another thread holds the device blocks instead of failing, and enough
    of them at once starve the thread pool that Miya's own observation loop waits
    on. See :mod:`mcpserver.screen_vision.camera_hardware`.
    """
    with HARDWARE_LOCK:
        return _probe_index_unlocked(cv2, index, width, height, name)


def _probe_index_unlocked(cv2, index: int, width: int, height: int, name: str = "") -> dict[str, Any]:
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
                    "name": name,
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
                "name": name,
                "backend": backend_name,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "luminance": round(mean, 2),
                "reason": "" if usable else _blind_reason(
                    frame, backend_name, mean, name),
            }
        except Exception as exc:  # noqa: BLE001 - a broken device must not break discovery
            return {"index": index, "available": False, "usable": False,
                    "name": name, "backend": backend_name, "reason": f"探测失败: {exc}"}
        finally:
            _safe_release(capture)
    return {"index": index, "available": False, "usable": False,
            "name": name, "reason": "该索引没有可用摄像头"}


def list_camera_devices(*, width: int = 640, height: int = 480, probe: bool = True) -> dict[str, Any]:
    """Enumerate OpenCV camera indices with an optional one-frame probe.

    The range covered is the wider of ``MAX_INDEX`` and the number of devices
    DirectShow reports. Enumerating only what happens to open hid the cameras
    that matter most: a plugged-in UVC camera whose DirectShow pins refuse to
    connect used to be indistinguishable from "no camera here", so the panel
    could not say "this device exists but will not open" - which is the single
    most useful sentence for diagnosing one.
    """
    try:
        import cv2
    except ImportError:
        return {
            "status": "unavailable",
            "message": "终端摄像头需要 OpenCV。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\camera.txt。",
            "devices": [],
            "names": [],
            "names_available": False,
        }
    names = dshow_device_names()
    _forget_failures_when_devices_change(names)
    devices: list[dict[str, Any]] = []
    # With a device list in hand there is nothing to guess: probing indices past
    # the end of it only opens devices that do not exist, and every open is the
    # riskiest call this process makes. Without ffmpeg the old index range is the
    # only way to find anything.
    # DirectShow names are useful labels, but they are not a complete device
    # inventory: Windows phone-camera bridges and Media Foundation-only drivers
    # can be addressable by OpenCV without appearing in ffmpeg's dshow list.
    # Always probe the configured index window as well, then retain named
    # devices that fail so the UI can explain their state.
    limit = max(1, MAX_INDEX, len(names))
    for index in range(limit):
        name = name_for_index(index, names=names)
        if not probe:
            # Enumeration without touching hardware. Opening each device to ask
            # "does this one open?" sounded cheap and was not: a camera whose
            # DirectShow pins refuse to connect makes the open attempt block for
            # seconds, so a caller polling this took ~27s per call. Names come
            # from the device list instead, and whether a camera works is
            # answered by the probe path or by the manager's cached scan.
            if not name:
                continue
            devices.append({
                "index": index,
                "available": None,
                "usable": None,
                "name": name,
                "reason": "",
            })
            continue
        failed_at = _failed_at.get(index, 0.0)
        if failed_at and (time.time() - failed_at) < UNOPENABLE_BACKOFF_SECONDS:
            # Leave a device that refuses to open alone for a while. Retrying it
            # on every scan cost seconds each time and repeated the one OpenCV
            # call that has taken this whole process down before; a camera that
            # is simply unplugged is caught by the device list changing instead.
            devices.append({
                "index": index,
                "available": False,
                "usable": False,
                "name": name,
                "backoff": True,
                "reason": _unopenable_reason(name)
                + f"（{int(UNOPENABLE_BACKOFF_SECONDS)} 秒内不再重复探测：反复去开一台连不上的设备既慢又危险）",
            })
            continue
        result = _probe_index(cv2, index, int(width), int(height), name)
        if result.get("available"):
            _failed_at.pop(index, None)
        else:
            _failed_at[index] = time.time()
        # A named device stays in the inventory even when it cannot be opened:
        # "your 4K camera is here but will not open" is information, while
        # dropping it silently is what made the panel look complete and wrong.
        if not result.get("available") and not name:
            continue
        if not result.get("available"):
            result["reason"] = _unopenable_reason(name)
        devices.append(result)
    usable = [item for item in devices if item.get("usable")]
    unopenable = [item for item in devices if item.get("available") is False]
    unchecked = [item for item in devices if item.get("available") is None]
    return {
        "status": "success",
        "count": len(devices),
        "usable_count": len(usable),
        "unopenable_count": len(unopenable),
        "checked": bool(probe),
        "devices": devices,
        "names": names,
        "names_available": bool(names),
        "default_index": int(usable[0]["index"]) if usable else (int(devices[0]["index"]) if devices else None),
        "message": _inventory_message(devices, usable, unopenable, unchecked),
    }


def _inventory_message(
    devices: list[dict[str, Any]],
    usable: list[dict[str, Any]],
    unopenable: list[dict[str, Any]],
    unchecked: list[dict[str, Any]] | None = None,
) -> str:
    """One honest sentence about the whole inventory.

    The counts are not interchangeable: a camera that returns no picture and a
    camera that cannot be opened need opposite next steps, so they are never
    folded into a single "not usable" number. A name-only enumeration says so
    instead of reporting zero working cameras.
    """
    unchecked = unchecked or []
    if not devices:
        return "没有发现任何摄像头。"
    if unchecked and not (usable or unopenable):
        return "发现 " + "、".join(
            str(item.get("name") or f"索引 {item.get('index')}") for item in devices
        ) + "（本次只列设备名，没有探测画面）。"
    sleeping = len(devices) - len(usable) - len(unopenable) - len(unchecked)
    parts = [f"发现 {len(devices)} 台摄像头，其中 {len(usable)} 台正在出画面"]
    if sleeping:
        parts.append(f"{sleeping} 台能打开但没有画面")
    if unopenable:
        blocked = "、".join(
            str(item.get("name") or f"索引 {item.get('index')}") for item in unopenable
        )
        parts.append(f"{len(unopenable)} 台打不开（{blocked}）")
    if unchecked:
        parts.append(f"{len(unchecked)} 台未探测")
    return "；".join(parts) + "。"


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
