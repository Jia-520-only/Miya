"""
Miya Star System - 插件系统

参考 AstrBot 的 Star 插件架构
- 支持插件热重载
- 事件机制
- 依赖管理
- 配置文件
"""

import logging
import os
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

logger = logging.getLogger("miya.star")


@dataclass
class StarMetadata:
    """插件元数据"""

    name: str | None = None
    author: str | None = None
    desc: str | None = None
    version: str | None = None
    repo: str | None = None

    star_cls_type: type | None = None
    module_path: str | None = None
    star_cls: Any = None
    module: ModuleType | None = None
    root_dir_name: str | None = None
    reserved: bool = False
    activated: bool = True

    config: Any = None
    star_handler_full_names: list[str] = field(default_factory=list)
    display_name: str | None = None
    logo_path: str | None = None
    support_platforms: list[str] = field(default_factory=list)
    miya_version: str | None = None


# 插件注册表
star_registry: list[StarMetadata] = []
star_map: dict[str, StarMetadata] = {}


class Star:
    """插件基类"""

    author: str = "Miya"
    name: str = "star"

    def __init__(self, context: Any, config: dict | None = None) -> None:
        self.context = context
        self.config = config or {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not star_map.get(cls.__module__):
            metadata = StarMetadata(
                star_cls_type=cls,
                module_path=cls.__module__,
            )
            star_map[cls.__module__] = metadata
            star_registry.append(metadata)
        else:
            star_map[cls.__module__].star_cls_type = cls
            star_map[cls.__module__].module_path = cls.__module__

    async def initialize(self) -> None:
        """插件激活时调用"""
        pass

    async def terminate(self) -> None:
        """插件禁用时调用"""
        pass


# 事件类型
class EventType:
    """事件类型常量"""

    ON_MIYA_LOADED = "on_miya_loaded"
    ON_PLATFORM_LOADED = "on_platform_loaded"
    ADAPTER_MESSAGE = "adapter_message"
    ON_LLM_REQUEST = "on_llm_request"
    ON_LLM_RESPONSE = "on_llm_response"
    ON_AGENT_BEGIN = "on_agent_begin"
    ON_AGENT_DONE = "on_agent_done"
    ON_DECORATING_RESULT = "on_decorating_result"
    ON_CALLING_FUNC_TOOL = "on_calling_func_tool"
    ON_PLUGIN_LOADED = "on_plugin_loaded"
    ON_PLUGIN_UNLOADED = "on_plugin_unloaded"


# 处理器注册表
_handler_registry: dict[str, list] = {}


def register_handler(event_type: str):
    """事件处理器装饰器"""

    def decorator(func):
        if event_type not in _handler_registry:
            _handler_registry[event_type] = []
        _handler_registry[event_type].append(func)
        return func

    return decorator


def get_handlers(event_type: str) -> list:
    """获取事件处理器"""
    return _handler_registry.get(event_type, [])


async def emit_event(event_type: str, **kwargs) -> None:
    """触发事件"""
    handlers = get_handlers(event_type)
    for handler in handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(**kwargs)
            else:
                handler(**kwargs)
        except Exception as e:
            logger.error(f"[Star] 事件处理错误 {event_type}: {e}")


import asyncio

__all__ = [
    "Star",
    "StarMetadata",
    "star_registry",
    "star_map",
    "EventType",
    "register_handler",
    "get_handlers",
    "emit_event",
]
