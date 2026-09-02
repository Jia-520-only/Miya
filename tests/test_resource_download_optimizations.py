"""资源搜索与下载工具的边界回归测试。"""

import pytest

from core.ai_client import OpenAIClient
from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.tools.basic import resource_find
from webnet.ToolNet.tools.basic.download_file import (
    DownloadFileTool,
    _as_bool,
    _extract_filename,
    _filename_from_content_disposition,
    _normalize_url as _normalize_download_url,
    _validate_url,
)


def test_download_url_and_boolean_normalization():
    assert _validate_url("file:///tmp/a.png")
    assert _validate_url("not-a-url")
    assert _validate_url("https://example.com/a.png") is None
    assert _as_bool("false") is False
    assert _as_bool("0") is False
    assert _as_bool("true") is True


def test_escaped_search_urls_are_normalized_and_deduplicated():
    escaped = r"https:\u002F\u002Fdown.gameloop.com\u002Fapp\u002Fmiya.apk\\"
    assert resource_find._normalize_url(escaped) == "https://down.gameloop.com/app/miya.apk"
    assert _normalize_download_url(escaped) == "https://down.gameloop.com/app/miya.apk"

    html = (
        '<script>"downloadUrl":"https:\\u002F\\u002Fdown.gameloop.com\\u002Fapp\\u002Fmiya.apk"</script>'
        '<a href="https://down.gameloop.com/app/miya.apk\\">duplicate</a>'
    )
    assert resource_find._extract_urls(html, resource_find._get_extractors("apk")) == [
        "https://down.gameloop.com/app/miya.apk"
    ]


def test_download_uses_server_filename_and_apk_mime_type():
    assert _filename_from_content_disposition("attachment; filename*=UTF-8''tomato%20latest.apk") == (
        "tomato latest.apk"
    )
    assert _filename_from_content_disposition('attachment; filename="tomato.apk"') == "tomato.apk"
    assert _extract_filename(
        "https://gdown.baidu.com/appcenter/pkg/upload/id", "application/vnd.android.package-archive"
    ) == "downloaded.apk"


@pytest.mark.anyio
async def test_resource_search_returns_clean_direct_apk_links(monkeypatch):
    async def fake_search(*args, **kwargs):
        return [{"title": "search", "url": "https://search.example/result", "source": "bing_cn"}]

    async def fake_crawl(url):
        return (
            '<script>"downloadUrl":"https:\\u002F\\u002Fgdown.baidu.com\\u002Fapp\\u002Fpkg?id=1"</script>'
            '<a href="https://down.gameloop.com/app/miya.apk\\">apk</a>'
        )

    monkeypatch.setattr(resource_find, "_smart_web_search", fake_search)
    monkeypatch.setattr(resource_find, "_crawl_page", fake_crawl)
    result = await resource_find.ResourceFindTool().execute(
        {"query": "番茄小说", "resource_type": "apk", "count": 5}, ToolContext()
    )

    assert "https://gdown.baidu.com/app/pkg?id=1" in result
    assert "https://down.gameloop.com/app/miya.apk" in result
    assert r"\u002F" not in result
    assert "miya.apk\\" not in result


def test_resource_download_tools_remain_composable():
    """搜索/下载必须把结果交回模型，才能继续完成发送链路。"""
    direct = set(OpenAIClient._direct_return_tools)
    assert "resource_find" not in direct
    assert "download_file" not in direct
    assert "video_download" not in direct
    assert "jmcomic_download" not in direct
    assert "python_interpreter" not in direct
    assert "send_platform_file" in direct


@pytest.mark.anyio
async def test_download_rejects_non_http_without_network():
    result = await DownloadFileTool().execute({"url": "file:///tmp/a.txt"}, ToolContext())
    assert "仅支持 http/https" in result


@pytest.mark.anyio
async def test_site_search_skips_broad_search(monkeypatch):
    called = False

    async def fail_broad(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("site search must not call broad search")

    async def fake_booru(query, count, site):
        return [{"title": "demo", "url": "https://example.com/a.jpg", "source": site}]

    monkeypatch.setattr(resource_find, "_smart_web_search", fail_broad)
    monkeypatch.setattr(resource_find, "_booru_search", fake_booru)

    result = await resource_find.ResourceFindTool().execute(
        {"query": "bianca", "resource_type": "image", "site": "gelbooru", "count": "2"},
        ToolContext(),
    )

    assert called is False
    assert "example.com/a.jpg" in result
