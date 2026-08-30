"""
MIYA Star 插件系统 (独立版本)

灵感来自 AstrBot，完全独立的插件系统
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StarEventType(str, Enum):
    """Star 事件类型"""

    MESSAGE = "message"
    PRIVATE_MESSAGE = "private_message"
    GROUP_MESSAGE = "group_message"
    COMMAND = "command"
    REGEX = "regex"
    MENTION = "mention"
    TIMER = "timer"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    FILE_RECEIVED = "file_received"
    VOICE_RECEIVED = "voice_received"


@dataclass
class StarContext:
    """Star 执行上下文"""

    event_type: str
    message: Any = None
    user_id: Optional[str] = None
    user_name: str = ""
    group_id: Optional[str] = None
    group_name: str = ""
    platform: str = "qq"
    session_id: Optional[str] = None
    raw_message: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StarInfo:
    """Star 信息"""

    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    enabled: bool = True
    loaded: bool = False


class Star(ABC):
    """
    Star 插件基类

    使用方式:
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

    async def on_private_message(self, context: StarContext) -> Optional[Any]:
        """处理私聊消息"""
        pass

    async def on_group_message(self, context: StarContext) -> Optional[Any]:
        """处理群消息"""
        pass

    async def on_command(self, context: StarContext, command: str, args: List[str]) -> Optional[Any]:
        """处理命令"""
        pass

    async def on_regex(self, context: StarContext, match: Any) -> Optional[Any]:
        """处理正则匹配"""
        pass

    async def on_mention(self, context: StarContext) -> Optional[Any]:
        """处理@提及"""
        pass

    async def on_timer(self, context: StarContext) -> Optional[Any]:
        """定时任务"""
        pass

    async def on_startup(self, context: StarContext) -> Optional[Any]:
        """启动事件"""
        pass

    async def on_shutdown(self, context: StarContext) -> Optional[Any]:
        """停止事件"""
        pass

    def get_context(self) -> Optional[StarContext]:
        """获取上下文"""
        return self._ctx


class StarManager:
    """
    MIYA Star 插件管理器

    负责:
    - 插件加载/卸载/启用/禁用
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
        self._star_classes: Dict[str, type] = {}
        self._commands: Dict[str, Callable] = {}
        self._command_aliases: Dict[str, str] = {}
        self._event_handlers: Dict[StarEventType, List[Callable]] = {}
        self._timers: List[Dict] = []
        self._initialized = True

        logger.info("[StarManager] 初始化完成")

    def register_star_class(self, star_cls: type, name: str = None):
        """注册 Star 类"""
        star_name = name or (star_cls.name if hasattr(star_cls, "name") else star_cls.__name__.lower())
        self._star_classes[star_name] = star_cls
        logger.info(f"[StarManager] 注册 Star: {star_name}")

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
        logger.info(f"[StarManager] 注册命令: {name}")

    def register_event_handler(self, event_type: StarEventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.info(f"[StarManager] 注册事件: {event_type}")

    async def load_star(self, name: str, config: Optional[Dict] = None) -> Optional[Star]:
        """加载并激活 Star"""
        star_cls = self._star_classes.get(name)
        if not star_cls:
            logger.warning(f"[StarManager] Star不存在: {name}")
            return None

        try:
            star = star_cls()
            await star.activate()
            self._stars[name] = star
            logger.info(f"[StarManager] 已加载: {name}")
            return star
        except Exception as e:
            logger.error(f"[StarManager] 加载失败 {name}: {e}")
            return None

    async def unload_star(self, name: str):
        """卸载 Star"""
        if name in self._stars:
            star = self._stars[name]
            try:
                await star.deactivate()
                del self._stars[name]
                logger.info(f"[StarManager] 已卸载: {name}")
            except Exception as e:
                logger.error(f"[StarManager] 卸载失败 {name}: {e}")

    async def enable_star(self, name: str):
        """启用 Star"""
        if name in self._stars:
            self._stars[name]._enabled = True
            logger.info(f"[StarManager] 已启用: {name}")

    async def disable_star(self, name: str):
        """禁用 Star"""
        if name in self._stars:
            self._stars[name]._enabled = False
            logger.info(f"[StarManager] 已禁用: {name}")

    def get_star(self, name: str) -> Optional[Star]:
        """获取 Star"""
        return self._stars.get(name)

    def list_stars(self) -> List[StarInfo]:
        """列出所有 Star"""
        result = []
        for name, star in self._stars.items():
            result.append(
                StarInfo(
                    name=name,
                    description=star.description,
                    version=star.version,
                    author=star.author,
                    enabled=star._enabled,
                    loaded=True,
                )
            )
        return result

    def get_command(self, name: str) -> Optional[Callable]:
        """获取命令处理器"""
        if name in self._commands:
            return self._commands[name]
        if name in self._command_aliases:
            return self._commands.get(self._command_aliases[name])
        return None

    def list_commands(self) -> Dict[str, str]:
        """列出所有命令"""
        return {name: cmd.__doc__ or "" for name, cmd in self._commands.items()}

    async def dispatch_event(self, event_type: StarEventType, context: StarContext):
        """分发事件给所有Star"""
        for name, star in self._stars.items():
            if not star._enabled:
                continue

            try:
                handler_map = {
                    StarEventType.MESSAGE: star.on_message,
                    StarEventType.PRIVATE_MESSAGE: star.on_private_message,
                    StarEventType.GROUP_MESSAGE: star.on_group_message,
                    StarEventType.MENTION: star.on_mention,
                    StarEventType.STARTUP: star.on_startup,
                    StarEventType.SHUTDOWN: star.on_shutdown,
                    StarEventType.TIMER: star.on_timer,
                }

                handler = handler_map.get(event_type)
                if handler and asyncio.iscoroutinefunction(handler):
                    await handler(context)
                elif handler:
                    handler(context)
            except Exception as e:
                logger.error(f"[StarManager] 事件处理失败 {name}: {e}")

    async def handle_command(self, context: StarContext, command: str, args: List[str]) -> Optional[Any]:
        """处理命令"""
        # 先尝试 Star
        for name, star in self._stars.items():
            if not star._enabled:
                continue
            if hasattr(star, "on_command"):
                try:
                    result = await star.on_command(context, command, args)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.error(f"[StarManager] 命令处理失败 {name}: {e}")

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


# 装饰器


def star(
    name: str = "",
    description: str = "",
    version: str = "1.0.0",
    author: str = "",
):
    """Star 插件装饰器"""

    def decorator(cls):
        if not issubclass(cls, Star):
            raise TypeError("star 装饰器只能用于 Star 子类")

        cls.name = name or cls.__name__.lower()
        cls.description = description
        cls.version = version
        cls.author = author

        # 延迟注册 - 在模块加载完成后通过 get_star_manager() 注册
        def register_later():
            try:
                sm = get_star_manager()
                sm.register_star_class(cls, cls.name)
            except Exception as e:
                logger.warning(f"Star 注册延迟: {e}")

        # 保存到待注册列表
        if not hasattr(cls, "_register_callback"):
            cls._register_callback = register_later

        return cls

    return decorator


def command(
    name: str,
    description: str = "",
    aliases: Optional[List[str]] = None,
):
    """注册命令装饰器"""

    def decorator(func: Callable):
        # 延迟注册
        def register_later():
            try:
                sm = get_star_manager()
                sm.register_command(name, func, description, aliases)
            except Exception as e:
                logger.warning(f"Command 注册延迟: {e}")

        if not hasattr(func, "_register_callback"):
            func._register_callback = register_later
        return func

    return decorator


def on_event(event_type: StarEventType):
    """注册事件装饰器"""

    def decorator(func: Callable):
        # 延迟注册
        def register_later():
            try:
                sm = get_star_manager()
                sm.register_event_handler(event_type, func)
            except Exception as e:
                logger.warning(f"Event handler 注册延迟: {e}")

        if not hasattr(func, "_register_callback"):
            func._register_callback = register_later
        return func

    return decorator


# 全局实例
_star_manager = None


def get_star_manager() -> StarManager:
    """获取 Star 管理器"""
    global _star_manager
    if _star_manager is None:
        _star_manager = StarManager()
    return _star_manager


# 示例 Star


@star(name="help", description="帮助插件 - 显示可用命令", version="1.0.0", author="MIYA")
class HelpStar(Star):
    """帮助插件"""

    async def activate(self):
        logger.info("[HelpStar] 已激活")

    async def deactivate(self):
        logger.info("[HelpStar] 已停用")

    async def on_command(self, context: StarContext, command: str, args: List[str]) -> Optional[str]:
        if command == "/help":
            manager = get_star_manager()
            stars = manager.list_stars()
            commands = manager.list_commands()

            msg = "=== MIYA 帮助 ===\n\n"
            msg += "📦 已加载的插件:\n"
            for s in stars:
                status = "✅" if s.enabled else "❌"
                msg += f"  {status} {s.name}: {s.description}\n"

            msg += "\n📝 可用命令:\n"
            for cmd, desc in commands.items():
                msg += f"  {cmd}: {desc}\n"

            return msg
        return None


@command("/ping", description="Ping测试", aliases=["/p"])
async def ping_command(context: StarContext, *args):
    return "Pong! 🏓"


__all__ = [
    "Star",
    "StarContext",
    "StarInfo",
    "StarManager",
    "StarEventType",
    "get_star_manager",
    "star",
    "command",
    "on_event",
]
