"""One-shot physical camera capture for non-browser callers.

The browser camera path remains available for live preview and companion mode.
This module is deliberately one-shot: open the device, read a warm frame, encode
it in memory, and always release the device before returning.
"""

from __future__ import annotations

import base64
import platform
from typing import Any


def capture_camera_frame(
    camera_index: int = 0,
    *,
    width: int = 640,
    height: int = 480,
    warmup_frames: int = 3,
) -> dict[str, Any]:
    """Capture one JPEG data URL from a local physical camera."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "终端摄像头需要 OpenCV。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\camera.txt。"
        ) from exc

    try:
        index = int(camera_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("camera_index 必须是整数。") from exc
    if index < 0:
        raise ValueError("camera_index 不能小于 0。")

    width = max(160, min(int(width), 1920))
    height = max(120, min(int(height), 1080))
    warmup_frames = max(0, min(int(warmup_frames), 30))

    capture = cv2.VideoCapture(index)
    if not capture.isOpened() and platform.system() == "Windows" and hasattr(cv2, "CAP_DSHOW"):
        capture.release()
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"无法打开摄像头 index={index}。请检查设备、系统权限或尝试 --camera-index。")

    try:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        frame = None
        for _ in range(warmup_frames + 1):
            ok, candidate = capture.read()
            if ok and candidate is not None and candidate.size:
                frame = candidate
        if frame is None:
            raise RuntimeError("摄像头已打开但没有返回有效画面。")

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
        if not ok:
            raise RuntimeError("摄像头画面 JPEG 编码失败。")
        raw = encoded.tobytes()
        return {
            "image_data": f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}",
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "camera_index": index,
            "source": "camera_terminal",
        }
    finally:
        capture.release()
