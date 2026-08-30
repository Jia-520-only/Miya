"""
弥娅消息队列系统 - 源自Undefined的队列模型

6车道优先级队列：
- superadmin: 超级管理员私聊
- group_superadmin: 群聊超级管理员
- private: 普通私聊
- group_mention: 群聊被@
- group_normal: 群聊普通
- background: 后台请求

特点：
- 非阻塞发车（可配置节奏，默认1Hz）
- 优先级调度（严格优先级 + 轮转）
- 每个AI模型独立队列
"""

import asyncio
import contextlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

logger = logging.getLogger("Miya.MessageQueue")


# 队列车道常量
QUEUE_LANE_SUPERADMIN = "superadmin"
QUEUE_LANE_GROUP_SUPERADMIN = "group_superadmin"
QUEUE_LANE_PRIVATE = "private"
QUEUE_LANE_GROUP_MENTION = "group_mention"
QUEUE_LANE_GROUP_NORMAL = "group_normal"
QUEUE_LANE_BACKGROUND = "background"

STRICT_PRIORITY_LANES = (
    QUEUE_LANE_SUPERADMIN,
    QUEUE_LANE_GROUP_SUPERADMIN,
)
ROTATING_QUEUE_LANES = (
    QUEUE_LANE_PRIVATE,
    QUEUE_LANE_GROUP_MENTION,
    QUEUE_LANE_GROUP_NORMAL,
)
ALL_QUEUE_LANES = (
    *STRICT_PRIORITY_LANES,
    *ROTATING_QUEUE_LANES,
    QUEUE_LANE_BACKGROUND,
)

QUEUE_LANE_DISPLAY_NAMES = {
    QUEUE_LANE_SUPERADMIN: "超级管理员私聊",
    QUEUE_LANE_GROUP_SUPERADMIN: "群聊超级管理员",
    QUEUE_LANE_PRIVATE: "普通私聊",
    QUEUE_LANE_GROUP_MENTION: "群聊被@",
    QUEUE_LANE_GROUP_NORMAL: "群聊普通",
    QUEUE_LANE_BACKGROUND: "后台请求",
}


@dataclass
class LaneQueue:
    """支持尾插与"插入第2位"的轻量队列"""

    _items: deque = field(default_factory=deque)

    def qsize(self) -> int:
        return len(self._items)

    def empty(self) -> bool:
        return not self._items

    async def put(self, item: dict) -> None:
        self.put_nowait(item)

    def put_nowait(self, item: dict) -> None:
        self._items.append(item)

    async def put_second(self, item: dict) -> None:
        self.put_second_nowait(item)

    def put_second_nowait(self, item: dict) -> None:
        if len(self._items) <= 1:
            self._items.append(item)
            return
        items = list(self._items)
        items.insert(1, item)
        self._items = deque(items)

    async def get(self) -> dict:
        return self.get_nowait()

    def get_nowait(self) -> dict:
        return self._items.popleft()

    def drain(self) -> list:
        items = list(self._items)
        self._items.clear()
        return items

    def retry_count(self) -> int:
        return sum(1 for item in self._items if int(item.get("_retry_count", 0) or 0) > 0)


@dataclass
class ModelQueue:
    """单个模型的优先队列组"""

    model_name: str
    superadmin_queue: LaneQueue = field(default_factory=LaneQueue)
    group_superadmin_queue: LaneQueue = field(default_factory=LaneQueue)
    private_queue: LaneQueue = field(default_factory=LaneQueue)
    group_mention_queue: LaneQueue = field(default_factory=LaneQueue)
    group_normal_queue: LaneQueue = field(default_factory=LaneQueue)
    background_queue: LaneQueue = field(default_factory=LaneQueue)

    def lane_queues(self) -> Dict[str, LaneQueue]:
        return {
            QUEUE_LANE_SUPERADMIN: self.superadmin_queue,
            QUEUE_LANE_GROUP_SUPERADMIN: self.group_superadmin_queue,
            QUEUE_LANE_PRIVATE: self.private_queue,
            QUEUE_LANE_GROUP_MENTION: self.group_mention_queue,
            QUEUE_LANE_GROUP_NORMAL: self.group_normal_queue,
            QUEUE_LANE_BACKGROUND: self.background_queue,
        }

    def total_retry_count(self) -> int:
        return sum(queue.retry_count() for queue in self.lane_queues().values())


@dataclass
class QueueReceipt:
    """入队回执"""

    model_name: str
    lane: str
    size: int
    estimated_wait_seconds: float


class MessageQueueManager:
    """弥娅消息队列管理器 - 源自Undefined的队列模型"""

    _instance = None

    @classmethod
    def get_instance(cls, default_interval: float = 1.0) -> "MessageQueueManager":
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls(default_interval)
        return cls._instance

    def __init__(self, default_interval: float = 1.0):
        self._default_interval = max(0.1, default_interval)
        self._model_intervals: Dict[str, float] = {}
        self._model_queues: Dict[str, ModelQueue] = {}
        self._processor_tasks: Dict[str, asyncio.Task] = {}
        self._inflight_tasks: set = set()
        self._next_dispatch_at: Dict[str, float] = {}
        self._request_handler: Optional[Callable] = None

    def update_model_intervals(self, model_intervals: Dict[str, float]) -> None:
        """更新模型发车节奏"""
        normalized = {}
        for name, interval in model_intervals.items():
            if isinstance(name, str) and name.strip():
                normalized[name.strip()] = max(0.1, float(interval))
        self._model_intervals = normalized
        logger.info(f"[消息队列] 已更新模型发车节奏: count={len(self._model_intervals)}")

    def get_interval(self, model_name: str) -> float:
        """获取模型发车节奏"""
        return self._model_intervals.get(model_name, self._default_interval)

    def start(self, request_handler: Callable) -> None:
        """启动队列处理"""
        self._request_handler = request_handler
        logger.info(f"[消息队列] 队列管理器已就绪: interval={self._default_interval}s")

    async def stop(self) -> None:
        """停止所有队列"""
        logger.info(f"[消息队列] 正在停止: processors={len(self._processor_tasks)}")

        for task in self._processor_tasks.values():
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._processor_tasks.clear()
        self._next_dispatch_at.clear()

        for task in list(self._inflight_tasks):
            if not task.done():
                task.cancel()
        self._inflight_tasks.clear()

        logger.info("[消息队列] 已停止")

    def _track_inflight(self, task: asyncio.Task) -> None:
        self._inflight_tasks.add(task)
        task.add_done_callback(self._inflight_tasks.discard)

    def _get_or_create_queue(self, model_name: str) -> ModelQueue:
        """获取或创建模型队列"""
        if model_name not in self._model_queues:
            self._model_queues[model_name] = ModelQueue(model_name=model_name)
            if self._request_handler:
                task = asyncio.create_task(self._process_model_loop(model_name))
                self._processor_tasks[model_name] = task
                logger.info(f"[消息队列] 已启动模型处理: model={model_name}")
        return self._model_queues[model_name]

    def _get_lane_queue(self, model_queue: ModelQueue, lane: str) -> LaneQueue:
        lane_queue = model_queue.lane_queues().get(lane)
        if lane_queue is not None:
            return lane_queue
        return model_queue.background_queue

    def _format_meta(self, request: dict) -> str:
        parts = []
        if request.get("request_id"):
            parts.append(f"id={request.get('request_id')}")
        if request.get("group_id"):
            parts.append(f"group={request.get('group_id')}")
        if request.get("user_id"):
            parts.append(f"user={request.get('user_id')}")
        return " ".join(parts) or "meta=none"

    def estimate_wait(self, model_name: str, lane: str) -> float:
        model_queue = self._model_queues.get(model_name)
        if model_queue is None:
            return 0.0
        now = time.perf_counter()
        base = max(0.0, self._next_dispatch_at.get(model_name, now) - now)
        total = sum(q.qsize() for q in model_queue.lane_queues().values())
        ahead = max(0, total - 1)
        return base + (self.get_interval(model_name) * ahead)

    async def _enqueue(
        self,
        request: dict,
        model_name: str,
        lane: str,
        display_name: str,
        insert_second: bool = False,
    ) -> QueueReceipt:
        queue = self._get_or_create_queue(model_name)
        request["_queue_lane"] = lane
        lane_queue = self._get_lane_queue(queue, lane)

        if insert_second:
            await lane_queue.put_second(request)
        else:
            await lane_queue.put(request)

        logger.info(f"[入队][{model_name}] {display_name}: size={lane_queue.qsize()} {self._format_meta(request)}")

        return QueueReceipt(
            model_name=model_name,
            lane=lane,
            size=lane_queue.qsize(),
            estimated_wait_seconds=self.estimate_wait(model_name, lane),
        )

    async def add_superadmin(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_SUPERADMIN, "超级管理员私聊")

    async def add_group_superadmin(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_GROUP_SUPERADMIN, "群聊超级管理员")

    async def add_private(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_PRIVATE, "普通私聊")

    async def add_group_mention(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_GROUP_MENTION, "群聊被@")

    async def add_group_normal(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_GROUP_NORMAL, "群聊普通")

    async def add_background(self, request: dict, model_name: str = "default") -> QueueReceipt:
        return await self._enqueue(request, model_name, QUEUE_LANE_BACKGROUND, "后台请求")

    async def _process_model_loop(self, model_name: str) -> None:
        """模型处理循环（非阻塞发车）"""
        model_queue = self._model_queues[model_name]
        lane_queues = model_queue.lane_queues()
        rotating_queues = [lane_queues[lane] for lane in ROTATING_QUEUE_LANES]
        rotating_names = [QUEUE_LANE_DISPLAY_NAMES[lane] for lane in ROTATING_QUEUE_LANES]

        current_idx = 0
        processed_count = 0

        try:
            while True:
                cycle_start = time.perf_counter()
                interval = self.get_interval(model_name)
                self._next_dispatch_at[model_name] = cycle_start + interval

                request = None
                dispatch_name = ""

                # 严格优先级
                for lane in STRICT_PRIORITY_LANES:
                    queue = lane_queues[lane]
                    if not queue.empty():
                        request = queue.get_nowait()
                        dispatch_name = QUEUE_LANE_DISPLAY_NAMES[lane]
                        break

                # 轮转队列
                if request is None:
                    start = current_idx
                    for i in range(len(rotating_queues)):
                        idx = (start + i) % len(rotating_queues)
                        queue = rotating_queues[idx]
                        if not queue.empty():
                            request = queue.get_nowait()
                            dispatch_name = rotating_names[idx]
                            processed_count += 1
                            if processed_count >= 2:
                                current_idx = (current_idx + 1) % len(rotating_queues)
                                processed_count = 0
                            break

                # 后台队列
                if request is None and not model_queue.background_queue.empty():
                    request = model_queue.background_queue.get_nowait()
                    dispatch_name = QUEUE_LANE_DISPLAY_NAMES[QUEUE_LANE_BACKGROUND]

                if request and self._request_handler:
                    logger.info(f"[发车][{model_name}] {dispatch_name}: {self._format_meta(request)}")
                    task = asyncio.create_task(self._safe_handle(request, model_name, dispatch_name))
                    self._track_inflight(task)

                elapsed = time.perf_counter() - cycle_start
                await asyncio.sleep(max(0.0, interval - elapsed))

        except asyncio.CancelledError:
            logger.info(f"[消息队列] 处理循环已取消: {model_name}")
        except Exception as e:
            logger.exception(f"[消息队列] 处理循环异常: {model_name} - {e}")

    async def _safe_handle(self, request: dict, model_name: str, queue_name: str) -> None:
        """安全执行请求"""
        start = time.perf_counter()
        try:
            if self._request_handler:
                await self._request_handler(request)
            elapsed = time.perf_counter() - start
            logger.info(f"[完成][{model_name}] {queue_name}: {elapsed:.2f}s {self._format_meta(request)}")
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"[失败][{model_name}] {queue_name}: {elapsed:.2f}s {self._format_meta(request)} - {e}")

    def snapshot(self) -> dict:
        """队列状态快照"""
        models = {}
        totals = {"retry": 0, **{lane: 0 for lane in ALL_QUEUE_LANES}}

        for name, queue in self._model_queues.items():
            snap = {
                "retry": queue.total_retry_count(),
                **{lane: q.qsize() for lane, q in queue.lane_queues().items()},
            }
            models[name] = snap
            for k, v in snap.items():
                totals[k] += v

        return {
            "interval": self._default_interval,
            "processors": len(self._processor_tasks),
            "inflight": len(self._inflight_tasks),
            "models": models,
            "totals": totals,
        }


# 全局单例
_message_queue = None


def get_message_queue() -> MessageQueueManager:
    """获取消息队列管理器"""
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueueManager.get_instance()
    return _message_queue
