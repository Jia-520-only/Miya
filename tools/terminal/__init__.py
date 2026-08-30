"""
智能终端工具模块
弥娅系统的终端命令执行能力，支持跨平台和自然语言
"""

from .platform_detector import (
    detect_platform,
    detect_linux_distro,
    get_platform_name,
    get_system_info,
    is_windows,
    is_linux,
    is_macos
)
from .platform_adapter import WindowsAdapter, LinuxAdapter, MacOSAdapter, get_platform_adapter
from .command_executor import CommandExecutor, ExecutionResult
from .nlp_parser import NLPParser, CommandIntent
from .security import SecurityAuditor, SecurityLevel
from .command_history import CommandHistory
from .terminal_tool import TerminalTool
from .command_chain import CommandChain, CommandChainManager, Step, StepStatus
from .command_templates import CommandChainTemplates

__all__ = [
    # 平台检测
    'detect_platform',
    'detect_linux_distro',
    'get_platform_name',
    'get_system_info',
    'is_windows',
    'is_linux',
    'is_macos',
    # 平台适配器
    'WindowsAdapter',
    'LinuxAdapter',
    'MacOSAdapter',
    'get_platform_adapter',
    # 命令执行
    'CommandExecutor',
    'ExecutionResult',
    # NLP 解析
    'NLPParser',
    'CommandIntent',
    # 安全审计
    'SecurityAuditor',
    'SecurityLevel',
    # 命令历史
    'CommandHistory',
    # 终端工具
    'TerminalTool',
    # 命令链
    'CommandChain',
    'CommandChainManager',
    'Step',
    'StepStatus',
    'CommandChainTemplates',
]


