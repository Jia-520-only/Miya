"""统一主动性协调器。

各个器官只提交结构化事实，协调器负责决定是否值得打扰主人、人格化表达、
统一限频/去重以及最终发送。采集和状态落盘由来源器官继续负责，因此被跳过
的通知不会丢失事实。
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

from core.proactive_delivery import DeliveryResult, delivery_accepted

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
        self._last_kind = VOICE
        self._fingerprints: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._reservations: dict[str, dict] = {}
        self._send_timeout = 30.0
        self._decision_timeout = 30.0
        self._send_attempts = 1
        self._context_provider = None

    def set_context_provider(self, provider) -> None:
        self._context_provider = provider

    def configure(
        self, *, ai_client=None, personality=None, send_callback=None,
        config: Optional[dict] = None, default_target_id: str = "default",
    ) -> None:
        """完整验证后原子应用策略，非法配置不会污染已有策略。"""
        import math

        cfg = config or {}
        for key in ("max_messages_per_hour", "max_messages_per_source_per_hour", "max_events_per_source_per_hour",
                    "min_interval_seconds", "same_source_interval_seconds", "send_timeout_seconds",
                    "decision_timeout_seconds", "send_attempts"):
            if key in cfg:
                value = cfg[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"主动协调配置 {key} 必须是非负有限数值")
        hours = cfg.get("quiet_hours", list(self._quiet_hours))
        if not isinstance(hours, list) or any(type(hour) is not int or not 0 <= hour <= 23 for hour in hours):
            raise ValueError("静默时段必须是 0 到 23 的整数列表")
        staged = object.__new__(type(self))
        staged.__dict__ = self.__dict__.copy()
        staged._apply_configuration(ai_client=ai_client, personality=personality, send_callback=send_callback,
                                    config=cfg, default_target_id=default_target_id)
        self.__dict__.update(staged.__dict__)

    def _apply_configuration(
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
        self._send_timeout = max(0.01, float(cfg.get("send_timeout_seconds", self._send_timeout)))
        self._decision_timeout = max(0.01, float(cfg.get("decision_timeout_seconds", self._decision_timeout)))
        self._send_attempts = max(1, min(3, int(cfg.get("send_attempts", self._send_attempts))))
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

    def _claim(self, key: str, facts: str, urgency: str, source: str = "", kind: str = VOICE) -> Optional[str]:
        now = time.time()
        source = str(source or "unknown")
        kind = str(kind or VOICE)
        self._prune(now)
        if len(self._sent_at) + len(self._reservations) >= self._max_per_hour:
            logger.info("[主动协调] 小时总额度已满，跳过 key=%s", key)
            return False
        # The gap that has to be respected is the one belonging to whoever spoke
        # last: a different source waits the full global interval, while the same
        # source is spaced out by its own, shorter one. Comparing against the
        # global interval regardless made one camera line silence the camera's own
        # presence event two minutes later - two different facts, queued up behind
        # each other for no reason.
        last_origin = self._last_origin
        last_kind = self._last_kind
        last_at = self._sent_at[-1] if self._sent_at else 0.0
        if self._reservations:
            latest = max(self._reservations.values(), key=lambda item: item["at"])
            if latest["at"] >= last_at:
                last_at, last_origin, last_kind = latest["at"], latest["source"], latest["kind"]
        # A real state-change event must not wait behind a conversational camera
        # observation from the same source. Events still retain their own key,
        # fingerprint, and hourly limits, and two consecutive events still use
        # the normal same-source interval.
        event_after_voice = kind == EVENT and last_origin == source and last_kind != EVENT
        gap = 0.0 if event_after_voice else (
            self._same_source_interval if last_origin == source else self._min_interval
        )
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
        reserved_count = sum(
            item["source"] == source and item["kind"] == kind for item in self._reservations.values()
        )
        if len(stamps) + reserved_count >= allowance:
            logger.info("[主动协调] 来源 %s 的%s配额已满，跳过 key=%s",
                        source, "事件" if kind == EVENT else "发言", key)
            return False
        key_window = 3600 if key.startswith(("camera:presence:", "camera:voice:")) else self._min_interval
        if now - self._last_by_key.get(key, 0) < key_window:
            logger.info("[主动协调] 同类事件冷却中，跳过 key=%s", key)
            return False
        fingerprint = hashlib.sha256(facts.encode("utf-8")).hexdigest()
        if any(item["key"] == key or item["fingerprint"] == fingerprint for item in self._reservations.values()):
            return None
        if now - self._fingerprints.get(fingerprint, 0) < 3600:
            logger.info("[主动协调] 重复事实已去重，跳过 key=%s", key)
            return False
        token = uuid4().hex
        self._reservations[token] = {
            "at": now, "key": key, "fingerprint": fingerprint, "source": source, "kind": kind,
        }
        return token

    async def _send_reserved(self, token: str, message: str, target_id: str,
                             chat_type: str, platform: str, trigger_type: str, detailed: bool = False):
        accepted = False
        try:
            callback = self._send_callback
            if callback is None:
                return False
            try:
                parameters = inspect.signature(callback).parameters
                accepts_id = "delivery_id" in parameters or any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
                )
            except (TypeError, ValueError):
                accepts_id = False
            for attempt in range(self._send_attempts):
                kwargs = {"delivery_id": token} if accepts_id else {}
                result = callback(message, target_id, chat_type, platform, trigger_type, **kwargs)
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout=self._send_timeout)
                accepted = delivery_accepted(result)
                if accepted:
                    logger.info("[主动协调] 投递已接受 status=%s delivery_id=%s",
                                result.status if isinstance(result, DeliveryResult) else "sent", token)
                    return result if detailed and isinstance(result, DeliveryResult) else (
                        DeliveryResult("sent", token) if detailed else True
                    )
                if isinstance(result, DeliveryResult) and result.status == "rejected":
                    break
                if attempt + 1 < self._send_attempts:
                    await asyncio.sleep(0.1)
            return False
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[主动协调] 投递失败 delivery_id=%s: %s", token, exc)
            return False
        finally:
            async with self._lock:
                reservation = self._reservations.pop(token, None)
                if accepted and reservation:
                    now = time.time()
                    source, kind = reservation["source"], reservation["kind"]
                    self._sent_at.append(now)
                    self._last_origin, self._last_kind = source, kind
                    self._last_by_key[reservation["key"]] = now
                    self._last_by_source[source] = now
                    self._source_counts.setdefault((source, kind), deque()).append(now)
                    self._fingerprints[reservation["fingerprint"]] = now

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
                "摄像头在场事件只能说明检测到或没检测到人脸，不能据此推断去了厕所、微信、喝水或其它地点。"
                "JSON 中的消息发送平台只是投递路线，不是人的现实位置；没有物理位置证据就不要写具体去向。"
                "memory_context 和 JSON 中标明的旧事、近期对话都只是背景，不能当成当前摄像头画面；"
                "当前事实没有提到的杯子、食物、姿势、地点、时间长度或动作，不得写进消息。"
                "可以参考 candidate_message，但必须按当前人格重新表达。不要输出标题、分析、JSON、模块名或动作描述。",
                personality=self._personality,
                ai_client=self._ai_client,
            )
            response = await asyncio.wait_for(self._ai_client.chat(
                messages=[AIMessage(role="system", content=system), AIMessage(role="user", content=facts)],
                use_miya_prompt=False,
                tools=[], tool_choice="none",
            ), timeout=self._decision_timeout)
            text = str(response or "").strip()
            if not text or text.upper().startswith("SKIP"):
                return None
            return text[:240]
        except Exception as exc:
            logger.warning("[主动协调] 人格化判断失败，保留事件等待重试: %s", exc)
            return None

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
        if not self._enabled or not self._send_callback:
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
        decision_event = dict(event)
        if self._context_provider:
            try:
                context = self._context_provider(target_id, chat_type, platform, event)
                if inspect.isawaitable(context):
                    context = await asyncio.wait_for(context, timeout=6)
                if context:
                    decision_event["memory_context"] = str(context)[:8000]
            except Exception as exc:
                logger.warning("[主动协调] 上下文读取失败，继续处理真实事件: %s", exc)
        message = await self._decide_message(decision_event)
        if not message:
            logger.info("[主动协调] AI 判断无需通知 key=%s", key)
            return False
        async with self._lock:
            if not self._enabled or (self._in_quiet_hours() and not force and urgency not in {"high", "critical"}):
                return False
            token = self._claim(key, facts, urgency, origin, EVENT)
        if not token:
            return False
        return await self._send_reserved(token, message, target_id, chat_type, platform, trigger_type)

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
        detailed: bool = False,
    ) -> bool:
        """接收已经经过主动聊天判断的消息，只统一执行总限频和发送。"""
        if not message or not self._enabled:
            return False
        if self._in_quiet_hours():
            return False
        if target_id == "default":
            target_id = self._default_target_id
        event = {"source": source, "event": "chat_candidate", "message": message,
                 "target_id": str(target_id), "chat_type": chat_type, "platform": platform}
        facts = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        async with self._lock:
            if not self._send_callback or not self._enabled or self._in_quiet_hours():
                return False
            token = self._claim(key, facts, "normal", source, kind)
        if not token:
            return False
        return await self._send_reserved(token, message, target_id, chat_type, platform, trigger_type, detailed)


_coordinator: Optional[ProactiveCoordinator] = None


def get_proactive_coordinator() -> ProactiveCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = ProactiveCoordinator()
    return _coordinator
