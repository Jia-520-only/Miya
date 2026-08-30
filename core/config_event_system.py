"""配置事件系统

负责配置更新事件的发布和订阅
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ConfigEvent:
    """配置更新事件"""

    event_type: str  # config_update, config_reload, error
    timestamp: float
    changes: Dict[str, Any]
    source: str = "config_hot_reload"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfigEventPublisher:
    """配置事件发布器

    职责：
    - 管理事件订阅者
    - 发布配置更新事件
    - 通过WebSocket通知前端
    """

    def __init__(self, runtime_api=None):
        """
        初始化事件发布器

        Args:
            runtime_api: Runtime API实例（用于WebSocket通知）
        """
        self.runtime_api = runtime_api
        self._event_subscribers: Dict[str, List[Callable[[ConfigEvent], None]]] = {}
        self._all_subscribers: List[Callable[[ConfigEvent], None]] = []

    def subscribe_event(self, event_type: str, callback: Callable[[ConfigEvent], None]) -> None:
        """订阅特定类型的事件

        Args:
            event_type: 事件类型，如 'config_update', 'config_reload', 'error'
            callback: 回调函数，接收ConfigEvent对象
        """
        if event_type not in self._event_subscribers:
            self._event_subscribers[event_type] = []
        self._event_subscribers[event_type].append(callback)
        logger.debug(f"[配置事件] 新增订阅者: event_type={event_type}")

    def subscribe_all_events(self, callback: Callable[[ConfigEvent], None]) -> None:
        """订阅所有事件

        Args:
            callback: 回调函数，接收ConfigEvent对象
        """
        self._all_subscribers.append(callback)
        logger.debug("[配置事件] 新增全局订阅者")

    def unsubscribe_event(self, event_type: str, callback: Callable[[ConfigEvent], None]) -> None:
        """取消订阅特定类型的事件"""
        if event_type in self._event_subscribers and callback in self._event_subscribers[event_type]:
            self._event_subscribers[event_type].remove(callback)
            logger.debug(f"[配置事件] 移除订阅者: event_type={event_type}")

    def unsubscribe_all_events(self, callback: Callable[[ConfigEvent], None]) -> None:
        """取消订阅所有事件"""
        if callback in self._all_subscribers:
            self._all_subscribers.remove(callback)
            logger.debug("[配置事件] 移除全局订阅者")

    async def publish_event(self, event: ConfigEvent) -> None:
        """发布事件到所有订阅者

        Args:
            event: 配置更新事件
        """
        try:
            # 先通知全局订阅者
            for callback in self._all_subscribers:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"[配置事件] 全局订阅者回调异常: {e}", exc_info=True)

            # 再通知特定类型的订阅者
            if event.event_type in self._event_subscribers:
                for callback in self._event_subscribers[event.event_type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.error(f"[配置事件] 订阅者回调异常 (type={event.event_type}): {e}", exc_info=True)

            # 尝试通过WebSocket通知（如果有runtime_api）
            if self.runtime_api:
                await self._notify_via_websocket(event)

            logger.debug(f"[配置事件] 事件已发布: type={event.event_type}, changes={list(event.changes.keys())}")

        except Exception as e:
            logger.error(f"[配置事件] 事件发布失败: {e}", exc_info=True)

    async def _notify_via_websocket(self, event: ConfigEvent) -> None:
        """通过WebSocket通知前端

        Args:
            event: 配置更新事件
        """
        try:
            if hasattr(self.runtime_api, "notify_config_change"):
                await self.runtime_api.notify_config_change(
                    {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "changes": event.changes,
                        "source": event.source,
                    }
                )
        except Exception as e:
            logger.debug(f"[配置事件] WebSocket通知失败: {e}")
