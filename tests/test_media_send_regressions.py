"""媒体下载/发送链路回归测试。"""

from pathlib import Path

import pytest

from webnet.ToolNet.tools.basic.download_file import _default_ua
from webnet.ToolNet.tools.message import send_platform_file
from webnet.ToolNet.base import ToolContext


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


@pytest.mark.anyio
async def test_send_platform_file_normalizes_null_arguments():
    result = await send_platform_file.SendPlatformFileTool().execute(
        {"file_path": None, "file_name": None, "caption": None}, ToolContext()
    )
    assert "请提供文件路径" in result
