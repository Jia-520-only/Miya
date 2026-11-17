from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def test_profile_storage_uses_configured_profile_root(tmp_path, monkeypatch):
    from webnet.ToolNet.tools.cognitive import profile_storage

    expected = tmp_path / "profiles"
    monkeypatch.setattr(
        profile_storage,
        "get_cognitive_config",
        lambda key, default=None: {"path": str(expected)} if key == "profile" else default,
    )

    assert profile_storage._get_cognitive_dir() == expected


@pytest.mark.asyncio
async def test_profile_command_reads_canonical_identity(monkeypatch):
    from skills.commands.profile import handler

    loaded = []

    class LegacyStorage:
        def __init__(self, *_args, **_kwargs):
            pass

        async def load(self, entity_type, entity_id):
            loaded.append(("legacy", entity_type, entity_id))
            return None

    cognitive_storage = SimpleNamespace(read_profile=AsyncMock(return_value="统一身份侧写"))
    monkeypatch.setattr("memory.profile_storage.ProfileStorage", LegacyStorage)
    monkeypatch.setattr("webnet.ToolNet.tools.cognitive.profile_storage.get_profile_storage", lambda: cognitive_storage)

    response = await handler.execute(
        ["-t"],
        SimpleNamespace(
            canonical_user_id="canonical-user",
            user_id="platform-user",
            sender_id="platform-user",
            check_permission=lambda _required: False,
        ),
    )

    assert "统一身份侧写" in response
    assert loaded == [("legacy", "user", "canonical-user")]
    cognitive_storage.read_profile.assert_awaited_once_with("user", "canonical-user")


def test_p_alias_resolves_to_profile_command():
    from core.command_system import CommandRegistry

    registry = CommandRegistry()

    assert registry.match("/p") == ("profile", "", [])


@pytest.mark.asyncio
async def test_slash_dispatch_keeps_raw_and_canonical_user_ids(monkeypatch):
    from core.command_system import CommandContext
    from core.unified_platform_impl.message_mixin import _dispatch_slash_command

    captured = {}

    async def execute(_name, _subcommand, _args, context):
        captured["context"] = context
        return "profile result"

    registry = SimpleNamespace(
        match=lambda _text: ("profile", "", []),
        _commands={"profile": {"permission": "public"}},
        check_rate_limit=lambda *_args: (True, 0),
        execute=execute,
    )
    monkeypatch.setattr("core.command_system.get_command_registry", lambda: registry)
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: SimpleNamespace(
        is_superadmin=lambda *_args, **_kwargs: False,
    ))
    monkeypatch.setattr("webnet.ToolNet.tools.knowledge.knowledge_store.get_knowledge_store", lambda: None)
    resolver = SimpleNamespace(canonicalize=lambda user_id: "canonical-user")
    monkeypatch.setattr("memory.identity_resolver.get_identity_resolver", lambda: resolver)

    platform = SimpleNamespace(platform_id="telegram")
    result = await _dispatch_slash_command(platform, "/p", "platform-user", "", "private")

    assert result == "profile result"
    context = captured["context"]
    assert isinstance(context, CommandContext)
    assert context.user_id == "platform-user"
    assert context.canonical_user_id == "canonical-user"
