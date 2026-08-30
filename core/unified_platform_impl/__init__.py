"""
弥娅统一平台实现包

所有平台适配器的命名空间包。
"""

from .discord_platform import DiscordPlatform
from .generic_platform import GenericPlatform
from .onebot_platform import OneBotPlatform
from .qq_official_platform import QQOfficialPlatform
from .real_platforms import (
    DingTalkPlatform,
    KOOKPlatform,
    SatoriPlatform,
    SlackPlatform,
    WeChatOfficialPlatform,
    WeComPlatform,
)
from .telegram_platform import TelegramPlatform
from .webhook_base import WebhookPlatform
from .webhook_platforms import LarkPlatform, LINEPlatform
from .weixin_ilink_platform import WeixinIlinkPlatform

__all__ = [
    "QQOfficialPlatform",
    "TelegramPlatform",
    "DiscordPlatform",
    "OneBotPlatform",
    "GenericPlatform",
    "WebhookPlatform",
    "LarkPlatform",
    "KOOKPlatform",
    "SlackPlatform",
    "LINEPlatform",
    "DingTalkPlatform",
    "SatoriPlatform",
    "WeComPlatform",
    "WeChatOfficialPlatform",
    "WeixinIlinkPlatform",
]
