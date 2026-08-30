"""
平台状态与事件定义

定义平台全生命周期中的状态、事件和健康度模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PlatformStatus(str, Enum):
    """平台连接状态"""

    DISABLED = "disabled"  # 未启用
    CONNECTING = "connecting"  # 正在连接
    ONLINE = "online"  # 已连接，正常
    DEGRADED = "degraded"  # 已连接但性能下降
    RECONNECTING = "reconnecting"  # 断开后正在重连
    OFFLINE = "offline"  # 已断开（手动断开或多次重连失败）
    ERROR = "error"  # 发生错误无法恢复


class PlatformEvent(str, Enum):
    """平台生命周期事件"""

    REGISTERED = "platform.registered"
    UNREGISTERED = "platform.unregistered"
    CONNECTING = "platform.connecting"
    CONNECTED = "platform.connected"
    DISCONNECTED = "platform.disconnected"
    RECONNECTING = "platform.reconnecting"
    RECONNECTED = "platform.reconnected"
    RECONNECT_FAILED = "platform.reconnect_failed"
    ERROR = "platform.error"
    HEALTH_CHECK_FAILED = "platform.health_check_failed"
    HEALTH_CHECK_RECOVERED = "platform.health_check_recovered"
    SHUTDOWN = "platform.shutdown"


@dataclass
class PlatformHealth:
    """平台健康状态快照"""

    status: PlatformStatus = PlatformStatus.DISABLED
    last_online: Optional[datetime] = None
    last_offline: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    reconnect_count: int = 0
    max_reconnect_attempts: int = 10
    latency_ms: float = 0.0
    message_count: int = 0
    message_in_count: int = 0
    message_out_count: int = 0
    uptime_seconds: float = 0.0
    last_heartbeat: Optional[datetime] = None
    heartbeat_interval: float = 30.0
    consecutive_health_failures: int = 0
    last_message_received: Optional[datetime] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "last_online": self.last_online.isoformat() if self.last_online else None,
            "last_offline": self.last_offline.isoformat() if self.last_offline else None,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "reconnect_count": self.reconnect_count,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "latency_ms": self.latency_ms,
            "message_count": self.message_count,
            "message_in_count": self.message_in_count,
            "message_out_count": self.message_out_count,
            "uptime_seconds": self.uptime_seconds,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "heartbeat_interval": self.heartbeat_interval,
            "consecutive_health_failures": self.consecutive_health_failures,
            "last_message_received": self.last_message_received.isoformat() if self.last_message_received else None,
        }
