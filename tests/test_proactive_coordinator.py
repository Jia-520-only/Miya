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


# --- fairness between sources ----------------------------------------------
#
# Regression: every background organ shared one hourly budget and the loudest
# one took all of it. earth_online patrols every 45 minutes and self-check warns
# about disks on its own schedule, so Miya's camera - the thing that actually
# knows how Jia is doing - was left with nothing. The log said it plainly:
# "小时总额度已满，跳过 key=camera:presence:returned".


def _fair_coordinator(sent, **overrides):
    coordinator = ProactiveCoordinator()
    config = {"max_messages_per_hour": 4, "max_messages_per_source_per_hour": 2,
              "max_events_per_source_per_hour": 2,
              "min_interval_seconds": 0, "same_source_interval_seconds": 0,
              "quiet_hours_enabled": False}
    config.update(overrides)
    coordinator.configure(send_callback=lambda *args: sent.append(args) or True, config=config)
    return coordinator


def test_one_source_cannot_eat_the_whole_hour():
    sent = []
    coordinator = _fair_coordinator(sent)

    for index in range(3):
        asyncio.run(coordinator.submit_event(
            {"source": "earth_online", "event": "operator_update", "n": index}, key=f"earth:{index}"))

    assert len(sent) == 2, "单一来源只能拿到它自己那份配额"
    # ...and there is still room for a different source to speak.
    assert asyncio.run(coordinator.submit_event(
        {"source": "camera", "event": "presence_change", "candidate_message": "佳刚回到电脑前"},
        key="camera:presence:returned"))
    assert len(sent) == 3


def test_different_sources_still_respect_the_global_interval():
    sent = []
    coordinator = _fair_coordinator(
        sent, min_interval_seconds=300, same_source_interval_seconds=90)
    assert asyncio.run(coordinator.submit_event({"source": "self_check", "event": "disk"}, key="disk"))
    assert not asyncio.run(coordinator.submit_event(
        {"source": "earth_online", "event": "patrol"}, key="patrol")), "不同来源要走全局间隔"


def test_a_source_may_follow_its_own_shorter_interval():
    """The camera's own two facts must not silence each other for two minutes.

    ``camera:voice`` went out and the global interval then dropped
    ``camera:presence:returned`` - a separate, more important fact - because both
    were judged against the same 120s gap.
    """
    sent = []
    coordinator = _fair_coordinator(
        sent, min_interval_seconds=120, same_source_interval_seconds=90)

    assert asyncio.run(coordinator.submit_event({"source": "camera", "event": "presence_change"}, key="k1"))
    now = coordinator._sent_at[-1]
    coordinator._sent_at[-1] = now - 100          # past the source's own interval
    coordinator._last_by_source["camera"] = now - 100
    assert asyncio.run(coordinator.submit_event({"source": "camera", "event": "activity"}, key="k2")), \
        "同一来源的两条不同事实应该排队发出，而不是互相顶掉"
    coord_now = coordinator._sent_at[-1]
    assert asyncio.run(coordinator.submit_event({"source": "camera", "event": "too_soon"}, key="k3")) is False
    assert coord_now  # 上一条确实发出去了


# --- events and voices are budgeted apart ----------------------------------
#
# Regression from the live log: the camera's own queued observations
# ("camera:voice:...:7/8/9/11") exhausted the camera's per-source allowance, and
# then every one of them was refused anyway - while `camera:presence:returned`,
# which fires once per real arrival, was refused for the same reason. Her
# observations and her one real event were drawing on one budget.


def test_her_chatter_cannot_starve_a_camera_event():
    sent = []
    coordinator = _fair_coordinator(
        sent, max_messages_per_hour=8, max_messages_per_source_per_hour=2,
        max_events_per_source_per_hour=2, min_interval_seconds=0, same_source_interval_seconds=0)

    # Two lines she decided to say use up the camera's *voice* allowance.
    for index in range(3):
        asyncio.run(coordinator.submit_message(
            f"她攒下的话 {index}", key=f"camera:voice:{index}",
            source="camera", trigger_type="camera_aware", kind="voice"))
    assert len(sent) == 2, "发言配额应该生效"

    # The arrival still gets through, because events have their own allowance.
    assert asyncio.run(coordinator.submit_event(
        {"source": "camera", "event": "presence_change", "candidate_message": "佳刚回到电脑前"},
        key="camera:presence:returned")), "她自己的闲话不该把'他回来了'挤掉"
    assert len(sent) == 3


def test_an_event_allowance_is_its_own_cap():
    sent = []
    coordinator = _fair_coordinator(
        sent, max_messages_per_hour=8, max_messages_per_source_per_hour=3,
        max_events_per_source_per_hour=2, min_interval_seconds=0, same_source_interval_seconds=0)

    for index in range(4):
        asyncio.run(coordinator.submit_event(
            {"source": "earth_online", "event": "operator_update", "n": index},
            key=f"earth:{index}"))
    assert len(sent) == 2, "事件也有自己的上限，不能无限"
    # ...and her voice still has room.
    assert asyncio.run(coordinator.submit_message(
        "她想说句话", key="camera:voice:1", source="camera", kind="voice"))
    assert len(sent) == 3


def test_the_default_kind_for_a_message_is_voice():
    """Callers that predate the split keep their budget, not the event one."""
    sent = []
    coordinator = _fair_coordinator(
        sent, max_messages_per_hour=8, max_messages_per_source_per_hour=1,
        max_events_per_source_per_hour=5, min_interval_seconds=0, same_source_interval_seconds=0)
    assert asyncio.run(coordinator.submit_message("第一句", key="a", source="soul"))
    assert not asyncio.run(coordinator.submit_message("第二句", key="b", source="soul")), \
        "不传 kind 的消息应该按'发言'记账"


# --- the decision must not hold the coordinator lock ------------------------


def test_a_slow_model_call_does_not_block_other_sources():
    """One slow AI round trip used to stall every source behind one lock.

    The model call is a network round trip; holding the single coordinator lock
    across it made the whole proactive system look dead whenever a reply was
    slow.
    """
    sent = []
    active = {"n": 0, "peak": 0}

    class SlowAI:
        async def chat(self, **kwargs):
            active["n"] += 1
            active["peak"] = max(active["peak"], active["n"])
            await asyncio.sleep(0.05)
            active["n"] -= 1
            return "弥娅想说的话"

    coordinator = ProactiveCoordinator()
    coordinator.configure(
        ai_client=SlowAI(),
        send_callback=lambda *args: sent.append(args) or True,
        config={"max_messages_per_hour": 10, "max_messages_per_source_per_hour": 10,
                "min_interval_seconds": 0, "same_source_interval_seconds": 0,
                "quiet_hours_enabled": False},
    )

    async def run_both():
        await asyncio.gather(
            coordinator.submit_event({"source": "camera", "event": "a"}, key="a"),
            coordinator.submit_event({"source": "earth_online", "event": "b"}, key="b"),
        )

    asyncio.run(run_both())
    assert active["peak"] == 2, "两条决策必须能同时进行，说明锁没有跨在模型调用上"
    assert len(sent) == 2
