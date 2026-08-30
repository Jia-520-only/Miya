#!/usr/bin/env python3
"""
多媒体预处理模块

支持图片/音频的预处理：
- URL 下载
- Base64 编码
- 文件路径转换
- 格式检测与转换
"""

import base64
import logging
import os
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

logger = logging.getLogger(__name__)

# 支持的图片格式
SUPPORTED_IMAGE_FORMATS = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
}

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "m4a": "audio/m4a",
}


class MediaPreprocessor:
    """多媒体预处理器"""

    def __init__(self, timeout: int = 30, proxy: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    async def download_file(
        self,
        url: str,
        target_path: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """下载文件

        Args:
            url: 文件 URL
            target_path: 目标路径（可选）

        Returns:
            (文件路径, 是否需要清理)
        """
        need_cleanup = False

        try:
            parsed = urlparse(url)
            suffix = Path(parsed.path).suffix or ".tmp"

            if not target_path:
                temp_dir = tempfile.gettempdir()
                target_path = os.path.join(
                    temp_dir,
                    f"miya_media_{uuid.uuid4().hex}{suffix}",
                )
                need_cleanup = True

            # 下载
            async with httpx.AsyncClient(
                proxies=self._get_proxies(),
                timeout=self.timeout,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                with open(target_path, "wb") as f:
                    f.write(response.content)

            return target_path, need_cleanup

        except Exception as e:
            logger.warning(f"[MediaPreprocessor] 下载失败 {url}: {e}")
            return url, False

    def _get_proxies(self) -> Optional[Dict[str, str]]:
        """获取代理配置"""
        if not self.proxy:
            return None
        return {
            "http://": self.proxy,
            "https://": self.proxy,
        }

    async def download_image(
        self,
        image_ref: str,
    ) -> Optional[str]:
        """下载图片

        Args:
            image_ref: 图片引用 (http URL, file:// 路径, base64://, 或本地路径)

        Returns:
            本地文件路径
        """
        # Base64
        if image_ref.startswith("base64://"):
            data = image_ref.replace("base64://", "")
            try:
                image_bytes = base64.b64decode(data)
            except Exception:
                return None

            # 保存为临时文件
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(
                temp_dir,
                f"miya_image_{uuid.uuid4().hex}.jpg",
            )

            with open(file_path, "wb") as f:
                f.write(image_bytes)

            return file_path

        # HTTP URL
        if image_ref.startswith("http"):
            return (await self.download_file(image_ref))[0]

        # file:// 路径
        if image_ref.startswith("file://"):
            return self._file_uri_to_path(image_ref)

        # 本地路径
        if os.path.exists(image_ref):
            return image_ref

        return None

    def _file_uri_to_path(self, file_uri: str) -> str:
        """file:// URI 转换为路径

        Args:
            file_uri: file:// URI

        Returns:
            本地路径
        """
        parsed = urlparse(file_uri)
        netloc = unquote(parsed.netloc or "")
        path = unquote(parsed.path or "")

        # Windows 盘符
        if netloc and len(netloc) == 1:
            return f"{netloc}:{path}"
        if netloc == "localhost":
            return path

        # UNC 路径
        if netloc:
            return f"//{netloc}{path}"

        return path

    async def encode_image_to_data_url(
        self,
        image_path: str,
        mode: str = "safe",
    ) -> Optional[str]:
        """编码图片为 data URL

        Args:
            image_path: 图片路径
            mode: 模式 (safe/strict)

        Returns:
            data URL 或 None
        """
        try:
            image_bytes = Path(image_path).read_bytes()
        except OSError:
            if mode == "strict":
                raise
            return None

        try:
            with PILImage.open(BytesIO(image_bytes)) as image:
                image.verify()
                image_format = str(image.format or "").upper()
        except (OSError, UnidentifiedImageError):
            if mode == "strict":
                raise ValueError(f"无效图片: {image_path}")
            return None

        mime_type = SUPPORTED_IMAGE_FORMATS.get(
            image_format.lower(),
            "image/jpeg",
        )

        image_bs64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{image_bs64}"

    async def resolve_image_url(
        self,
        image_ref: str,
        detail: Optional[str] = None,
    ) -> Optional[Dict]:
        """解析图片引用为 OpenAI 格式

        Args:
            image_ref: 图片引用
            detail: 详细程度 (low/high)

        Returns:
            OpenAI 格式的图片对象
        """
        # 已经是 data URL
        if image_ref.startswith("data:"):
            payload = {"url": image_ref}
        else:
            # 下载并编码
            image_data = await self.download_image(image_ref)
            if not image_data:
                logger.warning(f"[MediaPreprocessor] 图片解析失败: {image_ref}")
                return None

            image_data_url = await self.encode_image_to_data_url(image_data)
            if not image_data_url:
                return None

            payload = {"url": image_data_url}

        if detail:
            payload["detail"] = detail

        return {
            "type": "image_url",
            "image_url": payload,
        }

    def is_image_file(self, file_path: str) -> bool:
        """检查是否是图片文件"""
        try:
            suffix = Path(file_path).suffix.lower().lstrip(".")
            return suffix in SUPPORTED_IMAGE_FORMATS
        except Exception:
            return False

    def is_audio_file(self, file_path: str) -> bool:
        """检查是否是音频文件"""
        try:
            suffix = Path(file_path).suffix.lower().lstrip(".")
            return suffix in SUPPORTED_AUDIO_FORMATS
        except Exception:
            return False

    async def extract_images_from_context(
        self,
        contexts: List[Dict],
    ) -> Tuple[List[Dict], List[str]]:
        """从上下文中提取图片

        Args:
            contexts: 上下文列表

        Returns:
            (处理后的上下文, 图片引用列表)
        """
        image_refs = []

        for ctx in contexts:
            content = ctx.get("content")
            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue

                if item.get("type") == "image_url":
                    image_url = item.get("image_url", {})
                    if isinstance(image_url, dict):
                        url = image_url.get("url", "")
                        if url and url.startswith(("http", "file://", "base64:")):
                            image_refs.append(url)

        return contexts, image_refs

    async def materialize_images_in_context(
        self,
        contexts: List[Dict],
    ) -> List[Dict]:
        """将上下文中所有图片物化为 data URL

        Args:
            contexts: 上下文

        Returns:
            处理后的上下文
        """
        new_contexts = []

        for ctx in contexts:
            content = ctx.get("content")
            if not isinstance(content, list):
                new_contexts.append(ctx)
                continue

            new_content = []
            for item in content:
                if not isinstance(item, dict):
                    new_content.append(item)
                    continue

                if item.get("type") == "image_url":
                    image_url = item.get("image_url", {})
                    if isinstance(image_url, dict):
                        url = image_url.get("url", "")
                        if url:
                            resolved = await self.resolve_image_url(url)
                            if resolved:
                                new_content.append(resolved)
                            else:
                                # 保留原样
                                new_content.append(item)
                        else:
                            new_content.append(item)
                    else:
                        new_content.append(item)
                else:
                    new_content.append(item)

            new_contexts.append({**ctx, "content": new_content})

        return new_contexts


# 全局实例
_preprocessor_instance = None


def get_media_preprocessor(
    timeout: int = 30,
    proxy: str = "",
) -> MediaPreprocessor:
    """获取多媒体预处理器实例"""
    global _preprocessor_instance
    if _preprocessor_instance is None:
        _preprocessor_instance = MediaPreprocessor(timeout, proxy)
    return _preprocessor_instance
