"""
核心终端管理模块 - 弥娅V4.0
支持单机多终端管理、智能编排、协同执行
"""

from .terminal_types import (
    TerminalType,
    TerminalStatus,
    CommandResult,
    TerminalSession
)

from .local_terminal_manager import (
    LocalTerminalManager
)

from .terminal_orchestrator import (
    IntelligentTerminalOrchestrator
)

from .master_terminal_controller import (
    MasterTerminalController,
    Task,
    TaskResult,
    TaskPriority
)

from .child_terminal import (
    ChildTerminal,
    ChildTerminalConfig,
    ChildTerminalManager
)

from .miya_takeover_mode import (
    MiyaTakeoverMode
)

__all__ = [
    # 枚举
    'TerminalType',
    'TerminalStatus',
    'TaskPriority',
    
    # 数据类
    'CommandResult',
    'TerminalSession',
    'Task',
    'TaskResult',
    'ChildTerminalConfig',
    
    # 管理器
    'LocalTerminalManager',
    'IntelligentTerminalOrchestrator',
    'MasterTerminalController',
    'ChildTerminal',
    'ChildTerminalManager',
    'MiyaTakeoverMode',
]
