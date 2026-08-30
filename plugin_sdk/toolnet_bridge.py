from __future__ import annotations

"""
ToolNet 桥接 — 将现有 ToolNet 工具暴露为弥娅插件

弥娅已有的 ToolNet (webnet/ToolNet/) 包含 25 个工具系列，
每个系列有多个工具。本桥接模块将它们封装为 Plugin SDK 兼容的格式，
使现有的 ToolNet 工具可以通过插件市场发现和使用。

双向桥接:
  ToolNet → Plugin SDK: ToolNet 工具作为 plugin entry 注册
  Plugin SDK → ToolNet: 新插件自动注册为 ToolNet 工具
"""

import logging
from typing import Any, Optional

from plugin_sdk.core.base import MiyaPlugin, PluginEntry, PluginMeta, miya_plugin, plugin_entry
from plugin_sdk.core.registry import PluginRegistry, get_plugin_registry
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger("miya.plugin.toolnet_bridge")


class _FuncTool(BaseTool):
    """将函数包装为 ToolNet 工具对象（对齐主 ToolRegistry.register(tool) 接口）"""

    def __init__(self, name: str, func, description: str = "", category: str = "utility", keywords=None):
        super().__init__(name, description)
        self._func = func
        self._category = category
        self._keywords = keywords or []

    @property
    def config(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, context, **kwargs):
        return await self._func(**kwargs)


@miya_plugin(
    plugin_id="miya_toolnet_bridge",
    name="ToolNet Bridge",
    version="1.0.0",
    description="弥娅内置工具系统桥接",
    category="system",
    auto_start=True,
)
class ToolNetBridgePlugin(MiyaPlugin):
    """
    将 ToolNet 工具暴露为弥娅插件。

    弥娅启动时自动加载，所有 ToolNet 工具以 plugin entry 形式暴露，
    供弥娅的决策中枢调用。
    """

    def __init__(self) -> None:
        super().__init__()
        self._tool_registry = None
        self._exposed_tools: dict[str, dict] = {}

    async def on_startup(self) -> None:
        await super().on_startup()
        await self._expose_toolnet()

    async def _expose_toolnet(self) -> None:
        try:
            from webnet.ToolNet.registry import get_tool_registry

            self._tool_registry = get_tool_registry()
            if self._tool_registry is None:
                self._logger.warning("[ToolNetBridge] ToolRegistry 未初始化")
                return

            for tool_name, tool in self._tool_registry.tools.items():
                self._exposed_tools[tool_name] = {
                    "name": tool_name,
                    "description": getattr(tool, "description", ""),
                    "category": getattr(tool, "category", "utility"),
                    "keywords": getattr(tool, "keywords", []),
                }

            self._logger.info(f"[ToolNetBridge] 暴露 {len(self._exposed_tools)} 个 ToolNet 工具")
        except ImportError:
            self._logger.warning("[ToolNetBridge] ToolNet 不可用")
        except Exception as exc:
            self._logger.error(f"[ToolNetBridge] 暴露 ToolNet 失败: {exc}")

    @plugin_entry(
        description="列出所有可用的弥娅内置工具",
        keywords=["工具", "tools", "内置"],
        category="system",
    )
    async def list_toolnet_tools(self) -> dict[str, Any]:
        return {
            "tools": list(self._exposed_tools.keys()),
            "count": len(self._exposed_tools),
            "details": self._exposed_tools,
        }

    @plugin_entry(
        description="执行一个弥娅内置工具",
        keywords=["执行", "调用", "工具"],
        category="system",
        timeout=60.0,
    )
    async def execute_toolnet_tool(self, tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._tool_registry is None:
            return {"success": False, "error": "ToolRegistry 未初始化"}

        try:
            result = await self._tool_registry.execute_tool(tool_name, ToolContext(), **(args or {}))
            return {"success": True, "tool_name": tool_name, "result": result}
        except Exception as exc:
            return {"success": False, "tool_name": tool_name, "error": str(exc)}

    def get_exposed_tool_names(self) -> list[str]:
        return list(self._exposed_tools.keys())


def register_toolnet_as_plugin(registry: Optional[PluginRegistry] = None) -> ToolNetBridgePlugin:
    reg = registry or get_plugin_registry()
    bridge = ToolNetBridgePlugin()
    reg.register(bridge)
    logger.info("[ToolNetBridge] 已注册 ToolNet 桥接插件")
    return bridge


def register_plugin_as_toolnet_tool(
    plugin_id: str,
    entry_name: str,
    plugin: MiyaPlugin,
    entry: PluginEntry,
) -> None:
    """
    将插件入口点注册为 ToolNet 工具。

    当弥娅需要一个操作时，它可以：
    1. 直接调用 action::tool_call {tool_name=plugin_id.entry_name}
    2. ToolNet 路由到相应的插件入口点
    """
    try:
        from webnet.ToolNet.registry import get_tool_registry

        registry = get_tool_registry()
        if registry is None:
            return

        tool_name = f"plugin::{plugin_id}::{entry_name}"

        async def wrapper(**kwargs):
            result = await entry.func(plugin, **kwargs)
            return result

        wrapper.__name__ = tool_name
        wrapper.description = entry.description
        wrapper.category = entry.category
        wrapper.keywords = entry.keywords + [plugin_id, "plugin"]

        registry.register(
            _FuncTool(
                name=tool_name,
                func=wrapper,
                description=entry.description,
                category=entry.category,
                keywords=wrapper.keywords,
            )
        )

        logger.debug(f"[ToolNetBridge] 注册插件工具: {tool_name}")
    except ImportError:
        pass
    except Exception as exc:
        logger.warning(f"[ToolNetBridge] 注册插件工具失败 {plugin_id}.{entry_name}: {exc}")
