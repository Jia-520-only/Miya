"""One-shot physical camera capture for non-browser callers.

The browser camera path remains available for live preview and companion mode.
This module is deliberately one-shot: open the device, read a warm frame, encode
it in memory, and always release the device before returning.
"""

from __future__ import annotations

import base64
import logging
import os
import platform
import time
from typing import Any

logger = logging.getLogger("screen_vision.camera_capture")

from .camera_hardware import HARDWARE_LOCK  # noqa: E402 - after logger, before cv2 use

try:
    import cv2

    OPENCV_AVAILABLE = True
except ImportError:  # pragma: no cover - handled at call sites
    cv2 = None  # type: ignore[assignment]
    OPENCV_AVAILABLE = False

# Below this mean luminance a frame is black, which means the device is not really
# delivering - a sleeping phone, or another program holding it. Kept in step with
# camera_stream.BLANK_FRAME_MEAN so both paths agree on what "no picture" means.
BLANK_FRAME_MEAN = float(os.getenv("MIYA_CAMERA_BLANK_MEAN", "4.0"))
# Windows' phone-as-webcam bridge can show a permission prompt after the
# virtual device has already opened. Keep that device alive long enough for the
# user to approve it instead of treating the first black frames as final.
VIRTUAL_CAMERA_STARTUP_GRACE_SECONDS = float(os.getenv("MIYA_VIRTUAL_CAMERA_STARTUP_GRACE", "12.0"))


def make_thumbnail(frame, *, max_width: int = 160, quality: int = 70) -> str:
    """Downscale one raw BGR frame to a small JPEG data URL.

    The panel only needs a memory of what she saw, not the frame itself, so this
    is deliberately tiny: a bounded number of these is kept, and nothing leaves
    the machine.
    """
    try:
        import cv2
    except ImportError:
        return ""
    if frame is None or not getattr(frame, "size", 0):
        return ""
    height, width = frame.shape[:2]
    if width > max_width:
        scale = max_width / float(width)
        frame = cv2.resize(frame, (max_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return ""
    return f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}"


def thumbnail_from_data_url(data_url: str, *, max_size: int = 160, quality: int = 70) -> str:
    """Shrink an already-encoded JPEG/PNG data URL into a small thumbnail.

    The browser hands over a full-size JPEG; the panel only needs a memory of it,
    so this avoids keeping the large one around.
    """
    try:
        import base64 as _base64
        import io as _io

        from PIL import Image
    except ImportError:
        return ""
    header, separator, payload = str(data_url or "").partition(",")
    if not separator or ";base64" not in header:
        return ""
    try:
        image = Image.open(_io.BytesIO(_base64.b64decode(payload))).convert("RGB")
    except Exception:
        return ""
    # A square bounding box preserves the aspect ratio.
    image.thumbnail((max_size, max_size))
    buffer = _io.BytesIO()
    image.save(buffer, format="JPEG", quality=int(quality))
    return "data:image/jpeg;base64," + _base64.b64encode(buffer.getvalue()).decode("ascii")


def _mean_luminance(frame) -> float:
    """Average brightness of a raw frame; sampled, not over every pixel."""
    try:
        import numpy as np

        if frame is None or not getattr(frame, "size", 0):
            return 0.0
        if frame.ndim == 3:
            return float(np.asarray(frame[::8, ::8], dtype="float32").mean())
        return float(np.asarray(frame, dtype="float32").mean())
    except Exception:
        return 0.0


def _backend_candidates() -> list[tuple[str, int]]:
    """Capture backends to try, best first.

    A phone acting as a webcam routinely opens on one Windows backend and yields
    nothing but black frames on another, so "did it open" is not a sufficient
    test - each candidate has to actually produce a picture before it is accepted.
    MSMF is tried first on Windows because it tends to handle virtual and
    phone-provided cameras better than DirectShow.
    """
    candidates: list[tuple[str, int]] = []
    if hasattr(cv2, "CAP_MSMF"):
        candidates.append(("msmf", cv2.CAP_MSMF))
    if hasattr(cv2, "CAP_DSHOW"):
        candidates.append(("dshow", cv2.CAP_DSHOW))
    candidates.append(("default", cv2.CAP_ANY))
    return candidates


def open_camera(index: int, *, width: int, height: int, warmup: int = 8):
    """Open a camera and return ``(capture, backend_name)`` once it really works.

    Tries each backend until one delivers a non-black frame. Returns
    ``(None, last_reason)`` when none of them can, so the caller can report the
    actual reason instead of a generic failure.

    Serialized against every other camera operation: opening a device that
    another thread is already opening blocks rather than failing, and a pile of
    those starves the thread pool Miya's observation loop waits on.
    """
    with HARDWARE_LOCK:
        return _open_camera_unlocked(index, width=width, height=height, warmup=warmup)


def _open_camera_unlocked(index: int, *, width: int, height: int, warmup: int = 8):
    # `cv2` is intentionally replaceable in callers that provide a compatible
    # capture backend (and in hardware probes). Checking the module reference
    # keeps that seam usable even when the optional import was unavailable at
    # module load time.
    if not OPENCV_AVAILABLE and cv2 is None:
        raise RuntimeError(
            "终端摄像头需要 OpenCV。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\camera.txt。"
        )

    last_reason = "没有可用的采集后端"
    try:
        from .camera_names import is_virtual_name, name_for_index

        device_name = name_for_index(index)
        is_virtual = is_virtual_name(device_name)
    except Exception:  # noqa: BLE001 - friendly names are optional
        device_name = ""
        is_virtual = False
    startup_deadline = time.monotonic() + max(0.0, VIRTUAL_CAMERA_STARTUP_GRACE_SECONDS) if is_virtual else 0.0
    for name, flag in _backend_candidates():
        capture = None
        try:
            capture = cv2.VideoCapture(index) if name == "default" else cv2.VideoCapture(index, flag)
            if not capture.isOpened():
                last_reason = f"{name} 无法打开设备"
                _safe_release(capture)
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            brightest = 0.0
            frame = None
            attempts = 0
            while attempts < max(3, int(warmup)) or (is_virtual and time.monotonic() < startup_deadline):
                attempts += 1
                ok, candidate = capture.read()
                if not ok or candidate is None or not getattr(candidate, "size", 0):
                    if is_virtual and time.monotonic() < startup_deadline:
                        time.sleep(0.15)
                    continue
                luminance = _mean_luminance(candidate)
                if luminance > brightest:
                    brightest = luminance
                    frame = candidate
                if luminance >= BLANK_FRAME_MEAN:
                    return capture, name
                if is_virtual and time.monotonic() < startup_deadline:
                    time.sleep(0.15)
            if frame is None:
                last_reason = f"{name} 打开了但没有画面"
            else:
                last_reason = f"{name} 只返回全黑画面（亮度 {brightest:.1f}）"
            _safe_release(capture)
        except Exception as exc:  # noqa: BLE001 - try the next backend
            last_reason = f"{name} 出错: {exc}"
            _safe_release(capture)
    return None, last_reason


def _safe_release(capture) -> None:
    if capture is None:
        return
    try:
        capture.release()
    except Exception:  # noqa: BLE001 - release failures are not actionable
        logger.debug("[CameraCapture] 释放摄像头时出错", exc_info=True)


def capture_camera_frame(
    camera_index: int = 0,
    *,
    width: int = 640,
    height: int = 480,
    warmup_frames: int = 3,
) -> dict[str, Any]:
    """Capture one JPEG data URL from a local physical camera.

    The whole open-read-release cycle holds the hardware lock, so two callers can
    never be inside the same device at once.
    """
    with HARDWARE_LOCK:
        return _capture_camera_frame_unlocked(
            camera_index, width=width, height=height, warmup_frames=warmup_frames,
        )


def _capture_camera_frame_unlocked(
    camera_index: int = 0,
    *,
    width: int = 640,
    height: int = 480,
    warmup_frames: int = 3,
) -> dict[str, Any]:
    cv_module = cv2
    if cv_module is None:
        raise RuntimeError(
            "终端摄像头需要 OpenCV。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\camera.txt。"
        )

    try:
        index = int(camera_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("camera_index 必须是整数。") from exc
    if index < 0:
        raise ValueError("camera_index 不能小于 0。")

    width = max(160, min(int(width), 1920))
    height = max(120, min(int(height), 1080))
    warmup_frames = max(0, min(int(warmup_frames), 30))

    # Try every capture backend until one actually produces a picture. A phone
    # acting as a webcam commonly opens on one Windows backend and returns
    # nothing but black frames on another, so "it opened" proves very little.
    capture, backend = open_camera(index, width=width, height=height,
                                   warmup=max(6, warmup_frames + 4))
    if capture is None:
        raise RuntimeError(f"无法从摄像头 index={index} 得到画面：{backend}。"
                           "请检查设备、系统权限，或手机端推流程序是否还在运行。")

    try:
        frame = None
        for _ in range(warmup_frames + 1):
            ok, candidate = capture.read()
            if ok and candidate is not None and candidate.size:
                frame = candidate
        if frame is None:
            raise RuntimeError("摄像头已打开但没有返回有效画面。")

        ok, encoded = cv_module.imencode(".jpg", frame, [int(cv_module.IMWRITE_JPEG_QUALITY), 78])
        if not ok:
            raise RuntimeError("摄像头画面 JPEG 编码失败。")
        raw = encoded.tobytes()
        return {
            "image_data": f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}",
            "thumbnail": make_thumbnail(frame),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "camera_index": index,
            "backend": backend,
            "source": "camera_terminal",
        }
    finally:
        capture.release()
