"""
弥娅统一平台抽象层 (Miya Unified Platform Layer)

提供：
- PlatformStatus: 平台状态枚举
- BasePlatform: 平台基类 (生命周期: connect/disconnect/health/reconnect)
- PlatformRegistry: 动态平台注册表 (无 if-elif 链)
- ReconnectPolicy: 重连策略 (指数退避)
"""

from .base import BasePlatform
from .platform_type import MiyaPlatform
from .reconnect import ExponentialBackoffPolicy, ReconnectPolicy
from .registry import PlatformRegistry, get_registry, register_platform
from .status import PlatformEvent, PlatformHealth, PlatformStatus

__all__ = [
    "MiyaPlatform",
    "PlatformStatus",
    "PlatformHealth",
    "PlatformEvent",
    "BasePlatform",
    "PlatformRegistry",
    "register_platform",
    "get_registry",
    "ReconnectPolicy",
    "ExponentialBackoffPolicy",
]
