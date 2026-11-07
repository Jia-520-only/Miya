"""History recovery must distinguish unavailable history from an empty result."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from core.unified_message_store import UnifiedMessageStore
from core.unified_platform_impl.onebot_platform import OneBotPlatform


def _reply_over_websocket(platform, response):
    async def send(payload):
        request = json.loads(payload)
        platform._pending_echoes[request["echo"]].set_result(response)

    platform._connected = True
    platform._ws = Mock(send_str=AsyncMock(side_effect=send))


@pytest.mark.parametrize("response, expected", [
    ({"status": "failed", "retcode": 200, "message": "消息0不存在"}, None),
    ({"status": "ok", "data": {"messages": []}}, {"messages": []}),
])
def test_history_response_does_not_repeat_explicit_failure_over_http(monkeypatch, caplog, response, expected):
    async def run():
        platform = OneBotPlatform({"bot_qq": "999"})
        _reply_over_websocket(platform, response)
        http_session = Mock(side_effect=AssertionError("An answered query must not be repeated"))
        monkeypatch.setattr("aiohttp.ClientSession", http_session)

        assert await platform.get_group_msg_history(2001, count=100) == expected
        http_session.assert_not_called()
        request = json.loads(platform._ws.send_str.call_args.args[0])
        assert request["params"] == {"group_id": 2001, "message_seq": 0, "count": 100}
        assert not platform._pending_echoes
        if expected is None:
            assert "群 2001 历史暂不可用" in caplog.text
            assert "消息0不存在" in caplog.text

    asyncio.run(run())


def test_history_transport_error_can_still_fall_back_to_http(monkeypatch):
    async def run():
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._connected = True
        platform._ws = Mock(send_str=AsyncMock(side_effect=ConnectionError("closed")))
        response = Mock(status=200, json=AsyncMock(return_value={"status": "ok", "data": {"messages": []}}))
        request_context = AsyncMock()
        request_context.__aenter__.return_value = response
        session = AsyncMock()
        session.post = Mock(return_value=request_context)
        session_context = AsyncMock()
        session_context.__aenter__.return_value = session
        monkeypatch.setattr("aiohttp.ClientSession", Mock(return_value=session_context))

        assert await platform.get_group_msg_history(2001) == {"messages": []}
        session.post.assert_called_once()
        assert not platform._pending_echoes

    asyncio.run(run())


def test_history_retries_only_failed_groups_and_continues_after_an_exception(tmp_path, monkeypatch):
    async def run():
        import core.unified_message_store as message_store_module

        store = UnifiedMessageStore(str(tmp_path / "messages.db"))
        monkeypatch.setattr(message_store_module, "get_unified_message_store", lambda: store)
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._is_group_allowed = lambda group_id: group_id != "2004"
        platform._is_user_allowed = lambda _user_id: True
        platform.get_group_list = AsyncMock(return_value=[
            {"group_id": group_id} for group_id in (2001, 2002, 2003, 2004, 2005)
        ])
        calls = []

        async def history(group_id, **_kwargs):
            calls.append(group_id)
            if group_id == 2001 and calls.count(group_id) == 1:
                return None
            if group_id == 2003 and calls.count(group_id) == 1:
                raise ConnectionError("NapCat is starting")
            if group_id == 2005:
                return {"messages": []}
            return {"messages": [{
                "message_id": group_id, "time": 1793872800,
                "sender": {"user_id": 1001, "nickname": "小明"},
                "message": [{"type": "text", "data": {"text": "离线时的消息"}}],
            }]}

        async def no_wait(_delay):
            pass

        platform.get_group_msg_history = history
        monkeypatch.setattr(asyncio, "sleep", no_wait)
        try:
            await platform._recover_recent_group_history_with_retry()
            assert calls == [2001, 2002, 2003, 2005, 2001, 2003]
            for group_id in (2001, 2002, 2003):
                rows = await store.query_messages(platform_id="aiocqhttp", group_id=str(group_id))
                assert len(rows) == 1
                assert rows[0]["timestamp"] == "2026-11-05T10:00:00+00:00"
        finally:
            await store.close()

    asyncio.run(run())


@pytest.mark.parametrize("result", [None, {}, {"messages": None}, {"messages": {}}, {"messages": [None]}])
def test_unavailable_or_malformed_history_never_reports_recovery_complete(monkeypatch, caplog, result):
    async def run():
        import core.unified_message_store as message_store_module

        monkeypatch.setattr(message_store_module, "get_unified_message_store", lambda: Mock(
            query_messages=AsyncMock(return_value=[]),
        ))
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._is_group_allowed = lambda _group_id: True
        platform.get_group_list = AsyncMock(return_value=[{"group_id": 2001}])
        platform.get_group_msg_history = AsyncMock(return_value=result)

        async def no_wait(_delay):
            pass

        monkeypatch.setattr(asyncio, "sleep", no_wait)
        await platform._recover_recent_group_history_with_retry()

        assert platform.get_group_msg_history.await_count == 3
        assert "待重试群: 2001" in caplog.text
        assert "3 次尝试后仍未完成" in caplog.text
        assert "回填任务完成" not in caplog.text

    asyncio.run(run())


def test_recovery_does_not_complete_when_persistent_archive_write_fails(monkeypatch):
    async def run():
        import core.unified_message_store as message_store_module

        store = Mock(query_messages=AsyncMock(return_value=[]), record_message=AsyncMock(return_value=None))
        monkeypatch.setattr(message_store_module, "get_unified_message_store", lambda: store)
        platform = OneBotPlatform({"bot_qq": "999"})
        platform._is_group_allowed = lambda _group_id: True
        platform._is_user_allowed = lambda _user_id: True
        platform.get_group_list = AsyncMock(return_value=[{"group_id": 2001}])
        platform.get_group_msg_history = AsyncMock(return_value={"messages": [{
            "message_id": 1234, "sender": {"user_id": 1001}, "message": "无法落盘的消息",
        }]})

        async def no_wait(_delay):
            pass

        monkeypatch.setattr(asyncio, "sleep", no_wait)
        completed = set()
        assert await platform._recover_recent_group_history(completed) is False
        assert completed == set()
        assert store.record_message.await_count == 3

    asyncio.run(run())


@pytest.mark.parametrize("groups", [None, []])
def test_missing_group_list_is_retried(monkeypatch, groups):
    async def run():
        platform = OneBotPlatform({"bot_qq": "999"})
        platform.get_group_list = AsyncMock(return_value=groups)
        platform.get_group_msg_history = AsyncMock()

        async def no_wait(_delay):
            pass

        monkeypatch.setattr(asyncio, "sleep", no_wait)
        await platform._recover_recent_group_history_with_retry()
        assert platform.get_group_list.await_count == 3
        platform.get_group_msg_history.assert_not_awaited()

    asyncio.run(run())
