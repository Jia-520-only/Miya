"""The camera must reach Miya's unified proactive system, not a private copy.

The failure this guards against is specific and repeatable: the observation loop
worked, the trackers filled up, Miya formed clear conclusions ("he left the
desk") - and she said nothing, because the camera's triggers lived inside a poll
that only runs for targets who had chatted recently. Verified in the daemon log
as ``targets=0`` while she was actively noticing Jia come and go.

These tests pin the join: structured facts, all four kinds of context attached,
throttling delegated to the one coordinator, and nothing spoken unless the
coordinator accepted it.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from mcpserver.screen_vision import proactive


class _FakeCoordinator:
    """Records what would be submitted, without sending anything."""

    def __init__(self, accept: bool = True) -> None:
        self.accepted = accept
        self.events: list[dict] = []
        self.messages: list[dict] = []

    async def submit_event(self, event, **kwargs):
        self.events.append({"event": event, **kwargs})
        return self.accepted

    async def submit_message(self, message, **kwargs):
        self.messages.append({"message": message, **kwargs})
        return self.accepted


@pytest.fixture()
def bridge_and_coordinator(monkeypatch):
    coordinator = _FakeCoordinator()
    monkeypatch.setattr(
        "core.proactive_coordinator.get_proactive_coordinator", lambda: coordinator
    )
    bridge = proactive.CameraProactiveBridge()
    # Keep the tests off memory and the conversation history store.
    monkeypatch.setattr(proactive, "remember_observation", _async_false)
    monkeypatch.setattr(proactive, "_conversation_context", _async_empty)
    monkeypatch.setattr(proactive, "current_mood", lambda: {"form": "阮梅态", "lifecycle": "RUNNING"})
    return bridge, coordinator


async def _async_false(**_kwargs) -> bool:
    return False


async def _async_empty(*_args, **_kwargs) -> str:
    return ""


class _Snapshot:
    def __init__(self, **kwargs) -> None:
        self.state = kwargs.get("state", "")
        self.transition = kwargs.get("transition", "")
        self.confidence = kwargs.get("confidence", 0.7)
        self.reasons = kwargs.get("reasons", ["测试"])
        self.updated_at = kwargs.get("updated_at", time.time())
        self.last_face_seconds = kwargs.get("last_face_seconds", 5.0)
        self.kind = kwargs.get("kind", "")
        self.phrase = kwargs.get("phrase", "")
        self.duration = kwargs.get("duration", 0.0)

    def describe(self) -> str:
        return f"测试在场状态 {self.state}"


def _presence(monkeypatch, **kwargs):
    snapshot = _Snapshot(**kwargs)

    class _Tracker:
        def snapshot(self):
            return snapshot

        def last_transition(self):
            """Mirrors the real tracker: the last change it produced, with its
            own timestamp. The bridge reads this rather than the snapshot, because
            a transition only exists for the one evaluation that produced it."""
            return (snapshot.transition, snapshot.updated_at)

    monkeypatch.setattr("mcpserver.screen_vision.presence.get_presence_tracker", lambda: _Tracker())
    return snapshot


def _activity(monkeypatch, snapshot):
    class _Tracker:
        def peek_change(self):
            return snapshot

        def consume_change(self):
            return snapshot

    monkeypatch.setattr("mcpserver.screen_vision.activity.get_activity_tracker", lambda: _Tracker())
    return snapshot


# --- the event carries the four kinds of context ---------------------------


def test_a_return_produces_a_structured_fact_with_persona_mood_and_context(monkeypatch):
    async def _recall(query, limit=5):
        return "[她想起的相关往事]\n- 佳上周也熬到三点"

    monkeypatch.setattr(proactive, "recall_relevant", _recall)
    monkeypatch.setattr(proactive, "current_mood",
                        lambda: {"form": "阮梅态", "lifecycle": "RUNNING"})
    snapshot = _presence(monkeypatch, state="returned", transition="returned")
    event = asyncio.run(proactive.build_presence_event(snapshot))

    assert event["source"] == "camera"
    assert event["event"] == "presence_change"
    facts = event["facts"]
    # What she saw, and how sure she is.
    assert "在场判断" in facts and "置信度" in facts
    # Mood: the persona prompt only carries the form, so this must be explicit.
    assert "弥娅当下" in facts and "阮梅态" in facts["弥娅当下"]
    # Memory read back: the decision is not made in a vacuum - and it is labelled
    # as *past observations*, because this recall is keyed on the event itself and
    # otherwise reads like evidence that the arrival was already announced.
    memory_key = next((key for key in facts if "旧事" in str(key)), None)
    assert memory_key, f"在场事件应该带回记忆，实际字段: {sorted(facts)}"
    assert "过去" in memory_key or "以前" in memory_key, "记忆字段必须说明它是过去的观察"
    assert "熬到三点" in facts[memory_key]


def test_mood_is_omitted_rather_than_faked_when_it_cannot_be_read(monkeypatch):
    """An empty "弥娅当下" would tell the model nothing while looking like fact."""
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    monkeypatch.setattr(proactive, "current_mood", lambda: {})
    snapshot = _presence(monkeypatch, state="returned", transition="returned")
    event = asyncio.run(proactive.build_presence_event(snapshot))
    assert "弥娅当下" not in event["facts"]


def test_an_event_includes_the_recent_conversation_when_there_is_one(monkeypatch):
    async def _context(limit=4):
        return "佳：今天好累\n弥娅：那就早点休息"

    monkeypatch.setattr(proactive, "_conversation_context", _context)
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    snapshot = _presence(monkeypatch, state="returned", transition="returned")
    event = asyncio.run(proactive.build_presence_event(snapshot))
    assert "最近对话" in event["facts"]
    assert "好累" in event["facts"]["最近对话"]


# --- only clear events earn her voice --------------------------------------


def test_only_clear_presence_events_speak():
    """The log showed her wondering about every glance; she should not narrate them."""
    assert proactive.should_speak_for_presence("returned") is True
    assert proactive.should_speak_for_presence("left") is True
    assert proactive.should_speak_for_presence("present") is False
    assert proactive.should_speak_for_presence("at_desk") is False
    assert proactive.should_speak_for_presence("") is False


def test_what_jia_is_doing_is_left_to_the_one_judge():
    """No duration rule may decide whether she speaks about his activity.

    There used to be a second judge in the bridge: `activity_deserves_voice`
    fired for typing/phone only after ninety minutes. Besides being a rule where
    a judgement belongs, reading the one-shot change there starved the model
    path. Deciding is now the model's alone.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2]
              / "mcpserver" / "screen_vision" / "proactive.py").read_text(encoding="utf-8")
    assert "activity_deserves_voice" not in source
    assert "LONG_ACTIVITY_SECONDS" not in source
    assert "build_activity_event" not in source


# --- the tick submits, and does not speak on its own -----------------------


def test_a_return_is_submitted_to_the_unified_coordinator(monkeypatch, bridge_and_coordinator):
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)
    result = asyncio.run(bridge.tick())

    assert len(coordinator.events) == 1
    submitted = coordinator.events[0]
    assert submitted["trigger_type"] == "camera_aware"
    assert submitted["key"].startswith("camera:presence:")
    assert result["presence"] is True


def test_the_same_transition_is_not_submitted_twice(monkeypatch, bridge_and_coordinator):
    """The tracker raises a transition once; the bridge must not re-raise it."""
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)
    asyncio.run(bridge.tick())
    asyncio.run(bridge.tick())
    assert len(coordinator.events) == 1


def test_a_stale_transition_is_not_spoken_about(monkeypatch, bridge_and_coordinator):
    """Coming back twenty minutes ago is history, not news."""
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="returned", transition="returned",
              updated_at=time.time() - (proactive.TRANSITION_MAX_AGE_SECONDS + 60))
    _activity(monkeypatch, None)
    result = asyncio.run(bridge.tick())
    assert coordinator.events == []
    assert result["presence"] is None


def test_a_mundane_state_is_not_submitted(monkeypatch, bridge_and_coordinator):
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="present", transition="present")
    _activity(monkeypatch, None)
    asyncio.run(bridge.tick())
    assert coordinator.events == []


def test_the_bridge_does_not_send_anything_itself(monkeypatch, bridge_and_coordinator):
    """Delivery is the coordinator's job; the bridge only submits facts."""
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="left", transition="left")
    _activity(monkeypatch, None)
    asyncio.run(bridge.tick())
    assert coordinator.messages == [], "桥接不该自己发消息，那是协调器的事"
    assert len(coordinator.events) == 1


def test_a_rejected_submission_is_not_counted_as_sent(monkeypatch):
    coordinator = _FakeCoordinator(accept=False)
    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator", lambda: coordinator)
    monkeypatch.setattr(proactive, "_conversation_context", _async_empty)
    monkeypatch.setattr(proactive, "current_mood", lambda: {})
    monkeypatch.setattr(proactive, "remember_observation", _async_false)
    bridge = proactive.CameraProactiveBridge()
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)
    result = asyncio.run(bridge.tick())
    assert result["presence"] is False
    assert bridge.stats()["submitted"] == 0


def test_a_refused_transition_is_retried_on_the_next_tick(monkeypatch, bridge_and_coordinator):
    """Regression: being refused once is not the same as having said it.

    The bridge marked a transition handled *before* submitting it, so a refusal
    ended it for good - the log shows exactly this, a single
    ``全局冷却中，跳过 key=camera:presence:returned`` and then nothing, while Jia
    sat back down and she said nothing about it.
    """
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)

    coordinator.accepted = False
    first = asyncio.run(bridge.tick())
    assert len(coordinator.events) == 1, "第一次应该尝试提交"
    assert first["presence"] is False
    assert bridge._last_presence_state == "", "被拒时不该把它记成已处理"

    # The next tick, twenty seconds later, tries the same arrival again.
    coordinator.accepted = True
    second = asyncio.run(bridge.tick())
    assert len(coordinator.events) == 2, "被拒的在场事件必须在下一个 tick 重试"
    assert second["presence"] is True
    assert bridge._last_presence_state == "returned", "成功之后才记账"

    # And once it has gone out, it is not said again.
    asyncio.run(bridge.tick())
    assert len(coordinator.events) == 2, "发出去之后不该重复提交"


def test_a_transition_that_expires_unspoken_stops_being_retried(monkeypatch, bridge_and_coordinator):
    """The retry window is bounded: a stale arrival is history, not news."""
    bridge, coordinator = bridge_and_coordinator
    _presence(monkeypatch, state="returned", transition="returned",
              updated_at=time.time() - (proactive.TRANSITION_MAX_AGE_SECONDS + 60))
    _activity(monkeypatch, None)
    coordinator.accepted = False
    for _ in range(3):
        asyncio.run(bridge.tick())
    assert coordinator.events == [], "过期的transition连尝试都不该尝试"


# --- memory is written sparingly -------------------------------------------


def test_memory_writes_are_rate_limited(monkeypatch, bridge_and_coordinator):
    """An entry every 30 seconds would bury what is actually worth remembering."""
    bridge, _coordinator = bridge_and_coordinator
    calls: list[dict] = []

    async def _remember(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(proactive, "remember_observation", _remember)
    snapshot = _Snapshot(state="returned", transition="returned")
    now = time.time()
    assert asyncio.run(bridge._remember_presence(snapshot, now)) is True
    # A second event moments later must not create a second memory entry.
    assert asyncio.run(bridge._remember_presence(snapshot, now + 5)) is False
    assert len(calls) == 1
    # Past the interval it is allowed again.
    assert asyncio.run(bridge._remember_presence(
        snapshot, now + proactive.MEMORY_MIN_INTERVAL_SECONDS + 1)) is True
    assert len(calls) == 2


def test_settled_presence_still_records_the_original_transition(monkeypatch, bridge_and_coordinator):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    bridge, coordinator = bridge_and_coordinator
    snapshot = _Snapshot(state="at_desk", transition="")
    tracker = SimpleNamespace(snapshot=lambda: snapshot, last_transition=lambda: ("returned", snapshot.updated_at))
    monkeypatch.setattr("mcpserver.screen_vision.presence.get_presence_tracker", lambda: tracker)
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    remember = AsyncMock(return_value=True)
    monkeypatch.setattr(proactive, "remember_observation", remember)
    _activity(monkeypatch, None)

    result = asyncio.run(bridge.tick())

    assert result["remembered"] is True
    assert result["presence"] is True
    assert coordinator.events[0]["event"]["facts"]["变化"] == "returned"
    assert remember.call_args.kwargs["summary"] == "摄像头在场变化：returned"


def test_disabled_presence_speech_still_remembers_without_raising(monkeypatch, bridge_and_coordinator):
    from unittest.mock import AsyncMock

    bridge, coordinator = bridge_and_coordinator
    monkeypatch.setattr(proactive, "camera_aware_config", lambda: {"presence": {"enabled": False}})
    remember = AsyncMock(return_value=True)
    monkeypatch.setattr(proactive, "remember_observation", remember)
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)

    result = asyncio.run(bridge.tick())

    assert result["remembered"] is True
    assert result["presence"] is None
    assert coordinator.events == []
    assert bridge._last_presence_state == "returned"


def test_a_sustained_activity_is_remembered_even_without_a_remark(monkeypatch, bridge_and_coordinator):
    """"He typed for three hours" is exactly what she should be able to recall."""
    bridge, _coordinator = bridge_and_coordinator
    calls: list[dict] = []

    async def _remember(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(proactive, "remember_observation", _remember)
    snapshot = _Snapshot(kind="typing", phrase="在敲键盘", duration=7200)
    assert asyncio.run(bridge._remember_activity(snapshot, time.time())) is True
    assert calls and "分钟" in calls[0]["summary"]


def test_a_momentary_change_is_remembered_without_pretending_it_lasted(monkeypatch, bridge_and_coordinator):
    """Rate limiting is the only filter on memory now: a wave is worth recalling.

    The old duration gate existed to keep short activities out of memory, but the
    30-minute interval already does that, and a generic camera subject is exactly
    the kind of
    thing she should be able to bring up later.
    """
    bridge, _coordinator = bridge_and_coordinator
    calls: list[dict] = []

    async def _remember(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(proactive, "remember_observation", _remember)
    snapshot = _Snapshot(kind="wave", phrase="在跟你挥手", duration=0.0)
    assert asyncio.run(bridge._remember_activity(snapshot, time.time())) is True
    assert calls and calls[0]["summary"] == "画面里的人在跟你挥手"
    assert "持续" not in calls[0]["summary"]


def test_an_empty_summary_is_never_stored(monkeypatch):
    """A blank memory would be worse than none: it looks like a real recollection."""
    monkeypatch.setattr(proactive, "_owner_target_id", lambda: "owner")
    assert asyncio.run(proactive.remember_observation(summary="   ")) is False


# --- the wiring itself ------------------------------------------------------


def test_the_bridge_is_started_by_the_proactive_startup():
    """Guards the join, not just the class: nothing called the old triggers."""
    from pathlib import Path

    hub_source = (Path(__file__).resolve().parents[2] / "hub" / "decision_hub.py").read_text(encoding="utf-8")
    assert "start_camera_proactive_background" in hub_source
    assert "get_camera_bridge" in hub_source

    daemon_source = (Path(__file__).resolve().parents[2] / "core" / "miya_daemon.py").read_text(encoding="utf-8")
    assert "start_camera_proactive_background" in daemon_source, (
        "摄像头不该只在主动聊天开启时才接入"
    )


def test_the_owner_is_registered_so_silence_does_not_blind_her():
    """The exact bug: `targets=0` meant the camera chain never ran."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2]
              / "mcpserver" / "screen_vision" / "proactive.py").read_text(encoding="utf-8")
    assert "_register_owner_target" in source
    assert "update_context" in source, "登记目标靠 update_context，不需要他先说话"


# --- against the real trackers, not hand-built snapshots --------------------
#
# The fakes above set `state` and `transition` to the same string, which is
# exactly what the real trackers never do. Two of the defects below lived
# entirely inside that gap, so these tests drive the genuine trackers.


def test_a_real_return_is_submitted(monkeypatch, bridge_and_coordinator):
    """Regression: with the real tracker the bridge submitted nothing, ever.

    `PresenceTracker` keeps `state` as "at_desk"/"present" and puts "returned" in
    `transition`; the old guard demanded `transition == state`, so the branch was
    unreachable and an evening of coming and going went unspoken.
    """
    from mcpserver.screen_vision import presence as presence_module
    from mcpserver.screen_vision.presence import PresenceTracker

    bridge, coordinator = bridge_and_coordinator
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    _activity(monkeypatch, None)

    tracker = PresenceTracker()
    now = time.time()
    tracker.observe(at=now - 310, faces=1, face_ratio=0.05)   # 在电脑前
    left = tracker.observe(at=now - 10, faces=0)              # 人脸消失超过阈值
    returned = tracker.observe(at=now, faces=1, face_ratio=0.05)

    # Precondition: this is what the tracker really produces.
    assert left.transition == "left"
    assert returned.state == "at_desk"
    assert returned.transition == "returned"

    monkeypatch.setattr(presence_module, "get_presence_tracker", lambda: tracker)
    result = asyncio.run(bridge.tick())

    assert result["presence"] is True, "真实存在场变化没有提交给协调器"
    assert len(coordinator.events) == 1
    assert coordinator.events[0]["key"].startswith("camera:presence:returned:")


def test_two_real_returns_in_one_evening_are_both_submitted(monkeypatch, bridge_and_coordinator):
    """Deduplicating by transition name alone would swallow the second return."""
    from mcpserver.screen_vision import presence as presence_module
    from mcpserver.screen_vision.presence import PresenceTracker

    bridge, coordinator = bridge_and_coordinator
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    _activity(monkeypatch, None)

    tracker = PresenceTracker()
    monkeypatch.setattr(presence_module, "get_presence_tracker", lambda: tracker)
    now = time.time()

    def go_away_and_come_back(offset: float) -> None:
        tracker.observe(at=now + offset, faces=1, face_ratio=0.05)
        tracker.observe(at=now + offset + 300, faces=0)
        tracker.observe(at=now + offset + 310, faces=1, face_ratio=0.05)
        # The bridge judges freshness against the wall clock, so pin it.
        tracker.snapshot().updated_at = time.time()
        asyncio.run(bridge.tick())

    go_away_and_come_back(0.0)
    go_away_and_come_back(3600.0)

    keys = [item["key"] for item in coordinator.events]
    assert len(keys) == 2, "一整晚的第二次回到电脑前被当成重复丢掉了"
    assert all(key.startswith("camera:presence:returned:") for key in keys)
    assert keys[0] != keys[1]


def test_the_bridge_does_not_steal_the_activity_change_from_the_poll(monkeypatch, bridge_and_coordinator):
    """One change, two readers: the bridge may remember it, not take it.

    Consuming on read meant the bridge (every 20s) always beat the proactive poll
    (every 45s) to every change, so the only path that asks the model whether to
    speak never saw one.
    """
    from mcpserver.screen_vision import activity as activity_module
    from mcpserver.screen_vision.activity import ActivityTracker, activity_change_card

    bridge, _coordinator = bridge_and_coordinator
    monkeypatch.setattr(proactive, "recall_relevant", _async_empty)
    monkeypatch.setattr(proactive, "_conversation_context", _async_empty)
    _presence(monkeypatch, state="at_desk", transition="")

    remembered: list[str] = []

    async def _remember(**kwargs):
        remembered.append(kwargs.get("summary", ""))
        return True

    monkeypatch.setattr(proactive, "remember_observation", _remember)

    tracker = ActivityTracker()
    monkeypatch.setattr(activity_module, "get_activity_tracker", lambda: tracker)
    monkeypatch.setattr(activity_module, "_tracker", tracker)
    base = time.time()
    tracker.observe("still", at=base - 60, confidence=0.7)
    tracker.observe("typing", at=base - 30, confidence=0.8)
    tracker.observe("typing", at=base, confidence=0.8)
    assert "敲键盘" in activity_change_card(), "前置条件：活动变化确实存在"

    asyncio.run(bridge.tick())

    assert remembered, "桥接层没有把这次活动写进记忆"
    assert tracker.has_pending_change() is True, "桥接层把活动变化独吞了"
    assert "敲键盘" in activity_change_card(), "主动轮询再也看不到这次变化了"


def test_the_camera_switch_in_the_yaml_silences_the_bridge(monkeypatch, bridge_and_coordinator):
    """Turning the camera off must silence both paths, not only the poll loop."""
    bridge, coordinator = bridge_and_coordinator
    monkeypatch.setattr(proactive, "camera_aware_config", lambda: {"enabled": False})
    _presence(monkeypatch, state="returned", transition="returned")
    _activity(monkeypatch, None)

    assert asyncio.run(bridge.tick())["presence"] is None
    assert coordinator.events == []


# --- the camera switches in the yaml actually reach the system --------------


def test_the_camera_aware_section_is_not_dropped_by_config_normalization():
    """Regression: `_normalize_config` rebuilt the config and discarded the section.

    Everything written under `camera_aware` in `config/proactive_chat.yaml` was
    silently replaced by hard-coded defaults, so the switches could not be turned
    off and `agency.max_age_seconds` could not be changed.
    """
    from core.proactive_chat import _normalize_config

    cfg = _normalize_config({
        "camera_aware": {
            "presence": {"notify_on": ["returned", "left"]},
            "agency": {"enabled": False, "max_age_seconds": 120},
        },
        "screen_aware": {"enabled": False},
    })

    camera = cfg["camera_aware"]
    assert camera["enabled"] is True
    assert camera["presence"]["notify_on"] == ["returned", "left"]
    assert camera["agency"] == {"enabled": False, "max_age_seconds": 120}
    assert cfg["screen_aware"]["enabled"] is False
    # 半段配置不能把同段其余默认值一起冲掉
    assert camera["presence"]["min_confidence"] == 0.5
    assert camera["events"], "events 默认值不该丢"


def test_the_shipped_yaml_survives_normalization():
    """The real file, not a hand-written dict: its camera switches must land."""
    from core.proactive_chat import load_config

    camera = load_config()["camera_aware"]
    assert camera["enabled"] is True
    assert camera["presence"]["notify_on"] == ["returned"]
    assert camera["activity"]["enabled"] is True
    assert camera["agency"] == {"enabled": True, "max_age_seconds": 600}
