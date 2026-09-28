"""Local screen OCR adapter used by the unified vision dispatcher."""

from __future__ import annotations

import base64
import binascii
import ctypes
import io
import sys
import threading
from typing import Any

_observer_lock = threading.Lock()
_observer: Any = None


def _get_ocr_observer() -> Any:
    global _observer
    with _observer_lock:
        if _observer is None:
            from miya_senses.sensors.screen_aware import ScreenAwareProactive

            _observer = ScreenAwareProactive(vision_mode="ocr_only", ocr_startup_grace_seconds=0)
        if _observer._ocr_engine is None:
            _observer._ocr_engine = _observer._init_paddle_ocr()
        return _observer


def _extract_windows_accessibility() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"status": "unsupported", "window_title": "", "elements": []}

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"status": "unavailable", "window_title": "", "elements": []}
        title_length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        window_title = title_buffer.value.strip()
    except Exception as exc:
        return {"status": "unavailable", "window_title": "", "elements": [], "message": str(exc)[:200]}

    try:
        from pywinauto import Desktop
    except ModuleNotFoundError:
        return {
            "status": "unavailable",
            "window_title": window_title,
            "elements": [],
            "message": "pywinauto未安装；请安装 Windows 桌面依赖 setup/dependencies/win32.txt。",
        }

    try:
        root = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    except Exception as exc:
        return {"status": "unavailable", "window_title": window_title, "elements": [], "message": str(exc)[:200]}

    controls: list[dict[str, Any]] = []
    queue: list[tuple[Any, int]] = [(root, 0)]
    visited = 0
    useful_roles = {
        "Button", "CheckBox", "ComboBox", "DataItem", "Document", "Edit", "Hyperlink",
        "ListItem", "MenuItem", "RadioButton", "TabItem", "Text", "TreeItem",
    }
    while queue and visited < 700 and len(controls) < 150:
        current, depth = queue.pop(0)
        try:
            children = current.children()
        except Exception:
            continue
        for child in children:
            visited += 1
            if visited > 700:
                break
            try:
                info = child.element_info
                role = str(getattr(info, "control_type", "") or "").strip()
                raw_name = str(getattr(info, "name", "") or "").strip()
                password_flag = getattr(info, "is_password", False)
                is_password = bool(password_flag() if callable(password_flag) else password_flag)
                name = "密码输入框" if is_password else raw_name
                if role in useful_roles and name:
                    try:
                        rect = child.rectangle()
                        bounds = [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)]
                    except Exception:
                        bounds = [0, 0, 0, 0]
                    try:
                        enabled = bool(child.is_enabled())
                    except Exception:
                        enabled = None
                    item = {
                        "text": name[:180],
                        "role": role,
                        "enabled": enabled,
                        "bounds_screen": bounds,
                    }
                    automation_id = str(getattr(info, "automation_id", "") or "").strip()
                    if automation_id:
                        item["automation_id"] = automation_id[:120]
                    if is_password:
                        item["redacted"] = True
                    controls.append(item)
            except Exception:
                pass
            if depth < 7 and len(controls) < 150:
                queue.append((child, depth + 1))

    controls.sort(key=lambda item: (item["bounds_screen"][1], item["bounds_screen"][0]))
    return {"status": "available", "window_title": window_title, "elements": controls}


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

    ocr_error = ""
    try:
        observer = _get_ocr_observer()
        text, confidence, blocks = observer._analyze_with_ocr_details(image_bytes)
    except ModuleNotFoundError as exc:
        package = "paddleocr" if exc.name == "paddleocr" else str(exc.name or "PaddleOCR 依赖")
        ocr_error = f"本地 OCR 依赖未安装（{package}）。请执行 .venv\\Scripts\\python.exe -m pip install -r setup\\dependencies\\ocr.txt。"
        text, confidence, blocks = "", 0.0, []
    except Exception as exc:
        ocr_error = f"本地 OCR 不可用：{exc}"
        text, confidence, blocks = "", 0.0, []

    clean_text = " ".join(str(text or "").split())
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
    except Exception:
        width = height = 0

    elements = []
    positioned_lines = []
    for block in blocks:
        points = block.get("box") or []
        if points and width and height:
            left = min(1.0, max(0.0, min(point[0] for point in points) / max(width, 1)))
            top = min(1.0, max(0.0, min(point[1] for point in points) / max(height, 1)))
            right = min(1.0, max(0.0, max(point[0] for point in points) / max(width, 1)))
            bottom = min(1.0, max(0.0, max(point[1] for point in points) / max(height, 1)))
        else:
            left = top = right = bottom = 0.0
        element = {
            "text": block["text"],
            "confidence": round(float(block["confidence"]), 4),
            "bbox": [round(left, 4), round(top, 4), round(right, 4), round(bottom, 4)],
        }
        elements.append(element)
        positioned_lines.append(
            f"({round((left + right) * 50)}%, {round((top + bottom) * 50)}%) {block['text']}"
        )

    accessibility = _extract_windows_accessibility()
    ocr_indexes = {" ".join(item["text"].casefold().split()): index for index, item in enumerate(elements)}
    accessibility_lines = []
    for item in accessibility.get("elements", []):
        key = " ".join(str(item.get("text") or "").casefold().split())
        index = ocr_indexes.get(key)
        if index is not None:
            elements[index]["role"] = item["role"]
            elements[index]["enabled"] = item["enabled"]
            elements[index]["uia_bounds_screen"] = item["bounds_screen"]
            positioned_lines[index] = f"[{item['role']}] {positioned_lines[index]}"
            item["matched_ocr"] = True
        else:
            item["matched_ocr"] = False
            text = item["text"].replace("\n", " ")
            enabled = item.get("enabled")
            availability = "可用" if enabled is True else "不可用" if enabled is False else "状态未知"
            bounds = item.get("bounds_screen") or [0, 0, 0, 0]
            accessibility_lines.append(f"[{item['role']}] {text}（{availability}，屏幕坐标 {bounds[0]},{bounds[1]}）")

    message_parts = []
    if accessibility.get("window_title"):
        message_parts.append(f"前台窗口：{accessibility['window_title'][:180]}")
    if accessibility_lines:
        message_parts.append("Windows 控件：\n" + "\n".join(accessibility_lines[:60]))
    if positioned_lines:
        message_parts.append("屏幕文字与位置：\n" + "\n".join(positioned_lines[:100]))
    if ocr_error:
        message_parts.append(ocr_error)
    elif not positioned_lines and not accessibility_lines:
        message_parts.append("本地 OCR 没有识别到清晰文字。")
    accessibility_error = str(accessibility.get("message") or "")
    if accessibility_error and accessibility.get("status") == "unavailable":
        message_parts.append(accessibility_error)

    has_result = bool(clean_text or accessibility_lines or accessibility.get("window_title"))
    return {
        "status": "success" if has_result else ("unavailable" if ocr_error else "partial"),
        "message": "本地界面信息（未上传）：\n" + "\n".join(message_parts),
        "ocr_text": clean_text[:4000],
        "elements": elements[:200],
        "accessibility": {
            "status": accessibility.get("status", "unavailable"),
            "window_title": accessibility.get("window_title", ""),
            "elements": accessibility.get("elements", [])[:150],
        },
        "confidence": round(float(confidence or 0), 4),
        "width": width,
        "height": height,
        "source": "screen_local_ocr",
        "persisted": False,
    }
