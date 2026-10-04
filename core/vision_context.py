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
        safe.pop("image_data", None)
        safe.pop("image_url", None)
        with self._lock:
            previous = self._events[-1] if self._events else None
            if (
                previous
                and previous.get("source") == safe.get("source")
                and previous.get("summary") == safe.get("summary")
                and 0 <= safe["timestamp"] - float(previous.get("timestamp", 0)) < 2.0
            ):
                return previous
            self._events.append(safe)
        return safe

    def recent(self, *, source: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if source:
            events = [event for event in events if event.get("source") == source]
        return events[-max(1, int(limit)) :]

    def latest(self, *, source: str | None = None) -> dict[str, Any] | None:
        events = self.recent(source=source, limit=1)
        return events[0] if events else None

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
    event = _store.add(
        {
            "source": "camera",
            "kind": "proactive_observation" if proactive else "observation",
            "summary": summary,
            "query": str(query or "")[:300],
            "mode": str(mode or "snapshot"),
            "local_only": local_only,
            "status": result.get("status"),
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
            "camera_source_ids": [str(item)[:160] for item in (camera_source_ids or []) if str(item).strip()],
            "faces": faces,
        }
    )


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
