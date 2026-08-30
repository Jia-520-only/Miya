"""
MIYA 系统信息

提供系统信息查询功能
"""

import platform
import sys
from dataclasses import dataclass
from typing import Dict, List

# Python 版本
PYTHON_VERSION = sys.version.split()[0]
PYTHON_IMPL = platform.python_implementation()

# 系统信息
SYSTEM_NAME = platform.system()
SYSTEM_VERSION = platform.version()
SYSTEM_MACHINE = platform.machine()
SYSTEM_PROCESSOR = platform.processor()


# ==================== 系统信息类 ====================


@dataclass
class SystemInfo:
    """系统信息"""

    name: str = "MIYA"
    version: str = "6.0.0"
    mode: str = "unified"
    python_version: str = ""
    platform: str = ""
    machine: str = ""
    start_time: float = 0
    uptime: int = 0


def get_system_info() -> Dict:
    """获取系统信息"""
    import core.miya_system

    status = core.miya_system.get_system_status() if core.miya_system._SYSTEM else {}

    return {
        "name": "MIYA",
        "version": "6.0",
        "mode": status.get("mode", "unified"),
        "python": PYTHON_VERSION,
        "platform": SYSTEM_NAME,
        "machine": SYSTEM_MACHINE,
        "uptime": status.get("uptime", 0),
    }


def get_modules_info() -> List[Dict]:
    """获取所有模块信息"""
    import core.miya_system

    if not core.miya_system._SYSTEM:
        return []

    status = core.miya_system.get_system_status()
    modules = status.get("modules", {})

    result = []
    for name, info in modules.items():
        result.append(
            {
                "name": name,
                "status": info.get("status", "unknown"),
                "error": info.get("error"),
                "load_time_ms": info.get("load_time_ms", 0),
            }
        )

    return result


def get_runtime_info() -> Dict:
    """获取运行时信息"""
    return {
        "python_version": PYTHON_VERSION,
        "python_implementation": PYTHON_IMPL,
        "system": SYSTEM_NAME,
        "system_version": SYSTEM_VERSION,
        "machine": SYSTEM_MACHINE,
        "processor": SYSTEM_PROCESSOR,
    }


def format_uptime(seconds: int) -> str:
    """格式化运行时间"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


__all__ = [
    "SystemInfo",
    "get_system_info",
    "get_modules_info",
    "get_runtime_info",
    "format_uptime",
]
