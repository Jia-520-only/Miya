import asyncio

from core.unified_message_store import UnifiedMessageStore
from core.unified_platform_impl.onebot_platform import OneBotPlatform


def test_message_store_deduplicates_replayed_group_events(tmp_path):
    async def run():
        store = UnifiedMessageStore(str(tmp_path / "messages.db"))
        first = await store.record_message(
            platform_id="aiocqhttp",
            user_id="u1",
            sender_id="u1",
            sender_name="小明",
            content={"text": "普通群消息"},
            message_id="1001",
            group_id="2001",
            timestamp="2026-11-05T10:00:00+00:00",
        )
        replay = await store.record_message(
            platform_id="aiocqhttp",
            user_id="u1",
            sender_id="u1",
            sender_name="小明",
            content={"text": "普通群消息"},
            message_id="1001",
            group_id="2001",
            timestamp="2026-11-05T10:00:00+00:00",
        )
        rows = await store.query_messages(
            platform_id="aiocqhttp", group_id="2001", direction="in", limit=10,
        )

        assert first == replay
        assert len(rows) == 1
        assert rows[0]["timestamp"] == "2026-11-05T10:00:00+00:00"
        await store.close()

    asyncio.run(run())


def test_message_store_upgrades_legacy_row_with_source_event_data(tmp_path):
    async def run():
        store = UnifiedMessageStore(str(tmp_path / "messages.db"))
        row_id = await store.record_message(
            platform_id="aiocqhttp",
            user_id="u1",
            sender_id="u1",
            sender_name="小明",
            content={"text": "旧版截断记录"},
            message_id="1002",
            group_id="2001",
        )
        await store.record_message(
            platform_id="aiocqhttp",
            user_id="u1",
            sender_id="u1",
            sender_name="小明",
            content={"text": "完整原文", "segments": [{"type": "text"}], "timestamp_epoch": 1793872800},
            message_id="1002",
            group_id="2001",
            timestamp="2026-11-05T10:00:00+00:00",
        )
        rows = await store.query_messages(
            platform_id="aiocqhttp", group_id="2001", direction="in", limit=10,
        )

        assert len(rows) == 1
        assert rows[0]["id"] == row_id
        assert rows[0]["content"] == "完整原文"
        assert rows[0]["raw_content"]["timestamp_epoch"] == 1793872800
        await store.close()

    asyncio.run(run())


def test_untriggered_group_message_is_archived_before_reply_filter(tmp_path, monkeypatch):
    async def run():
        import core.unified_message_store as message_store_module

        store = UnifiedMessageStore(str(tmp_path / "messages.db"))
        monkeypatch.setattr(message_store_module, "get_unified_message_store", lambda: store)
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._is_group_allowed = lambda _group_id: True
        platform._is_user_allowed = lambda _user_id: True
        platform._event_tasks = set()
        monkeypatch.setattr(platform, "_should_dispatch", lambda _data: False)

        event = {
            "post_type": "message",
            "message_type": "group",
            "message_id": 1234,
            "time": 1793872800,
            "group_id": 2001,
            "self_id": 999,
            "sender": {"user_id": 1001, "nickname": "小明"},
            "message": [{"type": "text", "data": {"text": "大家早上好"}}],
        }
        await platform._dispatch_event(event)
        rows = await store.query_messages(
            platform_id="aiocqhttp", group_id="2001", direction="in", limit=10,
        )

        assert len(rows) == 1
        assert rows[0]["content"] == "大家早上好"
        assert rows[0]["sender_id"] == "1001"
        assert rows[0]["raw_content"]["segments"] == event["message"]
        assert rows[0]["timestamp"] == "2026-11-05T10:00:00+00:00"
        await store.close()

    asyncio.run(run())


def test_reconnect_replays_available_group_history_idempotently(tmp_path, monkeypatch):
    async def run():
        import core.unified_message_store as message_store_module

        store = UnifiedMessageStore(str(tmp_path / "messages.db"))
        monkeypatch.setattr(message_store_module, "get_unified_message_store", lambda: store)
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._is_group_allowed = lambda _group_id: True
        platform._is_user_allowed = lambda _user_id: True
        platform._bot_qq = "999"
        platform.get_group_list = lambda: asyncio.sleep(0, result=[{"group_id": 2001}])
        platform.get_group_msg_history = lambda *_args, **_kwargs: asyncio.sleep(0, result={
            "messages": [{
                "message_id": 1234,
                "time": 1793872800,
                "sender": {"user_id": 1001, "nickname": "小明"},
                "message": [{"type": "text", "data": {"text": "补到的消息"}}],
            }],
        })

        await platform._recover_recent_group_history()
        await platform._recover_recent_group_history()
        rows = await store.query_messages(
            platform_id="aiocqhttp", group_id="2001", direction="in", limit=10,
        )

        assert len(rows) == 1
        assert rows[0]["content"] == "补到的消息"
        await store.close()

    asyncio.run(run())
