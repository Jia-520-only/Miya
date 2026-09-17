import json
import os
import pathlib
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


def test_new_save_has_no_virtual_world_tables_or_seeded_areas():
    store, _ = _build_store()
    player = store.get_player()
    assert player["miya_currency"] == 100
    assert player["earth_currency"] == 0
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert not {"world_regions", "world_discoveries", "world_discovery_choices", "world_custom_events"} & names
    status = store.get_world_status()
    assert status["date"]
    assert status["weather"]
    assert status["event_areas"] == []


def test_legacy_virtual_world_is_backed_up_then_removed():
    import sqlite3

    temp_dir = tempfile.mkdtemp(prefix="earthonline_legacy_")
    db_path = os.path.join(temp_dir, "earthonline.db")
    conn = sqlite3.connect(db_path)
    for table in ("world_regions", "world_discoveries", "world_discovery_choices", "world_custom_events"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, payload TEXT)")
    conn.execute("INSERT INTO world_regions (payload) VALUES ('legacy virtual region')")
    conn.commit()
    conn.close()

    store = EarthOnlineStore(db_path=db_path)

    backups = list(pathlib.Path(store.backup_dir).glob("earthonline-before-reality-map-*.db"))
    assert len(backups) == 1
    conn = sqlite3.connect(store.db_path)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert not {"world_regions", "world_discoveries", "world_discovery_choices", "world_custom_events"} & names

    backup = sqlite3.connect(backups[0])
    assert backup.execute("SELECT payload FROM world_regions").fetchone()[0] == "legacy virtual region"
    backup.close()


def test_real_context_never_fakes_weather_and_map_context_keeps_provenance():
    store, _ = _build_store()

    settings = store.update_real_context_settings({"city": ""})
    assert settings["city"] == ""
    context = store.refresh_real_context()
    assert context["source_status"] in {"needs_location", "not_configured", "error", "ok"}
    if context["source_status"] != "ok":
        assert context["weather"] == "未同步"

    pending = store.record_real_place_visit("对话地点", source="conversation", latitude=30, longitude=120)
    observed = store.record_real_place_visit("定位地点", source="browser_geolocation", latitude=31, longitude=121, accuracy_m=12)
    facts = store.get_map_fact_context()
    assert pending["verification_status"] == "unverified"
    assert observed["verification_status"] == "observed"
    assert facts["counts"]["unverified"] == 1
    assert facts["counts"]["observed"] == 1
    assert facts["weather"]["source_status"] == context["source_status"]


def test_one_off_weather_query_does_not_change_default_city_or_world_snapshot(monkeypatch):
    import sqlite3

    store, _ = _build_store()
    store.update_real_context_settings({"city": "杭州"})

    def fake_query(location, **kwargs):
        assert location == "东京"
        return {
            "requested_location": location,
            "resolved_location": {"name": "东京", "path": "日本, 东京", "timezone": "Asia/Tokyo"},
            "city": "东京",
            "source": "seniverse",
            "source_status": "ok",
            "captured_at": "2026-09-17T16:00:00+09:00",
            "weather": "晴",
            "weather_icon": "☼",
            "temperature": 27.0,
            "humidity": 55.0,
            "wind": "东 2级",
            "forecast": [],
        }

    monkeypatch.setattr("core.weather_service.query_weather", fake_query)

    result = store.refresh_real_context({"city": "东京", "include_forecast": True})

    assert result["city"] == "东京"
    assert result["requested_location"] == "东京"
    assert store.get_real_context_settings()["city"] == "杭州"
    conn = sqlite3.connect(store.db_path)
    snapshot_count = conn.execute("SELECT COUNT(*) FROM world_real_context_snapshots").fetchone()[0]
    conn.close()
    assert snapshot_count == 0


def test_default_weather_snapshot_uses_requested_location_for_freshness(monkeypatch):
    from datetime import datetime

    store, _ = _build_store()
    store.update_real_context_settings({"city": "杭州市", "refresh_minutes": 30})

    def fake_query(location, **kwargs):
        return {
            "requested_location": location,
            "resolved_location": {"name": "杭州", "path": "中国, 浙江, 杭州", "timezone": "Asia/Shanghai"},
            "city": "杭州",
            "source": "seniverse",
            "source_status": "ok",
            "captured_at": datetime.now().astimezone().isoformat(),
            "weather": "晴",
            "weather_icon": "☼",
            "temperature": 28.0,
            "humidity": 50.0,
            "wind": "东 2级",
            "forecast": [],
        }

    monkeypatch.setattr("core.weather_service.query_weather", fake_query)
    snapshot = store.refresh_real_context()
    loaded = store.get_real_context(auto_refresh=False)

    assert snapshot["city"] == "杭州"
    assert loaded["city"] == "杭州"
    assert loaded["is_stale"] == 0
    assert loaded["settings"]["city"] == "杭州市"


def test_unverified_place_can_be_explicitly_confirmed_without_losing_source():
    store, _ = _build_store()
    pending = store.record_real_place_visit(
        "对话候选地点", source="conversation", latitude=30.2, longitude=120.1,
    )
    original_source = pending["source"]

    confirmed = store.update_real_place(pending["place_key"], {"verification_status": "confirmed"})

    assert confirmed["verification_status"] == "confirmed"
    assert confirmed["source"] == original_source
    assert confirmed["source_updated_at"]


def test_journey_facts_require_a_real_coordinate_track():
    store, _ = _build_store()
    store.create_story(
        title="现实步行旅程",
        content="这段文字只是叙事，不作为坐标事实。",
        fields={
            "journey": True,
            "source": "journey_gps",
            "verification_status": "observed",
            "recorded_at": "2026-09-17T10:05:00+08:00",
            "distance_m": 1234.5,
            "duration_seconds": 900,
            "track": [
                {"latitude": 30.1001, "longitude": 120.2001, "timestamp": 1},
                {"latitude": 30.1010, "longitude": 120.2020, "timestamp": 2},
                {"latitude": "invalid", "longitude": 120.3},
            ],
        },
    )
    store.create_story(title="纯叙事旅程", fields={"journey": True, "track": []})
    store.create_story(
        title="对话生成的伪轨迹",
        fields={
            "journey": True,
            "source": "conversation",
            "track": [{"latitude": 30.5, "longitude": 120.5}],
        },
    )

    journeys = store.list_real_journeys()

    assert len(journeys) == 1
    assert journeys[0]["source"] == "journey_gps"
    assert journeys[0]["verification_status"] == "observed"
    assert journeys[0]["distance_m"] == 1234.5
    assert len(journeys[0]["track"]) == 2


def test_real_place_provenance_survives_export_import_roundtrip():
    source_store, _ = _build_store()
    place = source_store.record_real_place_visit(
        "轨迹终点", latitude=31.1, longitude=121.2, accuracy_m=8,
        source="journey_gps", provider_id="gps-finish", observed_at="2026-09-17T11:00:00+08:00",
    )
    payload = source_store.export_json()
    target_store, _ = _build_store()

    target_store.import_json(payload)
    restored = target_store.get_real_place(place["place_key"])

    assert restored["verification_status"] == "observed"
    assert restored["source"] == "journey_gps"
    assert restored["provider_id"] == "gps-finish"
    assert restored["visits"][0]["verification_status"] == "observed"
    assert restored["visits"][0]["observed_at"] == "2026-09-17T11:00:00+08:00"


# ── v13: 属性联动 / 好感解锁 / 现实活动 ──


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
    assert store.list_world_event_areas() == []


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


def test_real_places_keep_same_name_locations_separate_and_merge_nearby_visits():
    """同名异地不能串档；明确 provider 或近邻坐标仍应累计为同一地点。"""
    store, _ = _build_store()

    east = store.record_real_place_visit(
        "星光咖啡", latitude=31.2304, longitude=121.4737,
        provider_id="node-1001", display_address="上海市黄浦区", source="map_search",
    )
    west = store.record_real_place_visit(
        "星光咖啡", latitude=30.5728, longitude=104.0668,
        provider_id="node-2002", display_address="成都市锦江区", source="map_search",
    )
    again = store.record_real_place_visit(
        "星光咖啡", latitude=31.23041, longitude=121.47371,
        provider_id="node-1001", display_address="上海市黄浦区", note="第二次来",
    )

    assert east["place_key"] != west["place_key"]
    assert again["place_key"] == east["place_key"]
    assert again["visit_count"] == 2
    detail = store.get_real_place(east["place_key"])
    assert detail is not None
    assert len(detail["visits"]) == 2
    assert detail["visits"][0]["note"] == "第二次来"


def test_real_place_detail_edit_gallery_and_delete():
    """地点档案支持标签/收藏编辑、多照片和结构化删除。"""
    store, _ = _build_store()
    place = store.record_real_place_visit(
        "河畔公园", latitude=30.1, longitude=120.2,
        display_address="测试市河畔路", provider_id="way-3003",
    )

    updated = store.update_real_place(place["place_key"], {
        "subtitle": "傍晚散步的地方", "category": "park",
        "tags": ["散步", "安静", "散步"], "favorite": True,
    })
    assert updated["subtitle"] == "傍晚散步的地方"
    assert updated["tags"] == ["散步", "安静"]
    assert updated["favorite"] is True
    revisit = store.record_real_place_visit("河畔公园", place_key=place["place_key"], latitude=30.1, longitude=120.2)
    assert revisit["category"] == "park"

    store.update_real_place_image(place["place_key"], "/api/earth/images/a.jpg")
    detail = store.update_real_place_image(place["place_key"], "/api/earth/images/b.jpg")
    assert len(detail["photos"]) == 2
    assert detail["image_path"].endswith("b.jpg")

    assert store.delete_real_place(place["place_key"]) is True
    assert store.get_real_place(place["place_key"]) is None
    assert store.delete_real_place(place["place_key"]) is False


def test_nearby_place_normalization_includes_distance_and_live_metadata():
    """附近 POI 应带距离、类别和可核验的外部字段，且不写入地点档案。"""
    from core.earth_online_store import EarthOnlineStore

    result = EarthOnlineStore._normalize_nearby_result({
        "type": "node", "id": 9988, "lat": 31.2305, "lon": 121.4738,
        "tags": {
            "name": "测试咖啡馆", "amenity": "cafe", "opening_hours": "08:00-20:00",
            "phone": "12345", "website": "https://example.test", "addr:city": "上海市",
        },
    }, 31.2304, 121.4737)

    assert result is not None
    assert result["provider_id"] == "node-9988"
    assert result["category"] == "cafe"
    assert result["category_group"] == "amenity"
    assert 0 < result["distance_m"] < 30
    assert result["opening_hours"] == "08:00-20:00"
    assert result["source"] == "openstreetmap_overpass"


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
    """工具注册层严格对齐，并且不再暴露虚拟世界能力。"""
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
    reality_map = {"earth_map_context", "earth_list_journeys", "earth_confirm_place", "earth_query_weather"}
    retired = {
        "earth_explore", "earth_region_commission", "earth_update_region",
        "earth_add_world_event", "earth_list_world_events", "earth_delete_world_event",
        "earth_list_discoveries", "earth_choose_discovery",
    }
    assert v17 | reality_map <= schema_names
    assert schema_names == toolnet_names
    assert not retired & schema_names


def test_earning_profile_routes_and_sprint_flow():
    """收益档案会排序路线；7 天实验幂等创建，并把首步放入委托板。"""
    store, _ = _build_store()
    prefs = store.update_earning_preferences({
        "skills": ["Python", "自动化", "写作"],
        "sellable_assets": ["脚本", "模板"],
        "accepted_models": ["automation_tool", "digital_product", "skill_service"],
        "weekly_hours": 6,
        "target_amount": 100,
        "constraints": "不垫资",
    })
    assert prefs["skills"] == ["Python", "自动化", "写作"]
    assert prefs["accepted_models"] == ["automation_tool", "digital_product", "skill_service"]

    routes = store.earning_routes()
    assert {route["key"] for route in routes} == {"automation_tool", "digital_product", "skill_service"}
    assert "automation_tool" in {route["key"] for route in routes[:2]}
    assert next(route for route in routes if route["key"] == "automation_tool")["fit_score"] >= 80

    sprint = store.create_earning_sprint({"route_key": "automation_tool", "goal_amount": 100})
    assert sprint["success"] is True and sprint["created"] is True
    assert sprint["plan"]["is_sprint"] == 1
    assert len(sprint["plan"]["steps"]) == 5
    assert sprint["plan"]["steps"][0]["quest_id"]

    again = store.create_earning_sprint({"route_key": "automation_tool", "goal_amount": 200})
    assert again["success"] is True and again["created"] is False
    assert again["plan"]["id"] == sprint["plan"]["id"]


def test_earning_quest_completion_syncs_plan_and_guidance():
    """委托完成会回写收益阶段，指导接口给出真实下一步与漏斗。"""
    store, _ = _build_store()
    store.update_earning_preferences({"skills": ["整理"], "weekly_hours": 3})
    sprint = store.create_earning_sprint({"route_key": "resale", "goal_amount": 100})
    first = sprint["plan"]["steps"][0]

    result = store.complete_quest(first["quest_id"])
    assert result["success"] is True
    plan = store.get_earning_plan(sprint["plan"]["id"])
    assert plan["steps"][0]["status"] == "done"
    assert plan["steps"][1]["status"] == "pending"

    guidance = store.earning_guidance()
    assert guidance["profile_ready"] is True
    assert guidance["next_action"]["id"] == plan["steps"][1]["id"]
    assert guidance["totals"]["effective_hourly_rate"] == 0
    assert set(guidance["pipeline"]) == {"inbox", "shortlisted", "applied", "won", "closed"}


def test_earning_opportunity_verification_and_income_validation():
    """机会核验影响推荐分；零收入不会污染真实收益流水。"""
    import pytest

    store, _ = _build_store()
    pending = store.create_earning_opportunity({
        "title": "公开需求", "income_min": 100, "income_max": 100, "hours": 2,
        "risk": "low", "confidence": "medium",
    })
    before = store.earning_guidance()["opportunities"][0]["fit_score"]
    store.update_earning_opportunity(pending["id"], {"verification_status": "verified"})
    after = store.earning_guidance()["opportunities"][0]["fit_score"]
    assert after > before

    with pytest.raises(ValueError, match="必须大于 0"):
        store.record_income({"amount": 0, "cost": 0, "hours": 1})


def test_first_income_experiment_creates_guarded_offer_and_sprint():
    """首单入口固化每天两小时、净收入 200+ 和自动化微服务边界。"""
    store, _ = _build_store()

    result = store.start_first_income_experiment({
        "weekly_hours": 2,
        "target_amount": 100,
        "price": "invalid",
    })

    assert result["success"] is True
    assert result["preferences"]["weekly_hours"] == 14
    assert result["preferences"]["target_amount"] == 201
    assert result["preferences"]["primary_route"] == "automation_tool"
    assert result["offer"]["title"] == "48 小时自动化微服务"
    assert result["offer"]["price"] == 299
    assert "付款" in result["offer"]["scope"]
    assert result["sprint"]["plan"]["route_key"] == "automation_tool"


def test_earning_action_approval_is_content_bound_and_revocable():
    """批准只绑定当前草稿；改稿会使批准失效，且可随时撤销。"""
    import pytest

    store, _ = _build_store()
    offer = store.create_earning_offer({"title": "小型自动化", "price": 299})
    draft = store.create_earning_action({
        "offer_id": offer["id"],
        "action_type": "proposal",
        "target": "公开需求 #123",
        "title": "自动化服务提案",
        "content": "交付一条自动化流程，报价 299 元。",
        "amount": 299,
        "risk": "low",
    })
    submitted = store.submit_earning_action(draft["id"])
    assert submitted["status"] == "pending"
    assert len(submitted["content_hash"]) == 64

    with pytest.raises(ValueError, match="校验失败"):
        store.approve_earning_action(draft["id"], "0" * 64)

    approved = store.approve_earning_action(draft["id"], submitted["content_hash"])
    assert approved["status"] == "approved"
    assert approved["approved_hash"] == submitted["content_hash"]
    assert approved["expires_at"]

    changed = store.update_earning_action(draft["id"], {"content": "调整后的提案内容。"})
    assert changed["status"] == "draft"
    assert changed["approved_hash"] == ""
    assert changed["expires_at"] == ""

    resubmitted = store.submit_earning_action(draft["id"])
    revoked = store.revoke_earning_action(resubmitted["id"])
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"]


def test_earning_actions_reject_financial_operations_and_expire_approval():
    """资金类动作永不进入审批箱；过期批准会在读取时自动失效。"""
    import pytest

    store, _ = _build_store()
    for action_type in ("payment", "transfer", "withdraw", "refund"):
        with pytest.raises(ValueError, match="不受支持"):
            store.create_earning_action({
                "action_type": action_type,
                "title": "禁止动作",
                "content": "不得创建",
            })

    draft = store.create_earning_action({
        "action_type": "contact",
        "title": "联系草稿",
        "content": "仅用于测试审批过期。",
    })
    submitted = store.submit_earning_action(draft["id"])
    approved = store.approve_earning_action(draft["id"], submitted["content_hash"])
    conn = store._connect()
    try:
        conn.execute(
            "UPDATE earning_action_drafts SET expires_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00", approved["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    assert store.get_earning_action(approved["id"])["status"] == "expired"


def test_public_feed_resolution_rejects_private_dns_answers(monkeypatch):
    """公开域名若解析到内网地址，也不能被信息源抓取器访问。"""
    import pytest

    monkeypatch.setattr(
        "core.earth_online_store.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(ValueError, match="内网"):
        EarthOnlineStore._fetch_public_feed("https://example.com/feed.xml")


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
