"""
重连策略定义

支持多种重连策略，自动指数退避，防止雪崩。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("Miya.Reconnect")


class ReconnectPolicy(ABC):
    """重连策略基类"""

    @abstractmethod
    async def should_retry(self, attempt: int, error: Optional[Exception] = None) -> bool:
        """判断是否应该重试"""
        ...

    @abstractmethod
    def next_delay(self, attempt: int) -> float:
        """返回第 N 次重试的等待时间（秒）"""
        ...

    @abstractmethod
    def reset(self):
        """重置重连计数器"""
        ...


class ExponentialBackoffPolicy(ReconnectPolicy):
    """
    指数退避重连策略

    延迟公式: base_delay * (backoff_factor ^ attempt) + jitter
              上限 cap_delay
    """

    def __init__(
        self,
        max_attempts: int = 10,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        cap_delay: float = 60.0,
        jitter: float = 0.5,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.cap_delay = cap_delay
        self.jitter = jitter
        self._attempt = 0

    async def should_retry(self, attempt: int, error: Optional[Exception] = None) -> bool:
        self._attempt = attempt
        return attempt < self.max_attempts

    def next_delay(self, attempt: int) -> float:
        import random

        delay = self.base_delay * (self.backoff_factor**attempt)
        delay = min(delay, self.cap_delay)
        delay += random.uniform(0, self.jitter)
        return delay

    def reset(self):
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt


class FixedDelayPolicy(ReconnectPolicy):
    """固定延迟重连策略"""

    def __init__(self, max_attempts: int = 5, delay: float = 5.0):
        self.max_attempts = max_attempts
        self.delay = delay
        self._attempt = 0

    async def should_retry(self, attempt: int, error: Optional[Exception] = None) -> bool:
        self._attempt = attempt
        return attempt < self.max_attempts

    def next_delay(self, attempt: int) -> float:
        return self.delay

    def reset(self):
        self._attempt = 0


class NoReconnectPolicy(ReconnectPolicy):
    """不重连策略"""

    async def should_retry(self, attempt: int, error: Optional[Exception] = None) -> bool:
        return False

    def next_delay(self, attempt: int) -> float:
        return 0

    def reset(self):
        pass


async def run_reconnect_loop(
    policy: ReconnectPolicy,
    connect_fn: Callable[[], Awaitable[bool]],
    on_reconnecting: Optional[Callable[[int, float], Awaitable[None]]] = None,
    on_reconnected: Optional[Callable[[int], Awaitable[None]]] = None,
    on_give_up: Optional[Callable[[int], Awaitable[None]]] = None,
    on_error: Optional[Callable[[int, Exception], Awaitable[None]]] = None,
) -> bool:
    """
    执行重连循环

    Args:
        policy: 重连策略
        connect_fn: 连接函数 (返回 True 表示成功)
        on_reconnecting: 重连前回调 (attempt, delay)
        on_reconnected: 重连成功回调 (attempt)
        on_give_up: 放弃重连回调 (attempt)
        on_error: 重连失败回调 (attempt, error)

    Returns:
        是否重连成功
    """
    attempt = 0

    while await policy.should_retry(attempt):
        delay = policy.next_delay(attempt)
        logger.info(f"重连尝试 {attempt + 1}/{policy.max_attempts}，等待 {delay:.1f}s ...")

        if on_reconnecting:
            with contextlib.suppress(Exception):
                await on_reconnecting(attempt + 1, delay)

        await asyncio.sleep(delay)

        try:
            success = await connect_fn()
            if success:
                logger.info(f"重连成功 (尝试 {attempt + 1})")
                policy.reset()
                if on_reconnected:
                    with contextlib.suppress(Exception):
                        await on_reconnected(attempt + 1)
                return True
        except Exception as e:
            logger.warning(f"重连尝试 {attempt + 1} 失败: {e}")
            if on_error:
                with contextlib.suppress(Exception):
                    await on_error(attempt + 1, e)

        attempt += 1

    logger.error(f"重连失败，已达最大尝试次数 {policy.max_attempts}")
    policy.reset()
    if on_give_up:
        with contextlib.suppress(Exception):
            await on_give_up(attempt)
    return False
