from __future__ import annotations

"""
弥娅 Plugin SDK — 让弥娅的能力可扩展

弥娅的插件系统允许开发者（或佳自己）为弥娅添加新能力。
灵感来自 N.E.K.O 的插件生态，深度集成到弥娅的决策中枢中。

核心概念：
  - Plugin: 独立的能力单元，可被决策中枢选中调用
  - Extension: 扩展现有插件的行为（类似中间件）
  - Adapter: 协议适配器（如 MCP 协议翻译）
  - Market: 插件市场，发现和安装

架构：
  plugin_sdk/
  ├── core/         # 核心 SDK（装饰器、基类、注册表）
  ├── message_plane/ # 插件间通信
  └── toolnet_bridge.py  # 与现有 ToolNet 的双向桥接
"""

from plugin_sdk.core import MiyaPlugin, PluginMeta, miya_plugin, plugin_entry
from plugin_sdk.core.registry import PluginRegistry

__all__ = [
    "MiyaPlugin",
    "PluginMeta",
    "miya_plugin",
    "plugin_entry",
    "PluginRegistry",
]
