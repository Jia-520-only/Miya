"""Turn instantaneous pose readings into "what Jia has been doing".

A single frame can only ever say "a skeleton is sitting at this angle".  Jia's
complaint was precisely that: reporting ``confidence 0.00`` and
``2/17 landmarks`` is a machine talking to itself, not a companion who noticed
something.

This module keeps a short, bounded timeline of local activity readings and turns
it into two things a person would actually say:

* a *current activity* that has persisted long enough to be worth mentioning,
  together with how long it has lasted;
* a *change* when that activity really switches, so Miya can react to "you just
  started typing" rather than re-describing the same posture forever.

Only derived labels and durations are stored - never frames, never keypoints.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# An activity must survive this long before it is treated as the current one.
ACTIVITY_MIN_SECONDS = float(os.getenv("MIYA_ACTIVITY_MIN_SECONDS", "6"))
# How much history to keep for duration and transition calculation.
ACTIVITY_WINDOW_SECONDS = float(os.getenv("MIYA_ACTIVITY_WINDOW_SECONDS", "600"))
# A change is only news while the moment it describes is still current.  Two
# readers share this timeline - the camera bridge remembers what Jia did, and the
# proactive poll decides whether to say something about it - so a change nobody
# acted on has to expire on its own instead of being re-offered as "just now"
# for the rest of the evening.
ACTIVITY_CHANGE_MAX_AGE_SECONDS = float(os.getenv("MIYA_ACTIVITY_CHANGE_MAX_AGE", "300"))

# Readings that describe a momentary gesture rather than a sustained activity.
MOMENTARY_KINDS = {"wave", "clap", "sit_down", "stand_up", "nod", "stretch", "raised_hand"}
# Readings that carry no conclusion, so they must not reset a real activity.
INCONCLUSIVE_KINDS = {"low_confidence", "unknown", ""}

# Phrasing for a sustained activity, chosen to read naturally after "像是在".
SUSTAINED_PHRASES: dict[str, str] = {
    "typing": "专心敲键盘",
    "phone": "在看手机",
    "drink": "在喝水或吃东西",
    "lean_back": "靠在椅背上歇着",
    "still": "安静地坐着",
    "sitting": "坐在电脑前",
    "standing": "站着",
    "walk": "走来走去",
    "body_motion": "在动身体",
    "hands_resting": "手搭在桌上",
}
# The same activities, phrased for a single moment rather than a duration.
MOMENT_PHRASES: dict[str, str] = {
    "typing": "在敲键盘",
    "phone": "在看手机",
    "drink": "在喝水或吃东西",
    "lean_back": "往后靠了靠",
    "still": "安静地待着",
    "sitting": "坐着",
    "standing": "站着",
    "walk": "在走动",
    "body_motion": "换了个姿势",
    "hands_resting": "把手搭在桌上",
    "wave": "在跟你挥手",
    "clap": "在鼓掌",
    "stretch": "在伸懒腰",
    "sit_down": "刚坐下",
    "stand_up": "刚站起来",
    "nod": "点了下头",
    "raised_hand": "举起了手",
}

# Activities worth telling Jia about when they begin.
NOTABLE_KINDS = {"typing", "phone", "drink", "stretch", "walk", "sit_down", "stand_up", "lean_back"}


@dataclass
class Reading:
    at: float
    kind: str
    label: str
    confidence: float = 0.0


@dataclass
class ActivitySnapshot:
    kind: str = ""
    phrase: str = ""
    duration: float = 0.0
    confidence: float = 0.0
    reading_count: int = 0
    changed: bool = False
    previous_phrase: str = ""
    recent: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "phrase": self.phrase,
            "duration": round(self.duration, 1),
            "confidence": round(self.confidence, 3),
            "reading_count": self.reading_count,
            "changed": self.changed,
            "previous_phrase": self.previous_phrase,
            "recent": list(self.recent),
        }

    def describe(self) -> str:
        if not self.phrase:
            return "还看不出佳在做什么。"
        if self.duration >= 60:
            return f"佳像是在{self.phrase}，已经大约 {int(self.duration // 60)} 分钟了。"
        if self.duration >= ACTIVITY_MIN_SECONDS:
            return f"佳像是在{self.phrase}。"
        return f"佳{self.phrase}。"


class ActivityTracker:
    """Bounded timeline of local activity readings."""

    def __init__(self, *, max_readings: int = 400) -> None:
        self._lock = threading.RLock()
        self._readings: list[Reading] = []
        self._max = max(20, int(max_readings))
        self._kind = ""
        self._since = 0.0
        self._last_confidence = 0.0
        # A change happens on exactly one reading, but the consumer (proactive
        # chat) polls on its own schedule. Remembering the change until it is
        # collected is what stops "he just sat down" from being lost.
        self._pending_change = ""
        self._pending_previous = ""
        self._pending_at = 0.0

    def observe(self, kind: str, label: str = "", *, confidence: float = 0.0, at: float | None = None) -> ActivitySnapshot:
        timestamp = time.time() if at is None else float(at)
        clean = str(kind or "")
        with self._lock:
            self._readings.append(Reading(at=timestamp, kind=clean, label=str(label or ""), confidence=float(confidence)))
            if len(self._readings) > self._max:
                del self._readings[: len(self._readings) - self._max]
            cutoff = timestamp - ACTIVITY_WINDOW_SECONDS
            self._readings = [item for item in self._readings if item.at >= cutoff]
            # A reading is the tracker's clock tick, so this is where an
            # uncollected change stops being news.
            self._expire_change_locked(timestamp)

            changed = False
            previous = ""
            if clean in INCONCLUSIVE_KINDS:
                # No conclusion: keep whatever activity was already established.
                pass
            elif clean in MOMENTARY_KINDS:
                # A gesture is an event, not a state. It is reported once and the
                # established activity continues underneath it.
                changed = True
                previous = SUSTAINED_PHRASES.get(self._kind, self._kind)
                self._kind = clean
                self._since = timestamp
                self._last_confidence = float(confidence)
                self._mark_change(clean, previous, timestamp)
            elif clean != self._kind:
                # Only accept a new sustained activity once it has been seen for
                # long enough to be more than a single noisy reading.
                first_seen = self._first_seen(clean, timestamp)
                if (timestamp - first_seen) >= ACTIVITY_MIN_SECONDS or not self._kind:
                    changed = True
                    previous = SUSTAINED_PHRASES.get(self._kind, self._kind)
                    self._kind = clean
                    self._since = first_seen if (timestamp - first_seen) >= ACTIVITY_MIN_SECONDS else timestamp
                    self._mark_change(clean, previous, timestamp)
                self._last_confidence = float(confidence)
            else:
                self._last_confidence = float(confidence)

            return self._snapshot_locked(timestamp, changed=changed, previous=previous)

    def _mark_change(self, kind: str, previous: str, at: float) -> None:
        self._pending_change = kind
        self._pending_previous = previous
        self._pending_at = at

    def _first_seen(self, kind: str, now: float) -> float:
        """Timestamp where the current run of ``kind`` began, walking back."""
        first = now
        for reading in reversed(self._readings):
            if reading.kind != kind:
                break
            first = reading.at
        return first

    def _snapshot_locked(self, now: float, *, changed: bool, previous: str) -> ActivitySnapshot:
        duration = 0.0
        if self._kind and self._since:
            duration = max(0.0, now - self._since)
        phrase = ""
        if self._kind:
            if self._kind in MOMENTARY_KINDS:
                phrase = MOMENT_PHRASES.get(self._kind, self._kind)
            elif duration >= ACTIVITY_MIN_SECONDS:
                phrase = SUSTAINED_PHRASES.get(self._kind, MOMENT_PHRASES.get(self._kind, self._kind))
            else:
                phrase = MOMENT_PHRASES.get(self._kind, self._kind)
        recent: list[str] = []
        for reading in reversed(self._readings[-40:]):
            if reading.kind in INCONCLUSIVE_KINDS:
                continue
            text = MOMENT_PHRASES.get(reading.kind, reading.kind)
            if text and (not recent or recent[-1] != text):
                recent.append(text)
            if len(recent) >= 5:
                break
        return ActivitySnapshot(
            kind=self._kind,
            phrase=phrase,
            duration=duration,
            confidence=self._last_confidence,
            reading_count=len(self._readings),
            changed=changed,
            previous_phrase=previous,
            recent=recent,
        )

    def snapshot(self, *, at: float | None = None) -> ActivitySnapshot:
        timestamp = time.time() if at is None else float(at)
        with self._lock:
            return self._snapshot_locked(timestamp, changed=False, previous="")

    def has_pending_change(self) -> bool:
        with self._lock:
            return bool(self._pending_change)

    def _expire_change_locked(self, now: float) -> None:
        """Drop a change nobody acted on before it stops being news.

        Caller holds the lock.  Evaluated against the tracker's own injected
        clock, on every new reading, so the module keeps a single time domain -
        the rest of it is testable without sleeping precisely because of that.
        With observations arriving every 30 seconds a change is offered for about
        ``ACTIVITY_CHANGE_MAX_AGE_SECONDS`` and then quietly expires, instead of
        being re-offered as "just now" for the rest of the evening.
        """
        if not self._pending_change or ACTIVITY_CHANGE_MAX_AGE_SECONDS <= 0:
            return
        if (now - self._pending_at) > ACTIVITY_CHANGE_MAX_AGE_SECONDS:
            self._pending_change = ""
            self._pending_previous = ""
            self._pending_at = 0.0

    def _build_change_locked(self, kind: str, previous: str, at: float) -> ActivitySnapshot:
        """Render one change as a snapshot without touching the tracker state."""
        snapshot = self._snapshot_locked(at, changed=True, previous=previous)
        snapshot.kind = kind
        snapshot.phrase = MOMENT_PHRASES.get(kind, kind)
        return snapshot

    def peek_change(self) -> ActivitySnapshot | None:
        """Read the pending change **without** consuming it, or ``None``.

        Reading used to be destructive, and because two readers share this
        timeline the one that happened to poll first (the camera bridge, every
        20s) silently stole every change from the one that actually asks the
        model whether to speak (the proactive poll, every 45s).  Reading is
        therefore non-destructive; only the reader that acted consumes.
        """
        with self._lock:
            kind = self._pending_change
            if not kind:
                return None
            return self._build_change_locked(kind, self._pending_previous, self._pending_at)

    def consume_change(self) -> ActivitySnapshot | None:
        """Collect the most recent change exactly once, or ``None``.

        A momentary gesture is not a state, so after reporting it the tracker
        falls back to the activity that was running underneath, which is what a
        companion would describe if asked again a moment later.
        """
        with self._lock:
            kind = self._pending_change
            if not kind:
                return None
            previous = self._pending_previous
            at = self._pending_at
            self._pending_change = ""
            self._pending_previous = ""
            self._pending_at = 0.0
            if kind in MOMENTARY_KINDS:
                # Resume the sustained activity that the gesture interrupted.
                resumed = previous if previous in SUSTAINED_PHRASES.values() else ""
                if resumed:
                    for candidate, phrase in SUSTAINED_PHRASES.items():
                        if phrase == previous:
                            self._kind = candidate
                            break
                else:
                    self._kind = ""
                self._since = at
            snapshot = self._snapshot_locked(at, changed=True, previous=previous)
            snapshot.kind = kind
            snapshot.phrase = MOMENT_PHRASES.get(kind, kind)
            return snapshot

    def pending_change(self) -> tuple[str, str]:
        """Read the pending change without consuming it: ``(kind, previous)``."""
        with self._lock:
            return self._pending_change, self._pending_previous

    def reset(self) -> None:
        with self._lock:
            self._readings.clear()
            self._kind = ""
            self._since = 0.0
            self._last_confidence = 0.0
            self._pending_change = ""
            self._pending_previous = ""
            self._pending_at = 0.0


_tracker = ActivityTracker()


def get_activity_tracker() -> ActivityTracker:
    return _tracker


def observe_action(action: dict[str, Any] | None, *, at: float | None = None) -> ActivitySnapshot:
    """Feed one classifier result (``{kind, label, confidence}``) into the tracker."""
    action = action or {}
    return _tracker.observe(
        str(action.get("kind") or ""),
        str(action.get("label") or ""),
        confidence=float(action.get("confidence") or 0.0),
        at=at,
    )


def activity_card() -> str:
    """Image-free prompt card describing what Jia has been doing."""
    snapshot = _tracker.snapshot()
    if not snapshot.kind:
        return ""
    lines = [f"[弥娅观察到的活动] {snapshot.describe()}"]
    if snapshot.recent:
        lines.append("最近的迹象：" + " → ".join(reversed(snapshot.recent[:4])))
    if snapshot.changed and snapshot.previous_phrase:
        lines.append(f"刚刚从「{snapshot.previous_phrase}」变成「{snapshot.phrase}」")
    return "\n".join(lines)


def activity_change_message(snapshot: ActivitySnapshot) -> str:
    """One short natural line Miya could say when an activity begins."""
    if not snapshot or not snapshot.kind:
        return ""
    if snapshot.kind in INCONCLUSIVE_KINDS:
        return ""
    return MOMENT_PHRASES.get(snapshot.kind, snapshot.kind)


def take_activity_change() -> ActivitySnapshot | None:
    """Collect a pending activity change exactly once, from the shared tracker."""
    return _tracker.consume_change()


def peek_activity_change() -> ActivitySnapshot | None:
    """Look at a pending activity change without taking it away from other readers."""
    return _tracker.peek_change()


def activity_change_card() -> str:
    """Prompt fragment describing a change that has not been mentioned yet."""
    kind, previous = _tracker.pending_change()
    if not kind:
        return ""
    phrase = MOMENT_PHRASES.get(kind, kind)
    if previous:
        return f"[弥娅注意到的变化] 佳刚刚从「{previous}」变成「{phrase}」"
    return f"[弥娅注意到的变化] 佳{phrase}"
