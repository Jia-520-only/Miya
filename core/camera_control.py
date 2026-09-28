"""Small cross-process control plane for the desktop camera companion.

Chat platforms and the desktop browser do not share a JavaScript runtime.  A
single atomic JSON state gives slash commands a safe way to request a camera
mode without ever carrying an image or camera permission across the boundary.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[1]
_STATE_PATH = _ROOT / "data" / "camera_control.json"
_REQUEST_PATH = _ROOT / "data" / "camera_observation_request.json"
_RESULT_PATH = _ROOT / "data" / "camera_observation_result.json"
_VALID_MODES = {"off", "companion", "snapshot"}


def _default_state() -> dict[str, Any]:
    return {
        "mode": "off",
        "local_only": False,
        "action_recognition": True,
        "autonomous": False,
        "request_id": "initial",
        "updated_at": 0.0,
    }


def read_state() -> dict[str, Any]:
    """Read the latest requested camera mode; malformed files fail closed."""
    try:
        value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("camera control state is not an object")
    except (OSError, ValueError, json.JSONDecodeError):
        return _default_state()
    state = _default_state()
    state.update(value)
    if state["mode"] not in _VALID_MODES:
        state["mode"] = "off"
    state["local_only"] = bool(state["local_only"])
    state["action_recognition"] = bool(state["action_recognition"])
    state["autonomous"] = bool(state["autonomous"])
    return state


def write_state(
    mode: str,
    *,
    local_only: bool | None = None,
    action_recognition: bool | None = None,
    autonomous: bool | None = None,
) -> dict[str, Any]:
    """Atomically publish a new desired mode and return the persisted state."""
    if mode not in _VALID_MODES:
        raise ValueError(f"unsupported camera mode: {mode}")
    state = read_state()
    state["mode"] = mode
    if local_only is not None:
        state["local_only"] = bool(local_only)
    if action_recognition is not None:
        state["action_recognition"] = bool(action_recognition)
    if autonomous is not None:
        state["autonomous"] = bool(autonomous)
    state["request_id"] = uuid.uuid4().hex
    state["updated_at"] = time.time()

    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="camera-control-", suffix=".json", dir=_STATE_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, _STATE_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return state


def describe_state(state: dict[str, Any] | None = None) -> str:
    state = state or read_state()
    mode_names = {"off": "关闭", "companion": "陪伴视觉", "snapshot": "单次观察"}
    return (
        f"摄像头视觉：{mode_names.get(state.get('mode'), '关闭')}；"
        f"弥娅自主观察：{'开' if state.get('autonomous') else '关'}；"
        f"本地动作识别：{'开' if state.get('action_recognition', True) else '关'}；"
        f"仅本地：{'开' if state.get('local_only') else '关'}。"
    )


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def request_observation(query: str = "", *, local_only: bool | None = None) -> dict[str, Any]:
    """Queue one model-requested observation; no image crosses this boundary."""
    request = {
        "request_id": uuid.uuid4().hex,
        "query": str(query or "请观察我当前的姿态、动作和环境。")[:2000],
        "local_only": local_only,
        "created_at": time.time(),
    }
    _atomic_write(_REQUEST_PATH, request)
    return request


def read_observation_request() -> dict[str, Any] | None:
    try:
        value = json.loads(_REQUEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or not value.get("request_id"):
        return None
    # A request is a one-shot handshake. Never let a newly opened desktop
    # process execute a stale observation from a previous session.
    try:
        if time.time() - float(value.get("created_at", 0)) > 60:
            return None
    except (TypeError, ValueError):
        return None
    return value


def publish_observation_result(request_id: str, result: dict[str, Any]) -> None:
    _atomic_write(_RESULT_PATH, {"request_id": request_id, "result": result, "created_at": time.time()})


def wait_for_observation_result(request_id: str, timeout: float = 25.0) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, min(float(timeout), 60.0))
    while time.monotonic() < deadline:
        try:
            value = json.loads(_RESULT_PATH.read_text(encoding="utf-8"))
            if value.get("request_id") == request_id and isinstance(value.get("result"), dict):
                return value["result"]
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    return None
