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
import copy
import logging
import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Any, Callable

from core.miya_intention import MAX_FOLLOWUPS, TERMINAL_STATUSES, change_intention, life_scope, project_intention, same_scope
from core.miya_life_event import LifeEventType, MiyaEvent
from core.miya_life_journal import LifeEventJournal, default_journal_path
from core.miya_organ import MiyaOrgan
from core.miya_soul_state import LifecyclePhase, MiyaLifeState, MiyaSoulState

logger = logging.getLogger("Miya.Spine")


class MiyaSpine:
    """
    弥娅的脊柱神经——中枢总线。

    Usage:
        spine = MiyaSpine()
        spine.register_organ(decision_hub_organ)
        spine.register_organ(proactive_chat_organ)
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
        event_journal: LifeEventJournal | None = None,
    ):
        self._heartbeat_interval = heartbeat_interval
        self._idle_detection = idle_detection

        # 器官注册表
        self._organs: dict[str, MiyaOrgan] = {}
        self._organs_by_priority: list[MiyaOrgan] = []

        # 状态
        self._phase: LifecyclePhase = LifecyclePhase.INIT
        self._current_state: MiyaSoulState = MiyaSoulState()
        self._state_lock = threading.RLock()
        self._event_lock = threading.RLock()
        self._life_state = MiyaLifeState()
        self._event_history: deque[MiyaEvent] = deque(maxlen=200)
        self._event_journal = event_journal
        self._persistence_error = ""
        self._failed_writes = 0
        self._failed_event_ids: deque[str] = deque(maxlen=200)
        self._pending_journal_events: deque[MiyaEvent] = deque()
        self._dropped_writes = 0
        self._intentions: dict[str, dict] = {}
        self._focus_scope: dict[str, str] | None = None
        self._emotion_provider: Callable | None = None

        # 心跳
        self._heartbeat_running = False
        self._heartbeat_thread: threading.Thread | None = None
        self._tick_count: int = 0
        self._last_heartbeat_at: float | None = None
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
        if self._event_journal is not None:
            try:
                restored = self._event_journal.recent()
                self._event_history.extend(restored)
                self._life_state.recent_experience = [event.to_dict() for event in restored[-20:]]
                self._life_state.last_event_at = restored[-1].timestamp if restored else None
                self._intentions = {
                    record["intention_id"]: record for record in self._event_journal.load_intentions()
                }
                # 历史只恢复为证据，不重放器官钩子或恢复旧会话的行动。
                self._current_state = self._capture_soul_state()
            except Exception as exc:
                self._persistence_error = str(exc)
                logger.warning("生命事件历史恢复失败: %s", exc)
        # 上次退出时没有回执的行动只恢复为待核实事项，绝不重放工具。
        for record in tuple(self._intentions.values()):
            if record["status"] in {"in_progress", "paused"} and record.get("pending_action_id"):
                self.manage_intention("recover", record, intention_id=record["intention_id"])

    # ══════════════════════════════════════════════════
    #  器官注册
    # ══════════════════════════════════════════════════

    def register_organ(self, organ: MiyaOrgan) -> None:
        """注册一个器官到脊柱"""
        if organ.name in self._organs:
            logger.warning(f"Organ [{organ.name}] already registered, replacing")
        self._organs[organ.name] = organ
        organ.bind_spine(self)
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
            organ.bind_spine(None)
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
            return copy.deepcopy(self._current_state)

    @property
    def event_history(self) -> tuple[MiyaEvent, ...]:
        with self._state_lock:
            return copy.deepcopy(tuple(self._event_history))

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

        await asyncio.to_thread(self.flush_event_journal, limit=512)

        self._shutdown_event.set()
        logger.info("弥娅脊柱神经已关闭")

    async def wait(self) -> None:
        """阻塞等待直到收到关闭信号"""
        await self._shutdown_event.wait()

    async def _transition(self, new_phase: LifecyclePhase) -> None:
        """执行生命周期阶段转换，通知所有器官"""
        with self._event_lock:
            old_phase = self._phase
            if old_phase == new_phase:
                return
            with self._state_lock:
                self._phase = new_phase
                self._life_state.life_phase = new_phase.value
            logger.info(f"生命阶段: {old_phase.value} → {new_phase.value}")
            self.emit_event(MiyaEvent(
                event_type=LifeEventType.LIFECYCLE_CHANGED,
                source="spine",
                payload={"old_phase": old_phase.value, "new_phase": new_phase.value},
                importance=0.7,
            ))

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
        if (
            self._phase in (LifecyclePhase.IDLE, LifecyclePhase.DROWSY, LifecyclePhase.SLEEP)
            and self._loop is not None
            and self._loop.is_running()
        ):
            asyncio.run_coroutine_threadsafe(self._resume_interaction(), self._loop)

    async def _resume_interaction(self) -> None:
        if self._phase in (LifecyclePhase.DROWSY, LifecyclePhase.SLEEP):
            await self._transition(LifecyclePhase.WAKE)
        if self._phase in (LifecyclePhase.IDLE, LifecyclePhase.WAKE):
            await self._transition(LifecyclePhase.RUNNING)

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
                with self._event_lock:
                    # 捕获与发布为同一次更新，避免覆盖刚刚接收的事件状态。
                    with self._state_lock:
                        self._tick_count += 1
                        self._last_heartbeat_at = time.time()
                        soul_state = self._capture_soul_state()
                        self._current_state = copy.deepcopy(soul_state)
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
        with self._state_lock:
            records = sorted(self._intentions.values(), key=lambda item: item["updated_at"], reverse=True)
            self._life_state.intentions = copy.deepcopy([
                item for item in records if item["status"] not in TERMINAL_STATUSES
            ][:50])
            focused = [item for item in records if self._focus_scope and same_scope(item, self._focus_scope)]
            self._life_state.needs = {
                "pending": sum(item["status"] not in TERMINAL_STATUSES | {"paused"} for item in focused),
                "needs_confirmation": sum(item["status"] == "needs_confirmation" for item in focused),
            }
            if self._emotion_provider is not None:
                try:
                    self._life_state.mood = copy.deepcopy(self._emotion_provider(focused))
                except Exception as exc:
                    logger.warning("经历情绪投影失败: %s", exc)
            return MiyaSoulState(
                tick_index=self._tick_count,
                tick_count=self._tick_count,
                last_heartbeat_at=self._last_heartbeat_at,
                uptime_seconds=self.uptime_seconds,
                lifecycle_phase=self._phase,
                message_count=self._message_count,
                life_state=copy.deepcopy(self._life_state),
                organs_online={name: organ.started for name, organ in self._organs.items()},
            )

    # ══════════════════════════════════════════════════
    #  广播
    # ══════════════════════════════════════════════════

    def _broadcast(self, state: MiyaSoulState) -> None:
        """将灵魂状态广播到所有器官"""
        for organ in self._organs_by_priority:
            try:
                organ.on_soul_state(copy.deepcopy(state))
            except Exception as e:
                logger.warning(f"Organ [{organ.name}] on_soul_state failed: {e}")

    # ══════════════════════════════════════════════════
    #  事件注入
    # ══════════════════════════════════════════════════

    def emit_event(self, event: MiyaEvent) -> MiyaEvent:
        """进入统一生命事件总线，并同步分发给所有器官。"""
        event = copy.deepcopy(event)
        with self._event_lock:
            if any(previous.event_id == event.event_id for previous in self._event_history):
                return event
            if self._event_journal is not None:
                try:
                    self.flush_event_journal()
                    if self._pending_journal_events:
                        raise OSError(self._persistence_error or "前序事件尚未落盘")
                    if not self._event_journal.append(event):
                        return event
                    self._persistence_error = ""
                except Exception as exc:
                    self._persistence_error = str(exc)
                    self._failed_writes += 1
                    self._failed_event_ids.append(event.event_id)
                    if len(self._pending_journal_events) >= 512:
                        self._pending_journal_events.popleft()
                        self._dropped_writes += 1
                    self._pending_journal_events.append(copy.deepcopy(event))
                    logger.warning("生命事件持久化失败 event_id=%s: %s", event.event_id, exc)
            with self._state_lock:
                if event.event_type == LifeEventType.USER_MESSAGE:
                    self._last_interaction = time.time()
                    self._message_count += 1
                    self._focus_scope = life_scope({**event.payload, "user_id": event.actor,
                                                    "platform": event.payload.get("platform") or event.source})
                    self._life_state.attention = {
                        "actor": event.actor,
                        "source": event.source,
                        "content": str(event.payload.get("message", ""))[:200],
                    }
                if event.event_type in (LifeEventType.ACTION_STARTED, LifeEventType.ACTION_RESULT):
                    action_id = event.payload.get("action_id")
                    if action_id:
                        self._life_state.open_loops = [
                            loop for loop in self._life_state.open_loops if loop["action_id"] != action_id
                        ]
                        if event.event_type == LifeEventType.ACTION_STARTED:
                            self._life_state.open_loops.append({
                                "action_id": action_id, "action": event.payload.get("action", ""),
                                "correlation_id": event.correlation_id,
                            })
                            self._life_state.open_loops = self._life_state.open_loops[-50:]
                    if event.event_type == LifeEventType.ACTION_RESULT:
                        self._life_state.last_action = {
                            "event_id": event.event_id, "action_id": action_id,
                            "action": event.payload.get("action", ""),
                            "result": copy.deepcopy(event.payload.get("result", {})),
                        }
                elif event.event_type == LifeEventType.MEMORY_RECALLED:
                    self._life_state.memory_focus = list(event.payload.get("event_ids", []))[-20:]
                intention_id = event.payload.get("intention_id")
                if intention_id:
                    record = project_intention(self._intentions.get(intention_id), event)
                    if record is not None:
                        self._intentions[intention_id] = record
                        if self._focus_scope is None:
                            self._focus_scope = life_scope(record)
                    closed = sorted(
                        (item for item in self._intentions.values() if item["status"] in TERMINAL_STATUSES),
                        key=lambda item: item["updated_at"], reverse=True,
                    )
                    for item in closed[200:]:
                        self._intentions.pop(item["intention_id"], None)
                self._event_history.append(event)
                self._life_state.last_event_at = event.timestamp
                self._life_state.recent_experience.append(event.to_dict())
                self._life_state.recent_experience = self._life_state.recent_experience[-20:]
                state = self._capture_soul_state()
                self._current_state = state

            if event.event_type == LifeEventType.USER_MESSAGE:
                self._wake_if_needed()

            organs = tuple(self._organs_by_priority)
            for organ in organs:
                try:
                    organ.on_life_event(copy.deepcopy(event), copy.deepcopy(state))
                except Exception as exc:
                    logger.warning(f"Organ [{organ.name}] on_life_event failed: {exc}")

            for organ in organs:
                try:
                    payload = copy.deepcopy(event.payload)
                    if event.event_type == LifeEventType.USER_MESSAGE:
                        organ.on_user_message(str(payload.get("message", "")), event.actor)
                    elif event.event_type == LifeEventType.ACTION_RESULT:
                        organ.on_action_result(str(payload.get("action", "")), payload.get("result", {}))
                    elif event.event_type in (LifeEventType.SYSTEM_EVENT, LifeEventType.PLATFORM_EVENT):
                        organ.on_system_event(str(payload.get("event", event.event_type)), payload.get("data"))
                    elif event.event_type == LifeEventType.LIFECYCLE_CHANGED:
                        organ.on_lifecycle_change(
                            LifecyclePhase(payload["old_phase"]), LifecyclePhase(payload["new_phase"])
                        )
                except Exception as exc:
                    logger.warning(f"Organ [{organ.name}] legacy event hook failed: {exc}")
        return copy.deepcopy(event)

    def handle_event(self, event: MiyaEvent) -> MiyaEvent:
        return self.emit_event(event)

    def inject_user_message(
        self, message: str, user_id: str = "", *, source: str = "user",
        correlation_id: str | None = None, context: dict | None = None,
    ) -> None:
        """注入用户消息事件"""
        event = MiyaEvent(
            event_type=LifeEventType.USER_MESSAGE,
            source=source,
            actor=str(user_id),
            payload={**(context or {}), "message": message, "user_id": user_id},
            importance=0.8,
        )
        if correlation_id:
            event.correlation_id = correlation_id
        self.emit_event(event)

    def inject_action_result(self, action: str, result: dict) -> None:
        """注入行动结果（回流到所有器官）"""
        self.emit_event(MiyaEvent(
            event_type=LifeEventType.ACTION_RESULT,
            source="action",
            payload={"action": action, "result": result},
            importance=0.7,
        ))

    def recall_action_experiences(
        self, *, user_id: str, platform: str, group_id: str = "", session_id: str = "",
        query: str = "", limit: int = 5,
    ) -> list[dict]:
        """只召回明确会话范围内的持久行动证据。"""
        if self._event_journal is None:
            return []
        return self._event_journal.recall_actions(
            user_id=user_id, platform=platform, group_id=group_id, session_id=session_id, query=query, limit=limit,
        )

    def set_emotion_provider(self, provider: Callable) -> None:
        with self._event_lock, self._state_lock:
            self._emotion_provider = provider
            self._current_state = self._capture_soul_state()

    def get_experience_mood(self, context: dict) -> dict:
        with self._state_lock:
            if self._emotion_provider is None:
                return {}
            return copy.deepcopy(self._emotion_provider(self.list_intentions(context, include_closed=True)))

    def flush_event_journal(self, *, limit: int = 32) -> bool:
        """按原顺序补写暂存事件，不再次分发钩子或执行行动。"""
        with self._event_lock:
            if self._event_journal is None:
                return False
            for _ in range(min(limit, len(self._pending_journal_events))):
                event = self._pending_journal_events[0]
                try:
                    self._event_journal.append(event)
                except Exception as exc:
                    self._persistence_error = str(exc)
                    return False
                self._pending_journal_events.popleft()
                if event.event_id in self._failed_event_ids:
                    self._failed_event_ids.remove(event.event_id)
            if not self._pending_journal_events:
                self._persistence_error = ""
                return True
            return False

    def list_intentions(self, context: dict, *, include_closed: bool = False) -> list[dict]:
        scope = life_scope(context)
        if not scope["user_id"] or scope["platform"] == "unknown":
            return []
        with self._state_lock:
            return copy.deepcopy(sorted(
                (item for item in self._intentions.values() if same_scope(item, scope)
                 and (include_closed or item["status"] not in TERMINAL_STATUSES)),
                key=lambda item: item["updated_at"], reverse=True,
            ))

    def manage_intention(self, operation: str, context: dict, *, intention_id: str = "", **values) -> dict:
        with self._event_lock:
            if self._phase == LifecyclePhase.SHUTDOWN:
                raise ValueError("脊柱已关闭")
            if operation == "remember":
                scope = life_scope(context)
                # 模型或调用方重试同一约定时返回原事项，不创建重复跟进。
                for item in self.list_intentions(scope):
                    if (item["title"] == str(values.get("title") or "").strip()[:200]
                            and item["expected_outcome"] == str(values.get("expected_outcome") or "").strip()[:300]
                            and item["action_name"] == str(values.get("action_name") or "").strip()[:100]
                            and item["completion_mode"] == values.get("completion_mode", "user_confirmation")
                            and item["follow_up"] == values.get("follow_up", False)
                            and item["correlation_id"] == str(context.get("request_id") or context.get("message_id") or "")):
                        item["persisted"] = self._event_journal is not None and not self._pending_journal_events
                        return item
                if len(self._intentions) >= 1200 or len(self.list_intentions(scope)) >= 50:
                    raise ValueError("未收尾事项过多，请先整理现有事项")
            current = self._intentions.get(intention_id)
            record = change_intention(current, operation, context, **values)
            event = MiyaEvent(
                LifeEventType.INTENTION_CHANGED, source=record["platform"], actor="miya",
                correlation_id=str(context.get("request_id") or record["correlation_id"]),
                payload={**life_scope(record), "intention_id": record["intention_id"],
                         "operation": operation, "intention": record}, importance=0.8,
            )
            self.emit_event(event)
            result = copy.deepcopy(self._intentions[record["intention_id"]])
            result["persisted"] = self._event_journal is not None and event.event_id not in self._failed_event_ids
            return result

    def match_action_intention(self, action: str, context: dict) -> str:
        """只关联本请求中显式指定该工具的事项，歧义时不猜测。"""
        correlation = str(context.get("request_id") or context.get("message_id") or "")
        if not correlation:
            return ""
        requested = str(context.get("intention_id") or "")
        candidates = [item for item in self.list_intentions(context)
                      if item["action_name"] == action and item["correlation_id"] == correlation
                      and item["status"] in {"active", "waiting"}
                      and (not requested or item["intention_id"] == requested)]
        return candidates[0]["intention_id"] if len(candidates) == 1 else ""

    def due_intentions(self, *, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        with self._state_lock:
            return copy.deepcopy(sorted(
                (item for item in self._intentions.values()
                 if item["follow_up"] and item["status"] in {"active", "waiting", "needs_confirmation"}
                 and item["followup_count"] < MAX_FOLLOWUPS
                 and item.get("next_followup_at") is not None and item["next_followup_at"] <= now),
                key=lambda item: item["next_followup_at"],
            )[:5])

    def inject_system_event(self, event: str, data: dict | None = None) -> None:
        """注入系统事件"""
        self.emit_event(MiyaEvent(
            event_type=LifeEventType.SYSTEM_EVENT,
            source="system",
            payload={"event": event, "data": data},
            importance=0.5,
        ))

    def inject_platform_event(self, event: dict) -> None:
        """保留平台广播原始字段，供所有器官共享连接状态变化。"""
        self.emit_event(MiyaEvent(
            event_type=LifeEventType.PLATFORM_EVENT,
            source=str(event.get("platform_id", "unknown")),
            payload=event,
            importance=0.6,
        ))

    # ══════════════════════════════════════════════════
    #  状态查询 (供外部使用)
    # ══════════════════════════════════════════════════

    def get_status(self) -> dict:
        """获取弥娅当前状态摘要"""
        with self._state_lock:
            state = self._current_state
            return {
                "version": self.VERSION,
                "phase": state.lifecycle_phase.value,
                "uptime_seconds": self.uptime_seconds,
                "tick_count": state.tick_count,
                "last_heartbeat_at": state.last_heartbeat_at,
                "message_count": state.message_count,
                "organs": list(self._organs.keys()),
                "organs_online": dict(state.organs_online),
                "proactive": state.proactive,
                "event_history_size": len(self._event_history),
                "life_state": asdict(state.life_state),
                "persistence": {
                    "enabled": self._event_journal is not None,
                    "error": self._persistence_error,
                    "failed_writes": self._failed_writes,
                    "pending_writes": len(self._pending_journal_events),
                    "dropped_writes": self._dropped_writes,
                },
            }


# ── 全局单例 ──

_spine_instance: MiyaSpine | None = None


def get_existing_spine() -> MiyaSpine | None:
    """查询已创建的脊柱，允许未启用脊柱的入口继续独立工作。"""
    return _spine_instance


def get_spine() -> MiyaSpine:
    """获取全局弥娅脊柱实例（懒初始化）"""
    global _spine_instance
    if _spine_instance is None:
        persistence_error = ""
        try:
            journal = LifeEventJournal(default_journal_path())
        except Exception as exc:
            logger.warning("生命事件日志初始化失败，继续使用内存状态: %s", exc)
            persistence_error = str(exc)
            journal = None
        _spine_instance = MiyaSpine(event_journal=journal)
        if persistence_error:
            _spine_instance._persistence_error = persistence_error
    return _spine_instance


def reset_spine() -> None:
    """重置脊柱实例（用于测试或重启）"""
    global _spine_instance
    _spine_instance = None
