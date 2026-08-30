"""
统一平台管理器 - Unified Platform Manager

整合弥娅原有平台 + AstrBot 迁移平台
===============================================

优先级:
1. AstrBot 平台 (更全面)
2. Miya 原有平台 (保留特色)
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("miya.unified.platform")

# 平台列表
AVAILABLE_PLATFORMS = {
    # AstrBot 平台 (优先)
    "qqofficial": {
        "name": "QQ 官方机器人",
        "module": "astrbot.core.platform.sources.qqofficial",
        "adapter": "QQOfficialPlatformAdapter",
    },
    "qqofficial_webhook": {
        "name": "QQ 官方 Webhook",
        "module": "astrbot.core.platform.sources.qqofficial_webhook",
        "adapter": "QQOfficialWebhookAdapter",
    },
    "telegram": {
        "name": "Telegram",
        "module": "astrbot.core.platform.sources.telegram",
        "adapter": "TelegramPlatformAdapter",
    },
    "discord": {
        "name": "Discord",
        "module": "astrbot.core.platform.sources.discord",
        "adapter": "DiscordPlatformAdapter",
    },
    "slack": {
        "name": "Slack",
        "module": "astrbot.core.platform.sources.slack",
        "adapter": "SlackPlatformAdapter",
    },
    "lark": {
        "name": "飞书/Lark",
        "module": "astrbot.core.platform.sources.lark",
        "adapter": "LarkPlatformAdapter",
    },
    "dingtalk": {
        "name": "钉钉",
        "module": "astrbot.core.platform.sources.dingtalk",
        "adapter": "DingTalkPlatformAdapter",
    },
    "wecom": {
        "name": "企业微信",
        "module": "astrbot.core.platform.sources.wecom",
        "adapter": "WeComPlatformAdapter",
    },
    "wecom_ai_bot": {
        "name": "企业微信 AI 机器人",
        "module": "astrbot.core.platform.sources.wecom_ai_bot",
        "adapter": "WeComAIBotAdapter",
    },
    "kook": {
        "name": "KOOK",
        "module": "astrbot.core.platform.sources.kook",
        "adapter": "KOOKPlatformAdapter",
    },
    "satori": {
        "name": "Satori",
        "module": "astrbot.core.platform.sources.satori",
        "adapter": "SatoriPlatformAdapter",
    },
    "line": {
        "name": "LINE",
        "module": "astrbot.core.platform.sources.line",
        "adapter": "LINEPlatformAdapter",
    },
    "mattermost": {
        "name": "Mattermost",
        "module": "astrbot.core.platform.sources.mattermost",
        "adapter": "MattermostPlatformAdapter",
    },
    "misskey": {
        "name": "Misskey",
        "module": "astrbot.core.platform.sources.misskey",
        "adapter": "MisskeyPlatformAdapter",
    },
    "weixin_official_account": {
        "name": "微信公众平台",
        "module": "astrbot.core.platform.sources.weixin_official_account",
        "adapter": "WeixinOfficialAccountAdapter",
    },
    "weixin_oc": {
        "name": "微信开放平台",
        "module": "astrbot.core.platform.sources.weixin_oc",
        "adapter": "WeixinOCAdapter",
    },
    "aiocqhttp": {
        "name": "OneBot v11 (QQ)",
        "module": "astrbot.core.platform.sources.aiocqhttp",
        "adapter": "AIOCQHTTPPlatformAdapter",
    },
    # Miya 原有平台 (备用)
    "terminal": {
        "name": "终端",
        "module": "hub.platform_adapters",
        "adapter": "TerminalAdapter",
    },
    "desktop": {
        "name": "桌面端",
        "module": "hub.platform_adapters",
        "adapter": "PCUIAdapter",
    },
    "mobile": {
        "name": "手机端",
        "module": "hub.platform_adapters",
        "adapter": "MobileAdapter",
    },
}


class UnifiedPlatformManager:
    """统一平台管理器"""

    def __init__(self, event_queue: Optional[asyncio.Queue] = None) -> None:
        self._event_queue = event_queue or asyncio.Queue()
        self._platforms: Dict[str, Any] = {}
        self._running = False

    async def initialize(self, platform_configs: List[dict]) -> None:
        """初始化所有启用的平台"""
        logger.info(f"[PlatformManager] 初始化 {len(platform_configs)} 个平台...")

        for config in platform_configs:
            platform_type = config.get("type")
            platform_id = config.get("id")
            enabled = config.get("enabled", True)

            if not enabled:
                continue

            await self.create_platform(platform_type, platform_id, config)

        logger.info(f"[PlatformManager] 已初始化 {len(self._platforms)} 个平台")

    async def create_platform(
        self,
        platform_type: str,
        platform_id: str,
        config: dict,
    ) -> Optional[Any]:
        """创建平台实例"""
        platform_info = AVAILABLE_PLATFORMS.get(platform_type)

        if not platform_info:
            logger.warning(f"[PlatformManager] 未知平台类型: {platform_type}")
            return None

        try:
            # 尝试从 AstrBot 导入
            module_path = platform_info["module"]
            adapter_name = platform_info["adapter"]

            # 动态导入
            import importlib

            module = importlib.import_module(module_path)
            adapter_cls = getattr(module, adapter_name)

            # 创建实例
            platform = adapter_cls(config, self._event_queue)

            self._platforms[platform_id] = platform
            logger.info(f"[PlatformManager] 创建平台: {platform_id} ({platform_type})")

            return platform

        except ImportError as e:
            logger.warning(f"[PlatformManager] 平台 {platform_type} 导入失败: {e}")

            # 回退到 Miya 原有平台
            return await self._create_miya_platform(platform_type, platform_id, config)

    async def _create_miya_platform(
        self,
        platform_type: str,
        platform_id: str,
        config: dict,
    ) -> Optional[Any]:
        """创建 Miya 原有平台"""
        from hub.platform_adapters import get_adapter

        adapter_cls = get_adapter(platform_type)
        if not adapter_cls:
            return None

        try:
            platform = adapter_cls(platform_id)
            self._platforms[platform_id] = platform
            logger.info(f"[PlatformManager] 创建 Miya 平台: {platform_id}")
            return platform
        except Exception as e:
            logger.error(f"[PlatformManager] 创建 Miya 平台失败: {e}")
            return None

    async def start_all(self) -> None:
        """启动所有平台"""
        logger.info("[PlatformManager] 启动所有平台...")
        self._running = True

        for platform_id, platform in self._platforms.items():
            try:
                asyncio.create_task(platform.run())
            except Exception as e:
                logger.error(f"[PlatformManager] 启动平台失败 {platform_id}: {e}")

        logger.info("[PlatformManager] 所有平台已启动")

    async def stop_all(self) -> None:
        """停止所有平台"""
        logger.info("[PlatformManager] 停止所有平台...")
        self._running = False

        for platform_id, platform in self._platforms.items():
            try:
                await platform.terminate()
            except Exception as e:
                logger.error(f"[PlatformManager] 停止平台失败 {platform_id}: {e}")

        self._platforms.clear()

    def get_platform(self, platform_id: str) -> Optional[Any]:
        """获取平台实例"""
        return self._platforms.get(platform_id)

    def list_platforms(self) -> Dict[str, Dict]:
        """列出所有平台状态"""
        return {pid: p.get_stats() if hasattr(p, "get_stats") else {"id": pid} for pid, p in self._platforms.items()}

    def get_event_queue(self) -> asyncio.Queue:
        """获取事件队列"""
        return self._event_queue

    @property
    def is_running(self) -> bool:
        return self._running


# 全局实例
_platform_manager: Optional[UnifiedPlatformManager] = None


def get_platform_manager() -> UnifiedPlatformManager:
    """获取全局平台管理器"""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = UnifiedPlatformManager()
    return _platform_manager


def list_available_platforms() -> Dict[str, Dict]:
    """列出所有可用平台"""
    return AVAILABLE_PLATFORMS.copy()


__all__ = [
    "UnifiedPlatformManager",
    "get_platform_manager",
    "list_available_platforms",
    "AVAILABLE_PLATFORMS",
]
