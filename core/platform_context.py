"""
当前请求的平台上下文
提供工具执行时需要访问的平台适配器引用。
"""

import base64 as _base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.PlatformContext")

_current_platform_adapter: Optional[Any] = None
_current_platform: str = ""


def set_current_platform_adapter(adapter: Any) -> None:
    """设置当前请求的平台适配器引用"""
    global _current_platform_adapter
    _current_platform_adapter = adapter


def get_current_platform_adapter() -> Optional[Any]:
    """获取当前请求的平台适配器引用"""
    return _current_platform_adapter


def set_current_platform(platform: str) -> None:
    """设置当前请求的平台标识（用于 app 端降级处理）"""
    global _current_platform
    _current_platform = platform


def get_current_platform() -> str:
    """获取当前请求的平台标识"""
    return _current_platform


class AppPlatformBridge:
    """桌面/移动端轻量适配器 — 提供基本文件读写能力"""

    platform_id: str
    last_file_url: str = ""
    last_file_info: Optional[Dict[str, Any]] = None
    supports_file_send: bool = True  # 桌面/移动端通过 Web 目录暂存文件

    def __init__(self, platform_id: str):
        self.platform_id = platform_id
        self._web_files_dir = Path(__file__).resolve().parent.parent / "data" / "web_files"
        os.makedirs(self._web_files_dir, exist_ok=True)

    @staticmethod
    def _guess_mime(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime_map = {
            "txt": "text/plain",
            "md": "text/markdown",
            "json": "application/json",
            "xml": "application/xml",
            "html": "text/html",
            "csv": "text/csv",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "svg": "image/svg+xml",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "ogg": "audio/ogg",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "zip": "application/zip",
            "rar": "application/x-rar-compressed",
            "py": "text/x-python",
            "js": "text/javascript",
            "ts": "text/typescript",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def send_file(
        self,
        target: str = "",
        file_path: str = "",
        file_name: str = "",
        file_data: Optional[bytes] = None,
        caption: str = "",
        **kwargs,
    ) -> bool:
        """文件暂存到 web 可访问目录，同时保存 base64 数据供 API 响应"""
        data = file_data
        if not data and file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read()

        if not data:
            logger.warning(f"[{self.platform_id}] 无法读取文件内容")
            return False

        name = file_name or (os.path.basename(file_path) if file_path else "file.bin")
        dest = self._web_files_dir / name
        dest.write_bytes(data)

        mime = self._guess_mime(name)
        b64 = _base64.b64encode(data).decode()

        self.last_file_url = f"/api/files/download/{name}"
        self.last_file_info = {
            "name": name,
            "size": len(data),
            "mime_type": mime,
            "url": self.last_file_url,
            "base64": b64,
        }
        logger.info(f"[{self.platform_id}] 文件已暂存: {name} ({len(data)}B, {len(b64)}B b64) → {self.last_file_url}")
        return True

    async def send_image(self, target: str = "", image_path: str = "", **kwargs) -> bool:
        return await self.send_file(target=target, file_path=image_path, **kwargs)

    async def send_file_from_url(
        self,
        target: str = "",
        url: str = "",
        file_name: str = "",
        **kwargs,
    ) -> bool:
        logger.warning(f"[{self.platform_id}] send_file_from_url 暂未实现")
        return False

    def is_online(self) -> bool:
        return True

    def _record_message_out(self):
        pass
