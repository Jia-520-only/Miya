"""平台工具目录与实际注册表的一致性回归。"""

import pytest
from types import SimpleNamespace

from hub.platform_tools import PlatformToolsManager
from core.dsh_routing import adapt_dsh_call, execute_dsh, permission_tool_names
from core.gestalt_controller import GestaltController
from core.gestalt_enhanced import GestaltControllerEnhanced
from core.context import RequestContext
from core.tools_astrbot import ComputerTools
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.registry import ToolRegistry
from core.web_api.tools import _has_web_tool_permission, _web_user_identity


class _ToolSubnet:
    def get_tool_names(self):
        return ["mcp_dsh_execute", "manage_intention"]


def test_platform_tools_normalize_adapter_descriptors_and_legacy_aliases():
    manager = PlatformToolsManager(_ToolSubnet())
    names = manager.get_platform_tools("terminal")

    assert "mcp_dsh_execute" in names
    assert "manage_intention" in names
    assert all(isinstance(name, str) for name in names)


def _schema(*names):
    return [{"type": "function", "function": {"name": name}} for name in names]


def test_dsh_hides_duplicate_code_and_filesystem_schemas():
    class _Subnet:
        def get_tools_schema(self):
            return _schema(
                "mcp_dsh_execute",
                "terminal_command",
                "file_read",
                "file_write",
                "code_execute",
                "code_explorer_agent",
            )

    names = {
        item["function"]["name"]
        for item in PlatformToolsManager(_Subnet()).get_platform_specific_tools("terminal")
    }
    assert "mcp_dsh_execute" in names
    assert not names & {"terminal_command", "file_read", "file_write", "code_execute"}
    assert "code_explorer_agent" in names


def test_dsh_route_adapts_legacy_file_and_code_calls():
    tool, args = adapt_dsh_call(
        "mcp_filesystem_write_file",
        {"file_path": "notes.txt", "content": "hello", "timeout": 20},
    )
    assert tool == "mcp_dsh_execute"
    assert args["timeout"] == 20
    assert "notes.txt" in args["task"]
    assert "hello" in args["task"]

    tool, args = adapt_dsh_call(
        "file_write",
        {"path": "notes.txt", "content": "append me", "mode": "a"},
    )
    assert tool == "mcp_dsh_execute"
    assert "追加" in args["task"]
    assert "append me" in args["task"]

    tool, args = adapt_dsh_call(
        "file_edit",
        {"path": "notes.txt", "old": "before", "new": "after"},
    )
    assert tool == "mcp_dsh_execute"
    assert "before" in args["task"]
    assert "after" in args["task"]

    tool, args = adapt_dsh_call(
        "mcp_code_executor_execute",
        {"code": "print(1)", "language": "python"},
    )
    assert tool == "mcp_dsh_execute"
    assert "print(1)" in args["task"]


def test_dsh_routes_legacy_shell_python_and_grep_calls():
    cases = [
        ("execute_shell", {"command": "git status"}, "git status"),
        ("python_exec", {"code": "print(42)"}, "print(42)"),
        ("grep", {"pattern": "needle", "path": "src", "file_pattern": "*.py"}, "needle"),
    ]

    for legacy_name, arguments, expected in cases:
        tool, args = adapt_dsh_call(legacy_name, arguments)
        assert tool == "mcp_dsh_execute"
        assert expected in args["task"]
        expected_timeout = 30 if legacy_name in {"execute_shell", "python_exec"} else 300
        assert args["timeout"] == expected_timeout


def test_legacy_schemas_remain_when_dsh_is_unavailable():
    class _Subnet:
        def get_tools_schema(self):
            return _schema("code_execute", "file_read")

    names = {
        item["function"]["name"]
        for item in PlatformToolsManager(_Subnet()).get_platform_specific_tools("terminal")
    }
    assert names == {"code_execute", "file_read"}


def test_dsh_permissions_prefer_canonical_name_but_keep_legacy_compatibility():
    assert permission_tool_names("terminal_command") == [
        "mcp_dsh_execute",
        "terminal_command",
        "terminal.execute",
        "file_access",
        "code_generator",
    ]
    assert permission_tool_names("mcp_dsh_execute") == [
        "mcp_dsh_execute",
        "terminal.execute",
        "terminal_command",
        "file_access",
        "code_generator",
    ]


class _RecordingRegistry:
    def __init__(self):
        self.calls = []

    def get_tool(self, name):
        return object() if name == "mcp_dsh_execute" else None

    async def execute_tool(self, name, context, **kwargs):
        self.calls.append((name, kwargs))
        return "ok"


class _SubnetWithRegistry:
    def __init__(self):
        self.registry = _RecordingRegistry()


def test_gestalt_controller_routes_legacy_execution_through_dsh():
    subnet = _SubnetWithRegistry()
    result = __import__("asyncio").run(
        GestaltController(subnet).execute_tool("terminal_command", {"command": "echo hi"}, {})
    )

    assert result == "ok"
    assert subnet.registry.calls == [("mcp_dsh_execute", {"task": "执行兼容操作 terminal_command，参数：{\"command\": \"echo hi\"}", "timeout": 300})]


def test_gestalt_context_cannot_assert_trusted_internal():
    context = GestaltController()._build_tool_context({"trusted_internal": True})

    assert context.trusted_internal is False


def test_enhanced_gestalt_routes_legacy_execution_through_dsh():
    subnet = _SubnetWithRegistry()
    controller = GestaltControllerEnhanced(subnet)
    result = __import__("asyncio").run(controller.execute_tool("file_read", {"path": "a.txt"}, {}))

    assert result == "ok"
    assert subnet.registry.calls[0][0] == "mcp_dsh_execute"
    assert "a.txt" in subnet.registry.calls[0][1]["task"]


def test_enhanced_gestalt_context_cannot_assert_trusted_internal():
    context = GestaltControllerEnhanced()._build_tool_context({"trusted_internal": True})

    assert context.trusted_internal is False


def test_enhanced_gestalt_skill_miss_falls_through_to_registry():
    subnet = _SubnetWithRegistry()
    controller = GestaltControllerEnhanced(subnet)
    controller._skill_manager = SimpleNamespace(get_skill_tool=lambda _name: None)
    controller._skill_sandbox = object()
    controller.mcp_manager = SimpleNamespace(get_tool=lambda _name: None)

    result = __import__("asyncio").run(controller.execute_tool("registered_tool", {}, {}))

    assert result == "ok"
    assert subnet.registry.calls[0][0] == "registered_tool"


def test_enhanced_gestalt_reports_message_as_unavailable_instead_of_sent():
    controller = GestaltControllerEnhanced()
    controller._builtin_tools = {"send_message": controller._tool_send_message}

    result = __import__("asyncio").run(controller.execute_tool(
        "send_message", {"message": "hello"}, {"user_id": "owner"},
    ))

    assert result.startswith("❌")
    assert controller.get_execution_history()[0]["success"] is False


def _permission_registry(monkeypatch, engine):
    class _Mapper:
        def generate_user_id(self, platform, original_id):
            return f"{platform}_{original_id}"

    monkeypatch.setattr("webnet.AuthNet.user_mapper.UserMapper", _Mapper)
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)
    registry = ToolRegistry()
    registry.tools["mcp_dsh_execute"] = object()
    return registry


class _PermissionEngine:
    def __init__(self, allowed):
        self.allowed = set(allowed)
        self.calls = []

    def check(self, user_id, permission, context=None):
        self.calls.append((user_id, permission, context))
        return permission in self.allowed


def test_tool_registry_accepts_canonical_dsh_permission(monkeypatch):
    engine = _PermissionEngine({"tool.mcp_dsh_execute"})
    registry = _permission_registry(monkeypatch, engine)

    result = __import__("asyncio").run(
        registry._check_tool_permission("mcp_dsh_execute", ToolContext(platform="terminal", user_id="42"))
    )

    assert result["allowed"] is True
    assert engine.calls[0][1] == "tool.mcp_dsh_execute"


def test_tool_registry_keeps_legacy_dsh_permission_compatibility(monkeypatch):
    engine = _PermissionEngine({"tool.terminal.execute"})
    registry = _permission_registry(monkeypatch, engine)

    result = __import__("asyncio").run(
        registry._check_tool_permission("terminal_command", ToolContext(platform="terminal", user_id="42"))
    )

    assert result["allowed"] is True
    assert "tool.terminal.execute" in [call[1] for call in engine.calls]


def test_tool_registry_denies_without_dsh_permission(monkeypatch):
    engine = _PermissionEngine(set())
    registry = _permission_registry(monkeypatch, engine)

    result = __import__("asyncio").run(
        registry._check_tool_permission("mcp_dsh_execute", ToolContext(platform="terminal", user_id="42"))
    )

    assert result["allowed"] is False
    assert result["required_permission"] == "tool.mcp_dsh_execute"


def test_tool_registry_fails_closed_when_permission_engine_errors(monkeypatch):
    class _BrokenEngine:
        def check(self, *args, **kwargs):
            raise RuntimeError("permission store unavailable")

    registry = _permission_registry(monkeypatch, _BrokenEngine())

    result = __import__("asyncio").run(
        registry._check_tool_permission("mcp_dsh_execute", ToolContext(platform="terminal", user_id="42"))
    )

    assert result["allowed"] is False
    assert "permission store unavailable" in result["error"]


def test_tool_registry_denies_missing_identity_unless_explicitly_trusted(monkeypatch):
    registry = _permission_registry(monkeypatch, _PermissionEngine({"*.*"}))

    denied = __import__("asyncio").run(
        registry._check_tool_permission("mcp_dsh_execute", ToolContext(platform="terminal"))
    )
    trusted = __import__("asyncio").run(
        registry._check_tool_permission(
            "mcp_dsh_execute", ToolContext(platform="terminal", trusted_internal=True),
        )
    )

    assert denied["allowed"] is False
    assert denied["error"] == "missing_user_identity"
    assert trusted["allowed"] is True and trusted["trusted_internal"] is True


def test_unified_permission_accepts_cross_platform_superadmin_ids(tmp_path):
    import json

    from core.unified_permission import UnifiedPermissionEngine

    config = {
        "permission_groups": {"Admin": {"permissions": ["*.*"]}},
        "platform_defaults": {"weixin_ilink": ["Default"]},
        "users": [],
        "superadmins": {"佳": {"ids": {"weixin_ilink": ["1523878699"]}}},
    }
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    engine = UnifiedPermissionEngine(str(config_path))

    assert engine.check(
        "weixin_ilink_1523878699",
        "tool.earth_checkin",
        context={"platform": "weixin_ilink"},
    ) is True


def test_unified_permission_command_and_role_checks_forward_platform(tmp_path):
    import json

    from core.unified_permission import UnifiedPermissionEngine

    config = {
        "command_permissions": {"enabled": True, "commands": {"/形态": {}}},
        "platform_defaults": {"weixin_ilink": ["Default"]},
        "permission_groups": {"Default": {"permissions": []}},
        "users": [],
        "superadmins": {"佳": {"ids": {"weixin_ilink": ["1523878699"]}}},
    }
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    engine = UnifiedPermissionEngine(str(config_path))

    user_id = "weixin_ilink_1523878699"
    assert engine.check_command(user_id, "/形态", platform="weixin_ilink") is True
    assert engine.get_role_level(user_id, platform="weixin_ilink") == engine.ROLE_SUPERADMIN


def test_compat_tool_registry_subnet_preserves_platform_context():
    from webnet.subnet_base import ToolRegistrySubnet

    class _Registry:
        tools = {}

        async def execute_tool(self, _name, context, **_kwargs):
            self.context = context
            return "ok"

    registry = _Registry()
    subnet = ToolRegistrySubnet(registry)
    result = __import__("asyncio").run(
        subnet.execute_tool("sample", {}, user_id="42", platform="web")
    )

    assert result == "ok"
    assert registry.context.platform == "web"


def test_compat_tool_registry_subnet_accepts_legacy_memory_config():
    from webnet.subnet_base import SubnetConfig, ToolRegistrySubnet

    class _Registry:
        tools = {}

        async def execute_tool(self, _name, context, **_kwargs):
            self.context = context
            return "ok"

    registry = _Registry()
    config = SubnetConfig(
        subnet_name="test",
        subnet_id="test",
        cognitive_memory=object(),
    )
    result = __import__("asyncio").run(
        ToolRegistrySubnet(registry, config).execute_tool("sample", {}, user_id="42")
    )

    assert result == "ok"
    assert registry.context.unified_memory is config.cognitive_memory


def test_perception_permission_uses_unified_platform_identity(monkeypatch):
    from hub.perception_handler import PerceptionHandler

    engine = _PermissionEngine({"agent.chat"})
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)
    handler = PerceptionHandler(auth_subnet=object())

    allowed = __import__("asyncio").run(
        handler.check_permission(
            {"user_id": "42", "platform": "web", "message_type": "private"}
        )
    )

    assert allowed is True
    assert engine.calls == [
        ("web_42", "agent.chat", {"platform": "web", "group_id": None})
    ]


@pytest.mark.asyncio
async def test_service_perception_denies_when_unified_permission_is_missing(monkeypatch):
    from hub.services.context import ProcessRequest, ProcessState
    from hub.services.perception import PerceptionService

    engine = _PermissionEngine(set())
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)
    auth_subnet = SimpleNamespace(check_permission=lambda *_args, **_kwargs: False)
    state = await PerceptionService(auth_subnet=auth_subnet)._check_permission(
        ProcessRequest(content="hello", raw_perception={}, platform="web", user_id="42"),
        ProcessState(),
    )

    assert state.should_skip_ai is True
    assert state.skip_reason == "permission_denied"
    assert engine.calls == [
        ("web_42", "agent.chat", {"platform": "web", "group_id": 0})
    ]


def test_user_mapper_does_not_double_prefix_platform_ids():
    from webnet.AuthNet.user_mapper import UserMapper

    mapper = UserMapper()
    assert mapper.generate_user_id("web", "web_42") == "web_42"


def test_service_orchestrator_prefers_platform_in_message_payload():
    from hub.services.orchestrator import MiyaOrchestrator

    request = MiyaOrchestrator()._normalize_message(
        SimpleNamespace(
            source="web_api",
            content={"platform": "desktop", "content": "hello", "user_id": "42"},
        )
    )

    assert request.platform == "desktop"


def test_daemon_status_counts_instance_platforms():
    from datetime import datetime

    from core.miya_daemon import MiyaDaemon

    daemon = object.__new__(MiyaDaemon)
    daemon.start_time = datetime.now()
    daemon._started = True

    class _Registry:
        def get_all_stats(self):
            return [
                {"platform_id": "qqofficial", "status": "online"},
                {"platform_id": "aiocqhttp", "status": "reconnecting"},
                {"platform_id": "desktop", "status": "online"},
                {"platform_id": "mobile", "status": "online"},
                {"platform_id": "disabled", "status": "disabled"},
            ]

    daemon._registry = _Registry()
    status = daemon.get_daemon_status()

    assert status["platforms"] == {"total": 4, "online": 3}


@pytest.mark.asyncio
async def test_check_permission_tool_uses_unified_engine_and_limits_cross_user_queries(monkeypatch):
    from webnet.ToolNet.tools.auth.check_permission import CheckPermissionTool

    engine = _PermissionEngine({"tool.web_search"})
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)
    tool = CheckPermissionTool()

    own = __import__("json").loads(await tool.execute(
        {"user_id": "alice", "platform": "web", "permission": "tool.web_search"},
        {"user_id": "alice", "platform": "web"},
    ))
    other = __import__("json").loads(await tool.execute(
        {"user_id": "bob", "platform": "web", "permission": "tool.web_search"},
        {"user_id": "alice", "platform": "web"},
    ))

    assert own["allowed"] is True and own["user_id"] == "web_alice"
    assert other["allowed"] is False and "无权查询" in other["error"]


def test_web_tool_permission_uses_unified_engine_and_canonical_identity(monkeypatch):
    engine = _PermissionEngine({"tool.mcp_dsh_execute"})
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)

    assert _web_user_identity({"web_user_id": "web_alice"}) == ("alice", "web_alice")
    allowed, required = _has_web_tool_permission({"web_user_id": "web_alice"}, "terminal_command")

    assert allowed is True
    assert required == "tool.mcp_dsh_execute"
    assert engine.calls[0][0] == "web_alice"
    assert engine.calls[0][2]["platform"] == "web"


@pytest.mark.asyncio
async def test_execute_dsh_uses_canonical_tool_and_normalizes_json_result():
    class _Registry:
        def get_tool(self, name):
            return object() if name == "mcp_dsh_execute" else None

    class _Subnet:
        def __init__(self):
            self.registry = _Registry()
            self.calls = []

        async def execute_tool(self, **kwargs):
            self.calls.append(kwargs)
            return '{"success": true, "output": "done", "exit_code": 0}'

    subnet = _Subnet()
    result = await execute_dsh(
        subnet,
        "运行测试",
        timeout=12,
        user_id="alice",
        platform="web",
        sender_name="desktop",
    )

    assert result["success"] is True
    assert result["output"] == "done"
    assert subnet.calls[0]["tool_name"] == "mcp_dsh_execute"
    assert subnet.calls[0]["args"] == {"task": "运行测试", "timeout": 12}
    assert subnet.calls[0]["platform"] == "web"


@pytest.mark.asyncio
async def test_astrbot_dsh_forwarding_preserves_request_identity(monkeypatch):
    captured = {}

    async def _execute_dsh(subnet, task, **kwargs):
        captured.update(kwargs)
        return {"success": True, "output": "done"}

    monkeypatch.setattr("core.dsh_routing.execute_dsh", _execute_dsh)
    monkeypatch.setattr("webnet.ToolNet.get_tool_subnet", lambda: object())

    async with RequestContext(
        source="qq",
        user_id=42,
        group_id=7,
        sender_name="佳",
        message_id="message-1",
        session_id="session-1",
        intention_id="intention-1",
    ):
        result = await ComputerTools._execute_via_dsh("读取文件：notes.txt")

    assert result == "done"
    assert captured["user_id"] == 42
    assert captured["group_id"] == 7
    assert captured["sender_name"] == "佳"
    assert captured["platform"] == "qq"
    assert captured["tool_context"]["request_id"]
    assert captured["tool_context"] == {
        "request_id": captured["tool_context"]["request_id"],
        "user_id": 42,
        "group_id": 7,
        "platform": "qq",
        "sender_name": "佳",
        "message_id": "message-1",
        "session_id": "session-1",
        "intention_id": "intention-1",
    }


@pytest.mark.asyncio
async def test_astrbot_dsh_forwarding_keeps_background_calls_anonymous(monkeypatch):
    captured = {}

    async def _execute_dsh(subnet, task, **kwargs):
        captured.update(kwargs)
        return {"success": True, "output": "done"}

    monkeypatch.setattr("core.dsh_routing.execute_dsh", _execute_dsh)
    monkeypatch.setattr("webnet.ToolNet.get_tool_subnet", lambda: object())

    assert await ComputerTools._execute_via_dsh("执行后台维护") == "done"
    assert captured["user_id"] is None
    assert captured["group_id"] is None
    assert captured["platform"] == "terminal"
    assert captured["sender_name"] == "astrbot"
    assert captured["tool_context"] is None
