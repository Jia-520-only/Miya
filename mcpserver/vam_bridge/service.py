"""MCP bridge for a local Virt-A-Mate (VAM) control plugin.

The VAM side is expected to expose a localhost WebSocket endpoint and speak
the small request/response protocol documented in ``docs/VAM_BRIDGE.md``.
Keeping the bridge here makes VAM optional: Miya can start without the
``websockets`` package or without VAM running, and reports a useful error only
when a VAM tool is called.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("miya.mcp.vam_bridge")

DEFAULT_URL = "ws://127.0.0.1:8765/miya-vam"
DEFAULT_TIMEOUT = 8.0
MAX_TIMEOUT = 30.0
MAX_TEXT_LENGTH = 4000
MAX_DURATION = 30.0

_ACTION_NAMES = {
    "set_expression": "设置人物表情或 Morph 参数",
    "set_pose": "设置人物姿态参数",
    "play_animation": "播放已加载的动作/动画预设",
    "look_at": "让人物看向指定目标",
    "speak": "发送文本用于口型/说话动画同步",
}


class VAMBridgeService:
    """Connect Miya to a local VAM control plugin over WebSocket."""

    def __init__(self) -> None:
        self.name = "vam_bridge"
        self.display_name = "VAM Bridge"
        self.description = "通过本地 WebSocket 受控操作 Virt-A-Mate 人物与场景"
        self.version = "0.1.0"
        self._ws: Any = None
        self._listen_task: Optional[asyncio.Task] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._url = os.getenv("MIYA_VAM_WS_URL", DEFAULT_URL).strip() or DEFAULT_URL
        self._token = os.getenv("MIYA_VAM_TOKEN", "").strip()
        try:
            configured_timeout = float(os.getenv("MIYA_VAM_TIMEOUT", str(DEFAULT_TIMEOUT)))
        except (TypeError, ValueError):
            configured_timeout = DEFAULT_TIMEOUT
        self._timeout = max(1.0, min(configured_timeout, MAX_TIMEOUT))
        self._state: Dict[str, Any] = {}

    def get_tool_definitions(self) -> List[dict]:
        """Return schemas for ToolNet/MCP discovery."""
        return [
            {
                "name": "vam_connect",
                "description": "连接本机 VAM 控制插件。通常首次使用 VAM 工具前调用。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "可选 WebSocket 地址"}},
                    "required": [],
                },
            },
            {
                "name": "vam_disconnect",
                "description": "断开 VAM 控制连接并取消等待中的命令。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "vam_status",
                "description": "获取 VAM 连接、场景和人物状态。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "vam_list_atoms",
                "description": "列出当前 VAM 场景中可控制的人物/Atom。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "vam_set_expression",
                "description": "设置 VAM 人物的表情预设或 Morph 参数。只应使用用户允许的角色和预设。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom 名称"},
                        "expression": {"type": "string", "description": "表情预设名"},
                        "morphs": {"type": "object", "description": "可选 Morph 名称到数值的映射"},
                        "duration": {"type": "number", "description": "过渡秒数，0-30"},
                    },
                    "required": ["atom"],
                },
            },
            {
                "name": "vam_set_pose",
                "description": "设置 VAM 人物姿态预设或受限姿态参数。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom 名称"},
                        "pose": {"type": "string", "description": "姿态预设名"},
                        "parameters": {"type": "object", "description": "可选姿态参数"},
                        "duration": {"type": "number", "description": "过渡秒数，0-30"},
                    },
                    "required": ["atom"],
                },
            },
            {
                "name": "vam_play_animation",
                "description": "播放 VAM 中已配置的安全动画预设。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom 名称"},
                        "animation": {"type": "string", "description": "动画预设名"},
                        "loop": {"type": "boolean", "description": "是否循环"},
                    },
                    "required": ["atom", "animation"],
                },
            },
            {
                "name": "vam_look_at",
                "description": "让 VAM 人物看向用户、镜头或场景中的目标。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom 名称"},
                        "target": {"type": "string", "description": "目标：user、camera 或目标名称"},
                        "duration": {"type": "number", "description": "过渡秒数，0-30"},
                    },
                    "required": ["atom", "target"],
                },
            },
            {
                "name": "vam_speak",
                "description": "把弥娅的文本发送给 VAM，用于口型、说话动画或字幕同步；不负责 TTS 合成。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要说的文本，最多 4000 字符"},
                        "atom": {"type": "string", "description": "可选人物 Atom 名称"},
                        "emotion": {"type": "string", "description": "可选情绪标签"},
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "vam_stop_all",
                "description": "立即停止 VAM 中由弥娅触发的动作、说话和过渡。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        ]

    async def handle_handoff(self, tool_call: dict) -> str:
        tool_name = str(tool_call.get("tool_name", "")).strip()
        args = {k: v for k, v in tool_call.items() if k not in {"service_name", "tool_name", "message"}}
        if isinstance(tool_call.get("arguments"), dict):
            args = tool_call["arguments"]

        handlers = {
            "vam_connect": self._connect_tool,
            "vam_disconnect": self._disconnect_tool,
            "vam_status": self._status_tool,
            "vam_list_atoms": self._list_atoms_tool,
            "vam_set_expression": lambda a: self._action_tool("set_expression", a),
            "vam_set_pose": lambda a: self._action_tool("set_pose", a),
            "vam_play_animation": lambda a: self._action_tool("play_animation", a),
            "vam_look_at": lambda a: self._action_tool("look_at", a),
            "vam_speak": self._speak_tool,
            "vam_stop_all": self._stop_all_tool,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return self._result(False, error=f"未知工具: {tool_name}")
        try:
            return json.dumps(await handler(args), ensure_ascii=False)
        except Exception as exc:
            logger.exception("VAM tool failed: %s", tool_name)
            return self._result(False, error=str(exc))

    async def _connect_tool(self, args: dict) -> dict:
        url = str(args.get("url", "")).strip()
        if url:
            if not _is_loopback_ws_url(url):
                raise ValueError("为安全起见，VAM 地址必须指向 127.0.0.1")
            self._url = url
        await self._ensure_connected()
        return {"ok": True, "connected": True, "url": self._url}

    async def _disconnect_tool(self, _args: dict) -> dict:
        await self._disconnect()
        return {"ok": True, "connected": False}

    async def _status_tool(self, _args: dict) -> dict:
        await self._ensure_connected()
        response = await self._send_request("get_status", {})
        self._state = response.get("data") or {}
        return {"ok": True, "connected": True, "state": self._state}

    async def _list_atoms_tool(self, _args: dict) -> dict:
        await self._ensure_connected()
        response = await self._send_request("list_atoms", {})
        return {"ok": True, "atoms": response.get("data", [])}

    async def _action_tool(self, action: str, args: dict) -> dict:
        if action not in _ACTION_NAMES:
            raise ValueError("不允许的 VAM 操作")
        atom = _required_text(args, "atom", 128)
        params: dict[str, Any] = {"atom": atom}
        if action == "set_expression":
            expression = _optional_text(args, "expression", 128)
            morphs = args.get("morphs")
            if not expression and not isinstance(morphs, dict):
                raise ValueError("set_expression 需要 expression 或 morphs")
            if expression:
                params["expression"] = expression
            if isinstance(morphs, dict):
                params["morphs"] = morphs
        elif action == "set_pose":
            pose = _optional_text(args, "pose", 128)
            parameters = args.get("parameters")
            if not pose and not isinstance(parameters, dict):
                raise ValueError("set_pose 需要 pose 或 parameters")
            if pose:
                params["pose"] = pose
            if isinstance(parameters, dict):
                params["parameters"] = parameters
        elif action == "play_animation":
            params["animation"] = _required_text(args, "animation", 128)
            params["loop"] = bool(args.get("loop", False))
        elif action == "look_at":
            params["target"] = _required_text(args, "target", 128)
        duration = _duration(args.get("duration"))
        if duration is not None:
            params["duration"] = duration
        response = await self._send_request(action, params)
        return {"ok": True, "action": action, "data": response.get("data")}

    async def _speak_tool(self, args: dict) -> dict:
        text = _required_text(args, "text", MAX_TEXT_LENGTH)
        params: dict[str, Any] = {"text": text}
        atom = _optional_text(args, "atom", 128)
        emotion = _optional_text(args, "emotion", 64)
        if atom:
            params["atom"] = atom
        if emotion:
            params["emotion"] = emotion
        response = await self._send_request("speak", params)
        return {"ok": True, "data": response.get("data")}

    async def _stop_all_tool(self, _args: dict) -> dict:
        await self._ensure_connected()
        response = await self._send_request("stop_all", {})
        return {"ok": True, "data": response.get("data")}

    async def _ensure_connected(self) -> None:
        async with self._lock:
            if self._ws is not None:
                return
            if not _is_loopback_ws_url(self._url):
                raise RuntimeError("为安全起见，VAM 地址必须是指向 127.0.0.1 的 ws/wss 地址")
            try:
                import websockets
            except ImportError as exc:
                raise RuntimeError("VAM Bridge 需要 websockets：pip install 'websockets>=12.0'") from exc
            self._ws = await websockets.connect(self._url, open_timeout=self._timeout, close_timeout=2)
            self._listen_task = asyncio.create_task(self._listen_loop(self._ws))
            try:
                await self._send_request("hello", {"client": "miya", "version": self.version})
            except Exception:
                await self._disconnect()
                raise

    async def _disconnect(self) -> None:
        ws, self._ws = self._ws, None
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        error = ConnectionError("VAM Bridge disconnected")
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(error)
        self._pending.clear()
        if ws is not None:
            close = getattr(ws, "close", None)
            if close:
                result = close()
                if asyncio.iscoroutine(result):
                    await result

    async def _listen_loop(self, ws: Any) -> None:
        try:
            async for raw in ws:
                try:
                    message = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                request_id = message.get("id") or message.get("request_id")
                if request_id and request_id in self._pending:
                    future = self._pending[request_id]
                    if not future.done():
                        future.set_result(message)
                elif message.get("type") == "state_update" and isinstance(message.get("data"), dict):
                    self._state = message["data"]
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.info("VAM WebSocket disconnected: %s", exc)
        finally:
            if self._ws is ws:
                self._ws = None
            error = ConnectionError("VAM Bridge disconnected")
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(error)

    async def _send_request(self, action: str, params: dict) -> dict:
        if self._ws is None:
            raise ConnectionError("VAM Bridge 未连接")
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload = {"id": request_id, "type": "command", "action": action, "params": params}
        if self._token:
            payload["token"] = self._token
        try:
            await self._ws.send(json.dumps(payload, ensure_ascii=False))
            response = await asyncio.wait_for(future, timeout=self._timeout)
            if not isinstance(response, dict):
                raise RuntimeError("VAM 返回了无效响应")
            if response.get("ok") is False:
                raise RuntimeError(str(response.get("error") or "VAM 命令失败"))
            return response
        finally:
            self._pending.pop(request_id, None)

    @staticmethod
    def _result(ok: bool, **payload: Any) -> str:
        return json.dumps({"ok": ok, **payload}, ensure_ascii=False)


def _required_text(args: dict, key: str, limit: int) -> str:
    value = str(args.get(key, "")).strip()
    if not value:
        raise ValueError(f"缺少参数: {key}")
    if len(value) > limit:
        raise ValueError(f"参数 {key} 过长（最多 {limit} 字符）")
    return value


def _optional_text(args: dict, key: str, limit: int) -> str:
    value = str(args.get(key, "")).strip()
    if len(value) > limit:
        raise ValueError(f"参数 {key} 过长（最多 {limit} 字符）")
    return value


def _duration(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("duration 必须是数字") from exc
    if not 0 <= duration <= MAX_DURATION:
        raise ValueError(f"duration 必须在 0 到 {MAX_DURATION} 秒之间")
    return duration


def _is_loopback_ws_url(value: str) -> bool:
    """Allow only websocket URLs whose parsed hostname is exactly localhost."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"ws", "wss"} and parsed.hostname == "127.0.0.1"
