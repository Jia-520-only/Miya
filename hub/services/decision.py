"""
决策服务 —— 模型选择、策略决策、Ethics 检查

弥娅 v4.1.11 重构 —— 从 DecisionHub 中独立出来
"""

from __future__ import annotations

import logging
from typing import Any

from hub.services.context import ProcessRequest, ProcessState

logger = logging.getLogger("miya.services.decision")


class DecisionService:
    """决策层服务"""

    def __init__(
        self,
        decision_engine: Any = None,
        model_pool: Any = None,
        model_scheduler: Any = None,
        ethics: Any = None,
        personality: Any = None,
        emotion: Any = None,
    ):
        self.decision_engine = decision_engine
        self.model_pool = model_pool
        self.model_scheduler = model_scheduler
        self.ethics = ethics
        self.personality = personality
        self.emotion = emotion

    async def process(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        state.phase = state.phase.DECISION

        state = await self._select_model(request, state)

        state = await self._check_ethics(request, state)

        state = await self._generate_strategy(request, state)

        return state

    async def _select_model(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        if self.model_scheduler and hasattr(self.model_scheduler, "get_optimal_model"):
            try:
                result = await self.model_scheduler.get_optimal_model(
                    content=request.content,
                    platform=request.platform,
                )
                state.selected_model = result.get("model", "")
                state.task_type = result.get("task_type", "chat")
                logger.info(f"[决策] 模型选择: {state.selected_model} ({state.task_type})")
            except Exception as e:
                logger.warning(f"[决策] 模型选择失败: {e}")

        return state

    async def _check_ethics(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        if self.ethics and hasattr(self.ethics, "check_content"):
            try:
                result = await self.ethics.check_content(request.content)
                if not result.get("allowed", True):
                    state.should_skip_ai = True
                    state.skip_reason = "ethics_blocked"
                    logger.warning(f"[决策] 伦理检查阻止: {result.get('reason')}")
            except Exception as e:
                logger.warning(f"[决策] 伦理检查失败: {e}")

        return state

    async def _generate_strategy(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        if self.decision_engine and hasattr(self.decision_engine, "make_decision"):
            try:
                decision = self.decision_engine.make_decision(
                    context={"content": request.content, "platform": request.platform},
                    options=[{"id": "respond", "label": "生成响应"}],
                )
                if decision:
                    state.strategy_guidance = decision.get("guidance", "")
            except Exception as e:
                logger.warning(f"[决策] 策略生成失败: {e}")

        return state
