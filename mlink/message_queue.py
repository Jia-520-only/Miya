"""
M-Link 消息队列
优化 M-Link 消息处理性能
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import heapq

from .message import Message, MessageType


logger = logging.getLogger(__name__)


@dataclass(order=True)
class PriorityQueueItem:
    """优先队列项"""
    priority: int  # 优先级（数字越小优先级越高）
    timestamp: float
    message: Message = field(compare=False)


class MessageQueue:
    """
    M-Link 消息队列

    功能：
    - 消息优先级队列
    - 消息去重
    - 消息超时处理
    - 批量处理优化
    - 流量控制
    """

    def __init__(
        self,
        max_size: int = 1000,
        enable_dedup: bool = True,
        batch_size: int = 10,
        batch_timeout: float = 0.1
    ):
        """
        初始化消息队列

        Args:
            max_size: 队列最大容量
            enable_dedup: 是否启用去重
            batch_size: 批量处理大小
            batch_timeout: 批量处理超时（秒）
        """
        self.max_size = max_size
        self.enable_dedup = enable_dedup
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout

        # 优先队列
        self._priority_queue: List[PriorityQueueItem] = []
        self._queue_lock = asyncio.Lock()

        # 消息去重（使用message_id）
        self._dedup_cache: set = set()

        # 统计信息
        self._stats = {
            'total_enqueued': 0,
            'total_dequeued': 0,
            'total_dropped': 0,
            'total_dedup': 0,
            'current_size': 0
        }

        # 处理器
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False

    async def enqueue(self, message: Message) -> bool:
        """
        入队

        Args:
            message: 消息对象

        Returns:
            是否入队成功
        """
        async with self._queue_lock:
            # 检查队列是否已满
            if len(self._priority_queue) >= self.max_size:
                logger.warning(f"[MessageQueue] 队列已满，丢弃消息: {message.message_id}")
                self._stats['total_dropped'] += 1
                return False

            # 去重检查
            if self.enable_dedup and message.message_id in self._dedup_cache:
                logger.debug(f"[MessageQueue] 消息重复，忽略: {message.message_id}")
                self._stats['total_dedup'] += 1
                return False

            # 创建优先队列项
            priority = message.priority if hasattr(message, 'priority') else 0
            item = PriorityQueueItem(
                priority=priority,
                timestamp=datetime.now().timestamp(),
                message=message
            )

            # 入队
            heapq.heappush(self._priority_queue, item)

            # 更新去重缓存
            if self.enable_dedup:
                self._dedup_cache.add(message.message_id)
                # 限制缓存大小
                if len(self._dedup_cache) > self.max_size * 2:
                    self._dedup_cache.clear()

            # 更新统计
            self._stats['total_enqueued'] += 1
            self._stats['current_size'] = len(self._priority_queue)

            logger.debug(f"[MessageQueue] 消息入队: {message.message_id}, 队列大小: {self._stats['current_size']}")
            return True

    async def dequeue(self) -> Optional[Message]:
        """
        出队（单条）

        Returns:
            消息对象，队列为空时返回 None
        """
        async with self._queue_lock:
            if not self._priority_queue:
                return None

            item = heapq.heappop(self._priority_queue)
            self._stats['total_dequeued'] += 1
            self._stats['current_size'] = len(self._priority_queue)

            # 从去重缓存中移除
            if self.enable_dedup and item.message.message_id in self._dedup_cache:
                self._dedup_cache.remove(item.message.message_id)

            logger.debug(f"[MessageQueue] 消息出队: {item.message.message_id}, 队列大小: {self._stats['current_size']}")
            return item.message

    async def dequeue_batch(self) -> List[Message]:
        """
        批量出队

        Returns:
            消息列表
        """
        messages = []
        timeout_at = datetime.now().timestamp() + self.batch_timeout

        async with self._queue_lock:
            while len(self._priority_queue) > 0 and len(messages) < self.batch_size:
                # 检查超时
                if datetime.now().timestamp() >= timeout_at and len(messages) > 0:
                    break

                item = heapq.heappop(self._priority_queue)
                messages.append(item.message)

                # 从去重缓存中移除
                if self.enable_dedup and item.message.message_id in self._dedup_cache:
                    self._dedup_cache.remove(item.message.message_id)

            self._stats['total_dequeued'] += len(messages)
            self._stats['current_size'] = len(self._priority_queue)

        logger.debug(f"[MessageQueue] 批量出队: {len(messages)} 条消息")
        return messages

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        return {
            **self._stats,
            'max_size': self.max_size,
            'enable_dedup': self.enable_dedup,
            'batch_size': self.batch_size
        }

    def clear(self) -> None:
        """清空队列"""
        self._priority_queue.clear()
        self._dedup_cache.clear()
        logger.info("[MessageQueue] 队列已清空")

    async def start_processor(
        self,
        handler: Callable[[Message], Any],
        use_batch: bool = True
    ) -> None:
        """
        启动消息处理器

        Args:
            handler: 消息处理函数
            use_batch: 是否使用批量处理
        """
        if self._running:
            logger.warning("[MessageQueue] 处理器已在运行")
            return

        self._running = True

        if use_batch:
            self._processor_task = asyncio.create_task(self._batch_processor(handler))
        else:
            self._processor_task = asyncio.create_task(self._single_processor(handler))

        logger.info(f"[MessageQueue] 处理器已启动 (批量模式: {use_batch})")

    async def stop_processor(self) -> None:
        """停止消息处理器"""
        if not self._running:
            return

        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        logger.info("[MessageQueue] 处理器已停止")

    async def _single_processor(self, handler: Callable) -> None:
        """单条消息处理器"""
        while self._running:
            try:
                message = await self.dequeue()
                if message is None:
                    await asyncio.sleep(0.01)
                    continue

                # 处理消息
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MessageQueue] 处理消息失败: {e}", exc_info=True)

    async def _batch_processor(self, handler: Callable) -> None:
        """批量消息处理器"""
        while self._running:
            try:
                # 批量出队
                messages = await self.dequeue_batch()
                if not messages:
                    await asyncio.sleep(0.01)
                    continue

                # 批量处理
                if asyncio.iscoroutinefunction(handler):
                    await handler(messages)
                else:
                    handler(messages)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MessageQueue] 批量处理失败: {e}", exc_info=True)
