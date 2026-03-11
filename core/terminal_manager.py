"""
核心终端管理模块 - 弥娅V4.0
支持单机多终端管理、智能编排、协同执行
"""

from .terminal_manager import (
    TerminalType,
    TerminalStatus,
    CommandResult,
    TerminalSession,
    LocalTerminalManager
)

from .terminal_orchestrator import (
    IntelligentTerminalOrchestrator
)

__all__ = [
    # 枚举
    'TerminalType',
    'TerminalStatus',
    
    # 数据类
    'CommandResult',
    'TerminalSession',
    
    # 管理器
    'LocalTerminalManager',
    'IntelligentTerminalOrchestrator',
]
