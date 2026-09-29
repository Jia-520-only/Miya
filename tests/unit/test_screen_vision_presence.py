"""Presence state machine tests: time-injected, no camera required."""

from __future__ import annotations

import json

from mcpserver.screen_vision import presence
from mcpserver.screen_vision.service import ScreenVisionService


def _fresh_tracker() -> presence.PresenceTracker:
    return presence.PresenceTracker()


def test_absent_signals_report_unknown_not_left():
    """Never claim someone left before any evidence has arrived."""
    tracker = _fresh_tracker()
    snapshot = tracker.evaluate(at=1000.0)
    assert snapshot.state == presence.UNKNOWN
    assert snapshot.at_computer is False


def test_close_face_is_judged_at_the_computer():
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=1, face_ratio=0.06, face_score=0.93, centered=True,
                    posture="sitting", action_kind="typing", pose_usable=True)
    snapshot = tracker.evaluate(at=1000.5)
    assert snapshot.state == presence.AT_DESK
    assert snapshot.at_computer is True
    assert snapshot.in_room is True
    assert snapshot.confidence > 0.6
    assert any("人脸" in reason for reason in snapshot.reasons)


def test_distant_face_is_in_room_but_not_at_the_computer():
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=1, face_ratio=0.004, face_score=0.7, centered=False)
    snapshot = tracker.evaluate(at=1000.4)
    assert snapshot.state == presence.PRESENT
    assert snapshot.at_computer is False
    assert snapshot.in_room is True


def test_short_gap_is_away_and_long_gap_becomes_left():
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=1, face_ratio=0.05, face_score=0.9, centered=True, posture="sitting")
    # Face gone for longer than the grace window but well inside the away window.
    away = tracker.evaluate(at=1000.0 + presence.PRESENCE_GRACE_SECONDS + 5)
    assert away.state == presence.AWAY
    assert away.transition == "away"
    assert away.at_computer is False

    left = tracker.evaluate(at=1000.0 + presence.AWAY_AFTER_SECONDS + 30)
    assert left.state == presence.LEFT
    assert left.transition == "left"
    assert any("没有检测到人脸" in reason for reason in left.reasons)


def test_returning_is_reported_as_a_single_transition_then_settles():
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=1, face_ratio=0.05, face_score=0.9, centered=True, posture="sitting")
    tracker.evaluate(at=1000.0 + presence.AWAY_AFTER_SECONDS + 30)
    back = tracker.observe(at=1000.0 + presence.AWAY_AFTER_SECONDS + 40, faces=1, face_ratio=0.05,
                           face_score=0.9, centered=True, posture="sitting")
    assert back.transition == "returned"
    assert back.label == presence.LABELS[presence.RETURNED]
    # The next evaluation must not keep announcing "just came back".
    settled = tracker.evaluate(at=1000.0 + presence.AWAY_AFTER_SECONDS + 41)
    assert settled.transition == ""
    assert settled.state == presence.AT_DESK


def test_blank_camera_reports_unknown_instead_of_left():
    """A dead or virtual camera must not be read as 'Jia walked away'."""
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=1, face_ratio=0.05, face_score=0.9, centered=True)
    snapshot = tracker.observe(at=1000.0 + presence.AWAY_AFTER_SECONDS + 30, luminance=0.0)
    assert snapshot.state == presence.UNKNOWN
    assert "全黑" in "".join(snapshot.reasons)
    assert snapshot.at_computer is False


def test_body_without_face_still_counts_as_in_the_room():
    tracker = _fresh_tracker()
    tracker.observe(at=1000.0, faces=0, pose_usable=True, posture="standing", motion=2.0)
    snapshot = tracker.evaluate(at=1000.5)
    assert snapshot.state == presence.PRESENT
    assert snapshot.in_room is True
    assert snapshot.at_computer is False


def test_presence_from_local_result_reads_nested_signals():
    tracker = _fresh_tracker()
    result = {
        "status": "success",
        "faces": 1,
        "luminance": 91.2,
        "observations": [{
            "face_signals": {"count": 1, "largest_ratio": 0.05, "best_score": 0.9, "centered": True},
            "pose_quality": {"usable": True},
            "action": {"kind": "typing", "label": "敲键盘或操作鼠标", "confidence": 0.7},
        }],
    }
    snapshot = tracker.observe(
        faces=int(result["observations"][0]["face_signals"]["count"]),
        face_ratio=result["observations"][0]["face_signals"]["largest_ratio"],
        face_score=result["observations"][0]["face_signals"]["best_score"],
        centered=True,
        posture="typing",
        action_kind="typing",
        pose_usable=True,
        luminance=result["luminance"],
    )
    assert snapshot.state == presence.AT_DESK
    assert snapshot.to_dict()["at_computer"] is True
    assert json.dumps(snapshot.to_dict(), ensure_ascii=False)


def test_camera_presence_tool_reports_state_without_images():
    service = ScreenVisionService()
    tracker = presence.get_presence_tracker()
    tracker.reset()
    tracker.observe(faces=1, face_ratio=0.06, face_score=0.91, centered=True, posture="sitting")

    raw = service._camera_event({"event": {"kind": "motion", "summary": "检测到明显动作"}, "motion_score": 2.0})
    payload = json.loads(raw)
    assert payload["status"] == "success"
    assert payload["presence"]["at_computer"] is True
    assert "image" not in raw

    reported = json.loads(service._camera_presence({}))
    assert reported["status"] == "success"
    assert reported["presence"]["at_computer"] is True
    assert reported["message"]


def test_presence_status_is_exposed_on_camera_capabilities():
    from mcpserver.screen_vision.local_camera import discover_local_camera_capabilities

    capabilities = discover_local_camera_capabilities()
    assert "face_backend" in capabilities
    assert "blank_frame_mean" in capabilities
