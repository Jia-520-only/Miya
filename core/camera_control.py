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
_VALID_POLICIES = {"auto", "single", "multi"}
_VALID_VISION_CONTROLS = {"user", "miya", "hybrid"}
_VALID_STARTUP_POLICIES = {"on_demand", "resident"}


def _default_state() -> dict[str, Any]:
    return {
        "mode": "off",
        "local_only": True,
        "action_recognition": True,
        "autonomous": False,
        # Which physical sources the autonomous observer may use. ``auto`` lets
        # Miya adapt between the preferred source and periodic multi-camera
        # sweeps; ``single`` and ``multi`` are explicit user choices.
        "camera_policy": "auto",
        "camera_indices": [],
        "preferred_index": None,
        "camera_source_ids": [],
        "preferred_source_id": None,
        "browser_source_ids": [],
        "preferred_browser_source_id": None,
        "vision_control": "hybrid",
        "startup_policy": "resident",
        "consent_granted": False,
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
    control = str(state.get("vision_control") or "hybrid").strip().lower()
    state["vision_control"] = control if control in _VALID_VISION_CONTROLS else "hybrid"
    startup = str(state.get("startup_policy") or "resident").strip().lower()
    state["startup_policy"] = startup if startup in _VALID_STARTUP_POLICIES else "resident"
    state["consent_granted"] = bool(state.get("consent_granted"))
    policy = str(state.get("camera_policy") or "auto").strip().lower()
    state["camera_policy"] = policy if policy in _VALID_POLICIES else "auto"
    raw_indices = state.get("camera_indices")
    if not isinstance(raw_indices, list):
        raw_indices = []
    indices: list[int] = []
    for value in raw_indices:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0 and index not in indices:
            indices.append(index)
    state["camera_indices"] = indices
    raw_browser = state.get("browser_source_ids")
    state["browser_source_ids"] = [str(value)[:120] for value in raw_browser if str(value).strip()] if isinstance(raw_browser, list) else []
    preferred_browser = state.get("preferred_browser_source_id")
    state["preferred_browser_source_id"] = str(preferred_browser)[:120] if preferred_browser else None
    try:
        preferred = state.get("preferred_index")
        state["preferred_index"] = int(preferred) if preferred is not None and int(preferred) >= 0 else None
    except (TypeError, ValueError):
        state["preferred_index"] = None
    raw_source_ids = state.get("camera_source_ids")
    state["camera_source_ids"] = sorted({str(value)[:160] for value in raw_source_ids if str(value).strip()}) if isinstance(raw_source_ids, list) else []
    preferred_source_id = state.get("preferred_source_id")
    state["preferred_source_id"] = str(preferred_source_id)[:160] if preferred_source_id else None
    return state


def write_state(
    mode: str,
    *,
    local_only: bool | None = None,
    action_recognition: bool | None = None,
    autonomous: bool | None = None,
    camera_policy: str | None = None,
    camera_indices: list[int] | None = None,
    preferred_index: int | None = None,
    camera_source_ids: list[str] | None = None,
    preferred_source_id: str | None = None,
    browser_source_ids: list[str] | None = None,
    preferred_browser_source_id: str | None = None,
    vision_control: str | None = None,
    startup_policy: str | None = None,
    consent_granted: bool | None = None,
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
    if camera_policy is not None:
        policy = str(camera_policy).strip().lower()
        if policy not in _VALID_POLICIES:
            raise ValueError(f"unsupported camera policy: {camera_policy}")
        state["camera_policy"] = policy
    if camera_indices is not None:
        state["camera_indices"] = camera_indices
    if preferred_index is not None:
        state["preferred_index"] = preferred_index
    if camera_source_ids is not None:
        state["camera_source_ids"] = camera_source_ids
    if preferred_source_id is not None:
        state["preferred_source_id"] = preferred_source_id
    if browser_source_ids is not None:
        state["browser_source_ids"] = browser_source_ids
    if preferred_browser_source_id is not None:
        state["preferred_browser_source_id"] = preferred_browser_source_id
    if vision_control is not None:
        control = str(vision_control).strip().lower()
        if control not in _VALID_VISION_CONTROLS:
            raise ValueError(f"unsupported vision control: {vision_control}")
        state["vision_control"] = control
    if startup_policy is not None:
        startup = str(startup_policy).strip().lower()
        if startup not in _VALID_STARTUP_POLICIES:
            raise ValueError(f"unsupported startup policy: {startup_policy}")
        state["startup_policy"] = startup
    if consent_granted is not None:
        state["consent_granted"] = bool(consent_granted)
    # Re-apply the same normalization used on reads before persisting values
    # supplied by the HTTP/UI boundary.
    policy = str(state.get("camera_policy") or "auto").strip().lower()
    state["camera_policy"] = policy if policy in _VALID_POLICIES else "auto"
    raw_indices = state.get("camera_indices") if isinstance(state.get("camera_indices"), list) else []
    state["camera_indices"] = sorted({int(value) for value in raw_indices if str(value).lstrip("-").isdigit() and int(value) >= 0})
    raw_source_ids = state.get("camera_source_ids") if isinstance(state.get("camera_source_ids"), list) else []
    state["camera_source_ids"] = sorted({str(value)[:160] for value in raw_source_ids if str(value).strip()})
    state["preferred_source_id"] = str(state.get("preferred_source_id") or "")[:160] or None
    state["browser_source_ids"] = sorted({str(value)[:120] for value in (state.get("browser_source_ids") or []) if str(value).strip()})
    state["preferred_browser_source_id"] = str(state.get("preferred_browser_source_id") or "")[:120] or None
    try:
        preferred = state.get("preferred_index")
        state["preferred_index"] = int(preferred) if preferred is not None and int(preferred) >= 0 else None
    except (TypeError, ValueError):
        state["preferred_index"] = None
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
        f"仅本地：{'开' if state.get('local_only') else '关'}；"
        f"摄像头策略：{'自动' if state.get('camera_policy') == 'auto' else '单路' if state.get('camera_policy') == 'single' else '多路'}。"
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
