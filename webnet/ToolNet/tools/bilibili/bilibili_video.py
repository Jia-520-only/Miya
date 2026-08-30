"""
B站视频处理工具
支持：B站链接/BV号/AV号解析、视频信息获取、视频卡片生成
"""

import logging
from typing import Any, Dict, Optional

from webnet.ToolNet.base import BaseTool, ToolContext
from webnet.ToolNet.tools.bilibili.downloader import (
    build_info_card,
    get_video_info,
)
from webnet.ToolNet.tools.bilibili.parser import (
    extract_all_from_message,
    extract_from_message,
)

logger = logging.getLogger(__name__)


class BilibiliVideoTool(BaseTool):
    """B站视频处理工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "bilibili_video",
            "description": "处理B站视频链接，支持从消息中自动提取B站视频标识，获取视频信息和分享链接。当用户发送B站视频链接、BV号、AV号时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "B站视频标识：BV号、AV号、完整URL或b23.tv短链。也可以直接传入消息文本自动提取。",
                    },
                    "action": {
                        "type": "string",
                        "description": "操作类型：info(获取视频信息), card(生成信息卡片), auto(自动检测并处理)",
                        "enum": ["info", "card", "auto"],
                        "default": "auto",
                    },
                },
                "required": ["video_id"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        """执行B站视频处理"""
        args = args or {}
        video_id = args.get("video_id", "")
        action = args.get("action", "auto")

        if not video_id:
            return "请提供视频标识"

        bvid = await extract_from_message(video_id)
        if not bvid:
            bvid = video_id

        if action == "auto":
            bvid = await extract_from_message(video_id)
            if not bvid:
                return "未检测到有效的B站视频标识"
            action = "card"

        if action == "info":
            info = await get_video_info(bvid)
            if not info:
                return f"获取视频信息失败: {bvid}"
            return f"标题: {info.title}\nUP主: {info.up_name}\n简介: {info.desc}\n链接: https://www.bilibili.com/video/{bvid}"

        if action == "card":
            info = await get_video_info(bvid)
            if not info:
                return f"获取视频信息失败: {bvid}"
            return build_info_card(info)

        return "未知的操作类型"


class BilibiliAutoExtract:
    """B站视频自动提取器 - 用于消息预处理"""

    @staticmethod
    async def check_and_extract(message: str) -> Optional[str]:
        """检查消息中是否包含B站视频，返回BV号"""
        return await extract_from_message(message)

    @staticmethod
    async def extract_all(message: str) -> list[str]:
        """提取消息中所有B站视频"""
        return await extract_all_from_message(message)
