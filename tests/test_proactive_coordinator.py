import asyncio

from core.proactive_coordinator import ProactiveCoordinator


class FakeAI:
    def __init__(self, response):
        self.response = response

    async def chat(self, **kwargs):
        return self.response


def test_skip_does_not_consume_global_quota():
    sent = []
    coordinator = ProactiveCoordinator()
    coordinator.configure(
        ai_client=FakeAI("SKIP"),
        send_callback=lambda *args: sent.append(args) or True,
        config={"max_messages_per_hour": 1, "min_interval_seconds": 0, "quiet_hours_enabled": False},
    )

    result = asyncio.run(coordinator.submit_event({"source": "self_check", "event": "normal"}, key="a"))
    assert result is False
    assert not sent
    assert not coordinator._sent_at


def test_all_sources_share_throttle_and_keep_real_event_for_ai():
    sent = []
    coordinator = ProactiveCoordinator()
    coordinator.configure(
        ai_client=FakeAI("按当前人格提醒：磁盘使用率为 96.5%。"),
        send_callback=lambda *args: sent.append(args) or True,
        config={"max_messages_per_hour": 1, "min_interval_seconds": 0, "quiet_hours_enabled": False},
    )

    first = asyncio.run(coordinator.submit_event(
        {"source": "self_check", "event": "resource_threshold_exceeded", "value": 96.5},
        key="resource:disk",
    ))
    second = asyncio.run(coordinator.submit_event(
        {"source": "earth_online", "event": "operator_update", "actions": ["真实动作"]},
        key="earth:patrol",
    ))
    assert first is True
    assert second is False
    assert sent[0][0].startswith("按当前人格")
    assert sent[0][1] == "default"


def test_high_priority_can_bypass_interval_but_not_hourly_quota():
    sent = []
    coordinator = ProactiveCoordinator()
    coordinator.configure(
        send_callback=lambda *args: sent.append(args) or True,
        config={"max_messages_per_hour": 1, "min_interval_seconds": 9999, "quiet_hours_enabled": False},
    )
    assert asyncio.run(coordinator.submit_event({"source": "self_check", "event": "offline"}, key="offline"))
    assert not asyncio.run(coordinator.submit_event(
        {"source": "self_check", "event": "recovered", "urgency": "critical"}, key="recovered"
    ))
