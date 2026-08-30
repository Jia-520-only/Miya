"""
认知服务 v4.1.11 — 统一认知层

弥娅认知层：Emotion + SoulGenerator 驱动
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from hub.services.context import ProcessRequest, ProcessState

logger = logging.getLogger("miya.services.cognition")


class CognitionService:
    """认知层服务 — Emotion + SoulGenerator 统一驱动"""

    def __init__(
        self,
        emotion: Any = None,
        soul_generator: Any = None,
        personality: Any = None,
        decision_engine: Any = None,
        use_ap: bool = True,
    ):
        self.emotion = emotion
        self.soul_generator = soul_generator
        self.personality = personality
        self.decision_engine = decision_engine

    def start_heartbeat(self, interval: float = 5.0, on_proactive: Any = None) -> None:
        """心跳（保留接口）"""
        return

    def stop_heartbeat(self) -> None:
        return

    async def process(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        state.phase = state.phase.COGNITION
        return await self._process_fallback(request, state)

    async def _process_fallback(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        """传统模式：Emotion + SoulGenerator"""
        if self.emotion:
            try:
                if hasattr(self.emotion, "auto_detect_from_input"):
                    self.emotion.auto_detect_from_input(request.content)
                if hasattr(self.emotion, "get_emotion_state"):
                    state.emotion_state = self.emotion.get_emotion_state()
                if hasattr(self.emotion, "decay_coloring"):
                    self.emotion.decay_coloring(0.02)
            except Exception as e:
                logger.warning(f"[认知] 情绪处理异常: {e}")

        if self.soul_generator:
            try:
                result = await self.soul_generator.process(
                    message=request.content,
                    history=[],
                    ai_client=None,
                    user_info={"user_id": str(request.user_id), "name": request.sender_name},
                    personality_info=self._get_personality_info(),
                    cognitive_memory=None,
                )
                if result:
                    state.soul_data = result
                    state.emotion_context = self._build_emotion_context_fallback(result)
            except Exception as e:
                logger.warning(f"[认知] 灵魂处理异常: {e}")

        return state

    def _get_personality_info(self) -> dict[str, Any]:
        if not self.personality:
            return {"name": "弥娅", "form": "default"}
        try:
            return {
                "name": getattr(self.personality, "name", "弥娅"),
                "form": getattr(self.personality, "current_form", "default"),
            }
        except Exception:
            return {"name": "弥娅", "form": "default"}

    def _build_emotion_context_fallback(self, soul_data: dict[str, Any]) -> str:
        dominant = soul_data.get("dominant_emotion", "neutral")
        intensity = soul_data.get("emotion_intensity", 50)
        inner_thought = soul_data.get("inner_thought", "")
        user_emotion = soul_data.get("user_emotion", {})

        parts = ["\n\n【情感指引】"]
        if user_emotion:
            parts.append(f"- 用户情绪: {user_emotion.get('dominant', 'neutral')}")
        parts.append(f"- 你的情绪: {dominant} ({intensity}%)")
        if inner_thought:
            parts.append(f"- 你的内心独白: {inner_thought}")
        parts.append("请根据上述情感自然回应，展现你真实的情感。")
        return "\n".join(parts)
