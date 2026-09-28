"""Route screen/camera image analysis through local OCR or cloud vision."""

from __future__ import annotations

import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)


def image_vision_mode() -> str:
    """Read the shared vision route; invalid configuration fails closed locally."""
    try:
        from config.config_utils import get_qq_config

        mode = str(get_qq_config("tools", "qq_image_analyzer", "vision_mode", default="local")).strip().lower()
    except Exception:
        logger.warning("[ImageVision] Route config unavailable; using local OCR", exc_info=True)
        return "local"
    if mode not in {"local", "cloud", "hybrid"}:
        logger.warning("[ImageVision] Unknown vision route %r; using local OCR", mode)
        return "local"
    return mode


def _analyze_local_ocr(image_data: bytes) -> dict[str, Any]:
    from mcpserver.screen_vision.local_screen import analyze_local_screen

    result = analyze_local_screen(f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('ascii')}")
    text = str(result.get("ocr_text") or "")
    success = result.get("status") in {"success", "partial"}
    description = str(result.get("message") or "本地 OCR 不可用")
    return {
        "success": success,
        "description": description,
        "labels": ["含文字"] if text else [],
        "nsfw_score": 0.0,
        "has_text": bool(text),
        "text": text,
        "text_content": text,
        "text_confidence": float(result.get("confidence") or 0.0),
        "format": "image",
        "model": "本地 OCR",
        "model_used": "本地 OCR",
        "provider": "local",
        "confidence": float(result.get("confidence") or 0.0),
        "error_message": "" if success else description,
        "source": result.get("source", "image_local_ocr"),
        "persisted": False,
    }


async def analyze_image_with_route(image_data: bytes) -> dict[str, Any]:
    """Analyze an image without using cloud unless the configured route allows it."""
    mode = image_vision_mode()
    local_result: dict[str, Any] | None = None
    if mode in {"local", "hybrid"}:
        try:
            local_result = _analyze_local_ocr(image_data)
        except Exception as exc:
            logger.warning("[ImageVision] Local OCR failed: %s", exc)
            local_result = {
                "success": False,
                "description": f"本地 OCR 不可用：{exc}",
                "labels": [],
                "nsfw_score": 0.0,
                "has_text": False,
                "text": "",
                "text_content": "",
                "text_confidence": 0.0,
                "format": "image",
                "model": "本地 OCR",
                "model_used": "本地 OCR",
                "provider": "local",
                "confidence": 0.0,
                "error_message": str(exc),
                "source": "image_local_ocr",
                "persisted": False,
            }
        if mode == "local" or (local_result.get("success") and local_result.get("has_text")):
            return local_result
        if local_result and not local_result.get("success"):
            logger.warning(
                "[ImageVision] Local OCR unavailable; falling back to cloud vision (mode=%s): %s",
                mode,
                local_result.get("error_message") or local_result.get("description") or "unknown error",
            )

    return await analyze_cloud_image(image_data)


async def analyze_cloud_image(image_data: bytes, max_retries: int = 2) -> dict[str, Any]:
    """Analyze an incoming platform image with the configured cloud multimodal model.

    This route is intentionally independent from ``vision_mode``.  That setting
    controls local screen/camera observation and must not make OneBot images go
    through OCR first.
    """
    try:
        from core.multi_vision_analyzer import analyze_image_multi_model

        result = await analyze_image_multi_model(image_data, max_retries=max_retries)
        cloud_result = result.to_context_dict()
        cloud_result.setdefault("provider", "cloud")
        cloud_result["source"] = "image_cloud_vision"
        cloud_result["persisted"] = False
        return cloud_result
    except Exception as exc:
        logger.warning("[ImageVision] Cloud image analysis failed: %s", exc)
        return {
            "success": False,
            "description": "云端视觉分析失败",
            "labels": [],
            "provider": "cloud",
            "model": "云端多模态模型",
            "error_message": str(exc),
            "source": "image_cloud_vision",
            "persisted": False,
        }
