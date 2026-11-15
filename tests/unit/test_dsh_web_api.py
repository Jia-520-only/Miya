"""Web API execution routes stay on the canonical DSH boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute

from core.web_api.desktop import DesktopRoutes
from core.web_api.tools import ToolExecuteRequest, ToolRoutes


def _endpoints(router):
    return {
        route.path: route.endpoint
        for route in router.routes
        if isinstance(route, APIRoute)
    }


@pytest.mark.asyncio
async def test_desktop_execution_routes_delegate_to_dsh(monkeypatch):
    calls = []

    async def fake_execute_dsh(tool_subnet, task, **kwargs):
        calls.append((task, kwargs))
        if task.startswith("列出目录"):
            return {
                "success": True,
                "structured_output": {"files": [{"name": "a.txt"}]},
                "output": "",
            }
        if task.startswith("读取文件"):
            return {
                "success": True,
                "structured_output": {"content": "line 1\nline 2\n"},
                "output": "",
            }
        return {"success": True, "output": "ok", "exit_code": 0}

    monkeypatch.setattr("core.web_api.desktop.execute_dsh", fake_execute_dsh)
    routes = DesktopRoutes(None, SimpleNamespace(tool_subnet=object()))
    endpoint = _endpoints(routes.router)

    terminal = await endpoint["/api/desktop/terminal/execute"]("echo hi", 12)
    listing = await endpoint["/api/desktop/files/list"](".", False)
    reading = await endpoint["/api/desktop/files/read"]("README.md", 0, 2)
    writing = await endpoint["/api/desktop/files/write"]({"path": "a.txt", "content": "hello"})
    deleting = await endpoint["/api/desktop/files/delete"]("README.md")

    assert terminal["success"] is True
    assert listing["files"] == [{"name": "a.txt"}]
    assert reading["content"] == "line 1\nline 2\n"
    assert writing["success"] is True
    assert deleting["success"] is True
    assert len(calls) == 5
    assert all("timeout" in kwargs for _, kwargs in calls)


@pytest.mark.asyncio
async def test_desktop_routes_keep_request_boundary_checks(monkeypatch):
    dsh = AsyncMock(return_value={"success": True, "output": "ok", "exit_code": 0})
    monkeypatch.setattr("core.web_api.desktop.execute_dsh", dsh)
    routes = DesktopRoutes(None, SimpleNamespace(tool_subnet=object()))
    endpoint = _endpoints(routes.router)

    with pytest.raises(Exception) as dangerous:
        await endpoint["/api/desktop/terminal/execute"]("shutdown /s", 30)
    assert getattr(dangerous.value, "status_code", None) == 403

    with pytest.raises(Exception) as outside:
        await endpoint["/api/desktop/files/list"]("..", False)
    assert getattr(outside.value, "status_code", None) == 403

    dsh.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_execute_command_delegates_to_dsh(monkeypatch):
    dsh = AsyncMock(return_value={"success": True, "output": "done", "exit_code": 0})
    monkeypatch.setattr("core.web_api.tools.execute_dsh", dsh)
    routes = ToolRoutes(None, SimpleNamespace(tool_subnet=object()))
    endpoint = _endpoints(routes.router)["/api/tools/task_execute"]

    result = await endpoint({"command": "echo hi"})

    assert result == {"success": True, "result": "done", "exit_code": 0}
    dsh.assert_awaited_once()
    assert "echo hi" in dsh.await_args.args[1]


def test_parse_dsh_result_rejects_error_payload_and_decodes_json_output():
    from core.dsh_routing import parse_dsh_result

    failed = parse_dsh_result({"status": "failed", "error": "boom"})
    assert failed["success"] is False

    structured = parse_dsh_result('{"files": [{"name": "a.txt"}]}')
    assert structured["success"] is True
    assert structured["structured_output"] == {"files": [{"name": "a.txt"}]}
