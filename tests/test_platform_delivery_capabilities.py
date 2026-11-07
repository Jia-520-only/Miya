"""Platform capability checks shared by proactive delivery routes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hub.decision_hub import DecisionHub, _supports_proactive_delivery


def test_proactive_capability_respects_explicit_opt_out_and_chat_type():
    adapter = SimpleNamespace(
        support_proactive_message=False,
        send_private_message=AsyncMock(),
        send_group_message=AsyncMock(),
    )
    assert not _supports_proactive_delivery(adapter, "private")
    assert not _supports_proactive_delivery(adapter, "group")


def test_proactive_capability_requires_the_matching_sender():
    private_only = SimpleNamespace(send_private_message=AsyncMock())
    assert _supports_proactive_delivery(private_only, "private")
    assert not _supports_proactive_delivery(private_only, "group")


def test_priority_route_skips_platforms_that_opt_out():
    opted_out = SimpleNamespace(
        is_online=True,
        support_proactive_message=False,
        send_private_message=AsyncMock(return_value=True),
    )
    allowed = SimpleNamespace(
        is_online=True,
        send_private_message=AsyncMock(return_value=True),
    )
    registry = SimpleNamespace(
        list_active=lambda: ["weixin_official_account", "weixin_ilink"],
        get=lambda pid: {
            "weixin_official_account": opted_out,
            "weixin_ilink": allowed,
        }[pid],
    )
    hub = object.__new__(DecisionHub)
    hub.platform_registry = registry
    hub._resolve_cross_platform_target_id = lambda target, _platform: target
    hub._attempt_proactive_send = lambda sender, *args: sender(*args)

    sent = asyncio.run(hub._send_by_priority("user", "reminder", "private", {}))

    assert sent
    opted_out.send_private_message.assert_not_called()
    allowed.send_private_message.assert_awaited_once_with("user", "reminder")

