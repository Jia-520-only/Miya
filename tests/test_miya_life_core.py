"""生命事件总线的兼容性、状态一致性和真实入口回归。"""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core import miya_spine
from core.miya_decision_hub_organ import MiyaDecisionHubOrgan
from core.miya_life_event import LifeEventType, MiyaEvent
from core.miya_organ import MiyaOrgan, MiyaOrganGroup
from core.miya_soul_state import LifecyclePhase
from core.miya_spine import MiyaSpine


class RecordingOrgan(MiyaOrgan):
    def __init__(self, name="recording", priority=50):
        super().__init__(name, priority)
        self.events = []
        self.messages = []
        self.actions = []
        self.system_events = []
        self.phases = []

    def on_life_event(self, event, state):
        self.events.append((event, state))

    def on_user_message(self, message, user_id=""):
        self.messages.append((message, user_id))

    def on_action_result(self, action, result):
        self.actions.append((action, result))

    def on_system_event(self, event, data=None):
        self.system_events.append((event, data))

    def on_lifecycle_change(self, old, new):
        self.phases.append((old, new))


@pytest.fixture
def spine(monkeypatch):
    instance = MiyaSpine(heartbeat_interval=0.01, idle_detection=False)
    monkeypatch.setattr(miya_spine, "_spine_instance", instance)
    return instance


def test_event_serialization_is_detached_and_preserves_trace():
    event = MiyaEvent(
        LifeEventType.ACTION_RESULT, source="tool", actor="miya",
        payload={"result": {"ok": True}}, timestamp=123.0, correlation_id="turn-1",
    )
    result = event.to_dict()
    assert json.loads(json.dumps(result)) == result
    assert result["correlation_id"] == "turn-1"
    result["payload"]["result"]["ok"] = False
    assert event.payload["result"]["ok"] is True


def test_injection_updates_current_state_and_decision_cache_immediately(spine):
    organ = RecordingOrgan()
    decision = MiyaDecisionHubOrgan()
    spine.register_organs(organ, decision)
    before = spine.current_state
    spine.inject_user_message("你好", "USER_OPENID", source="qqofficial", correlation_id="msg-1")
    event, state = organ.events[0]
    assert event.event_type == LifeEventType.USER_MESSAGE
    assert event.correlation_id == "msg-1"
    assert organ.messages == [("你好", "USER_OPENID")]
    assert state.message_count == spine.current_state.message_count == 1
    assert state.life_state.attention == {
        "actor": "USER_OPENID", "source": "qqofficial", "content": "你好",
    }
    assert state.life_state.last_event_at == event.timestamp
    assert spine.current_state.life_state.recent_experience == [event.to_dict()]
    assert decision.get_cached_state().life_state.attention == state.life_state.attention
    assert before.message_count == 0
    assert before.life_state.recent_experience == []
    assert json.loads(json.dumps(spine.get_status()))["message_count"] == 1


def test_legacy_hooks_keep_payloads_and_empty_user_id(spine):
    organ = RecordingOrgan()
    spine.register_organ(organ)
    spine.inject_user_message("匿名消息")
    spine.inject_action_result("send", {"ok": False, "error": "offline"})
    spine.inject_system_event("network.changed", {"event": "nested", "online": False})
    spine.inject_system_event("sleep")
    assert organ.messages == [("匿名消息", "")]
    assert organ.actions == [("send", {"ok": False, "error": "offline"})]
    assert organ.system_events == [
        ("network.changed", {"event": "nested", "online": False}),
        ("sleep", None),
    ]
    assert len(organ.events) == 4
    assert spine.current_state.message_count == 1


def test_direct_event_uses_same_accounting_as_legacy_injection(spine):
    event = MiyaEvent(LifeEventType.USER_MESSAGE, actor="user", payload={"message": "direct"})
    spine.handle_event(event)
    assert spine.current_state.message_count == 1
    assert spine.current_state.life_state.attention["content"] == "direct"
    assert spine._last_interaction > 0


def test_history_and_recent_experiences_are_bounded(spine):
    for index in range(225):
        spine.inject_system_event("tick", {"index": index})
    assert len(spine.event_history) == 200
    assert spine.event_history[0].payload["data"]["index"] == 25
    recent = spine.current_state.life_state.recent_experience
    assert len(recent) == 20
    assert recent[0]["payload"]["data"]["index"] == 205
    assert recent[-1]["payload"]["data"]["index"] == 224


def test_input_and_consumer_mutations_cannot_rewrite_shared_experience(spine):
    class MutatingOrgan(MiyaOrgan):
        def on_life_event(self, event, state):
            event.payload["result"]["ok"] = False
            state.life_state.recent_experience.clear()

        def on_action_result(self, action, result):
            result["ok"] = False

    recorder = RecordingOrgan()
    spine.register_organs(MutatingOrgan("mutating", priority=1), recorder)
    event = MiyaEvent(LifeEventType.ACTION_RESULT, payload={"action": "send", "result": {"ok": True}})
    returned = spine.emit_event(event)
    event.payload["result"]["ok"] = False
    returned.payload["result"]["ok"] = False
    spine.event_history[0].payload["result"]["ok"] = False
    snapshot = spine.current_state
    snapshot.life_state.recent_experience.clear()
    assert recorder.events[0][0].payload["result"]["ok"] is True
    assert recorder.actions == [("send", {"ok": True})]
    assert spine.event_history[0].payload["result"]["ok"] is True
    assert len(spine.current_state.life_state.recent_experience) == 1


def test_new_hook_failure_does_not_block_other_organs_or_legacy_hooks(spine):
    broken = RecordingOrgan("broken", priority=1)
    broken.on_life_event = Mock(side_effect=RuntimeError("failed"))
    recorder = RecordingOrgan()
    spine.register_organs(recorder, broken)
    spine.inject_user_message("hello", "user")
    assert broken.messages == recorder.messages == [("hello", "user")]
    assert len(recorder.events) == 1


def test_organs_receive_new_and_old_hooks_once_in_priority_order(spine):
    calls = []
    for name, priority in [("last", 99), ("first", 1)]:
        organ = MiyaOrgan(name, priority)
        organ.on_life_event = lambda event, state, name=name: calls.append(("new", name))
        organ.on_user_message = lambda text, uid, name=name: calls.append(("old", name))
        spine.register_organ(organ)
    spine.inject_user_message("hello")
    assert calls == [("new", "first"), ("new", "last"), ("old", "first"), ("old", "last")]


def test_group_forwards_both_hooks_and_system_payload(spine):
    children = [RecordingOrgan("a"), RecordingOrgan("b")]
    spine.register_organ(MiyaOrganGroup("group", children))
    spine.inject_system_event("network", {"online": True})
    for child in children:
        assert len(child.events) == 1
        assert child.system_events == [("network", {"online": True})]


@pytest.mark.asyncio
async def test_lifecycle_events_match_legacy_hooks_and_published_state(spine):
    organ = RecordingOrgan()
    spine.register_organ(organ)
    await spine.start()
    try:
        assert organ.started
        assert spine.current_state.lifecycle_phase == LifecyclePhase.RUNNING
        await spine._transition(LifecyclePhase.IDLE)
        await spine._transition(LifecyclePhase.IDLE)
        assert spine.current_state.life_state.life_phase == "IDLE"
    finally:
        await spine.shutdown()
    events = [event for event, _ in organ.events if event.event_type == LifeEventType.LIFECYCLE_CHANGED]
    assert [event.payload["new_phase"] for event in events] == ["BOOT", "RUNNING", "IDLE", "SHUTDOWN"]
    assert len(organ.phases) == len(events)
    assert spine.current_state.lifecycle_phase == LifecyclePhase.SHUTDOWN
    assert not organ.started


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", [LifecyclePhase.IDLE, LifecyclePhase.DROWSY, LifecyclePhase.SLEEP])
async def test_message_restores_running_phase(spine, phase):
    spine._loop = asyncio.get_running_loop()
    await spine._transition(phase)
    restored = asyncio.Event()

    class WakeObserver(MiyaOrgan):
        def on_lifecycle_change(self, old, new):
            if new == LifecyclePhase.RUNNING:
                restored.set()

    spine.register_organ(WakeObserver("wake"))
    spine.inject_user_message("醒醒", "user")
    await asyncio.wait_for(restored.wait(), timeout=1)
    assert spine.current_state.life_state.life_phase == "RUNNING"
    assert spine.current_state.message_count == 1


@pytest.mark.asyncio
async def test_concurrent_messages_and_heartbeat_do_not_lose_state(spine):
    recorder = RecordingOrgan()
    spine.register_organ(recorder)
    await spine.start()
    try:
        def send_messages():
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda index: spine.inject_user_message(str(index), "user"), range(40)))

        await asyncio.wait_for(asyncio.to_thread(send_messages), timeout=5)
        # 等待确实发生一次新的心跳，再检查发布状态没有倒退。
        heartbeat = threading.Event()
        observer = MiyaOrgan("heartbeat")
        observer.on_soul_state = lambda state: heartbeat.set()
        spine.register_organ(observer)
        assert await asyncio.to_thread(heartbeat.wait, 1)
        messages = [(event, state) for event, state in recorder.events if event.event_type == LifeEventType.USER_MESSAGE]
        assert [state.message_count for _, state in messages] == list(range(1, 41))
        assert spine.current_state.message_count == 40
        assert len(recorder.messages) == 40
        assert spine.current_state.life_state.attention == messages[-1][1].life_state.attention
        assert spine.get_status()["life_state"]["last_event_at"] == messages[-1][0].timestamp
    finally:
        await spine.shutdown()


@pytest.fixture
def message_hub(monkeypatch):
    from hub.decision_hub import DecisionHub

    hub = object.__new__(DecisionHub)
    hub.proactive_chat = None
    hub.personality = None
    hub._check_and_learn_image_correction = AsyncMock()
    hub._handle_quick_commands = AsyncMock(return_value="收到")
    store = SimpleNamespace(initialize=AsyncMock(), record_message=AsyncMock())
    monkeypatch.setattr("core.unified_message_store.get_unified_message_store", lambda: store)
    monkeypatch.setattr("core.management_api.get_management_api", lambda: None)
    monkeypatch.setattr("core.platform_awareness.get_platform_awareness", lambda: SimpleNamespace(record_activity=Mock()))
    monkeypatch.setattr("core.user_persona.get_user_persona_manager", lambda: SimpleNamespace(update_from_message=Mock()))
    monkeypatch.setattr("memory.diteng_listener.get_diting", lambda: SimpleNamespace(on_group_message=Mock()))
    return hub


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["terminal", "web", "qqofficial", "discord"])
async def test_actual_decision_entry_injects_one_traceable_message(spine, message_hub, platform):
    from mlink.message import Message

    await spine._transition(LifecyclePhase.RUNNING)
    message = Message("data", {
        "platform": platform, "content": "你好", "sender_id": "USER_OPENID",
        "message_id": "platform-message", "group_id": "GROUP_OPENID",
        "message_type": "group", "sender_name": "佳", "is_at_bot": True,
    }, "test")
    assert await message_hub.process_perception_cross_platform(message) == "收到"
    events = [event for event in spine.event_history if event.event_type == LifeEventType.USER_MESSAGE]
    assert len(events) == 1
    event = events[0]
    assert (event.source, event.actor, event.correlation_id) == (platform, "USER_OPENID", "platform-message")
    assert event.payload["group_id"] == "GROUP_OPENID"
    assert event.payload["message_type"] == "group"
    assert spine.current_state.message_count == 1
    await asyncio.sleep(0)  # 让已有的入站消息存储任务完成。


@pytest.mark.asyncio
async def test_decision_entry_skips_internal_marker_and_uses_mlink_trace(spine, message_hub):
    from mlink.message import Message

    await spine._transition(LifecyclePhase.RUNNING)
    marker = Message("data", {"platform": "web", "content": "[表情包请求已处理] 已发送"}, "test")
    assert await message_hub.process_perception_cross_platform(marker) == "已发送"
    assert spine.current_state.message_count == 0
    message = Message("data", {"source": "web", "input": [{"type": "image"}], "user_id": "user"}, "test")
    assert await message_hub.process_perception_cross_platform(message) == "收到"
    event = spine.event_history[-1]
    assert event.correlation_id == message.message_id
    assert event.payload["message"] == "[图片]"
    await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [None, LifecyclePhase.INIT, LifecyclePhase.SHUTDOWN])
async def test_decision_entry_works_without_active_spine(spine, message_hub, monkeypatch, state):
    from mlink.message import Message

    if state is None:
        monkeypatch.setattr(miya_spine, "_spine_instance", None)
    elif state == LifecyclePhase.SHUTDOWN:
        await spine._transition(state)
    message = Message("data", {"platform": "web", "content": "hello"}, "test")
    assert await message_hub.process_perception_cross_platform(message) == "收到"
    assert spine.current_state.message_count == 0
    if state is None:
        assert miya_spine.get_existing_spine() is None
    await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", [
    "platform.connected", "platform.disconnected", "platform.reconnecting",
    "platform.reconnected", "platform.reconnect_failed", "platform.error", "platform.shutdown",
])
async def test_registry_broadcast_reaches_life_bus_with_original_platform_data(spine, event_type):
    from core.miya_daemon import MiyaDaemon
    from core.unified_platform import PlatformRegistry

    # INIT 阶段也接收平台事件，保留启动期间发生的连接。
    daemon = object.__new__(MiyaDaemon)
    registry = PlatformRegistry()
    registry.on_broadcast(daemon._on_platform_broadcast)
    organ = RecordingOrgan()
    spine.register_organ(organ)
    payload = {
        "event": event_type, "platform_id": "qqofficial", "timestamp": "2026-11-15T12:00:00",
        "status": "offline", "data": {"attempt": 2},
    }
    await registry._on_platform_event(payload)
    event = spine.event_history[0]
    assert event.event_type == LifeEventType.PLATFORM_EVENT
    assert event.source == "qqofficial"
    assert event.payload == payload
    assert organ.system_events == [(event_type, {"attempt": 2})]
    assert spine.current_state.message_count == 0


@pytest.mark.asyncio
async def test_platform_events_do_not_create_or_revive_spine(spine, monkeypatch):
    from core.miya_daemon import MiyaDaemon

    daemon = object.__new__(MiyaDaemon)
    event = {"event": "platform.connected", "platform_id": "web"}
    monkeypatch.setattr(miya_spine, "_spine_instance", None)
    await daemon._on_platform_broadcast(event)
    assert miya_spine.get_existing_spine() is None
    monkeypatch.setattr(miya_spine, "_spine_instance", spine)
    await spine._transition(LifecyclePhase.SHUTDOWN)
    count = len(spine.event_history)
    await daemon._on_platform_broadcast(event)
    assert len(spine.event_history) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [False, True])
async def test_bootstrap_creates_bus_before_platform_connections_only_when_enabled(monkeypatch, disabled):
    from core import miya_daemon
    from run import daemon as bootstrap

    monkeypatch.setattr(miya_spine, "_spine_instance", None)
    monkeypatch.setenv("MIYA_NO_SPINE", "1" if disabled else "")

    real_daemon = miya_daemon.MiyaDaemon

    async def connect(**kwargs):
        await real_daemon._on_platform_broadcast(
            SimpleNamespace(), {"event": "platform.connected", "platform_id": "test"},
        )
        assert (miya_spine.get_existing_spine() is None) == disabled

    fake_daemon = SimpleNamespace(start=AsyncMock(side_effect=connect))
    monkeypatch.setattr(miya_daemon, "MiyaDaemon", Mock(return_value=fake_daemon))
    legacy = AsyncMock()
    spine_runner = AsyncMock()
    monkeypatch.setattr(bootstrap, "run_daemon_legacy", legacy)
    monkeypatch.setattr(bootstrap, "run_daemon_spine", spine_runner)
    await bootstrap.run_daemon(api_enabled=False)
    assert legacy.await_count == int(disabled)
    assert spine_runner.await_count == int(not disabled)
    if not disabled:
        assert miya_spine.get_existing_spine().event_history[0].payload["event"] == "platform.connected"
