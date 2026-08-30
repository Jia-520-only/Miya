"""
MIYA Star Plugin System (内联版)

灵感来自 AstrBot 插件系统，让 MIYA 可以加载和管理插件
支持:
- 事件处理 (on_message, on_command, on_regex)
- 定时任务 (cron)
- 工具注册 (tools)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型"""

    MESSAGE = "message"
    PRIVATE_MESSAGE = "private_message"
    GROUP_MESSAGE = "group_message"
    COMMAND = "command"
    REGEX = "regex"
    MENTION = "mention"
    TIMER = "timer"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


@dataclass
class StarContext:
    """插件执行上下文"""

    event: Any
    message: Any
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    platform: str = ""
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Star(ABC):
    """
    Star 插件基类

    使用方式:
    @register_star()
    class MyStar(Star):
        name = "my_plugin"
        description = "我的插件"

        async def activate(self):
            pass

        async def deactivate(self):
            pass
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""

    _enabled: bool = True
    _ctx: Optional[StarContext] = None
    _hooks: Dict[str, Callable] = field(default_factory=dict)

    @abstractmethod
    async def activate(self):
        """激活插件"""
        pass

    @abstractmethod
    async def deactivate(self):
        """停用插件"""
        pass

    async def on_message(self, context: StarContext) -> Optional[Any]:
        """处理消息事件"""
        pass

    async def on_command(self, context: StarContext, command: str, args: List[str]) -> Optional[Any]:
        """处理命令"""
        pass

    async def on_regex(self, context: StarContext, match: Any) -> Optional[Any]:
        """处理正则匹配"""
        pass

    async def on_timer(self, context: StarContext) -> Optional[Any]:
        """定时任务"""
        pass

    def register_hook(self, event_type: str, handler: Callable):
        """注册事件钩子"""
        self._hooks[event_type] = handler

    def get_ctx(self) -> Optional[StarContext]:
        """获取上下文"""
        return self._ctx


def register_star(
    name: Optional[str] = None,
    description: str = "",
    version: str = "1.0.0",
    author: str = "",
):
    """Star 插件装饰器"""

    def decorator(cls):
        if not issubclass(cls, Star):
            raise TypeError("Star 装饰器只能用于 Star 子类")

        cls.name = name or cls.__name__.lower()
        cls.description = description
        cls.version = version
        cls.author = author

        StarManager.get_instance().register(cls)
        return cls

    return decorator


def command(
    name: str,
    description: str = "",
    aliases: Optional[List[str]] = None,
):
    """注册命令装饰器"""

    def decorator(func: Callable):
        StarManager.get_instance().register_command(name, func, description, aliases)
        return func

    return decorator


def register_event(event_type: EventType):
    """注册事件类型装饰器"""

    def decorator(func: Callable):
        StarManager.get_instance().register_event_handler(event_type, func)
        return func

    return decorator


class StarManager:
    """
    Star 插件管理器

    负责:
    - 插件加载/卸载
    - 事件分发
    - 命令路由
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

        self._stars: Dict[str, Star] = {}
        self._star_classes: Set[type] = set()
        self._commands: Dict[str, Callable] = {}
        self._command_aliases: Dict[str, str] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._enabled_stars: Set[str] = set()
        self._initialized = True

        logger.info("[StarManager] 初始化完成")

    @staticmethod
    def get_instance() -> "StarManager":
        return StarManager()

    def register(self, star_cls: type):
        """注册 Star 类"""
        self._star_classes.add(star_cls)
        logger.debug(f"[StarManager] 注册 Star: {star_cls.name}")

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        aliases: Optional[List[str]] = None,
    ):
        """注册命令"""
        self._commands[name] = handler
        if aliases:
            for alias in aliases:
                self._command_aliases[alias] = name
        logger.debug(f"[StarManager] 注册命令: {name}")

    def register_event_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"[StarManager] 注册事件: {event_type}")

    async def load_star(self, star_cls: type, config: Optional[Dict] = None) -> Star:
        """加载并激活 Star"""
        star = star_cls()
        try:
            await star.activate()
            self._stars[star.name] = star
            self._enabled_stars.add(star.name)
            logger.info(f"[StarManager] 已加载: {star.name}")
            return star
        except Exception as e:
            logger.error(f"[StarManager] 加载失败 {star.name}: {e}")
            raise

    async def unload_star(self, star_name: str):
        """卸载 Star"""
        if star_name in self._stars:
            star = self._stars[star_name]
            try:
                await star.deactivate()
                del self._stars[star_name]
                self._enabled_stars.discard(star_name)
                logger.info(f"[StarManager] 已卸载: {star_name}")
            except Exception as e:
                logger.error(f"[StarManager] 卸载失败 {star_name}: {e}")

    async def load_all(self, config: Optional[Dict] = None):
        """加载所有注册的 Star"""
        for star_cls in self._star_classes:
            try:
                await self.load_star(star_cls, config)
            except Exception as e:
                logger.error(f"[StarManager] 加载 {star_cls.name} 失败: {e}")

    async def unload_all(self):
        """卸载所有 Star"""
        for star_name in list(self._stars.keys()):
            await self.unload_star(star_name)

    def get_star(self, name: str) -> Optional[Star]:
        """获取 Star"""
        return self._stars.get(name)

    def list_stars(self) -> List[Dict]:
        """列出所有 Star"""
        return [
            {
                "name": star.name,
                "description": star.description,
                "version": star.version,
                "author": star.author,
                "enabled": star.name in self._enabled_stars,
            }
            for star in self._stars.values()
        ]

    def get_command(self, name: str) -> Optional[Callable]:
        """获取命令处理器"""
        if name in self._commands:
            return self._commands[name]
        if name in self._command_aliases:
            real_name = self._command_aliases[name]
            return self._commands.get(real_name)
        return None

    def list_commands(self) -> Dict[str, str]:
        """列出所有命令"""
        return {name: cmd.__doc__ or "" for name, cmd in self._commands.items()}

    async def dispatch_event(self, event_type: EventType, context: StarContext):
        """分发事件"""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(context)
                    else:
                        handler(context)
                except Exception as e:
                    logger.error(f"[StarManager] 事件处理失败: {e}")

    async def handle_command(self, context: StarContext, command: str, args: List[str]) -> Optional[Any]:
        """处理命令"""
        # 先尝试 Star 命令
        for star in self._stars.values():
            if star._enabled and hasattr(star, "on_command"):
                try:
                    result = await star.on_command(context, command, args)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.error(f"[StarManager] 命令处理失败: {e}")

        # 再尝试全局命令
        handler = self.get_command(command)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(context, *args)
                else:
                    return handler(context, *args)
            except Exception as e:
                logger.error(f"[StarManager] 命令执行失败: {e}")

        return None


# 内置工具注册
class ToolRegistry:
    """工具注册表"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tools: Dict[str, Callable] = {}
        self._initialized = True

    def register(self, name: str, func: Callable, description: str = ""):
        """注册工具"""
        self._tools[name] = func
        logger.debug(f"[ToolRegistry] 注册工具: {name}")

    def get(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict]:
        """列出工具"""
        return [{"name": name, "description": func.__doc__ or ""} for name, func in self._tools.items()]


def register_tool(name: str, description: str = ""):
    """注册工具装饰器"""

    def decorator(func: Callable):
        ToolRegistry.get_instance().register(name, func, description)
        return func

    return decorator


def get_star_manager() -> StarManager:
    return StarManager()


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry()
