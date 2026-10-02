"""End-to-end: a camera transition must actually reach the send callback.

The unit tests use a fake coordinator, so they prove the bridge hands facts over.
This proves the *real* coordinator accepts them - including its own quiet-hours,
hourly quota and de-duplication rules - which is the part that could silently
swallow her line and leave the bridge looking healthy.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from mcpserver.screen_vision import proactive
from core import proactive_coordinator as coordinator_module


class _Snapshot:
    state = "returned"
    transition = "returned"
    confidence = 0.8
    reasons = ["80 秒后重新检测到人脸"]
    last_face_seconds = 1.0
    kind = ""
    phrase = ""
    duration = 0.0

    def __init__(self) -> None:
        self.updated_at = time.time()

    def describe(self) -> str:
        return "佳刚回到电脑前"


@pytest.fixture()
def real_coordinator(monkeypatch):
    """A genuine coordinator with a capturing send callback."""
    sent: list[tuple] = []

    async def _send(message, target_id, chat_type, platform, trigger_type):
        sent.append((message, target_id, chat_type, platform, trigger_type))
        return True

    coordinator = coordinator_module.ProactiveCoordinator()
    coordinator.configure(
        ai_client=None,  # no model needed; the raw facts become the message
        personality=None,
        send_callback=_send,
        config={"enabled": True, "max_messages_per_hour": 5, "min_interval_seconds": 0,
                "quiet_hours": [], "quiet_hours_enabled": False},
        default_target_id="1523878699",
    )
    monkeypatch.setattr(coordinator_module, "get_proactive_coordinator", lambda: coordinator)
    monkeypatch.setattr(proactive, "_owner_target_id", lambda: "1523878699")
    return coordinator, sent


@pytest.fixture()
def quiet(monkeypatch):
    monkeypatch.setattr(proactive, "remember_observation", _false)
    monkeypatch.setattr(proactive, "_conversation_context", _empty)
    monkeypatch.setattr(proactive, "recall_relevant", _empty)
    monkeypatch.setattr(proactive, "current_mood", lambda: {})


async def _false(**_kwargs) -> bool:
    return False


async def _empty(*_args, **_kwargs) -> str:
    return ""


def _presence(monkeypatch, snapshot):
    class _Tracker:
        def snapshot(self):
            return snapshot

        def last_transition(self):
            """The tracker's own record of its last change, which is what the
            bridge reads - a transition only survives one evaluation in the
            snapshot, so slower consumers would never see it."""
            return (snapshot.transition, snapshot.updated_at)

    monkeypatch.setattr("mcpserver.screen_vision.presence.get_presence_tracker", lambda: _Tracker())


def _activity(monkeypatch, snapshot):
    class _Tracker:
        def peek_change(self):
            return snapshot

        def consume_change(self):
            return snapshot

    monkeypatch.setattr("mcpserver.screen_vision.activity.get_activity_tracker", lambda: _Tracker())


def test_a_return_reaches_the_real_send_callback(monkeypatch, real_coordinator, quiet):
    _coordinator, sent = real_coordinator
    _presence(monkeypatch, _Snapshot())
    _activity(monkeypatch, None)
    bridge = proactive.CameraProactiveBridge()

    result = asyncio.run(bridge.tick())

    assert result["presence"] is True, "真实协调器拒绝了这次提交"
    assert len(sent) == 1, "她的话没有到达发送回调"
    message, target_id, _chat_type, _platform, trigger_type = sent[0]
    assert target_id == "1523878699"
    assert trigger_type == "camera_aware"
    # The facts she reasoned over are carried in the message, since no model was
    # configured to rewrite them.
    assert "returned" in message or "回到电脑前" in message


def test_the_hourly_quota_actually_limits_her(monkeypatch, real_coordinator, quiet):
    """Her voice must obey the same ceiling as every other background source."""
    coordinator, sent = real_coordinator
    coordinator.configure(config={"max_messages_per_hour": 1, "min_interval_seconds": 0,
                                  "quiet_hours": [], "quiet_hours_enabled": False})
    bridge = proactive.CameraProactiveBridge()

    _presence(monkeypatch, _Snapshot())
    _activity(monkeypatch, None)
    assert asyncio.run(bridge.tick())["presence"] is True

    # A different transition, moments later, must be refused by the quota.
    departed = _Snapshot()
    departed.state = "left"
    departed.transition = "left"
    _presence(monkeypatch, departed)
    assert asyncio.run(bridge.tick())["presence"] is False
    assert len(sent) == 1, "额度用完还是发出去了"


def test_quiet_hours_silence_her(monkeypatch, real_coordinator, quiet):
    coordinator, sent = real_coordinator
    coordinator.configure(config={"quiet_hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
                                                  13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                                  "quiet_hours_enabled": True})
    _presence(monkeypatch, _Snapshot())
    _activity(monkeypatch, None)
    bridge = proactive.CameraProactiveBridge()
    assert asyncio.run(bridge.tick())["presence"] is False
    assert sent == [], "静默时段不该发消息"


# --- routing to where he actually is ---------------------------------------


def test_she_speaks_on_the_platform_he_is_actually_using(monkeypatch, real_coordinator, quiet):
    """Regression: her line went to a desktop socket nobody was watching.

    The bridge submitted without a platform, so it took the default and the
    dispatcher reported "无法直接发送到 desktop，使用 WS 兜底" while Jia was in
    WeChat. ``get_current_platform`` is the documented single authority for
    routing proactive messages, so the bridge must ask it.
    """
    _coordinator, sent = real_coordinator
    monkeypatch.setattr(proactive, "active_platform", lambda: "weixin_ilink")
    _presence(monkeypatch, _Snapshot())
    _activity(monkeypatch, None)
    bridge = proactive.CameraProactiveBridge()

    assert asyncio.run(bridge.tick())["presence"] is True
    assert len(sent) == 1
    _message, _target, _chat_type, platform, _trigger = sent[0]
    assert platform == "weixin_ilink", "她的话没有送到佳真正在的平台"


def test_the_active_platform_is_stated_in_the_facts(monkeypatch):
    """The decision model should know where he is, not just what he is doing."""
    monkeypatch.setattr(proactive, "active_platform", lambda: "weixin_ilink")
    monkeypatch.setattr(proactive, "recall_relevant", _empty)
    monkeypatch.setattr(proactive, "current_mood", lambda: {})
    snapshot = _Snapshot()
    event = asyncio.run(proactive.build_presence_event(snapshot))
    assert event["facts"].get("消息发送平台（不是物理位置）") == "weixin_ilink"
    assert event["facts"].get("物理位置") == "摄像头无法判断"


def test_an_unknown_platform_falls_back_rather_than_dropping_the_message(monkeypatch, real_coordinator, quiet):
    """If awareness has no record, she should still be able to speak."""
    _coordinator, sent = real_coordinator
    monkeypatch.setattr(proactive, "active_platform", lambda: "")
    _presence(monkeypatch, _Snapshot())
    _activity(monkeypatch, None)
    bridge = proactive.CameraProactiveBridge()
    assert asyncio.run(bridge.tick())["presence"] is True
    assert len(sent) == 1


def test_active_platform_defers_to_platform_awareness(monkeypatch):
    """It must not invent a platform of its own."""
    from core import platform_awareness

    class _Awareness:
        def get_current_platform(self, user_id):
            assert user_id == "1523878699"
            return "weixin_ilink"

    monkeypatch.setattr(platform_awareness, "get_platform_awareness", lambda: _Awareness())
    monkeypatch.setattr(proactive, "_owner_target_id", lambda: "1523878699")
    assert proactive.active_platform() == "weixin_ilink"


def test_active_platform_is_empty_when_awareness_cannot_answer(monkeypatch):
    from core import platform_awareness

    def _boom():
        raise RuntimeError("没有平台感知")

    monkeypatch.setattr(platform_awareness, "get_platform_awareness", _boom)
    assert proactive.active_platform() == ""
