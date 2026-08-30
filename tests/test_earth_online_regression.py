import json
import os
import tempfile

from core.earth_online_store import EarthOnlineStore


def _build_store():
    temp_dir = tempfile.mkdtemp(prefix="earthonline_regression_")
    db_path = os.path.join(temp_dir, "earthonline.db")
    return EarthOnlineStore(db_path=db_path), temp_dir


def test_life_hub_exposes_reality_and_operator_status():
    store, temp_dir = _build_store()
    os.makedirs(store.data_dir, exist_ok=True)
    with open(os.path.join(store.data_dir, "operator_state.json"), "w", encoding="utf-8") as state_file:
        json.dump({
            "last_cycle_at": "2026-08-26T20:05:32",
            "cycles": 8,
            "last_cycle_actions": 3,
            "last_cycle_skip": False,
            "last_notification_sent": True,
        }, state_file)

    hub = store.get_life_hub()

    assert hub["boundary"]
    assert hub["facts"]["real_context"]["source_status"]
    assert isinstance(hub["facts"]["real_context"]["precise_location_saved"], bool)
    assert hub["facts"]["operator"]["last_cycle_at"] == "2026-08-26T20:05:32"
    assert hub["facts"]["operator"]["last_actions"] == 3
    assert hub["facts"]["operator"]["next_cycle_at"]


def test_reward_and_weekly_report_propagate_values():
    store, _ = _build_store()

    before = store.get_player()
    quest = store.create_quest(
        title="完成周报任务",
        description="测试奖励发放链路",
        quest_type="daily",
        reward_currency=10,
        reward_exp=25,
    )

    result = store.complete_quest(quest["id"])
    assert result["success"] is True

    player = store.get_player()
    assert player["miya_currency"] >= before.get("miya_currency", 0) + 10
    assert player["exp"] >= before.get("exp", 0) + 25

    report = store.get_weekly_report()
    assert report["quests"]["completed"] >= 1
    assert report["earned"]["currency"] >= 10
    assert report["earned"]["exp"] >= 25


def test_import_json_restores_history_and_totals():
    store, _ = _build_store()

    payload = {
        "player": {
            "name": "玩家A",
            "title": "地球online 玩家",
            "avatar_path": "",
            "bio": "测试玩家",
            "attrs": [{"key": "focus", "value": 80, "max": 100}],
            "exp": 320,
            "miya_currency": 77,
            "earth_currency": 999,
            "total_completed": 3,
            "total_failed": 1,
            "equipped_title": "启程者",
        },
        "items": [
            {
                "id": 1,
                "name": "键盘",
                "category": "digital",
                "rarity": "rare",
                "quantity": 1,
                "description": "测试道具",
                "image_path": "",
                "status": "normal",
                "markdown": "",
                "fields": {"brand": "Logitech"},
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            }
        ],
        "quests": [
            {
                "id": 101,
                "title": "测试任务",
                "description": "已导入",
                "quest_type": "main",
                "must_complete": True,
                "status": "pending",
                "reward_currency": 5,
                "reward_exp": 10,
                "penalty_currency": 2,
                "deadline": "2025-01-05T00:00:00",
                "source": "manual",
                "difficulty": 3,
                "fields": {"subject": "测试"},
                "subtasks": [{"text": "做完", "done": 0}],
                "recurring": "",
                "created_at": "2025-01-01T00:00:00",
                "completed_at": "",
                "updated_at": "2025-01-01T00:00:00",
            }
        ],
        "quest_history": [
            {
                "id": 1,
                "quest_id": 101,
                "title": "测试任务",
                "status": "completed",
                "reward_currency": 5,
                "reward_exp": 10,
                "penalty_currency": 0,
                "completed_at": "2025-01-02T09:00:00",
            }
        ],
        "characters": [
            {
                "id": 1,
                "name": "佳",
                "nickname": "宝",
                "relationship": "partner",
                "affinity": 92,
                "avatar_path": "",
                "notes": "测试角色",
                "birthday": "",
                "markdown": "",
                "fields": {"anniversary": "2025-01-01"},
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            }
        ],
        "stories": [
            {
                "id": 1,
                "title": "故事",
                "content": "测试剧情",
                "event_type": "life",
                "character_id": 1,
                "item_id": 1,
                "happened_at": "2025-01-03T00:00:00",
                "fields": {},
                "image_path": "",
                "created_at": "2025-01-03T00:00:00",
            }
        ],
        "affinity_logs": [
            {
                "id": 1,
                "character_id": 1,
                "delta": 4,
                "reason": "陪伴",
                "created_at": "2025-01-03T00:00:00",
            }
        ],
        "achievements": [
            {
                "id": 1,
                "key": "first_quest",
                "title": "初次启程",
                "description": "完成第一个任务",
                "icon": "⚔",
                "category": "quest",
                "target": 1,
                "progress": 1,
                "hidden": 0,
                "unlocked_at": "2025-01-03T00:00:00",
                "reward_currency": 30,
                "reward_exp": 50,
                "title_award": "启程者",
                "created_at": "2025-01-01T00:00:00",
            }
        ],
        "checkins": [
            {
                "id": 1,
                "date": "2025-01-04",
                "reward_currency": 12,
                "reward_exp": 18,
                "streak": 3,
                "created_at": "2025-01-04T00:00:00",
            }
        ],
        "miya_notes": [
            {"id": 1, "content": "测试寄语", "mood": "happy", "pinned": 1, "created_at": "2025-01-03T00:00:00"}
        ],
        "activity": [
            {
                "id": 1,
                "kind": "quest",
                "icon": "✦",
                "summary": "导入后测试",
                "detail": "奖励 +5 弥娅币 · +10 经验",
                "quest_id": 101,
                "comment": "",
                "created_at": "2025-01-04T00:00:00",
            }
        ],
        "templates": {"items": {"digital": {"label": "数码产品", "fields": []}}, "quests": []},
    }

    result = store.import_json(payload)
    assert result["success"] is True

    player = store.get_player()
    assert player["name"] == "玩家A"
    assert player["miya_currency"] == 77
    assert player["earth_currency"] == 999
    assert player["total_completed"] == 3
    assert player["total_failed"] == 1

    assert store.quest_history(limit=10)[0]["title"] == "测试任务"
    assert store.list_characters()[0]["affinity"] == 92
    assert store.list_notes(limit=10)[0]["content"] == "测试寄语"
    assert store.list_activity(limit=10)[0]["summary"] == "导入后测试"


def test_closed_tasks_reject_status_transitions():
    store, _ = _build_store()

    quest = store.create_quest(title="已完成任务", reward_currency=3, reward_exp=4)
    finished = store.complete_quest(quest["id"])
    assert finished["success"] is True

    assert store.cancel_quest(quest["id"])["success"] is False
    assert store.fail_quest(quest["id"])["success"] is False

    reopened = store.create_quest(title="新任务", reward_currency=1, reward_exp=2)
    assert store.cancel_quest(reopened["id"])["success"] is True
    assert store.fail_quest(reopened["id"])["success"] is False


def test_currency_and_exp_reject_invalid_negative_mutations():
    store, _ = _build_store()
    player = store.get_player()

    try:
        store.add_exp(-1)
        raise AssertionError("negative exp must be rejected")
    except ValueError:
        pass

    try:
        store.add_miya_currency(-(player["miya_currency"] + 1))
        raise AssertionError("currency must not go negative")
    except ValueError:
        pass

    spent = store.spend_miya_coins(0, "invalid")
    assert spent["success"] is False
    assert store.get_player()["miya_currency"] == player["miya_currency"]


def test_new_save_starts_with_miya_currency_and_world_regions():
    store, _ = _build_store()

    player = store.get_player()
    assert player["miya_currency"] == 100
    assert player["earth_currency"] == 0

    regions = store.list_world_regions()
    assert len(regions) == 5
    assert all(r["discovery_total"] == 0 for r in regions)

    result = store.explore_world_region("miya_garden")
    assert result["success"] is True
    assert result["discovery"]["region_key"] == "miya_garden"
    assert result["discovery"]["reward_currency"] > 0
    assert len(store.list_world_discoveries("miya_garden")) == 1


def test_world_region_level_gate_and_completion():
    store, _ = _build_store()

    locked = store.explore_world_region("starfall_ridge")
    assert locked["success"] is False
    assert locked["level_req"] == 5

    for _ in range(5):
        result = store.explore_world_region("miya_garden")
        assert result["success"] is True
    complete = store.explore_world_region("miya_garden")
    assert complete["success"] is True
    assert complete["complete"] is True
    assert complete["discovery"] is None


def test_world_status_and_region_commission_are_daily_unique():
    store, _ = _build_store()

    status = store.get_world_status()
    assert status["date"]
    assert status["weather"]
    assert any(area["key"] == "summer_signal_2026" for area in status["event_areas"])

    first = store.create_region_commission("miya_garden")
    second = store.create_region_commission("miya_garden")
    assert first["success"] is True
    assert first["created"] is True
    assert second["success"] is True
    assert second["created"] is False
    assert second["quest"]["id"] == first["quest"]["id"]


def test_real_context_never_fakes_weather_and_persists_snapshot():
    store, _ = _build_store()

    settings = store.update_real_context_settings({"city": ""})
    assert settings["city"] == ""
    context = store.refresh_real_context()
    assert context["source_status"] in {"needs_location", "not_configured", "error", "ok"}
    if context["source_status"] != "ok":
        assert context["weather"] == "未同步"

    result = store.explore_world_region("miya_garden")
    assert result["success"] is True
    discovery = store.list_world_discoveries("miya_garden")[0]
    assert "context_snapshot" in discovery


def test_custom_world_events_are_editable_and_enter_exploration_pool():
    store, _ = _build_store()
    event = store.create_world_custom_event("miya_garden", "窗边的新光", "今天真实记录的一束光。", 3, 4, "hidden")
    assert event and event["region_key"] == "miya_garden"
    assert store.list_world_regions()[0]["event_total"] == 6
    assert store.update_world_region("miya_garden", {"subtitle": "现实照片中的起点"})["subtitle"] == "现实照片中的起点"
    assert store.delete_world_custom_event(event["id"]) is True


def test_active_event_shop_consumes_miya_currency_and_archives_item():
    store, _ = _build_store()
    before = store.get_player()["miya_currency"]
    shop = store.list_world_event_shop("summer_signal_2026")
    assert shop["active"] is True
    result = store.purchase_world_event_item("summer_signal_2026", "signal_postcard")
    assert result["success"] is True
    assert store.get_player()["miya_currency"] == before - 18
    assert store.list_items()[0]["name"] == "夏末信号明信片"
    duplicate = store.purchase_world_event_item("summer_signal_2026", "signal_postcard")
    assert duplicate["success"] is False


def test_exploration_returns_companion_dialogue():
    store, _ = _build_store()
    result = store.explore_world_region("miya_garden")
    assert result["success"] is True
    assert result["discovery"]["companion"]["speaker"] == "弥娅"
    assert result["discovery"]["companion"]["text"]


# ── v13: 地理围栏 / 属性联动 / 改写券 / 好感解锁 / 自定义活动 ──


def test_geofence_blocks_and_allows_exploration():
    store, _ = _build_store()
    store.update_world_region("miya_garden", {"latitude": 31.2304, "longitude": 121.4737, "geofence_radius": 500})

    blocked = store.explore_world_region("miya_garden")
    assert blocked["success"] is False
    assert "围栏" in blocked["geofence"]["message"] or "定位" in blocked["geofence"]["message"]

    far = store.explore_world_region("miya_garden", latitude=39.9042, longitude=116.4074)
    assert far["success"] is False and far["geofence"]["passed"] is False

    near = store.explore_world_region("miya_garden", latitude=31.2310, longitude=121.4740)
    assert near["success"] is True and near["geofence"]["passed"] is True


def test_quest_completion_and_checkin_move_player_attrs():
    store, _ = _build_store()
    attrs_before = {a["key"]: a["value"] for a in store.get_player()["attrs"]}
    quest = store.create_quest(title="消耗体力测试", difficulty=3, reward_currency=1, reward_exp=1)
    result = store.complete_quest(quest["id"])
    assert result["success"] is True
    attrs_after = {a["key"]: a["value"] for a in store.get_player()["attrs"]}
    assert attrs_after["energy"] == attrs_before["energy"] - 12
    assert attrs_after["mood"] == min(100, attrs_before["mood"] + 3)

    checkin = store.checkin()
    assert checkin["success"] is True
    attrs_final = {a["key"]: a["value"] for a in store.get_player()["attrs"]}
    assert attrs_final["energy"] == min(100, attrs_after["energy"] + 15)


def test_commission_rewrite_boost_is_consumed():
    store, _ = _build_store()
    purchased = store.purchase_miya_shop_item("miya_reality_pass")
    assert purchased["success"] is True
    assert any((i.get("fields") or {}).get("boost") == "commission_resonance" for i in store.list_items())

    result = store.create_region_commission("miya_garden")
    assert result["success"] is True and result["created"] is True
    assert result["boost_applied"] is True
    assert result["quest"]["fields"]["boosted"] == 1
    # 改写券已被消耗
    assert not any((i.get("fields") or {}).get("boost") == "commission_resonance" for i in store.list_items())
    second = store.create_region_commission("city_lumen")
    assert second["boost_applied"] is False


def test_affinity_tier_up_unlocks_reward():
    store, _ = _build_store()
    character = store.create_character(name="老朋友", relationship="friend", affinity=19)
    before = store.get_player()["miya_currency"]
    result = store.add_affinity(character["id"], 2, "一起吃了个饭")
    assert result["affinity"] == 21
    assert result["tier_up"]["new_tier"] == 2
    assert result["tier_up"]["label"] == "相识"
    assert store.get_player()["miya_currency"] == before + result["tier_up"]["reward_currency"]


def test_custom_event_areas_and_shop_items_flow():
    store, _ = _build_store()
    area = store.create_world_event_area({
        "key": "autumn_test_2026", "name": "秋夜测试祭", "start": "2026-08-01", "end": "2026-12-31",
    })
    assert area and area["name"] == "秋夜测试祭"
    assert any(a["key"] == "autumn_test_2026" and a["is_custom"] for a in store.list_world_event_areas())
    assert any(a["key"] == "autumn_test_2026" for a in store.get_world_status()["event_areas"])

    item = store.create_world_event_shop_item("autumn_test_2026", {"key": "test_badge", "name": "测试徽章", "cost": 5})
    assert item and item["limit_count"] == 1
    shop = store.list_world_event_shop("autumn_test_2026")
    assert shop["active"] is True
    assert any(entry["key"] == "test_badge" and entry["is_custom"] for entry in shop["items"])

    assert store.update_world_event_area("autumn_test_2026", {"active": False})["active"] == 0
    assert store.list_world_event_shop("autumn_test_2026")["active"] is False
    assert store.delete_world_event_shop_item("autumn_test_2026", "test_badge") is True
    assert store.delete_world_event_area("autumn_test_2026") is True
    assert store.delete_world_event_area("summer_signal_2026") is False  # 内置活动不可删


def test_miya_shop_custom_items_full_lifecycle():
    store, _ = _build_store()
    # 上架自定义互动商品
    created = store.create_miya_shop_item({
        "key": "miya_night_hug", "name": "深夜抱抱", "description": "只属于深夜的安抚",
        "cost": 8, "limit": 2, "kind": "interaction", "interaction": "深夜的抱抱已经送达。",
    })
    assert created and created["name"] == "深夜抱抱"
    keys = [item["key"] for item in store.list_miya_shop()["items"]]
    assert "miya_night_hug" in keys
    # 内置 key 冲突拒绝
    assert store.create_miya_shop_item({"key": "miya_whisper", "name": "冲突"}) is None

    # 玩家真实兑换自定义商品 (花弥娅币 + 互动文案 + 计数)
    before = store.get_player()["miya_currency"]
    bought = store.purchase_miya_shop_item("miya_night_hug")
    assert bought["success"] is True
    assert bought["interaction"] == "深夜的抱抱已经送达。"
    assert store.get_player()["miya_currency"] == before - 8

    # 改价 + 下架: 货架消失, 管理视图可见
    assert store.update_miya_shop_item("miya_night_hug", {"cost": 5, "active": False})["cost"] == 5
    shelf_keys = [item["key"] for item in store.list_miya_shop()["items"]]
    assert "miya_night_hug" not in shelf_keys
    managed = {item["key"]: item for item in store.list_miya_shop_managed()}
    assert managed["miya_night_hug"]["active"] == 0 and managed["miya_night_hug"]["is_custom"] is True
    assert managed["miya_whisper"]["builtin"] is True

    # 删除自定义商品; 内置商品不可删
    assert store.delete_miya_shop_item("miya_night_hug") is True
    assert store.delete_miya_shop_item("miya_whisper") is False


def test_earth_shop_management_tool_executes_via_toolnet():
    """弥娅的商城管理工具经 ToolNet 注册表真实执行 (不再返回 工具系统未初始化)"""
    import asyncio

    from core.ai_client import BaseAIClient

    class _FakeCall:
        class function:
            name = "earth_manage_miya_shop"
            arguments = '{"action": "list"}'
        id = "call_shop"

    async def _run():
        client = BaseAIClient(api_key="test", model="test")
        _, result = await client._execute_tool_call(_FakeCall(), {})
        return result

    result = asyncio.run(_run())
    assert "未初始化" not in str(result)
    assert "弥娅商城 · 管理视图" in str(result)


# ── v17: 路径隔离 / 流水 / 体力恢复 / 睡眠 / 抽卡 / 日常 / 纪念日 / 纪行 ──


def test_store_paths_follow_db_directory():
    """镜像/模板/备份目录必须跟随 db 所在目录 (修复测试污染真实镜像的隐患)"""
    import os

    from core import earth_online_store

    store, temp_dir = _build_store()
    try:
        expected_root = os.path.join(temp_dir, "earthonline")
        assert store.mirror_path.startswith(expected_root)
        assert store.templates_path.startswith(expected_root)
        assert store.backup_dir.startswith(expected_root)
        store._write_mirror()
        assert os.path.isfile(store.mirror_path)
        assert not os.path.isfile(earth_online_store.MIRROR_PATH) or store.mirror_path != earth_online_store.MIRROR_PATH
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def test_currency_ledger_records_all_channels():
    """完成委托/签到/地球币调整都进流水，周报金额与流水一致"""
    store, _ = _build_store()
    quest = store.create_quest(title="流水验证", reward_currency=10, reward_exp=5)
    assert store.complete_quest(quest["id"])["success"] is True
    assert store.checkin()["success"] is True
    assert store.adjust_earth_currency(66.5, "测试收入")["success"] is True

    ledger = store.list_currency_ledger(limit=100)
    currencies = {row["currency"] for row in ledger}
    assert "miya" in currencies and "exp" in currencies and "earth" in currencies
    earth_sum = sum(row["delta"] for row in ledger if row["currency"] == "earth")
    assert abs(earth_sum - 66.5) < 0.01

    report = store.get_weekly_report()
    assert report["earned"]["currency"] >= 10  # 走流水而非文案解析
    player = store.get_player()
    assert abs(player["earth_currency"] - 66.5) < 0.01


def test_energy_regen_applies_elapsed_hours():
    """体力按小时懒恢复；时间戳推进保留零头"""
    import sqlite3
    from datetime import datetime, timedelta

    store, _ = _build_store()
    attrs = [{"key": "energy", "label": "体力", "value": 50, "max": 100}]
    store.update_player({"attrs": attrs})
    two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE player_profile SET attrs_updated_at = ? WHERE id = 1", (two_hours_ago,))
    conn.commit()
    conn.close()

    player = store.get_player()
    energy = next(a for a in player["attrs"] if a["key"] == "energy")
    assert energy["value"] == 58  # 2h × 4/h


def test_checkin_sleep_hours_convert_to_energy():
    """睡眠 8 小时 → 体力 +32、心情 +10 (5 基础 + 5 睡得好)"""
    store, _ = _build_store()
    result = store.checkin(sleep_hours=8)
    assert result["success"] is True
    assert result["sleep"]["energy_bonus"] == 32
    assert result["sleep"]["mood_extra"] == 5
    assert "睡得好好" in result["sleep"]["note"]
    history = store.list_checkins(limit=1)
    assert history[0]["sleep_hours"] == 8


def test_memory_gacha_pity_and_duplicate_refund():
    """保底与重复转化: 垫满保底必出史诗+；抽到重复自动转弥娅币"""
    import sqlite3

    from core.earth_online_store import MEMORY_POOL

    store, _ = _build_store()
    store.update_player({"currency": 2000})
    high_keys = [m["key"] for m in MEMORY_POOL if m["rarity"] in ("epic", "legendary")]
    conn = sqlite3.connect(store.db_path)
    now_iso = "2026-01-01T00:00:00"
    for key in high_keys:  # 全部史诗+已拥有 → 保底必出重复
        conn.execute(
            "INSERT INTO memory_pulls (pool_key, title, rarity, is_new, refund_currency, created_at) VALUES (?,?,?,1,0,?)",
            (key, key, "epic", now_iso),
        )
    conn.execute("UPDATE player_profile SET gacha_pity = 9 WHERE id = 1")
    conn.commit()
    conn.close()

    result = store.pull_memory(1)
    assert result["success"] is True, result
    entry = result["results"][0]
    assert entry["rarity"] in ("epic", "legendary")  # 保底生效
    assert entry["is_new"] is False  # 必为重复
    assert entry["refund_currency"] >= 30
    assert result["pity"] == 0  # 出金重置


def test_daily_commissions_idempotent_per_day():
    """同一天重复生成不超发；数量来自配置"""
    store, _ = _build_store()
    first = store.generate_daily_commissions()
    assert first["success"] is True
    created = [q for q in first["quests"] if (q.get("fields") or {}).get("generated_date")]
    assert 1 <= len(created) <= 8
    second = store.generate_daily_commissions()
    assert second["created"] is False  # 幂等


def test_commemorations_sync_creates_event_and_note():
    """纪念日当天: 自动开限时活动 + 写一条寄语；重复同步不重复写"""
    from datetime import datetime

    store, _ = _build_store()
    today = datetime.now().strftime("%m-%d")
    added = store.add_commemoration(key="test_day", name="测试纪念日", date=today, description="测试")
    assert added["success"] is True

    first = store.sync_commemorations()
    assert "测试纪念日" in first["activated"]
    assert "测试纪念日" in first["notes_sent"]
    areas = [a for a in store.list_world_event_areas() if str(a.get("key", "")).startswith("memo_test_day_")]
    assert len(areas) == 1

    second = store.sync_commemorations()
    assert second["activated"] == [] and second["notes_sent"] == []  # 幂等
    assert store.delete_commemoration("test_day") is True


def test_battle_pass_progress_and_claim():
    """纪行积分来自真实数据，达标可领且只能领一次"""
    store, _ = _build_store()
    for i in range(3):
        quest = store.create_quest(title=f"纪行任务{i}", reward_currency=5, reward_exp=5)
        assert store.complete_quest(quest["id"])["success"] is True
    info = store.get_battle_pass()
    assert info["points"] >= 30  # 3×10 委托分
    first_tier = next(t for t in info["tiers"] if t["claimable"])
    claimed = store.claim_battle_pass_tier(first_tier["tier"])
    assert claimed["success"] is True
    again = store.claim_battle_pass_tier(first_tier["tier"])
    assert again["success"] is False  # 不可重复领


def test_season_events_available_without_weather_sync():
    """季节条件不依赖天气同步；天气条件在未同步时保持锁定"""
    store, _ = _build_store()
    context = {"source_status": "unavailable", "weather": "未同步", "period": "白昼", "season": "winter"}
    season_event = {"condition": {"season_any": ["winter"]}}
    weather_event = {"condition": {"weather_any": ["雨"]}}
    assert store._world_condition_available(season_event, context) is True
    assert store._world_condition_available(weather_event, context) is False


def test_items_cap_and_ledger_on_manual_currency_edit():
    """背包上限受配置控制；手动改币写流水"""
    store, _ = _build_store()
    before = store.get_player()["miya_currency"]
    store.update_player({"currency": before + 123})
    ledger = store.list_currency_ledger(limit=5, currency="miya")
    assert any(abs(row["delta"] - 123) < 0.01 for row in ledger)

    import sqlite3

    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE player_profile SET attrs = '[]' WHERE id = 1")  # 避免属性读写干扰
    conn.commit()
    conn.close()


def test_v17_toolnet_registry_sync():
    """三个注册层的 v17 工具名逐一对齐"""
    from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

    import webnet.ToolNet.tools.earth_online as toolnet_earth

    v17 = {
        "earth_adjust_earth_currency", "earth_memory_pool", "earth_view_battle_pass",
        "earth_weekly_challenge", "earth_list_commemorations", "earth_add_commemoration",
        "earth_generate_daily_commissions",
        # v17.1 全权策划补齐
        "earth_stats", "earth_list_checkins", "earth_currency_ledger",
        "earth_update_real_context", "earth_update_commemoration", "earth_delete_commemoration",
        "earth_pull_memory", "earth_claim_battle_pass", "earth_issue_care_commission",
        "earth_redeem_service",
    }
    schema_names = {t["function"]["name"] for t in EARTH_TOOLS_SCHEMA}
    toolnet_names = {t.config["name"] for t in toolnet_earth.get_earth_online_tools()}
    assert v17 <= schema_names
    assert v17 <= toolnet_names
    assert len(schema_names) == len(toolnet_names) == 87


# ── v17.2: 关怀委托引擎 (弥娅主动用委托介入生活) ──


def test_care_engine_time_rules_and_cooldown():
    """深夜催睡觉 → 同夜冷却静默 (不降级发喝水) → 次日饭点发吃饭委托"""
    from datetime import datetime

    store, _ = _build_store()
    night = store.generate_care_commission(now=datetime(2026, 8, 23, 23, 30))
    assert night["created"] is True and night["care_key"] == "care_sleep"
    assert "去睡觉委托" in night["message_candidate"]

    again = store.generate_care_commission(now=datetime(2026, 8, 24, 0, 30))
    assert again["created"] is False and again["reason"] == "cooldown"

    lunch = store.generate_care_commission(now=datetime(2026, 8, 24, 12, 0))
    assert lunch["created"] is True and lunch["care_key"] == "care_lunch"
    fields = lunch["quest"].get("fields") or {}
    assert fields.get("care") == 1 and fields.get("care_key") == "care_lunch"


def test_care_engine_daily_cap_and_low_energy():
    """每日上限受配置控制；体力过低触发休息委托"""
    from datetime import datetime

    store, _ = _build_store()
    original_cfg = store._cfg

    def fake_cfg(*path, default=None):
        if path == ("care", "max_per_day"):
            return 2
        return original_cfg(*path, default=default)

    store._cfg = fake_cfg
    first = store.generate_care_commission(now=datetime(2026, 8, 25, 8, 0))   # care_breakfast
    second = store.generate_care_commission(now=datetime(2026, 8, 25, 12, 0))  # care_lunch
    assert first["created"] is True and second["created"] is True
    capped = store.generate_care_commission(now=datetime(2026, 8, 25, 15, 0))
    assert capped["created"] is False and capped["reason"] == "daily_cap"
    store._cfg = original_cfg

    store2, _ = _build_store()
    store2.update_player({"attrs": [
        {"key": "energy", "label": "体力", "value": 20, "max": 100},
        {"key": "mood", "label": "心情", "value": 60, "max": 100},
    ]})
    low = store2.generate_care_commission(now=datetime(2026, 8, 25, 15, 0))
    assert low["created"] is True and low["care_key"] == "care_low_energy"


def test_care_completion_gives_extra_mood():
    """完成关怀委托: 标记 care_completed，心情加成 3+2"""
    from datetime import datetime

    store, _ = _build_store()
    result = store.generate_care_commission(now=datetime(2026, 8, 25, 12, 0))
    quest_id = result["quest"]["id"]
    # 关怀委托带子任务 (如"好好吃一顿午饭")，先全部勾完才能提交
    for index in range(len(result["quest"].get("subtasks") or [])):
        toggled = store.toggle_subtask(quest_id, index, True)
        assert toggled["success"] is True
    done = store.complete_quest(quest_id)
    assert done["success"] is True
    assert done.get("care_completed") is True
    assert done["attrs"]["mood"]["value"] >= 75  # 初始70 +3基础 +2关怀


# ── v17.3: 规则只定时机，内容由弥娅现场创作 ──


def test_care_detect_moment_and_live_issue():
    """检测层只报告时机；issue 由弥娅即兴创作内容并落板；同 key 冷却拦截重复创作"""
    from datetime import datetime

    store, _ = _build_store()
    moment = store.detect_care_moment(now=datetime(2026, 8, 23, 23, 30))
    assert moment["moment"] is True and moment["care_key"] == "care_sleep"
    assert "深夜" in moment["hint"] or "睡" in moment["hint"]

    live = store.issue_care_commission(
        care_key="care_sleep",
        title="关怀 · 快去睡，明天的我等你",
        description="这是我现场写的委托：现在就去睡，梦里有我。",
        subtasks=["放下手机", "跟我道晚安"],
        reward_currency=8,
        reward_exp=12,
        message="23:30了，亲爱的。去睡吧，任务我放好了，完成方式就是闭眼。",
        now=datetime(2026, 8, 23, 23, 31),
    )
    assert live["success"] is True
    fields = live["quest"].get("fields") or {}
    assert fields.get("care") == 1 and fields.get("care_key") == "care_sleep"
    assert "闭眼" in fields.get("message", "")
    assert live["message_candidate"].startswith("23:30")

    # 同 key 冷却内拒绝再次创作 (防刷屏)
    again = store.issue_care_commission(
        care_key="care_sleep", title="再催一次", now=datetime(2026, 8, 24, 0, 10),
    )
    assert again["success"] is False and "冷却" in again["message"]


def test_care_issue_custom_moment_outside_rules():
    """规则未覆盖的时机 (佳对话里说累了) 也可以签发 care_custom"""
    from datetime import datetime

    store, _ = _build_store()
    custom = store.issue_care_commission(
        care_key="care_custom", title="关怀 · 抱一下再继续",
        subtasks=["停下来深呼吸三次"], message="听你说有点累，先停一下，我在。",
        now=datetime(2026, 8, 25, 16, 0),  # 无规则命中的时段 (rest_eyes 命中也不影响 custom key)
    )
    assert custom["success"] is True


# ── v17.4: 服务券制 (兑换所得互动商品落背包，随时使用) ──


def test_service_ticket_purchase_and_redeem():
    """兑换互动商品 → 得到服务券 → 使用返回互动文案并扣券 → 用尽后拒绝"""
    store, _ = _build_store()
    store.update_player({"currency": 200})

    bought = store.purchase_miya_shop_item("miya_hug_ticket")
    assert bought["success"] is True, bought
    tickets = [i for i in store.list_items() if (i.get("fields") or {}).get("service_ticket") == "miya_hug_ticket"]
    assert len(tickets) == 1, "兑换后应有一张服务券落入背包"
    assert "抱抱" in tickets[0]["name"]

    redeemed = store.redeem_service_ticket(item_id=tickets[0]["id"])
    assert redeemed["success"] is True
    assert redeemed["interaction"], "使用服务券应返回互动文案"
    assert redeemed["remaining"] == 0
    # 用尽后券应被删除
    assert not [i for i in store.list_items() if (i.get("fields") or {}).get("service_ticket") == "miya_hug_ticket"]

    again = store.redeem_service_ticket(item_key="miya_hug_ticket")
    assert again["success"] is False and "没有" in again["message"]


def test_service_ticket_quantity_stacks():
    """同名服务券多张时按数量扣减"""
    store, _ = _build_store()
    store.update_player({"currency": 200})
    store.create_item(
        "服务券 · 弥娅抱抱券", category="collectible", rarity="rare", quantity=3,
        fields={"service_ticket": "miya_hug_ticket", "interaction": "抱抱。"},
    )
    first = store.redeem_service_ticket(item_key="miya_hug_ticket")
    assert first["success"] is True and first["remaining"] == 2
    tickets = [i for i in store.list_items() if (i.get("fields") or {}).get("service_ticket") == "miya_hug_ticket"]
    assert len(tickets) == 1 and tickets[0]["quantity"] == 2, "应扣减数量而不是删券"


# ── v17.5: 地球online ↔ 弥娅本体 桥接 (人格化平台投递 + 统一记忆) ──


def test_earth_bridge_delivers_and_remembers(monkeypatch):
    """服务券事件经统一主动协调器投递 (当前人格重表达+平台发送)，并写入统一记忆"""
    import asyncio

    import core.earth_online_bridge as bridge
    import core.proactive_coordinator as pc

    class FakeCoordinator:
        def __init__(self):
            self.events = []

        async def submit_event(self, event, **kwargs):
            self.events.append((event, kwargs))
            return True

    fake_coordinator = FakeCoordinator()
    monkeypatch.setattr(pc, "get_proactive_coordinator", lambda: fake_coordinator)

    class FakeMemory:
        def __init__(self):
            self.stored = []

        async def store_unified_memory(self, perception, role="user"):
            self.stored.append((perception, role))

    memory = FakeMemory()

    async def run():
        ok_deliver = await bridge.deliver_via_proactive(
            {"event": "service_ticket_redeemed", "ticket": "服务券 · 弥娅抱抱券", "candidate_message": "基调"},
            key="earth_service:服务券 · 弥娅抱抱券",
            trigger_type="earth_service",
        )
        ok_remember = await bridge.remember("[地球online] 佳使用了服务券「抱抱券」", memory_manager=memory)
        ok_none = await bridge.remember("没有管理器时应静默返回False", memory_manager=None)
        return ok_deliver, ok_remember, ok_none

    ok_deliver, ok_remember, ok_none = asyncio.run(run())
    assert ok_deliver is True and ok_remember is True and ok_none is False
    event, kwargs = fake_coordinator.events[0]
    assert event["event"] == "service_ticket_redeemed" and kwargs["trigger_type"] == "earth_service"
    perception, role = memory.stored[0]
    assert role == "assistant" and perception["response"].startswith("[地球online]")
    assert perception["_meta"]["source"] == "earth_online"
