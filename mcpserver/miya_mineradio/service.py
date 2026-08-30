"""
miya-mineradio MCP Service

Miya music player control service.
Controls Mineradio via WebSocket: playback, search, playlist, lyrics, remote launch.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MINERADIO_PATH = (
    Path(os.getenv("MINERADIO_PATH", ""))
    if os.getenv("MINERADIO_PATH")
    else Path(__file__).resolve().parents[2] / "music" / "Mineradio"
)
PORT_FILE = MINERADIO_PATH / ".miya-port"
DEFAULT_PORT = 3000
WS_PATH = "/miya"
CONNECT_TIMEOUT = 3.0


class MiyaMineradioService:
    """Miya Mineradio control service."""

    def __init__(self):
        self.name = "miya-mineradio"
        self.display_name = "Miya Mineradio Control"
        self.description = "Full control of Mineradio music player"
        self.version = "1.0.0"
        self._ws = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._request_counter = 0
        self._state: Dict[str, Any] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def get_tool_definitions(self) -> List[dict]:
        return [
            {
                "name": "mineradio_get_status",
                "description": "获取 Mineradio 桌面播放器当前状态：歌曲信息、播放进度、音量、播放模式",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_play",
                "description": "在 Mineradio 桌面播放器上开始/恢复播放",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_pause",
                "description": "暂停 Mineradio 桌面播放器",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_toggle_play",
                "description": "切换 Mineradio 桌面播放器播放/暂停",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_next",
                "description": "Minradio 下一首",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_prev",
                "description": "Minradio 上一首",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_seek",
                "description": "跳转 Mineradio 播放进度（秒）",
                "inputSchema": {
                    "type": "object",
                    "properties": {"position": {"type": "number", "description": "目标秒数"}},
                    "required": ["position"],
                },
            },
            {
                "name": "mineradio_set_volume",
                "description": "设置 Mineradio 音量（0-100）",
                "inputSchema": {
                    "type": "object",
                    "properties": {"value": {"type": "integer", "description": "音量 0-100"}},
                    "required": ["value"],
                },
            },
            {
                "name": "mineradio_toggle_mute",
                "description": "切换 Mineradio 静音",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_search",
                "description": "通过 Mineradio 在网易云音乐上搜索歌曲。返回可播放曲目列表。注意：搜完之后必须立即调用 mineradio_play_song 来实际播放！不要只搜不播。即使搜索结果为空，也应该调用 mineradio_play_song 并传入歌曲名作为 title（play_song 会自己做二次搜索和播放）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "limit": {"type": "integer", "description": "返回数量，默认 10"},
                        "source": {
                            "type": "string",
                            "description": "音乐源: netease(网易云) 或 qq(QQ音乐)，默认 netease",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "mineradio_play_song",
                "description": "在 Mineradio 桌面音乐播放器上播放歌曲。支持两种方式：1) 传入 song_id（来自搜索结果）直接播放；2) 只传 title（歌曲名），工具会自动搜索并播放第一个匹配结果。这是佳电脑上真正的 Mineradio 桌面应用——不是 ai_sing（AI 模仿唱歌）。用户要求「放歌」「听音乐」「播一首」「来首歌」时必须用这个工具。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "song_id": {"type": "string", "description": "歌曲 ID（来自 mineradio_search 结果）"},
                        "source": {"type": "string", "description": "音乐源: netease 或 qq，默认 netease"},
                        "title": {"type": "string", "description": "歌曲标题（可选）"},
                        "artist": {"type": "string", "description": "歌手名（可选）"},
                        "cover": {"type": "string", "description": "封面 URL（可选）"},
                    },
                    "required": [],
                },
            },
            {
                "name": "mineradio_add_to_queue",
                "description": "添加歌曲到 Mineradio 播放队列",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "song_id": {"type": "string", "description": "歌曲 ID"},
                        "source": {"type": "string", "description": "音乐源: netease 或 qq"},
                        "title": {"type": "string", "description": "歌曲标题（可选）"},
                        "artist": {"type": "string", "description": "歌手名（可选）"},
                        "cover": {"type": "string", "description": "封面 URL（可选）"},
                    },
                    "required": ["song_id"],
                },
            },
            {
                "name": "mineradio_clear_queue",
                "description": "清空 Mineradio 播放队列",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_get_queue",
                "description": "获取 Mineradio 当前播放队列",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_get_playlists",
                "description": "获取 Mineradio 中用户的歌单列表（含网易云和 QQ 音乐）",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_get_playlist_tracks",
                "description": "获取指定歌单中的歌曲列表。需要 playlist_id 和 source(netease/qq)。拿到曲目后，用 mineradio_play_song 播放第一首，用 mineradio_add_to_queue 把剩余歌曲加入队列，这样就能切歌了。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "playlist_id": {"type": "string", "description": "歌单 ID"},
                        "source": {"type": "string", "description": "音乐源: netease 或 qq"},
                    },
                    "required": ["playlist_id", "source"],
                },
            },
            {
                "name": "mineradio_play_list",
                "description": "自动获取歌单全部曲目并开始播放。传入 playlist_id 和 source，工具会自动拉取所有歌曲加入队列并开始播放第一首。之后用户就可以用 mineradio_next/mineradio_prev 切歌。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "playlist_id": {"type": "string", "description": "歌单 ID"},
                        "source": {"type": "string", "description": "音乐源: netease 或 qq"},
                    },
                    "required": ["playlist_id", "source"],
                },
            },
            {
                "name": "mineradio_get_lyrics",
                "description": "获取 Mineradio 当前播放歌曲的歌词",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_set_mode",
                "description": "设置 Mineradio 播放模式: loop(列表循环) / shuffle(随机) / single(单曲循环)",
                "inputSchema": {
                    "type": "object",
                    "properties": {"mode": {"type": "string", "description": "播放模式"}},
                    "required": ["mode"],
                },
            },
            {
                "name": "mineradio_like_song",
                "description": "在 Mineradio 中红心收藏当前歌曲",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_unlike_song",
                "description": "取消红心收藏当前歌曲",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_create_playlist",
                "description": "在 Mineradio 中创建新歌单",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "歌单名称"}},
                    "required": ["name"],
                },
            },
            {
                "name": "mineradio_shuffle_queue",
                "description": "随机打乱 Mineradio 当前播放队列",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_remove_from_queue",
                "description": "从 Mineradio 播放队列中移除指定位置的歌曲",
                "inputSchema": {
                    "type": "object",
                    "properties": {"index": {"type": "integer", "description": "队列索引（从0开始）"}},
                    "required": ["index"],
                },
            },
            {
                "name": "mineradio_launch",
                "description": "启动 Mineradio 桌面音乐播放器应用",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "mineradio_health",
                "description": "检查 Mineradio 桌面播放器是否在运行且可连接",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        ]

    async def handle_handoff(self, tool_call: dict) -> str:
        """MCP adapter entry point — called by mcp_manager."""
        tool_name = tool_call.get("tool_name", "")

        # MCP manager passes params at top level (not nested under "arguments")
        args = {k: v for k, v in tool_call.items() if k not in ("service_name", "tool_name", "message")}

        # If there's an "arguments" key (stdio MCP server path), use that instead
        if "arguments" in tool_call and isinstance(tool_call["arguments"], dict):
            args = tool_call["arguments"]

        return await self.handle_tool_call(tool_name, args)

    async def handle_tool_call(self, name: str, args: dict) -> str:
        handlers = {
            "mineradio_get_status": self._get_status,
            "mineradio_play": self._play,
            "mineradio_pause": self._pause,
            "mineradio_toggle_play": self._toggle_play,
            "mineradio_next": self._next,
            "mineradio_prev": self._prev,
            "mineradio_seek": self._seek,
            "mineradio_set_volume": self._set_volume,
            "mineradio_toggle_mute": self._toggle_mute,
            "mineradio_search": self._search,
            "mineradio_play_song": self._play_song,
            "mineradio_add_to_queue": self._add_to_queue,
            "mineradio_clear_queue": self._clear_queue,
            "mineradio_get_queue": self._get_queue,
            "mineradio_get_playlists": self._get_playlists,
            "mineradio_get_playlist_tracks": self._get_playlist_tracks,
            "mineradio_play_list": self._play_list,
            "mineradio_get_lyrics": self._get_lyrics,
            "mineradio_set_mode": self._set_mode,
            "mineradio_like_song": self._like_song,
            "mineradio_unlike_song": self._unlike_song,
            "mineradio_create_playlist": self._create_playlist,
            "mineradio_shuffle_queue": self._shuffle_queue,
            "mineradio_remove_from_queue": self._remove_from_queue,
            "mineradio_launch": self._launch,
            "mineradio_health": self._health,
        }
        handler = handlers.get(name)
        if handler:
            try:
                return await handler(args)
            except Exception as e:
                logger.exception(f"Tool call failed: {name}")
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        return json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False)

    async def _ensure_connected(self) -> None:
        async with self._lock:
            if self._ws is not None:
                try:
                    await self._ws.ping()
                    return
                except Exception:
                    self._ws = None
                    self._listen_task = None
            await self._connect()

        # Warm-up outside lock: first command always fails (cold start)
        try:
            await self._send_command("get_status", {})
        except Exception:
            pass

    async def _connect(self) -> None:
        url = await self._resolve_ws_url()
        logger.info(f"Connecting to Mineradio: {url}")
        try:
            import websockets
        except ImportError:
            raise RuntimeError("Please install websockets: pip install websockets")

        try:
            self._ws = await websockets.connect(url, open_timeout=CONNECT_TIMEOUT)
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.info("Connected to Mineradio")
            return
        except Exception:
            logger.info("Mineradio not reachable, attempting to launch...")

        try:
            subprocess.Popen(
                ["npm", "start"],
                cwd=str(MINERADIO_PATH),
                shell=True,
                creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            logger.info("Launched Mineradio, waiting for startup...")
        except Exception as e:
            raise RuntimeError(f"Failed to launch Mineradio: {e}") from e

        for i in range(15):
            await asyncio.sleep(1.5)
            try:
                self._ws = await websockets.connect(url, open_timeout=CONNECT_TIMEOUT)
                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info("Connected to Mineradio after launch")
                return
            except Exception:
                continue

        raise RuntimeError("Mineradio failed to start. Please launch it manually with start.bat")

    async def _resolve_ws_url(self) -> str:
        port = self._read_port_file()
        return f"ws://127.0.0.1:{port}{WS_PATH}"

    def _read_port_file(self) -> int:
        try:
            if PORT_FILE.exists():
                text = PORT_FILE.read_text("utf-8").strip()
                port = int(text)
                if 1 <= port <= 65535:
                    return port
        except Exception:
            pass
        return DEFAULT_PORT

    async def _listen_loop(self):
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "response":
                        req_id = msg.get("request_id", "")
                        if req_id and req_id in self._pending:
                            self._pending[req_id].set_result(msg)
                    elif msg.get("type") == "state_update":
                        self._state = msg.get("data", {})
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    async def _send_command(self, action: str, params: dict = None) -> dict:
        await self._ensure_connected()
        self._request_counter += 1
        request_id = str(self._request_counter)
        future: asyncio.Future = asyncio.Future()
        self._pending[request_id] = future
        try:
            payload = json.dumps(
                {
                    "type": "command",
                    "action": action,
                    "params": params or {},
                    "request_id": request_id,
                }
            )
            await self._ws.send(payload)
            result = await asyncio.wait_for(future, timeout=10.0)
            return result
        finally:
            self._pending.pop(request_id, None)

    async def _get_status(self, args: dict) -> str:
        resp = await self._send_command("get_status")
        data = resp.get("data", self._state)
        self._state = data
        return json.dumps(data, ensure_ascii=False, indent=2)

    async def _play(self, args: dict) -> str:
        resp = await self._send_command("play")
        return json.dumps(resp, ensure_ascii=False)

    async def _pause(self, args: dict) -> str:
        resp = await self._send_command("pause")
        return json.dumps(resp, ensure_ascii=False)

    async def _toggle_play(self, args: dict) -> str:
        resp = await self._send_command("toggle_play")
        return json.dumps(resp, ensure_ascii=False)

    async def _next(self, args: dict) -> str:
        resp = await self._send_command("next")
        return json.dumps(resp, ensure_ascii=False)

    async def _prev(self, args: dict) -> str:
        resp = await self._send_command("prev")
        return json.dumps(resp, ensure_ascii=False)

    async def _seek(self, args: dict) -> str:
        position = float(args.get("position", 0))
        resp = await self._send_command("seek", {"position": position})
        return json.dumps(resp, ensure_ascii=False)

    async def _set_volume(self, args: dict) -> str:
        value = max(0, min(100, int(args.get("value", 50))))
        resp = await self._send_command("volume", {"value": value})
        return json.dumps(resp, ensure_ascii=False)

    async def _toggle_mute(self, args: dict) -> str:
        resp = await self._send_command("mute")
        return json.dumps(resp, ensure_ascii=False)

    async def _search(self, args: dict) -> str:
        query = args.get("query", "")
        limit = int(args.get("limit", 10))
        source = args.get("source", "netease")

        async def _do_search():
            try:
                return await self._send_command(
                    "search",
                    {
                        "query": query,
                        "limit": limit,
                        "source": source,
                    },
                )
            except Exception:
                return None

        resp = await _do_search()

        # Retry on cold start / timeout
        if not resp or not isinstance(resp, dict) or resp.get("ok") is False:
            resp = await _do_search()

        data = resp.get("data") or {} if resp else {}
        if not (data or {}).get("results"):
            resp = await _do_search()
            data = resp.get("data") or {} if resp else {}
        if not (data or {}).get("results"):
            return json.dumps(
                {
                    "ok": True,
                    "results": [],
                    "query": query,
                    "hint": "No results. Try a different search query or check the song name spelling.",
                },
                ensure_ascii=False,
                indent=2,
            )
        results = []
        for item in data["results"]:
            results.append(
                {
                    "id": str(item.get("id", "")),
                    "name": item.get("name", ""),
                    "artist": item.get("artist")
                    or (
                        ", ".join([a.get("name", "") for a in (item.get("artists") or [])])
                        if item.get("artists")
                        else ""
                    ),
                    "album": item.get("album", {}).get("name", "")
                    if isinstance(item.get("album"), dict)
                    else item.get("album", ""),
                    "cover": item.get("cover")
                    or (item.get("album", {}).get("picUrl", "") if isinstance(item.get("album"), dict) else ""),
                    "source": source,
                    "mid": str(item.get("mid", "")),
                }
            )
        return json.dumps(
            {
                "ok": True,
                "results": results,
                "query": query,
                "source": source,
                "hint": f"Found {len(results)} results. To play one, call mineradio_play_song with the song_id from a result.",
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _play_song(self, args: dict) -> str:
        song_id = args.get("song_id", "")
        title = args.get("title", "")
        source = args.get("source", "netease")

        # If no song_id but a title is provided, auto-search and play first result
        if (not song_id) and title:
            search_resp = await self._send_command(
                "search",
                {
                    "query": title + (" " + args.get("artist", "") if args.get("artist") else ""),
                    "limit": 3,
                    "source": source,
                },
            )
            search_data = search_resp.get("data", {})
            results = search_data.get("results", [])
            if results:
                first = results[0]
                song_id = str(first.get("id", ""))
                title = first.get("name", title)
                source = first.get("source", source)
                args["artist"] = first.get("artist", args.get("artist", ""))
                args["cover"] = first.get("cover", args.get("cover", ""))

        if not song_id:
            return json.dumps(
                {
                    "ok": False,
                    "error": "No song_id and auto-search found nothing. Please use mineradio_search first to find a song, then call mineradio_play_song with the song_id.",
                },
                ensure_ascii=False,
            )

        resp = await self._send_command(
            "play_song",
            {
                "song_id": song_id,
                "source": source,
                "title": title,
                "artist": args.get("artist", ""),
                "cover": args.get("cover", ""),
            },
        )
        return json.dumps(resp, ensure_ascii=False)

    async def _add_to_queue(self, args: dict) -> str:
        resp = await self._send_command(
            "add_to_queue",
            {
                "song_id": args.get("song_id", ""),
                "source": args.get("source", "netease"),
                "title": args.get("title", ""),
                "artist": args.get("artist", ""),
                "cover": args.get("cover", ""),
            },
        )
        return json.dumps(resp, ensure_ascii=False)

    async def _clear_queue(self, args: dict) -> str:
        resp = await self._send_command("clear_queue")
        return json.dumps(resp, ensure_ascii=False)

    async def _get_queue(self, args: dict) -> str:
        resp = await self._send_command("get_status")
        data = resp.get("data", self._state)
        self._state = data
        return json.dumps(
            {
                "current_song": data.get("song"),
                "playing": data.get("playing"),
                "progress": data.get("progress"),
                "duration": data.get("duration"),
                "queue_length": data.get("queue_length", 0),
                "queue_index": data.get("queue_index", -1),
                "mode": data.get("mode", "loop"),
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _get_playlists(self, args: dict) -> str:
        resp = await self._send_command("get_playlists")
        return json.dumps(resp.get("data", resp), ensure_ascii=False, indent=2)

    async def _get_playlist_tracks(self, args: dict) -> str:
        playlist_id = args.get("playlist_id", "")
        source = args.get("source", "netease")
        resp = await self._send_command(
            "get_playlist_tracks",
            {
                "playlist_id": playlist_id,
                "source": source,
            },
        )
        return json.dumps(resp.get("data", resp), ensure_ascii=False, indent=2)

    async def _play_list(self, args: dict) -> str:
        playlist_id = args.get("playlist_id", "")
        source = args.get("source", "netease")

        tracks_resp = await self._send_command(
            "get_playlist_tracks",
            {
                "playlist_id": playlist_id,
                "source": source,
            },
        )
        tracks_data = tracks_resp.get("data", {})
        tracks = tracks_data.get("tracks", [])
        total = tracks_data.get("total", len(tracks))

        if not tracks:
            return json.dumps({"ok": False, "error": "Playlist has no tracks"}, ensure_ascii=False)

        # Send all tracks in a single batch command
        batch = []
        for track in tracks[:200]:
            batch.append(
                {
                    "id": str(track.get("id", "")),
                    "name": track.get("name", ""),
                    "artist": track.get("artist", ""),
                    "cover": track.get("cover", ""),
                    "source": source,
                }
            )

        resp = await self._send_command("play_multiple", {"tracks": batch, "source": source})
        data = resp.get("data") or {}

        return json.dumps(
            {
                "ok": data.get("ok", True),
                "playlist_id": playlist_id,
                "total_tracks": total,
                "queued": min(len(tracks), 200),
                "playing": data.get("playing", False),
                "message": f"Playing playlist with {min(len(tracks), 200)} tracks",
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _get_lyrics(self, args: dict) -> str:
        resp = await self._send_command("get_lyrics")
        return json.dumps(resp.get("data", resp), ensure_ascii=False, indent=2)

    async def _set_mode(self, args: dict) -> str:
        mode = args.get("mode", "loop")
        if mode not in ("loop", "shuffle", "single"):
            return json.dumps({"ok": False, "error": f"Invalid mode: {mode}"}, ensure_ascii=False)
        resp = await self._send_command("set_mode", {"mode": mode})
        return json.dumps(resp, ensure_ascii=False)

    async def _like_song(self, args: dict) -> str:
        resp = await self._send_command("like")
        return json.dumps(resp, ensure_ascii=False)

    async def _unlike_song(self, args: dict) -> str:
        resp = await self._send_command("unlike")
        return json.dumps(resp, ensure_ascii=False)

    async def _create_playlist(self, args: dict) -> str:
        name = args.get("name", "")
        resp = await self._send_command("create_playlist", {"name": name})
        return json.dumps(resp, ensure_ascii=False)

    async def _shuffle_queue(self, args: dict) -> str:
        resp = await self._send_command("shuffle_queue")
        return json.dumps(resp, ensure_ascii=False)

    async def _remove_from_queue(self, args: dict) -> str:
        index = int(args.get("index", -1))
        resp = await self._send_command("remove_from_queue", {"index": index})
        return json.dumps(resp, ensure_ascii=False)

    async def _launch(self, args: dict) -> str:
        if self._ws is not None:
            try:
                await self._ws.ping()
                return json.dumps({"ok": True, "message": "Mineradio is already running"}, ensure_ascii=False)
            except Exception:
                pass
        try:
            subprocess.Popen(
                ["npm", "start"],
                cwd=str(MINERADIO_PATH),
                shell=True,
                creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            logger.info("Launched Mineradio")
            for i in range(15):
                await asyncio.sleep(1.5)
                try:
                    await self._connect()
                    return json.dumps(
                        {"ok": True, "message": "Mineradio launched and connected", "port": self._read_port_file()},
                        ensure_ascii=False,
                    )
                except Exception:
                    continue
            return json.dumps(
                {"ok": False, "error": "Mineradio launch timeout, please check manually"}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Launch failed: {e}"}, ensure_ascii=False)

    async def _health(self, args: dict) -> str:
        try:
            await self._ensure_connected()
            return json.dumps(
                {
                    "ok": True,
                    "connected": True,
                    "state": self._state,
                    "port": self._read_port_file(),
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {
                    "ok": True,
                    "connected": False,
                    "error": str(e),
                },
                ensure_ascii=False,
                indent=2,
            )


service = MiyaMineradioService()
