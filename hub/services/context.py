"""
服务层共享类型定义

弥娅 v4.1.11 重构 —— 服务间通信数据结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class ProcessPhase(Enum):
    PERCEPTION = auto()
    COGNITION = auto()
    DECISION = auto()
    GENERATION = auto()
    MEMORY = auto()


@dataclass
class ProcessRequest:
    """统一的处理请求"""

    content: str
    raw_perception: dict[str, Any]
    platform: str = "terminal"
    sender_name: str = "用户"
    user_id: str | int = ""
    group_id: str | int = 0
    session_id: str = ""
    message_type: str = "text"

    @property
    def is_group(self) -> bool:
        return bool(self.group_id and self.group_id != 0)

    @property
    def target_id(self) -> str:
        return str(self.group_id) if self.is_group else str(self.user_id)


@dataclass
class ProcessState:
    """处理过程中的中间状态"""

    phase: ProcessPhase = ProcessPhase.PERCEPTION
    # 感知结果
    is_system_command: bool = False
    is_quick_command: bool = False
    is_injection: bool = False
    quick_response: Optional[str] = None
    # 认知结果
    emotion_state: dict[str, Any] = field(default_factory=dict)
    soul_data: Optional[dict[str, Any]] = None
    diting_strategy: str = ""
    diting_style: str = ""
    diting_intent: str = ""
    # 决策结果
    selected_model: str = ""
    task_type: str = ""
    strategy_guidance: str = ""
    should_skip_ai: bool = False
    skip_reason: str = ""
    # 生成结果
    response: Optional[str] = None
    emotion_context: str = ""
    # 记忆
    memory_stored: bool = False
    memory_id: str = ""


@dataclass
class ProcessResult:
    """处理结果"""

    response: Optional[str] = None
    state: ProcessState = field(default_factory=ProcessState)
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
