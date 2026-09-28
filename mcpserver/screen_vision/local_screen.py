"""Local screen OCR adapter used by the unified vision dispatcher."""

from __future__ import annotations

import base64
import binascii
from typing import Any


def analyze_local_screen(data_url: str) -> dict[str, Any]:
    """Extract visible text locally without sending or persisting the frame."""
    header, separator, payload = str(data_url or "").partition(",")
    mime = header.removeprefix("data:").split(";", 1)[0].lower()
    if not separator or mime not in {"image/png", "image/jpeg", "image/webp"} or ";base64" not in header:
        return {"status": "error", "message": "缺少有效的屏幕截图。", "persisted": False}
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return {"status": "error", "message": "屏幕截图编码无效。", "persisted": False}
    if len(image_bytes) > 8 * 1024 * 1024:
        return {"status": "error", "message": "屏幕截图过大。", "persisted": False}

    try:
        from miya_senses.sensors.screen_aware import ScreenAwareProactive

        observer = ScreenAwareProactive(vision_mode="ocr_only", ocr_startup_grace_seconds=0)
        # Explicit initialization makes an on-demand request deterministic;
        # the proactive sensor still uses its own lazy background lifecycle.
        observer._ocr_engine = observer._init_paddle_ocr()
        text, confidence = observer._analyze_with_ocr(image_bytes)
    except ModuleNotFoundError as exc:
        package = "paddleocr" if exc.name == "paddleocr" else str(exc.name or "PaddleOCR 依赖")
        return {
            "status": "unavailable",
            "message": f"本地 OCR 依赖未安装（{package}）。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\ocr.txt。",
            "persisted": False,
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "message": f"本地 OCR 不可用：{exc}",
            "persisted": False,
        }

    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        return {
            "status": "partial",
            "message": "本地 OCR 没有识别到清晰文字。",
            "ocr_text": "",
            "confidence": float(confidence or 0),
            "source": "screen_local_ocr",
            "persisted": False,
        }
    return {
        "status": "success",
        "message": f"本地 OCR：{clean_text[:1200]}",
        "ocr_text": clean_text[:4000],
        "confidence": round(float(confidence or 0), 4),
        "source": "screen_local_ocr",
        "persisted": False,
    }
