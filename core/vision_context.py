"""Shared, image-free context for Miya's screen and camera senses.

The browser owns camera permission and frame capture, while the backend owns
screen awareness and proactive chat.  This small process-local store is the
meeting point between the two without moving or persisting raw images.
"""

from __future__ import annotations

import threading
import time
import math
from collections import deque
from typing import Any


_TRANSIENT_KINDS = frozenset({
    "wave", "sit_down", "stand_up", "walk", "clap", "stretch", "nod", "raised_hand",
})
_HEALTH_KINDS = frozenset({"camera_health"})


class VisionContextStore:
    """Bounded, thread-safe stream of derived visual observations."""

    def __init__(self, max_events: int = 120) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(20, int(max_events)))
        self._lock = threading.RLock()

    def add(self, event: dict[str, Any]) -> dict[str, Any]:
        safe = dict(event)
        safe["timestamp"] = float(safe.get("timestamp") or time.time())
        if not math.isfinite(safe["timestamp"]):
            raise ValueError("Visual observation time must be finite")
        safe["observed_at"] = safe["timestamp"]
        safe["expires_at"] = float(safe.get("expires_at") or safe["timestamp"] + 180.0)
        if not math.isfinite(safe["expires_at"]):
            raise ValueError("Visual observation expiry must be finite")
        safe["visibility"] = "owner"
        safe["source"] = str(safe.get("source") or "unknown")
        safe["summary"] = str(safe.get("summary") or "").strip()[:1000]
        safe["kind"] = str(safe.get("kind") or "observation")
        source_ids = safe.get("source_ids")
        if not isinstance(source_ids, list):
            source_ids = safe.get("camera_source_ids")
        if not isinstance(source_ids, list) and safe.get("source_id"):
            source_ids = [safe.get("source_id")]
        safe["source_ids"] = sorted({
            str(item).strip()[:160] for item in (source_ids or []) if str(item).strip()
        })
        if safe.get("source_id"):
            safe["source_id"] = str(safe["source_id"]).strip()[:160]
        safe.pop("image_data", None)
        safe.pop("image_url", None)
        with self._lock:
            previous = self._events[-1] if self._events else None
            if (
                previous
                and previous.get("source") == safe.get("source")
                and previous.get("kind") == safe.get("kind")
                and previous.get("source_ids") == safe.get("source_ids")
                and previous.get("summary") == safe.get("summary")
                and 0 <= safe["timestamp"] - float(previous.get("timestamp", 0)) < 2.0
            ):
                return previous
            self._events.append(safe)
        return safe

    @staticmethod
    def _matches_source(event: dict[str, Any], source_id: str | None) -> bool:
        if not source_id:
            return True
        wanted = str(source_id)
        ids = event.get("source_ids") or event.get("camera_source_ids") or []
        return wanted == str(event.get("source_id") or "") or wanted in {str(item) for item in ids}

    def recent(
        self, *, source: str | None = None, source_id: str | None = None, limit: int = 12,
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if source:
            events = [event for event in events if event.get("source") == source]
        if source_id:
            events = [event for event in events if self._matches_source(event, source_id)]
        return events[-max(1, int(limit)) :]

    def latest(self, *, source: str | None = None, source_id: str | None = None) -> dict[str, Any] | None:
        events = self.recent(source=source, source_id=source_id, limit=1)
        return events[0] if events else None

    def current(
        self, *, source: str | None = None, source_id: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Return the latest event and the latest still-valid sustained state.

        Gestures are news, but they should not replace durable state such as
        "在电脑前". Keeping both views here prevents each consumer from rebuilding
        its own interpretation of the event history.
        """
        moment = time.time() if now is None else float(now)
        with self._lock:
            events = list(self._events)
        if source:
            events = [event for event in events if event.get("source") == source]
        if source_id:
            events = [event for event in events if self._matches_source(event, source_id)]
        fresh = [
            event for event in events
            if float(event.get("timestamp") or 0.0) <= moment
            and moment <= float(event.get("expires_at") or 0.0)
        ]
        semantic = [event for event in fresh if event.get("kind") not in _HEALTH_KINDS]
        health_events = [event for event in fresh if event.get("kind") in _HEALTH_KINDS]
        latest = semantic[-1] if semantic else None
        state = next(
            (
                event for event in reversed(fresh)
                if event.get("kind") not in _HEALTH_KINDS
                and str(event.get("kind") or "observation") not in _TRANSIENT_KINDS
            ),
            None,
        )
        health_by_source: dict[str, dict[str, Any]] = {}
        for event in health_events:
            ids = event.get("source_ids") or ([event.get("source_id")] if event.get("source_id") else [])
            for item in ids:
                key = str(item).strip()
                if key:
                    health_by_source[key] = dict(event)
        return {
            "source": source,
            "source_id": source_id,
            "latest": dict(latest) if latest else None,
            "state": dict(state) if state else None,
            "health": dict(health_events[-1]) if health_events else None,
            "health_by_source": health_by_source,
            "sources": sorted(health_by_source),
            "age_seconds": (
                None if latest is None else round(max(0.0, moment - float(latest.get("timestamp") or moment)), 3)
            ),
            "stale": latest is None and any(event.get("kind") not in _HEALTH_KINDS for event in events),
            "observed_at": None if latest is None else latest.get("timestamp"),
            "expires_at": None if latest is None else latest.get("expires_at"),
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def build_card(
        self, *, source: str | None = None, limit: int = 8, max_age: float = 180.0, now: float | None = None
    ) -> str:
        """Build a compact prompt card from derived observations only."""
        from datetime import datetime

        events = self.recent(source=source, limit=limit)
        moment = time.time() if now is None else now
        events = [event for event in events if (
            0 <= moment - float(event["timestamp"]) <= max_age
            and moment <= float(event.get("expires_at", event["timestamp"] + max_age))
        )]
        events = [event for event in events if event.get("kind") not in _HEALTH_KINDS]
        if not events:
            return ""
        title = "[弥娅的摄像头感知]" if source == "camera" else "[弥娅的视觉上下文]"
        lines = [title]
        for event in events:
            stamp = datetime.fromtimestamp(float(event["timestamp"])).strftime("%m-%d %H:%M:%S")
            summary = event.get("summary") or "（没有可用摘要）"
            mode = event.get("mode")
            suffix = f" · {mode}" if mode else ""
            lines.append(f"- {stamp} [{event.get('kind', 'observation')}{suffix}] {summary[:240]}")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
        return {
            "total": len(events),
            "screen": sum(1 for event in events if event.get("source") == "screen"),
            "camera": sum(1 for event in events if event.get("source") == "camera"),
            "latest": events[-1] if events else None,
            "camera_sources": sorted({
                source_id
                for event in events if event.get("source") == "camera"
                for source_id in (event.get("source_ids") or [])
            }),
        }


_store = VisionContextStore()


def get_vision_context() -> VisionContextStore:
    return _store


def record_camera_observation(
    result: dict[str, Any],
    *,
    query: str = "",
    mode: str = "snapshot",
    local_only: bool | None = None,
    proactive: bool = False,
) -> dict[str, Any]:
    """Record a camera result while deliberately excluding image payloads."""
    observations = result.get("observations") if isinstance(result, dict) else None
    summary = str(result.get("message") or "").strip() if isinstance(result, dict) else ""
    if not summary and isinstance(observations, list):
        parts: list[str] = []
        for item in observations[:3]:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if isinstance(action, dict) and action.get("label"):
                parts.append(f"动作：{action['label']}")
            identity = item.get("identity")
            if isinstance(identity, dict) and identity.get("name"):
                parts.append(f"身份：{identity['name']}")
        summary = "；".join(parts)
    if not summary:
        summary = "摄像头观察完成" if result.get("status") == "success" else "摄像头观察未得到明确结果"
    source_ids = _camera_source_ids(result)
    event = _store.add(
        {
            "source": "camera",
            "kind": "proactive_observation" if proactive else "observation",
            "summary": summary,
            "query": str(query or "")[:300],
            "mode": str(mode or "snapshot"),
            "local_only": local_only,
            "status": result.get("status"),
            "source_ids": source_ids,
        }
    )
    observations = result.get("observations") if isinstance(result, dict) else None
    if isinstance(observations, list):
        for item in observations[:3]:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if not isinstance(action, dict) or not action.get("kind"):
                continue
            action_event = _store.add({
                "source": "camera",
                "kind": str(action.get("kind")),
                "summary": str(action.get("label") or action.get("kind")),
                "confidence": float(action.get("confidence") or 0),
                "mode": mode,
                "status": result.get("status"),
                "source_ids": source_ids,
            })
            event = action_event
    return event


def record_camera_event(
    *,
    kind: str,
    summary: str,
    confidence: float = 0.0,
    mode: str = "autonomous",
    status: str = "success",
    camera_indices: list[int] | None = None,
    camera_source_ids: list[str] | None = None,
    faces: int | None = None,
) -> dict[str, Any]:
    """Record one derived camera event from Miya's own observation loop.

    Two producers write here and they must both be able to: the desktop preview,
    which hands frames over through ``/api/camera/result``, and Miya's own
    autonomous loop, which owns the camera when no window is open. Only the
    browser path used to write, so with the desktop app closed the camera-aware
    trigger read an empty store and could never fire - she watched all evening
    and the one path that turns seeing into speaking saw nothing at all.

    Derived values only: the caller passes a gesture kind and a sentence, never a
    frame.
    """
    text = str(summary or "").strip()
    if not text:
        return {}
    return _store.add(
        {
            "source": "camera",
            "kind": str(kind or "observation"),
            "summary": text[:1000],
            "confidence": float(confidence or 0.0),
            "mode": str(mode or "autonomous"),
            "status": str(status or "success"),
            "camera_indices": list(camera_indices or []),
            "source_ids": [str(item)[:160] for item in (camera_source_ids or []) if str(item).strip()],
            "faces": faces,
        }
    )


def record_camera_state(
    *,
    summary: str,
    activity: str = "",
    presence: dict[str, Any] | None = None,
    confidence: float = 0.0,
    faces: int | None = None,
    camera_indices: list[int] | None = None,
    camera_source_ids: list[str] | None = None,
    mode: str = "autonomous",
) -> dict[str, Any]:
    """Publish one image-free current-state reading from Miya's own observer."""
    text = str(summary or "").strip()
    if not text:
        return {}
    return _store.add({
        "source": "camera",
        "kind": "camera_state",
        "summary": text[:1000],
        "activity": str(activity or "")[:160],
        "presence": dict(presence or {}),
        "confidence": float(confidence or 0.0),
        "faces": faces,
        "camera_indices": list(camera_indices or []),
        "source_ids": [str(item)[:160] for item in (camera_source_ids or []) if str(item).strip()],
        "mode": str(mode or "autonomous"),
    })


def _camera_source_ids(result: dict[str, Any] | None) -> list[str]:
    """Extract stable camera identities without retaining frame payloads."""
    if not isinstance(result, dict):
        return []
    values: list[Any] = []
    for key in ("source_ids", "camera_source_ids", "browser_source_ids"):
        if isinstance(result.get(key), list):
            values.extend(result[key])
    for item in result.get("captures") or []:
        if isinstance(item, dict) and item.get("source_id"):
            values.append(item["source_id"])
    return sorted({str(item).strip()[:160] for item in values if str(item).strip()})


def record_camera_health(
    *,
    source_id: str | None,
    health: str,
    reason: str = "",
    index: int | None = None,
    mode: str = "autonomous",
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Publish device health separately from what the pixels mean.

    A dark or disconnected camera must never become a presence observation.
    Consumers can show this as a diagnostic while keeping "佳离开了" strictly
    tied to a valid visual reading.
    """
    stable_id = str(source_id or (f"index:{int(index)}" if index is not None else "")).strip()[:160]
    if not stable_id:
        return {}
    state = str(health or "unknown").strip().lower()[:40] or "unknown"
    label = {
        "online": "在线",
        "black_frame": "黑帧",
        "frozen_frame": "画面冻结",
        "no_frame": "没有画面",
        "disconnected": "已断开",
        "unopenable": "无法打开",
    }.get(state, state)
    return _store.add({
        "source": "camera",
        "kind": "camera_health",
        "source_id": stable_id,
        "source_ids": [stable_id],
        "health": state,
        "summary": f"摄像头{label}" + (f"：{str(reason).strip()[:240]}" if str(reason).strip() else ""),
        "reason": str(reason or "").strip()[:500],
        "index": index,
        "mode": str(mode or "autonomous"),
        "timestamp": timestamp,
        "expires_at": (float(timestamp) if timestamp is not None else time.time()) + 180.0,
    })


def record_screen_observation(observation: Any) -> dict[str, Any]:
    """Record the derived portion of a ScreenObservation."""
    description = str(getattr(observation, "description", "") or "").strip()
    activity = str(getattr(observation, "detected_activity", "") or "").strip()
    summary = description or (f"当前活动：{activity}" if activity else "屏幕观察完成")
    return _store.add(
        {
            "source": "screen",
            "kind": "observation",
            "summary": summary,
            "activity": activity,
            "apps": list(getattr(observation, "detected_apps", []) or [])[:4],
            "tier": getattr(observation, "analysis_tier", 0),
        }
    )
