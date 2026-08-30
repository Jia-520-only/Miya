"""
MIYA Dashboard Backend (内联版)

复用 AstrBot 的 Dashboard API 设计
提供配置、人格、知识库、插件等管理接口
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DashboardAPI:
    """
    MIYA Dashboard API 统一入口

    负责:
    - 配置管理 (config)
    - 平台管理 (platform)
    - 提供商管理 (provider)
    - 人格管理 (personality)
    - 知识库管理 (knowledge_base)
    - 插件管理 (plugin)
    - 会话管理 (conversation)
    - 定时任务 (cron)
    - 工具 (tools)
    - 统计 (stats)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._route_handlers: Dict[str, Any] = {}
        self._initialized = True

        # 注册路由
        self._register_routes()

        logger.info("[DashboardAPI] 初始化完成")

    def _register_routes(self):
        """注册路由处理器"""
        from . import dashboard_routes

        # 配置路由
        self._route_handlers["config/get"] = dashboard_routes.get_config
        self._route_handlers["config/set"] = dashboard_routes.set_config
        self._route_handlers["config/reset"] = dashboard_routes.reset_config
        # 平台路由
        self._route_handlers["platform/list"] = dashboard_routes.list_platforms
        self._route_handlers["platform/add"] = dashboard_routes.add_platform
        self._route_handlers["platform/update"] = dashboard_routes.update_platform
        self._route_handlers["platform/delete"] = dashboard_routes.delete_platform
        # 提供商路由
        self._route_handlers["provider/list"] = dashboard_routes.list_providers
        self._route_handlers["provider/add"] = dashboard_routes.add_provider
        self._route_handlers["provider/update"] = dashboard_routes.update_provider
        self._route_handlers["provider/delete"] = dashboard_routes.delete_provider
        self._route_handlers["provider/test"] = dashboard_routes.test_provider
        # 人格路由
        self._route_handlers["persona/list"] = dashboard_routes.list_personas
        self._route_handlers["persona/add"] = dashboard_routes.add_persona
        self._route_handlers["persona/update"] = dashboard_routes.update_persona
        self._route_handlers["persona/delete"] = dashboard_routes.delete_persona
        self._route_handlers["persona/set_default"] = dashboard_routes.set_default_persona
        # 知识库路由
        self._route_handlers["kb/list"] = dashboard_routes.list_knowledge_bases
        self._route_handlers["kb/add"] = dashboard_routes.add_knowledge_base
        self._route_handlers["kb/update"] = dashboard_routes.update_knowledge_base
        self._route_handlers["kb/delete"] = dashboard_routes.delete_knowledge_base
        self._route_handlers["kb/query"] = dashboard_routes.query_knowledge_base
        self._route_handlers["kb/add_doc"] = dashboard_routes.add_document
        # 插件路由
        self._route_handlers["plugin/list"] = dashboard_routes.list_plugins
        self._route_handlers["plugin/install"] = dashboard_routes.install_plugin
        self._route_handlers["plugin/uninstall"] = dashboard_routes.uninstall_plugin
        self._route_handlers["plugin/enable"] = dashboard_routes.enable_plugin
        self._route_handlers["plugin/disable"] = dashboard_routes.disable_plugin
        # 会话路由
        self._route_handlers["conversation/list"] = dashboard_routes.list_conversations
        self._route_handlers["conversation/get"] = dashboard_routes.get_conversation
        self._route_handlers["conversation/delete"] = dashboard_routes.delete_conversation
        self._route_handlers["conversation/clear"] = dashboard_routes.clear_conversations
        # 定时任务路由
        self._route_handlers["cron/list"] = dashboard_routes.list_cron_jobs
        self._route_handlers["cron/add"] = dashboard_routes.add_cron_job
        self._route_handlers["cron/update"] = dashboard_routes.update_cron_job
        self._route_handlers["cron/delete"] = dashboard_routes.delete_cron_job
        self._route_handlers["cron/enable"] = dashboard_routes.enable_cron_job
        self._route_handlers["cron/disable"] = dashboard_routes.disable_cron_job
        # 统计路由
        self._route_handlers["stats/overview"] = dashboard_routes.get_stats_overview
        self._route_handlers["stats/conversation"] = dashboard_routes.get_conversation_stats
        self._route_handlers["stats/provider"] = dashboard_routes.get_provider_stats

    async def handle_request(self, route: str, **kwargs) -> Any:
        """处理API请求"""
        handler = self._route_handlers.get(route)
        if handler:
            try:
                return await handler(**kwargs)
            except Exception as e:
                logger.error(f"[DashboardAPI] 请求处理失败 {route}: {e}")
                return {"error": str(e)}
        return {"error": "Unknown route"}

    def list_routes(self) -> List[Dict]:
        """列出所有路由"""
        return [
            {"route": route, "handler": handler.__name__ if handler else ""}
            for route, handler in self._route_handlers.items()
        ]


def get_dashboard_api() -> DashboardAPI:
    return DashboardAPI()
