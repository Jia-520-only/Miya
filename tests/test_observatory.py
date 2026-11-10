"""Observatory truthfulness, persistence, streaming and concurrency regressions."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.miya_soul_state import LifecyclePhase, MiyaSoulState
from core.observatory import LAYERS, ObservatoryNoteStore, ObservatoryService
from core.observatory_organ import MiyaObservatoryOrgan, parse_note


def make_service(tmp_path):
    personality = SimpleNamespace(
        current_form="gentle",
        get_form_config=lambda _: {"name": "温柔的弥娅"},
        get_status_for_prompt=lambda: "这是当前温柔人格。",
    )
    hub = SimpleNamespace(personality=personality)
    service = ObservatoryService(hub, store=ObservatoryNoteStore(tmp_path))
    service._platforms = lambda: {"online_count": None, "enabled_count": None}
    service._memory = AsyncMock(return_value={"total": None, "layers": {key: None for key in LAYERS}})
    return service


def test_missing_sources_do_not_become_calm_fifty_or_zero(tmp_path):
    service = make_service(tmp_path)
    result = asyncio.run(service.snapshot())
    assert result["success"] is True
    assert result["emotion"]["name"] is None
    assert result["emotion"]["intensity"] is None
    assert result["memory"]["total"] is None
    assert result["lifecycle"]["phase"] is None
    assert result["platforms"]["enabled_count"] is None
    assert result["availability"] == {
        "persona": True,
        "emotion": False,
        "lifecycle": False,
        "platforms": False,
        "memory": False,
    }


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 0), (0.72, 72), (1, 100), (float("nan"), None), (50, None), (True, None)]
)
def test_emotion_scale_has_an_explicit_boundary(tmp_path, value, expected):
    service = make_service(tmp_path)
    service.hub.emotion = SimpleNamespace(
        get_emotion_state=lambda: {"dominant": "joy", "intensity": value, "current": {"joy": value}}
    )
    result = asyncio.run(service.snapshot())
    assert result["emotion"]["intensity"] == expected
    assert result["emotion"]["emotions"] == ([] if expected is None else [{"name": "joy", "intensity": expected}])


def test_stale_heartbeat_is_unknown_but_sleep_has_its_own_cadence(tmp_path):
    service = make_service(tmp_path)
    state = MiyaSoulState(tick_index=12, timestamp=time.time() - 40, message_count=9)
    service.spine = SimpleNamespace(is_running=lambda: True, current_state=state, phase=LifecyclePhase.IDLE)
    assert service._lifecycle()["phase"] is None
    service.spine.phase = LifecyclePhase.SLEEP
    assert service._lifecycle()["phase"] == "SLEEP"
    assert service._lifecycle()["message_count"] == 9
    state.timestamp = time.time() - 100
    assert service._lifecycle()["phase"] is None


def test_online_platforms_use_registry_statuses_not_configured_count(tmp_path, monkeypatch):
    import core.management_api

    platforms = [{"status": status} for status in ("online", "degraded", "offline", "disabled", "reconnecting")]
    api = SimpleNamespace(daemon=SimpleNamespace(get_platform_status=lambda: platforms))
    monkeypatch.setattr(core.management_api, "get_management_api", lambda: api)
    service = ObservatoryService(store=ObservatoryNoteStore(tmp_path))
    assert service._platforms() == {"online_count": 2, "enabled_count": 4}


def test_shared_snapshot_coalesces_readers(tmp_path):
    service = make_service(tmp_path)

    async def read_together():
        return await asyncio.gather(*(service.snapshot() for _ in range(5)))

    results = asyncio.run(read_together())
    assert service._memory.await_count == 1
    assert all(result["sampled_at"] == results[0]["sampled_at"] for result in results)


def test_daemon_and_web_api_can_read_on_different_event_loops(tmp_path):
    service = make_service(tmp_path)

    async def slow_memory():
        await asyncio.sleep(0.02)
        return {"total": 0, "layers": dict.fromkeys(LAYERS, 0)}

    service._memory = slow_memory

    def read():
        async def read_together():
            return await asyncio.gather(service.snapshot(), service.snapshot())

        return asyncio.run(read_together())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: read(), range(2)))
    assert all(snapshot["memory"]["total"] == 0 for batch in results for snapshot in batch)


def test_memory_counts_all_six_layers_once_instead_of_adding_mirrors(tmp_path):
    from memory.api.bus import MemoryBus
    from memory.core import JsonBackend

    backend = JsonBackend(tmp_path)
    backend._index = {f"id-{index}": {"level": key} for index, key in enumerate(LAYERS)}
    bus = MemoryBus()
    bus._initialized = True
    bus._core = SimpleNamespace(
        backend=backend, sqlite_backend=SimpleNamespace(count=AsyncMock(return_value=6)), _cache={}
    )
    result = asyncio.run(bus.observatory_stats())
    assert result["total"] == 6
    assert result["layers"] == dict.fromkeys(LAYERS, 1)
    bus._core.sqlite_backend.count.assert_not_awaited()


def test_one_failed_source_preserves_other_sources_and_saved_note(tmp_path):
    service = make_service(tmp_path)
    note = {"id": "old", "title": "今夜仍有微光", "body": "佳，愿这一点安静的光陪你慢慢走。"}
    service.store.write(note)
    service._memory = AsyncMock(side_effect=RuntimeError("memory unavailable"))
    result = asyncio.run(service.snapshot())
    assert result["availability"]["persona"] is True
    assert result["availability"]["memory"] is False
    assert result["note"] == note
    assert ObservatoryNoteStore(tmp_path).read() == note


def make_organ(service, reply):
    client = SimpleNamespace(chat=AsyncMock(return_value=reply))
    organ = MiyaObservatoryOrgan(service, client_factory=lambda: client)
    organ._config = lambda: {"quiet_hours": []}
    return organ, client


def test_generation_inherits_persona_persists_and_survives_restart(tmp_path):
    service = make_service(tmp_path)
    organ, client = make_organ(service, '{"title":"今夜仍有微光","body":"佳，愿这一点安静的光陪你慢慢走。"}')

    async def write_together():
        return await asyncio.gather(organ.generate_if_due(), organ.generate_if_due())

    results = asyncio.run(write_together())
    assert [item["status"] for item in results] == ["written", "throttled"]
    assert client.chat.await_count == 1
    assert "这是当前温柔人格。" in client.chat.call_args.kwargs["messages"][0].content
    note = ObservatoryNoteStore(tmp_path).read()
    assert note["title"] == "今夜仍有微光"
    assert note["persona_id"] == "gentle"
    assert note["created_at"].endswith("+00:00")
    restarted, _ = make_organ(make_service(tmp_path), "SKIP")
    assert asyncio.run(restarted.generate_if_due())["status"] == "throttled"


@pytest.mark.parametrize("reply", ["SKIP", "not JSON", '{"title":"新的微光","body":"太短"}'])
def test_silence_or_failure_keeps_previous_note_and_throttles_attempts(tmp_path, reply):
    service = make_service(tmp_path)
    previous = {"title": "之前留下的光", "body": "这张短笺应当在生成失败或保持沉默时留存。"}
    service.store.write(previous)
    organ, client = make_organ(service, reply)
    assert asyncio.run(organ.generate_if_due())["status"] in {"silent", "failed"}
    assert service.store.read() == previous
    assert asyncio.run(organ.generate_if_due())["status"] == "throttled"
    assert client.chat.await_count == 1


def test_persona_change_during_generation_discards_outdated_note(tmp_path):
    service = make_service(tmp_path)
    organ, client = make_organ(service, "")

    async def switch_persona(**kwargs):
        service.hub.personality.current_form = "another"
        return '{"title":"今夜仍有微光","body":"佳，愿这一点安静的光陪你慢慢走。"}'

    client.chat.side_effect = switch_persona
    assert asyncio.run(organ.generate_if_due())["status"] == "persona_changed"
    assert service.store.read() == {}


def test_messages_only_provider_receives_the_composed_persona(tmp_path):
    service = make_service(tmp_path)
    calls = []

    async def chat(messages):
        calls.append(messages)
        return '{"title":"今夜仍有微光","body":"佳，愿这一点安静的光陪你慢慢走。"}'

    client = SimpleNamespace(chat=chat)
    organ = MiyaObservatoryOrgan(service, client_factory=lambda: client)
    organ._config = lambda: {"quiet_hours": []}
    assert asyncio.run(organ.generate_if_due())["status"] == "written"
    assert "这是当前温柔人格。" in calls[0][0].content


def test_isolated_client_does_not_reset_or_evict_chat_client(monkeypatch):
    from core.ai_client import AIClientFactory

    class FakeClient:
        def __init__(self, **kwargs):
            self.tool_registry = "conversation tools"

    shared = FakeClient()
    key = AIClientFactory._cache_key("test", "fake-key", "fake-model")
    monkeypatch.setattr(AIClientFactory, "_clients", {"test": FakeClient})
    monkeypatch.setattr(AIClientFactory, "_cache", {key: shared})
    isolated = AIClientFactory.create_client("test", "fake-key", "fake-model", reuse=False)
    assert isolated is not shared
    assert shared.tool_registry == "conversation tools"
    assert AIClientFactory._cache == {key: shared}


@pytest.mark.parametrize(
    "reply",
    [
        "[]",
        '{"title":"<script>","body":"不应该接受包含标记的短笺文本。"}',
        '{"title":12,"body":"不能把数字当作短笺标题。"}',
    ],
)
def test_note_parser_rejects_invalid_output(reply):
    with pytest.raises(ValueError):
        parse_note(reply)


def test_rest_and_event_stream_deliver_the_same_snapshot(tmp_path, monkeypatch):
    import core.observatory
    from core.web_api.miya_api import MiyaAPI

    service = make_service(tmp_path)
    monkeypatch.setattr(core.observatory, "get_observatory", lambda _: service)
    api = MiyaAPI()
    endpoints = {route.path: route.endpoint for route in api.router.routes}

    async def read():
        rest = await endpoints["/api/observatory/snapshot"]()
        response = await endpoints["/api/observatory/events"](
            SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        )
        iterator = response.body_iterator
        assert await anext(iterator) == "retry: 3000\n\n"
        event = await anext(iterator)
        await iterator.aclose()
        assert event.startswith("event: presence\ndata: ")
        assert json.loads(event.split("data: ", 1)[1]) == rest
        assert response.headers["cache-control"] == "no-cache"

    asyncio.run(read())
