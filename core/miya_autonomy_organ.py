"""
弥娅自主进化器官 (MiyaAutonomyOrgan)

将 AutonomyManager / AutonomousEngine 挂载到 MiyaSpine 脊柱上。
弥娅在安静时可以自主进行代码优化、自我改进和学习。

v8.0 脊柱神经架构的一部分。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from core.miya_organ import MiyaOrgan

if TYPE_CHECKING:
    from core.miya_soul_state import MiyaSoulState, LifecyclePhase

logger = logging.getLogger("Miya.AutonomyOrgan")


class MiyaAutonomyOrgan(MiyaOrgan):
    """
    自主进化器官。

    功能：
    - 在弥娅 IDLE/DROWSY 阶段，定期检查是否需要进行自主改进
    - 通过脊柱感知弥娅的认知负荷，在低负荷时触发学习
    - 记录改进历史

    注意：此器官依赖于 AutonomyManager 已初始化。
    如果 AutonomyManager 不可用（如未在 daemon 中集成），
    此器官处于休眠状态。
    """

    def __init__(self):
        super().__init__(name="autonomy_organ", priority=50)
        self._last_check_time: float = 0.0
        self._check_interval: float = 300.0  # 每 5 分钟检查一次
        self._autonomy_manager = None
        self._improvement_count: int = 0
        self._enabled: bool = False

    async def on_start(self) -> None:
        await super().on_start()
        try:
            from core.autonomy_manager import AutonomyManager

            self._autonomy_manager = AutonomyManager()
            self._autonomy_manager.initialize()
            self._enabled = True
            logger.info("自主进化器官已就绪")
        except Exception as e:
            logger.info(f"自主进化器官休眠 (AutonomyManager 不可用): {e}")

    def on_soul_state(self, state: MiyaSoulState) -> None:
        """
        收到灵魂状态快照。

        在弥娅处于安静阶段且认知负荷低时，
        检查是否需要触发自主改进。
        """
        if not self._enabled or not self._autonomy_manager:
            return

        now = time.time()
        if now - self._last_check_time < self._check_interval:
            return

        # 只在安静阶段触发自主改进
        from core.miya_soul_state import LifecyclePhase

        if state.lifecycle_phase not in (
            LifecyclePhase.IDLE,
            LifecyclePhase.DROWSY,
        ):
            return

        self._last_check_time = now
        self._maybe_trigger_improvement(state)

    def _maybe_trigger_improvement(self, state: MiyaSoulState) -> None:
        """尝试触发一次自主改进"""
        try:
            if not self._autonomy_manager:
                return

            # 检查引擎是否就绪
            engine = getattr(self._autonomy_manager, "engine", None)
            if not engine:
                return

            # 触发改进周期 (非阻塞)
            logger.info(f"自主进化检查: phase={state.lifecycle_phase.value}, tick_count={state.tick_count}")

            # 使用自主引擎的改进周期
            if hasattr(engine, "improvement_cycle"):
                try:
                    # improvement_cycle 是 async 方法，需要在线程安全环境中调用
                    import asyncio

                    coro = engine.improvement_cycle()
                    if self._spine and self._spine._loop:
                        asyncio.run_coroutine_threadsafe(coro, self._spine._loop)
                        self._improvement_count += 1
                        logger.info(f"自主进化 #{self._improvement_count} 已调度")
                    else:
                        logger.debug("自主进化跳过: 无事件循环")
                except Exception as e:
                    logger.debug(f"自主进化周期跳过: {e}")

        except Exception as e:
            logger.debug(f"自主进化检查异常: {e}")

    def get_stats(self) -> dict:
        """获取自主进化统计"""
        return {
            "enabled": self._enabled,
            "improvement_count": self._improvement_count,
            "last_check_time": self._last_check_time,
            "check_interval": self._check_interval,
        }
