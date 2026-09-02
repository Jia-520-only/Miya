"""资源搜索与下载工具的边界回归测试。"""

import pytest

from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.tools.basic import resource_find
from webnet.ToolNet.tools.basic.download_file import DownloadFileTool, _as_bool, _validate_url


def test_download_url_and_boolean_normalization():
    assert _validate_url("file:///tmp/a.png")
    assert _validate_url("not-a-url")
    assert _validate_url("https://example.com/a.png") is None
    assert _as_bool("false") is False
    assert _as_bool("0") is False
    assert _as_bool("true") is True


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
