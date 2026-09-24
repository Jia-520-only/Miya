"""开放许可资源发现器回归测试 (不联网)。

覆盖:
  * 授权判定的确定性规则 (CC0/公域/开放许可/非商业/素材库/未知)
  * 自动核验只发生在可确定性判定的许可上
  * 去重、每日上限、开关
  * 巡检集成与所有平台的工具白名单
"""

import os
import tempfile

import pytest

from core.earth_online_resource_scout import (
    classify_candidate,
    normalise_scout_config,
    scout_open_resources,
)
from core.earth_online_store import EarthOnlineStore


def _build_store():
    temp_dir = tempfile.mkdtemp(prefix="earth_scout_")
    return EarthOnlineStore(db_path=os.path.join(temp_dir, "earthonline.db")), temp_dir


def _candidate(**overrides):
    title = str(overrides.get("title") or "Vintage Botanical Plate")
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    payload = {
        "title": title,
        "source_url": f"https://commons.example.org/wiki/{slug}",
        "landing_url": f"https://commons.example.org/wiki/{slug}",
        "source_name": "Openverse/example",
        "license_text": "cc0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "content_uri": f"https://cdn.example.org/{slug}.jpg",
        "creator": "Someone",
    }
    payload.update(overrides)
    return payload


def _fetcher(*candidates):
    def _search(_query, _limit):
        return [dict(item) for item in candidates]

    return _search


def _config(**overrides):
    payload = {
        "enabled": True,
        "auto_verify": True,
        "max_per_cycle": 5,
        "daily_cap": 20,
        "per_query": 5,
        "providers": ["openverse"],
        "queries": {"openverse": ["plants"]},
    }
    payload.update(overrides)
    return normalise_scout_config(payload)


@pytest.mark.parametrize(
    "license_text,verdict,license_type",
    [
        ("cc0 1.0", "auto_verified", "public_domain"),
        ("CC0", "auto_verified", "public_domain"),
        ("Public Domain Mark 1.0", "auto_verified", "public_domain"),
        ("public domain", "auto_verified", "public_domain"),
        ("PDM", "auto_verified", "public_domain"),
        ("no known copyright restrictions", "auto_verified", "public_domain"),
        ("CC BY 4.0", "manual", "open_license"),
        ("CC BY-SA 4.0", "manual", "open_license"),
        ("CC BY-ND 4.0", "manual", "open_license"),
        ("CC BY-NC 4.0", "blocked", "unknown"),
        ("CC BY-NC-SA 4.0", "blocked", "unknown"),
        ("All rights reserved", "blocked", "unknown"),
        ("", "skipped", "unknown"),
        ("some custom license", "skipped", "unknown"),
    ],
)
def test_license_classification_is_deterministic(license_text, verdict, license_type):
    decision = classify_candidate(_candidate(license_text=license_text))
    assert decision["verdict"] == verdict
    assert decision["license_type"] == license_type


@pytest.mark.parametrize(
    "url",
    [
        "https://unsplash.com/photos/abc",
        "https://images.pexels.com/photos/1/x.jpg",
        "https://pixabay.com/illustrations/abc-123/",
        "https://www.shutterstock.com/image-photo/abc-123",
        "https://www.pinterest.com/pin/123/",
    ],
)
def test_stock_photo_libraries_are_blocked_even_with_open_license_text(url):
    """免版税素材库即使标着 CC0 也不能原样转售。"""
    decision = classify_candidate(_candidate(source_url=url, landing_url=url, license_text="cc0"))
    assert decision["verdict"] == "blocked"
    assert decision["reason"]


def test_scout_auto_verifies_only_deterministic_licenses():
    store, _ = _build_store()
    fetchers = {
        "openverse": _fetcher(
            _candidate(title="CC0 Plate", license_text="cc0 1.0"),
            _candidate(title="BY Plate", license_text="CC BY 4.0"),
            _candidate(title="NC Plate", license_text="CC BY-NC 4.0"),
            _candidate(title="Unsplash Plate", source_url="https://unsplash.com/photos/x", landing_url="https://unsplash.com/photos/x"),
            _candidate(title="Mystery Plate", license_text="handshake license"),
        )
    }
    result = scout_open_resources(
        store, config=_config(), fetchers=fetchers, respect_limits=False
    )

    assert result["created_count"] == 2
    assert result["auto_verified_count"] == 1
    assert result["pending_count"] == 1
    assert result["blocked_count"] == 2  # NC + Unsplash
    assert result["skipped_license_count"] == 1  # 未知许可不入库

    resources = {item["title"]: item for item in store.list_digital_resources()}
    assert resources["CC0 Plate"]["rights_status"] == "verified"
    assert resources["CC0 Plate"]["status"] == "approved"
    assert resources["CC0 Plate"]["license_type"] == "public_domain"
    assert "公有领域" in resources["CC0 Plate"]["rights_note"]

    assert resources["BY Plate"]["rights_status"] == "pending"
    assert resources["BY Plate"]["status"] == "candidate"
    assert "署名" in resources["BY Plate"]["rights_note"]
    assert "Unsplash Plate" not in resources
    assert "NC Plate" not in resources

    # 自动核验后即可用于数字商品，说明资源真的进了可售资源库
    product = store.create_digital_product({
        "title": "公版植物图谱素材包",
        "description": "一整包 CC0 植物插画",
        "resource_ids": [resources["CC0 Plate"]["id"]],
        "price": 9.9,
    })
    assert product["status"] == "draft"


def test_scout_skips_duplicates_and_respects_daily_cap():
    store, _ = _build_store()
    fetchers = {"openverse": _fetcher(_candidate(title="CC0 Plate", license_text="cc0"))}
    config = _config(max_per_cycle=5, daily_cap=1)

    first = scout_open_resources(store, config=config, fetchers=fetchers)
    assert first["created_count"] == 1
    assert first["auto_verified_count"] == 1

    second = scout_open_resources(store, config=config, fetchers=fetchers)
    assert second["skipped"] == "daily_cap"
    assert second["created_count"] == 0
    assert len(store.list_digital_resources()) == 1

    unlimited = scout_open_resources(store, config=config, fetchers={"openverse": _fetcher(
        _candidate(title="Another Plate")
    )}, respect_limits=False)
    # 手动调用不受每日上限约束，但标题/来源去重依然生效
    assert unlimited["created_count"] == 1
    assert len(store.list_digital_resources()) == 2


def test_scout_is_idempotent_for_the_same_source():
    store, _ = _build_store()
    fetchers = {"openverse": _fetcher(_candidate(license_text="cc0"))}
    config = _config()

    scout_open_resources(store, config=config, fetchers=fetchers)
    again = scout_open_resources(store, config=config, fetchers=fetchers)
    assert again["created_count"] == 0
    assert again["skipped_duplicate_count"] == 1
    assert len(store.list_digital_resources()) == 1


def test_scout_respects_master_switch():
    store, _ = _build_store()
    result = scout_open_resources(
        store,
        config=_config(enabled=False),
        fetchers={"openverse": _fetcher(_candidate())},
    )
    assert result["skipped"] == "disabled"
    assert store.list_digital_resources() == []


OPDS_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dcterms="http://purl.org/dc/terms/">
  <entry>
    <id>https://www.gutenberg.org/ebooks/subjects/search.opds/?query=fairy+tales</id>
    <title>Subjects</title>
    <content type="text">64 subject headings match your search.</content>
  </entry>
  <entry>
    <id>https://www.gutenberg.org/ebooks/2591.opds</id>
    <title>Grimms' Fairy Tales</title>
    <content type="text">Jacob Grimm and Wilhelm Grimm</content>
  </entry>
  <entry>
    <id>https://www.gutenberg.org/ebooks/11.opds</id>
    <title>Alice's Adventures in Wonderland</title>
    <content type="text">Carroll, Lewis</content>
  </entry>
  <entry>
    <id>https://www.gutenberg.org/ebooks/51252.opds</id>
    <title>The Book of the Thousand Nights and a Night — Volume 01</title>
    <content type="text">39907 downloads</content>
  </entry>
</feed>
"""


def test_gutenberg_opds_parser_skips_navigation_and_auto_verifies(monkeypatch):
    """官方 OPDS 检索里的导航条目没有书号，必须被跳过；书条目是公版。(不联网)"""
    import core.earth_online_resource_scout as scout

    monkeypatch.setattr(
        scout, "_fetch_public_bytes",
        lambda url, accept, timeout=20: OPDS_FIXTURE.encode("utf-8"),
    )
    items = scout._search_gutenberg("fairy tales", 5)

    assert [item["title"] for item in items] == [
        "Grimms' Fairy Tales",
        "Alice's Adventures in Wonderland",
        "The Book of the Thousand Nights and a Night — Volume 01",
    ]
    first = items[0]
    assert first["source_url"] == "https://www.gutenberg.org/ebooks/2591"
    assert first["content_uri"] == "https://www.gutenberg.org/ebooks/2591.epub3.images"
    assert first["creator"] == "Jacob Grimm and Wilhelm Grimm"
    assert scout.classify_candidate(first)["verdict"] == "auto_verified"
    # 统计行不能当成作者名写进授权说明
    assert items[2]["creator"] == ""


def test_scout_refuses_hosts_outside_the_builtin_providers():
    """即使有人改了调用参数，也不可能让发现器去抓任意主机。"""
    import core.earth_online_resource_scout as scout

    with pytest.raises(ValueError, match="非内置数据源"):
        scout._fetch_public_bytes("https://evil.example.com/steal", "application/json")


def test_unknown_provider_is_reported_not_crashed():
    store, _ = _build_store()
    result = scout_open_resources(store, provider="not_a_source", config=_config())
    assert result["success"] is False
    assert result["skipped"] == "unknown_provider"


def test_scout_survives_a_failing_provider():
    store, _ = _build_store()

    def _boom(_query, _limit):
        raise RuntimeError("上游 503")

    result = scout_open_resources(
        store,
        config=_config(providers=["openverse", "gutenberg"]),
        fetchers={"openverse": _boom, "gutenberg": _fetcher(_candidate(license_text="public domain"))},
    )
    assert result["created_count"] == 1
    assert result["errors"] and result["errors"][0]["provider"] == "openverse"


def test_scout_config_drops_unknown_providers():
    config = normalise_scout_config({"providers": ["openverse", "wat"], "max_per_cycle": 999})
    assert config["providers"] == ["openverse"]
    assert config["dropped_providers"] == ["wat"]
    assert config["max_per_cycle"] == 20  # 上限收敛


def test_automation_cycle_stitches_the_scout_in():
    """巡检结果里必须带资源发现器这一环，且只做站内入库。"""
    store, _ = _build_store()
    stub = {
        "success": True, "enabled": True, "created": [{"id": 1, "title": "CC0 Plate", "status": "approved", "rights_status": "verified", "license_type": "public_domain"}],
        "created_count": 1, "auto_verified_count": 1, "pending_count": 0,
        "blocked": [], "blocked_count": 0, "skipped_duplicate_count": 0,
        "skipped_license_count": 0, "errors": [], "providers": {}, "scope": "", "daily_used": 0, "daily_cap": 12,
    }
    store.scout_digital_resources = lambda *args, **kwargs: dict(stub)

    result = store.run_earning_automation_cycle()

    assert result["resource_scout"]["created_count"] == 1
    assert any("资源发现器补充 1 条" in action for action in result["actions"])
    # 巡检仍然不产生任何外部动作
    assert result["guidance"]["action_drafts"] == []


@pytest.mark.parametrize("platform", ["qq", "aiocqhttp", "lark", "mobile", "terminal", "desktop", "web"])
def test_digital_workshop_tools_are_exposed_to_all_platform_tools(platform):
    """弥娅在任何平台都能整理资源、发现资源、准备商品草稿 (v21/v23)。"""
    from hub.platform_tools import PlatformToolsManager

    expected = {
        "earth_list_digital_resources",
        "earth_scout_digital_resources",
        "earth_add_digital_resource",
        "earth_create_digital_product",
        "earth_prepare_xianyu_listing",
    }

    class _Subnet:
        def get_tools_schema(self):
            return [{"type": "function", "function": {"name": name}} for name in expected]

    names = {
        schema["function"]["name"]
        for schema in PlatformToolsManager(_Subnet()).get_platform_specific_tools(platform)
    }
    assert expected <= names


def test_scout_tool_is_registered_in_both_tool_layers():
    """决策中枢 schema 与 ToolNet 注册表必须严格对齐 (地球online 的既有约定)。"""
    from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

    import webnet.ToolNet.tools.earth_online as toolnet_earth

    schema_names = {item["function"]["name"] for item in EARTH_TOOLS_SCHEMA}
    toolnet_names = {tool.config["name"] for tool in toolnet_earth.get_earth_online_tools()}
    assert "earth_scout_digital_resources" in schema_names
    assert schema_names == toolnet_names
