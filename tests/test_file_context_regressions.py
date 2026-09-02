"""统一文件上下文的格式识别与出站校验回归测试。"""

from pathlib import Path

import pytest

from core.file_context import FileContext, FileType, OutboundFile, guess_mime_type
from core.platform_context import AppPlatformBridge
from core.unified_platform_impl.qq_official_platform import QQOfficialPlatform
from webnet.ToolNet.file_categories import classify


@pytest.mark.parametrize(
    ("filename", "mime"),
    [
        ("photo.avif", "image/avif"),
        ("voice.m4a", "audio/mp4"),
        ("clip.mts", "video/mp2t"),
        ("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("slides.odp", "application/vnd.oasis.opendocument.presentation"),
        ("backup.bz2", "application/x-bzip2"),
        ("installer.apk", "application/vnd.android.package-archive"),
        ("script.py", "text/x-python"),
    ],
)
def test_common_file_types_have_stable_mime(filename, mime):
    assert guess_mime_type(filename) == mime
    assert OutboundFile._guess_mime(filename) == mime


def test_pdf_is_document_not_text():
    assert FileContext._detect_type("report.pdf") == FileType.DOCUMENT


def test_outbound_file_rejects_directories(tmp_path):
    directory = Path(tmp_path) / "not-a-file"
    directory.mkdir()
    with pytest.raises(FileNotFoundError):
        OutboundFile.from_local(str(directory))


@pytest.mark.parametrize(
    ("filename", "file_type"),
    [("photo.png", 1), ("clip.mp4", 2), ("voice.silk", 3), ("voice.m4a", None), ("archive.zip", None)],
)
def test_qq_official_supported_media_types(filename, file_type):
    assert QQOfficialPlatform._qq_official_file_type(filename) == file_type


def test_typescript_mime_and_file_type_are_consistent():
    assert guess_mime_type("app.ts") == "text/typescript"
    assert FileContext._detect_type("app.ts") == FileType.CODE
    assert classify("app.ts") == "code"


@pytest.mark.anyio
async def test_app_platform_stages_only_basename(tmp_path, monkeypatch):
    bridge = AppPlatformBridge("test")
    monkeypatch.setattr(bridge, "_web_files_dir", Path(tmp_path))

    assert await bridge.send_file(file_data=b"ok", file_name="..\\outside.txt")
    assert (Path(tmp_path) / "outside.txt").read_bytes() == b"ok"
    assert not (Path(tmp_path).parent / "outside.txt").exists()
