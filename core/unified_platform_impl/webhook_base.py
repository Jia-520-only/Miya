"""
Webhook 平台基类

所有 webhook 型平台（飞书、钉钉、KOOK、Slack、LINE 等）的抽象基类。
子类覆写 _setup_webhook_handler 返回路由 handler 即可。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.WebhookBase")


class WebhookPlatform(MessageMixin, BasePlatform):
    """
    Webhook 平台基类

    子类需要覆写:
        _setup_webhook_handler() → 返回 (router_prefix, FastAPI route handlers)
    """

    platform_id = "webhook"
    platform_name = "Webhook 平台"
    health_check_interval = 60.0
    auto_reconnect = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._active = False

    async def _do_connect(self) -> bool:
        self._active = True
        return True

    async def _do_disconnect(self):
        self._active = False

    async def _do_health_check(self) -> bool:
        return self._active

    def get_webhook_routes(self) -> Optional[dict]:
        """
        返回 webhook 路由定义，由 daemon 注册到 FastAPI

        Returns:
            {"prefix": str, "routes": [(method, path, handler), ...]} 或 None
        """
        return None
