"""弥娅队列管理器 - 整合Undefined的车站-列车模型

该模块整合Undefined的队列系统，采用"车站-列车"模型：
1. 每个模型有独立的队列组（车站）
2. 每个模型按配置节奏发车（列车），带走一个请求
3. 请求处理是异步不阻塞的（不管前一个是否结束）

设计理念：符合弥娅的分层架构，属于hub/scheduler层的增强
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelQueue:
    """单个模型的优先队列组
    
    符合弥娅的蛛网式分布式架构，提供多级优先级队列
    """
    model_name: str
    retry_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)
    superadmin_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)
    private_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)
    group_mention_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)
    group_normal_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)
    background_queue: asyncio.Queue[Dict[str, Any]] = field(default_factory=asyncio.Queue)

    def trim_normal_queue(self) -> None:
        """如果群聊普通队列超过阈值，仅保留最新的几个
        
        防止普通群聊消息淹没系统资源
        """
        queue_size = self.group_normal_queue.qsize()
        if queue_size > 10:
            logger.warning(
                "[队列修剪][%s] 群聊普通队列长度=%s 超过阈值(10)，将丢弃旧请求",
                self.model_name,
                queue_size,
            )
            all_requests: List[Dict[str, Any]] = []
            while not self.group_normal_queue.empty():
                all_requests.append(self.group_normal_queue.get_nowait())
            latest_requests = all_requests[-2:]
            for req in latest_requests:
                self.group_normal_queue.put_nowait(req)
            logger.info(
                "[队列修剪][%s] 修剪完成，保留最新=%s",
                self.model_name,
                len(latest_requests),
            )


@dataclass
class QueueStats:
    """队列统计信息"""
    total_requests: int = 0
    processed_requests: int = 0
    failed_requests: int = 0
    avg_wait_time: float = 0.0
    total_wait_time: float = 0.0


class QueueManager:
    """队列管理器 - 车站-列车模型
    
    职责：
    - 管理多模型队列
    - 按优先级调度请求
    - 限流和队列修剪
    
    架构定位：属于hub/scheduler层，增强任务调度能力
    """

    def __init__(
        self,
        ai_request_interval: float = 1.0,
        model_intervals: Dict[str, float] = None,
        max_retries: int = 2,
    ) -> None:
        if ai_request_interval <= 0:
            ai_request_interval = 1.0
        self.ai_request_interval = ai_request_interval
        self._default_interval = ai_request_interval
        self._max_retries = max(0, max_retries)
        self._model_intervals: Dict[str, float] = {}
        if model_intervals:
            self.update_model_intervals(model_intervals)

        # 按模型名称区分的队列组（车站）
        self._model_queues: Dict[str, ModelQueue] = {}

        # 处理任务映射：模型名 -> Task（列车调度器）
        self._processor_tasks: Dict[str, asyncio.Task[None]] = {}

        # 在途请求任务（发车后异步执行）
        self._inflight_tasks: set[asyncio.Task[None]] = set()

        self._request_handler: Optional[
            Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
        ] = None

        # 统计信息
        self._stats: Dict[str, QueueStats] = {}

    def update_model_intervals(self, model_intervals: Dict[str, float]) -> None:
        """更新模型队列发车节奏映射"""
        normalized: Dict[str, float] = {}
        for model_name, interval in model_intervals.items():
            if not isinstance(model_name, str):
                continue
            normalized[model_name] = max(0.1, float(interval))
        self._model_intervals = normalized

    def get_model_queue(self, model_name: str) -> ModelQueue:
        """获取或创建模型队列"""
        if model_name not in self._model_queues:
            self._model_queues[model_name] = ModelQueue(model_name=model_name)
            self._stats[model_name] = QueueStats()
        return self._model_queues[model_name]

    async def enqueue(
        self,
        model_name: str,
        request: Dict[str, Any],
        priority: str = "normal",
        max_retries: Optional[int] = None,
    ) -> bool:
        """入队请求
        
        Args:
            model_name: 模型名称
            request: 请求数据
            priority: 优先级 (superadmin/private/group_mention/group_normal/background/retry)
            max_retries: 最大重试次数
        
        Returns:
            是否入队成功
        """
        queue = self.get_model_queue(model_name)
        request["_enqueue_time"] = time.time()
        request["_max_retries"] = max_retries or self._max_retries
        request["_current_retries"] = 0

        try:
            if priority == "superadmin":
                queue.superadmin_queue.put_nowait(request)
            elif priority == "private":
                queue.private_queue.put_nowait(request)
            elif priority == "group_mention":
                queue.group_mention_queue.put_nowait(request)
            elif priority == "group_normal":
                queue.group_normal_queue.put_nowait(request)
                queue.trim_normal_queue()
            elif priority == "background":
                queue.background_queue.put_nowait(request)
            elif priority == "retry":
                queue.retry_queue.put_nowait(request)
            else:
                queue.group_normal_queue.put_nowait(request)
                queue.trim_normal_queue()

            self._stats[model_name].total_requests += 1
            logger.debug(
                "[入队][%s] 优先级=%s 总请求数=%s",
                model_name,
                priority,
                self._stats[model_name].total_requests,
            )
            return True
        except Exception as e:
            logger.error(
                "[入队失败][%s] priority=%s error=%s",
                model_name,
                priority,
                e,
                exc_info=True,
            )
            return False

    def set_request_handler(
        self, handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        """设置请求处理器"""
        self._request_handler = handler

    async def _dequeue_request(self, model_name: str) -> Optional[Dict[str, Any]]:
        """从队列中取出一个请求（按优先级）"""
        queue = self._model_queues.get(model_name)
        if not queue:
            return None

        # 按优先级顺序尝试出队
        priority_order = [
            queue.retry_queue,
            queue.superadmin_queue,
            queue.private_queue,
            queue.group_mention_queue,
            queue.group_normal_queue,
            queue.background_queue,
        ]

        for q in priority_order:
            if not q.empty():
                request = q.get_nowait()
                wait_time = time.time() - request.get("_enqueue_time", time.time())
                
                # 更新统计
                stats = self._stats.get(model_name, QueueStats())
                stats.total_wait_time += wait_time
                stats.avg_wait_time = stats.total_wait_time / stats.processed_requests if stats.processed_requests > 0 else wait_time
                
                return request
        
        return None

    async def _process_requests(self, model_name: str) -> None:
        """处理指定模型的所有请求
        
        这是"列车调度器"，按配置节奏发车（处理请求）
        """
        interval = self._model_intervals.get(model_name, self._default_interval)
        logger.info(
            "[列车调度器启动][%s] 发车间隔=%.1fs", model_name, interval
        )

        while True:
            try:
                await asyncio.sleep(interval)

                request = await self._dequeue_request(model_name)
                if not request:
                    continue

                if self._request_handler:
                    # 异步执行，不阻塞后续发车
                    task = asyncio.create_task(self._handle_request(model_name, request))
                    self._inflight_tasks.add(task)
                    task.add_done_callback(self._inflight_tasks.discard)

            except asyncio.CancelledError:
                logger.info("[列车调度器停止][%s]", model_name)
                break
            except Exception as e:
                logger.error(
                    "[列车调度器异常][%s] error=%s",
                    model_name,
                    e,
                    exc_info=True,
                )

    async def _handle_request(self, model_name: str, request: Dict[str, Any]) -> None:
        """处理单个请求"""
        try:
            if self._request_handler:
                await self._request_handler(request)
                
                stats = self._stats.get(model_name, QueueStats())
                stats.processed_requests += 1
                
        except Exception as e:
            logger.error(
                "[请求处理异常][%s] error=%s",
                model_name,
                e,
                exc_info=True,
            )
            
            stats = self._stats.get(model_name, QueueStats())
            stats.failed_requests += 1
            
            # 重试逻辑
            current_retries = request.get("_current_retries", 0)
            max_retries = request.get("_max_retries", self._max_retries)
            
            if current_retries < max_retries:
                request["_current_retries"] = current_retries + 1
                await self.enqueue(model_name, request, priority="retry")
                logger.debug(
                    "[请求重试][%s] current=%s max=%s",
                    model_name,
                    current_retries + 1,
                    max_retries,
                )

    async def start(self, model_names: List[str]) -> None:
        """启动队列管理器
        
        为每个模型启动一个列车调度器
        """
        logger.info("[队列管理器启动] 模型数=%s", len(model_names))
        
        for model_name in model_names:
            if model_name not in self._processor_tasks:
                task = asyncio.create_task(self._process_requests(model_name))
                self._processor_tasks[model_name] = task
                logger.info("[队列启动][%s]", model_name)

    async def stop(self) -> None:
        """停止队列管理器"""
        logger.info("[队列管理器停止] 开始优雅停机...")
        
        # 停止所有列车调度器
        for model_name, task in self._processor_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 等待所有在途任务完成
        if self._inflight_tasks:
            logger.info("[队列管理器停止] 等待在途任务... 等待数=%s", len(self._inflight_tasks))
            await asyncio.gather(*self._inflight_tasks, return_exceptions=True)
        
        self._processor_tasks.clear()
        self._inflight_tasks.clear()
        logger.info("[队列管理器停止] 已停止")

    def get_queue_status(self, model_name: str) -> Dict[str, int]:
        """获取队列状态"""
        queue = self._model_queues.get(model_name)
        if not queue:
            return {}
        
        return {
            "retry": queue.retry_queue.qsize(),
            "superadmin": queue.superadmin_queue.qsize(),
            "private": queue.private_queue.qsize(),
            "group_mention": queue.group_mention_queue.qsize(),
            "group_normal": queue.group_normal_queue.qsize(),
            "background": queue.background_queue.qsize(),
        }

    def get_stats(self, model_name: str) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.get(model_name)
        if not stats:
            return {}
        
        return {
            "total_requests": stats.total_requests,
            "processed_requests": stats.processed_requests,
            "failed_requests": stats.failed_requests,
            "success_rate": (
                stats.processed_requests / stats.total_requests * 100
                if stats.total_requests > 0
                else 0
            ),
            "avg_wait_time": stats.avg_wait_time,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型的统计信息"""
        return {
            model_name: self.get_stats(model_name)
            for model_name in self._model_queues.keys()
        }
