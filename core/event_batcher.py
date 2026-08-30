"""
Miya 事件通知批处理模块 - 性能优化
================================

该模块提供高频事件的批量通知功能,减少系统负载。
支持基于时间窗口和事件数量的批处理策略。

设计目标:
- 减少事件通知开销 20-40%
- 降低系统负载和CPU使用率
- 保持事件顺序和完整性
- 可配置的批处理策略
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BatchedEvent:
    """批量事件"""

    events: List[Dict[str, Any]] = field(default_factory=list)
    batch_id: str = ""
    batch_size: int = 0
    timestamp: float = 0.0
    event_type: str = ""


@dataclass
class BatchConfig:
    """批处理配置"""

    max_batch_size: int = 100  # 最大批量大小
    max_batch_delay: float = 1.0  # 最大批处理延迟(秒)
    min_batch_size: int = 10  # 最小批量大小
    enable_adaptive: bool = True  # 启用自适应批处理


class EventBatcher:
    """事件批处理器"""

    def __init__(self, config: Optional[BatchConfig] = None, max_workers: int = 4):
        self.config = config or BatchConfig()
        self.max_workers = max_workers

        # 事件队列(按事件类型分组)
        self._event_queues: Dict[str, deque] = defaultdict(deque)

        # 批处理定时器
        self._batch_timers: Dict[str, asyncio.Task] = {}
        self._last_batch_time: Dict[str, float] = {}

        # 订阅者管理
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # 统计信息
        self.stats = {
            "total_events": 0,
            "batches_processed": 0,
            "batched_events": 0,
            "direct_events": 0,
            "avg_batch_size": 0.0,
        }

        # 锁
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(f"[事件批处理] 初始化完成, max_batch_size={self.config.max_batch_size}")

    async def publish_event(self, event_type: str, event_data: Dict[str, Any]):
        """发布事件(自动批处理)"""
        with self._lock:
            self.stats["total_events"] += 1

            # 检查是否需要批处理
            subscribers = self._subscribers.get(event_type, [])

            if len(subscribers) > 3:  # 订阅者多时才批处理
                # 添加到批处理队列
                self._event_queues[event_type].append(event_data)
                queue_size = len(self._event_queues[event_type])

                # 检查是否达到批量大小
                if queue_size >= self.config.max_batch_size:
                    await self._flush_event_queue(event_type)
                else:
                    # 启动批处理定时器
                    await self._start_batch_timer(event_type)

                self.stats["batched_events"] += 1
            else:
                # 订阅者少时直接发送
                await self._notify_subscribers_directly(event_type, [event_data])
                self.stats["direct_events"] += 1

    async def _start_batch_timer(self, event_type: str):
        """启动批处理定时器"""
        # 取消现有定时器
        if event_type in self._batch_timers:
            self._batch_timers[event_type].cancel()

        # 创建新定时器
        async def flush_after_delay():
            try:
                await asyncio.sleep(self.config.max_batch_delay)
                await self._flush_event_queue(event_type)
            except asyncio.CancelledError:
                pass

        self._batch_timers[event_type] = asyncio.create_task(flush_after_delay())

    async def _flush_event_queue(self, event_type: str):
        """刷新事件队列(发送批量事件)"""
        with self._lock:
            queue = self._event_queues[event_type]

            if not queue:
                return

            # 检查是否达到最小批量
            if len(queue) < self.config.min_batch_size:
                return

            # 取出所有事件
            events = list(queue)
            queue.clear()

            # 取消定时器
            if event_type in self._batch_timers:
                self._batch_timers[event_type].cancel()
                del self._batch_timers[event_type]

        # 创建批量事件
        batched_event = BatchedEvent(
            events=events,
            batch_id=f"{event_type}_{int(time.time() * 1000)}",
            batch_size=len(events),
            timestamp=time.time(),
            event_type=event_type,
        )

        # 通知订阅者
        await self._notify_subscribers_batched(event_type, batched_event)

        # 更新统计
        with self._lock:
            self.stats["batches_processed"] += 1
            total_batches = self.stats["batches_processed"]
            avg_size = (self.stats["avg_batch_size"] * (total_batches - 1) + len(events)) / total_batches
            self.stats["avg_batch_size"] = avg_size

        logger.debug(f"[事件批处理] 批量发送: {event_type}, 数量={len(events)}")

    async def _notify_subscribers_directly(self, event_type: str, events: List[Dict[str, Any]]):
        """直接通知订阅者(单事件)"""
        subscribers = self._subscribers.get(event_type, [])

        tasks = []
        for subscriber in subscribers:
            for event in events:
                task = asyncio.create_task(self._safe_notify(subscriber, event))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _notify_subscribers_batched(self, event_type: str, batched_event: BatchedEvent):
        """批量通知订阅者"""
        subscribers = self._subscribers.get(event_type, [])

        tasks = []
        for subscriber in subscribers:
            # 异步通知
            task = asyncio.create_task(self._safe_notify_batched(subscriber, batched_event))
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_notify(self, subscriber: Callable, event: Dict[str, Any]):
        """安全地通知订阅者(单事件)"""
        try:
            if asyncio.iscoroutinefunction(subscriber):
                await subscriber(event)
            else:
                # 在线程池中执行同步函数
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, subscriber, event)
        except Exception as e:
            logger.error(f"[事件批处理] 订阅者通知失败: {e}")

    async def _safe_notify_batched(self, subscriber: Callable, batched_event: BatchedEvent):
        """安全地通知订阅者(批量事件)"""
        try:
            if asyncio.iscoroutinefunction(subscriber):
                await subscriber(batched_event)
            else:
                # 在线程池中执行同步函数
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, subscriber, batched_event)
        except Exception as e:
            logger.error(f"[事件批处理] 订阅者通知失败: {e}")

    def subscribe(self, event_type: str, subscriber: Callable):
        """订阅事件"""
        with self._lock:
            self._subscribers[event_type].append(subscriber)
            logger.debug(f"[事件批处理] 订阅: {event_type}, 订阅者数量={len(self._subscribers[event_type])}")

    def unsubscribe(self, event_type: str, subscriber: Callable):
        """取消订阅"""
        with self._lock:
            if event_type in self._subscribers and subscriber in self._subscribers[event_type]:
                self._subscribers[event_type].remove(subscriber)
                logger.debug(f"[事件批处理] 取消订阅: {event_type}")

    async def flush_all(self):
        """刷新所有待处理的事件队列"""
        event_types = list(self._event_queues.keys())
        for event_type in event_types:
            await self._flush_event_queue(event_type)
        logger.info(f"[事件批处理] 刷新所有队列完成, 事件类型数={len(event_types)}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            queue_sizes = {event_type: len(queue) for event_type, queue in self._event_queues.items()}
            return {
                **self.stats,
                "queue_sizes": queue_sizes,
                "subscriber_counts": {event_type: len(subs) for event_type, subs in self._subscribers.items()},
            }

    def clear_stats(self):
        """清空统计信息"""
        with self._lock:
            self.stats = {
                "total_events": 0,
                "batches_processed": 0,
                "batched_events": 0,
                "direct_events": 0,
                "avg_batch_size": 0.0,
            }

    async def shutdown(self):
        """关闭批处理器"""
        # 刷新所有队列
        await self.flush_all()

        # 关闭线程池
        self._executor.shutdown(wait=True)

        logger.info("[事件批处理] 批处理器已关闭")


class AdaptiveEventBatcher(EventBatcher):
    """自适应事件批处理器"""

    def __init__(self, config: Optional[BatchConfig] = None, max_workers: int = 4):
        super().__init__(config, max_workers)

        # 自适应参数
        self._event_frequency: Dict[str, float] = {}
        self._last_event_time: Dict[str, float] = {}

    async def publish_event(self, event_type: str, event_data: Dict[str, Any]):
        """发布事件(自适应批处理)"""
        with self._lock:
            # 更新事件频率
            now = time.time()
            if event_type in self._last_event_time:
                interval = now - self._last_event_time[event_type]
                self._event_frequency[event_type] = 1.0 / interval if interval > 0 else 0.0
            self._last_event_time[event_type] = now

            # 根据频率调整批处理策略
            frequency = self._event_frequency.get(event_type, 0.0)

            # 高频事件: 批量大小更大,延迟更短
            if frequency > 10.0:  # 每秒超过10个事件
                self.config.max_batch_size = 200
                self.config.max_batch_delay = 0.5
            # 中频事件: 默认配置
            elif frequency > 1.0:  # 每秒1-10个事件
                self.config.max_batch_size = 100
                self.config.max_batch_delay = 1.0
            # 低频事件: 不批处理
            else:
                self.config.max_batch_size = 1
                self.config.max_batch_delay = 0.1

        await super().publish_event(event_type, event_data)


# 全局事件批处理器实例
_global_batcher: Optional[EventBatcher] = None


def get_global_batcher() -> EventBatcher:
    """获取全局事件批处理器实例"""
    global _global_batcher
    if _global_batcher is None:
        _global_batcher = AdaptiveEventBatcher()
    return _global_batcher


def set_global_batcher(batcher: EventBatcher):
    """设置全局事件批处理器实例"""
    global _global_batcher
    _global_batcher = batcher


# 示例使用
if __name__ == "__main__":

    async def test_event_batcher():
        # 创建批处理器
        batcher = AdaptiveEventBatcher(BatchConfig(max_batch_size=10, max_batch_delay=1.0, min_batch_size=3))

        # 添加订阅者
        async def subscriber(event):
            print(f"收到事件: {event.get('data', '')}")

        batcher.subscribe("test_event", subscriber)

        # 发布事件
        for i in range(20):
            await batcher.publish_event("test_event", {"data": f"Event {i}"})
            await asyncio.sleep(0.05)

        # 等待批处理
        await asyncio.sleep(2)

        # 打印统计
        stats = batcher.get_stats()
        print(f"统计: {stats}")

        # 关闭
        await batcher.shutdown()

    asyncio.run(test_event_batcher())
