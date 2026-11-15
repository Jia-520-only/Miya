"""持续约定、行动证据、情绪投影与受控跟进的完整场景。"""

import asyncio
import json
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core import miya_spine
from core.miya_continuity_organ import MiyaContinuityOrgan
from core.miya_intention import FOLLOWUP_INTERVAL, experience_emotion
from core.miya_life_event import LifeEventType, MiyaEvent
from core.miya_life_journal import LifeEventJournal
from core.miya_organ import MiyaOrgan, MiyaOrganGroup
from core.miya_soul_state import LifecyclePhase
from core.miya_spine import MiyaSpine
from core.proactive_coordinator import ProactiveCoordinator
from core.proactive_delivery import DeliveryResult
from hub.context_builder import ConsumerRequest, ContextBuilder
from hub.emotion import Emotion
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.registry import ToolRegistry
from webnet.ToolNet.tools.memory.manage_intention import ManageIntention


def scope(**changes):
    return {"user_id": "owner", "platform": "web", "group_id": "", "session_id": "session-a",
            "request_id": "turn-1", "current_input": "请整理并发送资料", **changes}


def remember(spine, **changes):
    return spine.manage_intention(
        "remember", scope(), title="发送资料", expected_outcome="资料已经发送",
        action_name="send_materials", **{"completion_mode": "action_success", **changes},
    )


@pytest.fixture
def spine(tmp_path, monkeypatch):
    instance = MiyaSpine(event_journal=LifeEventJournal(tmp_path / "life.sqlite3"))
    monkeypatch.setattr(miya_spine, "_spine_instance", instance)
    return instance


@pytest.fixture
def registry():
    instance = ToolRegistry()
    instance._check_tool_permission = AsyncMock(return_value={"allowed": True})
    instance.register(ManageIntention())
    return instance


def restore(spine, monkeypatch):
    instance = MiyaSpine(event_journal=LifeEventJournal(spine._event_journal.path))
    monkeypatch.setattr(miya_spine, "_spine_instance", instance)
    return instance


async def manage(registry, operation, *, context=None, **values):
    result = await registry.execute_tool(
        "manage_intention", ToolContext(**(context or scope())), operation=operation, **values,
    )
    return json.loads(result)


@pytest.mark.asyncio
async def test_failed_promise_survives_restart_and_changes_next_conversation(spine, registry, monkeypatch):
    created = await manage(registry, "remember", title="发送资料", expected_outcome="收到发送回执",
                           action_name="send_materials", completion_mode="action_success")
    identity = created["intention"]["intention_id"]
    execute = AsyncMock(return_value={"success": False, "error": "连接中断"})
    registry.tools["send_materials"] = SimpleNamespace(execute=execute)
    await registry.execute_tool("send_materials", ToolContext(**scope()))
    assert spine.list_intentions(scope())[0]["status"] == "waiting"
    for index in range(205):
        spine.inject_system_event("tick", {"index": index})
    restarted = restore(spine, monkeypatch)
    assert restarted.list_intentions(scope())[0]["intention_id"] == identity
    execute.assert_awaited_once()  # 恢复历史没有再次执行发送。
    emotion = Emotion()
    builder = ContextBuilder(None, emotion=emotion)
    monkeypatch.setattr(builder, "_load_messages", AsyncMock(return_value=[]))
    allocation = await builder.build("session-a", user_id="owner", platform="web", current_input="资料呢？")
    evidence = next(item for item in allocation.get("default") if item["metadata"]["source"] == "life_intention")
    assert "连接中断" in evidence["content"]
    data = json.loads(evidence["content"].split("】", 1)[1])
    assert data["experience_emotion"]["current"]["sadness"] > emotion.current_emotions["sadness"]
    assert data["evidence_event_id"] in data["experience_emotion"]["evidence_event_ids"]
    later = scope(request_id="turn-2", current_input="现在继续发送资料")
    assert (await manage(registry, "resume", context=later, intention_id=identity))["success"]
    execute.return_value = {"success": True}
    await registry.execute_tool("send_materials", ToolContext(**later))
    assert restarted.list_intentions(scope()) == []
    done = restarted.list_intentions(scope(), include_closed=True)[0]
    assert done["status"] == "completed"
    assert done["attempts"] == 2
    assert emotion.get_experience_state([done])["current"]["joy"] > emotion.current_emotions["joy"]


@pytest.mark.asyncio
@pytest.mark.parametrize("result, expected", [
    ({"success": True}, "completed"),
    ({"success": False}, "waiting"),
    ({"success": True, "status": "queued"}, "waiting"),
    ({"success": True, "status": "claimed"}, "waiting"),
    ("工具已返回", "needs_confirmation"),
])
async def test_only_confirmed_action_results_can_complete(spine, registry, result, expected):
    remember(spine)
    registry.tools["send_materials"] = SimpleNamespace(execute=AsyncMock(return_value=result))
    await registry.execute_tool("send_materials", ToolContext(**scope()))
    assert spine.list_intentions(scope(), include_closed=True)[0]["status"] == expected


@pytest.mark.asyncio
async def test_user_confirmation_is_grounded_in_current_input(spine, registry):
    record = remember(spine, completion_mode="user_confirmation")
    registry.tools["send_materials"] = SimpleNamespace(execute=AsyncMock(return_value={"success": True}))
    await registry.execute_tool("send_materials", ToolContext(**scope()))
    assert spine.list_intentions(scope())[0]["status"] == "needs_confirmation"
    result = await manage(registry, "confirm", intention_id=record["intention_id"], evidence="已经收到了")
    assert not result["success"]
    result = await manage(registry, "confirm", context=scope(request_id="turn-2", current_input="已经收到了，谢谢"),
                          intention_id=record["intention_id"], evidence="已经收到了")
    assert result["intention"]["status"] == "completed"
    assert result["intention"]["last_result"]["summary"] == "已经收到了"


@pytest.mark.asyncio
async def test_interrupted_action_requires_verification_before_retry(spine, registry, monkeypatch):
    record = remember(spine)
    spine.emit_event(MiyaEvent(
        LifeEventType.ACTION_STARTED, correlation_id="turn-1",
        payload={**scope(), "intention_id": record["intention_id"], "action": "send_materials", "action_id": "old"},
    ))
    restarted = restore(spine, monkeypatch)
    assert restarted.list_intentions(scope())[0]["status"] == "needs_confirmation"
    assert not (await manage(registry, "resume", intention_id=record["intention_id"]))["success"]
    later = scope(request_id="turn-2", current_input="确认没有收到，请重发")
    result = await manage(registry, "retry", context=later, intention_id=record["intention_id"], evidence="确认没有收到，请重发")
    assert result["intention"]["status"] == "active"
    execute = AsyncMock(return_value={"success": True})
    registry.tools["send_materials"] = SimpleNamespace(execute=execute)
    await registry.execute_tool("send_materials", ToolContext(**later))
    execute.assert_awaited_once()
    assert restarted.list_intentions(scope()) == []


@pytest.mark.parametrize("changes", [
    {"user_id": "stranger"}, {"platform": "qqofficial"}, {"group_id": "group-1"}, {"session_id": "session-b"},
])
def test_scope_boundaries_apply_to_read_and_update(spine, changes):
    record = remember(spine)
    assert spine.list_intentions(scope(**changes), include_closed=True) == []
    with pytest.raises(ValueError, match="当前会话"):
        spine.manage_intention("pause", scope(**changes), intention_id=record["intention_id"])


@pytest.mark.asyncio
async def test_unrelated_tools_and_later_requests_do_not_complete_old_promise(spine, registry):
    remember(spine)
    registry.tools["send_materials"] = SimpleNamespace(execute=AsyncMock(return_value={"success": True}))
    registry.tools["search"] = SimpleNamespace(execute=AsyncMock(return_value={"success": True}))
    await registry.execute_tool("search", ToolContext(**scope()))
    await registry.execute_tool("send_materials", ToolContext(**scope(request_id="unrelated-turn")))
    record = spine.list_intentions(scope())[0]
    assert record["status"] == "active" and record["attempts"] == 0


def test_duplicate_remember_and_replayed_event_do_not_duplicate_progress(spine):
    first = remember(spine)
    again = remember(spine)
    assert first["intention_id"] == again["intention_id"]
    before = spine.list_intentions(scope())
    spine.emit_event(spine.event_history[0])
    assert spine.list_intentions(scope()) == before
    assert len(spine._event_journal.load_intentions()) == 1


def test_temporary_disk_failure_is_repaired_without_replaying_hooks(spine, monkeypatch):
    append = spine._event_journal.append
    monkeypatch.setattr(spine._event_journal, "append", lambda event: (_ for _ in ()).throw(OSError("disk busy")))
    record = remember(spine)
    assert record["persisted"] is False
    assert spine.get_status()["persistence"]["pending_writes"] == 1
    monkeypatch.setattr(spine._event_journal, "append", append)
    spine.inject_system_event("connection_restored")
    assert spine.get_status()["persistence"]["pending_writes"] == 0
    assert spine.get_status()["persistence"]["failed_writes"] == 1
    assert spine.get_status()["persistence"]["error"] == ""
    assert restore(spine, monkeypatch).list_intentions(scope())[0]["intention_id"] == record["intention_id"]


def test_journal_projection_and_event_commit_together(spine, monkeypatch):
    import core.miya_life_journal as journal_module

    reducer = journal_module.project_intention
    monkeypatch.setattr(journal_module, "project_intention", lambda *args: (_ for _ in ()).throw(OSError("projection failed")))
    record = remember(spine)
    assert spine._event_journal.recent() == []
    assert spine._event_journal.load_intentions() == []
    monkeypatch.setattr(journal_module, "project_intention", reducer)
    assert spine.flush_event_journal()
    assert spine._event_journal.load_intentions()[0]["intention_id"] == record["intention_id"]


def test_old_journal_migrates_without_broadening_explicit_sessions(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE life_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                     event_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL, platform TEXT NOT NULL,
                     user_id TEXT NOT NULL, group_id TEXT NOT NULL, data TEXT NOT NULL)""")
    journal = LifeEventJournal(path)
    event = MiyaEvent(LifeEventType.ACTION_RESULT, source="web", payload={
        "user_id": "owner", "action": "send_materials", "result": {"success": False},
    })
    assert journal.append(event)
    assert len(journal.recall_actions(user_id="owner", platform="web", session_id="user_owner")) == 1
    assert journal.recall_actions(user_id="owner", platform="web", session_id="explicit-private") == []


def test_action_recall_filters_relevance_and_explicit_session(spine):
    for session, summary in [("session-a", "资料发送失败"), ("session-a", "天气查询成功"), ("session-b", "资料发送成功")]:
        spine.emit_event(MiyaEvent(LifeEventType.ACTION_RESULT, source="web", payload={
            **scope(session_id=session), "action": "test", "result": {"summary": summary},
        }))
    found = spine.recall_action_experiences(user_id="owner", platform="web", session_id="session-a", query="之前的资料呢")
    assert len(found) == 1 and found[0]["payload"]["result"]["summary"] == "资料发送失败"
    assert spine.recall_action_experiences(user_id="owner", platform="web", session_id="session-a", query="音乐") == []


def test_emotion_projection_is_scoped_non_accumulating_and_decays(spine):
    record = remember(spine)
    current = {"joy": 0.5, "sadness": 0.2}
    record.update(last_result={"success": False}, evidence_event_id="receipt", evidence_at=100, status="waiting")
    first = experience_emotion(current, [record], now=100)
    assert experience_emotion(current, [record], now=100) == first
    assert current == {"joy": 0.5, "sadness": 0.2}
    assert first["current"]["sadness"] > experience_emotion(current, [record], now=21700)["current"]["sadness"]
    assert experience_emotion(current, [record], now=100000)["current"] == current
    assert experience_emotion(current, [], now=100)["evidence_event_ids"] == []


@pytest.mark.asyncio
async def test_experience_budget_preserves_latest_dialogue_and_valid_json(spine, monkeypatch):
    remember(spine)
    builder = ContextBuilder(None, emotion=Emotion())
    dialogue = [SimpleNamespace(role="user", content=f"近期对话 {index}", timestamp=str(index), metadata={}) for index in range(20)]
    monkeypatch.setattr(builder, "_load_messages", AsyncMock(return_value=dialogue))
    request = ConsumerRequest("main", max_messages=8, max_tokens=1200, experience_max_tokens=500)
    allocation = await builder.build("session-a", user_id="owner", platform="web", consumers=[request])
    result = allocation.slices["main"]
    assert len(result.messages) <= 8 and result.token_count <= 1200
    assert any(message["content"] == "近期对话 19" for message in result.messages)
    evidence = next(message for message in result.messages if message["metadata"].get("source") == "life_intention")
    assert evidence["role"] == "user"
    assert json.loads(evidence["content"].split("】", 1)[1])["title"] == "发送资料"
    other = await builder.build("session-b", user_id="owner", platform="web", consumers=[request])
    assert all(item["metadata"].get("source") != "life_intention" for item in other.get("main"))


def coordinator(sender, **config):
    instance = ProactiveCoordinator()
    instance.configure(send_callback=sender, config={
        "quiet_hours_enabled": False, "min_interval_seconds": 0, "same_source_interval_seconds": 0,
        "max_messages_per_hour": 10, **config,
    })
    return instance


def make_due(spine, monkeypatch):
    record = remember(spine, follow_up=True)
    future = time.time() + FOLLOWUP_INTERVAL + 1
    monkeypatch.setattr(time, "time", lambda: future)
    spine._phase = LifecyclePhase.RUNNING
    return record


@pytest.mark.asyncio
async def test_followup_queue_is_not_goal_completion_and_restart_keeps_cooldown(spine, monkeypatch):
    record = make_due(spine, monkeypatch)
    sender = AsyncMock(return_value=DeliveryResult("queued", "delivery-1"))
    organ = MiyaContinuityOrgan(coordinator(sender))
    organ.bind_spine(spine)
    result = await organ.follow_up(record)
    assert result.status == "queued"
    sender.assert_awaited_once()
    assert sender.await_args.args[1:4] == ("owner", "private", "web")
    assert not sender.await_args.args[0].startswith("{")
    pending = spine.list_intentions(scope())[0]
    assert pending["status"] == "active" and pending["followup_count"] == 1
    restarted = restore(spine, monkeypatch)
    assert restarted.due_intentions() == []
    assert restarted.list_intentions(scope())[0]["followup_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["quiet", "quota", "skip"])
async def test_suppressed_followup_keeps_promise_without_consuming_attempts(spine, monkeypatch, reason):
    record = make_due(spine, monkeypatch)
    sender = AsyncMock(return_value=True)
    policy = coordinator(sender)
    if reason == "quiet":
        policy._in_quiet_hours = lambda: True
    elif reason == "quota":
        policy._sent_at.extend([time.time()] * policy._max_per_hour)
    else:
        policy._decide_message = AsyncMock(return_value=None)
    organ = MiyaContinuityOrgan(policy)
    organ.bind_spine(spine)
    assert not await organ.follow_up(record)
    sender.assert_not_awaited()
    pending = spine.list_intentions(scope())[0]
    assert pending["followup_count"] == 0 and pending["next_followup_at"] > time.time()


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["pause", "new_message", "complete"])
async def test_followup_rechecks_user_changes_after_model_decision(spine, monkeypatch, interruption):
    record = make_due(spine, monkeypatch)
    sender = AsyncMock(return_value=True)
    policy = coordinator(sender)
    entered, release = asyncio.Event(), asyncio.Event()

    async def decide(event):
        entered.set()
        await release.wait()
        return "要继续吗？"

    policy._decide_message = decide
    organ = MiyaContinuityOrgan(policy)
    organ.bind_spine(spine)
    task = asyncio.create_task(organ.follow_up(record))
    await entered.wait()
    if interruption == "pause":
        spine.manage_intention("pause", scope(), intention_id=record["intention_id"])
    elif interruption == "complete":
        spine.manage_intention("confirm", scope(current_input="已经收到了"),
                               intention_id=record["intention_id"], evidence="已经收到了")
    else:
        spine.inject_user_message("先不要跟进", "owner", source="web")
    release.set()
    await task
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_abandoned_and_non_opted_in_promises_have_no_followups(spine):
    record = remember(spine)
    assert spine.due_intentions(now=time.time() + 86400) == []
    spine.manage_intention("pause", scope(), intention_id=record["intention_id"])
    assert spine.due_intentions(now=time.time() + 86400) == []
    spine.manage_intention("abandon", scope(), intention_id=record["intention_id"])
    assert spine.list_intentions(scope()) == []


@pytest.mark.asyncio
async def test_group_children_start_and_isolate_failed_or_mutating_sibling(spine):
    class Child(MiyaOrgan):
        def __init__(self, name):
            super().__init__(name)
            self.events = []

        def on_life_event(self, event, state):
            self.events.append(event)
            if self.name == "bad":
                event.payload["message"] = "被修改"
                raise RuntimeError("broken child")

    bad, good = Child("bad"), Child("good")
    spine.register_organ(MiyaOrganGroup("group", [bad, good]))
    await spine.get_organ("group").on_start()
    assert bad.started and good.started and good.spine is spine
    spine.inject_user_message("原始消息", "owner", source="web")
    assert good.events[0].payload["message"] == "原始消息"
    assert spine.event_history[0].payload["message"] == "原始消息"
    await spine.get_organ("group").on_shutdown()
    assert not good.started


def test_inbound_events_do_not_hide_a_stalled_heartbeat(spine):
    from core.observatory import ObservatoryService

    spine._phase = LifecyclePhase.RUNNING
    spine._tick_count = 10
    spine._last_heartbeat_at = time.time() - 100
    spine.inject_user_message("新消息", "owner", source="web")
    service = ObservatoryService(spine=spine)
    assert time.time() - spine.current_state.timestamp < 2
    assert service._lifecycle()["phase"] is None


def test_tool_is_available_in_normal_and_minimal_platform_schemas(registry):
    from hub.platform_tools import PlatformToolsManager

    manager = PlatformToolsManager(SimpleNamespace(get_tools_schema=registry.get_tools_schema))
    for platform in ("web", "terminal", "qqofficial"):
        assert any(item["function"]["name"] == "manage_intention"
                   for item in manager.get_platform_specific_tools(platform))
        assert any(item["function"]["name"] == "manage_intention"
                   for item in manager.get_minimal_chat_tools(platform))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "cancel"])
async def test_unknown_external_effect_stays_unconfirmed(spine, registry, failure):
    remember(spine)
    execute = AsyncMock(side_effect=TimeoutError("ack missing") if failure == "timeout" else asyncio.CancelledError())
    registry.tools["send_materials"] = SimpleNamespace(execute=execute)
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await registry.execute_tool("send_materials", ToolContext(**scope()))
    else:
        await registry.execute_tool("send_materials", ToolContext(**scope()))
    record = spine.list_intentions(scope())[0]
    assert record["status"] == "needs_confirmation"
    assert record["last_result"]["success"] is None
    assert record["pending_action_id"] == ""


@pytest.mark.asyncio
async def test_pausing_inflight_action_preserves_late_receipt(spine, registry):
    record = remember(spine, follow_up=True)
    entered, release = asyncio.Event(), asyncio.Event()

    async def execute(args, context):
        entered.set()
        await release.wait()
        return {"success": True}

    registry.tools["send_materials"] = SimpleNamespace(execute=execute)
    task = asyncio.create_task(registry.execute_tool("send_materials", ToolContext(**scope())))
    await entered.wait()
    spine.manage_intention("pause", scope(), intention_id=record["intention_id"])
    with pytest.raises(ValueError, match="尚未核实"):
        spine.manage_intention("resume", scope(), intention_id=record["intention_id"])
    release.set()
    await task
    pending = spine.list_intentions(scope())[0]
    assert pending["status"] == "paused" and pending["last_result"]["success"] is True
    assert pending["pending_action_id"] == "" and pending["next_followup_at"] is None


def test_restart_preserves_pause_and_allows_grounded_retry_after_interruption(spine, monkeypatch):
    record = remember(spine, follow_up=True)
    spine.emit_event(MiyaEvent(LifeEventType.ACTION_STARTED, correlation_id="turn-1", payload={
        **scope(), "intention_id": record["intention_id"], "action": "send_materials", "action_id": "interrupted",
    }))
    spine.manage_intention("pause", scope(), intention_id=record["intention_id"])
    restarted = restore(spine, monkeypatch)
    pending = restarted.list_intentions(scope())[0]
    assert pending["status"] == "paused" and pending["execution_interrupted"]
    assert restarted.due_intentions(now=time.time() + 86400) == []
    result = restarted.manage_intention("retry", scope(current_input="确认没有收到，请重试"),
                                       intention_id=record["intention_id"], evidence="确认没有收到，请重试")
    assert result["status"] == "active" and result["pending_action_id"] == ""


@pytest.mark.asyncio
async def test_followup_does_not_send_when_reservation_cannot_be_saved(spine, monkeypatch):
    record = make_due(spine, monkeypatch)
    monkeypatch.setattr(spine._event_journal, "append", lambda event: (_ for _ in ()).throw(OSError("disk full")))
    sender = AsyncMock(return_value=True)
    organ = MiyaContinuityOrgan(coordinator(sender))
    organ.bind_spine(spine)
    assert await organ.follow_up(record) is False
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_heartbeat_drives_followup_and_decision_organ_projects_emotion(spine, monkeypatch):
    from core.miya_decision_hub_organ import MiyaDecisionHubOrgan

    make_due(spine, monkeypatch)
    sender = AsyncMock(return_value=DeliveryResult("queued", "one"))
    organ = MiyaContinuityOrgan(coordinator(sender))
    decision = MiyaDecisionHubOrgan()
    emotion = Emotion()
    decision.bind_decision_hub(SimpleNamespace(emotion=emotion))
    spine.register_organs(organ, decision)
    await organ.on_start()
    await decision.on_start()
    spine._loop = asyncio.get_running_loop()
    spine._last_interaction = 0
    spine.inject_user_message("暂存的输入", "owner", source="web", context={"session_id": "session-a"})
    spine._last_interaction = 0
    spine._broadcast(spine.current_state)
    assert organ._future is not None
    await asyncio.wrap_future(organ._future)
    sender.assert_awaited_once()
    assert decision.get_cached_state().life_state.mood["source"] == "emotion_with_experiences"
    await organ.on_shutdown()


@pytest.mark.asyncio
async def test_due_intention_can_be_followed_up_while_spine_sleeps(spine, monkeypatch):
    record = make_due(spine, monkeypatch)
    spine._phase = LifecyclePhase.SLEEP
    sender = AsyncMock(return_value=DeliveryResult("sent", "sleep-followup"))
    organ = MiyaContinuityOrgan(coordinator(sender))
    organ.bind_spine(spine)

    result = await organ.follow_up(record)

    assert result.status == "sent"
    sender.assert_awaited_once()


@pytest.mark.asyncio
async def test_followup_limit_survives_restart_and_stops_without_abandoning_promise(spine, monkeypatch):
    record = make_due(spine, monkeypatch)
    sender = AsyncMock(return_value=True)
    organ = MiyaContinuityOrgan(coordinator(sender))
    organ.bind_spine(spine)
    assert await organ.follow_up(record)
    future = time.time() + 3601  # 相同跟进事实仍受协调器的一小时去重约束。
    monkeypatch.setattr(time, "time", lambda: future)
    assert await organ.follow_up(record)
    restarted = restore(spine, monkeypatch)
    assert restarted.list_intentions(scope())[0]["status"] == "active"
    assert restarted.list_intentions(scope())[0]["followup_count"] == 2
    assert restarted.due_intentions(now=future + 86400) == []
    assert sender.await_count == 2


@pytest.mark.asyncio
async def test_followup_stays_on_original_platform_when_offline(spine, monkeypatch):
    from hub.decision_hub import DecisionHub

    hub = object.__new__(DecisionHub)
    hub.onebot_client = None
    hub.platform_registry = SimpleNamespace(get=lambda _: None)
    hub._get_platform_routing_config = lambda: {"mode": "priority"}
    hub._send_by_priority = AsyncMock(return_value=True)
    monkeypatch.setattr("core.management_api.get_management_api", lambda: None)
    result = await hub._dispatch_proactive_message(
        "资料仍待核实", "owner-openid", platform="qqofficial", trigger_type="intention_followup",
        delivery_id="strict-followup",
    )
    assert result.status == "failed"
    hub._send_by_priority.assert_not_awaited()
    event = spine.event_history[-1]
    assert event.payload["platform"] == "qqofficial" and event.payload["user_id"] == "owner-openid"


@pytest.mark.asyncio
async def test_followup_retries_stop_after_user_pause_and_keep_attempt_count(spine, monkeypatch):
    record = make_due(spine, monkeypatch)

    async def sender(*args, **kwargs):
        spine.manage_intention("pause", scope(), intention_id=record["intention_id"])
        return False

    send = AsyncMock(side_effect=sender)
    organ = MiyaContinuityOrgan(coordinator(send, send_attempts=2))
    organ.bind_spine(spine)
    assert await organ.follow_up(record) is False
    send.assert_awaited_once()
    pending = spine.list_intentions(scope())[0]
    assert pending["status"] == "paused" and pending["followup_count"] == 1
