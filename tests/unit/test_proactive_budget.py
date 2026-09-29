"""Her speaking budget: what counts against it, and where it comes from.

Two separate defects made "she decided to say something" turn into silence:

* the hour's budget counted **proposals**, not delivered messages, so a handful
  of lines the unified coordinator throttled used up her whole hour and she
  stopped even forming new ones;
* three of the limits were hard-coded in `_normalize_config`, so whatever
  `config/proactive_chat.yaml` said about them had no effect at all.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from core.proactive_chat import (
    ChatContext,
    ProactiveResult,
    _normalize_config,
    get_proactive_chat_system,
    load_config,
)


@pytest.fixture()
def system():
    return get_proactive_chat_system()


# --- the knobs really come from the file -----------------------------------


def test_the_shipped_yaml_limits_reach_the_system():
    """These three used to be hard-coded, so the file could say anything."""
    limits = load_config()["limits"]
    assert limits["global_cooldown"] == 150
    assert limits["duplicate_window"] == 90
    assert limits["max_hourly_per_target"] == 8, "max_hourly_messages 必须真的读进来"
    assert limits["max_daily_per_target"] == 40
    assert limits["quiet_hours_enabled"] is True


def test_the_cross_source_quota_is_the_widened_one():
    """The old 3-per-hour was eaten by self-check and earth-online notices."""
    coordination = load_config()["coordination"]
    assert coordination["max_messages_per_hour"] == 8
    assert coordination["min_interval_seconds"] == 120


def test_a_missing_limits_section_falls_back_to_the_old_defaults():
    limits = _normalize_config({})["limits"]
    assert limits["global_cooldown"] == 300
    assert limits["duplicate_window"] == 60
    assert limits["quiet_hours_enabled"] is True
    assert limits["max_hourly_per_target"] == 3


# --- a refused message costs her nothing -----------------------------------


def test_a_refused_proposal_gives_the_hour_back(system):
    """A line the coordinator throttled never reached Jia, so it is not spent."""
    target = 497_001
    system._hourly_count.pop(target, None)
    for _ in range(system._max_hourly):
        system._record_trigger(target)
    assert system._check_rate_limits(target) is False

    system._refund_trigger(target)
    assert system._check_rate_limits(target) is True


def test_a_refused_proposal_gives_the_day_back(system):
    target = 497_002
    system._hourly_count.pop(target, None)
    system._daily_count[target] = {"date": datetime.now().date(), "count": system._max_daily}
    assert system._check_rate_limits(target) is False

    system._refund_trigger(target)
    assert system._check_rate_limits(target) is True


def test_refunding_an_empty_budget_is_harmless(system):
    """Refunds must never drive a counter below zero."""
    target = 497_003
    system._daily_count[target] = {"date": datetime.now().date(), "count": 0}
    system._hourly_count[target] = []
    system._refund_trigger(target)
    system._refund_trigger(target)
    assert system._daily_count[target]["count"] == 0
    assert system._hourly_count[target] == []


# --- the loop refunds, and does not lie about it ---------------------------


def _result(target: int) -> ProactiveResult:
    ctx = ChatContext(chat_type="private", target_id=target, platform="weixin_ilink")
    return ProactiveResult(True, "困了就歇一会儿。", "camera_aware", ctx)


def test_a_throttled_message_is_refunded_and_not_reported_as_sent(system, monkeypatch):
    target = 497_004
    system._hourly_count.pop(target, None)
    system._record_trigger(target)
    before = len(system._hourly_count[target])

    async def _refuse(*_args, **_kwargs):
        return False

    monkeypatch.setattr(system, "_send_callback", _refuse, raising=False)
    delivered = asyncio.run(system._deliver_background_result(target, _result(target)))

    assert delivered is False
    assert len(system._hourly_count[target]) == before - 1, "被拦下的提案不该占额度"


def test_a_delivered_message_keeps_its_cost(system, monkeypatch):
    target = 497_005
    system._hourly_count.pop(target, None)
    system._record_trigger(target)
    before = len(system._hourly_count[target])

    async def _accept(*_args, **_kwargs):
        return True

    monkeypatch.setattr(system, "_send_callback", _accept, raising=False)
    delivered = asyncio.run(system._deliver_background_result(target, _result(target)))

    assert delivered is True
    assert len(system._hourly_count[target]) == before, "真的发出去了就要照价计入"


def test_a_failing_send_outlet_also_refunds(system, monkeypatch):
    target = 497_006
    system._hourly_count.pop(target, None)
    system._record_trigger(target)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("发送出口挂了")

    monkeypatch.setattr(system, "_send_callback", _boom, raising=False)
    assert asyncio.run(system._deliver_background_result(target, _result(target))) is False
    assert len(system._hourly_count[target]) == 0
