"""Miya's own camera loop must feed the path that turns seeing into speaking.

Written after measuring a real gap. ``core/vision_context`` is the store the
camera-aware proactive trigger reads, and it was written *only* by the desktop
browser's frame handover (``/api/camera/result`` and ``camera_event``). With no
window open her autonomous loop still looked every thirty seconds and still
wrote impressions - but the event trigger read an empty store, so a wave or a
sit-down seen by her own eyes could never become a line.

Four places held camera state and only one of them was wired to her voice. These
tests pin the wiring rather than the storage, because that is where the failure
was: the function existed and nothing called it.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _clear_camera_events() -> None:
    """Drop the process-local camera events so each test sees only its own."""
    from core.vision_context import get_vision_context

    store = get_vision_context()
    store._events.clear()  # noqa: SLF001 - there is no public reset, by design


@pytest.fixture()
def chat_system(monkeypatch):
    from core.proactive_chat import get_proactive_chat_system

    system = get_proactive_chat_system()

    class _AI:
        async def chat(self, **_kwargs):
            return "刚看到你挥手啦。"

    monkeypatch.setattr(system, "ai_client", _AI(), raising=False)
    monkeypatch.setattr("core.camera_control.read_state",
                        lambda: {"autonomous": True, "mode": "companion"}, raising=False)
    system._last_camera_event_key = ""  # noqa: SLF001
    system._last_camera_event_time = 0.0  # noqa: SLF001
    system._last_trigger_by_type.clear()  # noqa: SLF001
    return system


def test_a_reading_from_her_own_loop_is_readable_by_the_trigger():
    from core.vision_context import get_vision_context, record_camera_event

    _clear_camera_events()
    record_camera_event(
        kind="wave",
        summary="看到你在画面里，像是在跟你挥手。",
        confidence=0.9,
        mode="autonomous",
        camera_indices=[0],
        faces=1,
    )

    event = get_vision_context().latest(source="camera")
    assert event is not None, "她自己的观察必须写进这条主动链路读的存储"
    assert event["kind"] == "wave"
    assert event["status"] == "success"
    assert event["source"] == "camera"
    assert time.time() - float(event["timestamp"]) < 5
    assert event["camera_indices"] == [0]


def test_the_camera_trigger_fires_on_an_event_her_own_loop_wrote(chat_system):
    """The end-to-end gap: her eyes -> the store -> the proactive trigger."""
    from core.proactive_chat import ChatContext
    from core.vision_context import record_camera_event

    _clear_camera_events()
    record_camera_event(kind="wave", summary="像是在跟你挥手。", confidence=0.9)

    context = ChatContext(chat_type="private", target_id=1523878699, platform="weixin_ilink")
    result = asyncio.run(chat_system._check_camera_aware_trigger(context.target_id, context))

    assert result is not None and result.should_respond, \
        "她自己看到的手势必须能变成一句话，而不是只有浏览器推帧时才可以"
    _clear_camera_events()


def test_states_are_not_published_as_events():
    """A gesture is an event; "still" and "sitting" are states.

    Publishing states here would have her comment every time he simply sat
    quietly - the activity tracker already owns those, and it requires a
    duration before believing them.
    """
    from mcpserver.screen_vision.vision_agent import _GESTURE_EVENT_KINDS

    assert {"wave", "sit_down", "stand_up", "walk"} <= set(_GESTURE_EVENT_KINDS)
    assert not ({"still", "sitting", "standing", "typing", "low_confidence"}
                & set(_GESTURE_EVENT_KINDS))


def test_the_observation_loop_actually_publishes_them():
    """Source-level, because the disease here is "nobody calls it".

    The store, the trigger and the gesture list can all be correct while the
    loop that sees Jia never writes to any of them.
    """
    source = (ROOT / "mcpserver" / "screen_vision" / "vision_agent.py").read_text(encoding="utf-8")
    assert "record_camera_event" in source, \
        "自主观察循环没有把事件写进主动链路读的存储"


def test_camera_state_changes_are_booked_as_events_not_small_talk():
    """Source-level: the send callback must tell the coordinator which budget.

    Camera state changes reach the coordinator through the generic send callback,
    which defaulted to the *voice* allowance. The log showed the consequence -
    "来源 camera 的发言配额已满" - while the separate event allowance sat unused,
    so an arrival could be refused as if it were small talk.
    """
    source = (ROOT / "hub" / "decision_hub.py").read_text(encoding="utf-8")
    assert "EVENT if trigger_type == \"camera_aware\"" in source, \
        "摄像头状态变化必须走事件额度，而不是和她的话抢发言额度"
