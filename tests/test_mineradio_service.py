"""Regression tests for the Mineradio MCP adapter."""

import json
from unittest.mock import AsyncMock

import pytest

from mcpserver.miya_mineradio.service import MiyaMineradioService


def _search_response():
    return {
        "ok": True,
        "data": {
            "results": [
                {
                    "id": 123,
                    "name": "Test Song",
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "cover": "https://example.invalid/cover.jpg",
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_search_then_play_by_song_id_uses_cached_metadata():
    service = MiyaMineradioService()
    service._send_command = AsyncMock(
        side_effect=[
            _search_response(),
            {"ok": True, "data": {"playing": True}},
        ]
    )

    search = json.loads(await service._search({"query": "test", "source": "netease"}))
    result = json.loads(await service._play_song({"song_id": str(search["results"][0]["id"])}))

    assert result["ok"] is True
    assert service._send_command.await_args_list[1].args[0] == "play_song"
    assert service._send_command.await_args_list[1].args[1]["title"] == "Test Song"
    assert service._send_command.await_args_list[1].args[1]["artist"] == "Test Artist"


@pytest.mark.asyncio
async def test_add_by_unknown_song_id_returns_actionable_error_without_command():
    service = MiyaMineradioService()
    service._send_command = AsyncMock()

    result = json.loads(await service._add_to_queue({"song_id": "missing", "source": "netease"}))

    assert result == {
        "ok": False,
        "error": "Unknown song_id. Search first, then add the returned song_id, or provide title.",
    }
    service._send_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_provider_metadata_is_forwarded_for_exact_playback():
    service = MiyaMineradioService()
    service._cache_tracks("kugou", [{"hash": "abc123", "name": "Kugou Song", "artist": "Artist"}])
    service._send_command = AsyncMock(return_value={"ok": True, "data": {"playing": True}})

    result = json.loads(await service._play_song({"song_id": "abc123", "source": "kugou"}))

    assert result["ok"] is True
    payload = service._send_command.await_args.args[1]
    assert payload["source"] == "kugou"
    assert payload["hash"] == "abc123"


def test_invalid_source_and_negative_seek_are_rejected():
    service = MiyaMineradioService()

    with pytest.raises(ValueError, match="Unsupported remote music source"):
        service._normalize_source("unknown-provider")

    assert service._normalize_source("kugou") == "kugou"


@pytest.mark.asyncio
async def test_negative_seek_does_not_reach_player():
    service = MiyaMineradioService()
    service._send_command = AsyncMock()

    result = json.loads(await service._seek({"position": -1}))

    assert result == {"ok": False, "error": "Seek position must be non-negative"}
    service._send_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_reports_disconnected_as_failure():
    service = MiyaMineradioService()
    service._ensure_connected = AsyncMock(side_effect=RuntimeError("not connected"))

    result = json.loads(await service._health({}))

    assert result["ok"] is False
    assert result["connected"] is False
    assert result["error"] == "not connected"
