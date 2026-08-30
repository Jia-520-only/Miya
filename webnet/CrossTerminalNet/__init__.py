"""
CrossTerminalNet - 跨端互联模块

提供多端消息转发、状态同步、设备发现等功能
"""

from .hub import CrossTerminalHub

__all__ = ['CrossTerminalHub']
