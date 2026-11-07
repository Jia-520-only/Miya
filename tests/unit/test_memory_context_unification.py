from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.vision_context import VisionContextStore
from hub.memory_manager import MemoryManager
from memory.context_assembler import ContextAssembler
from memory.context_identity import ContextIdentity
from memory.context_identity import matches_context_scope
from memory.core import JsonBackend, MiyaMemoryCore
from memory.models import MemoryItem, MemoryLevel
from memory.models import MemoryQuery


def test_context_identity_uses_one_group_session_shape():
    identity = ContextIdentity.resolve("user-1", "group-1", "qq")

    assert identity.session_id == "group_group-1_user-1"
    assert identity.group_id == "group-1"
    assert identity.metadata()["visibility"] == "group"


@pytest.mark.asyncio
async def test_memory_manager_writes_group_id_to_bus():
    manager = object.__new__(MemoryManager)
    manager.memory_net = None
    manager.time_tracker = None
    manager._bus = SimpleNamespace(store_dialogue=AsyncMock())

    await manager.store_user_message({
        "content": "群消息",
        "user_id": "user-1",
        "group_id": "group-1",
        "platform": "qq",
        "message_type": "group",
    })

    call = manager._bus.store_dialogue.call_args.kwargs
    assert call["group_id"] == "group-1"
    assert call["session_id"] == "group_group-1_user-1"


@pytest.mark.asyncio
async def test_dialogue_reads_latest_and_exact_session(tmp_path):
    core = MiyaMemoryCore(tmp_path, enable_backup=False)
    core._identity_resolver = None
    start = datetime(2026, 10, 3, 10, 0)
    items = []
    for number in range(10):
        item = MemoryItem(
            id=f"memory-{number}", content=f"消息 {number}", level=MemoryLevel.DIALOGUE,
            user_id="user-1", session_id="user_user-1", role="user",
            created_at=(start + timedelta(minutes=number)).isoformat(),
        )
        items.append(item)
    group_item = MemoryItem(
        id="group-memory", content="群消息", level=MemoryLevel.DIALOGUE,
        user_id="user-1", session_id="group_group-1_user-1", group_id="group-1",
        role="user", created_at=start.isoformat(), metadata={"visibility": "group"},
    )
    core._cache = {item.id: item for item in [*items, group_item]}
    core._user_index = {"user-1": set(core._cache)}

    latest = await core.get_dialogue(user_id="user-1", limit=3)
    exact = await core.get_dialogue(
        session_id="group_group-1_user-1", user_id="user-1", limit=3,
    )

    assert [item.content for item in latest] == ["消息 7", "消息 8", "消息 9"]
    assert [item.content for item in exact] == ["群消息"]


@pytest.mark.asyncio
async def test_context_assembler_merges_cache_and_unified_store():
    cache = SimpleNamespace(
        conversation_history=SimpleNamespace(
            get_history=AsyncMock(return_value=[SimpleNamespace(
                role="user", content="缓存消息", timestamp="2026-10-03T10:00:00", metadata={},
            )])
        )
    )
    unified = [SimpleNamespace(
        role="assistant", content="统一消息", created_at="2026-10-03T10:01:00", metadata={},
    )]

    with patch("memory.get_dialogue_history", AsyncMock(return_value=unified)):
        messages = await ContextAssembler(cache).load_dialogue(
            ContextIdentity.resolve("user-1", platform="qq"), limit=10,
        )

    assert [message.content for message in messages] == ["缓存消息", "统一消息"]


@pytest.mark.asyncio
async def test_context_assembler_does_not_leak_private_history_into_group():
    private = SimpleNamespace(
        id="private", role="user", content="私聊内容",
        timestamp="2026-10-03T10:00:00", metadata={}, group_id="",
    )
    group = SimpleNamespace(
        id="group", role="user", content="群聊内容",
        timestamp="2026-10-03T10:01:00", metadata={"group_id": "group-1"}, group_id="group-1",
    )

    with (
        patch("memory.get_dialogue_history", AsyncMock(return_value=[private, group])),
        patch("core.unified_message_store.get_unified_message_store", return_value=SimpleNamespace(
            query_messages=AsyncMock(return_value=[]),
        )),
    ):
        messages = await ContextAssembler().load_dialogue(
            ContextIdentity.resolve("user-1", "group-1", "qq"), limit=10,
        )

    assert [message.content for message in messages] == ["群聊内容"]


@pytest.mark.asyncio
async def test_context_assembler_loads_archived_group_messages_with_event_time():
    archive = SimpleNamespace(query_messages=AsyncMock(return_value=[{
        "message_id": "event-1",
        "sender_id": "user-1",
        "sender_name": "小明",
        "group_id": "group-1",
        "content": "普通群消息",
        "timestamp": "2026-10-03T10:02:00+00:00",
    }]))

    with (
        patch("memory.get_dialogue_history", AsyncMock(return_value=[])),
        patch("core.unified_message_store.get_unified_message_store", return_value=archive),
    ):
        messages = await ContextAssembler().load_dialogue(
            ContextIdentity.resolve("user-1", "group-1", "aiocqhttp"), limit=10,
        )

    assert [message.content for message in messages] == ["普通群消息"]
    assert messages[0].timestamp == "2026-10-03T10:02:00+00:00"
    assert messages[0].metadata["group_id"] == "group-1"
    assert messages[0].metadata["sender_name"] == "小明"


def test_group_context_keeps_speaker_identity_in_prompt_formatting():
    from core.prompt_manager import PromptManager

    manager = object.__new__(PromptManager)
    text = manager._format_memory_context([
        {
            "role": "user",
            "content": "这是群友说的话",
            "metadata": {
                "group_id": "group-1",
                "conversation_scope": "group",
                "sender_name": "小明",
                "platform_user_id": "1001",
            },
        },
        {
            "role": "user",
            "content": "这是佳说的话",
            "metadata": {
                "group_id": "group-1",
                "conversation_scope": "group",
                "sender_name": "佳",
                "platform_user_id": "1523878699",
            },
        },
    ])

    assert "群成员 小明[1001]：这是群友说的话" in text
    assert "群成员 佳[1523878699]：这是佳说的话" in text
    assert "用户：这是群友说的话" not in text


@pytest.mark.asyncio
async def test_context_assembler_reads_onebot_archive_for_qq_alias():
    async def query_messages(**kwargs):
        if kwargs.get("platform_id") == "aiocqhttp":
            return [{
                "message_id": "event-qq",
                "sender_id": "user-1",
                "group_id": "group-1",
                "content": "OneBot 历史消息",
                "timestamp": "2026-10-03T10:02:00+00:00",
            }]
        return []

    archive = SimpleNamespace(query_messages=AsyncMock(side_effect=query_messages))

    with (
        patch("memory.get_dialogue_history", AsyncMock(return_value=[])),
        patch("core.unified_message_store.get_unified_message_store", return_value=archive),
    ):
        messages = await ContextAssembler().load_dialogue(
            ContextIdentity.resolve("user-1", "group-1", "qq"), limit=10,
        )

    assert [message.content for message in messages] == ["OneBot 历史消息"]


def test_browser_camera_card_expires_old_observations():
    store = VisionContextStore()
    store.add({"source": "camera", "timestamp": 1, "summary": "过期观察"})

    assert store.build_card(source="camera") == ""


def test_memory_query_cache_key_is_scoped_by_conversation():
    core = object.__new__(JsonBackend)

    private = MemoryQuery(user_id="user-1", session_id="user_user-1", platform="qq")
    group = MemoryQuery(
        user_id="user-1", session_id="group_group-1_user-1", group_id="group-1", platform="qq",
    )
    other_platform = MemoryQuery(user_id="user-1", session_id="user_user-1", platform="weixin_ilink")

    assert core._get_cache_key(private) != core._get_cache_key(group)
    assert core._get_cache_key(private) != core._get_cache_key(other_platform)


def test_memory_context_scope_keeps_group_history_private_and_shares_personal_memories():
    user_scope = MemoryQuery(scope_user_ids=["owner"])
    group_scope = MemoryQuery(scope_user_ids=["owner"], scope_group_id="group-1")
    group_only = MemoryItem(
        content="群内讨论", user_id="owner", group_id="group-1",
        metadata={"visibility": "group"},
    )
    personal = MemoryItem(
        content="喜欢海盐冰淇淋", user_id="owner",
        metadata={"visibility": "personal", "group_id": ""},
    )

    assert not matches_context_scope(group_only, user_scope)
    assert matches_context_scope(personal, user_scope)
    assert matches_context_scope(group_only, group_scope)
    assert matches_context_scope(personal, group_scope)


@pytest.mark.asyncio
async def test_group_message_only_owner_personal_facts_become_cross_context_memory():
    owner = SimpleNamespace(
        owner_canonical_id="owner",
        canonicalize=lambda value: str(value),
        expand=lambda value: [str(value)],
    )
    bus = SimpleNamespace(
        store_dialogue=AsyncMock(),
        get_user_memories=AsyncMock(return_value=[]),
        store_important=AsyncMock(),
    )
    manager = object.__new__(MemoryManager)
    manager.memory_net = None
    manager.time_tracker = None
    manager._bus = bus

    with patch("memory.identity_resolver.get_identity_resolver", return_value=owner):
        await manager.store_user_message({
            "content": "我喜欢海盐冰淇淋",
            "user_id": "owner",
            "group_id": "group-1",
            "platform": "qq",
            "message_type": "group",
            "message_id": "event-7",
            "timestamp": "2026-10-03T10:00:00+08:00",
        })
        await manager.store_user_message({
            "content": "我喜欢海盐冰淇淋",
            "user_id": "member-2",
            "group_id": "group-1",
            "platform": "qq",
            "message_type": "group",
        })

    assert bus.store_important.await_count == 1
    metadata = bus.store_important.await_args.kwargs["metadata"]
    assert metadata["visibility"] == "personal"
    assert metadata["group_id"] == ""
    assert metadata["source_group_id"] == "group-1"
    assert metadata["source_message_id"] == "event-7"
    assert metadata["source_timestamp"] == "2026-10-03T10:00:00+08:00"


@pytest.mark.asyncio
async def test_service_context_uses_group_scoped_assembler():
    from hub.services.context import ProcessRequest
    from hub.services.memory import MemoryService

    message = SimpleNamespace(
        role="user", content="群里的上一句", timestamp="2026-10-03T10:00:00", metadata={"group_id": "group-1"},
    )
    service = MemoryService(memory_net=None)

    with patch("memory.context_assembler.ContextAssembler.build", AsyncMock(
        return_value=SimpleNamespace(messages=[message]),
    )) as build:
        result = await service.get_context(ProcessRequest(
            content="继续说", raw_perception={}, user_id="user-1", group_id="group-1",
            platform="qq", session_id="group_group-1_user-1",
        ))

    build.assert_awaited_once()
    identity = build.await_args.args[0]
    assert identity.group_id == "group-1"
    assert result[0]["content"] == "群里的上一句"
