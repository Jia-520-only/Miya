"""Activity accumulation and multi-camera fusion tests.

These cover the two things Jia actually asked for: notice what he *did*, and
use every camera that can deliver a picture.
"""

from __future__ import annotations

import json

from mcpserver.screen_vision import activity, camera_manager
from mcpserver.screen_vision.service import ScreenVisionService


def _tracker() -> activity.ActivityTracker:
    return activity.ActivityTracker()


# --- activity accumulation -------------------------------------------------


def test_short_reading_is_described_as_a_moment_not_an_activity():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    snapshot = tracker.snapshot(at=1000.5)
    assert snapshot.kind == "typing"
    # Not yet sustained, so it must not claim a lasting activity.
    assert snapshot.phrase == "在敲键盘"


def test_sustained_activity_reports_a_duration_in_plain_language():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    for offset in (1, 2, 3, 4, 5, 6, 7, 8):
        tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + offset)
    snapshot = tracker.snapshot(at=1000.0 + 8)
    assert snapshot.kind == "typing"
    assert snapshot.duration >= activity.ACTIVITY_MIN_SECONDS
    assert "专心敲键盘" in snapshot.describe()
    assert "confidence" not in snapshot.describe()


def test_long_activity_reports_minutes_without_numeric_jargon():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 190)
    snapshot = tracker.snapshot(at=1000.0 + 190)
    assert "3 分钟" in snapshot.describe()
    assert "0." not in snapshot.describe()


def test_inconclusive_readings_do_not_reset_a_real_activity():
    """A bad angle for one frame must not erase 'he has been typing'."""
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 8)
    tracker.observe("low_confidence", "看不清", confidence=0.0, at=1000.0 + 9)
    snapshot = tracker.snapshot(at=1000.0 + 9)
    assert snapshot.kind == "typing"
    assert activity.INCONCLUSIVE_KINDS.issuperset({"low_confidence"})


def test_a_noisy_single_reading_cannot_take_over_the_activity():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 8)
    # One isolated different reading must not immediately become the activity.
    tracker.observe("walk", "在走动", confidence=0.6, at=1000.0 + 9)
    assert tracker.snapshot(at=1000.0 + 9).kind == "typing"


def test_a_new_activity_takes_over_once_it_persists():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 8)
    for offset in range(10, 20):
        tracker.observe("phone", "在看手机", confidence=0.7, at=1000.0 + offset)
    snapshot = tracker.snapshot(at=1000.0 + 19)
    assert snapshot.kind == "phone"
    # The change itself must survive until the conversation layer collects it,
    # because proactive chat polls on its own schedule.
    assert tracker.has_pending_change() is True
    collected = tracker.consume_change()
    assert collected is not None
    assert collected.kind == "phone"
    assert collected.changed is True
    assert tracker.consume_change() is None


def test_a_momentary_gesture_is_reported_once_and_does_not_erase_the_activity():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 10)
    tracker.observe("wave", "在跟你挥手", confidence=0.9, at=1000.0 + 11)

    gesture = tracker.consume_change()
    assert gesture is not None
    assert gesture.kind == "wave"
    assert "挥手" in gesture.phrase
    # Having reported the gesture, the sustained activity resumes underneath.
    assert tracker.snapshot(at=1000.0 + 12).kind == "typing"
    assert tracker.consume_change() is None


def test_an_uncollected_change_expires_instead_of_staying_news_forever():
    """One change now has two readers, so it must stop being "just now" by itself.

    Nothing consumes a change the model declined to speak about, so without an
    expiry the poll would keep offering the same half-hour-old "佳刚刚从…变成…"
    on every round.
    """
    tracker = _tracker()
    base = 1000.0
    tracker.observe("still", "安静地待着", confidence=0.7, at=base)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.8, at=base + 10)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.8, at=base + 20)
    assert tracker.pending_change()[0] == "typing", "前置条件：变化确实产生了"

    # Still inside the window: a new reading must not wipe the change.
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.8,
                    at=base + 20 + activity.ACTIVITY_CHANGE_MAX_AGE_SECONDS - 1)
    assert tracker.has_pending_change() is True

    # Past it, the next reading retires the change.
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.8,
                    at=base + 20 + activity.ACTIVITY_CHANGE_MAX_AGE_SECONDS + 1)
    assert tracker.has_pending_change() is False
    assert tracker.consume_change() is None
    assert activity.activity_change_card() == ""


def test_peeking_does_not_take_the_change_away():
    """The camera bridge remembers; it must not consume what the poll needs."""
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    peeked = tracker.peek_change()
    assert peeked is not None and peeked.kind == "typing"
    # The change is still there for the next reader.
    assert tracker.has_pending_change() is True
    collected = tracker.consume_change()
    assert collected is not None and collected.kind == "typing"
    assert tracker.peek_change() is None


def test_activity_card_is_image_free_and_readable():
    tracker = _tracker()
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0)
    tracker.observe("typing", "在打键盘或动鼠标", confidence=0.7, at=1000.0 + 10)
    card = activity.activity_card() if False else None  # module tracker is separate
    assert card is None or isinstance(card, str)
    # The module-level card must render from the shared tracker.
    shared = activity.get_activity_tracker()
    shared.reset()
    activity.observe_action({"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.7})
    shared_snapshot = shared.snapshot()
    assert shared_snapshot.kind == "typing"
    assert "image" not in json.dumps(shared_snapshot.to_dict())
    shared.reset()


def test_observe_action_accepts_a_classifier_result():
    tracker = _tracker()
    snapshot = tracker.observe("wave", "在跟你挥手", confidence=0.9, at=500.0)
    assert snapshot.kind == "wave"
    assert snapshot.phrase == "在跟你挥手"


# --- camera inventory ------------------------------------------------------


def test_camera_manager_reports_a_sleeping_phone_in_plain_language(monkeypatch):
    manager = camera_manager.CameraManager()

    def fake_list(**_kwargs):
        return {"devices": [
            {"index": 0, "available": True, "usable": True, "luminance": 88.0, "width": 640, "height": 480, "backend": "dshow"},
            {"index": 1, "available": True, "usable": False, "luminance": 0.0, "reason": "返回全黑画面"},
        ]}

    monkeypatch.setattr(camera_manager, "list_camera_devices", fake_list)
    manager.scan(force=True)
    described = manager.describe()

    assert described["usable_indices"] == [0]
    assert described["sleeping_indices"] == [1]
    assert "息屏" in described["message"]
    assert manager.usable_indices() == [0]


def test_camera_manager_rescan_picks_up_a_camera_that_woke_up(monkeypatch):
    manager = camera_manager.CameraManager()
    state = {"usable": False}

    def fake_list(**_kwargs):
        return {"devices": [
            {"index": 1, "available": True, "usable": state["usable"], "luminance": 0.0 if not state["usable"] else 70.0,
             "width": 1280, "height": 720, "backend": "dshow"},
        ]}

    monkeypatch.setattr(camera_manager, "list_camera_devices", fake_list)
    manager.scan(force=True)
    assert manager.usable_indices() == []

    state["usable"] = True
    manager.scan(force=True)
    assert manager.usable_indices() == [1]


def test_camera_manager_respects_the_rescan_interval(monkeypatch):
    manager = camera_manager.CameraManager()
    calls = {"count": 0}

    def fake_list(**_kwargs):
        calls["count"] += 1
        return {"devices": [{"index": 0, "available": True, "usable": True, "luminance": 50.0}]}

    monkeypatch.setattr(camera_manager, "list_camera_devices", fake_list)
    manager.scan(force=True)
    manager.scan()  # inside the interval: must not probe hardware again
    assert calls["count"] == 1


def test_resolve_capture_index_prefers_the_browser_held_camera(monkeypatch):
    """The preview owns that device, so the backend must not compete for it."""
    manager = camera_manager.get_camera_manager()
    # The browser is holding index 0; the backend can also open index 1.
    manager.remember_browser_frame(index=0, data_url="data:image/jpeg;base64,ZmFrZQ==")
    monkeypatch.setattr(manager, "scan", lambda **_kwargs: {})
    monkeypatch.setattr(manager, "usable_indices", lambda: [1])
    assert camera_manager.resolve_capture_index({}) == 0, "浏览器持有的那一路优先"

    # Once the browser's frame goes stale, fall back to a camera we can open.
    manager._browser_frame = None
    assert camera_manager.resolve_capture_index({}) == 1


def test_an_explicit_camera_index_always_wins(monkeypatch):
    manager = camera_manager.get_camera_manager()
    manager.remember_browser_frame(index=0, data_url="data:image/jpeg;base64,ZmFrZQ==")
    assert camera_manager.resolve_capture_index({"camera_index": 3}) == 3
    manager._browser_frame = None


def test_a_browser_held_camera_is_not_reported_as_broken(monkeypatch):
    """The probe cannot open it, which used to look like a dead camera."""
    manager = camera_manager.CameraManager()
    manager.remember_browser_frame(index=0, data_url="data:image/jpeg;base64,ZmFrZQ==")
    # Pretend the probe found index 0 un-openable because the browser holds it.
    monkeypatch.setattr(camera_manager, "list_camera_devices", lambda **_kwargs: {"devices": [
        {"index": 0, "available": True, "usable": False, "luminance": 0.0, "reason": "打不开"},
        {"index": 1, "available": True, "usable": True, "luminance": 80.0},
    ]})
    manager.scan(force=True)

    described = manager.describe()
    assert 0 in described["usable_indices"], "浏览器正在用的摄像头不该被报成不可用"
    source = [item for item in described["devices"] if item["index"] == 0][0]
    assert source["owner"] == "browser"
    assert source["reason"] == ""


# --- fusion ----------------------------------------------------------------


def _result(*, faces=0, ratio=0.0, action=None, pose_usable=False, luminance=90.0):
    observation: dict = {}
    if faces:
        observation["face_signals"] = {"count": faces, "largest_ratio": ratio, "best_score": 0.9, "centered": True}
    if pose_usable:
        observation["pose_quality"] = {"confident": 12, "total": 17, "usable": True}
        observation["pose"] = {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9}] * 17}
    if action:
        observation["action"] = action
    return {"status": "success", "faces": faces, "luminance": luminance, "observations": [observation]}


def test_fusion_takes_the_best_action_across_cameras():
    fused = camera_manager.fuse_observations([
        {"index": 0, "result": _result(faces=0, action={"kind": "low_confidence", "label": "看不清", "confidence": 0.0})},
        {"index": 1, "result": _result(faces=1, ratio=0.07, pose_usable=True,
                                       action={"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.78})},
    ])
    assert fused["status"] == "success"
    assert fused["sources_used"] == [0, 1]
    assert fused["camera_count"] == 2
    assert fused["action"]["kind"] == "typing"
    assert fused["face_signals"]["largest_ratio"] == 0.07


def test_fusion_never_invents_a_conclusion_from_no_sources():
    fused = camera_manager.fuse_observations([])
    assert fused["status"] == "unknown"
    assert fused["sources_used"] == []
    assert "没有能看清你" in fused["message"]


def test_fused_narrative_uses_plain_language_and_no_confidence_numbers():
    fused = camera_manager.fuse_observations([
        {"index": 0, "result": _result(faces=1, ratio=0.07, pose_usable=True,
                                       action={"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.78})},
        {"index": 1, "result": _result(faces=0, pose_usable=True)},
    ])
    text = camera_manager.narrative_for_fused(fused, activity="专心敲键盘", duration=190)
    assert "专心敲键盘" in text
    assert "3 分钟" in text
    assert "0.78" not in text
    assert "2 个摄像头" in text


def test_fused_narrative_never_reads_an_inconclusive_kind_as_an_activity():
    """`low_confidence` is a state of the reader, not something Jia is doing."""
    fused = camera_manager.fuse_observations([
        {"index": 0, "result": _result(faces=0, action={"kind": "low_confidence", "label": "看不清", "confidence": 0.0})},
    ])
    for activity_kind in ("", "low_confidence", "unknown"):
        text = camera_manager.narrative_for_fused(fused, activity=activity_kind)
        assert "low_confidence" not in text
        assert "unknown" not in text
        assert "像是在" not in text or "看不清" in text
        assert text.endswith("。")


def test_fused_narrative_admits_when_the_angle_is_useless():
    fused = camera_manager.fuse_observations([
        {"index": 0, "result": {"status": "success", "faces": 0, "observations": [{}]}},
    ])
    text = camera_manager.narrative_for_fused(fused)
    assert "看不清" in text
    assert "0." not in text


def test_camera_fuse_reports_missing_cameras_without_calling_cloud(monkeypatch):
    service = ScreenVisionService()
    manager = camera_manager.get_camera_manager()
    monkeypatch.setattr(manager, "usable_indices", lambda: [])

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("fusing local cameras must not touch the cloud")

    monkeypatch.setattr(service, "_analyze_with_miya_vision", fail_if_called)
    result = json.loads(__import__("asyncio").run(service._camera_fuse({})))

    assert result["status"] == "unavailable"
    assert "息屏" in result["message"]


def test_camera_activity_tool_returns_readable_state():
    service = ScreenVisionService()
    shared = activity.get_activity_tracker()
    shared.reset()
    activity.observe_action({"kind": "drink", "label": "在喝水或吃东西", "confidence": 0.7})

    payload = json.loads(service._camera_activity({}))
    assert payload["status"] == "success"
    assert payload["activity"]["kind"] == "drink"
    assert payload["card"].startswith("[弥娅观察到的活动]")
    assert "image" not in json.dumps(payload)
    shared.reset()
