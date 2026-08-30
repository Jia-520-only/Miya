from __future__ import annotations

"""
弥娅插件核心 — 基类、装饰器、元数据

弥娅插件的最小定义：
  1. 继承 MiyaPlugin
  2. 用 @miya_plugin 装饰
  3. 实现至少一个 @plugin_entry 方法
"""

import functools
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("miya.plugin")


@dataclass
class PluginMeta:
    """插件元数据"""

    plugin_id: str
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    keywords: list[str] = field(default_factory=list)
    category: str = "utility"  # utility, game, social, knowledge, creative, system
    min_sdk_version: str = "1.0.0"
    auto_start: bool = False
    single_instance: bool = True
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    homepage: str = ""
    source: str = "local"  # local, market


class PluginEntry:
    """插件入口点"""

    def __init__(self, func: Callable, meta: dict | None = None):
        self.func = func
        self.name = func.__name__
        self.description = (meta or {}).get("description", func.__doc__ or "")
        self.keywords: list[str] = (meta or {}).get("keywords", [])
        self.category: str = (meta or {}).get("category", "general")
        self.passive: bool = (meta or {}).get("passive", False)
        self.auto_approve: bool = (meta or {}).get("auto_approve", False)
        self.timeout: float = float((meta or {}).get("timeout", 30.0))

    def __repr__(self):
        return f"PluginEntry({self.name})"


class MiyaPlugin:
    """
    弥娅插件基类。

    集成说明：
      - 每个插件自动注册为行动节点 (action::plugin_{plugin_id})
      - 弥娅的决策中枢可以在需要时选中插件执行
    """

    def __init__(self):
        self.meta: PluginMeta = PluginMeta(plugin_id=self.__class__.__name__)
        self.entries: dict[str, PluginEntry] = {}
        self._started = False
        self._logger = logging.getLogger(f"miya.plugin.{self.meta.plugin_id}")

    def collect_entries(self) -> dict[str, PluginEntry]:
        if self.entries:
            return dict(self.entries)
        for name in dir(self):
            obj = getattr(self, name, None)
            if isinstance(obj, PluginEntry):
                self.entries[name] = obj
        return dict(self.entries)

    async def on_startup(self) -> None:
        self._started = True
        self._logger.info(f"插件启动: {self.meta.name}")

    async def on_shutdown(self) -> None:
        self._started = False
        self._logger.info(f"插件关闭: {self.meta.name}")

    async def on_freeze(self) -> None:
        self._logger.info(f"插件冻结: {self.meta.name}")

    async def on_unfreeze(self) -> None:
        self._logger.info(f"插件恢复: {self.meta.name}")

    async def health_check(self) -> dict:
        return {"healthy": True, "plugin_id": self.meta.plugin_id}

    @property
    def is_running(self) -> bool:
        return self._started


def miya_plugin(
    plugin_id: str = "",
    name: str = "",
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    keywords: list | None = None,
    category: str = "utility",
    auto_start: bool = False,
    permissions: list | None = None,
    dependencies: list | None = None,
):
    """
    弥娅插件注册装饰器。

    使用方式：
        @miya_plugin(
            plugin_id="my_web_search",
            name="Web Search",
            description="搜索互联网",
            category="knowledge",
        )
        class WebSearchPlugin(MiyaPlugin):
            ...
    """

    def decorator(cls):
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.meta = PluginMeta(
                plugin_id=plugin_id or cls.__name__,
                name=name or cls.__name__,
                version=version,
                description=description or cls.__doc__ or "",
                author=author,
                keywords=list(keywords or []),
                category=category,
                auto_start=auto_start,
                permissions=list(permissions or []),
                dependencies=list(dependencies or []),
            )
            self._logger = logging.getLogger(f"miya.plugin.{self.meta.plugin_id}")

        cls.__init__ = new_init
        return cls

    return decorator


def plugin_entry(
    description: str = "",
    keywords: list | None = None,
    category: str = "general",
    passive: bool = False,
    auto_approve: bool = False,
    timeout: float = 30.0,
):
    """
    插件入口点装饰器。

    使用方式：
        @plugin_entry(description="搜索互联网", keywords=["搜索", "web"])
        async def search(self, query: str) -> str:
            ...
    """
    meta = {
        "description": description,
        "keywords": list(keywords or []),
        "category": category,
        "passive": passive,
        "auto_approve": auto_approve,
        "timeout": timeout,
    }

    def decorator(func):
        entry = PluginEntry(func, meta)
        func._plugin_entry = entry
        return entry

    return decorator
