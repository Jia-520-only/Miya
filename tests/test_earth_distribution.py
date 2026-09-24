"""网盘分发中枢回归测试 (不联网)。

覆盖 v24 网盘分发中枢:
  * 合规闸门: 只有授权已核验且已进入可售资源库的资源能进资源包
  * 分发平台/投放位的登记边界 (拒绝保存密码、Cookie、登录态)
  * 按渠道物料生成 (模板、变体、去重) 与风险词自检
  * 审批边界: 审批箱绑定、批准回填、只有审批通过才能标记已发布
  * 转化数据回流: 真实收益自动汇入 income_records 与台账
  * 复盘: 漏斗、逐物料判定与合规检查
  * 巡检: 只落站内草稿, 绝不发布
"""

import os
import tempfile
from datetime import datetime

import pytest

from core.earth_online_store import EarthOnlineStore


def _build_store():
    temp_dir = tempfile.mkdtemp(prefix="earth_dist_")
    return EarthOnlineStore(db_path=os.path.join(temp_dir, "earthonline.db")), temp_dir


def _verified_resource(store, title="公版植物图鉴", license_type="public_domain"):
    resource = store.create_digital_resource({
        "title": title,
        "license_type": license_type,
        "source_url": f"https://example.org/{abs(hash(title)) % 10**8}",
        "source_name": "示例开放许可源",
        "rights_note": "公有领域, 可自由分发",
    })
    return store.update_digital_resource(resource["id"], {
        "rights_status": "verified", "status": "approved", "license_type": license_type,
    })


def _ready_package(store, title="公版植物图鉴合集", channel_id=None, keywords=None):
    resource = _verified_resource(store)
    package = store.create_dist_package({
        "title": title,
        "resource_ids": [resource["id"]],
        "channel_id": channel_id,
        "keywords": keywords or ["植物图鉴"],
        "cover_hint": "清爽绿色封面",
    })
    channel = store.get_dist_channel(channel_id) if channel_id else store.list_dist_channels()[0]
    store.bind_dist_share(package["id"], "https://pan.example.com/s/abc123", "8k2d", "共 12 份高清图")
    store.update_dist_package(package["id"], {"channel_id": channel["id"]})
    return store.get_dist_package(package["id"]), resource, channel


# ── 合规闸门 ────────────────────────────────────────


def test_unverified_resource_cannot_enter_ready_package():
    """授权未核验的资源不能进入可分发状态, 错误信息要说清原因。"""
    store, _ = _build_store()
    resource = store.create_digital_resource({
        "title": "来源不明的合集", "license_type": "unknown", "source_url": "https://example.org/x",
    })
    with pytest.raises(ValueError) as excinfo:
        store.create_dist_package({"title": "不该通过", "resource_ids": [resource["id"]], "status": "ready"})
    assert "授权未核验" in str(excinfo.value)

    package = store.create_dist_package({"title": "先当草稿", "resource_ids": [resource["id"]]})
    assert package["status"] == "draft"
    with pytest.raises(ValueError):
        store.update_dist_package(package["id"], {"status": "ready"})

    bind = store.bind_dist_share(package["id"], "https://pan.example.com/s/zzz")
    assert bind["success"] is True
    assert bind["package"]["status"] == "draft"
    assert "warning" in bind


def test_package_requires_at_least_one_resource_and_existing_ids():
    store, _ = _build_store()
    with pytest.raises(ValueError):
        store.create_dist_package({"title": "空包"})
    with pytest.raises(ValueError) as excinfo:
        store.create_dist_package({"title": "幽灵资源", "resource_ids": [999]})
    assert "不存在" in str(excinfo.value)


def test_share_link_must_be_public_http_url():
    store, _ = _build_store()
    package, _, _ = _ready_package(store)
    with pytest.raises(ValueError):
        store.bind_dist_share(package["id"], "file:///etc/passwd")


# ── 登记边界 ────────────────────────────────────────


def test_target_rejects_credentials():
    """投放位只记录账号标识, 绝不保存密码/Cookie/令牌。"""
    store, _ = _build_store()
    for label in ("小红书 密码:abc", "知乎 cookie=xyz", "B站 token:123"):
        with pytest.raises(ValueError):
            store.upsert_dist_target({"platform": "xiaohongshu", "account_label": label})
    target = store.upsert_dist_target({
        "platform": "xiaohongshu", "account_label": "小红书主号", "audience_note": "学生党",
    })
    assert target["platform"] == "xiaohongshu"
    # 同平台同账号幂等, 不产生重复投放位
    assert store.upsert_dist_target({"platform": "xiaohongshu", "account_label": "小红书主号"})["id"] == target["id"]
    assert len(store.list_dist_targets(platform="xiaohongshu")) == 1


def test_invalid_platform_is_rejected():
    store, _ = build_stub = _build_store()
    with pytest.raises(ValueError):
        store.upsert_dist_target({"platform": "tiktok", "account_label": "海外号"})


def test_default_channels_seed_is_idempotent():
    """配置里的分发平台在 store 构造时入库, 再次调用不重复也不覆盖已填链接。"""
    store, _ = _build_store()
    channels = store.list_dist_channels()
    assert {item["key"] for item in channels} >= {"quark", "xunlei", "uc"}
    assert all(item["kind"] for item in channels)

    quark = next(item for item in channels if item["key"] == "quark")
    store.upsert_dist_channel({"id": quark["id"], "promo_url": "https://pan.example.com/invite/quark"})
    again = store.ensure_distribution_defaults()
    assert again["created_channels"] == 0
    assert len(store.list_dist_channels()) == len(channels)
    quark = next(item for item in store.list_dist_channels() if item["key"] == "quark")
    assert quark["promo_url"] == "https://pan.example.com/invite/quark"


def test_channel_commission_note_round_trips_and_survives_edits():
    """佣金口径备注能被写入、被读取, 且编辑平台时不会被清空。"""
    store, _ = _build_store()
    channel = store.upsert_dist_channel({
        "name": "夸克网盘拉新", "key": "quark-test", "kind": "netdisk_cps",
        "promo_url": "https://pan.example.com/invite/quark",
        "promo_code": "QK123", "settlement_cycle": "T+1",
        "commission_note": "新用户首登 7 元 / 开通会员 30%",
    })
    assert channel["commission_rule"]["note"] == "新用户首登 7 元 / 开通会员 30%"

    # 只改结算周期, 佣金口径要保留
    updated = store.upsert_dist_channel({"id": channel["id"], "settlement_cycle": "月结"})
    assert updated["commission_rule"]["note"] == "新用户首登 7 元 / 开通会员 30%"
    assert updated["settlement_cycle"] == "月结"

    # 显式覆盖佣金口径
    replaced = store.upsert_dist_channel({"id": channel["id"], "commission_note": "单价以平台后台为准"})
    assert replaced["commission_rule"]["note"] == "单价以平台后台为准"

    # 显式传 commission_rule 时以它为准
    explicit = store.upsert_dist_channel({
        "id": channel["id"], "commission_rule": {"note": "结构化口径", "per_new_user": 7},
    })
    assert explicit["commission_rule"] == {"note": "结构化口径", "per_new_user": 7}


def test_channel_in_use_cannot_be_deleted():
    store, _ = _build_store()
    package, _, channel = _ready_package(store)
    with pytest.raises(ValueError):
        store.delete_dist_channel(channel["id"])
    store.update_dist_package(package["id"], {"channel_id": None})
    assert store.delete_dist_channel(channel["id"]) is True


# ── 物料生成 ────────────────────────────────────────


def test_generate_materials_per_channel_and_dedupe():
    """按投放位生成物料, 变体数量正确, 重复生成只跳过不重复插入。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "xiaohongshu", "account_label": "小红书主号"})
    store.upsert_dist_target({"platform": "bilibili", "account_label": "B站主号"})
    package, _, _ = _ready_package(store)

    first = store.generate_dist_materials(package["id"], variants=2)
    assert first["created_count"] == 4
    assert {item["platform"] for item in first["created"]} == {"xiaohongshu", "bilibili"}
    assert {item["variant"] for item in first["created"]} == {1, 2}
    material = first["created"][0]
    assert material["status"] == "draft"
    assert "公版植物图鉴合集" in material["title"]
    assert material["tags"] and material["cta"]

    second = store.generate_dist_materials(package["id"], variants=2)
    assert second["created_count"] == 0
    assert second["skipped_count"] == 4
    assert len(store.list_dist_materials(package_id=package["id"])) == 4


def test_generate_requires_target_and_shares_template_variables():
    store, _ = _build_store()
    package, _, _ = _ready_package(store)
    with pytest.raises(ValueError) as excinfo:
        store.generate_dist_materials(package["id"])
    assert "投放位" in str(excinfo.value)

    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号", "audience_note": "职场新人"})
    created = store.generate_dist_materials(package["id"])
    material = created["created"][0]
    assert "职场新人" in material["body"]
    assert "公版植物图鉴" in material["body"]  # 资源清单来自真实资源标题


def test_material_risk_flags_are_detected():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]
    assert material["risk_flags"] == []

    updated = store.update_dist_material(material["id"], {
        "body": "全网最全的资料，私信我加微信领取，含破解版与付费课搬运。",
    })
    assert "疑似诱导私下联系" in updated["risk_flags"]
    assert "疑似夸大承诺" in updated["risk_flags"]
    assert "疑似侵权资源" in updated["risk_flags"]


def test_package_with_unverified_resource_cannot_generate_materials():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    resource = store.create_digital_resource({"title": "来源不明", "license_type": "unknown"})
    package = store.create_dist_package({"title": "草稿包", "resource_ids": [resource["id"]]})
    with pytest.raises(ValueError) as excinfo:
        store.generate_dist_materials(package["id"])
    assert "授权未核验" in str(excinfo.value)


# ── 审批边界 ────────────────────────────────────────


def test_promote_requires_share_or_promo_entry():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, channel = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]

    # 拿掉分享链接且平台没有推广链接 → 拒绝提交
    store.update_dist_package(package["id"], {"share_url": ""})
    with pytest.raises(ValueError) as excinfo:
        store.promote_dist_material(material["id"])
    assert "承接入口" in str(excinfo.value)

    # 平台补上推广链接即可
    store.upsert_dist_channel({"id": channel["id"], "promo_url": "https://pan.example.com/invite/quark"})
    promoted = store.promote_dist_material(material["id"])
    assert promoted["material"]["status"] == "submitted"
    assert promoted["action"]["action_type"] == "publish"
    assert promoted["action"]["status"] == "pending"
    assert "https://pan.example.com/invite/quark" in promoted["action"]["content"]


def test_approval_flow_backfills_material_status():
    """批准后物料变为 approved, 撤销或过期则退回 draft。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    materials = store.generate_dist_materials(package["id"], variants=3)["created"]

    approved = store.promote_dist_material(materials[0]["id"])
    revoked = store.promote_dist_material(materials[1]["id"])
    store.promote_dist_material(materials[2]["id"])

    store.approve_earning_action(int(approved["action"]["id"]), approved["action"]["content_hash"])
    store.revoke_earning_action(int(revoked["action"]["id"]))

    summary = store.sync_dist_material_actions()
    assert summary["approved"] == 1
    assert summary["returned"] == 1
    assert store.get_dist_material(materials[0]["id"])["status"] == "approved"
    assert store.get_dist_material(materials[1]["id"])["status"] == "draft"
    # 仍在审批中的物料保持 submitted, 不会被误判
    assert store.get_dist_material(materials[2]["id"])["status"] == "submitted"


def test_publish_requires_approval_and_marks_package_published():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]

    with pytest.raises(ValueError) as excinfo:
        store.mark_dist_material_published(material["id"], "https://www.zhihu.com/p/1")
    assert "审批" in str(excinfo.value)

    promoted = store.promote_dist_material(material["id"])
    store.approve_earning_action(int(promoted["action"]["id"]), promoted["action"]["content_hash"])
    store.sync_dist_material_actions()
    published = store.mark_dist_material_published(material["id"], "https://www.zhihu.com/p/1")
    assert published["material"]["status"] == "published"
    assert published["material"]["published_url"] == "https://www.zhihu.com/p/1"
    assert store.get_dist_package(package["id"])["status"] == "published"
    # 已发布物料不再被审批过期流程拉回草稿
    store.sync_dist_material_actions()
    assert store.get_dist_material(material["id"])["status"] == "published"


def test_material_in_approval_cannot_be_edited():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]
    store.promote_dist_material(material["id"])
    with pytest.raises(ValueError):
        store.update_dist_material(material["id"], {"body": "改一下"})


# ── 转化回流与复盘 ──────────────────────────────────


def test_record_metrics_rolls_revenue_into_income_records():
    """有佣金时自动汇入现实收益流水与地球币台账; 没有佣金时不写收入。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]
    today = datetime.now().date().isoformat()

    empty = store.record_dist_metrics({
        "package_id": package["id"], "material_id": material["id"], "stat_date": today,
        "impressions": 300, "clicks": 10,
    })
    assert empty["income_record_id"] is None
    assert store.list_income_records() == []

    paid = store.record_dist_metrics({
        "package_id": package["id"], "material_id": material["id"], "stat_date": today,
        "impressions": 900, "clicks": 50, "saves": 8, "transfers": 15,
        "new_users": 3, "vip_orders": 1, "revenue": 45.5, "cost": 5.5, "note": "平台后台截图",
    })
    assert paid["income_record_id"]
    records = store.list_income_records()
    assert len(records) == 1
    assert records[0]["amount"] == 45.5
    assert records[0]["cost"] == 5.5
    ledger = store.list_currency_ledger(limit=10, currency="earth")
    assert any(abs(float(row["delta"]) - 40.0) < 1e-6 for row in ledger)


def test_metrics_require_package_or_material():
    store, _ = _build_store()
    with pytest.raises(ValueError):
        store.record_dist_metrics({"impressions": 10})


def test_distribution_report_funnel_and_verdicts():
    """漏斗比率正确, 逐物料给出加码/停投/样本不足判定与合规提示。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    store.upsert_dist_target({"platform": "tieba", "account_label": "贴吧主号"})
    package, _, _ = _ready_package(store)
    materials = store.generate_dist_materials(package["id"])["created"]
    by_platform = {item["platform"]: item for item in materials}
    today = datetime.now().date().isoformat()

    store.record_dist_metrics({
        "material_id": by_platform["zhihu"]["id"], "stat_date": today,
        "impressions": 1000, "clicks": 50, "transfers": 20, "new_users": 4,
        "vip_orders": 1, "revenue": 60.0, "cost": 10.0,
    })
    store.record_dist_metrics({
        "material_id": by_platform["tieba"]["id"], "stat_date": today,
        "impressions": 800, "clicks": 40, "revenue": 0.0,
    })

    report = store.distribution_report(days=30)
    funnel = report["funnel"]
    assert funnel["impressions"] == 1800
    assert funnel["clicks"] == 90
    assert funnel["ctr"] == 5.0
    assert funnel["revenue"] == 60.0
    assert funnel["net"] == 50.0
    assert funnel["revenue_per_1k"] == pytest.approx(33.33, abs=0.01)

    verdicts = {item["platform"]: item["verdict"] for item in report["materials"]}
    assert verdicts["zhihu"] == "加码"
    assert verdicts["tieba"] == "停投"
    assert report["counts"]["metric_rows"] == 2
    assert report["compliance"]
    assert report["boundary"]


def test_distribution_report_marks_insufficient_sample():
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)
    material = store.generate_dist_materials(package["id"])["created"][0]
    store.record_dist_metrics({
        "material_id": material["id"], "stat_date": datetime.now().date().isoformat(),
        "impressions": 5, "clicks": 1,
    })
    report = store.distribution_report(days=30)
    assert report["materials"][0]["verdict"] == "样本不足"


# ── 巡检 ────────────────────────────────────────────


def test_distribution_cycle_only_produces_drafts_and_pending_approvals():
    """巡检只为可分发资源包生成草稿并提交审批, 绝不产生已发布物料。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    package, _, _ = _ready_package(store)

    cycle = store.run_distribution_cycle()
    assert cycle["success"] is True
    assert cycle["created_materials"] >= 1
    assert cycle["submitted"] >= 1
    statuses = {item["status"] for item in store.list_dist_materials()}
    assert statuses <= {"draft", "submitted"}
    assert "published" not in statuses


def test_distribution_cycle_is_disabled_by_switch(monkeypatch):
    store, _ = _build_store()
    store._cfg = lambda *path, default=None, **kwargs: (
        False if path[:2] == ("distribution", "enabled") else default
    )
    result = store.run_distribution_cycle()
    assert result.get("skipped") == "disabled"


def test_earning_automation_cycle_runs_distribution_without_external_actions():
    """收益巡检包含分发环节, 且仍然不创建任何外部动作。"""
    store, _ = _build_store()
    store.upsert_dist_target({"platform": "zhihu", "account_label": "知乎主号"})
    _ready_package(store)
    store.sync_earning_sources = lambda *args, **kwargs: {"success": True, "created_count": 0, "skipped": 0, "errors": []}
    store.scout_digital_resources = lambda *args, **kwargs: {
        "success": True, "created_count": 0, "skipped": "throttled", "errors": [],
    }

    result = store.run_earning_automation_cycle()
    assert "distribution" in result
    assert result["distribution"]["created_materials"] >= 1
    # 巡检把物料放进审批箱, 但自己不发布
    materials = store.list_dist_materials()
    assert materials and all(item["status"] in {"draft", "submitted"} for item in materials)
    assert all(item["status"] != "published" for item in materials)


def test_netdisk_route_is_offered_in_earning_routes():
    store, _ = _build_store()
    routes = {item["key"]: item for item in store.earning_routes()}
    assert "netdisk_share" in routes
    route = routes["netdisk_share"]
    assert route["steps"]
    assert route["fit_score"] >= 0


# ── 工具层接线 ──────────────────────────────────────


DISTRIBUTION_TOOLS = {
    "earth_distribution_report",
    "earth_list_dist_channels",
    "earth_upsert_dist_channel",
    "earth_list_dist_targets",
    "earth_upsert_dist_target",
    "earth_list_dist_packages",
    "earth_create_dist_package",
    "earth_bind_dist_share",
    "earth_list_dist_materials",
    "earth_generate_dist_materials",
    "earth_promote_dist_material",
    "earth_mark_dist_material_published",
    "earth_record_dist_metrics",
    "earth_run_distribution_cycle",
}


def test_distribution_tools_registered_in_both_layers():
    """决策中枢 schema 与 ToolNet 注册表必须严格对齐 (地球online 的既有约定)。"""
    from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

    import webnet.ToolNet.tools.earth_online as toolnet_earth

    schema_names = {item["function"]["name"] for item in EARTH_TOOLS_SCHEMA}
    toolnet_names = {tool.config["name"] for tool in toolnet_earth.get_earth_online_tools()}
    assert DISTRIBUTION_TOOLS <= schema_names
    assert DISTRIBUTION_TOOLS <= toolnet_names
    assert schema_names == toolnet_names


@pytest.mark.parametrize("platform", ["qq", "aiocqhttp", "lark", "mobile", "terminal", "desktop", "web"])
def test_distribution_tools_exposed_to_all_platform_tools(platform):
    """弥娅在任何平台上都能读分发复盘、组装资源包、生成并提交投放物料。"""
    from hub.platform_tools import PlatformToolsManager

    class _Subnet:
        def get_tools_schema(self):
            return [{"type": "function", "function": {"name": name}} for name in DISTRIBUTION_TOOLS]

    names = {
        schema["function"]["name"]
        for schema in PlatformToolsManager(_Subnet()).get_platform_specific_tools(platform)
    }
    assert DISTRIBUTION_TOOLS <= names


def test_distribution_tools_registered_in_gestalt_builtin_tools():
    """Gestalt 回退执行路径也必须认识这 14 个工具 (与 v18/v21/v23 的既有做法一致)。"""
    from core.gestalt_enhanced import get_gestalt_controller_enhanced
    from core.tools_astrbot import ToolRegistry

    ToolRegistry()
    builtin = get_gestalt_controller_enhanced()._builtin_tools
    assert DISTRIBUTION_TOOLS <= set(builtin)
    for name in DISTRIBUTION_TOOLS:
        assert callable(builtin[name])
