"""
生成服务 —— AI 响应生成、工具编排、模型调度

弥娅 v4.1.11 重构 —— 从 DecisionHub 中独立出来
"""

from __future__ import annotations

import logging
from typing import Any

from hub.services.context import ProcessRequest, ProcessState

logger = logging.getLogger("miya.services.generation")


class GenerationService:
    """生成层服务"""

    def __init__(
        self,
        ai_client: Any = None,
        personality: Any = None,
        prompt_manager: Any = None,
        tool_subnet: Any = None,
        response_generator: Any = None,
        collaboration_engine: Any = None,
        identity: Any = None,
    ):
        self.ai_client = ai_client
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.tool_subnet = tool_subnet
        self.response_generator = response_generator
        self.collaboration_engine = collaboration_engine
        self.identity = identity

    async def process(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        state.phase = state.phase.GENERATION

        if state.should_skip_ai:
            logger.info(f"[生成] 跳过 AI 生成: {state.skip_reason}")
            state.response = state.quick_response or state.skip_reason
            return state

        state = await self._generate_response(request, state)

        return state

    async def _generate_response(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        if self.response_generator and hasattr(self.response_generator, "generate_response"):
            try:
                response = await self.response_generator.generate_response(
                    content=request.content,
                    platform=request.platform,
                    context={
                        "emotion_context": state.emotion_context,
                        "emotion_state": state.emotion_state,
                        "strategy_guidance": state.strategy_guidance,
                        "selected_model": state.selected_model,
                        "task_type": state.task_type,
                    },
                )
                state.response = response
                logger.info(f"[生成] 响应已生成: {str(response)[:50]}...")
                return state
            except Exception as e:
                logger.error(f"[生成] 生成失败: {e}")
                state.response = await self._fallback(request)
                return state

        state.response = await self._direct_generate(request, state)
        return state

    async def _direct_generate(self, request: ProcessRequest, state: ProcessState) -> str:
        """直接使用 AI 客户端生成"""
        if not self.ai_client:
            return "弥娅正在休息中..."

        try:
            system_prompt = await self._build_system_prompt(request, state)
            response = await self.ai_client.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.content},
                ],
            )
            return response
        except Exception as e:
            logger.error(f"[生成] 直接生成失败: {e}")
            return await self._fallback(request)

    async def _build_system_prompt(self, request: ProcessRequest, state: ProcessState) -> str:
        parts = []

        if self.personality and hasattr(self.personality, "get_system_prompt"):
            parts.append(self.personality.get_system_prompt())
        else:
            from core.config_loader import get_text_config_value

            fallback = get_text_config_value(
                "prompt_templates.generation.fallback_identity", "你是弥娅 (MIYA)，一个 AI 虚拟化身。"
            )
            parts.append(fallback)

        if self.identity and hasattr(self.identity, "get_prompt"):
            parts.append(self.identity.get_prompt())

        if state.emotion_context:
            parts.append(state.emotion_context)

        return "\n\n".join(parts)

    async def _fallback(self, request: ProcessRequest) -> str:
        from core.config_loader import get_text_config_value

        person_names = get_text_config_value(
            "prompt_templates.generation.fallback_replies",
            [
                "嗯...我在想一些事情",
                "让我整理一下思绪",
                "亲爱的，稍等一下哦",
                "我需要一点时间思考",
            ],
        )
        import random

        return random.choice(person_names)
