"""Camera observations joining Miya's existing proactive system.

The camera used to be a system of its own: its own trackers, its own cooldowns,
its own duplicate-checking, and triggers that lived inside the proactive-chat
poll - which only runs for targets that have chatted recently. The result was
that Miya watched all evening, formed clear impressions ("he left the desk"),
and said nothing, because nothing connected her eyes to her voice.

This module makes the camera a normal contributor to the machinery that already
exists, alongside Earth-Online, self-care and the soul:

* **memory** - a meaningful observation is written to her long-term memory, using
  the same ``MemoryBus.store`` pattern the self-care organ established, with the
  ``emotional_tone`` / ``significance`` / ``location`` fields that exist for
  exactly this;
* **memory read back** - before she speaks, relevant memories are recalled, so
  the decision is not made in a vacuum;
* **persona and form** - inherited for free, because the coordinator composes
  ``compose_persona_system_prompt``;
* **mood** - the live soul state is attached, since the persona prompt only
  carries the static form definition, not how she feels right now;
* **context** - what she saw most recently, and what the conversation was about;
* **throttling and delivery** - the coordinator's, not a second copy of it.

Per Jia's decision, she opens her mouth for clear events (coming back, leaving),
not for every reading.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("screen_vision.proactive")

# How often the bridge looks for something worth submitting. This is independent
# of the observation interval: a transition can happen at any time.
BRIDGE_INTERVAL_SECONDS = 20.0
# A transition older than this is stale history, not something to speak about.
TRANSITION_MAX_AGE_SECONDS = 150.0
# Memory: only meaningful observations are kept, and they are kept rarely enough
# that they remain memorable. Every-30-seconds would be 2880 entries a day.
MEMORY_MIN_INTERVAL_SECONDS = 1800.0
MEMORY_PRIORITY = 0.62
# Which presence transitions are worth her voice, per Jia's choice.
SPEAK_ON_PRESENCE = {"returned", "left"}

_TONE_BY_ACTIVITY = {
    "typing": "专注",
    "phone": "分心",
    "drink": "休息",
    "stretch": "放松",
    "lean_back": "倦怠",
    "walk": "离开",
    "sit_down": "安定",
    "stand_up": "起身",
}

_LOCATION_TEXT = "电脑前"

# Plain sentences for the changes worth speaking about, keyed by the tracker's
# own transition names.
_PRESENCE_CHANGE_TEXT = {
    "returned": "佳刚回到电脑前",
    "left": "佳离开了电脑前",
    "away": "佳可能离开了座位",
}


def _owner_target_id() -> str:
    """The person Miya would speak to, in the identity system's canonical form."""
    try:
        from memory.identity_resolver import get_identity_resolver

        owner = get_identity_resolver().owner_canonical_id
        if owner:
            return str(owner)
    except Exception:
        logger.debug("[CameraProactive] 读取所有者身份失败", exc_info=True)
    return ""


async def remember_observation(
    *,
    summary: str,
    activity: str = "",
    mood: str = "",
    significance: float = 0.6,
    tags: list[str] | None = None,
    now: float | None = None,
) -> bool:
    """Write one meaningful observation into Miya's long-term memory.

    Same shape as the self-care organ's ``_store_memory``, because that is the
    established way a background organ contributes to her memory. Deliberately
    not called for every observation: an entry every 30 seconds would bury the
    things actually worth remembering.
    """
    text = str(summary or "").strip()
    if not text:
        return False
    try:
        from memory import MemoryLevel, MemorySource, get_memory_bus

        bus = await get_memory_bus()
        await bus.store(
            content=text,
            user_id=_owner_target_id() or "global",
            level=MemoryLevel.LONG_TERM,
            priority=float(MEMORY_PRIORITY),
            tags=["摄像头所见", *(tags or [])],
            source=MemorySource.SYSTEM,
            location=_LOCATION_TEXT,
            emotional_tone=str(mood or _TONE_BY_ACTIVITY.get(activity, "")),
            significance=float(significance),
            metadata={
                "type": "camera_observation",
                "activity": activity,
                "at": float(time.time() if now is None else now),
            },
        )
        logger.info("[CameraProactive] 已记入记忆: %s", text[:60])
        return True
    except Exception as exc:  # noqa: BLE001 - memory is best effort
        logger.debug("[CameraProactive] 写入记忆失败: %s", exc)
        return False


async def recall_relevant(query: str, *, limit: int = 5) -> str:
    """Recall memories relevant to what she is seeing, as a prompt fragment.

    The proactive path never read memory before, so a background decision had no
    history behind it. This is what lets her say "you did this last Tuesday too"
    instead of commenting on the present in isolation.
    """
    text = str(query or "").strip()
    if not text:
        return ""
    try:
        from memory import get_memory_bus

        bus = await get_memory_bus()
        result = await bus.recall(text, user_id=_owner_target_id(), limit=int(limit))
    except Exception as exc:  # noqa: BLE001
        logger.debug("[CameraProactive] 召回记忆失败: %s", exc)
        return ""

    # The bus already renders a prompt-ready fragment; use it rather than
    # reassembling the same thing by hand.
    prepared = str(getattr(result, "context_text", "") or "").strip()
    if prepared:
        return "[她想起的相关往事]\n" + prepared[:800]

    items = getattr(result, "memories", None) or []
    lines: list[str] = []
    for item in items:
        content = str(getattr(item, "content", "") or "").strip().replace("\n", " ")
        if content and content not in lines:
            lines.append(content[:120])
        if len(lines) >= int(limit):
            break
    if not lines:
        return ""
    return "[她想起的相关往事]\n" + "\n".join(f"- {line}" for line in lines)


def current_mood() -> dict[str, Any]:
    """Her live emotional state, which the persona prompt does not carry.

    ``compose_persona_system_prompt`` supplies the static form definition
    ("阮梅态"), not how she feels at this moment, so mood has to be gathered
    explicitly. The coordinator already holds the live Personality object, which
    is the same one the persona prompt uses - reading it from there guarantees
    the two agree.
    """
    mood: dict[str, Any] = {}
    try:
        from core.miya_spine import get_spine

        spine = get_spine()
        state = spine.current_state() if spine else None
        if state is not None:
            mood["lifecycle"] = str(getattr(getattr(state, "lifecycle_phase", None), "value", "") or "")
            mood["uptime_seconds"] = float(getattr(state, "uptime_seconds", 0.0) or 0.0)
    except Exception:
        logger.debug("[CameraProactive] 读取灵魂状态失败", exc_info=True)
    try:
        from core.proactive_coordinator import get_proactive_coordinator

        personality = getattr(get_proactive_coordinator(), "_personality", None)
        if personality is not None:
            mood["form"] = str(getattr(personality, "current_form", "") or "")
            mood["speak_mode"] = str(getattr(personality, "speak_mode", "") or "")
    except Exception:
        logger.debug("[CameraProactive] 读取当前形态失败", exc_info=True)
    return mood


def _mood_text(mood: dict[str, Any]) -> str:
    parts: list[str] = []
    if mood.get("form"):
        parts.append(f"当前形态：{mood['form']}")
    if mood.get("speak_mode"):
        parts.append(f"说话方式：{mood['speak_mode']}")
    if mood.get("lifecycle"):
        parts.append(f"生命阶段：{mood['lifecycle']}")
    return "；".join(parts)


async def _conversation_context(limit: int = 4) -> str:
    """The tail of the recent conversation, if there is one on record.

    She should not greet Jia as if the last hour of talking had not happened.
    """
    try:
        from core.conversation_history import get_conversation_history_manager

        manager = await get_conversation_history_manager()
        owner = _owner_target_id()
        if not owner or manager is None:
            return ""
        messages = await manager.get_history(str(owner), limit=int(limit))
    except Exception:
        logger.debug("[CameraProactive] 读取最近对话失败", exc_info=True)
        return ""
    lines: list[str] = []
    for message in messages or []:
        content = str(getattr(message, "content", "") or "").strip().replace("\n", " ")
        if not content:
            continue
        role = str(getattr(message, "role", "") or "")
        speaker = "佳" if role == "user" else "弥娅" if role == "assistant" else role
        lines.append(f"{speaker}：{content[:100]}")
    return "\n".join(lines)


def _presence_event_text(snapshot) -> str:
    """One plain sentence for the change that just happened.

    The change lives in ``transition``: the tracker keeps ``state`` as
    "at_desk"/"present" and only marks the single evaluation where something
    really changed.  Reading ``state`` here produced "刚回来（returned）", i.e. a
    raw enum leaking into the sentence she may end up saying when no model is
    configured to rewrite the facts.
    """
    transition = str(getattr(snapshot, "transition", "") or "")
    if transition in _PRESENCE_CHANGE_TEXT:
        return _PRESENCE_CHANGE_TEXT[transition]
    label = str(getattr(snapshot, "label", "") or "")
    if label:
        return label
    return str(getattr(snapshot, "describe", lambda: "")() or "")


async def build_presence_event(snapshot, *, changed_at: float = 0.0) -> dict[str, Any]:
    """A structured fact for the coordinator: Jia came back or went away.

    ``changed_at`` is the moment the tracker recorded the change. It goes into
    the facts on purpose: the coordinator de-duplicates on a hash of exactly
    these values for an hour, so without a per-instance stamp the *second*
    arrival of an evening was discarded as a repeat of the first. The comment on
    the caller claimed the facts carried this timestamp; they did not.
    """
    text = _presence_event_text(snapshot)
    mood = current_mood()
    recalled = await recall_relevant(text or "佳 电脑前 离开 回来")
    context_tail = await _conversation_context()
    platform = active_platform()
    facts: dict[str, Any] = {
        "在场判断": str(getattr(snapshot, "describe", lambda: "")() or ""),
        "依据": list(getattr(snapshot, "reasons", []) or []),
        "置信度": round(float(getattr(snapshot, "confidence", 0.0) or 0.0), 2),
    }
    transition = str(getattr(snapshot, "transition", "") or "")
    if transition:
        facts["变化"] = transition
    if changed_at:
        facts["发生时刻"] = time.strftime("%m-%d %H:%M:%S", time.localtime(float(changed_at)))
    event: dict[str, Any] = {
        "source": "camera",
        "event": "presence_change",
        "urgency": "normal",
        "candidate_message": text,
        "facts": facts,
    }
    if platform:
        event["facts"]["他现在在哪"] = platform
    if _mood_text(mood):
        event["facts"]["弥娅当下"] = _mood_text(mood)
    if context_tail:
        event["facts"]["最近对话"] = context_tail
    if recalled:
        # Labelled on purpose. This recall is keyed on the event itself, so it
        # returns *previous arrivals* - observations she made, not notifications
        # she sent. Handed over unlabelled, the coordinator's judge read it as
        # evidence of repetition and answered SKIP with its own reasoning:
        # "记忆里有多次类似事件，说明这种刚回来的通知已经发过很多次了".
        # Seeing him come back before is not the same as having already spoken
        # about this arrival.
        event["facts"]["她记得的旧事（以前看到过，不代表这次已经说过）"] = recalled
    return event


def active_platform() -> str:
    """Where Jia is actually reachable right now.

    The camera's proactive messages used to leave without a platform, so they
    fell back to the default and were handed to a desktop WebSocket that nobody
    was reading - she spoke into an empty room while Jia sat in WeChat.

    ``get_current_platform`` is described in its own docstring as the single
    authority for routing every proactive message, so this defers to it rather
    than guessing.
    """
    try:
        from core.platform_awareness import get_platform_awareness

        owner = _owner_target_id()
        if owner:
            platform = str(get_platform_awareness().get_current_platform(owner) or "")
            if platform:
                return platform
    except Exception:
        logger.debug("[CameraProactive] 查询活跃平台失败", exc_info=True)
    return ""


def _register_owner_target() -> None:
    """Make the owner an active proactive target without requiring a message.

    The camera triggers used to be reachable only for targets that had chatted
    recently, so an evening of silence made her blind to Jia walking back in.
    Registering the owner is what lets a greeting happen on its own terms.
    """
    try:
        from core.proactive_chat import ChatContext, get_proactive_chat_system

        chat = get_proactive_chat_system()
        owner = _owner_target_id()
        if chat is None or not owner:
            return
        try:
            target_id: Any = int(owner)
        except (TypeError, ValueError):
            target_id = owner
        if target_id in getattr(chat, "_context_cache", {}):
            return
        # Register on whichever platform he is actually reachable on. Hard-coding
        # "desktop" here would route her queued observations to a socket nobody is
        # reading - the same mistake the bridge made before it asked awareness.
        platform = active_platform() or "desktop"
        chat.update_context(target_id, ChatContext(chat_type="private", target_id=target_id), platform)
        logger.info("[CameraProactive] 已把所有者登记为主动目标（平台 %s，不依赖他先说话）", platform)
    except Exception:
        logger.debug("[CameraProactive] 登记所有者目标失败", exc_info=True)


def should_speak_for_presence(state: str) -> bool:
    """Only clear events earn her voice, so she is not narrating every glance."""
    return str(state or "") in SPEAK_ON_PRESENCE


def camera_aware_config() -> dict[str, Any]:
    """The camera slice of ``config/proactive_chat.yaml``, as the poll loop sees it.

    The switches Jia owns (``camera_aware.enabled`` and its ``presence`` /
    ``activity`` / ``agency`` children) must mean the same thing here as they do
    in the poll loop.  Reading the live system rather than the file keeps one
    source of truth: turning the camera off has to silence *both* paths, not just
    the one that happens to be looking.
    """
    try:
        from core.proactive_chat import get_proactive_chat_system

        config = getattr(get_proactive_chat_system(), "_camera_aware_config", None)
        if isinstance(config, dict):
            return config
    except Exception:
        logger.debug("[CameraProactive] 读取摄像头主动配置失败", exc_info=True)
    return {}


def _sub_switch(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


class CameraProactiveBridge:
    """Runs the camera's contribution to the proactive system.

    Kept separate from the observation loop on purpose: observing and *speaking*
    have different rhythms, and the thing that was missing was precisely the
    step between them.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._last_presence_state = ""
        self._last_presence_stamp = 0.0
        self._last_presence_at = 0.0
        self._submitted = 0
        self._remembered_at = 0.0

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        if self._task is not None and not self._task.done():
            return False
        _register_owner_target()
        self._task = asyncio.create_task(self._run())
        logger.info("[CameraProactive] 摄像头→主动链路已启动")
        return True

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def stats(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "submitted": self._submitted,
            "last_presence_state": self._last_presence_state,
        }

    # -- the loop ----------------------------------------------------------

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(BRIDGE_INTERVAL_SECONDS)
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("[CameraProactive] 桥接轮询出错", exc_info=True)

    async def tick(self) -> dict[str, Any]:
        """One pass: turn real camera transitions into proactive facts."""
        from .activity import get_activity_tracker
        from .presence import get_presence_tracker

        result: dict[str, Any] = {"presence": None, "remembered": False}
        config = camera_aware_config()
        if not bool(config.get("enabled", True)):
            return result

        presence = get_presence_tracker().snapshot()
        now = time.time()

        # Presence. The tracker keeps its state as "at_desk"/"present" and records
        # a real change separately, because a transition only exists for the one
        # evaluation that produced it - and whichever consumer evaluates first
        # (the panel polls every few seconds) used to be the only one that could
        # ever see it. Reading it from the tracker's own record, keyed on the
        # moment it happened, lets this bridge see the same arrival once even
        # though it only looks every 20 seconds.
        transition, stamp = get_presence_tracker().last_transition()
        if transition:
            stamp = round(float(stamp or 0.0), 3)
            already_handled = (transition, stamp) == (self._last_presence_state, self._last_presence_stamp)
            # A transition stays worth acting on for TRANSITION_MAX_AGE_SECONDS, and
            # it is only marked handled once it has actually been *accepted*.
            #
            # The bookkeeping used to happen before the submission, so a refused
            # one was never tried again - the log said it plainly:
            # "全局冷却中，跳过 key=camera:presence:returned", and then he came
            # back and she never mentioned it. Being refused once is not the same
            # as having said it.
            fresh = (now - stamp) <= TRANSITION_MAX_AGE_SECONDS
            if not already_handled and fresh and should_speak_for_presence(transition):
                speak_enabled = bool(_sub_switch(config, "presence").get("enabled", True))
                # Worth remembering either way - a return or a departure is a fact
                # about him, not about whether she managed to speak. The memory
                # write carries its own, much longer throttle.
                result["remembered"] = await self._remember_presence(presence, now)
                submitted = False
                if speak_enabled:
                    event = await build_presence_event(presence, changed_at=stamp)
                    # The key names the *kind* of event, kept stable per transition
                    # on purpose: it is what the coordinator uses to refuse the same
                    # arrival twice, and two consumers can see the same transition
                    # (the bridge here, and the proactive poll's own presence
                    # trigger). The instance is identified by the tracker's timestamp
                    # inside the event facts, which the coordinator's fingerprint
                    # compares.
                    submitted = await self._submit(event, key=f"camera:presence:{transition}")
                    result["presence"] = submitted
                if submitted or not speak_enabled:
                    # Nothing left to try when speaking about presence is off.
                    self._last_presence_state = transition
                    self._last_presence_stamp = stamp
                    self._last_presence_at = now

        # Activity: remembered here, but deliberately *not* spoken about. Whether
        # to open her mouth is a judgement, and it belongs to exactly one place -
        # the model, in the proactive poll's activity trigger, which decides with
        # everything she perceives. A duration rule here was a second, mechanical
        # judge that could only ever produce "he typed for ninety minutes", and
        # because it read the one-shot change first it also starved the real one.
        change = get_activity_tracker().peek_change()
        if change is not None and str(getattr(change, "kind", "") or ""):
            if await self._remember_activity(change, now):
                result["remembered"] = True
        return result

    # -- helpers -----------------------------------------------------------

    async def _submit(self, event: dict[str, Any], *, key: str) -> bool:
        """Hand a fact to the one coordinator that throttles and delivers."""
        try:
            from core.proactive_coordinator import get_proactive_coordinator

            coordinator = get_proactive_coordinator()
            if coordinator is None:
                return False
            target = _owner_target_id() or "default"
            # Route to wherever Jia actually is. Without this the message went to
            # the default platform and ended up on a desktop socket he was not
            # watching.
            platform = active_platform()
            sent = await coordinator.submit_event(
                event, key=key, target_id=target, trigger_type="camera_aware",
                platform=platform or "terminal",
            )
            if sent:
                self._submitted += 1
                logger.info("[CameraProactive] 已提交主动事件 key=%s platform=%s",
                            key, platform or "(未知，用兜底)")
            return bool(sent)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[CameraProactive] 提交事件失败: %s", exc)
            return False

    async def _remember_presence(self, presence, now: float) -> bool:
        if now - self._remembered_at < MEMORY_MIN_INTERVAL_SECONDS:
            return False
        text = _presence_event_text(presence)
        if not text:
            return False
        stored = await remember_observation(
            summary=text,
            significance=0.7,
            tags=["在场变化"],
            now=now,
        )
        if stored:
            self._remembered_at = now
        return stored

    async def _remember_activity(self, snapshot, now: float) -> bool:
        """Keep what Jia was doing in her long-term memory, sparingly.

        Rate-limited by the same interval as presence so a fidgety afternoon does
        not fill her memory with near-identical entries.
        """
        phrase = str(getattr(snapshot, "phrase", "") or getattr(snapshot, "kind", "") or "")
        if not phrase:
            return False
        if now - self._remembered_at < MEMORY_MIN_INTERVAL_SECONDS:
            return False
        duration = float(getattr(snapshot, "duration", 0.0) or 0.0)
        minutes = int(duration // 60)
        summary = f"佳{phrase}" + (f"，持续了约 {minutes} 分钟" if minutes >= 5 else "")
        stored = await remember_observation(
            summary=summary,
            activity=str(getattr(snapshot, "kind", "") or ""),
            significance=0.6,
            tags=["活动变化"],
            now=now,
        )
        if stored:
            self._remembered_at = now
        return stored


_bridge = CameraProactiveBridge()


def get_camera_bridge() -> CameraProactiveBridge:
    return _bridge
