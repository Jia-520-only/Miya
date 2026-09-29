"""统一主动性协调器。

各个器官只提交结构化事实，协调器负责决定是否值得打扰主人、人格化表达、
统一限频/去重以及最终发送。采集和状态落盘由来源器官继续负责，因此被跳过
的通知不会丢失事实。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger("Miya.ProactiveCoordinator")

# Two kinds of proactive traffic, budgeted apart.
#
# An EVENT is a bounded state change a tracker produced: he arrived, he started
# typing, the disk crossed a threshold. It happens a handful of times an hour at
# most, and each one is worth considering.
#
# A VOICE is something Miya decided to say: her queued observations from the
# camera, a soul impulse, a chat candidate. She can keep producing these, and she
# does.
#
# Sharing one per-source budget between them let a run of her own camera
# observations exhaust the camera's allowance, after which "佳刚回到电脑前" - one
# real event, once per arrival - was skipped exactly as if it were more small talk.
EVENT = "event"
VOICE = "voice"


class ProactiveCoordinator:
    """所有后台主动消息的统一决策与节流层。"""

    def __init__(self):
        self._ai_client = None
        self._personality = None
        self._send_callback: Optional[Callable[..., Awaitable[Any]]] = None
        self._enabled = True
        self._max_per_hour = 3
        # Per-source share of the hourly budget. Without it the loudest source
        # wins outright: a 45-minute patrol plus disk warnings were enough to
        # fill every slot, and the log filled up with
        # "小时总额度已满，跳过 key=camera:presence:returned" - Miya watched all
        # evening and never got to speak.
        self._max_per_source_per_hour = 3
        # Events get their own, separate allowance. See the EVENT/VOICE note above.
        self._max_events_per_source_per_hour = 4
        # One source's own back-to-back messages queue up instead of colliding
        # with the global cooldown; set below the global interval on purpose.
        self._same_source_interval = 90.0
        self._min_interval = 300.0
        self._quiet_hours = {23, 0, 1, 2, 3, 4, 5, 6, 7}
        self._quiet_hours_enabled = True
        self._default_target_id = "default"
        self._sent_at: deque[float] = deque()
        self._last_by_key: Dict[str, float] = {}
        self._last_by_source: Dict[str, float] = {}
        self._source_counts: Dict[str, deque[float]] = {}
        # Which source produced the most recent message: the cooldown it sets is
        # the one the next message has to respect.
        self._last_origin = ""
        self._fingerprints: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def configure(
        self,
        *,
        ai_client=None,
        personality=None,
        send_callback: Optional[Callable[..., Awaitable[Any]]] = None,
        config: Optional[dict] = None,
        default_target_id: str = "default",
    ) -> None:
        self._ai_client = ai_client or self._ai_client
        self._personality = personality or self._personality
        self._send_callback = send_callback or self._send_callback
        cfg = config or {}
        self._enabled = bool(cfg.get("enabled", self._enabled))
        self._max_per_hour = max(1, int(cfg.get("max_messages_per_hour", self._max_per_hour)))
        self._max_per_source_per_hour = max(
            1, min(self._max_per_hour,
                   int(cfg.get("max_messages_per_source_per_hour", self._max_per_source_per_hour)))
        )
        self._max_events_per_source_per_hour = max(
            1, min(self._max_per_hour,
                   int(cfg.get("max_events_per_source_per_hour", self._max_events_per_source_per_hour)))
        )
        self._same_source_interval = max(
            0.0, float(cfg.get("same_source_interval_seconds", self._same_source_interval))
        )
        self._min_interval = max(0.0, float(cfg.get("min_interval_seconds", self._min_interval)))
        self._quiet_hours = {int(h) for h in cfg.get("quiet_hours", self._quiet_hours)}
        self._quiet_hours_enabled = bool(cfg.get("quiet_hours_enabled", self._quiet_hours_enabled))
        if default_target_id and default_target_id != "default":
            self._default_target_id = str(default_target_id)

    def set_send_callback(self, callback: Callable[..., Awaitable[Any]]) -> None:
        self._send_callback = callback

    def _in_quiet_hours(self) -> bool:
        return self._quiet_hours_enabled and datetime.now().hour in self._quiet_hours

    def _prune(self, now: float) -> None:
        while self._sent_at and now - self._sent_at[0] >= 3600:
            self._sent_at.popleft()
        for store in (self._last_by_key, self._fingerprints, self._last_by_source):
            expired = [key for key, ts in store.items() if now - ts >= 3600]
            for key in expired:
                store.pop(key, None)
        for bucket, stamps in list(self._source_counts.items()):
            while stamps and now - stamps[0] >= 3600:
                stamps.popleft()
            if not stamps:
                self._source_counts.pop(bucket, None)

    def _claim(self, key: str, facts: str, urgency: str, source: str = "", kind: str = VOICE) -> bool:
        now = time.time()
        source = str(source or "unknown")
        kind = str(kind or VOICE)
        self._prune(now)
        if len(self._sent_at) >= self._max_per_hour:
            logger.info("[主动协调] 小时总额度已满，跳过 key=%s", key)
            return False
        # The gap that has to be respected is the one belonging to whoever spoke
        # last: a different source waits the full global interval, while the same
        # source is spaced out by its own, shorter one. Comparing against the
        # global interval regardless made one camera line silence the camera's own
        # presence event two minutes later - two different facts, queued up behind
        # each other for no reason.
        last_origin = self._last_origin
        last_at = self._sent_at[-1] if self._sent_at else 0.0
        gap = self._same_source_interval if last_origin == source else self._min_interval
        if last_at and (now - last_at) < gap and urgency not in {"high", "critical"}:
            logger.info("[主动协调] %s冷却中，跳过 key=%s",
                        "同来源" if last_origin == source else "全局", key)
            return False
        # Fairness: the loudest source must not eat the whole hour. One camera
        # presence event and one camera line are both worth more to Jia than a
        # third disk warning.
        #
        # Counted *per kind* as well, because those two are not the same thing: an
        # event is a bounded state change the trackers produced (an arrival, a
        # first "typing"), while a voice is something she decided to say and can
        # keep producing. Sharing one budget meant a run of her own observations
        # exhausted the camera's allowance and "佳刚回到电脑前" - one event, once
        # per arrival - was skipped as if it were more small talk.
        bucket = (source, kind)
        stamps = self._source_counts.setdefault(bucket, deque())
        allowance = self._max_events_per_source_per_hour if kind == EVENT else self._max_per_source_per_hour
        if len(stamps) >= allowance:
            logger.info("[主动协调] 来源 %s 的%s配额已满，跳过 key=%s",
                        source, "事件" if kind == EVENT else "发言", key)
            return False
        if now - self._last_by_key.get(key, 0) < self._min_interval:
            logger.info("[主动协调] 同类事件冷却中，跳过 key=%s", key)
            return False
        fingerprint = hashlib.sha256(facts.encode("utf-8")).hexdigest()
        if now - self._fingerprints.get(fingerprint, 0) < 3600:
            logger.info("[主动协调] 重复事实已去重，跳过 key=%s", key)
            return False
        self._sent_at.append(now)
        self._last_origin = source
        self._last_by_key[key] = now
        self._last_by_source[source] = now
        self._source_counts.setdefault(bucket, deque()).append(now)
        self._fingerprints[fingerprint] = now
        return True

    async def _decide_message(self, event: dict) -> Optional[str]:
        facts = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
        if not self._ai_client:
            return facts
        try:
            from core.ai_client import AIMessage
            from core.persona_prompt import compose_persona_system_prompt

            system = compose_persona_system_prompt(
                "你正在统一处理弥娅的后台主动事件。JSON 是唯一事实来源。"
                "请先判断现在是否值得给主人发送一条消息：没有实际价值、只是重复状态、"
                "或会打扰休息时回复 SKIP。值得通知时，只输出一条简短消息。"
                "不得补造 JSON 之外的事实；必须保留异常、失败、未恢复和资源数值。"
                "可以参考 candidate_message，但必须按当前人格重新表达。不要输出标题、分析、JSON、模块名或动作描述。",
                personality=self._personality,
                ai_client=self._ai_client,
            )
            response = await self._ai_client.chat(
                messages=[AIMessage(role="system", content=system), AIMessage(role="user", content=facts)],
                use_miya_prompt=False,
            )
            text = str(response or "").strip()
            if not text or text.upper().startswith("SKIP"):
                return None
            return text[:240]
        except Exception as exc:
            logger.debug("[主动协调] 人格化判断失败，回退事实: %s", exc)
            return facts

    async def submit_event(
        self,
        event: dict,
        *,
        key: str,
        target_id: str = "default",
        trigger_type: str = "proactive_event",
        chat_type: str = "private",
        platform: str = "terminal",
        force: bool = False,
        source: str = "",
    ) -> bool:
        """提交后台事件；返回是否实际发出消息。"""
        if not self._enabled:
            return False
        if target_id == "default":
            target_id = self._default_target_id
        # The event already carries which organ produced it; an explicit argument
        # only exists for callers that build a bare event.
        origin = str(source or event.get("source") or trigger_type or "unknown")
        urgency = str(event.get("urgency", "normal")).lower()
        if self._in_quiet_hours() and not force and urgency not in {"high", "critical"}:
            logger.info("[主动协调] 静默时段跳过 key=%s", key)
            return False
        facts = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
        # Ask the model *before* taking the lock. Deciding is a network round trip
        # of up to tens of seconds, and holding the one coordinator lock across it
        # stalled every other source - a single slow reply was enough to make the
        # whole proactive system look dead. Nothing here needs the lock: the
        # quota is only consumed by ``_claim``, which is still atomic.
        message = await self._decide_message(event)
        if not message:
            logger.info("[主动协调] AI 判断无需通知 key=%s", key)
            return False
        async with self._lock:
            if not self._claim(key, facts, urgency, origin, EVENT):
                return False
            if not self._send_callback:
                logger.warning("[主动协调] 发送出口未就绪，保留事件但不发送 key=%s", key)
                return False
            try:
                result = self._send_callback(message, target_id, chat_type, platform, trigger_type)
                if asyncio.iscoroutine(result):
                    result = await result
                logger.info("[主动协调] 已发送 source=%s key=%s", origin, key)
                return result is not False
            except Exception as exc:
                logger.warning("[主动协调] 统一发送失败 key=%s: %s", key, exc)
                return False

    async def submit_message(
        self,
        message: str,
        *,
        key: str,
        target_id: str = "default",
        chat_type: str = "private",
        platform: str = "terminal",
        trigger_type: str = "proactive_chat",
        source: str = "proactive_chat",
        kind: str = VOICE,
    ) -> bool:
        """接收已经经过主动聊天判断的消息，只统一执行总限频和发送。"""
        if not message or not self._enabled:
            return False
        if self._in_quiet_hours():
            return False
        event = {"source": source, "event": "chat_candidate", "message": message}
        facts = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        async with self._lock:
            if not self._send_callback or not self._claim(key, facts, "normal", source, kind):
                return False
            result = self._send_callback(message, target_id, chat_type, platform, trigger_type)
            if asyncio.iscoroutine(result):
                result = await result
            return result is not False


_coordinator: Optional[ProactiveCoordinator] = None


def get_proactive_coordinator() -> ProactiveCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = ProactiveCoordinator()
    return _coordinator
