from types import SimpleNamespace

from hub.context_builder import ContextBuilder


def test_context_builder_removes_current_event_but_keeps_earlier_same_text():
    older = SimpleNamespace(
        role="user", content="收到消息说个收到", timestamp="2026-11-17T12:00:00",
        metadata={"memory_event_id": "qq:1065262881:older"},
    )
    current = SimpleNamespace(
        role="user", content="收到消息说个收到", timestamp="2026-11-17T14:36:00",
        metadata={"memory_event_id": "qq:1065262881:current"},
    )

    result = ContextBuilder._exclude_current_message(
        [older, current], current_input="收到消息说个收到", current_message_id="current",
        group_id="1065262881", platform="aiocqhttp",
    )

    assert result == [older]


def test_context_builder_fallback_removes_only_latest_recent_duplicate(monkeypatch):
    older = SimpleNamespace(
        role="user", content="收到消息说个收到", timestamp="2026-11-17T12:00:00", metadata={},
    )
    recent = SimpleNamespace(
        role="user", content="收到消息说个收到", timestamp="2026-11-17T14:36:00", metadata={},
    )
    monkeypatch.setattr("hub.context_builder.datetime", SimpleNamespace(
        now=lambda: __import__("datetime").datetime(2026, 11, 17, 14, 36, 20).astimezone(),
    ))

    result = ContextBuilder._exclude_current_message(
        [older, recent], current_input="收到消息说个收到", current_message_id="",
        group_id="1065262881", platform="aiocqhttp",
    )

    assert result == [older]
