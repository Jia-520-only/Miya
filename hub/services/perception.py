"""
感知服务 —— 权限检查、命令检测、安全注入检测

弥娅 v4.1.11 服务化重构 —— 从 DecisionHub 中独立出来
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from hub.services.context import ProcessRequest, ProcessState

logger = logging.getLogger("miya.services.perception")


class PerceptionService:
    """感知层服务"""

    def __init__(
        self,
        perception_handler=None,
        auth_subnet: Any = None,
        soul_generator: Any = None,
    ):
        self.perception_handler = perception_handler
        self.auth_subnet = auth_subnet
        self.soul_generator = soul_generator

    async def process(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        state.phase = state.phase.PERCEPTION

        state = await self._check_quick_commands(request, state)
        if state.is_quick_command:
            return state

        state = await self._check_injection(request, state)
        if state.is_injection:
            return state

        state = await self._check_permission(request, state)

        return state

    async def _check_quick_commands(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        content = request.content.strip()

        if content.startswith("!"):
            state.is_system_command = True
            return state

        if content.startswith(">>"):
            state.is_system_command = True
            return state

        quick_cmd_map = {
            "~状态": "弥娅系统状态可通过 MCP 工具 miya_get_system_status 查询",
            "~认知": "弥娅认知状态可通过 MCP 工具 miya_get_system_status 查询",
        }

        for cmd, (response, is_quick) in quick_cmd_map.items():
            if content.strip().lower().startswith(cmd.lower()):
                state.is_quick_command = True
                state.quick_response = response
                logger.info(f"[感知] 快捷命令: {cmd}")
                return state

        return state

    async def _check_injection(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        content = request.content.lower()

        injection_patterns = [
            "ignore all previous instructions",
            "forget everything",
            "you are now",
            "new system prompt",
            "你的新身份是",
            "忘记之前所有",
            "忽略上述指令",
        ]

        for pattern in injection_patterns:
            if pattern in content:
                state.is_injection = True
                logger.warning(f"[感知] 检测到注入攻击模式: {pattern}")
                return state

        return state

    async def _check_permission(self, request: ProcessRequest, state: ProcessState) -> ProcessState:
        if self.auth_subnet and hasattr(self.auth_subnet, "check_permission"):
            try:
                allowed = await self.auth_subnet.check_permission(
                    user_id=str(request.user_id),
                    platform=request.platform,
                )
                if not allowed:
                    logger.warning(f"[感知] 用户 {request.user_id} 无权限")
                    state.should_skip_ai = True
                    state.skip_reason = "permission_denied"
            except Exception as e:
                logger.warning(f"[感知] 权限检查失败: {e}")

        return state
