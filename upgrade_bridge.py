from __future__ import annotations

"""
弥娅能力升级集成层 — Browser Use + Screen Aware + Plugin SDK

本模块统一初始化弥娅的三个扩展能力：

  ┌─────────────────────────────────────────────┐
  │              弥娅能力升级层                  │
  │                                              │
  │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
  │  │ Browser  │  │  Screen  │  │  Plugin   │  │
  │  │ Use      │  │  Aware   │  │  SDK      │  │
  │  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
  │       │             │              │         │
  │       ▼             ▼              ▼         │
  │  DeepSeek Harness   ScreenVision     ToolNet     │
  └─────────────────────────────────────────────┘

初始化顺序:
  1. BrowserUseExecutor   → 创建浏览器执行器
  2. get_screen_aware()   → 创建屏幕感知引擎
  3. get_plugin_registry()→ 初始化插件系统
  4. register_toolnet_as_plugin() → ToolNet 桥接
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("miya.upgrade")


class MiyaUpgradeBridge:
    """
    弥娅能力升级桥接层。

    将 Browser Use Agent、Screen-Aware Proactive 和 Plugin SDK
    统一集成到弥娅的决策中枢。
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self._initialized = False

        self._browser_executor: Any = None
        self._screen_aware: Any = None
        self._plugin_registry: Any = None
        self._toolnet_bridge: Any = None

    def initialize(
        self,
        *,
        browser_use_config: dict | None = None,
        screen_aware_config: dict | None = None,
    ) -> dict[str, bool]:
        """
        初始化所有能力升级。

        返回各模块的初始化状态。
        """
        if not self.enabled:
            return {"enabled": False}

        if self._initialized:
            logger.warning("[UpgradeBridge] 已初始化，跳过")
            return {"already_initialized": True}

        results: dict[str, bool] = {}

        bc = browser_use_config or {}
        results["browser_use"] = self._init_browser_use(
            enabled=bc.get("enabled", True),
        )

        sc = screen_aware_config or {}
        results["screen_aware"] = self._init_screen_aware(
            enabled=sc.get("enabled", True),
            min_interval=sc.get("min_interval_seconds", 30.0),
        )

        results["plugin_sdk"] = self._init_plugin_sdk()
        results["toolnet_bridge"] = self._init_toolnet_bridge()

        self._initialized = all(results.values())
        logger.info(
            f"[UpgradeBridge] 初始化完成: "
            f"browser={results['browser_use']}, "
            f"screen={results['screen_aware']}, "
            f"plugin={results['plugin_sdk']}, "
            f"toolnet={results['toolnet_bridge']}"
        )
        return results

    def _init_browser_use(self, enabled: bool = True) -> bool:
        try:
            from miya_senses.action.browser_use.adapter import BrowserUseExecutor

            self._browser_executor = BrowserUseExecutor(enabled=enabled)
            logger.info("[UpgradeBridge] Browser Use 执行器初始化完成")
            return True
        except Exception as exc:
            logger.warning(f"[UpgradeBridge] Browser Use 初始化失败: {exc}")
            return False

    def _init_screen_aware(self, enabled: bool = True, min_interval: float = 30.0) -> bool:
        try:
            from miya_senses.sensors.screen_aware import get_screen_aware

            self._screen_aware = get_screen_aware(
                enabled=enabled,
                min_interval_seconds=min_interval,
            )
            logger.info("[UpgradeBridge] Screen Aware 初始化完成")
            return True
        except Exception as exc:
            logger.warning(f"[UpgradeBridge] Screen Aware 初始化失败: {exc}")
            return False

    def _init_plugin_sdk(self) -> bool:
        try:
            from plugin_sdk.core.registry import get_plugin_registry

            self._plugin_registry = get_plugin_registry()
            logger.info("[UpgradeBridge] Plugin SDK 初始化完成")
            return True
        except Exception as exc:
            logger.warning(f"[UpgradeBridge] Plugin SDK 初始化失败: {exc}")
            return False

    def _init_toolnet_bridge(self) -> bool:
        try:
            from plugin_sdk.toolnet_bridge import register_toolnet_as_plugin

            self._toolnet_bridge = register_toolnet_as_plugin(self._plugin_registry)
            logger.info("[UpgradeBridge] ToolNet 桥接完成")
            return True
        except Exception as exc:
            logger.warning(f"[UpgradeBridge] ToolNet 桥接失败: {exc}")
            return False

    # ---- 浏览器操作接入 ----

    async def execute_browser_action(
        self,
        action_id: str,
        params: dict | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        """
        执行浏览器操作。

        由 DecisionHub 调用。
        """
        if self._browser_executor is None:
            return {"success": False, "error": "BrowserUse 未初始化"}

        result = await self._browser_executor.execute(
            action_id=action_id,
            params=params or {},
            context=context,
        )

        return {
            "success": result.success,
            "action_id": action_id,
            "reply": result.reply,
            "session_key": result.session_key,
            "status": result.status,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }

    def get_browser_session_keys(self) -> dict[str, str]:
        if self._browser_executor:
            return self._browser_executor.get_session_keys()
        return {}

    # ---- Proactive Intent 消费 ----

    async def consume_proactive_intent(
        self,
        proactive_chat_system: Any = None,
    ) -> Optional[str]:
        """
        消费 screen_aware 产生的主动说话意图，生成并发送消息。
        """
        if self._screen_aware is None:
            return None

        intent = self._screen_aware.should_proactive()
        if intent is None:
            return None

        logger.info(
            f"[UpgradeBridge] 主动说话意图: {intent.trigger_type} "
            f"(priority={intent.priority:.2f}, topic={intent.suggested_topic})"
        )

        return {
            "intent_id": intent.intent_id,
            "trigger_type": intent.trigger_type,
            "topic": intent.suggested_topic,
            "tone": intent.suggested_tone,
            "priority": intent.priority,
            "observation": (
                {
                    "activity": intent.observation.detected_activity,
                    "mood": intent.observation.mood_hint,
                }
                if intent.observation
                else None
            ),
        }

    # ---- 插件接入 ----

    def get_plugin_action_drives(self) -> list[dict]:
        """
        获取所有已注册插件的行动驱动。

        每个插件暴露的行动节点可以被弥娅的决策中枢选中执行。
        """
        if self._plugin_registry is None:
            return []

        drives: list[dict] = []
        for pid, meta in self._plugin_registry.list_plugins():
            plugin = self._plugin_registry.get_plugin(pid)
            if plugin is None:
                continue

            for entry_name, entry in plugin.collect_entries().items():
                if entry.passive:
                    continue
                drives.append(
                    {
                        "action_id": f"action::plugin_{pid}",
                        "entry_name": entry_name,
                        "description": entry.description,
                        "keywords": entry.keywords,
                        "category": entry.category,
                        "plugin_id": pid,
                        "plugin_name": meta.name,
                    }
                )

        return drives

    # ---- 健康检查 ----

    def health_check(self) -> dict:
        return {
            "enabled": self.enabled,
            "initialized": self._initialized,
            "browser_use": self._browser_executor is not None,
            "screen_aware": self._screen_aware is not None,
            "plugin_sdk": self._plugin_registry is not None,
            "plugin_count": (self._plugin_registry.plugin_count if self._plugin_registry else 0),
        }

    # ---- 清理 ----

    async def cleanup(self) -> None:
        if self._browser_executor:
            await self._browser_executor.cleanup()
        if self._plugin_registry:
            await self._plugin_registry.shutdown_all()


_upgrade_bridge: Optional[MiyaUpgradeBridge] = None


def get_upgrade_bridge(**kwargs) -> MiyaUpgradeBridge:
    global _upgrade_bridge
    if _upgrade_bridge is None:
        _upgrade_bridge = MiyaUpgradeBridge(**kwargs)
    return _upgrade_bridge
