"""
MIYA Event 事件系统

异步事件总线，支持消息、命令、定时任务等事件
"""

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型"""

    MESSAGE = "message"
    PRIVATE_MESSAGE = "private_message"
    GROUP_MESSAGE = "group_message"
    COMMAND = "command"
    TIMER = "timer"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    PLATFORM_CONNECT = "platform_connect"
    PLATFORM_DISCONNECT = "platform_disconnect"
    TOOL_EXECUTE = "tool_execute"
    ERROR = "error"


@dataclass
class Event:
    """事件"""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = 0

    def __post_init__(self):
        if self.timestamp == 0:
            import time

            self.timestamp = time.time()


class EventHandler(ABC):
    """事件处理器基类"""

    @abstractmethod
    async def handle(self, event: Event):
        """处理事件"""
        pass


class EventBus:
    """
    MIYA 事件总线

    负责事件的注册、分发和处理
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

        self._handlers: Dict[EventType, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._initialized = True

        logger.info("[EventBus] 初始化完成")

    def register_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"[EventBus] 注册处理器: {event_type}")

    def unregister_handler(self, event_type: EventType, handler: Callable):
        """注销事件处理器"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event):
        """发布事件"""
        await self._event_queue.put(event)

    async def dispatch(self, event: Event):
        """分发事件"""
        handlers = self._handlers.get(event.type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[EventBus] 事件处理失败: {e}")

    async def _dispatcher_loop(self):
        """事件分发循环"""
        logger.info("[EventBus] 事件分发器启动")

        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self.dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[EventBus] 事件处理异常: {e}")

    async def start(self):
        """启动事件总线"""
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())
        logger.info("[EventBus] 事件总线已启动")

    async def stop(self):
        """停止事件总线"""
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dispatcher_task
        logger.info("[EventBus] 事件总线已停止")

    def list_handlers(self) -> Dict[EventType, int]:
        """列出已注册的事件处理器"""
        return {event_type: len(handlers) for event_type, handlers in self._handlers.items()}


# ==================== 消息事件处理器 ====================


class MessageEventHandler(EventHandler):
    """消息事件处理器"""

    def __init__(self, message_handler: Callable):
        self.message_handler = message_handler

    async def handle(self, event: Event):
        await self.message_handler(event.data)


class CommandEventHandler(EventHandler):
    """命令事件处理器"""

    def __init__(self, command_handler: Callable):
        self.command_handler = command_handler

    async def handle(self, event: Event):
        await self.command_handler(event.data)


class TimerEventHandler(EventHandler):
    """定时任务处理器"""

    def __init__(self, timer_handler: Callable, interval: float):
        self.timer_handler = timer_handler
        self.interval = interval

    async def handle(self, event: Event):
        if event.type == EventType.TIMER:
            await self.timer_handler()


# ==================== Cron 定时任务 ====================


class CronJob:
    """定时任务"""

    def __init__(self, job_id: str, name: str, cron_expression: str, handler: Callable):
        self.job_id = job_id
        self.name = name
        self.cron_expression = cron_expression
        self.handler = handler
        self.enabled = True

    async def execute(self):
        """执行任务"""
        try:
            if asyncio.iscoroutinefunction(self.handler):
                await self.handler()
            else:
                self.handler()
            logger.info(f"[CronJob] 执行任务: {self.name}")
        except Exception as e:
            logger.error(f"[CronJob] 任务执行失败: {e}")


class CronManager:
    """定时任务管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._jobs: Dict[str, CronJob] = {}
        self._timers: List[asyncio.Task] = []
        self._initialized = True

        logger.info("[CronManager] 初始化完成")

    def register_job(self, job: CronJob):
        """注册定时任务"""
        self._jobs[job.job_id] = job
        logger.info(f"[CronManager] 注册定时任务: {job.name}")

    async def start_job(self, job_id: str):
        """启动定时任务"""
        job = self._jobs.get(job_id)
        if not job or not job.enabled:
            return

        # ��单定时器（简化版：每 N 秒执行一次）
        interval = self._parse_cron_to_seconds(job.cron_expression)

        async def run():
            while job.enabled:
                await asyncio.sleep(interval)
                await job.execute()

        task = asyncio.create_task(run())
        self._timers.append(task)
        logger.info(f"[CronManager] 启动定时任务: {job.name}")

    def _parse_cron_to_seconds(self, cron: str) -> float:
        """简化 Cron 解析"""
        # 简化版：支持简单的时间格式
        # 比如 "60s" = 60秒, "1m" = 60秒, "1h" = 3600秒

        if cron.endswith("s"):
            return float(cron[:-1])
        elif cron.endswith("m"):
            return float(cron[:-1]) * 60
        elif cron.endswith("h"):
            return float(cron[:-1]) * 3600
        elif cron.endswith("d"):
            return float(cron[:-1]) * 86400

        return 60  # 默认 60 秒

    async def stop_all(self):
        """停止所有定时任务"""
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        logger.info("[CronManager] 已停止所有定时任务")


# ==================== Pipeline 消息处理管道 ====================


class Pipeline:
    """消息处理管道"""

    def __init__(self, name: str):
        self.name = name
        self.steps: List[Callable] = []

    def add_step(self, step: Callable):
        """添加处理步骤"""
        self.steps.append(step)

    async def execute(self, context: Dict) -> Dict:
        """执行管道"""
        result = context

        for step in self.steps:
            try:
                result = await step(result) or result if asyncio.iscoroutinefunction(step) else step(result) or result
            except Exception as e:
                logger.error(f"[Pipeline] 步骤执行失败: {e}")

        return result


class PipelineScheduler:
    """管道调度器"""

    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}

    def register_pipeline(self, pipeline_id: str, pipeline: Pipeline):
        self._pipelines[pipeline_id] = pipeline

    async def execute(self, pipeline_id: str, context: Dict) -> Dict:
        pipeline = self._pipelines.get(pipeline_id)
        if pipeline:
            return await pipeline.execute(context)
        return context


# 全局实例
_event_bus = None
_cron_manager = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_cron_manager() -> CronManager:
    global _cron_manager
    if _cron_manager is None:
        _cron_manager = CronManager()
    return _cron_manager


__all__ = [
    "Event",
    "EventType",
    "EventHandler",
    "EventBus",
    "CronJob",
    "CronManager",
    "Pipeline",
    "PipelineScheduler",
    "get_event_bus",
    "get_cron_manager",
]
