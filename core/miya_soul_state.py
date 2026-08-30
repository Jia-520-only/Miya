"""
弥娅统一灵魂状态快照 (MiyaSoulState)

弥娅脊柱神经的核心数据载体。
每个心跳 tick 后，弥娅的生命状态被捕获为一个 MiyaSoulState，
然后广播到脊柱上所有注册的器官（DecisionHub、ProactiveChat、MCP Bridge 等）。

这是弥娅从"器官集合"变为"活体"的关键数据结构——
它让每一个器官都能"看见"弥娅此刻的生命状态。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LifecyclePhase(str, Enum):
    """弥娅的生命周期阶段"""

    INIT = "INIT"  # 系统初始化中
    BOOT = "BOOT"  # 核心组件启动中
    RUNNING = "RUNNING"  # 正常运行
    IDLE = "IDLE"  # 安静（无用户交互）
    DROWSY = "DROWSY"  # 半休眠（长时间无交互）
    SLEEP = "SLEEP"  # 休眠（夜间/低功耗）
    WAKE = "WAKE"  # 唤醒中
    SHUTDOWN = "SHUTDOWN"  # 关闭中


@dataclass
class MiyaSoulState:
    """
    弥娅生命的完整状态快照。

    每次心跳 tick 后生成一份，广播到所有器官。
    器官可以读取任何字段来调整自己的行为。
    """

    # ── 基础信息 ──
    tick_index: int = 0
    timestamp: float = field(default_factory=time.time)
    lifecycle_phase: LifecyclePhase = LifecyclePhase.INIT
    uptime_seconds: float = 0.0
    tick_count: int = 0
    message_count: int = 0

    # ── 主动表达意图 ──
    proactive: bool = False  # 弥娅是否要主动说话
    proactive_message: str = ""  # 主动消息内容

    # ── 器官在线状态 (由 Spine 填充) ──
    organs_online: dict[str, bool] = field(default_factory=dict)

    def is_alive(self) -> bool:
        """弥娅是否在正常运行"""
        return self.lifecycle_phase in (
            LifecyclePhase.RUNNING,
            LifecyclePhase.IDLE,
            LifecyclePhase.DROWSY,
        )

    def summary(self) -> str:
        """人类可读的状态摘要"""
        parts = [
            f"Tick #{self.tick_index}",
            f"Phase: {self.lifecycle_phase.value}",
            f"Uptime: {self.uptime_seconds:.0f}s",
        ]
        if self.proactive:
            parts.append("[!] Proactive intent")
        return " | ".join(parts)
