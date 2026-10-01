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
MAX_DURATION = 30.0
MAX_MOVE_OFFSET = 0.25
MAX_MOVE_DURATION = 5.0
MAX_SEQUENCE_STEPS = 32
MAX_SEQUENCE_WAIT = 60.0
MAX_SEQUENCE_CYCLE = 300.0
MIN_AUTONOMY_INTERVAL = 15.0
MAX_AUTONOMY_INTERVAL = 900.0
USER_CLOSE_DISTANCE = 1.5
USER_NEAR_DISTANCE = 3.0
USER_ENGAGED_ANGLE = 35.0
USER_VISIBLE_ANGLE = 70.0

_ACTION_NAMES = {
    "set_expression": "设置人物表情或 Morph 参数",
    "look_at": "让人物看向指定目标",
}


class VAMBridgeService:
    """Connect Miya to a local VAM control plugin over WebSocket."""

    def __init__(self) -> None:
        self.name = "vam_bridge"
        self.display_name = "VAM Bridge"
        self.description = "通过本地 WebSocket 受控操作 Virt-A-Mate 人物与场景"
        self.version = "0.4.0"
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
        self._autonomy_task: Optional[asyncio.Task] = None
        self._autonomy: Dict[str, Any] = {
            "enabled": False,
            "atom": "",
            "interval": 45.0,
            "mode": "ambient",
            "phase": 0,
            "last_decision": "",
            "last_error": "",
            "last_run": 0.0,
            "last_context": "unknown",
            "last_strategy": "",
            "user_distance": None,
            "user_gaze_angle": None,
            "user_in_view": None,
            "plugin_state_available": False,
            "plugin_state_error": "",
        }

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
                "name": "vam_inspect_person",
                "description": "暂时禁用：复杂插件参数自动枚举可能耗尽 VaM/Mono 堆；请使用固定的安全控制接口。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom UID"},
                        "storable": {"type": "string", "description": "可选，只查看一个控制器或插件"},
                    },
                    "required": ["atom"],
                },
            },
            {
                "name": "vam_get_person_state",
                "description": "只读获取人物及其插件当前公开参数值和动作清单，用于状态反馈。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom UID"},
                        "storable": {"type": "string", "description": "必须指定一个控制器或插件 ID，避免读取整棵插件树"},
                    },
                    "required": ["atom", "storable"],
                },
            },
            {
                "name": "vam_set_person_params",
                "description": "设置人物或其已加载插件公开的参数；仅使用已知且经过场景配置的安全参数。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string"},
                        "storable": {"type": "string"},
                        "values": {"type": "object", "description": "参数名到新值的映射，单次最多 32 项"},
                    },
                    "required": ["atom", "storable", "values"],
                },
            },
            {
                "name": "vam_call_person_action",
                "description": "调用人物或其已加载插件公开的动作；仅使用已知且经过场景配置的安全动作。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string"},
                        "storable": {"type": "string"},
                        "action": {"type": "string"},
                    },
                    "required": ["atom", "storable", "action"],
                },
            },
            {
                "name": "vam_run_sequence",
                "description": "提交一段由 VAM 主线程连续执行的动作序列，支持等待、过渡和循环。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string"},
                        "steps": {"type": "array", "description": "最多 32 步；每步含 action 和可选 wait"},
                        "loop": {"type": "boolean", "description": "是否循环执行，直到 vam_stop_all"},
                        "gap": {"type": "number", "description": "循环间隔秒数，0-60"},
                    },
                    "required": ["atom", "steps"],
                },
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
                "name": "vam_move_person",
                "description": "让当前场景中的人物沿安全限幅的相对位移平滑移动。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "人物 Atom UID"},
                        "offset": {"type": "object", "description": "相对当前位置的 x/y/z 位移，单轴不超过 0.25 米"},
                        "duration": {"type": "number", "description": "平滑移动时长，0-5 秒"},
                    },
                    "required": ["atom", "offset"],
                },
            },
            {
                "name": "vam_stop_all",
                "description": "恢复桥接修改的表情与视线，并停止人物内建动画时间线。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "vam_autonomy_start",
                "description": "启动弥娅的 VAM 主动行为循环；只在 VAM 空闲时编排短动作序列。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "atom": {"type": "string", "description": "可选人物 UID，省略时使用首个人物"},
                        "interval": {"type": "number", "description": "检查间隔，15-900 秒"},
                        "mode": {"type": "string", "description": "ambient 或 responsive"},
                    },
                    "required": [],
                },
            },
            {
                "name": "vam_autonomy_stop",
                "description": "停止弥娅的 VAM 主动行为循环，不影响当前场景的非弥娅动作。",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "vam_autonomy_status",
                "description": "查看弥娅 VAM 主动行为循环的运行状态。",
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
            "vam_inspect_person": self._inspect_person_tool,
            "vam_get_person_state": self._get_person_state_tool,
            "vam_set_person_params": self._set_person_params_tool,
            "vam_call_person_action": self._call_person_action_tool,
            "vam_run_sequence": self._run_sequence_tool,
            "vam_set_expression": lambda a: self._action_tool("set_expression", a),
            "vam_look_at": lambda a: self._action_tool("look_at", a),
            "vam_move_person": self._move_person_tool,
            "vam_stop_all": self._stop_all_tool,
            "vam_autonomy_start": self._autonomy_start_tool,
            "vam_autonomy_stop": self._autonomy_stop_tool,
            "vam_autonomy_status": self._autonomy_status_tool,
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
        await self._stop_autonomy("disconnect")
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

    async def _inspect_person_tool(self, args: dict) -> dict:
        raise RuntimeError(
            "为避免 VaM/Mono 堆耗尽，暂时禁用插件参数自动枚举；请使用固定的安全控制接口"
        )

    async def _get_person_state_tool(self, args: dict) -> dict:
        atom = _required_text(args, "atom", 128)
        storable = _required_text(args, "storable", 128)
        await self._ensure_connected()
        response = await self._send_request(
            "get_person_state", {"atom": atom, "storable": storable}
        )
        return {"ok": True, "data": response.get("data")}

    async def _set_person_params_tool(self, args: dict) -> dict:
        atom = _required_text(args, "atom", 128)
        storable = _required_text(args, "storable", 128)
        values = args.get("values")
        if not isinstance(values, dict) or not values:
            raise ValueError("values 必须是非空对象")
        if len(values) > 32:
            raise ValueError("单次最多设置 32 个参数")
        for name in values:
            if not isinstance(name, str) or not name.strip() or len(name) > 128:
                raise ValueError("参数名必须是 1 到 128 字符的文本")
        await self._ensure_connected()
        response = await self._send_request(
            "set_person_params", {"atom": atom, "storable": storable, "values": values}
        )
        return {"ok": True, "data": response.get("data")}

    async def _call_person_action_tool(self, args: dict) -> dict:
        params = {
            "atom": _required_text(args, "atom", 128),
            "storable": _required_text(args, "storable", 128),
            "action": _required_text(args, "action", 128),
        }
        await self._ensure_connected()
        response = await self._send_request("call_person_action", params)
        return {"ok": True, "data": response.get("data")}

    async def _run_sequence_tool(self, args: dict) -> dict:
        await self._stop_autonomy("manual_sequence")
        atom = _required_text(args, "atom", 128)
        steps = args.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps 必须是非空数组")
        if len(steps) > MAX_SEQUENCE_STEPS:
            raise ValueError(f"单段序列最多 {MAX_SEQUENCE_STEPS} 步")
        total_wait = 0.0
        normalized = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("每个 sequence step 必须是对象")
            action = _required_text(step, "action", 64)
            if action not in {"set_expression", "look_at", "move_person", "set_person_params", "call_person_action"}:
                raise ValueError(f"不允许的 sequence action: {action}")
            wait = _duration_limit(step.get("wait"), MAX_SEQUENCE_WAIT, "wait") or 0.0
            item = dict(step)
            item["action"] = action
            item["wait"] = wait
            if action == "set_expression":
                expression = _optional_text(step, "expression", 128)
                morphs = step.get("morphs")
                if not expression and not isinstance(morphs, dict):
                    raise ValueError("sequence set_expression 需要 expression 或 morphs")
                if isinstance(morphs, dict) and len(morphs) > 16:
                    raise ValueError("单步最多设置 16 个 Morph")
                duration = _duration(step.get("duration"))
                if duration is not None:
                    item["duration"] = duration
                    wait = max(wait, duration)
                    item["wait"] = wait
            elif action == "look_at":
                item["target"] = _required_text(step, "target", 128)
            elif action == "move_person":
                item["offset"] = _move_offset(step.get("offset"))
                item["duration"] = _move_duration(step.get("duration", 0.6))
                wait = max(wait, item["duration"])
                item["wait"] = wait
            elif action == "set_person_params":
                item["storable"] = _required_text(step, "storable", 128)
                values = step.get("values")
                if not isinstance(values, dict) or not values or len(values) > 32:
                    raise ValueError("sequence set_person_params 的 values 必须含 1 到 32 项")
                item["values"] = values
            else:
                item["storable"] = _required_text(step, "storable", 128)
                item["actionName"] = _required_text(step, "actionName", 128)
            total_wait += wait
            normalized.append(item)
        gap = _duration_limit(args.get("gap"), MAX_SEQUENCE_WAIT, "gap") or 0.0
        if bool(args.get("loop", False)) and gap < 0.5:
            gap = 0.5
        if total_wait + gap > MAX_SEQUENCE_CYCLE:
            raise ValueError(f"单次序列周期不能超过 {MAX_SEQUENCE_CYCLE} 秒")
        await self._ensure_connected()
        response = await self._send_request(
            "run_sequence",
            {"atom": atom, "steps": normalized, "loop": bool(args.get("loop", False)), "gap": gap},
        )
        return {"ok": True, "data": response.get("data")}

    async def _move_person_tool(self, args: dict) -> dict:
        atom = _required_text(args, "atom", 128)
        params = {
            "atom": atom,
            "offset": _move_offset(args.get("offset")),
            "duration": _move_duration(args.get("duration", 0.6)),
        }
        await self._stop_autonomy("manual_move")
        await self._ensure_connected()
        response = await self._send_request("move_person", params)
        return {"ok": True, "data": response.get("data")}

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
        elif action == "look_at":
            params["target"] = _required_text(args, "target", 128)
        duration = _duration(args.get("duration"))
        if duration is not None:
            params["duration"] = duration
        response = await self._send_request(action, params)
        return {"ok": True, "action": action, "data": response.get("data")}

    async def _stop_all_tool(self, _args: dict) -> dict:
        await self._stop_autonomy("stop_all")
        await self._ensure_connected()
        response = await self._send_request("stop_all", {})
        return {"ok": True, "data": response.get("data")}

    async def _autonomy_start_tool(self, args: dict) -> dict:
        await self._ensure_connected()
        atom = _optional_text(args, "atom", 128)
        interval = _duration_limit(
            args.get("interval", self._autonomy["interval"]),
            MAX_AUTONOMY_INTERVAL,
            "interval",
        )
        interval = max(MIN_AUTONOMY_INTERVAL, interval or self._autonomy["interval"])
        mode = _optional_text(args, "mode", 32).lower() or "ambient"
        if mode not in {"ambient", "responsive"}:
            raise ValueError("mode 必须是 ambient 或 responsive")

        atoms_response = await self._send_request("list_atoms", {})
        atoms = atoms_response.get("data", [])
        if not isinstance(atoms, list) or not atoms:
            raise RuntimeError("VAM 当前没有可控制的人物")
        atom_ids = {str(item.get("uid", "")) for item in atoms if isinstance(item, dict)}
        atom = atom or next(iter(atom_ids), "")
        if not atom or atom not in atom_ids:
            raise ValueError("atom 不是当前场景中的可控人物")

        await self._stop_autonomy("restarted")
        self._autonomy.update(
            {
                "enabled": True,
                "atom": atom,
                "interval": interval,
                "mode": mode,
                "phase": 0,
                "last_decision": "started",
                "last_error": "",
                "last_run": 0.0,
            }
        )
        # Perform the first decision before returning so callers can observe a
        # concrete action immediately; the background loop handles later ticks.
        try:
            await self._autonomy_tick()
        except Exception:
            self._autonomy["enabled"] = False
            raise
        self._autonomy_task = asyncio.create_task(self._autonomy_loop(), name="vam-autonomy")
        return {"ok": True, "autonomy": self._autonomy_snapshot()}

    async def _autonomy_stop_tool(self, _args: dict) -> dict:
        await self._stop_autonomy("user")
        return {"ok": True, "autonomy": self._autonomy_snapshot()}

    async def _autonomy_status_tool(self, _args: dict) -> dict:
        return {"ok": True, "autonomy": self._autonomy_snapshot()}

    async def _stop_autonomy(self, reason: str) -> None:
        task, self._autonomy_task = self._autonomy_task, None
        self._autonomy["enabled"] = False
        self._autonomy["last_decision"] = f"stopped:{reason}"
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def _autonomy_snapshot(self) -> dict:
        snapshot = dict(self._autonomy)
        snapshot["task_alive"] = bool(self._autonomy_task and not self._autonomy_task.done())
        snapshot["state_activity"] = (self._state.get("activity") or {}) if isinstance(self._state, dict) else {}
        return snapshot

    async def _autonomy_loop(self) -> None:
        try:
            while self._autonomy.get("enabled"):
                await asyncio.sleep(float(self._autonomy["interval"]))
                if self._autonomy.get("enabled"):
                    await self._autonomy_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._autonomy["last_error"] = str(exc)
            self._autonomy["last_decision"] = "failed"
            logger.warning("VAM autonomy loop failed: %s", exc)
        finally:
            if self._autonomy_task is asyncio.current_task():
                self._autonomy_task = None
            if self._autonomy.get("last_decision") != "failed":
                self._autonomy["enabled"] = False

    async def _autonomy_tick(self) -> None:
        status = await self._send_request("get_status", {})
        state = status.get("data") or {}
        if isinstance(state, dict):
            self._state = state
        activity = state.get("activity") if isinstance(state, dict) else None
        if isinstance(activity, dict) and _as_bool(activity.get("active")):
            self._autonomy["last_decision"] = "wait:scene_active"
            return

        atom = str(self._autonomy.get("atom") or "")
        if not atom:
            self._autonomy["last_decision"] = "wait:no_atom"
            return
        context = self._person_context(state, atom)
        self._autonomy.update(
            {
                "last_context": context["name"],
                "user_distance": context["distance"],
                "user_gaze_angle": context["gaze_angle"],
                "user_in_view": context["in_view"],
            }
        )
        sequence, strategy = self._build_autonomy_sequence(
            str(self._autonomy.get("mode", "ambient")), int(self._autonomy["phase"]), context["name"]
        )
        response = await self._send_request(
            "run_sequence",
            {"atom": atom, "steps": sequence, "loop": False, "gap": 0.0},
        )
        self._autonomy["phase"] = (int(self._autonomy["phase"]) + 1) % 4
        self._autonomy["last_run"] = asyncio.get_running_loop().time()
        self._autonomy["last_decision"] = "sequence_started"
        self._autonomy["last_strategy"] = strategy
        self._autonomy["last_error"] = ""
        self._state["last_autonomy_sequence"] = response.get("data")

    @staticmethod
    def _person_context(state: dict, atom: str) -> dict:
        scene = state.get("sceneState") if isinstance(state, dict) else None
        persons = scene.get("persons") if isinstance(scene, dict) else None
        item = next(
            (person for person in persons or [] if isinstance(person, dict) and str(person.get("uid")) == atom),
            None,
        )
        distance = _finite_float(item.get("userDistance")) if item else None
        gaze_angle = _finite_float(item.get("userGazeAngle")) if item else None
        in_view = _as_bool(item.get("userInView")) if item and "userInView" in item else None
        if distance is None or gaze_angle is None:
            return {"name": "unknown", "distance": distance, "gaze_angle": gaze_angle, "in_view": in_view}
        if distance <= USER_CLOSE_DISTANCE and gaze_angle <= USER_ENGAGED_ANGLE:
            name = "close_engaged"
        elif distance <= USER_NEAR_DISTANCE and gaze_angle <= USER_ENGAGED_ANGLE:
            name = "near_engaged"
        elif distance <= USER_NEAR_DISTANCE and gaze_angle <= USER_VISIBLE_ANGLE:
            name = "near_away"
        else:
            name = "far"
        return {"name": name, "distance": distance, "gaze_angle": gaze_angle, "in_view": in_view}

    @staticmethod
    def _build_autonomy_sequence(mode: str, phase: int, context: str) -> tuple[list[dict], str]:
        if context == "close_engaged":
            expression = "surprised" if phase % 3 == 1 else "happy"
            return [
                {"action": "look_at", "target": "user", "wait": 0.5},
                {"action": "set_expression", "expression": expression, "duration": 0.6, "wait": 1.8},
                {"action": "set_expression", "expression": "neutral", "duration": 1.0, "wait": 0.8},
            ], "welcome_close"
        if context == "near_engaged":
            expression = "happy" if (mode == "responsive" or phase % 2 == 0) else "neutral"
            return [
                {"action": "look_at", "target": "user", "wait": 0.8},
                {"action": "set_expression", "expression": expression, "duration": 0.8, "wait": 2.4},
                {"action": "set_expression", "expression": "neutral", "duration": 1.2, "wait": 1.0},
            ], "acknowledge_near"
        if context == "near_away":
            return [
                {"action": "look_at", "target": "user", "wait": 1.2},
                {"action": "set_expression", "expression": "neutral", "duration": 1.0, "wait": 2.8},
            ], "reacquire_attention"
        if context == "far":
            return [
                {"action": "look_at", "target": "camera", "wait": 1.5},
                {"action": "set_expression", "expression": "neutral", "duration": 1.4, "wait": 3.0},
            ], "ambient_far"

        expressions = ["happy", "surprised", "neutral", "happy"]
        expression = expressions[phase % len(expressions)]
        target = "user" if phase % 3 != 1 else "camera"
        return [
            {"action": "look_at", "target": target, "wait": 1.0},
            {"action": "set_expression", "expression": expression, "duration": 0.8, "wait": 2.0},
            {"action": "set_expression", "expression": "neutral", "duration": 1.2, "wait": 1.0},
        ], "ambient_unknown"

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


def _finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _duration_limit(value: Any, maximum: float, name: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not 0 <= duration <= maximum:
        raise ValueError(f"{name} 必须在 0 到 {maximum} 秒之间")
    return duration


def _move_duration(value: Any) -> float:
    duration = _duration_limit(value, MAX_MOVE_DURATION, "duration")
    return 0.6 if duration is None else duration


def _move_offset(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("offset 必须是含 x、y、z 的对象")
    result: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        number = _finite_float(value.get(axis, 0.0))
        if number is None or abs(number) > MAX_MOVE_OFFSET:
            raise ValueError(f"offset.{axis} 必须是有限数字且绝对值不超过 {MAX_MOVE_OFFSET} 米")
        result[axis] = number
    return result


def _is_loopback_ws_url(value: str) -> bool:
    """Allow only websocket URLs whose parsed hostname is exactly localhost."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"ws", "wss"} and parsed.hostname == "127.0.0.1"
