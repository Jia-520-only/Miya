"""Shared tool-result semantics and ToolNet accounting regressions."""

import asyncio
from types import SimpleNamespace

from core.tool_adapter import ToolAdapter
from core.miya_action import tool_outcome
from webnet.ToolNet.subnet import SubnetConfig, ToolSubnet


def test_adapter_recognizes_permission_and_missing_tool_errors():
    assert ToolAdapter._tool_result_state("❌ 权限不足：拒绝执行") is False
    assert ToolAdapter._tool_result_state("❌ 工具不存在: missing") is False
    assert ToolAdapter._tool_result_state("正常完成") is True


def test_adapter_preserves_unknown_execution_outcomes():
    assert ToolAdapter._tool_result_state(
        '{"status":"timed_out","success":false,"error":"ack missing"}'
    ) is None
    assert ToolAdapter._tool_result_state({"status": "completed", "success": None}) is None


def test_tool_adapter_context_cannot_assert_trusted_internal():
    context = ToolAdapter(enable_native=False)._prepare_tool_context({"trusted_internal": True})

    assert context.trusted_internal is False


def test_tool_adapter_batch_context_cannot_assert_trusted_internal():
    class NativeSubnet:
        async def execute_tool_batch(self, _calls, context):
            return [context]

    adapter = ToolAdapter(enable_native=True)
    adapter.mlink_subnet = NativeSubnet()
    context = {"trusted_internal": True, "user_id": None}

    result = asyncio.run(adapter.execute_tool_batch([], context))

    assert result[0].trusted_internal is False
    assert context == {"trusted_internal": True, "user_id": None}


def test_adapter_fallback_handles_structured_failure_results():
    calls = []

    class Registry:
        def get_tool(self, _name):
            return None

        async def execute_tool(self, name, _context, **_kwargs):
            calls.append(name)
            if name == "execute_on_desktop":
                return {"status": "rejected", "success": False}
            return "fallback completed"

    adapter = ToolAdapter(enable_native=False)
    adapter.set_tool_registry(Registry())

    result = asyncio.run(adapter.execute_tool(
        "execute_on_desktop", {}, {"platform": "desktop", "user_id": "42"},
    ))

    assert calls == ["execute_on_desktop", "terminal_command"]
    assert result.startswith("fallback completed")


def test_structured_failure_is_not_reported_as_success():
    assert tool_outcome({"status": "rejected", "success": False})["success"] is False


def test_adapter_does_not_repeat_an_unconfirmed_side_effect():
    calls = []

    class Registry:
        def get_tool(self, _name):
            return None

        async def execute_tool(self, name, _context, **_kwargs):
            calls.append(name)
            return '{"status":"timed_out","success":false,"error":"ack missing"}'

    adapter = ToolAdapter(enable_native=False)
    adapter.set_tool_registry(Registry())
    result = asyncio.run(adapter.execute_tool(
        "execute_on_desktop", {}, {"platform": "desktop", "user_id": "42"},
    ))

    assert '"timed_out"' in result
    assert calls == ["execute_on_desktop"]


def test_tool_subnet_accounts_for_failure_and_unknown_without_slicing_result():
    responses = iter([
        "❌ 权限不足：拒绝执行",
        {"status": "timed_out", "success": False, "error": "ack missing"},
    ])
    subnet = ToolSubnet.__new__(ToolSubnet)
    subnet.config = SubnetConfig()
    subnet.registry = SimpleNamespace(
        get_tool=lambda _name: object(),
        execute_tool=lambda *_args, **_kwargs: asyncio.sleep(0, result=next(responses)),
    )
    subnet._last_execution_info = None

    first = asyncio.run(subnet.execute_tool("sample", {}, user_id="42", platform="terminal"))
    second = asyncio.run(subnet.execute_tool("sample", {}, user_id="42", platform="terminal"))

    assert first.startswith("❌")
    assert second["status"] == "timed_out"
    assert subnet.config.success_calls == 0
    assert subnet.config.failed_calls == 1
    assert subnet.config.unknown_calls == 1
    assert subnet._last_execution_info["success"] is None
