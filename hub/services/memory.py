"""
记忆服务 —— 消息存储、检索、LifeBook、Historian

弥娅 v4.1.11 重构 —— 从 DecisionHub 中独立出来
"""

from __future__ import annotations

import logging
from typing import Any

from hub.services.context import ProcessRequest, ProcessState

logger = logging.getLogger("miya.services.memory")


class MemoryService:
    """记忆层服务"""

    def __init__(
        self,
        memory_net: Any = None,
        memory_engine: Any = None,
        memory_manager: Any = None,
        historian: Any = None,
        lifebook: Any = None,
        session_manager: Any = None,
        session_handler: Any = None,
    ):
        self.memory_net = memory_net
        self.memory_engine = memory_engine
        self.memory_manager = memory_manager
        self.historian = historian
        self.lifebook = lifebook
        self.session_manager = session_manager
        self.session_handler = session_handler

    async def store_input(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        """存储用户输入消息"""
        perception = request.raw_perception

        if self.memory_manager and hasattr(self.memory_manager, "store_user_message"):
            try:
                await self.memory_manager.store_user_message(perception)
            except Exception as e:
                logger.warning(f"[记忆] MemoryManager 存储失败: {e}")
        else:
            # 回退：直接调用 MemoryBus
            try:
                from memory import get_memory_bus
                bus = await get_memory_bus()
                await bus.store_dialogue(
                    content=request.content,
                    user_id=str(request.user_id),
                    session_id=request.session_id or request.target_id,
                    platform=request.platform,
                    role="user",
                    group_id=str(request.group_id) if request.is_group else None,
                    tags=["dialogue", "user_input"],
                )
                logger.debug(f"[记忆] 用户消息已存储: {request.content[:30]}")
            except Exception as e:
                logger.warning(f"[记忆] 存储用户消息失败: {e}")

        return state

    async def store_output(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        """存储助手响应"""
        if not state.response:
            return state

        stored = False

        if self.memory_manager and hasattr(self.memory_manager, "store_assistant_response"):
            try:
                await self.memory_manager.store_assistant_response(request.raw_perception, state.response)
                stored = True
            except Exception as e:
                logger.warning(f"[记忆] MemoryManager 存储失败: {e}")

        if not stored:
            try:
                from memory import get_memory_bus
                bus = await get_memory_bus()
                await bus.store_dialogue(
                    content=state.response,
                    user_id="miya",
                    session_id=request.session_id or request.target_id,
                    platform=request.platform,
                    role="assistant",
                    group_id=str(request.group_id) if request.is_group else None,
                    tags=["dialogue", "assistant_response"],
                )
                stored = True
                logger.debug(f"[记忆] 响应已存储: {state.response[:30]}")
            except Exception as e:
                logger.warning(f"[记忆] 存储响应失败: {e}")

        if self.historian and hasattr(self.historian, "auto_extract"):
            try:
                await self.historian.auto_extract(
                    user_input=request.content,
                    assistant_response=state.response,
                    user_id=str(request.user_id),
                )
            except Exception as e:
                logger.warning(f"[记忆] Historian 提取失败: {e}")

        if stored:
            state.memory_stored = True

        return state

    async def get_context(self, request: ProcessRequest, max_tokens: int = 2000) -> list[dict[str, Any]]:
        """获取对话上下文（统一跨平台检索，user_id 为主键）"""
        try:
            from memory import get_memory_bus
            bus = await get_memory_bus()

            user_id = str(request.user_id) if request.user_id else ""
            session_id = request.session_id or request.target_id

            if user_id:
                history = await bus.get_user_dialogue(user_id=user_id, limit=20)
            else:
                history = await bus.get_dialogue_history(session_id=session_id, limit=20)

            if not history and session_id:
                history = await bus.get_dialogue_history(session_id=session_id, limit=20)

            return [
                {
                    "role": h.role if hasattr(h, "role") else "user",
                    "content": h.content if hasattr(h, "content") else str(h),
                }
                for h in history
            ]
        except Exception as e:
            logger.warning(f"[记忆] 获取上下文失败: {e}")
            return []

    async def on_session_end(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        """会话结束时处理"""
        if self.session_handler and hasattr(self.session_handler, "on_session_end"):
            try:
                await self.session_handler.on_session_end(
                    user_id=str(request.user_id),
                    platform=request.platform,
                    group_id=str(request.group_id) if request.is_group else None,
                )
            except Exception as e:
                logger.warning(f"[记忆] 会话结束处理失败: {e}")

        if self.lifebook and hasattr(self.lifebook, "add_diary"):
            try:
                await self.lifebook.add_diary(
                    user_id=str(request.user_id),
                    content=f"与用户的对话: {request.content[:100]}",
                    context={"response": (state.response or "")[:100]},
                )
            except Exception as e:
                logger.warning(f"[记忆] LifeBook 写入失败: {e}")

        return state
