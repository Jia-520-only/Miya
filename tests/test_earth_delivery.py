"""M2 自建限时交付回归测试 (不联网)。

覆盖:
  * content_uri 解析与交付区边界 (.. 逃逸 / 区外绝对路径 / 符号链接)
  * 准备交付文件 (下载到本地交付区并改写 content_uri，幂等)
  * 令牌校验 / 过期 / 配额 (浏览不消耗、下载才消耗)
  * 公开交付页、单文件下载、打包下载、限流、总开关
"""

import os
import tempfile

import pytest

from core.earth_online_store import EarthOnlineStore
from core.web_api.earth_online import EarthOnlineRoutes, _DeliveryRateLimiter


def _build_store():
    temp_dir = tempfile.mkdtemp(prefix="earth_delivery_")
    return EarthOnlineStore(db_path=os.path.join(temp_dir, "earthonline.db")), temp_dir


def _delivery_settings(**overrides):
    settings = {
        "enabled": True,
        "allow_external_redirect": True,
        "max_file_mb": 200,
        "zip_max_mb": 500,
        "rate_limit_per_minute": 30,
        "base_url": "",
    }
    settings.update(overrides)
    return settings


def _paid_order_with_resource(store, *, content_uri="", numbers=1):
    """建一个已确认收款、可直接签发交付令牌的订单。"""
    resources = []
    for index in range(numbers):
        resources.append(store.create_digital_resource({
            "title": f"可交付资源 {index + 1}",
            "license_type": "original",
            "rights_status": "verified",
            "status": "approved",
            "content_uri": content_uri,
        }))
    product = store.create_digital_product({
        "title": "公版素材包", "description": "说明",
        "resource_ids": [item["id"] for item in resources],
        "price": 9.9, "status": "ready",
    })
    order = store.create_digital_order({"product_id": product["id"], "amount": 9.9})
    store.confirm_digital_order_payment(order["id"], f"确认订单 #{order['id']} 已收款")
    return order, resources


def _write_delivery_file(store, name, payload=b"hello miya"):
    os.makedirs(store.delivery_dir, exist_ok=True)
    path = os.path.join(store.delivery_dir, name)
    with open(path, "wb") as handle:
        handle.write(payload)
    return path


def _client(store, monkeypatch, **settings):
    """只挂地球online 路由的测试客户端 (不触碰真实存档)。"""
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(store, "delivery_settings", lambda: _delivery_settings(**settings))

    routes = EarthOnlineRoutes.__new__(EarthOnlineRoutes)
    routes.web_net = None
    routes.decision_hub = None
    routes.store = store
    routes._delivery_limiter = _DeliveryRateLimiter()
    routes.router = APIRouter(prefix="/api/earth")
    routes._setup_routes()
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


# ── 交付区边界 ─────────────────────────────────────────


def test_delivery_only_serves_files_inside_the_delivery_area():
    store, _ = _build_store()
    inside = _write_delivery_file(store, "r1-book.epub")
    outside_dir = tempfile.mkdtemp(prefix="earth_outside_")
    outside = os.path.join(outside_dir, "secret.txt")
    with open(outside, "w", encoding="utf-8") as handle:
        handle.write("不该被交付")

    ok = store.resolve_delivery_target({"content_uri": "delivery://r1-book.epub"})
    assert ok["kind"] == "file" and ok["path"] == os.path.realpath(inside)
    assert ok["size"] == len(b"hello miya")

    traversal = store.resolve_delivery_target({"content_uri": "delivery://../secret.txt"})
    assert traversal["kind"] == "missing"

    absolute_outside = store.resolve_delivery_target({"content_uri": outside})
    assert absolute_outside["kind"] == "missing"

    relative_without_scheme = store.resolve_delivery_target({"content_uri": "r1-book.epub"})
    assert relative_without_scheme["kind"] == "missing"

    external = store.resolve_delivery_target({"content_uri": "https://example.test/book.epub"})
    assert external["kind"] == "url" and external["href"].endswith("book.epub")
    assert external["filename"] == "book.epub"

    assert store.resolve_delivery_target({"content_uri": ""})["kind"] == "missing"


def test_symlink_escaping_the_delivery_area_is_rejected():
    store, _ = _build_store()
    os.makedirs(store.delivery_dir, exist_ok=True)
    outside_dir = tempfile.mkdtemp(prefix="earth_outside_")
    outside = os.path.join(outside_dir, "secret.txt")
    with open(outside, "w", encoding="utf-8") as handle:
        handle.write("不该被交付")
    link = os.path.join(store.delivery_dir, "shortcut.txt")
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("当前环境不支持创建符号链接")

    assert store.resolve_delivery_target({"content_uri": "delivery://shortcut.txt"})["kind"] == "missing"


# ── 准备交付文件 ───────────────────────────────────────


def test_stage_delivery_file_downloads_and_rewrites_content_uri(monkeypatch):
    store, _ = _build_store()
    resource = store.create_digital_resource({
        "title": "公版书", "license_type": "public_domain", "rights_status": "verified",
        "status": "approved", "content_uri": "https://www.gutenberg.org/ebooks/11.epub3.images",
    })

    def _fake_download(url, destination, *, max_bytes=0, timeout=60):
        assert url.endswith("11.epub3.images")
        with open(destination, "wb") as handle:
            handle.write(b"EPUB-PAYLOAD")
        return {"path": destination, "bytes": len(b"EPUB-PAYLOAD"), "sha256": "deadbeef"}

    monkeypatch.setattr(EarthOnlineStore, "download_public_file", staticmethod(_fake_download))

    first = store.stage_delivery_file(resource["id"])
    assert first["staged"] is True
    assert first["resource"]["content_uri"].startswith("delivery://r")
    assert first["resource"]["checksum"] == "deadbeef"
    assert first["manifest"]["kind"] == "file" and first["manifest"]["size"] == len(b"EPUB-PAYLOAD")

    # 幂等：已在交付区就不再重新下载
    again = store.stage_delivery_file(resource["id"])
    assert again["staged"] is False
    assert "已在本地交付区" in again["message"]


def test_stage_delivery_file_requires_verified_resource():
    store, _ = _build_store()
    candidate = store.create_digital_resource({"title": "候选", "content_uri": "https://example.test/a.zip"})
    with pytest.raises(ValueError):
        store.stage_delivery_file(candidate["id"])
    with pytest.raises(ValueError):
        store.stage_delivery_file(9999)


# ── 配额语义 ───────────────────────────────────────────


def test_browsing_does_not_consume_quota_but_download_does():
    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub")
    order, resources = _paid_order_with_resource(store)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    delivery = store.issue_digital_delivery(order["id"], expires_hours=1, max_downloads=2)

    for _ in range(3):
        inspected = store.inspect_digital_delivery(delivery["token"])
        assert inspected["success"] is True
        assert inspected["remaining_downloads"] == 2
        assert inspected["manifest"][0]["kind"] == "file"

    claimed = store.claim_digital_download(delivery["token"])
    assert claimed["success"] is True and claimed["remaining_downloads"] == 1
    exhausted = store.claim_digital_download(delivery["token"])
    assert exhausted["success"] is True and exhausted["remaining_downloads"] == 0
    assert store.claim_digital_download(delivery["token"])["success"] is False


def test_issue_returns_a_copyable_delivery_link(monkeypatch):
    store, _ = _build_store()
    monkeypatch.setattr(store, "delivery_settings", lambda: _delivery_settings(base_url="https://miya.example.com"))
    order, _resources = _paid_order_with_resource(store)
    delivery = store.issue_digital_delivery(order["id"])
    assert delivery["delivery_path"].startswith("/api/earth/d/")
    assert delivery["delivery_url"] == "https://miya.example.com" + delivery["delivery_path"]

    monkeypatch.setattr(store, "delivery_settings", lambda: _delivery_settings())
    assert store.issue_digital_delivery(order["id"])["delivery_url"].startswith("/api/earth/d/")


def test_expired_and_revoked_tokens_are_refused():
    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub")
    order, resources = _paid_order_with_resource(store)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    delivery = store.issue_digital_delivery(order["id"])

    assert store.inspect_digital_delivery("not-a-token")["success"] is False
    store.revoke_digital_delivery(delivery["delivery_id"])
    assert store.inspect_digital_delivery(delivery["token"])["success"] is False

    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect(store.db_path)
    conn.execute(
        "UPDATE earning_digital_deliveries SET status='active', expires_at=? WHERE id=?",
        ((datetime.now() - timedelta(minutes=1)).isoformat(), int(delivery["delivery_id"])),
    )
    conn.commit()
    conn.close()
    expired = store.inspect_digital_delivery(delivery["token"])
    assert expired["success"] is False and "过期" in expired["message"]


def test_delivery_pauses_when_resource_authorization_changes():
    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub")
    order, resources = _paid_order_with_resource(store)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    delivery = store.issue_digital_delivery(order["id"])

    store.update_digital_resource(resources[0]["id"], {"status": "paused"})
    paused = store.inspect_digital_delivery(delivery["token"])
    assert paused["success"] is False and "授权" in paused["message"]


# ── 公开交付页 ─────────────────────────────────────────


def test_public_delivery_page_lists_files_and_serves_them(monkeypatch):
    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub", b"EPUB-BYTES")
    order, resources = _paid_order_with_resource(store)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    delivery = store.issue_digital_delivery(order["id"], max_downloads=5)
    client = _client(store, monkeypatch)

    page = client.get(f"/api/earth/d/{delivery['token']}")
    assert page.status_code == 200
    assert "公版素材包" in page.text
    assert "r1-book.epub" not in page.text  # 页面上不暴露本地文件名
    assert f"/api/earth/d/{delivery['token']}/f/{resources[0]['id']}" in page.text

    download = client.get(f"/api/earth/d/{delivery['token']}/f/{resources[0]['id']}")
    assert download.status_code == 200
    assert download.content == b"EPUB-BYTES"

    # 页面浏览不消耗，实际下载消耗一次
    assert store.inspect_digital_delivery(delivery["token"])["remaining_downloads"] == 4

    from fastapi import HTTPException
    bad = client.get(f"/api/earth/d/{delivery['token']}/f/999999")
    assert bad.status_code == 404
    assert HTTPException is not None


def test_public_delivery_zip_bundles_local_files(monkeypatch):
    import io
    import zipfile

    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub", b"ONE")
    _write_delivery_file(store, "r2-book.epub", b"TWO")
    order, resources = _paid_order_with_resource(store, numbers=2)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    store.update_digital_resource(resources[1]["id"], {"content_uri": "delivery://r2-book.epub"})
    delivery = store.issue_digital_delivery(order["id"], max_downloads=5)
    client = _client(store, monkeypatch)

    page = client.get(f"/api/earth/d/{delivery['token']}")
    assert "打包下载全部" in page.text

    response = client.get(f"/api/earth/d/{delivery['token']}/zip")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == ["r1-book.epub", "r2-book.epub"]
    assert archive.read("r1-book.epub") == b"ONE"
    assert store.inspect_digital_delivery(delivery["token"])["remaining_downloads"] == 4


def test_public_delivery_zip_refuses_when_nothing_is_local(monkeypatch):
    store, _ = _build_store()
    order, _resources = _paid_order_with_resource(store, content_uri="https://example.test/book.epub")
    delivery = store.issue_digital_delivery(order["id"])
    client = _client(store, monkeypatch)
    assert client.get(f"/api/earth/d/{delivery['token']}/zip").status_code == 409


def test_external_resource_redirects_and_can_be_switched_off(monkeypatch):
    store, _ = _build_store()
    order, resources = _paid_order_with_resource(store, content_uri="https://example.test/book.epub")
    delivery = store.issue_digital_delivery(order["id"], max_downloads=5)

    allowing = _client(store, monkeypatch, allow_external_redirect=True)
    redirected = allowing.get(f"/api/earth/d/{delivery['token']}/f/{resources[0]['id']}", follow_redirects=False)
    assert redirected.status_code == 302
    assert redirected.headers["location"] == "https://example.test/book.epub"

    blocking = _client(store, monkeypatch, allow_external_redirect=False)
    assert blocking.get(f"/api/earth/d/{delivery['token']}/f/{resources[0]['id']}").status_code == 409


def test_public_delivery_respects_master_switch_and_rate_limit(monkeypatch):
    store, _ = _build_store()
    _write_delivery_file(store, "r1-book.epub")
    order, resources = _paid_order_with_resource(store)
    store.update_digital_resource(resources[0]["id"], {"content_uri": "delivery://r1-book.epub"})
    delivery = store.issue_digital_delivery(order["id"])

    disabled = _client(store, monkeypatch, enabled=False)
    assert disabled.get(f"/api/earth/d/{delivery['token']}").status_code == 404

    limited = _client(store, monkeypatch, rate_limit_per_minute=2)
    assert limited.get(f"/api/earth/d/{delivery['token']}").status_code == 200
    assert limited.get(f"/api/earth/d/{delivery['token']}").status_code == 200
    assert limited.get(f"/api/earth/d/{delivery['token']}").status_code == 429


def test_delivery_tool_schema_is_registered_everywhere():
    from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

    import webnet.ToolNet.tools.earth_online as toolnet_earth

    schema_names = {item["function"]["name"] for item in EARTH_TOOLS_SCHEMA}
    toolnet_names = {tool.config["name"] for tool in toolnet_earth.get_earth_online_tools()}
    assert "earth_stage_delivery_file" in schema_names
    assert schema_names == toolnet_names
