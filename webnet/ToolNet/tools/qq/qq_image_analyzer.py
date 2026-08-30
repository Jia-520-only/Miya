"""
QQ图片分析工具 - 简化版
"""

import io
import logging
from typing import Dict, Optional

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


class QQImageAnalyzerTool:
    """QQ图片分析工具"""

    @property
    def config(self) -> dict:
        return {
            "name": "qq_image_analyzer",
            "description": "分析QQ图片中的内容，包括图片尺寸、格式大小，并尝试识别图片中的文字。用户发送图片时必须调用此工具分析图片内容。",
            "parameters": {
                "type": "object",
                "properties": {"image_url": {"type": "string", "description": "图片的网络URL地址"}},
                "required": ["image_url"],
            },
        }

    def __init__(self):
        self.logger = logging.getLogger("qq_image_analyzer")

    async def execute(self, args: Dict, context=None):
        """执行图片分析"""
        args = args or {}
        actual_context = context

        self.logger.warning(f"[qq_image_analyzer] 实际参数: args={args}, ctx={type(actual_context)}")

        image_url = args.get("image_url", "")
        if not image_url:
            return "❌ 请提供图片URL"

        # 下载图片
        image_data = await self._download_image(image_url, actual_context)

        if not image_data:
            return f"❌ 图片下载失败: {image_url[:50]}..."

        # 使用视觉模型分析
        result = await self._analyze_image(image_data)
        return result

    async def _download_image(self, url: str, context) -> Optional[bytes]:
        """下载图片（支持本地文件路径与网络 URL）"""
        import os

        # 本地文件路径：直接读取（模型可能把截图/下载路径当 URL 传入）
        if url and not url.startswith(("http://", "https://")) and os.path.exists(url):
            try:
                with open(url, "rb") as f:
                    return f.read()
            except Exception as e:
                self.logger.warning(f"本地图片读取失败: {e}")
                return None

        # 尝试onebot_client
        try:
            onebot_client = None
            if context:
                onebot_client = getattr(context, "onebot_client", None)
            if onebot_client and hasattr(onebot_client, "download_image"):
                data = await onebot_client.download_image(url)
                if data:
                    return data
        except Exception as e:
            self.logger.warning(f"onebot_client下载失败: {e}")

        # 使用httpx直接下载
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, timeout=30.0)
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            self.logger.error(f"httpx下载失败: {e}")

        return None

    async def _analyze_image(self, image_data: bytes) -> str:
        """分析图片 - 使用视觉模型"""
        try:
            img = Image.open(io.BytesIO(image_data))
            width, height = img.size
            fmt = img.format or "未知"
            size_kb = len(image_data) / 1024

            result = "📐 图片信息\n"
            result += f"尺寸: {width} × {height} 像素\n"
            result += f"格式: {fmt}\n"
            result += f"大小: {size_kb:.1f} KB\n"

            # 使用视觉模型分析
            try:
                from core.multi_vision_analyzer import analyze_image_multi_model

                self.logger.info("[qq_image_analyzer] 调用视觉模型分析...")
                vision_result = await analyze_image_multi_model(image_data, max_retries=2)

                if vision_result and vision_result.success:
                    if vision_result.description:
                        result += f"\n🎨 图片内容:\n{vision_result.description}"
                    if vision_result.text_content:
                        result += f"\n📝 识别文字:\n{vision_result.text_content}"
                else:
                    self.logger.warning(f"视觉分析失败: {vision_result}")
            except Exception as e:
                self.logger.warning(f"视觉模型分析失败: {e}")

            return result
        except Exception as e:
            return f"❌ 图片分析失败: {str(e)}"
