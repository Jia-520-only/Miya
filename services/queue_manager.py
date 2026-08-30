"""Legacy station-train queue manager used by tests.

This module keeps the old ``QueueManager`` / ``QueueRequest`` API while the
production path is being migrated to ``core.message_queue.MessageQueueManager``.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("Miya.LegacyQueue")


@dataclass
class QueueRequest:
    request_id: str
    priority: int = 1
    payload: dict = field(default_factory=dict)
    model_name: str = "default"
    max_retries: int = 0
    retry_count: int = field(default=0, repr=False)


@dataclass(order=True)
class _PrioritizedItem:
    priority: int
    sequence: int
    request: QueueRequest = field(compare=False)


class _ModelQueue:
    def __init__(self, interval: float) -> None:
        self.interval = max(0.01, float(interval))
        self._heap: list[_PrioritizedItem] = []
        self._sequence = 0

    def push(self, request: QueueRequest) -> None:
        heapq.heappush(self._heap, _PrioritizedItem(request.priority, self._sequence, request))
        self._sequence += 1

    def pop(self) -> Optional[QueueRequest]:
        if not self._heap:
            return None
        return heapq.heappop(self._heap).request

    def qsize(self) -> int:
        return len(self._heap)


class QueueManager:
    def __init__(self, models: dict[str, float], default_interval: float = 0.1) -> None:
        self._default_interval = max(0.01, float(default_interval))
        self._model_queues: dict[str, _ModelQueue] = {
            str(name): _ModelQueue(float(interval)) for name, interval in models.items()
        }
        self._handler: Optional[Callable[[QueueRequest], Awaitable[None]]] = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._started = False

    def set_handler(self, handler: Callable[[QueueRequest], Awaitable[None]]) -> None:
        self._handler = handler

    def enqueue(self, request: QueueRequest) -> None:
        queue = self._model_queues.get(request.model_name)
        if queue is None:
            queue = _ModelQueue(self._default_interval)
            self._model_queues[request.model_name] = queue
        queue.push(request)

    def pending_count(self) -> int:
        return sum(queue.qsize() for queue in self._model_queues.values())

    def estimate_wait(self, model_name: str) -> float:
        queue = self._model_queues.get(model_name)
        if queue is None:
            return 0.0
        return queue.interval * max(0, queue.qsize() - 1)

    def update_model_intervals(self, model_intervals: dict[str, float]) -> None:
        for name, interval in model_intervals.items():
            name = str(name)
            if name in self._model_queues:
                self._model_queues[name].interval = max(0.01, float(interval))
            else:
                self._model_queues[name] = _ModelQueue(float(interval))

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for name, queue in self._model_queues.items():
            self._tasks[name] = asyncio.create_task(self._run_model_queue(name, queue))

    async def stop(self) -> None:
        self._started = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def _run_model_queue(self, model_name: str, queue: _ModelQueue) -> None:
        while True:
            request = queue.pop()
            if request is None:
                await asyncio.sleep(queue.interval)
                continue

            if self._handler is None:
                await asyncio.sleep(queue.interval)
                continue

            try:
                await self._handler(request)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[LegacyQueue] request failed: id=%s error=%s", request.request_id, exc)
                if request.retry_count < request.max_retries:
                    request.retry_count += 1
                    queue.push(request)

            await asyncio.sleep(queue.interval)
