"""Local "is Jia at the computer?" state machine for Miya Vision.

The companion camera already produces derived signals every few hundred
milliseconds: a browser frame delta, an optional local skeleton, and optional
local face detections.  Raw camera frames never reach this module.

This module turns that stream into a small, explainable presence model so Miya
can tell *being at the computer* apart from *being in the room* and from
*having walked away*.  Everything is time-injected, so behaviour is testable
without sleeping and without a camera.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# --- tunables -------------------------------------------------------------

# How long the screen may see no face at all before we stop claiming presence.
PRESENCE_GRACE_SECONDS = float(os.getenv("MIYA_PRESENCE_GRACE_SECONDS", "12"))
# Leaving needs a longer, more confident gap than "looked away for a moment".
AWAY_AFTER_SECONDS = float(os.getenv("MIYA_PRESENCE_AWAY_SECONDS", "45"))
# A face this large (area in normalized frame units) is close enough to be at
# the desk rather than merely somewhere in the room.
AT_DESK_FACE_RATIO = float(os.getenv("MIYA_PRESENCE_DESK_FACE_RATIO", "0.02"))
# Motion below this counts as stillness, not activity.
ACTIVE_MOTION_THRESHOLD = float(os.getenv("MIYA_PRESENCE_MOTION", "0.65"))
# A frame this dark means the camera is unusable, not that Jia left.
UNUSABLE_LUMINANCE = float(os.getenv("MIYA_PRESENCE_DARK_LUMINANCE", "4.0"))

PRESENT = "present"
AT_DESK = "at_desk"
AWAY = "away"
LEFT = "left"
RETURNED = "returned"
UNKNOWN = "unknown"

LABELS = {
    PRESENT: "在摄像头前",
    AT_DESK: "在电脑前",
    AWAY: "可能离开了座位",
    LEFT: "离开了",
    RETURNED: "刚回来",
    UNKNOWN: "看不清",
}


@dataclass
class _Observation:
    at: float
    faces: int = 0
    face_ratio: float = 0.0
    face_score: float = 0.0
    centered: bool = False
    posture: str = ""
    action_kind: str = ""
    pose_usable: bool = False
    motion: float = 0.0
    luminance: float | None = None


@dataclass
class PresenceSnapshot:
    """One explainable answer to "is Jia there right now?"."""

    state: str = UNKNOWN
    label: str = LABELS[UNKNOWN]
    confidence: float = 0.0
    at_computer: bool = False
    in_room: bool = False
    last_face_seconds: float | None = None
    last_motion_seconds: float | None = None
    transition: str = ""
    reasons: list[str] = field(default_factory=list)
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "at_computer": self.at_computer,
            "in_room": self.in_room,
            "last_face_seconds": None if self.last_face_seconds is None else round(self.last_face_seconds, 1),
            "last_motion_seconds": None if self.last_motion_seconds is None else round(self.last_motion_seconds, 1),
            "transition": self.transition,
            "reasons": list(self.reasons),
            "updated_at": round(self.updated_at, 3),
        }

    def describe(self) -> str:
        suffix = f"（{self.transition}）" if self.transition else ""
        return f"{self.label}{suffix}"


class PresenceTracker:
    """Bounded presence model over derived camera observations."""

    def __init__(self, *, max_samples: int = 240) -> None:
        self._lock = threading.RLock()
        self._samples: list[_Observation] = []
        self._max_samples = max(20, int(max_samples))
        self._last_face_at: float | None = None
        self._last_motion_at: float | None = None
        self._left_at: float | None = None
        self._state = UNKNOWN
        self._snapshot = PresenceSnapshot()
        # The last transition the state machine actually produced, kept apart from
        # the snapshot. A transition exists for exactly one evaluation - the next
        # one overwrites `_snapshot` - so anything polling slower than the caller
        # that happened to trigger it (Miya's 20s bridge and 45s proactive poll
        # versus a 2.5s UI poll) simply never saw the event. This is that event,
        # with the timestamp it belongs to, until a newer one replaces it.
        self._last_transition: tuple[str, float] = ("", 0.0)

    # -- ingest ------------------------------------------------------------

    def observe(
        self,
        *,
        at: float | None = None,
        faces: int = 0,
        face_ratio: float = 0.0,
        face_score: float = 0.0,
        centered: bool = False,
        posture: str = "",
        action_kind: str = "",
        pose_usable: bool = False,
        motion: float = 0.0,
        luminance: float | None = None,
    ) -> PresenceSnapshot:
        timestamp = time.time() if at is None else float(at)
        sample = _Observation(
            at=timestamp,
            faces=max(0, int(faces)),
            face_ratio=max(0.0, float(face_ratio)),
            face_score=max(0.0, float(face_score)),
            centered=bool(centered),
            posture=str(posture or ""),
            action_kind=str(action_kind or ""),
            pose_usable=bool(pose_usable),
            motion=max(0.0, float(motion)),
            luminance=None if luminance is None else float(luminance),
        )
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > self._max_samples:
                del self._samples[: len(self._samples) - self._max_samples]
            if sample.faces > 0:
                self._last_face_at = timestamp
            if sample.motion >= ACTIVE_MOTION_THRESHOLD:
                self._last_motion_at = timestamp
        return self.evaluate(at=timestamp)

    def note_frame(self, *, at: float | None = None, motion: float = 0.0, luminance: float | None = None) -> PresenceSnapshot:
        """Ingest a frame that carried no local model output."""
        return self.observe(at=at, motion=motion, luminance=luminance)

    # -- evaluate ----------------------------------------------------------

    def evaluate(self, *, at: float | None = None) -> PresenceSnapshot:
        timestamp = time.time() if at is None else float(at)
        with self._lock:
            samples = list(self._samples)
            last_face_at = self._last_face_at
            last_motion_at = self._last_motion_at
            previous_state = self._state
            left_at = self._left_at

        snapshot = PresenceSnapshot(updated_at=timestamp)
        if not samples:
            snapshot.reasons.append("还没有收到任何摄像头采样")
            self._snapshot = snapshot
            return snapshot

        # A dark or virtual camera tells us nothing; never claim someone left
        # because the device stopped delivering pixels.
        recent = [item for item in samples if timestamp - item.at <= max(PRESENCE_GRACE_SECONDS, 6.0)]
        if recent:
            luminance = [item.luminance for item in recent if item.luminance is not None]
            if luminance and max(luminance) < UNUSABLE_LUMINANCE:
                snapshot.state = UNKNOWN
                snapshot.label = LABELS[UNKNOWN]
                snapshot.reasons.append("摄像头画面全黑，无法判断你在不在")
                self._state = UNKNOWN
                self._snapshot = snapshot
                return snapshot

        face_age = None if last_face_at is None else max(0.0, timestamp - last_face_at)
        motion_age = None if last_motion_at is None else max(0.0, timestamp - last_motion_at)
        snapshot.last_face_seconds = face_age
        snapshot.last_motion_seconds = motion_age

        best_face = max((item.face_ratio for item in recent), default=0.0)
        best_score = max((item.face_score for item in recent), default=0.0)
        centered = any(item.centered for item in recent)
        postures = {item.posture for item in recent if item.posture}
        actions = {item.action_kind for item in recent if item.action_kind}
        motion_recent = any(item.motion >= ACTIVE_MOTION_THRESHOLD for item in recent)

        face_visible = face_age is not None and face_age <= PRESENCE_GRACE_SECONDS
        body_visible = any(item.pose_usable for item in recent)
        movement = motion_recent or (motion_age is not None and motion_age <= PRESENCE_GRACE_SECONDS)

        if face_visible:
            reasons = [f"{face_age:.0f} 秒内检测到人脸" if face_age >= 1 else "此刻检测到人脸"]
            if best_face >= AT_DESK_FACE_RATIO:
                reasons.append("人脸占画面比例达到近距阈值")
            if centered:
                reasons.append("人脸位于画面中央")
            if "sitting" in postures:
                reasons.append("姿态为坐姿")
            if actions & {"typing", "hand_to_face"}:
                reasons.append("双手在键盘或面部高度活动")
            snapshot.reasons = reasons
            # Sitting / typing / a close, centred face means "at the computer";
            # a visible-but-distant face only means "in the room".
            at_desk = (
                best_face >= AT_DESK_FACE_RATIO
                or "sitting" in postures
                or bool(actions & {"typing", "hand_to_face"})
            )
            snapshot.state = AT_DESK if at_desk else PRESENT
            snapshot.label = LABELS[snapshot.state]
            confidence = 0.60
            if best_score >= 0.8:
                confidence += 0.20
            if centered:
                confidence += 0.10
            if at_desk:
                confidence += 0.07
            snapshot.confidence = min(0.97, confidence)
            snapshot.at_computer = at_desk
            snapshot.in_room = True
            self._left_at = None
        elif body_visible:
            snapshot.state = PRESENT
            snapshot.label = LABELS[PRESENT]
            snapshot.confidence = 0.5
            snapshot.reasons = ["检测到可信骨架，但没有人脸"]
            snapshot.in_room = True
            self._left_at = None
        elif face_age is not None and face_age > AWAY_AFTER_SECONDS:
            departed = left_at is None
            if departed:
                self._left_at = timestamp
            snapshot.state = LEFT
            snapshot.label = LABELS[LEFT]
            snapshot.confidence = min(0.95, 0.62 + min(face_age - AWAY_AFTER_SECONDS, 120.0) / 400.0)
            snapshot.reasons = [f"{face_age / 60:.1f} 分钟没有检测到人脸"]
            if body_visible or movement:
                snapshot.reasons.append("但仍有画面活动，可能只是背对摄像头")
                snapshot.confidence = max(0.5, snapshot.confidence - 0.2)
            snapshot.at_computer = False
            snapshot.in_room = body_visible
        elif face_age is not None and face_age > PRESENCE_GRACE_SECONDS:
            snapshot.state = AWAY
            snapshot.label = LABELS[AWAY]
            snapshot.confidence = 0.55
            snapshot.reasons = [f"{face_age:.0f} 秒没有检测到人脸，但还没到确认离开的时长"]
            snapshot.at_computer = False
            snapshot.in_room = body_visible or movement
        else:
            snapshot.state = UNKNOWN
            snapshot.label = LABELS[UNKNOWN]
            snapshot.confidence = 0.3
            snapshot.reasons = ["没有可靠的人脸或骨架信号"]

        # Coming back is worth one explicit transition rather than a silent flip.
        if previous_state in {AWAY, LEFT} and snapshot.state in {PRESENT, AT_DESK}:
            snapshot.transition = "returned"
            snapshot.label = LABELS[RETURNED]
        elif previous_state in {PRESENT, AT_DESK, UNKNOWN, AWAY} and snapshot.state == LEFT:
            snapshot.transition = "left"
        elif previous_state in {PRESENT, AT_DESK} and snapshot.state == AWAY:
            snapshot.transition = "away"

        self._state = snapshot.state
        self._snapshot = snapshot
        if snapshot.transition:
            with self._lock:
                self._last_transition = (snapshot.transition, timestamp)
        return snapshot

    def last_transition(self) -> tuple[str, float]:
        """The most recent transition and the moment it happened.

        Reading this does not consume it and does not advance the state machine,
        which is the point: several consumers with different rhythms can each see
        the same arrival exactly once, keyed on the timestamp, instead of racing
        for a value that only lives inside the newest snapshot.
        """
        with self._lock:
            return self._last_transition

    def snapshot(self) -> PresenceSnapshot:
        return self._snapshot

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._last_face_at = None
            self._last_motion_at = None
            self._left_at = None
            self._state = UNKNOWN
            self._snapshot = PresenceSnapshot()
            self._last_transition = ("", 0.0)


_tracker = PresenceTracker()


def get_presence_tracker() -> PresenceTracker:
    return _tracker


def observe_presence(**kwargs: Any) -> PresenceSnapshot:
    return _tracker.observe(**kwargs)


def presence_from_local_result(result: dict[str, Any], *, motion: float = 0.0) -> PresenceSnapshot:
    """Feed one ``analyze_local_frame`` result into the shared tracker."""
    observations = result.get("observations") if isinstance(result, dict) else None
    first = observations[0] if isinstance(observations, list) and observations else {}
    if not isinstance(first, dict):
        first = {}
    signals = first.get("face_signals") if isinstance(first.get("face_signals"), dict) else {}
    action = first.get("action") if isinstance(first.get("action"), dict) else {}
    quality = first.get("pose_quality") if isinstance(first.get("pose_quality"), dict) else {}
    return _tracker.observe(
        faces=int(signals.get("count") or result.get("faces") or 0),
        face_ratio=float(signals.get("largest_ratio") or 0.0),
        face_score=float(signals.get("best_score") or 0.0),
        centered=bool(signals.get("centered")),
        posture=str(action.get("kind") or ""),
        action_kind=str(action.get("kind") or ""),
        pose_usable=bool(quality.get("usable")),
        motion=motion,
        luminance=result.get("luminance"),
    )


def presence_card() -> str:
    """Compact prompt card, image-free, for the conversation layer."""
    snapshot = _tracker.snapshot()
    if not snapshot.updated_at:
        return ""
    return f"[弥娅的在场判断] {snapshot.describe()}；依据：{'、'.join(snapshot.reasons) or '暂无'}"
