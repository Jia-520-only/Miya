"""
弥娅编排器 —— 替代 DecisionHub 的轻量级协调层

弥娅 v4.1.11 服务化重构
- 每个服务独立可测试
- 通过 M-Link 进行服务间通信
- 清晰的流水线：感知 → 认知 → 决策 → 生成 → 记忆
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from hub.services.context import ProcessRequest, ProcessResult, ProcessState
from hub.services.cognition import CognitionService
from hub.services.decision import DecisionService
from hub.services.generation import GenerationService
from hub.services.memory import MemoryService
from hub.services.perception import PerceptionService

logger = logging.getLogger("miya.services.orchestrator")


class MiyaOrchestrator:
    """
    弥娅编排器 —— v9.0 服务层替代 DecisionHub

    职责：
    1. 初始化所有服务
    2. 编排消息处理流水线
    3. 管理服务生命周期
    """

    def __init__(self):
        self.perception: Optional[PerceptionService] = None
        self.cognition: Optional[CognitionService] = None
        self.decision: Optional[DecisionService] = None
        self.generation: Optional[GenerationService] = None
        self.memory: Optional[MemoryService] = None

        self._initialized = False
        self._legacy_deps: dict[str, Any] = {}

    def wire_from_legacy(self, **deps: Any) -> "MiyaOrchestrator":
        """
        从旧 DecisionHub 的依赖中接线

        这是过渡期的桥梁方法，未来逐步移除。
        """
        self._legacy_deps.update(deps)

        self.perception = PerceptionService(
            perception_handler=deps.get("perception_handler"),
            auth_subnet=deps.get("auth_subnet"),
            soul_generator=deps.get("soul_generator"),
        )

        self.cognition = CognitionService(
            emotion=deps.get("emotion"),
            soul_generator=deps.get("soul_generator"),
            personality=deps.get("personality"),
            decision_engine=deps.get("decision_engine"),
            use_ap=deps.get("use_ap", True),
        )

        self.decision = DecisionService(
            decision_engine=deps.get("decision_engine"),
            model_pool=deps.get("model_pool"),
            model_scheduler=deps.get("model_scheduler"),
            ethics=deps.get("ethics"),
            personality=deps.get("personality"),
            emotion=deps.get("emotion"),
        )

        self.generation = GenerationService(
            ai_client=deps.get("ai_client"),
            personality=deps.get("personality"),
            prompt_manager=deps.get("prompt_manager"),
            tool_subnet=deps.get("tool_subnet"),
            response_generator=deps.get("response_generator"),
            collaboration_engine=deps.get("collaboration_engine"),
            identity=deps.get("identity"),
        )

        self.memory = MemoryService(
            memory_net=deps.get("memory_net"),
            memory_engine=deps.get("memory_engine"),
            memory_manager=deps.get("memory_manager"),
            historian=deps.get("historian"),
            lifebook=deps.get("lifebook"),
            session_manager=deps.get("session_manager"),
            session_handler=deps.get("session_handler"),
        )

        self._initialized = True
        logger.info("[编排器] 从旧依赖接线完成")
        return self

    def is_ready(self) -> bool:
        return self._initialized

    async def process_message(
        self,
        message: Any,
        callback: Optional[Any] = None,
    ) -> Optional[str]:
        """
        处理单条消息 —— 完整流水线

        流水线：归约 → 感知 → 认知 → 决策 → 生成 → 记忆 → 回调
        """
        request = self._normalize_message(message)
        state = ProcessState()

        try:
            state = await self.perception.process(request, state)

            if state.is_quick_command:
                return state.quick_response

            if state.is_injection:
                self.memory.store_input(request, state)
                return None

            state = await self.memory.store_input(request, state)

            state = await self.cognition.process(request, state)

            state = await self.decision.process(request, state)

            state = await self.generation.process(request, state)

            state = await self.memory.store_output(request, state)

            state = await self.memory.on_session_end(request, state)

            if callback and state.response:
                await self._invoke_callback(callback, request, state)

            return state.response

        except Exception as e:
            logger.error(f"[编排器] 处理异常: {e}", exc_info=True)
            return None

    def _normalize_message(self, message: Any) -> ProcessRequest:
        """将 M-Link 消息或原始感知数据归一化为 ProcessRequest"""
        if hasattr(message, "content"):
            perception = message.content if isinstance(message.content, dict) else {"content": str(message.content)}
            source = getattr(message, "source", "terminal")
        elif isinstance(message, dict):
            perception = message
            source = message.get("platform", message.get("source", "terminal"))
        else:
            perception = {"content": str(message)}
            source = "terminal"

        raw_content = perception.get("content", perception.get("input", ""))
        if isinstance(raw_content, list):
            content = ""
            for item in raw_content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        content = item.get("data", {}).get("text", "")
                        break
                    elif item.get("type") == "image":
                        content = "[图片]"
                        break
        else:
            content = str(raw_content)

        return ProcessRequest(
            content=content,
            raw_perception=perception,
            platform=source,
            sender_name=perception.get("sender_name", "用户"),
            user_id=perception.get("user_id", perception.get("sender_id", "")),
            group_id=perception.get("group_id", 0),
            session_id=perception.get("session_id", perception.get("group_id", source)),
            message_type=perception.get("message_type", "text"),
        )

    async def _invoke_callback(self, callback, request: ProcessRequest, state: ProcessState) -> None:
        try:
            if callable(callback):
                result = callback(request, state)
                if hasattr(result, "__await__"):
                    await result
        except Exception as e:
            logger.warning(f"[编排器] 回调异常: {e}")

    def start_ap_heartbeat(self, interval: float = 5.0) -> None:
        """启动心跳——让弥娅拥有持续的自主能力"""
        if self.cognition:
            self.cognition.start_heartbeat(interval=interval)
            logger.info("[编排器] 心跳已启动")

    def stop_ap_heartbeat(self) -> None:
        """停止心跳"""
        if self.cognition:
            self.cognition.stop_heartbeat()

    def get_status(self) -> dict[str, Any]:
        status = {
            "initialized": self._initialized,
            "services": {
                "perception": self.perception is not None,
                "cognition": self.cognition is not None,
                "decision": self.decision is not None,
                "generation": self.generation is not None,
                "memory": self.memory is not None,
            },
        }
        if self.cognition:
            status["ap"] = self.cognition.get_ap_status()
        return status
