"""真实工具出口、投递结果、持久经历与召回的闭环回归。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core import miya_spine
from core.miya_action import tool_outcome, track_action
from core.miya_life_event import LifeEventType, MiyaEvent
from core.miya_life_journal import LifeEventJournal
from core.miya_soul_state import LifecyclePhase
from core.miya_spine import MiyaSpine
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.registry import ToolRegistry


@pytest.fixture
def spine(tmp_path, monkeypatch):
    instance = MiyaSpine(event_journal=LifeEventJournal(tmp_path / "life.sqlite3"))
    monkeypatch.setattr(miya_spine, "_spine_instance", instance)
    return instance


@pytest.fixture
def registry():
    instance = ToolRegistry()
    instance._check_tool_permission = AsyncMock(return_value={"allowed": True})
    return instance


def results(spine):
    return [event for event in spine.event_history if event.event_type == LifeEventType.ACTION_RESULT]


def tool_context(**kwargs):
    return ToolContext(platform="web", user_id="owner", request_id="request-1", **kwargs)


def register(registry, execute):
    registry.tools["test"] = SimpleNamespace(execute=execute)


@pytest.mark.parametrize(("raw", "status", "success"), [
    ({"success": True}, "succeeded", True),
    ({"success": False}, "failed", False),
    ('{"status": "error", "error": "offline"}', "failed", False),
    ({"status": "queued", "success": True}, "queued", None),
    ({"status": "timed_out", "success": False, "error": "timeout"}, "timed_out", None),
    ({"status": "cancelled", "success": False}, "cancelled", None),
    ({"success": True, "stderr": "warning only"}, "succeeded", True),
    ("MCP 调用异常: server unavailable", "failed", False),
    ("没有错误或失败的正常说明", "completed", None),
    ("暂无记忆", "completed", None),
    ("❌ 参数错误", "failed", False),
    (True, "succeeded", True),
    (False, "failed", False),
    (None, "completed", None),
])
def test_tool_outcome_does_not_invent_success_or_match_arbitrary_words(raw, status, success):
    result = tool_outcome(raw)
    assert (result["status"], result["success"]) == (status, success)


@pytest.mark.asyncio
async def test_registry_result_closes_loop_and_keeps_original_message(registry, spine):
    spine.inject_user_message("执行", "owner", source="web", correlation_id="request-1")
    execute = AsyncMock(return_value={"success": False, "error": "offline"})
    register(registry, execute)
    result = await registry.execute_tool("test", tool_context(), ignored="never-persist-this-argument")
    assert result["success"] is False
    execute.assert_awaited_once()
    action = results(spine)[0]
    started = next(event for event in spine.event_history if event.event_type == LifeEventType.ACTION_STARTED)
    assert action.correlation_id == started.correlation_id == "request-1"
    assert action.payload["action_id"] == started.payload["action_id"]
    assert execute.await_args.args[1].action_id == action.payload["action_id"]
    assert action.payload["result"]["status"] == "failed"
    assert spine.current_state.life_state.open_loops == []
    assert spine.current_state.life_state.last_action["event_id"] == action.event_id
    assert "never-persist-this-argument" not in json.dumps([event.to_dict() for event in spine.event_history])


@pytest.mark.asyncio
async def test_adapter_uses_registry_once_even_when_tool_raises_type_error(registry, spine):
    from core.tool_adapter import ToolAdapter

    execute = AsyncMock(side_effect=TypeError("inside tool after side effect"))
    register(registry, execute)
    adapter = ToolAdapter(enable_native=False)
    adapter.set_tool_registry(registry)
    result = await adapter.execute_tool(
        "test", {}, {"platform": "web", "user_id": "owner", "request_id": "message"}, enable_fallback=False,
    )
    assert "工具执行失败" in result
    execute.assert_awaited_once()
    assert len(results(spine)) == 1
    assert results(spine)[0].payload["result"]["status"] == "failed"
    registry._check_tool_permission.assert_awaited_once()


@pytest.mark.asyncio
async def test_registry_keeps_legacy_signature_without_runtime_retry(registry, spine):
    async def execute(context, **kwargs):
        assert context.user_id == "owner"
        assert kwargs == {"key": "value"}
        return "正常返回"

    register(registry, execute)
    assert await registry.execute_tool("test", tool_context(), key="value") == "正常返回"
    assert results(spine)[0].payload["result"]["success"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "permission", "validation", "timeout"])
async def test_registry_rejection_and_timeout_have_actual_outcomes(registry, spine, failure):
    execute = AsyncMock(return_value="ok")
    register(registry, execute)
    if failure == "missing":
        registry.tools.clear()
    elif failure == "permission":
        registry._check_tool_permission.return_value = {"allowed": False}
    elif failure == "validation":
        registry.tools["test"].validate_args = lambda args: (False, "bad argument")
    elif failure == "timeout":
        execute.side_effect = TimeoutError("too slow")
    await registry.execute_tool("test", tool_context())
    assert results(spine)[0].payload["result"]["status"] == ("timed_out" if failure == "timeout" else "rejected")
    assert execute.await_count == int(failure == "timeout")
    assert not spine.current_state.life_state.open_loops


@pytest.mark.asyncio
async def test_cancellation_is_not_failure_or_success_and_is_propagated(registry, spine):
    entered = asyncio.Event()

    async def execute(args, context):
        entered.set()
        await asyncio.Event().wait()

    register(registry, execute)
    task = asyncio.create_task(registry.execute_tool("test", tool_context()))
    await entered.wait()
    assert len(spine.current_state.life_state.open_loops) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert results(spine)[0].payload["result"]["status"] == "cancelled"
    assert results(spine)[0].payload["result"]["success"] is None
    assert not spine.current_state.life_state.open_loops


@pytest.mark.asyncio
async def test_timeout_in_action_context_propagates_and_records_unknown_effect(spine):
    with pytest.raises(TimeoutError):
        async with track_action("send", {"user_id": "owner", "platform": "web"}, kind="delivery"):
            raise TimeoutError("no acknowledgement")
    assert results(spine)[0].payload["result"]["status"] == "timed_out"
    assert results(spine)[0].payload["result"]["success"] is None


def test_restart_restores_evidence_without_replaying_actions(spine):
    spine.inject_user_message("以前的消息", "owner", source="web")
    spine.inject_action_result("test", {"status": "failed"})
    old_events = spine.event_history
    restored = MiyaSpine(event_journal=LifeEventJournal(spine._event_journal.path))
    assert [event.event_id for event in restored.event_history] == [event.event_id for event in old_events]
    assert restored.current_state.life_state.recent_experience[-1] == old_events[-1].to_dict()
    assert restored.current_state.message_count == 0
    assert restored.current_state.lifecycle_phase == LifecyclePhase.INIT
    assert restored.current_state.life_state.open_loops == []
    # 已持久化事件 ID 重放不再次计数；相同关联 ID 的不同事件仍独立保存。
    restored.emit_event(old_events[0])
    assert restored.current_state.message_count == 0
    assert len(restored.event_history) == 2


def test_durable_dedup_survives_history_eviction(spine):
    event = MiyaEvent(LifeEventType.SYSTEM_EVENT, payload={"event": "first"})
    spine.emit_event(event)
    for index in range(205):
        spine.inject_system_event("other", {"index": index})
    assert all(previous.event_id != event.event_id for previous in spine.event_history)
    spine.emit_event(event)
    assert all(previous.event_id != event.event_id for previous in spine.event_history)
    assert len(spine._event_journal.recent()) == 200


def test_journal_queries_exact_scope_and_handles_quotes(spine):
    for user, platform, group in [
        ("owner", "web", ""), ("other", "web", ""), ("owner", "qqofficial", ""),
        ("owner", "web", "group"), ("owner", "web", "group-2"),
    ]:
        spine.emit_event(MiyaEvent(
            LifeEventType.ACTION_RESULT, source=platform,
            payload={"user_id": user, "platform": platform, "group_id": group,
                     "action": "test", "result": {"status": "failed"}},
        ))
    for group in ["", "group", "group-2"]:
        recalled = spine.recall_action_experiences(user_id="owner", platform="web", group_id=group)
        assert len(recalled) == 1
        assert recalled[0]["payload"]["group_id"] == group
    assert spine.recall_action_experiences(user_id="", platform="web") == []
    assert spine.recall_action_experiences(user_id="owner' OR 1=1 --", platform="web") == []


@pytest.mark.asyncio
async def test_memory_bus_and_prompt_recall_persisted_action_without_dialogue(spine, monkeypatch):
    from hub.context_builder import ContextBuilder
    from memory.api import MemoryBus

    async with track_action("test", {
        "platform": "web", "user_id": "owner", "request_id": "old-message",
    }, kind="tool") as feedback:
        feedback.result = {"status": "failed", "success": False, "summary": "offline"}
    restored = MiyaSpine(event_journal=LifeEventJournal(spine._event_journal.path))
    monkeypatch.setattr(miya_spine, "_spine_instance", restored)
    builder = ContextBuilder(None)
    monkeypatch.setattr(builder, "_load_messages", AsyncMock(return_value=[]))
    allocation = await builder.build("user_owner", user_id="owner", platform="web")
    prompt = allocation.get("default")
    assert len(prompt) == 1
    assert prompt[0]["role"] == "user"
    assert "offline" in prompt[0]["content"]
    assert "old-message" in prompt[0]["content"]
    assert restored.current_state.life_state.memory_focus == [results(restored)[0].event_id]
    assert await MemoryBus.recall_experiences(user_id="stranger", platform="web") == []


@pytest.mark.asyncio
async def test_memory_io_failure_does_not_turn_real_tool_success_into_failure(spine, registry, monkeypatch):
    monkeypatch.setattr(spine._event_journal, "append", lambda event: (_ for _ in ()).throw(OSError("disk full")))
    register(registry, AsyncMock(return_value={"success": True}))
    assert await registry.execute_tool("test", tool_context()) == {"success": True}
    assert results(spine)[0].payload["result"]["status"] == "succeeded"
    assert spine.get_status()["persistence"]["error"] == "disk full"


@pytest.mark.asyncio
async def test_instrumentation_without_spine_does_not_create_one(registry, monkeypatch):
    monkeypatch.setattr(miya_spine, "_spine_instance", None)
    register(registry, AsyncMock(return_value="ok"))
    assert await registry.execute_tool("test", tool_context()) == "ok"
    assert miya_spine.get_existing_spine() is None


@pytest.fixture
def delivery_hub(monkeypatch):
    from hub.decision_hub import DecisionHub

    hub = object.__new__(DecisionHub)
    hub.onebot_client = None
    hub.platform_registry = None
    hub._mobile_pending = {}
    hub.memory_manager = SimpleNamespace(store_unified_memory=AsyncMock())
    hub._get_platform_routing_config = lambda: {"mode": "priority"}
    hub._send_by_priority = AsyncMock(return_value=False)
    hub._resolve_cross_platform_target_id = lambda target, platform: str(target)
    monkeypatch.setattr("core.management_api.get_management_api", lambda: None)
    return hub


@pytest.mark.asyncio
async def test_sent_delivery_retries_are_one_action_and_one_memory(spine, delivery_hub):
    sender = AsyncMock(return_value=True)
    delivery_hub.platform_registry = SimpleNamespace(get=lambda _: SimpleNamespace(
        is_online=True, send_private_message=sender,
    ))
    outcomes = await asyncio.gather(*[
        delivery_hub._dispatch_proactive_message("hello", "owner", platform="web", delivery_id="one")
        for _ in range(3)
    ])
    assert all(result.status == "sent" for result in outcomes)
    sender.assert_awaited_once()
    delivery_hub.memory_manager.store_unified_memory.assert_awaited_once()
    assert len(results(spine)) == 1
    assert results(spine)[0].correlation_id == "one"
    assert results(spine)[0].payload["result"]["success"] is True


@pytest.mark.asyncio
async def test_queue_acceptance_and_claim_are_not_confirmed_delivery(spine, delivery_hub):
    outcome = await delivery_hub._dispatch_proactive_message(
        "hello", "owner", platform="desktop", delivery_id="queued-one",
    )
    assert outcome.status == "queued"
    assert results(spine)[0].payload["result"]["status"] == "queued"
    assert results(spine)[0].payload["result"]["success"] is None
    assert len(await delivery_hub.take_pending_proactive_messages("owner")) == 1
    claimed = results(spine)[-1]
    assert claimed.correlation_id == "queued-one"
    assert claimed.payload["result"]["status"] == "claimed"
    assert claimed.payload["result"]["success"] is None
    assert await delivery_hub.take_pending_proactive_messages("owner") == []
    assert len(results(spine)) == 2


@pytest.mark.asyncio
async def test_failed_send_can_retry_without_falsifying_first_outcome(spine, delivery_hub):
    sender = AsyncMock(side_effect=[False, True])
    delivery_hub.platform_registry = SimpleNamespace(get=lambda _: SimpleNamespace(
        is_online=True, send_group_message=sender,
    ))
    for _ in range(2):
        await delivery_hub._dispatch_proactive_message(
            "hello", "group", chat_type="group", platform="qqofficial", delivery_id="retry",
        )
    events = results(spine)
    assert [event.payload["result"]["status"] for event in events] == ["failed", "sent"]
    assert events[0].payload["action_id"] != events[1].payload["action_id"]
    assert events[0].correlation_id == events[1].correlation_id == "retry"


@pytest.mark.asyncio
async def test_feedback_exception_cannot_break_tool_result(registry, spine, monkeypatch):
    monkeypatch.setattr(spine, "emit_event", lambda event: (_ for _ in ()).throw(RuntimeError("feedback offline")))
    register(registry, AsyncMock(return_value="ok"))
    assert await registry.execute_tool("test", tool_context()) == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmed", [False, True])
async def test_delivery_cancellation_preserves_only_confirmed_result(spine, delivery_hub, confirmed):
    from core.proactive_delivery import DeliveryResult

    entered = asyncio.Event()

    async def send(*args):
        if confirmed:
            delivery_hub._proactive_delivery_results["cancel"] = (0, DeliveryResult("sent", "cancel"))
        entered.set()
        await asyncio.Event().wait()

    delivery_hub._dispatch_proactive_message_once = send
    task = asyncio.create_task(delivery_hub._dispatch_proactive_message(
        "hello", "owner", platform="web", delivery_id="cancel",
    ))
    await entered.wait()
    task.cancel()
    if confirmed:
        assert (await task).status == "sent"
    else:
        with pytest.raises(asyncio.CancelledError):
            await task
    outcome = results(spine)[0].payload["result"]
    assert outcome["status"] == ("sent" if confirmed else "cancelled")
    assert outcome["success"] is (True if confirmed else None)


@pytest.mark.asyncio
async def test_shutdown_spine_does_not_receive_late_action(registry, spine):
    await spine._transition(LifecyclePhase.SHUTDOWN)
    register(registry, AsyncMock(return_value="ok"))
    assert await registry.execute_tool("test", tool_context()) == "ok"
    assert results(spine) == []
