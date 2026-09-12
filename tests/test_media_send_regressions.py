"""媒体下载/发送链路回归测试。"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from webnet.ToolNet.tools.basic.download_file import _default_ua
from webnet.ToolNet.tools.message import send_platform_file
from webnet.ToolNet.base import ToolContext


def _load_media_platform_types():
    """按需加载媒体适配器，避免可选 AI 依赖阻塞基础回归测试收集。"""
    try:
        from core.file_context import OutboundFile
        from core.unified_platform.base import BasePlatform
        from core.unified_platform.status import PlatformStatus
        from core.unified_platform_impl.webhook_platforms import LarkPlatform
        from core.unified_platform_impl.weixin_ilink_platform import WeixinIlinkPlatform

        return OutboundFile, BasePlatform, PlatformStatus, LarkPlatform, WeixinIlinkPlatform
    except ModuleNotFoundError as exc:
        pytest.skip(f"媒体适配器可选依赖未安装: {exc.name}")


def test_file_send_size_limits_default_to_unlimited(tmp_path):
    """应用侧发送配置使用 0 表示不预限制文件字节数。"""
    project_root = Path(__file__).resolve().parents[1]
    constants = json.loads((project_root / "config" / "system_constants.json").read_text(encoding="utf-8"))
    assert constants["qq"]["image_max_size"] == 0
    assert constants["qq"]["file_max_size"] == 0

    from webnet.qq.config_loader import QQConfigLoader

    fallback = QQConfigLoader(config_path=str(tmp_path / "missing_qq_config.yaml"))._get_default_config()
    multimedia = fallback["qq"]["multimedia"]
    assert multimedia["image"]["max_size"] == 0
    assert multimedia["file"]["max_size"] == 0


def test_download_has_runtime_user_agent():
    assert _default_ua().startswith("Mozilla/5.0")


def test_data_file_lookup_recurses_into_image_directory(tmp_path, monkeypatch):
    nested = tmp_path / "downloads" / "image"
    nested.mkdir(parents=True)
    target = nested / "kafka_01.jpg"
    target.write_bytes(b"image")
    monkeypatch.setattr(send_platform_file, "_DATA_ROOT", tmp_path)
    monkeypatch.setattr(send_platform_file, "_DATA_SEARCH_DIRS", ["downloads"])

    resolved = send_platform_file._resolve_local_path("kafka_01.jpg")
    assert resolved == str(target.resolve())


def test_list_data_files_rejects_path_escape(monkeypatch):
    monkeypatch.setattr(send_platform_file, "_DATA_ROOT", Path("D:/MiyaFactory/Miya/data"))
    assert not send_platform_file._valid_data_directory("../")
    assert send_platform_file._valid_data_directory("downloads/image")


def test_target_resolution_uses_group_id_for_group_messages():
    context = ToolContext(user_id=123, group_id=456, platform_user_id="user-native")
    assert send_platform_file._resolve_target(context, "group") == "456"
    assert send_platform_file._resolve_target(context, "private") == "user-native"


def test_group_target_never_falls_back_to_sender_id():
    context = ToolContext(user_id=123, platform_user_id="user-native")
    assert send_platform_file._resolve_target(context, "group") == ""


def test_onebot_file_reference_log_summary_hides_base64():
    pytest.importorskip("numpy")
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    summary = OneBotPlatform._summarize_file_ref("base64://" + "A" * 120)
    assert "base64://<" in summary
    assert "AAAA" not in summary
    assert "编码120字符" in summary


def test_ai_tool_dispatch_preserves_group_context():
    source = Path(__file__).resolve().parents[1] / "core" / "ai_client.py"
    text = source.read_text(encoding="utf-8")
    dispatch = text[text.index("async def _dispatch_tool_execution"):]
    assert "group_id=context.get(\"group_id\")" in dispatch
    assert "message_type=context.get(\"message_type\")" in dispatch
    assert "platform_user_id=context.get(\"platform_user_id\")" in dispatch


@pytest.mark.anyio
async def test_send_platform_file_normalizes_null_arguments():
    result = await send_platform_file.SendPlatformFileTool().execute(
        {"file_path": None, "file_name": None, "caption": None}, ToolContext()
    )
    assert "请提供文件路径" in result


@pytest.mark.anyio
async def test_send_platform_file_serializes_same_adapter(tmp_path):
    class FakePlatform:
        supports_file_send = True
        last_file_url = ""

        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def send_file(self, **kwargs):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return True

    platform = FakePlatform()
    files = []
    for i in range(3):
        path = Path(tmp_path) / f"image_{i}.png"
        path.write_bytes(b"image")
        files.append(path)

    context = ToolContext(user_id=1, platform_user_id="user", platform_adapter=platform)
    results = await asyncio.gather(
        *(send_platform_file.SendPlatformFileTool().execute({"file_path": str(path)}, context) for path in files)
    )

    assert all("已发送" in result for result in results)
    assert platform.max_active == 1


@pytest.mark.anyio
async def test_onebot_file_waits_for_echo_and_rejects_rich_media_failure(tmp_path):
    pytest.importorskip("numpy")
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    class FakeWS:
        async def send_str(self, payload):
            return None

    path = Path(tmp_path) / "note.txt"
    path.write_bytes(b"hello")
    platform = OneBotPlatform.__new__(OneBotPlatform)
    platform._ws = FakeWS()
    platform._connected = True
    platform._file_send_lock = asyncio.Lock()
    platform._get_onebot_file_transport = lambda: "base64"
    platform._get_onebot_file_ref = lambda _path: _async_value("base64://aGVsbG8=")
    platform._is_image_file = lambda _path: False
    platform._record_message_out = lambda: None
    platform._call_onebot_api = lambda *args, **kwargs: _async_value(
        {"_miya_status": "failed", "response": {"status": "failed"}}
    )

    assert not await platform._send_onebot_file_inner(str(path), "note.txt", "", "group", "456")


@pytest.mark.anyio
async def test_onebot_file_falls_back_to_base64_after_path_failure(tmp_path):
    pytest.importorskip("numpy")
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    path = Path(tmp_path) / "note.txt"
    path.write_bytes(b"hello")
    platform = OneBotPlatform.__new__(OneBotPlatform)
    platform._ws = object()
    platform._connected = True
    platform._file_send_lock = asyncio.Lock()
    platform._get_onebot_file_transport = lambda: "file"
    platform._get_onebot_file_ref = lambda _path: _async_value("file:///container-missing/note.txt")
    platform._is_image_file = lambda _path: False
    platform._record_message_out = lambda: None
    calls = []

    async def call_api(_action, params, **_kwargs):
        calls.append(params)
        if len(calls) == 1:
            return {"_miya_status": "failed"}
        return {"message_id": 42}

    platform._call_onebot_api = call_api

    assert await platform._send_onebot_file_inner(str(path), "note.txt", "", "group", "456")
    assert len(calls) == 2
    assert calls[0]["message"][0]["data"]["file"].startswith("file://")
    assert calls[1]["message"][0]["data"]["file"].startswith("base64://")


async def _async_value(value):
    return value


@pytest.mark.anyio
async def test_degraded_platform_can_still_attempt_http_file_send():
    _, BasePlatform, PlatformStatus, _, _ = _load_media_platform_types()

    class FakePlatform(BasePlatform):
        platform_id = "http-platform"
        platform_name = "HTTP platform"

        def __init__(self):
            super().__init__()
            self.sent = False

        async def _do_connect(self):
            return True

        async def _do_disconnect(self):
            return None

        async def _do_health_check(self):
            return False

        async def _do_send_file(self, target, outbound_file, **kwargs):
            self.sent = True
            return True

    platform = FakePlatform()
    platform._set_status(PlatformStatus.DEGRADED)

    assert await platform.send_file(target="user", file_data=b"ok", file_name="note.txt")
    assert platform.sent


class _LarkResponse:
    code = 0
    msg = ""

    def __init__(self, **data):
        self.data = SimpleNamespace(**data)

    def success(self):
        return True


class _LarkEndpoint:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def acreate(self, request):
        self.calls.append(request)
        return self.response


def _fake_lark_client():
    image = _LarkEndpoint(_LarkResponse(image_key="img-key"))
    file = _LarkEndpoint(_LarkResponse(file_key="file-key"))
    message = _LarkEndpoint(_LarkResponse())
    client = SimpleNamespace(im=SimpleNamespace(v1=SimpleNamespace(image=image, file=file, message=message)))
    return client, image, file, message


def _patch_lark_client(monkeypatch, client):
    import lark_oapi as lark

    class Builder:
        def app_id(self, _value):
            return self

        def app_secret(self, _value):
            return self

        def build(self):
            return client

    monkeypatch.setattr(lark.Client, "builder", staticmethod(Builder))


@pytest.mark.anyio
async def test_lark_health_uses_its_long_connection_client():
    _, _, _, LarkPlatform, _ = _load_media_platform_types()

    platform = LarkPlatform({"app_id": "app", "app_secret": "secret"})
    assert not await platform._do_health_check()
    platform._ws_client = object()
    assert await platform._do_health_check()


@pytest.mark.anyio
async def test_lark_uses_image_api_group_target_and_separate_caption(monkeypatch):
    OutboundFile, _, _, LarkPlatform, _ = _load_media_platform_types()

    client, image, file, message = _fake_lark_client()
    _patch_lark_client(monkeypatch, client)
    platform = LarkPlatform({"app_id": "app", "app_secret": "secret"})
    outbound = OutboundFile.from_bytes(b"png", filename="photo.png", caption="图片说明")

    assert await platform._do_send_file("chat-id", outbound, message_type="group")
    assert len(image.calls) == 1
    assert not file.calls
    assert len(message.calls) == 2

    media_request, caption_request = message.calls
    assert media_request.receive_id_type == "chat_id"
    assert media_request.request_body.receive_id == "chat-id"
    assert media_request.request_body.msg_type == "image"
    assert json.loads(media_request.request_body.content) == {"image_key": "img-key"}
    assert caption_request.receive_id_type == "chat_id"
    assert caption_request.request_body.msg_type == "text"
    assert json.loads(caption_request.request_body.content) == {"text": "图片说明"}


@pytest.mark.anyio
async def test_lark_uses_file_api_for_arbitrary_private_files(monkeypatch):
    OutboundFile, _, _, LarkPlatform, _ = _load_media_platform_types()

    client, image, file, message = _fake_lark_client()
    _patch_lark_client(monkeypatch, client)
    platform = LarkPlatform({"app_id": "app", "app_secret": "secret"})
    monkeypatch.setattr(platform, "_resolve_lark_peer", lambda _target: "mapped-user")
    outbound = OutboundFile.from_bytes(b"zip", filename="archive.zip")

    assert await platform._do_send_file("canonical-user", outbound, message_type="private")
    assert not image.calls
    assert len(file.calls) == 1
    assert file.calls[0].request_body.file_type == "stream"
    assert len(message.calls) == 1
    request = message.calls[0]
    assert request.receive_id_type == "user_id"
    assert request.request_body.receive_id == "mapped-user"
    assert request.request_body.msg_type == "file"
    assert json.loads(request.request_body.content) == {"file_key": "file-key"}


@pytest.mark.anyio
async def test_weixin_media_transport_uses_configured_large_upload_timeout():
    _, _, _, _, WeixinIlinkPlatform = _load_media_platform_types()

    platform = WeixinIlinkPlatform(
        {
            "media_upload_timeout": 180,
            "media_upload_attempts": 4,
            "media_max_mb": 64,
        }
    )
    transport = platform._create_ilink_transport()
    try:
        assert transport.api_timeout_seconds == 180
        assert platform._media_upload_attempts == 4
        assert platform._media_max_bytes == 64 * 1024 * 1024
    finally:
        await transport.aclose()
