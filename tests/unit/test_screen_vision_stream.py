"""Miya's observation stream: her working, made visible and bounded.

The panel shows what she saw, which model read it, how long each step took, and
what she decided. Two rules are load-bearing here and are pinned below:
thumbnails are off unless asked for, and turning them off forgets what was kept.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from mcpserver.screen_vision import vision_agent, vision_stream
from mcpserver.screen_vision.vision_stream import ObservationEvent, VisionStream, motion_signature


@pytest.fixture()
def stream() -> VisionStream:
    return VisionStream(max_events=12)


def _event(at: float | None = None, **kwargs) -> ObservationEvent:
    return ObservationEvent(id="", at=at if at is not None else time.time(), **kwargs)


# --- thumbnails are opt-in -------------------------------------------------


def test_thumbnails_are_off_until_explicitly_enabled(stream: VisionStream):
    """The long-standing promise is "no camera frames are kept"."""
    assert stream.thumbnails_enabled is False
    event = _event(thumbnails=[{"index": 0, "data_url": "data:image/jpeg;base64,AAAA"}])
    stream.record(event)
    assert stream.latest(include_thumbnails=True)["thumbnails"] == []
    assert stream.status()["events_with_thumbnails"] == 0


def test_a_stored_thumbnail_only_appears_once_enabled(stream: VisionStream):
    stream.set_thumbnails_enabled(True)
    stream.record(_event(thumbnails=[{"index": 0, "data_url": "data:image/jpeg;base64,AAAA"}]))
    latest = stream.latest(include_thumbnails=True)
    assert len(latest["thumbnails"]) == 1
    assert stream.status()["events_with_thumbnails"] == 1


def test_turning_thumbnails_off_also_forgets_what_was_stored(stream: VisionStream):
    """Otherwise the switch would only stop future frames, not remove old ones."""
    stream.set_thumbnails_enabled(True)
    for index in range(3):
        stream.record(_event(thumbnails=[{"index": index, "data_url": f"data:image/jpeg;base64,{index}"}]))
    assert stream.status()["events_with_thumbnails"] == 3

    stream.set_thumbnails_enabled(False)
    status = stream.status()
    assert status["events_with_thumbnails"] == 0
    assert status["thumbnail_bytes"] == 0
    assert stream.latest(include_thumbnails=True)["thumbnails"] == []


def test_a_payload_that_is_not_an_image_is_refused(stream: VisionStream):
    stream.set_thumbnails_enabled(True)
    stream.record(_event(thumbnails=[
        {"index": 0, "data_url": "not-an-image"},
        {"index": 1, "data_url": "data:image/jpeg;base64,AAAA"},
    ]))
    stored = stream.latest(include_thumbnails=True)["thumbnails"]
    assert [item["index"] for item in stored] == [1]


def test_an_absurdly_large_thumbnail_is_refused(stream: VisionStream):
    stream.set_thumbnails_enabled(True)
    huge = "data:image/jpeg;base64," + "A" * (vision_stream.MAX_THUMBNAIL_CHARS + 10)
    stream.record(_event(thumbnails=[{"index": 0, "data_url": huge}]))
    assert stream.latest(include_thumbnails=True)["thumbnails"] == []


def test_stored_thumbnails_stay_within_the_count_budget(stream: VisionStream):
    stream.set_thumbnails_enabled(True)
    for index in range(vision_stream.MAX_THUMBNAILS + 6):
        stream.record(_event(thumbnails=[{"index": index, "data_url": f"data:image/jpeg;base64,{index}"}]))
    status = stream.status()
    assert status["events_with_thumbnails"] <= vision_stream.MAX_THUMBNAILS
    # The newest survive; the oldest pictures are the ones forgotten.
    newest = stream.recent(limit=1, include_thumbnails=True)[0]
    assert newest["thumbnails"], "最新的缩略图不该被丢掉"


def test_events_are_bounded_but_keep_the_newest(stream: VisionStream):
    for index in range(20):
        stream.record(_event(summary=f"第 {index} 轮"))
    recent = stream.recent(limit=100)
    assert len(recent) == 12  # max_events
    assert recent[-1]["summary"] == "第 19 轮"


# --- the event carries her whole round -------------------------------------


def test_an_event_records_every_step_of_her_round(stream: VisionStream):
    event = _event(
        capture_seconds=0.31, local_seconds=0.28, interpret_seconds=0.87, total_seconds=1.21,
        cameras_used=[0], cameras_failed=[{"index": 1, "message": "全黑"}],
        reading={"faces": True, "action": {"kind": "typing", "label": "在打键盘或动鼠标"}},
        reading_text="看到你在画面里，在打键盘或动鼠标。",
        expression_text="嘴是张着的",
        rig={"JawOpen": 0.3},
        interpreted=True, interpreter="deepseek-v4-flash",
        summary="佳正埋头敲键盘", activity="工作", mood="专注", attention="看屏幕",
        notable=True, said="还在忙呀", intent_texts=["想知道佳在不在电脑前"],
    )
    stream.record(event)
    payload = stream.latest(include_thumbnails=True)

    assert payload["timing"]["total"] == 1.21
    assert payload["cameras_used"] == [0]
    assert payload["cameras_failed"][0]["index"] == 1
    assert payload["interpreter"] == "deepseek-v4-flash"
    assert payload["notable"] is True and payload["said"] == "还在忙呀"
    assert payload["intent_texts"] == ["想知道佳在不在电脑前"]
    assert payload["expression_text"] == "嘴是张着的"
    # The structured reading stays available, not just the prose.
    assert payload["reading"]["action"]["kind"] == "typing"


def test_an_event_reports_why_she_did_not_interpret(stream: VisionStream):
    stream.record(_event(interpreted=False, degraded_reason="有一路摄像头全黑，这次没有解读"))
    payload = stream.latest()
    assert payload["interpreted"] is False
    assert "全黑" in payload["degraded_reason"]


def test_clear_drops_everything_and_reports_the_count(stream: VisionStream):
    for _ in range(4):
        stream.record(_event())
    assert stream.clear() == 4
    assert stream.recent() == []
    assert stream.latest() is None


def test_get_returns_one_event_by_id(stream: VisionStream):
    stream.set_thumbnails_enabled(True)
    stream.record(_event(summary="目标", thumbnails=[{"index": 0, "data_url": "data:image/jpeg;base64,AA"}]))
    event_id = stream.latest()["id"]
    found = stream.get(event_id)
    assert found is not None
    assert found["summary"] == "目标"
    assert len(found["thumbnails"]) == 1
    assert stream.get("obs-does-not-exist") is None


# --- adaptive pacing -------------------------------------------------------


def test_motion_signature_is_coarse_enough_to_ignore_micro_movement():
    """Otherwise ordinary fidgeting would hold her on the fastest cadence."""
    base = {"faces": True, "action": {"kind": "typing"}, "blank_frame": False}
    same = {"faces": True, "action": {"kind": "typing", "confidence": 0.99}, "blank_frame": False}
    assert motion_signature(base) == motion_signature(same)

    changed = {"faces": True, "action": {"kind": "walk"}, "blank_frame": False}
    assert motion_signature(base) != motion_signature(changed)
    assert motion_signature(base) != motion_signature({**base, "faces": False})
    assert motion_signature(base) != motion_signature({**base, "blank_frame": True})


def test_cadence_slows_down_after_repeated_identical_readings():
    agent = vision_agent.VisionAgent()
    agent._interval = 30.0
    agent._slow_interval = 120.0
    agent._slow_after = 3
    agent._adaptive = True

    assert agent.cadence()["current_interval"] == 30.0
    with agent._lock:
        agent._unchanged_streak = 3
    assert agent.cadence()["current_interval"] == 120.0
    with agent._lock:
        agent._unchanged_streak = 2
    assert agent.cadence()["current_interval"] == 30.0


def test_cadence_stays_fixed_when_adaptive_is_off():
    agent = vision_agent.VisionAgent()
    agent._interval = 45.0
    agent._adaptive = False
    with agent._lock:
        agent._unchanged_streak = 99
    assert agent.cadence()["current_interval"] == 45.0


def test_tick_writes_a_full_observation_event(monkeypatch):
    """The panel's data must come from a real tick, not a re-derivation."""
    from mcpserver.screen_vision import service as vision_service

    stream = vision_stream.get_vision_stream()
    stream.clear()
    agent = vision_agent.VisionAgent()

    async def fake_look():
        return {
            "status": "success", "faces": 1, "camera_count": 1, "sources_used": [0],
            "failures": [{"index": 1, "message": "全黑"}],
            "message": "看到你在画面里，嘴是张着的。",
            "action": {"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.7},
            "pose_quality": {"usable": True},
            "face_expression": "嘴是张着的",
            "captures": [{"index": 0, "owner": "backend", "rig": {"JawOpen": 0.3}, "thumbnail": ""}],
        }

    async def fake_interpret(_reading, _agency):
        return {"summary": "佳在敲键盘", "activity": "工作", "mood": "专注",
                "attention": "看屏幕", "notable": False, "say": "", "_interpreter": "deepseek-v4-flash"}

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", fake_interpret)
    monkeypatch.setattr(vision_service.ScreenVisionService, "_vision_candidates",
                        lambda self: [("kimi_k2_vision", "k", "https://x/v1", "m")])

    result = asyncio.run(agent.tick())
    assert result["interpreted"] is True
    event = result["event"]
    assert event["interpreter"] == "deepseek-v4-flash"
    assert event["summary"] == "佳在敲键盘"
    assert event["expression_text"] == "嘴是张着的"
    assert event["rig"] == {"JawOpen": 0.3}
    assert event["cameras_failed"][0]["index"] == 1
    assert event["timing"]["total"] >= 0
    # And it really landed in the stream the panel reads.
    assert stream.latest()["summary"] == "佳在敲键盘"
    stream.clear()
