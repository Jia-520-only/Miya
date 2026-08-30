"""
弥娅统一平台类型定义 (MIYA Unified Platform Type)

所有平台标识符统一由此处定义，作为弥娅唯一权威的平台类型来源。

Usage:
    from core.unified_platform.platform_type import MiyaPlatform

    MiyaPlatform.QQ            → "qq"           (QQ/NapCat)
    MiyaPlatform.QQ_OFFICIAL   → "qq_official"  (QQ 官方机器人)
    MiyaPlatform.MOBILE        → "mobile"       (手机端)
    MiyaPlatform.DISCORD       → "discord"
    ...
"""

from enum import Enum


class MiyaPlatform(str, Enum):
    """弥娅统一平台类型 — 唯一权威定义"""

    # -- QQ 系列 --
    QQ = "qq"
    QQ_OFFICIAL = "qq_official"
    QQ_WEBHOOK = "qqofficial_webhook"
    ONEBOT = "onebot"
    AIOCQHTTP = "aiocqhttp"

    # -- 国际 --
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    LINE = "line"

    # -- 国内 --
    FEISHU = "feishu"
    DINGDING = "dingding"
    WECHAT_WORK = "wechat_work"
    WECOM = "wecom"
    WECOM_AI_BOT = "wecom_ai_bot"
    WECHAT = "wechat"
    WEIXIN_OC = "weixin_oc"
    WEIXIN_OA = "weixin_official_account"
    WEIXIN_ILINK = "weixin_ilink"
    SATORI = "satori"

    # -- 社区 --
    MATRIX = "matrix"
    KOOK = "kook"
    MATTERMOST = "mattermost"
    MISSKEY = "misskey"

    # -- 内置 --
    MOBILE = "mobile"
    TERMINAL = "terminal"
    DESKTOP = "desktop"
    GENERIC = "generic"

    # -- 别名 (向后兼容) --
    LARK = "feishu"  # 飞书别名

    @classmethod
    def active_platforms(cls) -> list[str]:
        """返回弥娅当前启用的主要平台 ID 列表（用于快速迭代）"""
        return [
            cls.QQ.value,
            cls.QQ_OFFICIAL.value,
            cls.AIOCQHTTP.value,
            cls.DESKTOP.value,
            cls.MOBILE.value,
            cls.TERMINAL.value,
        ]

    @classmethod
    def qq_family(cls) -> set[str]:
        """QQ 系列平台集合（含所有实际流通的变体）"""
        return {
            cls.QQ.value,  # "qq" (NapCat/OneBot)
            cls.QQ_OFFICIAL.value,  # "qq_official"
            cls.AIOCQHTTP.value,  # "aiocqhttp" (OneBot v11)
            cls.ONEBOT.value,  # "onebot"
            "qqofficial",  # unified_platform 实际 platform_id (QQ 官方机器人)
        }

    @classmethod
    def is_qq_family(cls, platform: str) -> bool:
        """判断是否为 QQ 系列平台"""
        return platform in cls.qq_family()

    @classmethod
    def ws_direct_platforms(cls) -> set[str]:
        """WS 直推平台（跳过 AI 路由，直接走 WS 兜底）"""
        return {cls.MOBILE.value, cls.DESKTOP.value, "web"}

    @classmethod
    def is_ws_direct(cls, platform: str) -> bool:
        """判断是否为 WS 直推平台"""
        return platform in cls.ws_direct_platforms()

    @classmethod
    def is_qq(cls, platform: str) -> bool:
        """判断是否恰好是 QQ 平台（NapCat/OneBot，不含 qqofficial 等变体）"""
        return platform == cls.QQ.value

    @classmethod
    def is_local_platform(cls, platform: str) -> bool:
        """判断是否为弥娅本地内置平台（desktop/mobile/web/terminal）"""
        return platform in {cls.DESKTOP.value, cls.MOBILE.value, "web", cls.TERMINAL.value}

    @classmethod
    def injection_check_platforms(cls) -> set[str]:
        """需要做安全注入检查的平台（QQ 与移动端为主要聊天入口）"""
        return {cls.QQ.value, cls.MOBILE.value}

    @classmethod
    def requires_injection_check(cls, platform: str) -> bool:
        """判断该平台是否需要做安全注入检查"""
        return platform in cls.injection_check_platforms()

    @classmethod
    def chat_platforms(cls) -> set[str]:
        """可聊天的平台（排除 terminal）"""
        return {v.value for v in cls if v.value not in {"terminal", "generic"}}


# 向后兼容别名：原 PlatformType = MiyaPlatform
PlatformType = MiyaPlatform
