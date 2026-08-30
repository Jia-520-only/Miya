"""
弥娅自检看护器官 (MiyaSelfCareOrgan)

挂在 MiyaSpine 脊柱上的"自我照顾"器官:
    1. 看护巡检 (默认 60s): 平台掉线/连续健康失败 → 自动重启(限流) → 主动告警；
       资源/定时任务异常 → 冷却告警；平台恢复 → 补一条恢复通知
    2. 每日简报 (默认 8/22 点): 全量体检 → 写入长期记忆 + 主动说给主人听
    3. 每次巡检更新 data/self_care_last.json，供 decision_hub 时间感知注入
       （弥娅随时"知道自己最近一次体检结果"）

配置: config/self_care.yaml → self_care
状态: data/self_care_state.json (跨重启保留告警/重启历史)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.miya_organ import MiyaOrgan
from core.self_check import (
    collect_report,
    get_platform_stats,
    summarize_last,
)

if TYPE_CHECKING:
    from core.miya_soul_state import MiyaSoulState

logger = logging.getLogger("Miya.SelfCare")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(_PROJECT_ROOT, "data", "self_care_state.json")
LAST_PATH = os.path.join(_PROJECT_ROOT, "data", "self_care_last.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "watch_interval": 120,           # 看护巡检间隔（秒）；巡检本身零 token，只是别太吵
    "auto_restart": True,            # 掉线时尝试自动重启
    "max_restarts_per_hour": 3,      # 每平台每小时重启上限（防风暴）
    "restart_verify_seconds": 10,    # 重启后验证在线的等待窗口
    "alert_cooldown_minutes": 30,    # 同一平台告警冷却
    "resource_alert_cooldown_minutes": 60,
    "disk_percent_threshold": 90,
    "memory_percent_threshold": 90,
    "cpu_percent_threshold": 95,
    "task_failure_rate_threshold": 0.3,
    "task_failure_min_count": 5,
    "health_failure_threshold": 3,   # consecutive_health_failures 达到即视为异常
    "notify_owner": True,
    "max_proactive_notifications_per_hour": 3,
    "proactive_notification_cooldown_minutes": 30,
    "store_memory": True,
    "daily_briefing": {
        "enabled": True,
        "hours": [8, 22],
        "quiet_hours": [0, 1, 2, 3, 4, 5, 6, 7],  # 静默时段只存记忆不发消息
    },
}

_SERIOUS = ("offline", "error")
_EXTERNAL_PLATFORM_IDS = frozenset({
    "aiocqhttp",
    "qqofficial",
    "weixin_official_account",
    "weixin_ilink",
    "lark",
})


class MiyaSelfCareOrgan(MiyaOrgan):
    """自检看护器官 — 掉线告警 / 自动重启 / 资源告警 / 每日简报 / 记忆归档"""

    def __init__(self):
        super().__init__(name="self_care_organ", priority=55)
        self._daemon = None
        self._ai_client = None
        self._personality = None
        self._coordinator = None
        self._stats_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None  # 测试注入
        self.state_path = STATE_PATH
        self.last_path = LAST_PATH
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._state: Dict[str, Any] = {
            "last_watch_at": "",
            "last_briefing_key": "",
            "platform_status": {},
            "incidents": {},
            "alert_times": {},
            "proactive_notifications": [],
            "proactive_keys": {},
            "restarts": {},
            "cycles": 0,
        }
        self._last_tick_check: float = 0.0
        self._running: bool = False
        self._load_config()
        self._load_state()

    # ── 绑定与配置 ──

    def bind_core(self, daemon=None, personality=None) -> None:
        """由 daemon 注册时注入（用于 restart_platform 与简报生成）"""
        self._daemon = daemon
        self._ai_client = getattr(getattr(daemon, "_miya", None), "ai_client", None)
        self._personality = personality or getattr(getattr(daemon, "_miya", None), "personality", None)

    def bind_proactive_coordinator(self, coordinator) -> None:
        """接入统一主动性协调器；未接入时保留嵌入/测试环境的兼容出口。"""
        self._coordinator = coordinator

    def bind_stats_fn(self, fn: Callable[[], List[Dict[str, Any]]]) -> None:
        """注入平台状态获取函数（测试用）"""
        self._stats_fn = fn

    def _load_config(self) -> None:
        try:
            import yaml

            cfg_path = os.path.join(_PROJECT_ROOT, "config", "self_care.yaml")
            if os.path.isfile(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    saved = yaml.safe_load(f) or {}
                saved = saved.get("self_care") or {}
                merged = {**DEFAULT_CONFIG, **{k: v for k, v in saved.items() if v is not None}}
                if isinstance(saved.get("daily_briefing"), dict):
                    merged["daily_briefing"] = {
                        **DEFAULT_CONFIG["daily_briefing"],
                        **saved["daily_briefing"],
                    }
                self._config = merged
        except Exception as exc:
            logger.debug(f"读取 self_care 配置失败，使用默认值: {exc}")

    def _load_state(self) -> None:
        try:
            if os.path.isfile(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._state.update(saved)
        except Exception as exc:
            logger.debug(f"读取看护状态失败: {exc}")

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug(f"保存看护状态失败: {exc}")

    def _write_last(self, report: Dict[str, Any]) -> None:
        """更新最新体检摘要（decision_hub 时间感知读取，弥娅每轮对话都看得到）"""
        try:
            summary = summarize_last(report)
            summary["resources"] = report.get("resources") or {}
            summary["tasks"] = report.get("tasks") or {}
            summary["recent_errors_count"] = len(report.get("recent_errors") or [])
            summary["platforms"] = report.get("platforms", {}).get("all", [])
            # 进行中的事故覆盖默认 note —— 让弥娅知道"谁掉线、我试过什么、搞不搞得定"
            incidents = self._state.get("incidents") or {}
            if incidents:
                notes = []
                for incident_id, inc in incidents.items():
                    name = inc.get("name", "?")
                    notes.append({
                        "platform_id": inc.get("platform_id", incident_id),
                        "platform_name": name,
                        "status": "offline",
                        "since": inc.get("since"),
                        "restart_attempted": bool(inc.get("restarted")),
                        "escalated": bool(inc.get("escalated")),
                    })
                summary["note"] = json.dumps(notes, ensure_ascii=False, separators=(",", ":"))
                summary["incidents_detail"] = notes
                summary["incidents"] = sorted(incidents.keys())
            os.makedirs(os.path.dirname(self.last_path), exist_ok=True)
            with open(self.last_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug(f"写入体检摘要失败: {exc}")

    # ── 生命周期 ──

    async def on_start(self) -> None:
        await super().on_start()
        # 新进程开始: 清掉上一进程遗留的未闭合事故/状态快照，避免"幽灵恢复"通知
        # （重启额度 restarts 与资源告警冷却保留——防风暴跨进程有效）
        leftover = len(self._state.get("incidents") or {})
        if leftover or self._state.get("platform_status"):
            self._state["incidents"] = {}
            self._state["platform_status"] = {}
            self._state["last_watch_at"] = ""
            self._save_state()
            if leftover:
                logger.info(f"[自检] 已清空上一进程遗留的 {leftover} 个未闭合事故（不发幽灵恢复通知）")
        if self._config.get("enabled"):
            logger.info(
                "自检看护器官已就绪 (watch=%ss, briefing=%s点)",
                self._config.get("watch_interval"),
                self._config.get("daily_briefing", {}).get("hours"),
            )
        else:
            logger.info("自检看护器官休眠 (未启用)")

    def on_soul_state(self, state: MiyaSoulState) -> None:
        """心跳线程回调: 只做时间判断，实际工作调度到事件循环"""
        if not self._config.get("enabled") or self._running:
            return
        now = time.time()
        if now - self._last_tick_check < 30:
            return
        self._last_tick_check = now

        current = datetime.now()
        hour = current.hour

        # 每日简报: 当天该小时还没做过
        briefing = self._config.get("daily_briefing") or {}
        if briefing.get("enabled"):
            hours = {int(h) for h in briefing.get("hours") or [8, 22]}
            key = f"{current.strftime('%Y-%m-%d')}:{hour}"
            if hour in hours and self._state.get("last_briefing_key") != key:
                self._schedule(self.run_daily_briefing(hour))
                return

        # 看护巡检（不受静默时段限制——掉线告警要紧）
        last_watch = self._state.get("last_watch_at") or ""
        try:
            elapsed = now - datetime.fromisoformat(last_watch).timestamp() if last_watch else now
        except (ValueError, OSError):
            elapsed = now
        if elapsed >= int(self._config.get("watch_interval", 60)):
            self._schedule(self.run_watch_cycle())

    def _schedule(self, coro) -> None:
        self._running = True
        try:
            if self._spine and getattr(self._spine, "_loop", None):
                asyncio.run_coroutine_threadsafe(coro, self._spine._loop)
            else:
                self._running = False
        except Exception as exc:
            self._running = False
            logger.warning(f"自检任务调度失败: {exc}")

    # ── 工具方法 ──

    def _fetch_stats(self) -> List[Dict[str, Any]]:
        if self._stats_fn is not None:
            return self._stats_fn()
        return get_platform_stats()

    def _notify(self, text: str) -> None:
        """主动说给主人听（脊柱主动消息通路）"""
        if not self._config.get("notify_owner", True):
            return
        try:
            sender = getattr(self._spine, "_proactive_sender", None) if self._spine else None
            if sender:
                sender(text)
                logger.info(f"[自检] 已主动通知: {text[:60]}")
                return
        except Exception as exc:
            logger.warning(f"[自检] 主动通知发送失败: {exc}")
        logger.info(f"[自检] (主动通道未就绪) {text[:120]}")

    async def _submit_owner_event(self, event: Dict[str, Any], key: str) -> bool:
        """将真实自检事件交给统一主动层；兼容未启动完整守护进程的场景。"""
        if not self._config.get("notify_owner", True):
            return False
        if self._coordinator is not None:
            try:
                return await self._coordinator.submit_event(
                    event,
                    key=key,
                    trigger_type="self_check",
                )
            except Exception as exc:
                logger.warning(f"[自检] 统一主动层提交失败: {exc}")
                return False
        message = await self._compose_owner_message(event, key)
        if message:
            self._notify(message)
            return True
        return False

    def _claim_proactive_notification(self, key: str) -> bool:
        """领取一条主动通知额度；巡检、状态文件和记忆不受此限制。"""
        if not self._config.get("notify_owner", True):
            return False
        now = time.time()
        timestamps = [
            float(ts)
            for ts in self._state.setdefault("proactive_notifications", [])
            if now - float(ts) < 3600
        ]
        self._state["proactive_notifications"] = timestamps
        limit = int(self._config.get("max_proactive_notifications_per_hour", 3))
        if len(timestamps) >= limit:
            logger.info("[自检] 主动通知受小时上限抑制: key=%s", key)
            return False

        last_by_key = self._state.setdefault("proactive_keys", {})
        last = last_by_key.get(key)
        cooldown = float(self._config.get("proactive_notification_cooldown_minutes", 30)) * 60
        if last and now - float(last) < cooldown:
            logger.info("[自检] 主动通知处于同类冷却: key=%s", key)
            return False

        timestamps.append(now)
        last_by_key[key] = now
        return True

    async def _compose_owner_message(self, event: Dict[str, Any], notification_key: str = "") -> str:
        """只把真实事件交给当前人格表达；无模型时原样返回结构化事实。"""
        if not self._claim_proactive_notification(notification_key or str(event.get("event") or "self_check")):
            return ""
        facts = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
        if self._ai_client is None:
            return facts
        try:
            from core.ai_client import AIMessage
            from core.persona_prompt import compose_persona_system_prompt

            system = compose_persona_system_prompt(
                "你正在给主人发送系统自检事件。"
                "下面的 JSON 是唯一事实来源。只陈述其中已有字段，不要补猜测、不要把未知状态说成成功。"
                "如果事件包含 restart_attempted、restart_succeeded、external_dependency 或 error，必须准确保留。"
                "只输出最终消息，不要标题、分析、JSON、括号动作描述或模块名。"
                "简短自然，语气必须继承当前人格。",
                personality=self._personality,
                ai_client=self._ai_client,
            )
            self._ai_client.set_tool_registry(lambda: [])
            self._ai_client.set_tool_context({})
            try:
                response = await self._ai_client.chat(
                    messages=[
                        AIMessage(role="system", content=system),
                        AIMessage(role="user", content=facts),
                    ],
                    use_miya_prompt=False,
                )
            finally:
                self._ai_client.set_tool_registry(lambda: [])
                self._ai_client.set_tool_context({})
            text = str(response or "").strip()
            if text and not text.upper().startswith("SKIP"):
                return text[:200]
        except Exception as exc:
            logger.debug(f"自检消息人格化生成失败，返回原始事实: {exc}")
        return facts

    def _alert_allowed(self, key: str, cooldown_minutes: float) -> bool:
        """同类告警冷却（参考 proactive_chat 的 trigger_type_cooldown 模式）"""
        times = self._state.setdefault("alert_times", {})
        last = times.get(key)
        if last and time.time() - float(last) < cooldown_minutes * 60:
            return False
        times[key] = time.time()
        return True

    def _restart_allowed(self, pid: str) -> bool:
        history = [t for t in self._state.get("restarts", {}).get(pid, []) if time.time() - t < 3600]
        self._state.setdefault("restarts", {})[pid] = history
        return len(history) < int(self._config.get("max_restarts_per_hour", 3))

    def _record_restart(self, pid: str) -> None:
        self._state.setdefault("restarts", {}).setdefault(pid, []).append(time.time())

    async def _store_memory(self, content: str, kind: str) -> None:
        """把检查结果写进弥娅的长期记忆（tags 供召回过滤）"""
        if not self._config.get("store_memory", True):
            return
        try:
            from memory import MemoryLevel, MemorySource, get_memory_bus

            bus = await get_memory_bus()
            await bus.store(
                content=content,
                user_id="global",
                level=MemoryLevel.LONG_TERM,
                priority=0.55,
                tags=["系统记忆", "自检报告"],
                source=MemorySource.SYSTEM,
                metadata={"type": "self_check", "kind": kind},
            )
        except Exception as exc:
            logger.debug(f"自检记忆写入失败: {exc}")

    async def _verify_platform_online(self, pid: str) -> bool:
        deadline = time.time() + int(self._config.get("restart_verify_seconds", 10))
        while time.time() < deadline:
            await asyncio.sleep(2)
            for st in self._fetch_stats():
                if st.get("platform_id") == pid:
                    if st.get("status") == "online":
                        return True
                    break
        return False

    # ── 看护巡检 ──

    async def run_watch_cycle(self) -> Dict[str, Any]:
        """一次看护巡检: 平台事件 → 资源/任务检查 → 更新摘要"""
        started = datetime.now().isoformat(timespec="seconds")
        result: Dict[str, Any] = {"started_at": started, "alerts": []}
        try:
            report = await collect_report(platform_stats=self._fetch_stats())
            await self._check_platforms(report)
            await self._check_resources(report)
            await self._check_tasks(report)
            self._write_last(report)
            self._state.update({
                "last_watch_at": started,
                "cycles": int(self._state.get("cycles", 0)) + 1,
            })
            self._save_state()
            result["success"] = True
        except Exception as exc:
            logger.warning(f"看护巡检异常: {exc}")
            result["success"] = False
            result["error"] = str(exc)
        finally:
            self._running = False
        return result

    async def _check_platforms(self, report: Dict[str, Any]) -> None:
        threshold = int(self._config.get("health_failure_threshold", 3))
        incidents = self._state.setdefault("incidents", {})
        prev_status = self._state.setdefault("platform_status", {})

        for st in report.get("platforms", {}).get("all", []):
            pid = st.get("platform_id", "?")
            if prev_status.get(pid) is None and st.get("status") in ("connecting", "reconnecting"):
                # 首轮快照里的瞬时连接态不算事故
                continue
            cf = int(st.get("consecutive_health_failures") or 0)
            abnormal = st.get("status") in _SERIOUS or cf >= threshold
            was_incident = pid in incidents

            if abnormal and not was_incident:
                await self._handle_platform_incident(st)
            elif abnormal and was_incident:
                await self._maybe_escalate(st, incidents[pid])
            elif not abnormal and was_incident:
                await self._handle_platform_recovered(st)
            prev_status[pid] = st.get("status", "?")

    async def _maybe_escalate(self, st: Dict[str, Any], incident: Dict[str, Any]) -> None:
        """持续掉线 + 重启额度耗尽 → 一次性升级求助（不受告警冷却限制，只发一次）"""
        if incident.get("escalated"):
            return
        pid = st.get("platform_id", "?")
        if self._config.get("auto_restart") and self._restart_allowed(pid):
            return  # 还有重启额度，继续自己扛
        incident["escalated"] = True
        name = st.get("platform_name") or pid
        now_iso = datetime.now().strftime("%m-%d %H:%M")
        event = {
            "source": "self_check",
            "event": "platform_escalated",
            "urgency": "critical",
            "timestamp": now_iso,
            "platform_id": pid,
            "platform_name": name,
            "status": st.get("status"),
            "reason": st.get("last_error"),
            "consecutive_health_failures": st.get("consecutive_health_failures", 0),
            "restart_attempted": bool(incident.get("restarted")),
            "restart_budget_available": False,
            "external_dependency": pid in _EXTERNAL_PLATFORM_IDS,
            "action": "owner_required",
        }
        await self._submit_owner_event(event, f"platform_escalated:{pid}")
        await self._store_memory(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="escalation"
        )
        logger.warning(f"[自检] {name} 持续掉线，已升级求助主人")

    async def _handle_platform_incident(self, st: Dict[str, Any]) -> None:
        pid = st.get("platform_id", "?")
        name = st.get("platform_name") or pid
        cf = int(st.get("consecutive_health_failures") or 0)
        reason = st.get("last_error") or None
        now_iso = datetime.now().strftime("%m-%d %H:%M")

        restarted = False
        restart_succeeded = None
        restart_error = None
        restart_budget_available = self._restart_allowed(pid)
        if self._config.get("auto_restart") and self._restart_allowed(pid):
            if self._daemon is not None:
                restarted = True
                self._record_restart(pid)
                try:
                    await self._daemon.restart_platform(pid)
                except Exception as exc:
                    restart_error = str(exc)[:160]
                    logger.warning(f"[自检] 重启 {pid} 异常: {exc}")
                restart_succeeded = await self._verify_platform_online(pid)
            else:
                restart_error = "daemon_unavailable"
        elif self._config.get("auto_restart"):
            restart_error = "restart_budget_exhausted"

        # 事故一律先记录；是否真恢复由后续巡检判定（避免连接抖动造成误报）
        incidents = self._state.setdefault("incidents", {})
        incidents[pid] = {
            "platform_id": pid,
            "since": now_iso,
            "since_ts": time.time(),
            "name": name,
            "reason": str(reason)[:120] if reason else None,
            "restarted": restarted,
            "external": pid in _EXTERNAL_PLATFORM_IDS,
            "escalated": False,
        }

        if self._alert_allowed(f"platform:{pid}", int(self._config.get("alert_cooldown_minutes", 30))):
            event = {
                "source": "self_check",
                "event": "platform_offline",
                "urgency": "high",
                "timestamp": now_iso,
                "platform_id": pid,
                "platform_name": name,
                "status": st.get("status"),
                "reason": str(reason)[:120] if reason else None,
                "consecutive_health_failures": cf,
                "restart_attempted": restarted,
                "restart_succeeded": restart_succeeded,
                "restart_error": restart_error,
                "restart_budget_available": restart_budget_available,
                "external_dependency": pid in _EXTERNAL_PLATFORM_IDS,
                "action": "monitor",
            }
            await self._submit_owner_event(event, f"platform_offline:{pid}")
        # 记忆以弥娅第一人称视角落档——召回时是她自己的经历，不是冷冰冰的日志
        mem = json.dumps({
            "source": "self_check",
            "event": "platform_offline",
            "timestamp": now_iso,
            "platform_id": pid,
            "platform_name": name,
            "status": st.get("status"),
            "reason": str(reason)[:120] if reason else None,
            "consecutive_health_failures": cf,
            "restart_attempted": restarted,
            "restart_succeeded": restart_succeeded,
            "restart_error": restart_error,
            "restart_budget_available": restart_budget_available,
            "external_dependency": pid in _EXTERNAL_PLATFORM_IDS,
        }, ensure_ascii=False, separators=(",", ":"))
        await self._store_memory(mem, kind="incident")
        logger.warning("[自检] platform_offline event=%s", pid)

    async def _handle_platform_recovered(self, st: Dict[str, Any]) -> None:
        pid = st.get("platform_id", "?")
        name = st.get("platform_name") or pid
        incident = self._state.get("incidents", {}).pop(pid, None)
        since = (incident or {}).get("since", "")
        since_ts = float((incident or {}).get("since_ts") or 0)
        now_iso = datetime.now().strftime("%m-%d %H:%M")
        if since_ts:
            mins = max(1, round((time.time() - since_ts) / 60))
            duration_seconds = mins * 60
        elif since:
            duration_seconds = None
        else:
            duration_seconds = None
        event = {
            "source": "self_check",
            "event": "platform_recovered",
            "urgency": "normal",
            "timestamp": now_iso,
            "platform_id": pid,
            "platform_name": name,
            "status": st.get("status"),
            "previous_status": "offline",
            "incident_since": since,
            "incident_duration_seconds": duration_seconds,
            "action": "notify_owner",
        }
        await self._submit_owner_event(event, f"platform_recovered:{pid}")
        await self._store_memory(
            json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="recovery"
        )
        logger.info("[自检] platform_recovered event=%s", pid)

    async def _check_resources(self, report: Dict[str, Any]) -> None:
        res = report.get("resources", {})
        cooldown = int(self._config.get("resource_alert_cooldown_minutes", 60))

        checks = [
            ("memory", "memory_percent", "memory_percent_threshold", "内存"),
            ("cpu", "cpu_percent", "cpu_percent_threshold", "CPU"),
        ]
        for key, metric, threshold_key, label in checks:
            value = res.get(metric)
            if value is None:
                continue
            threshold = float(self._config.get(threshold_key, 90))
            if value > threshold and self._alert_allowed(f"resource:{key}", cooldown):
                event = {
                    "source": "self_check",
                    "event": "resource_threshold_exceeded",
                    "timestamp": datetime.now().strftime("%m-%d %H:%M"),
                    "resource": key,
                    "label": label,
                    "value": value,
                    "threshold": threshold,
                    "action": "notify_owner",
                }
                await self._submit_owner_event(event, f"resource:{key}")
                await self._store_memory(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="resource_alert"
                )

        # 磁盘按盘符分别判断，避免把某个挂载点误称为整台机器的磁盘。
        disks = res.get("disks") or []
        if disks:
            threshold = float(self._config.get("disk_percent_threshold", 90))
            for disk in disks:
                value = disk.get("percent")
                if value is None or value <= threshold:
                    continue
                drive = str(disk.get("drive") or disk.get("mountpoint") or "unknown")
                key = f"disk:{drive}"
                if not self._alert_allowed(key, cooldown):
                    continue
                event = {
                    "source": "self_check",
                    "event": "resource_threshold_exceeded",
                    "timestamp": datetime.now().strftime("%m-%d %H:%M"),
                    "resource": "disk",
                    "drive": drive,
                    "mountpoint": disk.get("mountpoint"),
                    "label": f"磁盘 {drive}",
                    "value": value,
                    "used_gb": disk.get("used_gb"),
                    "total_gb": disk.get("total_gb"),
                    "free_gb": disk.get("free_gb"),
                    "threshold": threshold,
                    "action": "inspect_storage",
                }
                await self._submit_owner_event(event, key)
                await self._store_memory(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="resource_alert"
                )
        elif res.get("disk_percent") is not None:
            # 兼容旧采集器或测试注入的单一磁盘字段。
            value = res.get("disk_percent")
            threshold = float(self._config.get("disk_percent_threshold", 90))
            if value > threshold and self._alert_allowed("resource:disk", cooldown):
                event = {
                    "source": "self_check",
                    "event": "resource_threshold_exceeded",
                    "timestamp": datetime.now().strftime("%m-%d %H:%M"),
                    "resource": "disk",
                    "label": "磁盘（未标明盘符）",
                    "value": value,
                    "used_gb": res.get("disk_used_gb"),
                    "total_gb": res.get("disk_total_gb"),
                    "free_gb": res.get("disk_free_gb"),
                    "threshold": threshold,
                    "action": "inspect_storage",
                }
                await self._submit_owner_event(event, "resource:disk")
                await self._store_memory(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="resource_alert"
                )

    async def _check_tasks(self, report: Dict[str, Any]) -> None:
        tasks = report.get("tasks") or {}
        failed = int(tasks.get("failed", 0))
        rate = float(tasks.get("failure_rate", 0))
        if (
            failed >= int(self._config.get("task_failure_min_count", 5))
            and rate > float(self._config.get("task_failure_rate_threshold", 0.3))
            and self._alert_allowed("resource:tasks", int(self._config.get("resource_alert_cooldown_minutes", 60)))
        ):
            event = {
                "source": "self_check",
                "event": "scheduled_tasks_failed",
                "timestamp": datetime.now().strftime("%m-%d %H:%M"),
                "completed": int(tasks.get("completed", 0)),
                "failed": failed,
                "failure_rate": rate,
                "threshold": float(self._config.get("task_failure_rate_threshold", 0.3)),
                "action": "inspect_tasks",
            }
            await self._submit_owner_event(event, "scheduled_tasks_failed")
            await self._store_memory(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")), kind="task_alert"
            )

    # ── 每日简报 ──

    @staticmethod
    def _briefing_facts(report: Dict[str, Any]) -> str:
        """结构化体检事实（记忆归档与简报生成的唯一数据源）。"""
        pl = report.get("platforms", {})
        res = report.get("resources", {})
        tasks = report.get("tasks") or {}
        return json.dumps({
            "platforms_online": pl.get("online", 0),
            "platforms_total": pl.get("total", 0),
            "abnormal_platforms": pl.get("abnormal", []),
            "resources": res,
            "tasks": tasks,
            "recent_errors_count": len(report.get("recent_errors") or []),
        }, ensure_ascii=False, separators=(",", ":"), default=str)

    async def _compose_briefing_message(self, greeting: str, facts: str) -> str:
        """让弥娅用当前人格表达体检事实；失败时返回原始事实。"""
        if self._ai_client is not None:
            try:
                from core.ai_client import AIMessage

                system = (
                    "你正在给主人发送每日系统自检简报。下面的 JSON 是唯一事实来源。"
                    "只陈述已有字段，不要编造、不要把未知状态说成成功。"
                    "60 字以内，只输出最终消息，不要标题、分析、JSON、括号动作描述或模块名。"
                )
                from core.persona_prompt import compose_persona_system_prompt

                system = compose_persona_system_prompt(
                    system,
                    personality=self._personality,
                    ai_client=self._ai_client,
                )
                self._ai_client.set_tool_registry(lambda: [])
                self._ai_client.set_tool_context({})
                try:
                    response = await self._ai_client.chat(
                        messages=[
                            AIMessage(role="system", content=system),
                            AIMessage(role="user", content=f"{greeting}体检事实：{facts}"),
                        ],
                        use_miya_prompt=False,
                    )
                finally:
                    self._ai_client.set_tool_registry(lambda: [])
                    self._ai_client.set_tool_context({})
                text = str(response or "").strip()
                if text and not text.upper().startswith("SKIP"):
                    return text[:200]
            except Exception as exc:
                logger.debug(f"简报 LLM 生成失败，返回原始事实: {exc}")
        return facts

    async def run_daily_briefing(self, hour: int) -> Dict[str, Any]:
        """每日体检简报: 事实一行入记忆 → 弥娅自己的话说给主人听（非静默时段）"""
        result: Dict[str, Any] = {}
        try:
            current = datetime.now()
            key = f"{current.strftime('%Y-%m-%d')}:{hour}"
            self._state["last_briefing_key"] = key

            report = await collect_report(platform_stats=self._fetch_stats())
            facts = self._briefing_facts(report)
            greeting = "早安" if hour < 12 else "晚安"
            briefing_facts = json.loads(facts)
            briefing_facts["greeting"] = greeting
            facts = json.dumps(briefing_facts, ensure_ascii=False, separators=(",", ":"))
            self._write_last(report)
            # 记忆只归档一行事实，避免长期积累撑爆召回上下文
            await self._store_memory(
                facts, kind="daily_briefing"
            )

            briefing = self._config.get("daily_briefing") or {}
            quiet = {int(h) for h in briefing.get("quiet_hours") or []}
            sent = False
            message = facts
            if hour not in quiet:
                if self._coordinator is not None:
                    event = {
                        "source": "self_check",
                        "event": "daily_briefing",
                        "timestamp": current.isoformat(timespec="seconds"),
                        "greeting": greeting,
                        "facts": briefing_facts,
                    }
                    sent = await self._submit_owner_event(event, f"daily_briefing:{key}")
                elif self._claim_proactive_notification(f"daily_briefing:{key}"):
                    message = await self._compose_briefing_message(greeting, facts)
                    self._notify(message)
                    sent = True
            self._save_state()
            result = {"success": True, "sent": sent, "message": message}
            logger.info(f"[自检] {greeting}简报完成 (已发送: {sent})")
        except Exception as exc:
            logger.warning(f"每日简报异常: {exc}")
            result = {"success": False, "error": str(exc)}
        finally:
            self._running = False
        return result
