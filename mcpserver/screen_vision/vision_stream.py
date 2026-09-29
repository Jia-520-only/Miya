"""What Miya saw, how she read it, and what she decided - as a stream.

Before this, a tick produced a rich intermediate result (the fused reading she
interpreted, the model that answered, whether it degraded to local) and threw
all of it away, keeping only the final impression summary. Jia asked to see her
working, so the working is now recorded.

Two deliberate privacy rules live here:

* thumbnails are **off by default** and only stored when explicitly enabled, so
  the long-standing "no camera frames are kept" promise holds unless he opts in;
* a stored thumbnail is small, bounded in count and total bytes, kept on this
  machine only, and is never sent to a model.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("screen_vision.stream")

# How many observations to keep in memory for the panel.
MAX_EVENTS = int(os.getenv("MIYA_VISION_STREAM_MAX", "120"))
# Stored thumbnails: bounded count and total size so this can never grow wild.
MAX_THUMBNAILS = int(os.getenv("MIYA_VISION_THUMB_MAX", "80"))
MAX_THUMBNAIL_BYTES = int(os.getenv("MIYA_VISION_THUMB_BYTES", str(12 * 1024 * 1024)))
# A thumbnail is a small JPEG data URL; anything larger is not from this path.
MAX_THUMBNAIL_CHARS = int(os.getenv("MIYA_VISION_THUMB_CHARS", "120000"))


@dataclass
class ObservationEvent:
    """One full round of Miya looking: inputs, reasoning, and decision."""

    id: str
    at: float
    # Step timings, in seconds; useful for spotting a slow step.
    capture_seconds: float = 0.0
    local_seconds: float = 0.0
    interpret_seconds: float = 0.0
    total_seconds: float = 0.0
    # What her senses reported.
    cameras_used: list[int] = field(default_factory=list)
    cameras_failed: list[dict[str, Any]] = field(default_factory=list)
    reading: dict[str, Any] = field(default_factory=dict)
    reading_text: str = ""
    expression_text: str = ""
    rig: dict[str, float] = field(default_factory=dict)
    # A black frame is "the camera failed", which is not the same as "Jia is not
    # there", and only the event can tell the two apart downstream.
    blank_frame: bool = False
    # How she read it.
    interpreted: bool = False
    interpreter: str = ""
    degraded_reason: str = ""
    # What she concluded.
    summary: str = ""
    activity: str = ""
    mood: str = ""
    attention: str = ""
    notable: bool = False
    said: str = ""
    intent_texts: list[str] = field(default_factory=list)
    # Optional picture of that moment, only when thumbnails are enabled.
    thumbnails: list[dict[str, Any]] = field(default_factory=list)
    thumbnail_enabled: bool = False

    def to_dict(self, *, include_thumbnails: bool = True) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "at": self.at,
            "timing": {
                "capture": round(self.capture_seconds, 3),
                "local": round(self.local_seconds, 3),
                "interpret": round(self.interpret_seconds, 3),
                "total": round(self.total_seconds, 3),
            },
            "cameras_used": list(self.cameras_used),
            "cameras_failed": list(self.cameras_failed),
            "reading": dict(self.reading),
            "reading_text": self.reading_text,
            "expression_text": self.expression_text,
            "rig": dict(self.rig),
            "blank_frame": bool(self.blank_frame),
            "interpreted": self.interpreted,
            "interpreter": self.interpreter,
            "degraded_reason": self.degraded_reason,
            "summary": self.summary,
            "activity": self.activity,
            "mood": self.mood,
            "attention": self.attention,
            "notable": self.notable,
            "said": self.said,
            "intent_texts": list(self.intent_texts),
            "thumbnail_enabled": self.thumbnail_enabled,
            "thumbnail_count": len(self.thumbnails),
        }
        if include_thumbnails:
            payload["thumbnails"] = [dict(item) for item in self.thumbnails]
        return payload


class VisionStream:
    """Bounded, thread-safe log of Miya's observation rounds."""

    def __init__(self, *, max_events: int = MAX_EVENTS) -> None:
        self._lock = threading.RLock()
        self._events: deque[ObservationEvent] = deque(maxlen=max(10, int(max_events)))
        self._thumbnails_enabled = False
        self._thumb_bytes = 0
        self._counter = 0

    # -- thumbnails --------------------------------------------------------

    @property
    def thumbnails_enabled(self) -> bool:
        with self._lock:
            return self._thumbnails_enabled

    def set_thumbnails_enabled(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self._thumbnails_enabled = bool(enabled)
            if not enabled:
                # Turning it off must also forget what was stored, otherwise the
                # switch would only stop future frames.
                self._drop_all_thumbnails_locked()
        logger.info("[VisionStream] 缩略图存储已%s", "开启" if enabled else "关闭并清空")
        return self.status()

    def _drop_all_thumbnails_locked(self) -> None:
        for event in self._events:
            event.thumbnails = []
        self._thumb_bytes = 0

    def _accept_thumbnail(self, data_url: str) -> bool:
        """Validate a thumbnail payload; rejects anything suspicious or huge."""
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            return False
        return len(data_url) <= MAX_THUMBNAIL_CHARS

    # -- recording ---------------------------------------------------------

    def record(self, event: ObservationEvent) -> ObservationEvent:
        with self._lock:
            self._counter += 1
            if not event.id:
                event.id = f"obs-{self._counter}"
            event.thumbnail_enabled = self._thumbnails_enabled
            if not self._thumbnails_enabled:
                event.thumbnails = []
            else:
                event.thumbnails = [
                    item for item in event.thumbnails
                    if isinstance(item, dict) and self._accept_thumbnail(str(item.get("data_url") or ""))
                ]
                for item in event.thumbnails:
                    self._thumb_bytes += len(str(item.get("data_url") or ""))
            self._events.append(event)
            self._enforce_limits_locked()
            return event

    def _enforce_limits_locked(self) -> None:
        """Keep the newest thumbnails within both budgets.

        Plain and predictable: count what is held, then walk oldest-first and
        forget pictures until the count and byte budgets are both satisfied.
        The events themselves stay; only their pictures are dropped.
        """
        self._thumb_bytes = sum(
            len(str(item.get("data_url") or ""))
            for event in self._events for item in event.thumbnails
        )
        held = sum(1 for event in self._events if event.thumbnails)
        if held <= MAX_THUMBNAILS and self._thumb_bytes <= MAX_THUMBNAIL_BYTES:
            return
        for event in self._events:  # oldest first
            if held <= MAX_THUMBNAILS and self._thumb_bytes <= MAX_THUMBNAIL_BYTES:
                break
            if not event.thumbnails:
                continue
            self._thumb_bytes -= sum(len(str(item.get("data_url") or "")) for item in event.thumbnails)
            event.thumbnails = []
            held -= 1
        self._thumb_bytes = max(0, self._thumb_bytes)

    # -- reading -----------------------------------------------------------

    def recent(self, *, limit: int = 20, include_thumbnails: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)[-max(1, int(limit)):]
            return [event.to_dict(include_thumbnails=include_thumbnails) for event in events]

    def latest(self, *, include_thumbnails: bool = False) -> dict[str, Any] | None:
        items = self.recent(limit=1, include_thumbnails=include_thumbnails)
        return items[0] if items else None

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            for event in self._events:
                if event.id == event_id:
                    return event.to_dict(include_thumbnails=True)
        return None

    def clear(self) -> int:
        with self._lock:
            count = len(self._events)
            self._events.clear()
            self._thumb_bytes = 0
            return count

    def status(self) -> dict[str, Any]:
        with self._lock:
            with_thumbs = sum(1 for event in self._events if event.thumbnails)
            return {
                "count": len(self._events),
                "capacity": self._events.maxlen,
                "thumbnails_enabled": self._thumbnails_enabled,
                "events_with_thumbnails": with_thumbs,
                "thumbnail_bytes": self._thumb_bytes,
                "thumbnail_max_bytes": MAX_THUMBNAIL_BYTES,
                "thumbnail_max_events": MAX_THUMBNAILS,
            }


_stream = VisionStream()


def get_vision_stream() -> VisionStream:
    return _stream


def motion_signature(reading: dict[str, Any]) -> str:
    """A cheap signature of "did anything change" for adaptive pacing.

    Derived values only: whether a face is present, what activity was read,
    whether the frame was blank. Deliberately coarse so ordinary micro-movement
    does not keep Miya on her fastest cadence.
    """
    action = (reading.get("action") or {}) if isinstance(reading.get("action"), dict) else {}
    return "|".join([
        str(bool(reading.get("faces"))),
        str(action.get("kind") or ""),
        str(bool(reading.get("blank_frame"))),
    ])
