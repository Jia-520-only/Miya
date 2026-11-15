"""DSH 与主弥娅进程的边界、上下文和异步生命周期回归。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from mcpserver.dsh import config_bridge
from mcpserver.dsh.service import DSHEngineService
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.tools.mcp.mcp_adapter import MCPTool
from webnet.ToolNet.tools.mcp.mcp_adapter import _MCP_KEYWORDS
from webnet.ToolNet.tools.basic.browse_web import BrowseWebTool
from webnet.ToolNet.subnet_router import ToolSubnetRouter


def test_headless_profile_only_registers_mineradio(tmp_path, monkeypatch):
    monkeypatch.setattr(config_bridge, "DSH_HOME", tmp_path)
    monkeypatch.setattr(config_bridge, "yaml", __import__("yaml"))

    config_bridge._ensure_headless_profile()
    patch_text = (tmp_path / "profiles" / "headless" / "cordis.patch.yml").read_text(encoding="utf-8")

    assert "mcp-miya-mineradio" in patch_text
    assert "miya-soul" not in patch_text


def test_dsh_config_reports_selected_base_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config_bridge, "DSH_HOME", tmp_path)
    monkeypatch.setattr(config_bridge, "_ensure_headless_profile", lambda: None)

    result = config_bridge.ensure_dsh_config(
        {
            "api_key": "test-key",
            "base_url": "https://model.example/v1",
            "model": "test-model",
            "provider": "deepseek-official",
        }
    )

    assert result["base_url"] == "https://model.example/v1"


@pytest.mark.asyncio
async def test_mcp_adapter_passes_request_context_to_dsh(monkeypatch):
    manager = SimpleNamespace(
        call=AsyncMock(return_value=SimpleNamespace(success=True, result="ok", execution_time=0.01))
    )
    monkeypatch.setattr("core.mcp_manager.get_mcp_manager", lambda: manager)

    tool = MCPTool("dsh", "execute", {"name": "execute", "parameters": {}})
    context = ToolContext(
        platform="web",
        user_id="owner",
        session_id="s1",
        request_id="r1",
        intention_id="i1",
        current_input="修复测试",
        action_id="a1",
    )
    assert await tool.execute({"task": "运行测试"}, context) == "ok"

    kwargs = manager.call.await_args.kwargs
    assert kwargs["miya_context"] == {
        "platform": "web",
        "user_id": "owner",
        "group_id": None,
        "session_id": "s1",
        "request_id": "r1",
        "intention_id": "i1",
        "message_id": None,
        "channel_id": None,
        "current_input": "修复测试",
        "action_id": "a1",
    }


@pytest.mark.asyncio
async def test_dsh_execute_is_async_and_returns_context(monkeypatch, tmp_path):
    service = DSHEngineService.__new__(DSHEngineService)
    service._bin_path = tmp_path / "bin.js"
    service._bin_path.touch()
    service._node_exe = "node"
    service._get_model_env = Mock(return_value={"api_key": "", "model": "test", "provider": "deepseek-official"})
    monkeypatch.setattr("mcpserver.dsh.service.ensure_dsh_config", lambda _env: {"home": str(tmp_path / "dsh")})

    process = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b"done", b"")),
        wait=AsyncMock(),
        terminate=Mock(),
    )
    monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=process))

    raw = await service._execute(
        {
            "task": "运行测试",
            "working_dir": str(tmp_path),
            "timeout": 5,
            "miya_context": {"request_id": "r1", "intention_id": "i1"},
        }
    )
    result = json.loads(raw)

    assert result["success"] is None
    assert result["context"] == {"request_id": "r1", "intention_id": "i1"}

    command = asyncio.create_subprocess_exec.await_args.args
    assert command[:4] == ("node", str(service._bin_path), "--profile", "headless")
    assert '"request_id": "r1"' in command[4]
    assert '"intention_id": "i1"' in command[4]


@pytest.mark.asyncio
async def test_dsh_timeout_terminates_process(monkeypatch, tmp_path):
    service = DSHEngineService.__new__(DSHEngineService)
    service._bin_path = tmp_path / "bin.js"
    service._bin_path.touch()
    service._node_exe = "node"
    service._get_model_env = Mock(return_value={"api_key": "", "model": "test", "provider": "deepseek-official"})
    monkeypatch.setattr("mcpserver.dsh.service.ensure_dsh_config", lambda _env: {"home": str(tmp_path / "dsh")})

    process = SimpleNamespace(
        returncode=None,
        communicate=AsyncMock(side_effect=asyncio.TimeoutError),
        wait=AsyncMock(),
        terminate=Mock(),
        kill=Mock(),
    )
    create = AsyncMock(return_value=process)
    monkeypatch.setattr("asyncio.create_subprocess_exec", create)

    result = json.loads(await service._execute({"task": "长任务", "timeout": 1}))

    assert result["success"] is False
    assert "超时" in result["error"]
    process.terminate.assert_called_once_with()
    process.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_dsh_result_contains_trace_fields_and_structured_output(monkeypatch, tmp_path):
    service = DSHEngineService.__new__(DSHEngineService)
    service._bin_path = tmp_path / "bin.js"
    service._bin_path.touch()
    service._node_exe = "node"
    service._get_model_env = Mock(return_value={"api_key": "", "model": "test", "provider": "deepseek-official"})
    monkeypatch.setattr("mcpserver.dsh.service.ensure_dsh_config", lambda _env: {"home": str(tmp_path / "dsh")})

    process = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b'{"changed": 2}', b"")),
        wait=AsyncMock(),
        terminate=Mock(),
    )
    monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=process))

    result = json.loads(
        await service._execute(
            {
                "task": "批量修改",
                "timeout": 5,
                "miya_context": {"request_id": "r1", "intention_id": "i1", "action_id": "a1"},
            }
        )
    )

    assert result["status"] == "completed"
    assert result["request_id"] == "r1"
    assert result["intention_id"] == "i1"
    assert result["action_id"] == "a1"
    assert result["structured_output"] == {"changed": 2}
    assert result["execution_status"] == "completed"
    assert result["success"] is None


@pytest.mark.asyncio
async def test_dsh_stderr_does_not_turn_successful_turn_into_failure(monkeypatch, tmp_path):
    service = DSHEngineService.__new__(DSHEngineService)
    service._bin_path = tmp_path / "bin.js"
    service._bin_path.touch()
    service._node_exe = "node"
    service._get_model_env = Mock(
        return_value={
            "api_key": "key",
            "base_url": "https://api.deepseek.com",
            "model": "test",
            "provider": "deepseek-official",
        }
    )
    monkeypatch.setattr("mcpserver.dsh.service.ensure_dsh_config", lambda _env: {"home": str(tmp_path / "dsh")})
    process = SimpleNamespace(
        returncode=0,
        communicate=AsyncMock(return_value=(b"turn ended", b"warning")),
        wait=AsyncMock(),
        terminate=Mock(),
    )
    create = AsyncMock(return_value=process)
    monkeypatch.setattr("asyncio.create_subprocess_exec", create)

    result = json.loads(await service._execute({"task": "检查", "timeout": 5}))

    assert result["success"] is None
    assert result["stderr"] == "warning"
    assert "error" not in result
    assert create.await_args.kwargs["env"]["DEEPSEEK_BASE_URL"] == "https://api.deepseek.com"


def test_subnet_router_discovers_unlisted_mcp_tools():
    class FakeTool:
        config = {"name": "mcp_memory_query"}

    class FakeRegistry:
        tools = {"mcp_memory_query": FakeTool()}

        def get_tool(self, name):
            return self.tools.get(name)

    router = ToolSubnetRouter(FakeRegistry())
    assert router.get_subnet_for_tool("mcp_memory_query") == "MCPNet"
    grouped = router.get_all_tools_by_subnet()
    assert grouped["MCPNet"][0]["name"] == "mcp_memory_query"


def test_dsh_and_browser_tools_have_non_overlapping_execution_boundaries():
    dsh_keywords = _MCP_KEYWORDS["dsh"]
    browser_description = BrowseWebTool().config["description"]

    assert "浏览器" not in dsh_keywords
    assert any("文件" in keyword for keyword in dsh_keywords)
    assert any("多步骤" in keyword for keyword in dsh_keywords)
    assert "浏览器专用工具" in browser_description
    assert "mcp_dsh_execute" in browser_description


@pytest.mark.asyncio
async def test_dsh_cancellation_terminates_process(monkeypatch, tmp_path):
    service = DSHEngineService.__new__(DSHEngineService)
    service._bin_path = tmp_path / "bin.js"
    service._bin_path.touch()
    service._node_exe = "node"
    service._get_model_env = Mock(return_value={"api_key": "", "model": "test", "provider": "deepseek-official"})
    monkeypatch.setattr("mcpserver.dsh.service.ensure_dsh_config", lambda _env: {"home": str(tmp_path / "dsh")})

    process = SimpleNamespace(
        returncode=None,
        communicate=AsyncMock(side_effect=asyncio.Event().wait),
        wait=AsyncMock(),
        terminate=Mock(),
        kill=Mock(),
    )
    monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=process))

    task = asyncio.create_task(service._execute({"task": "可取消任务", "timeout": 30}))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    process.terminate.assert_called_once_with()
    process.wait.assert_awaited_once()
