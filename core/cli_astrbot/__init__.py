"""
AstrBot CLI 命令模块

提供命令行接口能力
"""

from .commands import CLICommand, CommandRegistry
from .runner import CLIRunner

__all__ = ["CLICommand", "CommandRegistry", "CLIRunner"]
