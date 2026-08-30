"""
AstrBot Subagent 编排器

提供子代理管理和编排能力
- 子代理定义和配置
- 代理间切换
- 工具共享
"""

from .agent import SubAgent
from .config import SubAgentConfig
from .orchestrator import SubAgentOrchestrator, get_orchestrator

__all__ = [
    "SubAgentOrchestrator",
    "get_orchestrator",
    "SubAgentConfig",
    "SubAgent",
]
