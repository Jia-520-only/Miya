"""
单机多终端管理系统 - 弥娅V4.0核心模块

支持在同一操作系统上同时管理多个终端窗口
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable
import time

class TerminalType(Enum):
    """终端类型"""
    CMD = "cmd"              # Windows CMD
    POWERSHELL = "powershell"  # Windows PowerShell
    WSL = "wsl"             # WSL Bash
    BASH = "bash"            # Linux/Mac Bash
    ZSH = "zsh"             # Zsh
    GIT_BASH = "git_bash"     # Git Bash
    VENV = "venv"            # Python虚拟环境
    
    @classmethod
    def from_string(cls, value: str) -> 'TerminalType':
        """从字符串创建终端类型"""
        value_map = {
            'cmd': cls.CMD,
            'powershell': cls.POWERSHELL,
            'ps': cls.POWERSHELL,
            'wsl': cls.WSL,
            'bash': cls.BASH,
            'zsh': cls.ZSH,
            'git_bash': cls.GIT_BASH,
            'git': cls.GIT_BASH,
            'venv': cls.VENV
        }
        return value_map.get(value.lower(), cls.CMD)

class TerminalStatus(Enum):
    """终端状态"""
    IDLE = "idle"           # 空闲
    EXECUTING = "executing"  # 执行中
    ERROR = "error"          # 错误
    CLOSED = "closed"        # 已关闭

@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    session_id: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "session_id": self.session_id
        }

@dataclass
class OutputData:
    """输出数据"""
    type: str  # 'output' or 'error'
    content: str
    timestamp: float
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp
        }

@dataclass
class TerminalSession:
    """终端会话"""
    id: str
    name: str
    terminal_type: TerminalType
    process: Optional['subprocess.Popen'] = None
    status: TerminalStatus = TerminalStatus.IDLE
    current_dir: str = "."
    
    def __post_init__(self):
        import os
        if self.current_dir == ".":
            self.current_dir = os.getcwd()
    
    # 历史记录
    command_history: List[Dict] = field(default_factory=list)
    output_history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.terminal_type.value,
            "status": self.status.value,
            "directory": self.current_dir,
            "command_count": len(self.command_history),
            "output_count": len(self.output_history)
        }
    
    def add_command(self, command: str):
        """添加命令到历史"""
        self.command_history.append({
            "timestamp": time.time(),
            "command": command
        })
    
    def add_output(self, output: OutputData):
        """添加输出到历史"""
        self.output_history.append(output.to_dict())
