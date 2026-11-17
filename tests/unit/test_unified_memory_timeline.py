"""Regression tests for cross-channel dialogue, recall, and event time."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.conversation_history import ConversationHistoryManager
from core.prompt_manager import PromptManager
from hub.memory_manager import MemoryManager
from memory.api.bus import MemoryBus, RecallRequest
from memory.cognitive_engine import CognitiveEngine
from memory.context_assembler import ContextAssembler
from memory.context_identity import ContextIdentity, matches_context_scope
from memory.core import JsonBackend, MiyaMemoryCore
from memory.models import MemoryItem, MemoryLevel, MemoryQuery
from memory.sqlite_backend import SQLiteBackend
from memory.time_tracker import TimeTracker


@pytest.fixture
def identity(monkeypatch):
    resolver = SimpleNamespace(
        owner_canonical_id="owner",
        canonicalize=lambda value: "owner" if value in {"owner", "desktop-owner"} else value,
        expand=lambda value: ["owner", "desktop-owner"] if value in {"owner", "desktop-owner"} else [value],
    )
    monkeypatch.setattr("memory.identity_resolver.get_identity_resolver", lambda: resolver)
    return resolver


@pytest.fixture
def sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr("memory.sqlite_backend._load_sqlite_config", lambda: {
        "enabled": True, "table": {"fts_enabled": False},
    })
    backend = SQLiteBackend(str(tmp_path / "memory.db"))
    yield backend
    backend._conn.close()


def dialogue(content, user="owner", group="", platform="qq", timestamp=None, **metadata):
    return MemoryItem(
        content=content, level=MemoryLevel.DIALOGUE, role="user", user_id=user,
        group_id=group, platform=platform,
        session_id=f"group_{group}_{user}" if group else f"user_{user}",
        created_at=timestamp or datetime.now().isoformat(),
        metadata={"group_id": group, "visibility": "group" if group else "private", **metadata},
    )


@pytest.mark.asyncio
async def test_sqlite_and_json_share_the_same_recall_scope(tmp_path, sqlite):
    json_store = JsonBackend(tmp_path / "json")
    items = [
        dialogue("自己的私聊原文"),
        dialogue("自己在另一个群的经历", group="other-group", platform="desktop"),
        dialogue("当前群友的发言", user="member", group="current-group"),
        dialogue("别人的私聊", user="member"),
        dialogue("别的群友发言", user="member", group="other-group"),
        dialogue("共享事实", visibility="personal"),
    ]
    for item in items:
        assert await json_store.save(item)
        assert await sqlite.save(item)
    for query, expected in [
        (MemoryQuery(scope_user_ids=["owner"], limit=20), {0, 1, 5}),
        (MemoryQuery(scope_user_ids=["owner"], scope_group_id="current-group", scope_platforms=["qq"], limit=20), {0, 1, 2, 5}),
    ]:
        ids = {items[index].id for index in expected}
        assert {item.id for item in await sqlite.query(query)} == ids
        assert {item.id for item in await json_store.query(query)} == ids
        assert {item.id for item in items if matches_context_scope(item, query)} == ids


@pytest.mark.asyncio
async def test_both_chat_entries_read_the_same_users_original_dialogue(tmp_path, identity, sqlite):
    core = MiyaMemoryCore(tmp_path / "json", enable_backup=False)
    core.sqlite_backend = sqlite
    start = datetime(2026, 11, 16, 9)
    items = [
        dialogue("桌面私聊原文", user="desktop-owner", platform="desktop", timestamp=start.isoformat()),
        dialogue("当前群的原文", group="current", timestamp=(start + timedelta(minutes=1)).isoformat()),
        dialogue("另一个群的原文", group="other", timestamp=(start + timedelta(minutes=2)).isoformat()),
        dialogue("别人的私聊原文", user="member", timestamp=(start + timedelta(minutes=3)).isoformat()),
    ]
    for item in items:
        await core.backend.save(item)
        await sqlite.save(item)
    archive = SimpleNamespace(query_messages=AsyncMock(return_value=[]))
    with (
        patch("memory.get_dialogue_history", core.get_dialogue),
        patch("core.unified_message_store.get_unified_message_store", return_value=archive),
    ):
        for group, session in [("", ""), ("current", ""), ("current", "explicit-session")]:
            messages = await ContextAssembler().load_dialogue(
                ContextIdentity.resolve("owner", group, "qq", session), limit=20,
            )
            assert [message.content for message in messages] == [item.content for item in items[:3]]
            assert messages[2].metadata["group_id"] == "other"

    bus = MemoryBus()
    bus._core = core
    bus._initialized = True
    recalled = await bus.recall(RecallRequest(
        user_id="owner", group_id="current", platform="qq", session_id="group_current_owner",
    ))
    assert {item.content for item in recalled.memories} == {item.content for item in items[:3]}


@pytest.mark.asyncio
async def test_event_time_survives_manager_bus_both_backends_and_history(tmp_path, identity, sqlite):
    core = MiyaMemoryCore(tmp_path / "json", enable_backup=False)
    core.sqlite_backend = sqlite
    core._get_enhancer = lambda: None
    bus = MemoryBus()
    bus._core = core
    bus._initialized = True
    history = ConversationHistoryManager(tmp_path / "conversations")
    tracker = TimeTracker(tmp_path / "time")
    previous = datetime.now() - timedelta(hours=3)
    tracker.record_interaction("owner", "qq", group_id="current", timestamp=previous.isoformat())
    manager = object.__new__(MemoryManager)
    manager.memory_net = SimpleNamespace(conversation_history=history)
    manager.time_tracker = tracker
    manager._bus = bus
    event = {
        "content": "带原始时间的群消息", "user_id": "desktop-owner", "group_id": "current",
        "platform": "aiocqhttp", "timestamp": datetime.now().astimezone().isoformat(),
        "message_id": "event-1", "message_type": "group",
    }
    await manager.store_user_message(event)
    await history.flush()
    cached = await history.get_history("group_current_owner")
    stored = await core.get_dialogue(user_id="owner")
    assert len(cached) == len(stored) == 1
    assert cached[0].timestamp == stored[0].created_at
    assert cached[0].metadata["memory_event_id"] == stored[0].metadata["memory_event_id"]
    assert cached[0].metadata["canonical_user_id"] == "owner"
    assert cached[0].metadata["speaker_user_id"] == "owner"
    assert cached[0].metadata["source_platform"] == "aiocqhttp"
    assert cached[0].metadata["source_group_id"] == "current"
    assert cached[0].metadata["source_message_id"] == "event-1"
    assert stored[0].metadata["source_timestamp"] == event["timestamp"]
    assert previous.strftime("%Y-%m-%d %H:%M") in event["_interaction_time_context"]
    assert "距今间隔: 3小时前" in event["_interaction_time_context"]
    assert (await sqlite.load(stored[0].id)).created_at == cached[0].timestamp
    assert (await core.backend.load(stored[0].id)).created_at == cached[0].timestamp


def test_tracker_restores_group_clock_unifies_aliases_and_ignores_old_replays(tmp_path, identity):
    tracker = TimeTracker(tmp_path)
    latest = "2026-11-16T12:00:00"
    tracker.record_interaction("desktop-owner", "qq", group_id="current", timestamp=latest)
    tracker.record_interaction("owner", "aiocqhttp", group_id="current", timestamp="2026-11-15T12:00:00")
    tracker.record_interaction("member", "lark", group_id="current", timestamp="2026-11-17T12:00:00")
    tracker.flush()
    restored = TimeTracker(tmp_path)
    assert restored.get_profile("owner").last_interaction == latest
    assert restored.get_profile("desktop-owner").last_interaction == latest
    assert restored.get_group_profile("current", "aiocqhttp").last_interaction == latest
    assert restored.get_group_profile("current", "lark").last_interaction == "2026-11-17T12:00:00"


def test_prompt_preserves_dates_in_summaries_and_source_of_recent_messages():
    manager = PromptManager()
    messages = [
        {"role": "user", "content": f"消息 {number}", "timestamp": f"2026-11-{15 + number // 5:02}T10:00:00",
         "metadata": {"group_id": "current", "sender_name": "佳"}}
        for number in range(10)
    ]
    result = manager._format_memory_context(messages)
    assert "2026-11-15 10:00:00 至 2026-11-15 10:00:00" in result
    assert "[2026-11-16 10:00:00][群聊 current]" in result


@pytest.mark.asyncio
async def test_temporal_recall_finds_group_experience_from_private_without_keyword_overlap(tmp_path, identity):
    core = MiyaMemoryCore(tmp_path, enable_backup=False)
    yesterday = (datetime.now() - timedelta(days=1)).replace(hour=10, minute=0, second=0)
    item = dialogue("蓝色火箭试飞成功", group="current", timestamp=yesterday.isoformat())
    other = dialogue("其他人的私聊", user="member", timestamp=yesterday.isoformat())
    core._cache = {memory.id: memory for memory in [item, other]}
    engine = CognitiveEngine(core)
    engine._memory_core_initialized = True
    engine._extract_keywords = lambda _: []
    context = await engine.build_context("昨天我聊过什么", user_id="owner")
    assert "蓝色火箭试飞成功" in context
    assert "群聊 current" in context
    assert yesterday.strftime("%Y-%m-%d") in context
    assert "其他人的私聊" not in context


@pytest.mark.asyncio
async def test_recalled_memory_prompt_preserves_private_source_marker(tmp_path):
    core = MiyaMemoryCore(tmp_path, enable_backup=False)
    engine = CognitiveEngine(core)
    engine._memory_core_initialized = True
    private_memory = dialogue(
        "普通措辞的私聊摘要", timestamp="2026-11-16T10:00:00",
        source_privacy="private", privacy_level="private",
    )
    engine.retrieve = AsyncMock(return_value=[private_memory])

    context = await engine.build_context("那件事", user_id="owner", group_id="current")

    assert "普通措辞的私聊摘要" in context
    assert "私聊来源" in context
