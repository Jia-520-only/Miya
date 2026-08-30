"""
社交平台工具

跨端共享的社交平台交互工具。
所有弥娅实例（QQ/微信/桌面端）都可以使用这些工具。
"""

from .discord_tools import DiscordTools
from .qq_tools import (
    QQEmojiTool,
    QQFileReaderTool,
    QQImageAnalyzerTool,
)
from .social_base import SocialBase
from .wechat_tools import WeChatTools

__all__ = [
    "SocialBase",
    "QQEmojiTool",
    "QQFileReaderTool",
    "QQImageAnalyzerTool",
    "WeChatTools",
    "DiscordTools",
]
