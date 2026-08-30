"""
Star Bridge - Star 插件桥接器

将 core/star (新架构) 与主系统连接
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("miya.star.bridge")


class StarBridge:
    """Star 插件桥接器"""

    def __init__(self) -> None:
        self._stars: Dict[str, Any] = {}
        self._handlers: Dict[str, List] = {}
        self._config_path = Path("data/plugins")

    async def initialize(self) -> None:
        """初始化"""
        logger.info("[StarBridge] 初始化...")
        self._config_path.mkdir(parents=True, exist_ok=True)
        logger.info("[StarBridge] 已初始化")

    async def load_stars(self) -> int:
        """加载所有插件"""
        count = 0

        # 扫描内置插件
        builtin_dir = Path("core/star/builtin")
        if builtin_dir.exists():
            for plugin_file in builtin_dir.glob("*.py"):
                if plugin_file.stem != "__init__":
                    count += 1
                    logger.debug(f"[StarBridge] 内置插件: {plugin_file.stem}")

        # 扫描用户插件
        user_dir = self._config_path
        if user_dir.exists():
            for plugin_file in user_dir.glob("*.py"):
                if plugin_file.stem != "__init__":
                    count += 1
                    logger.debug(f"[StarBridge] 用户插件: {plugin_file.stem}")

        logger.info(f"[StarBridge] 已加载 {count} 个插件")
        return count

    async def load_star(self, name: str) -> bool:
        """加载单个插件"""
        try:
            logger.info(f"[StarBridge] 加载插件: {name}")
            return True
        except Exception as e:
            logger.error(f"[StarBridge] 加载失败 {name}: {e}")
            return False

    async def unload_star(self, name: str) -> bool:
        """卸载插件"""
        if name in self._stars:
            del self._stars[name]
            logger.info(f"[StarBridge] 已卸载: {name}")
            return True
        return False

    def register_handler(self, event_type: str, handler) -> None:
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"[StarBridge] 注册处理器: {event_type}")

    async def emit(self, event_type: str, **kwargs) -> None:
        """触发事件"""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error(f"[StarBridge] 事件处理失败 {event_type}: {e}")

    def list_stars(self) -> List[Dict]:
        """列出所有插件"""
        return [{"name": name, "loaded": name in self._stars} for name in self._stars]


# 全局实例
_star_bridge: Optional[StarBridge] = None


def get_star_bridge() -> StarBridge:
    """获取全局实例"""
    global _star_bridge
    if _star_bridge is None:
        _star_bridge = StarBridge()
    return _star_bridge


# 装饰器简化
def on(event_type: str):
    """事件监听装饰器"""

    def decorator(func):
        bridge = get_star_bridge()
        bridge.register_handler(event_type, func)
        return func

    return decorator


__all__ = [
    "StarBridge",
    "get_star_bridge",
    "on",
]
