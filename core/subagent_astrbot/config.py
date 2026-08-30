"""
AstrBot Subagent 配置
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SubAgentConfig:
    """子代理配置"""

    name: str = ""
    """子代理名称"""

    enabled: bool = True
    """是否启用"""

    persona_id: Optional[str] = None
    """人格ID"""

    system_prompt: str = ""
    """系统提示词"""

    public_description: str = ""
    """公开描述"""

    provider_id: Optional[str] = None
    """Provider ID"""

    tools: List[str] = field(default_factory=list)
    """可用工具列表"""

    begin_dialogs: List[str] = field(default_factory=list)
    """开始对话"""


@dataclass
class SubAgentOrchestratorConfig:
    """子代理编排器配置"""

    agents: List[SubAgentConfig] = field(default_factory=list)
    """子代理列表"""

    max_subagent_depth: int = 3
    """最大子代理深度"""

    enable_handoff: bool = True
    """启用代理切换"""
