"""
弥娅脊柱神经 (MiyaSpine)

弥娅的统一中枢神经系统。
连接决策中枢与所有功能器官（DecisionHub、ProactiveChat、MCP Bridge 等），
通过统一心跳驱动、状态广播、事件回流和生命周期编排，
使弥娅从"各自为政的组件集合"变为"浑然一体的活体"。

架构：

    MiyaSpine (脊柱)
    ├── Heartbeat Driver ─── 统一心跳 (3s/tick)
    │   ├── AP Engine → idle_tick() → 认知闭环
    │   ├── State Snapshot → MiyaSoulState
    │   └── Broadcast → 所有器官
    │
    ├── Organ Registry ─── 所有器官注册表
    │   ├── DecisionHub (决策层)
    │   ├── ProactiveChat (主动表达，合并AP proactive)
    │   ├── MCP Bridge (DSH 终端感知)
    │   ├── AutonomyEngine (自主改进)
    │   ├── Scheduler (统一定时)
    │   └── PlatformRegistry (跨平台分发)
    │
    ├── Lifecycle Orchestrator ─── 生命周期编排
    │   INIT → BOOT → RUNNING → IDLE → DROWSY → SLEEP → SHUTDOWN
    │
    └── Event Router ─── 事件回流
        用户消息 / 行动结果 / 系统事件 → 所有器官
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

from core.miya_organ import MiyaOrgan
from core.miya_soul_state import LifecyclePhase, MiyaSoulState

logger = logging.getLogger("Miya.Spine")


class MiyaSpine:
    """
    弥娅的脊柱神经——中枢总线。

    Usage:
        spine = MiyaSpine()
        spine.register_organ("decision_hub", decision_hub_organ)
        spine.register_organ("proactive_chat", proactive_chat_organ)
        await spine.start()
        await spine.wait()
        await spine.shutdown()
    """

    VERSION = "1.0.0"

    # 生命周期阶段转换阈值 (秒)
    IDLE_THRESHOLD = 60  # 60s 无交互 → IDLE
    DROWSY_THRESHOLD = 300  # 5min 无交互 → DROWSY
    SLEEP_THRESHOLD = 1800  # 30min 无交互 → SLEEP

    def __init__(
        self,
        heartbeat_interval: float = 3.0,
        idle_detection: bool = True,
    ):
        self._heartbeat_interval = heartbeat_interval
        self._idle_detection = idle_detection

        # 器官注册表
        self._organs: dict[str, MiyaOrgan] = {}
        self._organs_by_priority: list[MiyaOrgan] = []

        # 状态
        self._phase: LifecyclePhase = LifecyclePhase.INIT
        self._current_state: MiyaSoulState = MiyaSoulState()
        self._state_lock = threading.Lock()

        # 心跳
        self._heartbeat_running = False
        self._heartbeat_thread: threading.Thread | None = None
        self._tick_count: int = 0
        self._message_count: int = 0

        # 生命周期
        self._start_time: float | None = None
        self._shutdown_event = asyncio.Event()
        self._last_interaction: float = 0.0
        self._loop: asyncio.AbstractEventLoop | None = None

        # 回调：主动消息分发
        self._proactive_sender: Callable[[str], None] | None = None

        # 后台任务
        self._background_tasks: list[asyncio.Task] = []

    # ══════════════════════════════════════════════════
    #  器官注册
    # ══════════════════════════════════════════════════

    def register_organ(self, organ: MiyaOrgan) -> None:
        """注册一个器官到脊柱"""
        if organ.name in self._organs:
            logger.warning(f"Organ [{organ.name}] already registered, replacing")
        self._organs[organ.name] = organ
        organ._spine = self
        self._rebuild_priority_list()
        logger.info(f"Organ [{organ.name}] registered (priority={organ.priority})")

    def register_organs(self, *organs: MiyaOrgan) -> None:
        """批量注册器官"""
        for organ in organs:
            self.register_organ(organ)

    def unregister_organ(self, name: str) -> bool:
        """注销一个器官"""
        if name in self._organs:
            organ = self._organs.pop(name)
            organ._spine = None
            self._rebuild_priority_list()
            logger.info(f"Organ [{name}] unregistered")
            return True
        return False

    def get_organ(self, name: str) -> MiyaOrgan | None:
        """获取指定器官"""
        return self._organs.get(name)

    def _rebuild_priority_list(self) -> None:
        """按 priority 排序重建器官列表"""
        self._organs_by_priority = sorted(self._organs.values(), key=lambda o: o.priority)

    def set_proactive_sender(self, sender: Callable[[str], None]) -> None:
        """设置主动消息分发回调"""
        self._proactive_sender = sender

    # ══════════════════════════════════════════════════
    #  生命周期
    # ══════════════════════════════════════════════════

    @property
    def phase(self) -> LifecyclePhase:
        return self._phase

    @property
    def current_state(self) -> MiyaSoulState:
        with self._state_lock:
            return self._current_state

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def is_running(self) -> bool:
        return self._phase not in (LifecyclePhase.INIT, LifecyclePhase.SHUTDOWN)

    async def start(self) -> None:
        """启动弥娅脊柱神经"""
        if self._phase != LifecyclePhase.INIT:
            logger.warning(f"Spine already started (phase={self._phase})")
            return

        self._loop = asyncio.get_running_loop()
        self._start_time = time.time()
        self._last_interaction = time.time()

        # 1) BOOT 阶段
        await self._transition(LifecyclePhase.BOOT)
        logger.info(f"弥娅脊柱神经 v{self.VERSION} 启动中...")

        # 2) 启动所有器官
        for organ in self._organs_by_priority:
            try:
                await organ.on_start()
            except Exception as e:
                logger.error(f"Organ [{organ.name}] start failed: {e}")

        # 3) 启动心跳
        self._start_heartbeat()

        # 4) RUNNING 阶段
        await self._transition(LifecyclePhase.RUNNING)
        logger.info("弥娅脊柱神经已就绪 — 弥娅活过来了")

    async def shutdown(self) -> None:
        """关闭弥娅脊柱神经"""
        logger.info("弥娅脊柱神经关闭中...")

        # 1) 停止心跳
        self._stop_heartbeat()

        # 2) 转移到 SHUTDOWN
        await self._transition(LifecyclePhase.SHUTDOWN)

        # 3) 关闭所有器官 (逆序)
        for organ in reversed(self._organs_by_priority):
            try:
                await organ.on_shutdown()
            except Exception as e:
                logger.error(f"Organ [{organ.name}] shutdown failed: {e}")

        # 4) 取消后台任务
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._shutdown_event.set()
        logger.info("弥娅脊柱神经已关闭")

    async def wait(self) -> None:
        """阻塞等待直到收到关闭信号"""
        await self._shutdown_event.wait()

    async def _transition(self, new_phase: LifecyclePhase) -> None:
        """执行生命周期阶段转换，通知所有器官"""
        old_phase = self._phase
        if old_phase == new_phase:
            return
        self._phase = new_phase
        logger.info(f"生命阶段: {old_phase.value} → {new_phase.value}")
        for organ in self._organs_by_priority:
            try:
                organ.on_lifecycle_change(old_phase, new_phase)
            except Exception as e:
                logger.error(f"Organ [{organ.name}] lifecycle hook failed: {e}")

    # ══════════════════════════════════════════════════
    #  空闲检测 → 自动阶段转换
    # ══════════════════════════════════════════════════

    def _check_idle(self) -> None:
        """检测空闲时间并自动推进生命周期阶段"""
        if not self._idle_detection:
            return

        elapsed = time.time() - self._last_interaction

        if elapsed > self.SLEEP_THRESHOLD and self._phase not in (
            LifecyclePhase.SLEEP,
            LifecyclePhase.SHUTDOWN,
        ):
            asyncio.run_coroutine_threadsafe(self._transition(LifecyclePhase.SLEEP), self._loop)
        elif elapsed > self.DROWSY_THRESHOLD and self._phase == LifecyclePhase.IDLE:
            asyncio.run_coroutine_threadsafe(self._transition(LifecyclePhase.DROWSY), self._loop)
        elif elapsed > self.IDLE_THRESHOLD and self._phase == LifecyclePhase.RUNNING:
            asyncio.run_coroutine_threadsafe(self._transition(LifecyclePhase.IDLE), self._loop)

    def _wake_if_needed(self) -> None:
        """检查是否需要从休眠/半休眠中唤醒"""
        if self._phase in (LifecyclePhase.DROWSY, LifecyclePhase.SLEEP):
            asyncio.run_coroutine_threadsafe(self._transition(LifecyclePhase.WAKE), self._loop)

    # ══════════════════════════════════════════════════
    #  心跳引擎 — 弥娅的统一心跳
    # ══════════════════════════════════════════════════

    def _start_heartbeat(self) -> None:
        """启动统一心跳线程"""
        if self._heartbeat_running:
            return
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="MiyaSpine-Heartbeat")
        self._heartbeat_thread.start()
        logger.info(f"Spine heartbeat started (interval={self._heartbeat_interval}s)")

    def _stop_heartbeat(self) -> None:
        """停止统一心跳"""
        self._heartbeat_running = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
        logger.info("Spine heartbeat stopped")

    def _heartbeat_loop(self) -> None:
        """心跳循环——这是弥娅活着的节拍"""
        while self._heartbeat_running:
            try:
                self._tick_count += 1

                # ① 捕获弥娅灵魂状态快照
                soul_state = self._capture_soul_state()

                # ② 更新当前状态（线程安全）
                with self._state_lock:
                    self._current_state = soul_state

                # ③ 广播到所有器官
                self._broadcast(soul_state)

                # ④ 空闲检测 → 自动生命周期转换
                self._check_idle()

                # ⑤ 休眠时的节能：降低 tick 频率
                sleep_time = self._heartbeat_interval
                if self._phase == LifecyclePhase.SLEEP:
                    sleep_time = 30.0  # 休眠时 30s 一次 tick
                elif self._phase == LifecyclePhase.DROWSY:
                    sleep_time = 10.0  # 半休眠时 10s 一次 tick

                time.sleep(sleep_time)

            except Exception as e:
                logger.warning(f"Spine heartbeat error: {e}")
                time.sleep(5)

    def _capture_soul_state(self) -> MiyaSoulState:
        """捕获弥娅灵魂状态快照"""
        state = MiyaSoulState(
            tick_index=self._tick_count,
            tick_count=self._tick_count,
            uptime_seconds=self.uptime_seconds,
            lifecycle_phase=self._phase,
            message_count=self._message_count,
        )

        # 器官在线状态
        state.organs_online = {name: organ.started for name, organ in self._organs.items()}

        return state

    # ══════════════════════════════════════════════════
    #  广播
    # ══════════════════════════════════════════════════

    def _broadcast(self, state: MiyaSoulState) -> None:
        """将灵魂状态广播到所有器官"""
        for organ in self._organs_by_priority:
            try:
                organ.on_soul_state(state)
            except Exception as e:
                logger.warning(f"Organ [{organ.name}] on_soul_state failed: {e}")

    # ══════════════════════════════════════════════════
    #  事件注入
    # ══════════════════════════════════════════════════

    def inject_user_message(self, message: str, user_id: str = "") -> None:
        """注入用户消息事件"""
        self._last_interaction = time.time()
        self._message_count += 1
        self._wake_if_needed()

        for organ in self._organs_by_priority:
            try:
                organ.on_user_message(message, user_id)
            except Exception as e:
                logger.warning(f"Organ [{organ.name}] on_user_message failed: {e}")

    def inject_action_result(self, action: str, result: dict) -> None:
        """注入行动结果（回流到所有器官）"""
        for organ in self._organs_by_priority:
            try:
                organ.on_action_result(action, result)
            except Exception as e:
                logger.warning(f"Organ [{organ.name}] on_action_result failed: {e}")

    def inject_system_event(self, event: str, data: dict | None = None) -> None:
        """注入系统事件"""
        for organ in self._organs_by_priority:
            try:
                organ.on_system_event(event, data)
            except Exception as e:
                logger.warning(f"Organ [{organ.name}] on_system_event failed: {e}")

    # ══════════════════════════════════════════════════
    #  状态查询 (供外部使用)
    # ══════════════════════════════════════════════════

    def get_status(self) -> dict:
        """获取弥娅当前状态摘要"""
        state = self.current_state
        return {
            "version": self.VERSION,
            "phase": self._phase.value,
            "uptime_seconds": self.uptime_seconds,
            "tick_count": self._tick_count,
            "message_count": self._message_count,
            "organs": list(self._organs.keys()),
            "organs_online": state.organs_online,
            "proactive": state.proactive,
        }


# ── 全局单例 ──

_spine_instance: MiyaSpine | None = None


def get_spine() -> MiyaSpine:
    """获取全局弥娅脊柱实例（懒初始化）"""
    global _spine_instance
    if _spine_instance is None:
        _spine_instance = MiyaSpine()
    return _spine_instance


def reset_spine() -> None:
    """重置脊柱实例（用于测试或重启）"""
    global _spine_instance
    _spine_instance = None
