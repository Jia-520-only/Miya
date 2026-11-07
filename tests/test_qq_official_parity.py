"""QQ 官方机器人与 OneBot 的会话、权限、工具和媒体投递回归。"""

import asyncio
import base64
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.command_system import CommandContext
from core.file_context import OutboundFile
from core.platform_context import (
    get_current_platform_adapter,
    reset_current_platform_adapter,
    set_current_platform_adapter,
)
from core.unified_platform_impl import message_mixin as shared
from core.unified_platform_impl import qq_official_platform as official
from core.unified_platform_impl.qq_official_platform import QQOfficialPlatform
from hub.platform_tools import PlatformToolsManager
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.tools.message.send_message import SendMessageTool


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def platform(monkeypatch):
    adapter = QQOfficialPlatform({"bot_qq": "42"})
    adapter._bot_client = SimpleNamespace(api=SimpleNamespace(
        post_group_message=AsyncMock(return_value={"id": "group-receipt"}),
        post_c2c_message=AsyncMock(return_value={"id": "private-receipt"}),
        put_reaction=AsyncMock(return_value=""),
        _http=SimpleNamespace(request=AsyncMock(return_value={"file_info": "uploaded-media"})),
    ))
    monkeypatch.setattr(adapter, "_tts_should_voice", lambda: False)
    monkeypatch.setattr(adapter, "_tts_should_local", lambda: False)
    return adapter


@pytest.fixture
def command_registry(monkeypatch):
    registry = SimpleNamespace(
        match=lambda text: ("help", "", []) if text.startswith("/help") else None,
        _commands={"help": {"permission": "public"}},
        check_rate_limit=lambda *args: (True, 0),
        execute=AsyncMock(return_value="命令回复"),
    )
    engine = SimpleNamespace(is_superadmin=MagicMock(return_value=False), _config={"superadmins": {}})
    monkeypatch.setattr("core.command_system.get_command_registry", lambda: registry)
    monkeypatch.setattr("core.unified_permission.get_permission_engine", lambda: engine)
    monkeypatch.setattr("webnet.ToolNet.tools.knowledge.knowledge_store.get_knowledge_store", lambda: None)
    return registry, engine


@pytest.fixture
def routed_platform(platform, command_registry, monkeypatch):
    platform._miya_core = SimpleNamespace(decision_hub=SimpleNamespace(
        process_perception_cross_platform=AsyncMock(return_value="收到")
    ))
    monkeypatch.setattr(shared, "_resolve_files_and_images", AsyncMock())
    monkeypatch.setattr("core.platform_awareness.get_platform_awareness", lambda: SimpleNamespace(
        record_activity=lambda *args: None
    ))
    monkeypatch.setattr("webnet.ToolNet.pipelines.content_pipeline.get_pipeline", lambda: SimpleNamespace(
        detect_and_process=AsyncMock(return_value=[])
    ))
    return platform


def incoming(kind="group", group="GROUP_OPENID", user="USER_OPENID", content="/help", mid="incoming"):
    return SimpleNamespace(
        id=mid, content=content, group_openid=group if kind == "group" else None,
        channel_id="channel-1" if kind == "channel" else None,
        author=SimpleNamespace(user_openid=user), attachments=[], message_reference=None,
        reply=AsyncMock(return_value={"id": "channel-receipt"}),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["group", "c2c", "channel", "direct"])
async def test_command_returns_to_original_conversation(routed_platform, command_registry, kind):
    msg = incoming(kind, content="<@!42> /help" if kind in {"group", "channel"} else "/help")
    await routed_platform._handle_message(msg, kind)
    api = routed_platform._bot_client.api
    if kind in {"channel", "direct"}:
        msg.reply.assert_awaited_once_with(content="命令回复")
        api.post_c2c_message.assert_not_called()
        api.post_group_message.assert_not_called()
    else:
        sender = api.post_group_message if kind == "group" else api.post_c2c_message
        assert sender.await_count == 1
        payload = sender.call_args.kwargs
        assert payload["msg_id"] == "incoming"
        assert payload["content"] == "命令回复"
        assert payload["msg_seq"] == 1
        assert payload["group_openid" if kind == "group" else "openid"] == (
            "GROUP_OPENID" if kind == "group" else "USER_OPENID"
        )
    context = command_registry[0].execute.call_args.args[-1]
    assert context.sender_id == "USER_OPENID"
    assert context.scope == ("group" if kind in {"group", "channel"} else "private")
    assert routed_platform._reply_context.get() is None


@pytest.mark.anyio
@pytest.mark.parametrize("group", ["GROUP_A", "GROUP_B", "000123"])
async def test_group_openid_reaches_decision_hub_unchanged(routed_platform, group):
    token = set_current_platform_adapter(None)
    try:
        await routed_platform._handle_message(incoming(group=group, content="你好"), "group")
        perception = routed_platform._miya_core.decision_hub.process_perception_cross_platform.call_args.args[0].content
        assert perception["group_id"] == group
        assert perception["message_id"] == "incoming"
        assert perception["message_type"] == "group"
        assert get_current_platform_adapter() is None
    finally:
        reset_current_platform_adapter(token)


@pytest.mark.anyio
@pytest.mark.parametrize("owner_env", ["0", "123"])
async def test_official_permissions_do_not_use_numeric_qq_env(platform, command_registry, monkeypatch, owner_env):
    registry, engine = command_registry
    registry._commands["help"]["permission"] = "superadmin"
    monkeypatch.setenv("QQ_SUPERADMIN_QQ", owner_env)
    result = await shared._dispatch_slash_command(platform, "/help", "123", "GROUP", "group")
    assert result
    registry.execute.assert_not_called()
    engine.is_superadmin.assert_called_with("123", platform="qqofficial")


@pytest.mark.anyio
async def test_explicit_official_owner_keeps_openid_and_permission(platform, command_registry):
    registry, engine = command_registry
    registry._commands["help"]["permission"] = "superadmin"
    engine.is_superadmin.return_value = True
    await shared._dispatch_slash_command(platform, "/help", "OWNER_OPENID", "GROUP", "group")
    context = registry.execute.call_args.args[-1]
    assert context.sender_id == "OWNER_OPENID"
    assert context.check_permission("superadmin")
    assert context.onebot_client is None


def test_empty_legacy_ids_are_never_admins():
    context = CommandContext()
    assert context.check_permission("public")
    assert not context.check_permission("admin")
    assert not context.check_permission("superadmin")
    assert CommandContext(sender_id=123, superadmin_qq=123).check_permission("superadmin")


@pytest.mark.anyio
async def test_group_command_failure_never_retries_in_private():
    adapter = SimpleNamespace(
        send_group_message=AsyncMock(side_effect=RuntimeError("rejected")),
        send_private_message=AsyncMock(),
    )
    await shared._send_cmd_reply(adapter, "reply", "USER", "GROUP", "group")
    adapter.send_group_message.assert_awaited_once_with("GROUP", "reply")
    adapter.send_private_message.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["group", "private"])
async def test_onebot_command_replies_keep_numeric_protocol_targets(kind):
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    adapter = object.__new__(OneBotPlatform)
    adapter._ws = SimpleNamespace(send_str=AsyncMock())
    adapter._connected = True
    await shared._send_cmd_reply(adapter, "reply", "123", "456", kind)
    payload = json.loads(adapter._ws.send_str.call_args.args[0])
    assert payload["params"]["group_id" if kind == "group" else "user_id"] == (
        456 if kind == "group" else 123
    )


@pytest.mark.anyio
async def test_concurrent_official_replies_keep_their_message_ids(platform):
    barrier = asyncio.Event()
    count = 0

    async def route(**kwargs):
        nonlocal count
        count += 1
        if count == 2:
            barrier.set()
        await barrier.wait()
        return kwargs["group_id"]

    platform.route_to_decision_hub = route
    await asyncio.gather(
        platform._handle_message(incoming(group="GROUP_A", content="a", mid="message-a"), "group"),
        platform._handle_message(incoming(group="GROUP_B", content="b", mid="message-b"), "group"),
    )
    payloads = [call.kwargs for call in platform._bot_client.api.post_group_message.call_args_list]
    assert {(p["group_openid"], p["msg_id"], p["content"], p["msg_seq"]) for p in payloads} == {
        ("GROUP_A", "message-a", "GROUP_A", 1), ("GROUP_B", "message-b", "GROUP_B", 1)
    }


@pytest.mark.anyio
async def test_platform_context_is_isolated_between_concurrent_tasks():
    async def task(adapter):
        token = set_current_platform_adapter(adapter)
        try:
            await asyncio.sleep(0)
            return get_current_platform_adapter()
        finally:
            reset_current_platform_adapter(token)

    onebot, qq = object(), object()
    assert await asyncio.gather(task(onebot), task(qq)) == [onebot, qq]


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["group", "private", "c2c"])
async def test_media_upload_is_followed_by_confirmed_message(platform, tmp_path, kind):
    image = tmp_path / "picture.png"
    image.write_bytes(b"image-bytes")
    assert await platform._do_send_file("PEER_OPENID", OutboundFile.from_local(str(image)), message_type=kind)
    api = platform._bot_client.api
    route = api._http.request.call_args.args[0]
    upload = api._http.request.call_args.kwargs["json"]
    assert "/files" in route.url
    assert base64.b64decode(upload["file_data"]) == b"image-bytes"
    assert "url" not in upload
    assert upload["srv_send_msg"] is False
    sender = api.post_group_message if kind == "group" else api.post_c2c_message
    assert sender.call_args.kwargs["msg_type"] == 7
    assert sender.call_args.kwargs["media"] == {"file_info": "uploaded-media"}


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["upload", "send"])
async def test_media_requires_both_upload_and_delivery_receipts(platform, stage):
    api = platform._bot_client.api
    if stage == "upload":
        api._http.request.return_value = {}
    else:
        api.post_group_message.return_value = {}
    assert not await platform._send_media("GROUP", "group", 1, "aW1hZ2U=")
    assert platform._health.message_out_count == 0
    if stage == "upload":
        api.post_group_message.assert_not_called()


@pytest.mark.anyio
async def test_tts_sends_voice_with_reply_id_and_no_duplicate_text(platform, monkeypatch, tmp_path):
    voice = tmp_path / "voice.silk"
    voice.write_bytes(b"silk-data")
    monkeypatch.setattr(platform, "_tts_should_voice", lambda: True)
    monkeypatch.setattr("core.tts.engine_router.synthesize", AsyncMock(return_value=str(voice)))
    platform.route_to_decision_hub = AsyncMock(return_value="语音回复")
    await platform._handle_message(incoming(), "group")
    api = platform._bot_client.api
    api.post_group_message.assert_awaited_once()
    assert api.post_group_message.call_args.kwargs["msg_type"] == 7
    assert api.post_group_message.call_args.kwargs["msg_id"] == "incoming"
    assert api._http.request.call_args.kwargs["json"]["file_type"] == 3


@pytest.mark.anyio
async def test_voice_conversion_works_on_copy_and_failure_falls_back_to_text(platform, monkeypatch, tmp_path):
    voice = tmp_path / "original.mp3"
    voice.write_bytes(b"original-audio")
    converter = ModuleType("astrbot.core.utils.tencent_record_helper")

    async def fail_conversion(path):
        assert Path(path) != voice
        assert Path(path).read_bytes() == voice.read_bytes()
        Path(path).unlink()
        raise RuntimeError("encoder unavailable")

    converter.audio_to_tencent_silk_base64 = fail_conversion
    monkeypatch.setitem(sys.modules, converter.__name__, converter)
    monkeypatch.setattr(platform, "_tts_should_voice", lambda: True)
    monkeypatch.setattr("core.tts.engine_router.synthesize", AsyncMock(return_value=str(voice)))
    platform.route_to_decision_hub = AsyncMock(return_value="文字回退")
    await platform._handle_message(incoming(), "group")
    assert voice.read_bytes() == b"original-audio"
    payload = platform._bot_client.api.post_group_message.call_args.kwargs
    assert payload["content"] == "文字回退" and payload["msg_type"] == 0
    assert payload["msg_id"] == "incoming"


def test_attachment_is_downloaded_only_by_its_own_category(monkeypatch):
    download = MagicMock(return_value=b"image")
    monkeypatch.setattr(official, "_download_attachment_url", download)
    msg = SimpleNamespace(attachments=[SimpleNamespace(content_type="image/png", url="https://example/image.png")])
    assert len(official._parse_attachments(msg, "image")) == 1
    assert official._parse_attachments(msg, "file") == []
    download.assert_called_once()


def test_openid_mapping_never_selects_an_unrelated_owner(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    (config / "permissions.json").write_text(json.dumps({"superadmins": {
        "other": {"ids": {"qq": ["111"], "qqofficial": ["OTHER_OPENID"]}},
        "matching": {"ids": {"qq": ["222"], "qqofficial": "MATCHING_OPENID"}},
    }}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert QQOfficialPlatform._resolve_qqofficial_openid("222") == "MATCHING_OPENID"
    assert QQOfficialPlatform._resolve_qqofficial_openid("333") == "333"
    assert QQOfficialPlatform._resolve_qqofficial_openid("ALREADY_OPENID") == "ALREADY_OPENID"


@pytest.mark.parametrize("alias", ["qqofficial", "qq_official"])
def test_official_tools_share_business_features_and_filter_onebot_actions(alias):
    business = {"memory_add", "knowledge_text_search", "create_schedule_task", "weather_query", "send_message"}
    native = {"qq_like", "send_poke", "get_member_list", "group_file_downloader"}
    subnet = SimpleNamespace(get_tools_schema=lambda: [
        {"function": {"name": name}} for name in business | native | {"react_emoji"}
    ])
    manager = PlatformToolsManager(subnet)
    names = {tool["function"]["name"] for tool in manager.get_platform_specific_tools(alias)}
    assert business <= names
    assert "react_emoji" in names
    assert not names & native
    assert native <= {tool["function"]["name"] for tool in manager.get_platform_specific_tools("aiocqhttp")}
    assert not native & {tool["function"]["name"] for tool in manager.get_minimal_chat_tools(alias)}


@pytest.mark.anyio
async def test_message_tool_uses_official_adapter_and_respects_failure(platform):
    onebot = SimpleNamespace(send_group_message=AsyncMock(return_value=True))
    context = ToolContext(
        platform="qqofficial", platform_adapter=platform, onebot_client=onebot,
        user_id="canonical-user", platform_user_id="USER_OPENID", group_id="GROUP_OPENID", message_type="group",
    )
    result = await SendMessageTool().execute({"message": "hello"}, context)
    assert "✅" in result
    assert platform._bot_client.api.post_group_message.call_args.kwargs["group_openid"] == "GROUP_OPENID"
    onebot.send_group_message.assert_not_called()
    context.message_sent_this_turn = False
    platform._bot_client.api.post_group_message.return_value = {}
    assert "失败" in await SendMessageTool().execute({"message": "hello"}, context)
    assert not context.message_sent_this_turn


@pytest.mark.anyio
async def test_official_channel_reaction_uses_current_channel_and_message(platform):
    from webnet.ToolNet.tools.entertainment.react_emoji import ReactEmoji

    platform._bot_client.api.put_reaction = AsyncMock(return_value="")
    context = ToolContext(
        platform="qqofficial", platform_adapter=platform, channel_id="CHANNEL_OPENID",
        message_id="MESSAGE_OPENID", message_type="group",
    )
    result = await ReactEmoji().execute({"emoji_id": "123", "emoji_type": 1}, context)
    assert "✅" in result
    platform._bot_client.api.put_reaction.assert_awaited_once_with(
        "CHANNEL_OPENID", "MESSAGE_OPENID", 1, "123"
    )


@pytest.mark.anyio
async def test_channel_event_exposes_reaction_context_to_tools(platform):
    captured = {}

    async def route(**kwargs):
        captured.update(kwargs)
        return ""

    platform.route_to_decision_hub = route
    await platform._handle_message(incoming(kind="channel", mid="channel-message"), "channel")
    assert captured["extra"]["channel_id"] == "channel-1"
    assert captured["extra"]["message_id"] == "channel-message"


@pytest.mark.anyio
async def test_official_group_reaction_is_rejected_without_channel_id(platform):
    from webnet.ToolNet.tools.entertainment.react_emoji import ReactEmoji

    context = ToolContext(platform="qqofficial", platform_adapter=platform, message_id="GROUP_MSG")
    result = await ReactEmoji().execute({"emoji_id": "123"}, context)
    assert "频道消息" in result
    platform._bot_client.api.put_reaction.assert_not_called()


@pytest.mark.anyio
async def test_like_does_not_report_false_result_as_success():
    from webnet.ToolNet.tools.entertainment.qqlike import QQLike

    adapter = SimpleNamespace(platform_id="aiocqhttp", supports_like=True, send_like=AsyncMock(return_value=False))
    context = ToolContext(platform="aiocqhttp", platform_adapter=adapter, user_id=123)
    result = await QQLike().execute({"target_user_id": 456}, context)
    assert "未成功" in result


@pytest.mark.anyio
async def test_official_social_tools_reject_openids_without_onebot_fallback(platform):
    from webnet.ToolNet.tools.entertainment.qqlike import QQLike
    from webnet.ToolNet.tools.entertainment.send_poke import SendPoke

    onebot = SimpleNamespace(send_like=AsyncMock(), send_poke=AsyncMock())
    context = ToolContext(
        platform="qqofficial", platform_adapter=platform, onebot_client=onebot,
        user_id="USER_OPENID", group_id="GROUP_OPENID",
    )
    assert "暂不支持" in await QQLike().execute({}, context)
    assert "暂不支持" in await SendPoke().execute({}, context)
    onebot.send_like.assert_not_called()
    onebot.send_poke.assert_not_called()


@pytest.mark.anyio
async def test_onebot_social_methods_return_explicit_api_failures():
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    adapter = object.__new__(OneBotPlatform)
    adapter._call_onebot_api = AsyncMock(return_value={"_miya_status": "failed"})
    assert not await adapter.send_like(1)
    assert not await adapter.send_poke(1, 2)
    assert not await adapter.set_msg_emoji_like(3, "4")


@pytest.mark.anyio
async def test_scheduler_dispatch_uses_main_loop_and_never_falls_back_to_onebot():
    from hub.scheduler import Scheduler

    scheduler = Scheduler()
    main_loop = asyncio.get_running_loop()
    scheduler.main_event_loop = main_loop
    calls = []

    async def deliver(**kwargs):
        assert asyncio.get_running_loop() is main_loop
        calls.append(kwargs)
        return False

    scheduler.cross_platform_sender = deliver
    scheduler.onebot_client = SimpleNamespace(send_group_message=AsyncMock())
    data = {"target_type": "group", "target_id": "GROUP_OPENID", "platform": "qqofficial"}
    result = await asyncio.wait_for(asyncio.to_thread(
        lambda: asyncio.run(scheduler._send_scheduled_message(None, data, "reminder"))
    ), timeout=3)
    assert result is False
    assert calls[0]["target_id"] == "GROUP_OPENID"
    scheduler.cross_platform_sender = None
    assert not await scheduler._send_scheduled_message(None, data, "reminder")
    scheduler.onebot_client.send_group_message.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["group", "c2c"])
async def test_ai_tool_dispatch_creates_reminder_for_original_platform(monkeypatch, kind):
    from core import ai_client
    from webnet.ToolNet.subnet import SubnetConfig, ToolSubnet
    from webnet.ToolNet.tools.scheduler.create_schedule_task import CreateScheduleTaskTool

    scheduler = SimpleNamespace(schedule=MagicMock(), task_store=None)
    memory = SimpleNamespace(store_tide=MagicMock())
    runtime = {
        "platform": "qqofficial", "user_id": "canonical-user", "platform_user_id": "USER_OPENID",
        "group_id": "GROUP_OPENID" if kind == "group" else None, "message_type": kind,
        "scheduler": scheduler, "memory_engine": memory,
    }
    contexts = []

    async def execute(name, context, **args):
        contexts.append(context)
        return await CreateScheduleTaskTool().execute(args, context)

    # 惰性子网没有预先配置的组件，必须收到本次请求的运行时依赖。
    subnet = object.__new__(ToolSubnet)
    subnet.config = SubnetConfig(onebot_client=object())
    subnet.registry = SimpleNamespace(get_tool=lambda name: True, execute_tool=execute)
    monkeypatch.setattr(ai_client, "_get_toolnet_subnet", lambda: subnet)
    client = object.__new__(ai_client.BaseAIClient)
    result = await client._dispatch_tool_execution("create_schedule_task", {
        "task_type": "reminder", "message": "喝水", "schedule_time": "1分钟后",
    }, runtime)
    assert "✅" in result
    context = contexts[0]
    assert context.platform == "qqofficial" and context.onebot_client is None
    task = scheduler.schedule.call_args.args[0]
    assert task.data["platform"] == "qqofficial"
    assert task.data["target_id"] == ("GROUP_OPENID" if kind == "group" else "USER_OPENID")
    assert task.data["target_type"] == ("group" if kind == "group" else "private")


@pytest.mark.anyio
async def test_shared_ai_client_keeps_tool_context_per_request():
    from core.ai_client import BaseAIClient

    client = object.__new__(BaseAIClient)
    client.tool_context = None

    async def request(platform):
        client.set_tool_context({"platform": platform})
        await asyncio.sleep(0)
        return client.tool_context["platform"]

    assert await asyncio.gather(request("aiocqhttp"), request("qqofficial")) == ["aiocqhttp", "qqofficial"]
    assert client.tool_context is None


@pytest.mark.anyio
async def test_official_only_daemon_initializes_shared_scheduler(monkeypatch):
    from core.miya_daemon import MiyaDaemon

    daemon = object.__new__(MiyaDaemon)
    daemon._registry = SimpleNamespace(on_broadcast=MagicMock(), start=AsyncMock(return_value=True))
    scheduler = SimpleNamespace(start_background=MagicMock())
    hub = SimpleNamespace(_dispatch_proactive_message=AsyncMock())
    daemon._miya = SimpleNamespace(scheduler=scheduler, decision_hub=hub)
    monkeypatch.setattr("hub.scheduler.set_global_scheduler", MagicMock())
    await daemon._init_platforms(["qqofficial"])
    assert hub.platform_registry is daemon._registry
    assert scheduler.cross_platform_sender is hub._dispatch_proactive_message
    assert scheduler.main_event_loop is asyncio.get_running_loop()
    scheduler.start_background.assert_called_once()


def test_official_tool_context_never_inherits_another_platform_client(platform):
    from hub.decision_hub import DecisionHub

    hub = object.__new__(DecisionHub)
    hub.onebot_client = SimpleNamespace(platform_id="aiocqhttp")
    hub.platform_registry = SimpleNamespace(get=lambda name: platform if name == "qqofficial" else None)
    token = set_current_platform_adapter(hub.onebot_client)
    try:
        context = hub._platform_tool_context("qqofficial")
        assert context["platform_adapter"] is platform
        assert context["onebot_client"] is None
        assert context["send_like_callback"] is None
    finally:
        reset_current_platform_adapter(token)


def test_tool_adapter_fallback_rejects_a_different_platform():
    from webnet.ToolNet.base import resolve_platform_adapter
    from webnet.ToolNet.tools.message.send_platform_file import _resolve_platform_adapter

    token = set_current_platform_adapter(SimpleNamespace(platform_id="aiocqhttp"))
    try:
        context = ToolContext(platform="qqofficial")
        assert resolve_platform_adapter(context) is None
        assert _resolve_platform_adapter(context) is None
    finally:
        reset_current_platform_adapter(token)
