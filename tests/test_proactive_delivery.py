"""主动链路的失败、并发、幂等投递和热更新回归测试。"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.proactive_chat import ChatContext, ProactiveChatSystem, ProactiveResult, _normalize_config
from core.proactive_coordinator import ProactiveCoordinator
from core.proactive_delivery import DeliveryResult, enqueue_delivery, take_pending_deliveries


def coordinator(callback, **config):
    instance = ProactiveCoordinator()
    instance.configure(send_callback=callback, default_target_id="owner", config={
        "max_messages_per_hour": 10, "max_messages_per_source_per_hour": 10,
        "min_interval_seconds": 0, "same_source_interval_seconds": 0, "quiet_hours_enabled": False,
        **config,
    })
    return instance


@pytest.fixture
def chat(monkeypatch):
    instance = object.__new__(ProactiveChatSystem)
    instance._initialized = False
    instance.__init__()
    monkeypatch.setattr(instance, "reload_config_if_changed", lambda **kwargs: False)
    return instance


@pytest.fixture
def hub(monkeypatch):
    from hub.decision_hub import DecisionHub

    instance = object.__new__(DecisionHub)
    instance.platform_registry = SimpleNamespace(get=lambda platform: None)
    instance.onebot_client = None
    instance.proactive_coordinator = coordinator(AsyncMock(return_value=True))
    instance._mobile_pending = {}
    instance.memory_manager = SimpleNamespace(store_unified_memory=AsyncMock())
    instance._resolve_cross_platform_target_id = lambda user, platform: user
    instance._get_platform_routing_config = lambda: {"mode": "priority"}
    instance._send_by_priority = AsyncMock(return_value=False)
    monkeypatch.setattr("core.management_api.get_management_api", lambda: None)
    return instance


@pytest.mark.parametrize("result", [False, None, DeliveryResult("failed"), DeliveryResult("rejected")])
@pytest.mark.parametrize("event", [False, True])
def test_failed_delivery_leaves_no_budget_or_dedup_record(result, event):
    outlet = AsyncMock(return_value=result)
    instance = coordinator(outlet, max_messages_per_hour=1)

    async def run():
        if event:
            delivered = await instance.submit_event({"source": "test", "event": "arrival"}, key="arrival")
        else:
            delivered = await instance.submit_message("hello", key="arrival")
        assert not delivered
        assert not instance._sent_at
        assert not instance._reservations
        assert not instance._last_by_key
        assert not instance._fingerprints
        assert all(not bucket for bucket in instance._source_counts.values())
        outlet.return_value = True
        assert await instance.submit_message("hello", key="arrival")

    asyncio.run(run())


@pytest.mark.parametrize("failure", [RuntimeError("offline"), asyncio.TimeoutError()])
def test_exceptions_release_reservations(failure):
    instance = coordinator(AsyncMock(side_effect=failure))
    assert asyncio.run(instance.submit_message("hello", key="test")) is False
    assert not instance._sent_at and not instance._reservations


def test_pending_send_neither_blocks_other_sources_nor_overbooks_budget():
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def outlet(message, *args):
            if message == "slow":
                started.set()
                await release.wait()
            return True

        instance = coordinator(outlet, max_messages_per_hour=2)
        slow = asyncio.create_task(instance.submit_message("slow", key="slow", source="camera"))
        await started.wait()
        assert await asyncio.wait_for(instance.submit_message("fast", key="fast", source="soul"), 0.2)
        assert not await instance.submit_message("third", key="third", source="earth")
        release.set()
        assert await slow
        assert len(instance._sent_at) == 2
        assert not instance._reservations

    asyncio.run(run())


def test_same_inflight_fact_is_not_sent_twice():
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def outlet(*args):
            started.set()
            await release.wait()
            return True

        instance = coordinator(outlet)
        first = asyncio.create_task(instance.submit_message("hello", key="same"))
        await started.wait()
        assert not await instance.submit_message("hello", key="same")
        release.set()
        assert await first
        assert len(instance._sent_at) == 1

    asyncio.run(run())


def test_timeout_and_cancellation_release_budget():
    async def run():
        started = asyncio.Event()

        async def outlet(*args):
            started.set()
            await asyncio.sleep(10)

        instance = coordinator(outlet, send_timeout_seconds=0.01)
        assert not await instance.submit_message("timeout", key="timeout")
        assert not instance._reservations and not instance._sent_at
        instance.configure(config={"send_timeout_seconds": 10})
        started.clear()
        task = asyncio.create_task(instance.submit_message("cancel", key="cancel"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not instance._reservations and not instance._sent_at

    asyncio.run(run())


def test_safe_false_retry_reuses_delivery_id_and_commits_once():
    identities = []

    async def outlet(*args, delivery_id):
        identities.append(delivery_id)
        return len(identities) > 1

    instance = coordinator(outlet, send_attempts=2)
    assert asyncio.run(instance.submit_message("hello", key="retry"))
    assert len(identities) == 2 and len(set(identities)) == 1
    assert len(instance._sent_at) == 1


def test_default_owner_and_queued_status_are_preserved():
    outlet = AsyncMock(return_value=DeliveryResult("queued", "queue-id"))
    instance = coordinator(outlet)
    result = asyncio.run(instance.submit_message("hello", key="queue", detailed=True))
    assert result.status == "queued"
    assert outlet.call_args.args[1] == "owner"
    assert len(instance._sent_at) == 1


def test_invalid_coordinator_config_is_atomic():
    instance = coordinator(AsyncMock(return_value=True))
    before = instance.__dict__.copy()
    with pytest.raises(ValueError):
        instance.configure(config={"enabled": False, "max_messages_per_hour": "bad"})
    assert instance.__dict__ == before


def test_model_failure_does_not_send_raw_json():
    outlet = AsyncMock(return_value=True)
    instance = coordinator(outlet)
    instance.configure(ai_client=SimpleNamespace(chat=AsyncMock(side_effect=RuntimeError("model offline"))))
    assert not asyncio.run(instance.submit_event({"source": "camera", "facts": "private"}, key="event"))
    outlet.assert_not_called()
    assert not instance._sent_at


def test_single_flight_covers_decision_and_awaiting_delivery(chat, monkeypatch):
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def decide(target, message):
            started.set()
            await release.wait()
            chat._record_trigger(target)
            return ProactiveResult(True, "hello", "ai", ChatContext("private", target))

        monkeypatch.setattr(chat, "_check_and_respond_once", decide)
        monkeypatch.setattr(chat, "_send_callback", AsyncMock(return_value=True))
        first = asyncio.create_task(chat.check_and_respond(42))
        await started.wait()
        assert await chat.check_and_respond(42) is None
        release.set()
        proposal = await first
        assert await chat.check_and_respond(42) is None
        assert await chat._deliver_background_result(42, proposal)
        assert proposal.delivered and not chat._proposals
        assert await chat._deliver_background_result(42, proposal)
        assert chat._send_callback.await_count == 1

    asyncio.run(run())


def test_rejected_context_proposal_restores_facts_and_refunds_once(chat, monkeypatch):
    target = 42
    context = ChatContext("private", target, user_expectation="lunch")
    chat._context_cache[target] = context
    chat._record_trigger(target)

    async def decide(*args):
        context.user_expectation = None
        chat._record_trigger(target)
        chat._record_trigger_by_type(target, "context")
        chat._record_sent_message(target, "hello")
        chat._is_duplicate(target, "hello")
        return ProactiveResult(True, "hello", "context", context)

    monkeypatch.setattr(chat, "_check_and_respond_once", decide)
    monkeypatch.setattr(chat, "_send_callback", AsyncMock(return_value=False))

    async def run():
        proposal = await chat.check_and_respond(target)
        assert not await chat._deliver_background_result(target, proposal)
        assert not await chat._deliver_background_result(target, proposal)
        assert context.user_expectation == "lunch"
        assert len(chat._hourly_count[target]) == 1
        assert chat._daily_count[target]["count"] == 1
        assert not chat._message_cache
        assert not chat._sent_messages_history[target]
        assert not chat._proposals

    asyncio.run(run())


def test_camera_failure_does_not_double_refund(chat, monkeypatch):
    target = 42
    for _ in range(2):
        chat._record_trigger(target)
    result = ProactiveResult(True, "camera hello", "camera_aware", ChatContext("private", target),
                             rollback=lambda: chat._forget_camera_proposal(target, "camera hello"))
    monkeypatch.setattr(chat, "_send_callback", AsyncMock(return_value=False))
    assert not asyncio.run(chat._deliver_background_result(target, result))
    assert len(chat._hourly_count[target]) == 1


def test_decision_timeout_releases_target(chat, monkeypatch):
    async def decide(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr(chat, "_decision_timeout", 0.01)
    monkeypatch.setattr(chat, "_check_and_respond_once", decide)
    assert asyncio.run(chat.check_and_respond(42)) is None
    assert not chat._checking_targets and not chat._proposals


def test_daily_budget_resets_without_inbound_message(chat):
    chat._daily_count[42] = {"date": datetime.now().date() - timedelta(days=1), "count": 40}
    chat._record_trigger(42)
    assert chat._daily_count[42]["count"] == 1


def test_live_config_updates_policy_without_resetting_budget(chat, monkeypatch):
    instance = coordinator(AsyncMock(return_value=True))
    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator", lambda: instance)
    chat._record_trigger(42)
    chat.apply_config(_normalize_config({
        "enabled": False, "check_interval": 3, "max_hourly_messages": 7,
        "camera_aware": {"enabled": False}, "coordination": {"max_messages_per_hour": 9},
    }))
    assert not chat.is_enabled() and not instance._enabled
    assert chat._poll_interval == 3 and chat._max_hourly == 7
    assert not chat._camera_aware_config["enabled"]
    assert instance._max_per_hour == 9 and len(chat._hourly_count[42]) == 1


def test_malformed_or_invalid_yaml_keeps_last_config(chat, tmp_path, monkeypatch):
    path = tmp_path / "proactive.yaml"
    monkeypatch.setattr(chat, "_config_path", path)
    before = chat._config
    path.write_text("proactive_chat: [broken", encoding="utf-8")
    assert not ProactiveChatSystem.reload_config_if_changed(chat, force=True)
    assert chat._config is before
    path.write_text("proactive_chat:\n  check_interval: -1", encoding="utf-8")
    assert not ProactiveChatSystem.reload_config_if_changed(chat, force=True)
    assert chat._config is before


def test_valid_yaml_hot_reload_is_idempotent(chat, tmp_path, monkeypatch):
    instance = coordinator(AsyncMock(return_value=True))
    monkeypatch.setattr("core.proactive_coordinator.get_proactive_coordinator", lambda: instance)
    path = tmp_path / "proactive.yaml"
    path.write_text("proactive_chat:\n  check_interval: 3\n  enabled: false", encoding="utf-8")
    monkeypatch.setattr(chat, "_config_path", path)
    assert ProactiveChatSystem.reload_config_if_changed(chat, force=True)
    assert not chat.is_enabled() and chat._poll_interval == 3
    assert not ProactiveChatSystem.reload_config_if_changed(chat)


def test_queue_is_bounded_deduplicated_and_expires(monkeypatch):
    pending = {}
    monkeypatch.setattr("core.proactive_delivery.time.time", lambda: 1000)
    for index in range(105):
        enqueue_delivery(pending, "owner", str(index), str(index))
    enqueue_delivery(pending, "owner", "duplicate", "104")
    assert len(pending["owner"]) == 100
    assert pending["owner"][-1]["message"] == "104"
    monkeypatch.setattr("core.proactive_delivery.time.time", lambda: 1601)
    assert take_pending_deliveries(pending, "owner") == []


@pytest.mark.parametrize("connected", [False, True])
def test_desktop_uses_push_or_queue_but_not_both(hub, monkeypatch, connected):
    management = SimpleNamespace(broadcast_message=AsyncMock(return_value=int(connected)))
    monkeypatch.setattr("core.management_api.get_management_api", lambda: management)
    result = asyncio.run(hub._dispatch_proactive_message("hello", "owner", platform="desktop", delivery_id="one"))
    assert result.status == ("sent" if connected else "queued")
    assert bool(hub._mobile_pending) is not connected
    assert management.broadcast_message.await_count == 1
    assert hub.memory_manager.store_unified_memory.await_count == 1
    assert hub.memory_manager.store_unified_memory.call_args.args[0]["_meta"]["delivery_status"] == result.status


def test_group_without_group_sender_never_falls_back_to_private(hub):
    platform = SimpleNamespace(is_online=True, send_private_message=AsyncMock(return_value=True))
    hub.platform_registry = SimpleNamespace(get=lambda name: platform)
    result = asyncio.run(hub._dispatch_proactive_message("group hello", "group", "group", "qq"))
    assert result.status == "failed"
    platform.send_private_message.assert_not_called()


def test_group_send_failure_has_no_private_fallback_or_fake_memory(hub):
    platform = SimpleNamespace(is_online=True, send_group_message=AsyncMock(return_value=False))
    hub.platform_registry = SimpleNamespace(get=lambda name: platform)
    result = asyncio.run(hub._dispatch_proactive_message("group hello", "group", "group", "qq", delivery_id="group"))
    assert result.status == "failed"
    assert not hub._mobile_pending
    hub.memory_manager.store_unified_memory.assert_not_called()
    hub._send_by_priority.assert_not_called()


def test_concurrent_dispatch_of_same_id_has_one_send_and_one_memory(hub):
    async def send(*args):
        await asyncio.sleep(0.01)
        return True

    platform = SimpleNamespace(is_online=True, send_private_message=AsyncMock(side_effect=send))
    hub.platform_registry = SimpleNamespace(get=lambda name: platform)

    async def run():
        results = await asyncio.gather(*[
            hub._dispatch_proactive_message("hello", "owner", platform="qq", delivery_id="same")
            for _ in range(4)
        ])
        assert all(result.status == "sent" for result in results)

    asyncio.run(run())
    assert platform.send_private_message.await_count == 1
    assert hub.memory_manager.store_unified_memory.await_count == 1


def test_owner_alias_does_not_mirror_or_leak_queue(hub):
    result = asyncio.run(hub._dispatch_proactive_message("hello", "owner", platform="desktop", delivery_id="one"))
    assert result.status == "queued"
    assert list(hub._mobile_pending) == ["owner"]
    assert hub.take_pending_proactive_messages("stranger") == []
    assert len(hub.take_pending_proactive_messages("default")) == 1
    assert hub.take_pending_proactive_messages("owner") == []


def test_failed_dispatch_can_be_retried_with_same_id(hub):
    platform = SimpleNamespace(is_online=True, send_group_message=AsyncMock(side_effect=[False, True]))
    hub.platform_registry = SimpleNamespace(get=lambda name: platform)

    async def run():
        assert not await hub._dispatch_proactive_message("hello", "group", "group", "qq", delivery_id="retry")
        assert await hub._dispatch_proactive_message("hello", "group", "group", "qq", delivery_id="retry")

    asyncio.run(run())
    assert platform.send_group_message.await_count == 2
    assert hub.memory_manager.store_unified_memory.await_count == 1


def test_memory_failure_after_send_never_causes_a_resend(hub):
    platform = SimpleNamespace(is_online=True, send_private_message=AsyncMock(return_value=True))
    hub.platform_registry = SimpleNamespace(get=lambda name: platform)
    hub.memory_manager.store_unified_memory.side_effect = RuntimeError("memory offline")

    async def run():
        assert await hub._dispatch_proactive_message("hello", "owner", platform="qq", delivery_id="same")
        assert await hub._dispatch_proactive_message("hello", "owner", platform="qq", delivery_id="same")

    asyncio.run(run())
    assert platform.send_private_message.await_count == 1


def test_management_counts_actual_socket_sends_and_cleans_dead_clients():
    from core.management_api import ManagementAPI

    instance = object.__new__(ManagementAPI)
    live, dead, other = AsyncMock(), AsyncMock(), AsyncMock()
    dead.send_json.side_effect = RuntimeError("closed")
    instance._ws_clients = {live, dead, other}
    instance._ws_client_types = {live: "desktop", dead: "desktop", other: "mobile"}
    instance._ws_client_users = {live: "owner", dead: "owner", other: "owner"}
    assert asyncio.run(instance.push_proactive_message("owner", "hello", delivery_id="one")) == 1
    assert dead not in instance._ws_clients and dead not in instance._ws_client_types
    other.send_json.assert_not_called()
    assert live.send_json.call_args.args[0]["data"]["delivery_id"] == "one"
    assert asyncio.run(instance.broadcast_message("broadcast", message_id="two")) == 2
    instance._ws_clients.clear()
    assert asyncio.run(instance.broadcast_message("offline")) == 0


def test_same_background_result_is_delivered_once_under_concurrency(chat):
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def send(*args, **kwargs):
            started.set()
            await release.wait()
            return True

        chat._send_callback = send
        result = ProactiveResult(True, "hello", "ai")
        first = asyncio.create_task(chat._deliver_background_result(1, result))
        await started.wait()
        second = asyncio.create_task(chat._deliver_background_result(1, result))
        release.set()
        assert await asyncio.gather(first, second) == [True, True]
        assert result.delivered

    asyncio.run(run())


def test_normal_reply_path_uses_same_proposal_delivery(hub):
    proposal = ProactiveResult(True, "followup", "ai", ChatContext("private", "owner"))
    chat = SimpleNamespace(
        update_context=lambda *args: None, record_message=AsyncMock(),
        check_and_respond=AsyncMock(return_value=proposal),
        _deliver_background_result=AsyncMock(return_value=False),
    )
    hub.proactive_chat = chat
    result = asyncio.run(hub._handle_proactive_chat({"user_id": "owner", "platform": "desktop"}, "hello"))
    assert result is None
    chat._deliver_background_result.assert_awaited_once_with("owner", proposal)
    hub.memory_manager.store_unified_memory.assert_not_called()
