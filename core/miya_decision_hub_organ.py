"""
弥娅决策中枢器官 (MiyaDecisionHubOrgan)

将 DecisionHub 挂载到 MiyaSpine 脊柱上。
使决策中枢能够感知：
- 脊柱生命周期的变化（RUNNING → IDLE → DROWSY）
- 弥娅当前的灵魂状态（用于调整决策风格）
- 用户消息事件回流

v8.0 脊柱神经架构的一部分。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.miya_organ import MiyaOrgan

if TYPE_CHECKING:
    from core.miya_soul_state import MiyaSoulState, LifecyclePhase

logger = logging.getLogger("Miya.DecisionHubOrgan")


class MiyaDecisionHubOrgan(MiyaOrgan):
    """
    决策中枢脊柱器官。

    功能：
    - 接收脊柱生命周期的变更通知，相应调整决策层行为
    - 接收灵魂状态广播，缓存供决策层查询
    - 转发用户消息和行动结果到决策层
    """

    def __init__(self):
        super().__init__(name="decision_hub", priority=30)
        self._cached_state: MiyaSoulState | None = None
        self._hub = None

    def bind_decision_hub(self, hub) -> None:
        """绑定 DecisionHub 实例"""
        self._hub = hub
        logger.info("DecisionHub 已绑定到脊柱器官")

    async def on_start(self) -> None:
        await super().on_start()
        logger.info("决策中枢器官已接入脊柱")

    def on_lifecycle_change(self, old_phase: LifecyclePhase, new_phase: LifecyclePhase) -> None:
        from core.miya_soul_state import LifecyclePhase

        if new_phase == LifecyclePhase.IDLE:
            logger.info("脊柱进入 IDLE 阶段——决策层可降低轮询频率")
        elif new_phase == LifecyclePhase.DROWSY:
            logger.info("脊柱进入 DROWSY 阶段——决策层进入节能模式")
        elif new_phase == LifecyclePhase.SLEEP:
            logger.info("脊柱进入 SLEEP 阶段——决策层暂停非必要活动")
        elif new_phase == LifecyclePhase.WAKE:
            logger.info("脊柱唤醒——决策层恢复全功能")

    def on_soul_state(self, state: MiyaSoulState) -> None:
        """缓存最新灵魂状态，供决策层快速访问"""
        self._cached_state = state

    def on_user_message(self, message: str, user_id: str = "") -> None:
        """转发用户消息事件到决策层"""
        if self._hub and hasattr(self._hub, "on_spine_user_message"):
            try:
                self._hub.on_spine_user_message(message, user_id)
            except Exception:
                pass

    def get_cached_state(self) -> MiyaSoulState | None:
        """获取缓存的灵魂状态快照"""
        return self._cached_state
