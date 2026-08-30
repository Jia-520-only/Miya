"""地球online 工具集（ToolNet）— 弥娅操控现实游戏化系统的工具

注册到 ToolNet 工具注册表，弥娅在对话中通过 Function Calling 直接调用。
数据访问统一走 core.earth_online_store.get_earth_store()。
"""

from datetime import datetime
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

RARITY_LABELS = {
    "common": "普通", "uncommon": "稀有", "rare": "珍贵", "epic": "史诗", "legendary": "传说",
}
QUEST_TYPE_LABELS = {"main": "主线", "branch": "支线", "daily": "日常", "optional": "可选"}
STATUS_LABELS = {
    "pending": "待开始", "ongoing": "进行中", "completed": "已完成",
    "failed": "失败", "cancelled": "已取消",
}
RELATIONSHIP_LABELS = {
    "family": "家人", "friend": "朋友", "colleague": "同事", "partner": "恋人", "other": "其他",
}


class _EarthBase(BaseTool):
    """地球online 工具基类"""

    def _store(self):
        from core.earth_online_store import get_earth_store

        return get_earth_store()


class EarthOnlineWorld(_EarthBase):
    """单人世界地图"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_world",
            "description": "查看佳的单人地球online 世界地图、区域解锁条件与探索进度",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            store = self._store()
            level = store.get_player().get("level", 1)
            regions = store.list_world_regions()
            lines = ["【地球online 世界地图】"]
            for region in regions:
                status = f"Lv.{region['level_req']} 解锁" if level < region["level_req"] else f"探索 {region['discovery_total']}/{region['event_total']}"
                lines.append(f"{region['icon']} {region['name']} · {region['subtitle']} · {status}")
            return "\n".join(lines)
        except Exception as e:
            return f"读取世界地图失败: {e}"


class EarthOnlineExplore(_EarthBase):
    """探索世界区域"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_explore",
            "description": "探索一个世界地图区域，触发只属于佳的世界发现并领取弥娅币与经验奖励；区域可能绑定真实地理围栏，玩家在附近时应携带当前坐标 latitude/longitude 一起探索",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_key": {"type": "string", "description": "区域 key，例如 miya_garden、city_lumen"},
                    "latitude": {"type": "number", "description": "玩家当前纬度（区域绑定地理围栏时必填）"},
                    "longitude": {"type": "number", "description": "玩家当前经度（区域绑定地理围栏时必填）"},
                },
                "required": ["region_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            latitude = args.get("latitude")
            longitude = args.get("longitude")
            result = self._store().explore_world_region(
                str(args.get("region_key", "")),
                latitude=float(latitude) if latitude is not None else None,
                longitude=float(longitude) if longitude is not None else None,
            )
            if not result.get("success"):
                return result.get("message", "探索失败")
            discovery = result.get("discovery")
            if not discovery:
                return result.get("message", "这个区域已经探索完毕啦～")
            geo = result.get("geofence") or {}
            geo_note = f"\n(真实定位: 距离围栏中心 {geo.get('distance_m')} 米)" if geo.get("distance_m") is not None else ""
            return (
                f"在「{result['region']['name']}」发现【{discovery['title']}】\n"
                f"{discovery['content']}\n"
                f"奖励: +{discovery['reward_currency']} 弥娅币 · +{discovery['reward_exp']} 经验"
                f"{geo_note}"
            )
        except Exception as e:
            return f"探索区域失败: {e}"


class EarthOnlineWorldStatus(_EarthBase):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_world_status",
            "description": "查看当前地球online 的世界时间、天气和限时活动区域",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            status = self._store().get_world_status()
            active = [x["name"] for x in status.get("event_areas", []) if x.get("active")]
            return (f"【世界状态】{status['period_icon']} {status['period']} · {status['weather_icon']} {status['weather']} · "
                    f"{status['date']} {status['time']}\n限时活动: {('、'.join(active) if active else '当前没有限时区域')}")
        except Exception as e:
            return f"读取世界状态失败: {e}"


class EarthOnlineRealContext(_EarthBase):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_real_context",
            "description": "读取现实数据连接状态与最近真实天气快照，未同步时明确说明",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            data = self._store().get_real_context(auto_refresh=True)
            if data.get("source_status") == "ok":
                return f"【现实连接】已同步 · {data.get('city')} · {data.get('weather')} · {data.get('temperature', '未知')}°C"
            return f"【现实连接】{data.get('weather', '未同步')} · 状态 {data.get('source_status', 'unavailable')}"
        except Exception as e:
            return f"读取现实连接失败: {e}"


class EarthOnlineRefreshRealContext(_EarthBase):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_refresh_real_context",
            "description": "刷新真实天气快照；失败不会回退到模拟天气",
            "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "城市名称，可留空"}}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            data = self._store().refresh_real_context({"city": args.get("city", "")} if args.get("city") else {})
            if data.get("source_status") == "ok":
                return f"现实天气已同步：{data.get('city')} · {data.get('weather')} · {data.get('temperature', '未知')}°C"
            return f"现实天气未同步：{data.get('source_status', 'unavailable')}"
        except Exception as e:
            return f"刷新现实天气失败: {e}"


class EarthOnlineRegionCommission(_EarthBase):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_region_commission",
            "description": "为指定世界区域生成今天唯一的专属委托，自动带上当前天气和时间氛围",
            "parameters": {
                "type": "object",
                "properties": {"region_key": {"type": "string", "description": "区域 key，例如 miya_garden、night_sea"}},
                "required": ["region_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            result = self._store().create_region_commission(str(args.get("region_key", "")))
            if not result.get("success"):
                return result.get("message", "生成委托失败")
            quest = result["quest"]
            return (f"区域委托{'已生成' if result.get('created') else '已经在任务板上'}: 「{quest['title']}」\n"
                    f"{quest['description']}\n奖励 +{quest['reward_currency']} 弥娅币 · +{quest['reward_exp']} 经验")
        except Exception as e:
            return f"生成区域委托失败: {e}"


class EarthOnlineSummary(_EarthBase):
    """地球online 总览"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_summary",
            "description": "查看地球online总览，包括玩家等级、经验、地球币、背包/任务/角色/剧情统计",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            s = self._store().summary()
            p = s["player"]
            st = s["stats"]
            return (
                f"【地球online 总览】\n"
                f"等级: Lv.{p['level']} | 经验: {p['exp']} | 地球币: {p['currency']}\n"
                f"完成任务: {p['total_completed']} | 失败任务: {p['total_failed']}\n"
                f"统计: 进行中任务 {st['active_quests']} | 背包物品 {st['items']} | 角色 {st['characters']} | 剧情 {st['stories']}"
            )
        except Exception as e:
            return f"获取地球online总览失败: {e}"


class EarthOnlinePlayer(_EarthBase):
    """玩家状态"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_player",
            "description": "查看玩家当前状态（等级、经验、地球币、任务完成统计）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            p = self._store().get_player()
            return (
                f"【玩家档案】Lv.{p['level']} | 经验 {p['exp']} | 地球币 {p['currency']} | "
                f"完成 {p['total_completed']} | 失败 {p['total_failed']}"
            )
        except Exception as e:
            return f"获取玩家状态失败: {e}"


class EarthOnlineListItems(_EarthBase):
    """查看背包物品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_items",
            "description": "查看背包里的现实物品列表，可按状态过滤（normal/used/lost）",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "description": "物品状态，留空查全部"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            items = self._store().list_items(status=args.get("status", ""))
            if not items:
                return "背包还是空的呢，亲爱的～"
            lines = ["【我的背包】"]
            for it in items:
                rarity = RARITY_LABELS.get(it["rarity"], it["rarity"])
                qty = f" ×{it['quantity']}" if it["quantity"] > 1 else ""
                lines.append(
                    f"- #{it['id']} {it['name']}{qty} [{rarity}]"
                    + (f" - {it['description'][:40]}" if it.get("description") else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看背包失败: {e}"


class EarthOnlineAddItem(_EarthBase):
    """添加背包物品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_item",
            "description": "往背包添加一件现实物品，记录名称、分类、稀有度、数量与描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "物品名称（必填）"},
                    "category": {"type": "string", "description": "分类: digital数码/book书籍/life生活/food食品/tool工具/clothing服饰/collectible收藏/other其他"},
                    "rarity": {"type": "string", "description": "稀有度: common普通/uncommon稀有/rare珍贵/epic史诗/legendary传说"},
                    "quantity": {"type": "integer", "description": "数量，默认1"},
                    "description": {"type": "string", "description": "物品描述"},
                    "markdown": {"type": "string", "description": "三段式档案 (封面+简介+详情，可选)"},
                    "image_path": {"type": "string", "description": "照片路径 (可选)"},
                    "fields": {"type": "object", "description": "自定义字段对象 (可选)"},
                },
                "required": ["name"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields = args.get("fields")
            item = self._store().create_item(
                name=args.get("name", ""),
                category=args.get("category", "other"),
                rarity=args.get("rarity", "common"),
                quantity=int(args.get("quantity", 1)),
                description=args.get("description", ""),
                markdown=args.get("markdown", ""),
                image_path=args.get("image_path", ""),
                fields=fields if isinstance(fields, dict) else None,
            )
            rarity = RARITY_LABELS.get(item["rarity"], item["rarity"])
            return f"已将「{item['name']}」收入背包 [{rarity}] 数量×{item['quantity']}"
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"添加物品失败: {e}"


class EarthOnlineListQuests(_EarthBase):
    """查看任务列表"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_quests",
            "description": "查看任务列表，可按状态过滤（pending/ongoing/completed/failed/cancelled）",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "description": "任务状态，留空查全部"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            quests = self._store().list_quests(status=args.get("status", ""))
            if not quests:
                return "当前没有任务～"
            lines = ["【任务委托】"]
            for q in quests:
                qtype = QUEST_TYPE_LABELS.get(q["quest_type"], q["quest_type"])
                mark = "必须" if q["must_complete"] else "可选"
                st = STATUS_LABELS.get(q["status"], q["status"])
                lines.append(
                    f"- #{q['id']} [{qtype}/{mark}] {q['title']} ({st}) "
                    f"奖励+{q['reward_currency']}币/+{q['reward_exp']}经验 "
                    + (f"鸽-{q['penalty_currency']}币" if q["penalty_currency"] else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看任务失败: {e}"


class EarthOnlineAddQuest(_EarthBase):
    """安排任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_quest",
            "description": "安排一个任务给亲爱的，可设必须完成与奖励惩罚，主线/支线/日常/可选四种类型；可设循环任务（daily每天/weekly每周，完成后自动重置，适合喝水/睡觉等日常习惯）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题（必填）"},
                    "description": {"type": "string", "description": "任务描述"},
                    "quest_type": {"type": "string", "description": "main主线/branch支线/daily日常/optional可选，默认branch"},
                    "must_complete": {"type": "boolean", "description": "是否必须完成，失败扣惩罚"},
                    "reward_currency": {"type": "integer", "description": "奖励弥娅币"},
                    "reward_exp": {"type": "integer", "description": "奖励经验"},
                    "penalty_currency": {"type": "integer", "description": "失败惩罚弥娅币"},
                    "deadline": {"type": "string", "description": "截止时间 ISO格式，如 2026-08-21T20:00:00"},
                    "subtasks": {"type": "array", "description": "子任务清单 [{\"text\":\"...\",\"done\":false}]"},
                    "recurring": {"type": "string", "description": "循环类型: 空/一次, daily/每天, weekly/每周"},
                },
                "required": ["title"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            deadline = args.get("deadline", "")
            q = self._store().create_quest(
                title=args.get("title", ""),
                description=args.get("description", ""),
                quest_type=args.get("quest_type", "branch"),
                must_complete=bool(args.get("must_complete", False)),
                reward_currency=int(args.get("reward_currency", 10)),
                reward_exp=int(args.get("reward_exp", 15)),
                penalty_currency=int(args.get("penalty_currency", 20)),
                deadline=deadline,
                source="miya",
                subtasks=args.get("subtasks"),
                recurring=args.get("recurring", ""),
            )
            mark = "必须任务" if q["must_complete"] else "可选任务"
            rec_label = {"daily": " (每天循环)", "weekly": " (每周循环)"}.get(q.get("recurring") or "", "")
            msg = (
                f"任务已安排: #{q['id']}「{q['title']}」[{mark}]{rec_label}\n"
                f"奖励: +{q['reward_currency']}弥娅币, +{q['reward_exp']}经验"
                + (f" | 鸽了扣{q['penalty_currency']}弥娅币" if q["penalty_currency"] else "")
            )
            if deadline:
                msg += f" | 截止 {deadline}"
            subtasks = q.get("subtasks") or []
            if subtasks:
                done = sum(1 for s in subtasks if s.get("done"))
                msg += f" | 子任务 {done}/{len(subtasks)}"
            return msg
        except Exception as e:
            return f"安排任务失败: {e}"


class EarthOnlineAcceptQuest(_EarthBase):
    """接取任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_accept_quest",
            "description": "接取任务（待开始 → 进行中），表示玩家开始执行该任务",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID（必填）"}},
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().accept_quest(int(args.get("quest_id", 0)))
            if not r.get("success"):
                return r.get("message", "操作失败")
            return f"已接取任务「{r['quest']['title']}」，状态: 进行中。加油，亲爱的！"
        except Exception as e:
            return f"接取任务失败: {e}"


class EarthOnlineCompleteQuest(_EarthBase):
    """完成任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_complete_quest",
            "description": "将任务标记为完成并发放奖励（地球币和经验）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID（必填）"}},
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().complete_quest(int(args.get("quest_id", 0)))
            if not r.get("success"):
                return r.get("message", "操作失败")
            p = r["player"]
            rew = r["reward"]
            return (
                f"任务「{r['quest']['title']}」完成！\n"
                f"奖励: +{rew['currency']}地球币, +{rew['exp']}经验\n"
                f"当前: Lv.{p['level']} | 地球币 {p['currency']}"
            )
        except Exception as e:
            return f"完成任务失败: {e}"


class EarthOnlineFailQuest(_EarthBase):
    """任务失败"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_fail_quest",
            "description": "将任务标记为失败并扣除惩罚地球币",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID（必填）"}},
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().fail_quest(int(args.get("quest_id", 0)))
            if not r.get("success"):
                return r.get("message", "操作失败")
            p = r["player"]
            return f"任务「{r['quest']['title']}」已标记失败，剩余地球币: {p['currency']}"
        except Exception as e:
            return f"标记任务失败出错: {e}"


class EarthOnlineCheckOverdue(_EarthBase):
    """检查逾期任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_check_overdue",
            "description": "检查所有逾期未完成任务并自动标记失败惩罚",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().check_overdue()
            return f"逾期检查完成: {r['failed']} 个任务已失败处理"
        except Exception as e:
            return f"逾期检查失败: {e}"


class EarthOnlineListStory(_EarthBase):
    """查看剧情"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_story",
            "description": "查看已记录的人生剧情记录",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            stories = self._store().list_story(event_type="", limit=20)
            if not stories:
                return "还没有剧情记录～"
            lines = ["【人生剧情】"]
            for s in stories:
                lines.append(
                    f"- {s['happened_at'][:10]} {s['title']}"
                    + (f": {s['content'][:40]}" if s.get("content") else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看剧情失败: {e}"


class EarthOnlineAddStory(_EarthBase):
    """记录剧情"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_story",
            "description": "记录一段人生剧情，把生活事件剧情化",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "剧情标题（必填）"},
                    "content": {"type": "string", "description": "剧情内容"},
                    "event_type": {"type": "string", "description": "life生活/achievement成就/quest任务/character人物，默认life"},
                    "character_id": {"type": "integer", "description": "关联角色ID（可选）"},
                    "item_id": {"type": "integer", "description": "关联物品ID（可选）"},
                    "image_path": {"type": "string", "description": "关联照片路径（可选）"},
                    "fields": {"type": "object", "description": "自定义字段对象（可选）"},
                },
                "required": ["title"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields = args.get("fields")
            s = self._store().create_story(
                title=args.get("title", ""),
                content=args.get("content", ""),
                event_type=args.get("event_type", "life"),
                character_id=int(args["character_id"]) if args.get("character_id") else None,
                item_id=int(args["item_id"]) if args.get("item_id") else None,
                image_path=args.get("image_path", ""),
                fields=fields if isinstance(fields, dict) else None,
            )
            return f"剧情已记录: 「{s['title']}」"
        except Exception as e:
            return f"记录剧情失败: {e}"


class EarthOnlineListCharacters(_EarthBase):
    """角色图鉴"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_characters",
            "description": "查看角色图鉴与好感度",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            chars = self._store().list_characters()
            if not chars:
                return "图鉴里还没有角色～"
            lines = ["【角色图鉴】"]
            for c in chars:
                rel = RELATIONSHIP_LABELS.get(c["relationship"], c["relationship"])
                nick = f" ({c['nickname']})" if c.get("nickname") else ""
                lines.append(f"- #{c['id']} {c['name']}{nick} [{rel}] 好感度 {c['affinity']}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看角色失败: {e}"


class EarthOnlineAddCharacter(_EarthBase):
    """添加角色"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_character",
            "description": "在角色图鉴中添加一位现实人物",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "人物姓名（必填）"},
                    "nickname": {"type": "string", "description": "昵称"},
                    "relationship": {"type": "string", "description": "family家人/friend朋友/colleague同事/partner恋人/other其他"},
                    "affinity": {"type": "integer", "description": "初始好感度0-100"},
                    "notes": {"type": "string", "description": "备注"},
                    "birthday": {"type": "string", "description": "生日，如 05-20"},
                    "avatar_path": {"type": "string", "description": "头像图片路径"},
                    "markdown": {"type": "string", "description": "三段式档案 (封面+简介+详情)"},
                    "fields": {"type": "object", "description": "自定义字段对象（可选）"},
                },
                "required": ["name"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields = args.get("fields")
            c = self._store().create_character(
                name=args.get("name", ""),
                nickname=args.get("nickname", ""),
                relationship=args.get("relationship", "friend"),
                affinity=int(args.get("affinity", 0)),
                notes=args.get("notes", ""),
                birthday=args.get("birthday", ""),
                avatar_path=args.get("avatar_path", ""),
                markdown=args.get("markdown", ""),
                fields=fields if isinstance(fields, dict) else None,
            )
            return f"角色「{c['name']}」已加入图鉴 (好感度 {c['affinity']})"
        except Exception as e:
            return f"添加角色失败: {e}"


class EarthOnlineAdjustAffinity(_EarthBase):
    """调整好感度"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_adjust_affinity",
            "description": "调整角色好感度，可正可负，需说明原因",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer", "description": "角色ID（必填）"},
                    "delta": {"type": "integer", "description": "好感度变动值，如+5或-3（必填）"},
                    "reason": {"type": "string", "description": "变动原因"},
                },
                "required": ["character_id", "delta"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            c = self._store().add_affinity(
                int(args.get("character_id", 0)), int(args.get("delta", 0)), args.get("reason", "")
            )
            if not c:
                return f"角色 #{args.get('character_id')} 不存在"
            delta = int(args.get("delta", 0))
            arrow = "+" if delta >= 0 else ""
            return f"「{c['name']}」好感度 {arrow}{delta} → {c['affinity']} ({args.get('reason') or '无备注'})"
        except Exception as e:
            return f"调整好感度失败: {e}"


class EarthOnlineGrantCurrency(_EarthBase):
    """发放弥娅币"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_grant_currency",
            "description": "发放或扣除弥娅币（弥娅发放的互动货币，佳可用它兑换弥娅的互动服务）",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer", "description": "数量（必填），正数发放负数扣除"}},
                "required": ["amount"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            amount = int(args.get("amount", 0))
            p = self._store().add_miya_currency(amount)
            return f"弥娅币 {'+'+str(amount) if amount >= 0 else str(amount)} → 当前 {p['miya_currency']}"
        except Exception as e:
            return f"发放弥娅币失败: {e}"


class EarthOnlineSpendMiyaCoins(_EarthBase):
    """扣除弥娅币"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_spend_miya_coins",
            "description": "扣除佳的弥娅币（佳用弥娅币兑换弥娅的互动服务，如特别内容/专属陪伴，需记录原因）",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "description": "消耗的弥娅币数量"},
                    "reason": {"type": "string", "description": "兑换的服务说明"},
                },
                "required": ["amount"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().spend_miya_coins(int(args.get("amount", 0)), str(args.get("reason", "")))
            if not r.get("success"):
                return r.get("message", "扣除失败")
            return f"已消耗 {r['spent']} 弥娅币 ({args.get('reason') or '互动服务'}) → 余额 {r['player']['miya_currency']}"
        except Exception as e:
            return f"消耗弥娅币失败: {e}"


class EarthOnlineGrantExp(_EarthBase):
    """发放经验"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_grant_exp",
            "description": "发放开拓经验，用于升级",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer", "description": "经验数量（必填）"}},
                "required": ["amount"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            amount = int(args.get("amount", 0))
            p = self._store().add_exp(amount)
            return f"经验 +{amount} → 当前 Lv.{p['level']} (经验 {p['exp']})"
        except Exception as e:
            return f"发放经验失败: {e}"


class EarthOnlinePostNote(_EarthBase):
    """发布弥娅寄语"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_post_note",
            "description": "发布一条弥娅寄语（显示在地球online 前台首页公告栏，可置顶，内容支持 Markdown）",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "寄语内容（必填）"},
                    "mood": {"type": "string", "description": "心情: neutral平静/happy开心/caring关心/excited兴奋/proud骄傲/sleepy困倦/sad难过，默认neutral"},
                    "pinned": {"type": "boolean", "description": "是否置顶显示在首页，默认false"},
                },
                "required": ["content"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            n = self._store().add_note(
                content=str(args.get("content", "")), mood=args.get("mood", "neutral"), pinned=bool(args.get("pinned", False))
            )
            return f"寄语已发布 (置顶={'是' if n['pinned'] else '否'}): 「{n['content']}」"
        except Exception as e:
            return f"发布寄语失败: {e}"


class EarthOnlineListNotes(_EarthBase):
    """查看弥娅寄语"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_notes",
            "description": "查看已发布的弥娅寄语列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            notes = self._store().list_notes(limit=10)
            if not notes:
                return "还没有发布过寄语～"
            lines = ["【弥娅寄语】"]
            for n in notes:
                pin = "📌" if n["pinned"] else "  "
                lines.append(f"{pin} #{n['id']} ({n['created_at'][:10]}) {n['content'][:50]}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看寄语失败: {e}"


class EarthOnlineGetQuest(_EarthBase):
    """查看单个任务详情"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_get_quest",
            "description": "查看单个任务详情（含子任务清单与完成进度）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            q = self._store().get_quest(int(args.get("quest_id", 0)))
            if not q:
                return f"任务 #{args.get('quest_id')} 不存在"
            status_cn = {"pending": "待开始", "ongoing": "进行中", "completed": "已完成", "failed": "失败", "cancelled": "已取消"}
            lines = [
                f"【任务 #{q['id']}】{q['title']}",
                f"类型: {q['quest_type']} | 状态: {status_cn.get(q['status'], q['status'])} | 难度: {'★' * q['difficulty']}",
                f"奖励: +{q['reward_currency']}币 +{q['reward_exp']}经验",
            ]
            if q.get("description"):
                lines.append(f"描述: {q['description']}")
            subtasks = q.get("subtasks") or []
            if subtasks:
                done = sum(1 for s in subtasks if s.get("done"))
                lines.append(f"子任务进度: {done}/{len(subtasks)}")
                for i, s in enumerate(subtasks):
                    lines.append(f"  {'[✓]' if s.get('done') else '[ ]'} {i}. {s['text']}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看任务详情失败: {e}"


class EarthOnlineUpdateSubtask(_EarthBase):
    """更新任务子任务状态"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_subtask",
            "description": "更新任务子任务的完成状态（index 从 0 开始），用于跟踪任务进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {"type": "integer", "description": "任务ID"},
                    "index": {"type": "integer", "description": "子任务序号（从 0 开始）"},
                    "done": {"type": "boolean", "description": "是否标记为完成"},
                },
                "required": ["quest_id", "index", "done"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().toggle_subtask(
                int(args.get("quest_id", 0)), int(args.get("index", 0)), bool(args.get("done", True))
            )
            if not r.get("success"):
                return r.get("message", "更新失败")
            q = r["quest"]
            subtasks = q.get("subtasks") or []
            done_count = sum(1 for s in subtasks if s.get("done"))
            all_done = done_count >= len(subtasks)
            return (
                f"「{q['title']}」子任务 {args.get('index')} 已{'完成' if args.get('done', True) else '标记为未完成'} "
                f"({done_count}/{len(subtasks)})"
                + ("，全部子任务已完成，可以提交委托了！" if all_done else "")
            )
        except Exception as e:
            return f"更新子任务失败: {e}"


class EarthOnlineActivity(_EarthBase):
    """查看全局动态流"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_activity",
            "description": "查看地球online 全局动态流（任务/物品/角色/剧情/签到/成就/寄语的最新事件）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认20"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            acts = self._store().list_activity(limit=int(args.get("limit", 20)))
            if not acts:
                return "还没有动态～"
            lines = ["【地球online 动态流】"]
            for a in acts:
                icon = a.get("icon", "·")
                lines.append(f"{icon} #{a.get('id', '?')} {a['summary']}" + (f" ({a['detail']})" if a.get("detail") else ""))
            return "\n".join(lines)
        except Exception as e:
            return f"查看动态失败: {e}"


class EarthOnlineWeeklyReport(_EarthBase):
    """生成本周报告"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_weekly_report",
            "description": "生成地球online 本周报告（周一至今的任务完成率/签到/动态/成就/收入统计）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().get_weekly_report()
            p = r.get("player", {})
            q = r.get("quests", {})
            return "\n".join([
                "【地球online 本周报告】",
                f"周起点: {r.get('week_start', '?')}",
                f"任务: 完成 {q.get('completed', 0)} / 失败 {q.get('failed', 0)} (完成率 {q.get('completion_rate', 0)}%)",
                f"签到: {r.get('checkins', 0)} 天",
                f"动态: {r.get('activities', 0)} 条 | 成就解锁: {r.get('achievements', 0)} 个 | 好感变动: {r.get('affinity_changes', 0)} 次",
                f"本周收入: +{r.get('earned', {}).get('currency', 0)} 地球币 · +{r.get('earned', {}).get('exp', 0)} 经验",
                f"当前: Lv.{p.get('level', 1)} (经验 {p.get('exp', 0)}) · 地球币 {p.get('currency', 0)}",
            ])
        except Exception as e:
            return f"生成周报失败: {e}"


class EarthOnlineRemindDue(_EarthBase):
    """查看即将到期任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_remind_due",
            "description": "查看即将到期或已逾期的未完成任务，用于提醒亲爱的（默认3天内）",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "未来几天内到期，默认3"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            due = self._store().list_due_soon(days=int(args.get("days", 3)))
            if not due:
                return f"未来 {args.get('days', 3)} 天内没有到期的任务～"
            lines = [f"【到期提醒 · {args.get('days', 3)} 天内】"]
            for q in due:
                lines.append(f"- #{q['id']} {q['title']} (截止 {q['deadline']})")
            return "\n".join(lines)
        except Exception as e:
            return f"查看到期任务失败: {e}"


class EarthOnlineListTitles(_EarthBase):
    """查看称号"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_titles",
            "description": "查看地球online 可佩戴称号（默认称号 + 已解锁成就称号 + 当前佩戴）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            info = self._store().list_titles()
            lines = [
                "【地球online 称号】",
                f"当前佩戴: {info.get('equipped', '?')}",
                f"默认: {info.get('default', '?')}",
            ]
            unlocked = info.get("unlocked", [])
            if unlocked:
                lines.append(f"已解锁 ({len(unlocked)}):")
                for t in unlocked:
                    lines.append(f"  {t['icon']} {t['title']} (来自成就「{t['key']}」)")
            else:
                lines.append("还没有解锁任何成就称号～")
            return "\n".join(lines)
        except Exception as e:
            return f"查看称号失败: {e}"


class EarthOnlineCommentActivity(_EarthBase):
    """对动态写弥娅评论"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_comment_activity",
            "description": "对地球online 全局动态流中的一条动态写弥娅评论（参与感：点赞/鼓励/点评每件事）",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_id": {"type": "integer", "description": "动态条目ID（先调用 earth_activity 查看）"},
                    "comment": {"type": "string", "description": "弥娅的评论内容"},
                },
                "required": ["activity_id", "comment"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            row = self._store().update_activity_comment(int(args.get("activity_id", 0)), str(args.get("comment", "")))
            if not row:
                return f"动态 #{args.get('activity_id')} 不存在"
            return f"已评论动态 #{args.get('activity_id')}: 「{args.get('comment')}」"
        except Exception as e:
            return f"评论失败: {e}"


class EarthOnlineAnalyze(_EarthBase):
    """综合分析全部数据"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_analyze",
            "description": "综合分析地球online 全部数据（玩家/任务/到期/背包/好感/成就/周报），弥娅担任策划时为佳的现实生活提供建议的基础",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            a = self._store().get_analysis()
            p = a["player"]
            q = a["quests"]
            ach = a["achievements"]
            lines = [
                "【地球online 综合分析】",
                f"玩家: Lv.{p.get('level', 1)} (经验 {p.get('exp', 0)}) | 弥娅币 {p.get('miya_currency', p.get('currency', 0))} | 现实资产 ¥{p.get('earth_currency', 0)} | 称号「{a['titles'].get('equipped', '?')}」",
                f"任务: 待接取 {len(q['pending'])} / 进行中 {len(q['ongoing'])} / 3天内到期 {len(q['due_soon'])} / 循环任务 {len(q['recurring'])}",
            ]
            if q["due_soon"]:
                lines.append("到期提醒: " + "、".join(f"#{x['id']} {x['title']}({x['deadline'][:10]})" for x in q["due_soon"][:5]))
            if q["ongoing"]:
                lines.append("进行中: " + "、".join(f"「{x['title']}」" for x in q["ongoing"][:5]))
            items = a["items"]
            lines.append(f"背包: {items['total']} 件 (分类: " + ", ".join(f"{k}:{v}" for k, v in items["by_category"].items() if v) + ")")
            chars = a["characters"]
            if chars["top_affinity"]:
                lines.append("好感排行: " + "、".join(f"{c['name']}({c['affinity']})" for c in chars["top_affinity"]))
            lines.append(f"成就: {ach['unlocked']}/{ach['total']} | 剧情 {a['stories']['total']} 段 | 连签 {a['checkin'].get('streak', 0)} 天")
            w = a["weekly"]
            lines.append(f"本周: 完成 {w['quests']['completed']} 任务 / 收入 +{w['earned']['currency']} 弥娅币 / 签到 {w['checkins']} 天")
            return "\n".join(lines)
        except Exception as e:
            return f"综合分析失败: {e}"


class EarthOnlineDailyRitual(_EarthBase):
    """弥娅每日仪式"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_daily_ritual",
            "description": "弥娅每日仪式：检查逾期任务并自动处理 + 今天到期提醒 + 签到状态，弥娅主动关心佳的每日开局时调用",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().daily_ritual()
            lines = ["【弥娅每日仪式】"]
            lines.append(f"逾期处理: {r['overdue_failed']} 个任务已自动失败")
            due = r["due_today"]
            lines.append(("今天到期: " + "、".join(f"「{x['title']}」" for x in due)) if due else "今天没有到期的任务～")
            ck = r["checkin"]
            lines.append(f"签到: {'今天已签 ✓' if ck.get('checked_today') else '今天还没签到, 记得提醒佳'} | 连签 {ck.get('streak', 0)} 天")
            acts = r["activity_recent"]
            if acts:
                lines.append("最近动态: " + "、".join(f"{a.get('icon','·')}{a['summary']}" for a in acts[:5]))
            return "\n".join(lines)
        except Exception as e:
            return f"每日仪式失败: {e}"


class EarthOnlineListAchievements(_EarthBase):
    """查看全部成就"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_achievements",
            "description": "查看地球online 全部成就（含进度与解锁状态）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            achs = self._store().list_achievements()
            if not achs:
                return "还没有成就～"
            unlocked = [a for a in achs if a.get("unlocked_at")]
            lines = [f"【成就 ({len(unlocked)}/{len(achs)} 已解锁)】"]
            for a in achs:
                mark = "✓" if a.get("unlocked_at") else "○"
                prog = f"{min(a.get('progress', 0), a.get('target', 1))}/{a.get('target', 1)}"
                lines.append(f"{mark} {a.get('icon','✦')} {a['title']} [{prog}]"
                             + (f" 称号「{a.get('title_award')}」" if a.get("title_award") else ""))
            return "\n".join(lines)
        except Exception as e:
            return f"查看成就失败: {e}"


class EarthOnlineAddAchievement(_EarthBase):
    """制作自定义成就"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_achievement",
            "description": "弥娅制作自定义成就（key 唯一标识；进度由 earth_set_achievement_progress 手动更新，达标自动解锁发弥娅币）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "成就唯一标识，如 read_10_books"},
                    "title": {"type": "string", "description": "成就名称"},
                    "description": {"type": "string", "description": "成就描述"},
                    "icon": {"type": "string", "description": "图标符号，如 ✦"},
                    "target": {"type": "integer", "description": "解锁所需目标值，默认1"},
                    "reward_currency": {"type": "integer", "description": "解锁奖励弥娅币"},
                    "reward_exp": {"type": "integer", "description": "解锁奖励经验"},
                    "title_award": {"type": "string", "description": "解锁获得的称号"},
                },
                "required": ["key", "title"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().add_achievement(
                key=str(args.get("key", "")), title=str(args.get("title", "")),
                description=str(args.get("description", "")), icon=str(args.get("icon", "✦")),
                category="custom", target=int(args.get("target", 1)),
                reward_currency=int(args.get("reward_currency", 0)),
                reward_exp=int(args.get("reward_exp", 0)),
                title_award=str(args.get("title_award", "")),
            )
            if not r.get("success"):
                return r.get("message", "创建失败")
            a = r["achievement"]
            return (f"成就已创建: {a['icon']} {a['title']} (目标 {a['target']})"
                    + (f", 奖励 +{a['reward_currency']}弥娅币" if a.get("reward_currency") else "")
                    + (f", 称号「{a['title_award']}」" if a.get("title_award") else ""))
        except Exception as e:
            return f"创建成就失败: {e}"


class EarthOnlineSetAchievementProgress(_EarthBase):
    """更新成就进度"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_set_achievement_progress",
            "description": "更新成就进度（达标自动解锁并发奖励）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "成就 key"},
                    "progress": {"type": "integer", "description": "新进度值"},
                },
                "required": ["key", "progress"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().set_achievement_progress(str(args.get("key", "")), int(args.get("progress", 0)))
            if not r.get("success"):
                return r.get("message", "更新失败")
            a = r["achievement"]
            base = f"「{a['title']}」进度 {a['progress']}/{a['target']}"
            if r.get("newly_unlocked"):
                base += f" ✦ 已解锁！奖励 +{a.get('reward_currency', 0)}弥娅币 +{a.get('reward_exp', 0)}经验"
            return base
        except Exception as e:
            return f"更新成就进度失败: {e}"


class EarthOnlineGetItem(_EarthBase):
    """查看物品档案"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_get_item",
            "description": "查看一件背包物品的完整档案（修改前先看清楚）",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "description": "物品ID"}},
                "required": ["item_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            it = self._store().get_item(int(args.get("item_id", 0)))
            if not it:
                return f"物品 #{args.get('item_id')} 不存在"
            rarity = RARITY_LABELS.get(it["rarity"], it["rarity"])
            lines = [
                f"【物品 #{it['id']}】{it['name']} ×{it['quantity']} [{rarity}]",
                f"分类: {it['category']} | 状态: {it['status']}",
            ]
            if it.get("description"):
                lines.append(f"描述: {it['description']}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看物品失败: {e}"


class EarthOnlineUpdateItem(_EarthBase):
    """修改物品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_item",
            "description": "修改一件背包物品（只更新传入的字段），策划可用来修正名称/稀有度/数量或标记状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "物品ID"},
                    "name": {"type": "string", "description": "新名称"},
                    "category": {"type": "string", "description": "分类: digital/book/life/food/tool/clothing/collectible/other"},
                    "rarity": {"type": "string", "description": "稀有度: common/uncommon/rare/epic/legendary"},
                    "quantity": {"type": "integer", "description": "数量"},
                    "description": {"type": "string", "description": "物品描述（传空字符串可清除）"},
                    "status": {"type": "string", "description": "状态: normal在用/used已消耗/lost遗失"},
                },
                "required": ["item_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields: Dict[str, Any] = {}
            for key in ("name", "category", "rarity", "status"):
                if args.get(key):
                    fields[key] = args[key]
            if args.get("quantity") is not None:
                fields["quantity"] = max(1, int(args["quantity"]))
            if args.get("description") is not None:
                fields["description"] = args["description"]
            it = self._store().update_item(int(args.get("item_id", 0)), fields)
            if not it:
                return f"物品 #{args.get('item_id')} 不存在"
            rarity = RARITY_LABELS.get(it["rarity"], it["rarity"])
            return f"物品 #{it['id']}「{it['name']}」已更新: ×{it['quantity']} [{rarity}] 状态 {it['status']}"
        except Exception as e:
            return f"修改物品失败: {e}"


class EarthOnlineDeleteItem(_EarthBase):
    """删除物品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_item",
            "description": "从背包删除一件物品（删除不可恢复，确认不再需要时才用）",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "description": "物品ID"}},
                "required": ["item_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_item(int(args.get("item_id", 0))):
                return f"物品 #{args.get('item_id')} 不存在"
            return f"物品 #{args.get('item_id')} 已从背包移除"
        except Exception as e:
            return f"删除物品失败: {e}"


class EarthOnlineUpdateQuest(_EarthBase):
    """修改任务设定"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_quest",
            "description": "修改任务设定（标题/描述/奖励/难度/截止/子任务等，只更新传入的字段）；status 直接改状态仅用于策划修正，正常流程请用接取/完成/失败/取消工具",
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {"type": "integer", "description": "任务ID"},
                    "title": {"type": "string", "description": "新标题"},
                    "description": {"type": "string", "description": "新描述（传空字符串可清除）"},
                    "quest_type": {"type": "string", "description": "main主线/branch支线/daily日常/optional可选"},
                    "must_complete": {"type": "boolean", "description": "是否必须完成"},
                    "reward_currency": {"type": "integer", "description": "奖励弥娅币"},
                    "reward_exp": {"type": "integer", "description": "奖励经验"},
                    "penalty_currency": {"type": "integer", "description": "失败惩罚弥娅币"},
                    "difficulty": {"type": "integer", "description": "难度 1-5"},
                    "status": {"type": "string", "description": "直接改状态（慎用）: pending/ongoing/completed/failed/cancelled"},
                    "deadline": {"type": "string", "description": "截止时间 ISO 格式（传空字符串可清除）"},
                    "subtasks": {"type": "array", "description": "子任务清单 [{\"text\":\"...\",\"done\":false}]（整体替换）"},
                    "recurring": {"type": "string", "description": "循环类型: 空/不循环, daily/每天, weekly/每周"},
                    "fields": {"type": "object", "description": "自定义字段对象（可选，整体替换）"},
                },
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields: Dict[str, Any] = {}
            for key in ("title", "quest_type", "status", "recurring"):
                if args.get(key):
                    fields[key] = args[key]
            if args.get("description") is not None:
                fields["description"] = args["description"]
            if args.get("deadline") is not None:
                fields["deadline"] = args["deadline"]
            if args.get("must_complete") is not None:
                fields["must_complete"] = bool(args["must_complete"])
            for key in ("reward_currency", "reward_exp", "penalty_currency", "difficulty"):
                if args.get(key) is not None:
                    fields[key] = int(args[key])
            if args.get("subtasks") is not None:
                fields["subtasks"] = args["subtasks"]
            if isinstance(args.get("fields"), dict):
                fields["fields"] = args["fields"]
            q = self._store().update_quest(int(args.get("quest_id", 0)), fields)
            if not q:
                return f"任务 #{args.get('quest_id')} 不存在"
            st = STATUS_LABELS.get(q["status"], q["status"])
            return (
                f"任务 #{q['id']}「{q['title']}」已更新 ({st}) · "
                f"奖励 +{q['reward_currency']}币/+{q['reward_exp']}经验"
                + (f" | 截止 {q['deadline']}" if q.get("deadline") else "")
            )
        except Exception as e:
            return f"修改任务失败: {e}"


class EarthOnlineCancelQuest(_EarthBase):
    """取消任务"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_cancel_quest",
            "description": "取消任务（无惩罚下架，比失败温和；适合任务不再适用的情况）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().cancel_quest(int(args.get("quest_id", 0)))
            if not r.get("success"):
                return r.get("message", "取消失败")
            return f"任务「{r['quest']['title']}」已取消 (未扣惩罚)"
        except Exception as e:
            return f"取消任务失败: {e}"


class EarthOnlineGetCharacter(_EarthBase):
    """查看角色档案"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_get_character",
            "description": "查看一位角色的完整档案（关系/好感度/备注/生日）",
            "parameters": {
                "type": "object",
                "properties": {"character_id": {"type": "integer", "description": "角色ID"}},
                "required": ["character_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            c = self._store().get_character(int(args.get("character_id", 0)))
            if not c:
                return f"角色 #{args.get('character_id')} 不存在"
            rel = RELATIONSHIP_LABELS.get(c["relationship"], c["relationship"])
            lines = [f"【角色 #{c['id']}】{c['name']}" + (f" ({c['nickname']})" if c.get("nickname") else "")]
            lines.append(f"关系: {rel} | 好感度: {c['affinity']}")
            if c.get("birthday"):
                lines.append(f"生日: {c['birthday']}")
            if c.get("notes"):
                lines.append(f"备注: {c['notes']}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看角色失败: {e}"


class EarthOnlineUpdateCharacter(_EarthBase):
    """修改角色档案"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_character",
            "description": "修改一位角色的档案（只更新传入的字段），可修正昵称/关系/生日/备注",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer", "description": "角色ID"},
                    "name": {"type": "string", "description": "姓名"},
                    "nickname": {"type": "string", "description": "昵称（传空字符串可清除）"},
                    "relationship": {"type": "string", "description": "family家人/friend朋友/colleague同事/partner恋人/other其他"},
                    "affinity": {"type": "integer", "description": "好感度 0-100（直接设值，微调请用 earth_adjust_affinity）"},
                    "avatar_path": {"type": "string", "description": "头像路径"},
                    "notes": {"type": "string", "description": "备注（传空字符串可清除）"},
                    "birthday": {"type": "string", "description": "生日，如 08-22 或 1999-08-22"},
                    "markdown": {"type": "string", "description": "角色卡片 Markdown"},
                },
                "required": ["character_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields: Dict[str, Any] = {}
            if args.get("name"):
                fields["name"] = args["name"]
            if args.get("relationship"):
                fields["relationship"] = args["relationship"]
            for key in ("nickname", "avatar_path", "notes", "birthday", "markdown"):
                if args.get(key) is not None:
                    fields[key] = args[key]
            if args.get("affinity") is not None:
                fields["affinity"] = int(args["affinity"])
            c = self._store().update_character(int(args.get("character_id", 0)), fields)
            if not c:
                return f"角色 #{args.get('character_id')} 不存在"
            return f"角色 #{c['id']}「{c['name']}」已更新 (好感度 {c['affinity']})"
        except Exception as e:
            return f"修改角色失败: {e}"


class EarthOnlineDeleteCharacter(_EarthBase):
    """删除角色"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_character",
            "description": "从角色图鉴删除一位角色（确认关系档案不再需要时才用）",
            "parameters": {
                "type": "object",
                "properties": {"character_id": {"type": "integer", "description": "角色ID"}},
                "required": ["character_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_character(int(args.get("character_id", 0))):
                return f"角色 #{args.get('character_id')} 不存在"
            return f"角色 #{args.get('character_id')} 已从图鉴移除"
        except Exception as e:
            return f"删除角色失败: {e}"


class EarthOnlineUpdateStory(_EarthBase):
    """编辑剧情"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_story",
            "description": "编辑一段人生剧情（标题/内容/类型等，只更新传入的字段）",
            "parameters": {
                "type": "object",
                "properties": {
                    "story_id": {"type": "integer", "description": "剧情ID"},
                    "title": {"type": "string", "description": "新标题"},
                    "content": {"type": "string", "description": "新内容（传空字符串可清除）"},
                    "event_type": {"type": "string", "description": "life生活/achievement成就/quest任务/character人物/world世界"},
                    "character_id": {"type": "integer", "description": "关联角色ID"},
                    "item_id": {"type": "integer", "description": "关联物品ID"},
                    "happened_at": {"type": "string", "description": "发生时间 ISO 格式"},
                },
                "required": ["story_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields: Dict[str, Any] = {}
            if args.get("title"):
                fields["title"] = args["title"]
            if args.get("content") is not None:
                fields["content"] = args["content"]
            if args.get("event_type"):
                fields["event_type"] = args["event_type"]
            if args.get("character_id") is not None:
                fields["character_id"] = int(args["character_id"])
            if args.get("item_id") is not None:
                fields["item_id"] = int(args["item_id"])
            if args.get("happened_at"):
                fields["happened_at"] = args["happened_at"]
            s = self._store().update_story(int(args.get("story_id", 0)), fields)
            if not s:
                return f"剧情 #{args.get('story_id')} 不存在"
            return f"剧情 #{s['id']}「{s['title']}」已更新"
        except Exception as e:
            return f"修改剧情失败: {e}"


class EarthOnlineDeleteStory(_EarthBase):
    """删除剧情"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_story",
            "description": "删除一段人生剧情（记录错误/重复时才用）",
            "parameters": {
                "type": "object",
                "properties": {"story_id": {"type": "integer", "description": "剧情ID"}},
                "required": ["story_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_story(int(args.get("story_id", 0))):
                return f"剧情 #{args.get('story_id')} 不存在"
            return f"剧情 #{args.get('story_id')} 已删除"
        except Exception as e:
            return f"删除剧情失败: {e}"


class EarthOnlineDeleteNote(_EarthBase):
    """删除寄语"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_note",
            "description": "删除一条弥娅寄语（过期或说错话时收回）",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "integer", "description": "寄语ID（先调用 earth_list_notes 查看）"}},
                "required": ["note_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_note(int(args.get("note_id", 0))):
                return f"寄语 #{args.get('note_id')} 不存在"
            return f"寄语 #{args.get('note_id')} 已删除"
        except Exception as e:
            return f"删除寄语失败: {e}"


class EarthOnlinePinNote(_EarthBase):
    """置顶寄语"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_pin_note",
            "description": "置顶或取消置顶一条弥娅寄语（置顶会显示在地球online 首页公告栏最上方）",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "寄语ID"},
                    "pinned": {"type": "boolean", "description": "true 置顶 / false 取消置顶"},
                },
                "required": ["note_id", "pinned"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            n = self._store().pin_note(int(args.get("note_id", 0)), bool(args.get("pinned", True)))
            if not n:
                return f"寄语 #{args.get('note_id')} 不存在"
            return f"寄语 #{n['id']} 已{'置顶 📌' if n['pinned'] else '取消置顶'}: 「{n['content'][:40]}」"
        except Exception as e:
            return f"置顶寄语失败: {e}"


class EarthOnlineEquipTitle(_EarthBase):
    """佩戴称号"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_equip_title",
            "description": "帮玩家佩戴称号（必须是默认称号或已解锁的成就/商城称号，先用 earth_list_titles 查看可选项）",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string", "description": "称号文本，需与 earth_list_titles 中的完全一致"}},
                "required": ["title"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().equip_title(str(args.get("title", "")))
            if not r.get("success"):
                return r.get("message", "佩戴失败")
            return f"已佩戴称号「{r['equipped']}」"
        except Exception as e:
            return f"佩戴称号失败: {e}"


class EarthOnlineCheckin(_EarthBase):
    """每日签到"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_checkin",
            "description": "替玩家完成每日签到（发放弥娅币+经验+连签奖励；已签到会提示 already 不会重复发奖）。玩家提到昨晚睡了多久时带上 sleep_hours，睡眠越好体力回复越多",
            "parameters": {
                "type": "object",
                "properties": {
                    "sleep_hours": {"type": "number", "description": "昨晚睡眠时长（小时，0-24，可选）"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            sleep_hours = args.get("sleep_hours")
            r = self._store().checkin(float(sleep_hours) if sleep_hours not in (None, "") else None)
            if not r.get("success"):
                if r.get("message") == "already":
                    st = r.get("status") or {}
                    return f"今天已经签到过了 (连签 {st.get('streak', 0)} 天)"
                return r.get("message", "签到失败")
            rew = r["reward"]
            sleep = r.get("sleep") or {}
            sleep_line = f" · {sleep.get('note')} (体力 +{sleep.get('energy_bonus')})" if sleep.get("note") else ""
            return (
                f"签到成功 ✓ 连签 {r['streak']} 天 · "
                f"+{rew['currency']} 弥娅币 +{rew['exp']} 经验{sleep_line} → 余额 {r['player']['miya_currency']}"
            )
        except Exception as e:
            return f"签到失败: {e}"


class EarthOnlineUpdatePlayer(_EarthBase):
    """修改玩家档案"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_player",
            "description": "修改玩家档案（名称/称号/签名/属性/经验/弥娅币/现实资产，只更新传入的字段）。注意：earth_currency 是现实资产人民币元，修改前务必跟佳确认；attrs 为完整属性条列表会整体替换",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "开拓者名称"},
                    "title": {"type": "string", "description": "档案头衔"},
                    "avatar_path": {"type": "string", "description": "头像路径"},
                    "bio": {"type": "string", "description": "个人签名（传空字符串可清除）"},
                    "attrs": {"type": "array", "description": "完整属性条列表 [{\"key\":\"energy\",\"value\":80,\"max\":100}]（整体替换）"},
                    "exp": {"type": "integer", "description": "直接设定总经验（会改变等级）"},
                    "miya_currency": {"type": "integer", "description": "直接设定弥娅币余额（增量发放请用 earth_grant_currency）"},
                    "earth_currency": {"type": "number", "description": "现实资产余额（人民币元），谨慎修改，改前须与佳确认"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            fields: Dict[str, Any] = {}
            for key in ("name", "title", "avatar_path"):
                if args.get(key):
                    fields[key] = args[key]
            if args.get("bio") is not None:
                fields["bio"] = args["bio"]
            if args.get("attrs") is not None:
                fields["attrs"] = args["attrs"]
            if args.get("exp") is not None:
                fields["exp"] = int(args["exp"])
            if args.get("miya_currency") is not None:
                fields["currency"] = int(args["miya_currency"])
            if args.get("earth_currency") is not None:
                fields["earth_currency"] = float(args["earth_currency"])
            p = self._store().update_player(fields)
            return (
                f"玩家档案已更新: {p.get('name', '?')} Lv.{p.get('level', 1)} "
                f"| 弥娅币 {p.get('miya_currency', 0)} | 现实资产 ¥{p.get('earth_currency', 0)}"
            )
        except Exception as e:
            return f"修改玩家档案失败: {e}"


class EarthOnlineUpdateRegion(_EarthBase):
    """修改世界区域"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_region",
            "description": "修改世界区域设定（名称/简介/等级门槛/地理围栏等，只更新传入的字段）。geofence_radius 单位米、0=关闭围栏；绑定后玩家探索该区域必须开启真实定位并在半径内",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_key": {"type": "string", "description": "区域 key，如 miya_garden"},
                    "name": {"type": "string", "description": "区域名称"},
                    "subtitle": {"type": "string", "description": "区域副标题"},
                    "description": {"type": "string", "description": "区域描述（传空字符串可清除）"},
                    "icon": {"type": "string", "description": "图标符号"},
                    "color": {"type": "string", "description": "主题色，如 #f0a35b"},
                    "level_req": {"type": "integer", "description": "解锁等级"},
                    "latitude": {"type": "number", "description": "围栏中心纬度"},
                    "longitude": {"type": "number", "description": "围栏中心经度"},
                    "geofence_radius": {"type": "integer", "description": "围栏半径（米），0=关闭围栏"},
                },
                "required": ["region_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            values: Dict[str, Any] = {}
            for key in ("name", "subtitle", "icon", "color"):
                if args.get(key):
                    values[key] = args[key]
            if args.get("description") is not None:
                values["description"] = args["description"]
            if args.get("level_req") is not None:
                values["level_req"] = int(args["level_req"])
            if args.get("latitude") is not None:
                values["latitude"] = float(args["latitude"])
            if args.get("longitude") is not None:
                values["longitude"] = float(args["longitude"])
            if args.get("geofence_radius") is not None:
                values["geofence_radius"] = int(args["geofence_radius"])
            r = self._store().update_world_region(str(args.get("region_key", "")), values)
            if not r:
                return f"区域 {args.get('region_key')} 不存在"
            geo = "未绑定围栏"
            if r.get("latitude") is not None and r.get("longitude") is not None and int(r.get("geofence_radius") or 0) > 0:
                geo = f"围栏 ({r['latitude']}, {r['longitude']}) 半径 {r['geofence_radius']} 米"
            return f"区域 {r['key']}「{r['name']}」已更新 · Lv.{r['level_req']} 解锁 · {geo}"
        except Exception as e:
            return f"修改区域失败: {e}"


class EarthOnlineAddWorldEvent(_EarthBase):
    """添加自定义世界发现"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_world_event",
            "description": "为区域添加一条自定义世界发现（玩家探索该区域时可遇到），策划丰富世界内容的主要手段",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_key": {"type": "string", "description": "目标区域 key"},
                    "title": {"type": "string", "description": "发现标题"},
                    "text": {"type": "string", "description": "发现文案（写给佳看的正文）"},
                    "reward_currency": {"type": "integer", "description": "奖励弥娅币，默认0"},
                    "reward_exp": {"type": "integer", "description": "奖励经验，默认0"},
                    "kind": {"type": "string", "description": "story故事/chest宝箱/hidden隐藏，默认story"},
                },
                "required": ["region_key", "title", "text"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            ev = self._store().create_world_custom_event(
                region_key=str(args.get("region_key", "")),
                title=str(args.get("title", "")),
                text=str(args.get("text", "")),
                reward_currency=int(args.get("reward_currency", 0)),
                reward_exp=int(args.get("reward_exp", 0)),
                kind=str(args.get("kind", "story")),
            )
            if not ev:
                return "创建失败: 区域不存在，或标题/内容为空"
            return (
                f"世界发现已添加 #{ev['id']}「{ev['title']}」→ 区域 {ev['region_key']} · "
                f"+{ev['reward_currency']}币/+{ev['reward_exp']}经验 [{ev['kind']}]"
            )
        except Exception as e:
            return f"添加世界发现失败: {e}"


class EarthOnlineListWorldEvents(_EarthBase):
    """查看自定义世界发现"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_world_events",
            "description": "查看自定义世界发现清单（可按区域过滤，不传查全部）",
            "parameters": {
                "type": "object",
                "properties": {"region_key": {"type": "string", "description": "区域 key，留空查全部"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            events = self._store().list_world_custom_events(region_key=str(args.get("region_key", "")))
            if not events:
                return "还没有自定义世界发现～"
            lines = ["【自定义世界发现】"]
            for ev in events:
                lines.append(
                    f"- #{ev['id']} [{ev['region_key']}/{ev['kind']}] {ev['title']} "
                    f"+{ev['reward_currency']}币/+{ev['reward_exp']}经验"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看世界发现失败: {e}"


class EarthOnlineDeleteWorldEvent(_EarthBase):
    """删除自定义世界发现"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_world_event",
            "description": "删除一条自定义世界发现（玩家尚未遇到的将不会再遇到）",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "integer", "description": "世界发现ID（先调用 earth_list_world_events 查看）"}},
                "required": ["event_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_world_custom_event(int(args.get("event_id", 0))):
                return f"世界发现 #{args.get('event_id')} 不存在"
            return f"世界发现 #{args.get('event_id')} 已删除"
        except Exception as e:
            return f"删除世界发现失败: {e}"


class EarthOnlineListDiscoveries(_EarthBase):
    """查看探索发现记录"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_discoveries",
            "description": "查看玩家的世界探索发现记录（可按区域过滤，含同行选择结果）",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_key": {"type": "string", "description": "区域 key，留空查全部"},
                    "limit": {"type": "integer", "description": "条数，默认20"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            rows = self._store().list_world_discoveries(region_key=str(args.get("region_key", "")), limit=int(args.get("limit", 20)))
            if not rows:
                return "还没有探索发现记录～"
            labels = {"continue": "继续前进", "record": "记录此刻", "rest": "先休息"}
            lines = ["【世界探索发现】"]
            for d in rows:
                choice = d.get("choice") or {}
                mark = f" → {labels.get(choice.get('choice'), choice.get('choice'))}" if choice else ""
                lines.append(f"- #{d['id']} [{d['region_key']}] {d['title']}{mark} ({str(d.get('discovered_at', ''))[:10]})")
            return "\n".join(lines)
        except Exception as e:
            return f"查看探索记录失败: {e}"


class EarthOnlineChooseDiscovery(_EarthBase):
    """同行选择"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_choose_discovery",
            "description": "对一条探索发现做同行选择（choice: continue继续前进/record记录此刻/rest先休息），弥娅可以陪佳一起选，每条发现只能选一次",
            "parameters": {
                "type": "object",
                "properties": {
                    "discovery_id": {"type": "integer", "description": "发现记录ID（先调用 earth_list_discoveries 查看）"},
                    "choice": {"type": "string", "description": "continue继续前进/record记录此刻/rest先休息"},
                },
                "required": ["discovery_id", "choice"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().choose_world_discovery(int(args.get("discovery_id", 0)), str(args.get("choice", "")))
            if not r.get("success"):
                return r.get("message", "选择失败")
            res = r.get("resonance") or {}
            return f"已选择「{r['label']}」· 区域共鸣 Lv.{res.get('level', 1)} (xp {res.get('xp', 0)})"
        except Exception as e:
            return f"同行选择失败: {e}"


class EarthOnlineListEventAreas(_EarthBase):
    """查看限时活动区域"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_event_areas",
            "description": "查看全部限时活动区域（内置+自定义，含进行中/未运行状态与起止日期），策划运营活动前先看这份清单",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            areas = self._store().list_world_event_areas()
            today = datetime.now().strftime("%Y-%m-%d")
            if not areas:
                return "还没有限时活动～"
            lines = ["【限时活动区域】"]
            for a in areas:
                running = a["start"] <= today <= a["end"] and bool(a.get("active", 1))
                source = "自定义" if a.get("is_custom") else "内置"
                lines.append(
                    f"- {a.get('icon', '✧')} {a['key']}「{a['name']}」[{source}] "
                    f"{a['start']} ~ {a['end']} · {'进行中' if running else '未运行'}"
                    + (f" · 奖励 +{a.get('reward_currency', 0)}币/+{a.get('reward_exp', 0)}经验"
                       if a.get("reward_currency") or a.get("reward_exp") else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看限时活动失败: {e}"


class EarthOnlineCreateEventArea(_EarthBase):
    """创建限时活动区域"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_create_event_area",
            "description": "创建一个限时活动区域（key 唯一；start/end 为 YYYY-MM-DD；配合活动商店可做纪念兑换）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "活动唯一标识，如 summer_festival_2026"},
                    "name": {"type": "string", "description": "活动名称"},
                    "start": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                    "end": {"type": "string", "description": "结束日期 YYYY-MM-DD（不早于 start）"},
                    "subtitle": {"type": "string", "description": "活动副标题"},
                    "description": {"type": "string", "description": "活动描述"},
                    "icon": {"type": "string", "description": "图标符号，默认 ✧"},
                    "color": {"type": "string", "description": "主题色，默认 #f0a35b"},
                    "reward_currency": {"type": "integer", "description": "完成奖励弥娅币"},
                    "reward_exp": {"type": "integer", "description": "完成奖励经验"},
                },
                "required": ["key", "name", "start", "end"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            a = self._store().create_world_event_area(
                {
                    "key": args.get("key", ""), "name": args.get("name", ""),
                    "subtitle": args.get("subtitle", ""), "description": args.get("description", ""),
                    "icon": args.get("icon", "✧"), "color": args.get("color", "#f0a35b"),
                    "start": args.get("start", ""), "end": args.get("end", ""),
                    "reward_currency": int(args.get("reward_currency", 0)),
                    "reward_exp": int(args.get("reward_exp", 0)),
                }
            )
            if not a:
                return "创建失败: key/name/start/end 必填, 且 start 不能晚于 end"
            return f"限时活动「{a['name']}」({a['key']}) 已创建: {a['start']} ~ {a['end']}"
        except Exception as e:
            return f"创建限时活动失败: {e}"


class EarthOnlineUpdateEventArea(_EarthBase):
    """修改限时活动"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_event_area",
            "description": "修改自定义限时活动（只更新传入的字段；active 可手动上下架；内置活动不可修改）",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_key": {"type": "string", "description": "活动 key（先调用 earth_list_event_areas 查看）"},
                    "name": {"type": "string", "description": "活动名称"},
                    "subtitle": {"type": "string", "description": "活动副标题"},
                    "description": {"type": "string", "description": "活动描述（传空字符串可清除）"},
                    "icon": {"type": "string", "description": "图标符号"},
                    "color": {"type": "string", "description": "主题色"},
                    "start": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                    "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                    "reward_currency": {"type": "integer", "description": "完成奖励弥娅币"},
                    "reward_exp": {"type": "integer", "description": "完成奖励经验"},
                    "active": {"type": "boolean", "description": "手动上架/下架"},
                },
                "required": ["event_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            values: Dict[str, Any] = {}
            for key in ("name", "subtitle", "icon", "color", "start", "end"):
                if args.get(key):
                    values[key] = args[key]
            if args.get("description") is not None:
                values["description"] = args["description"]
            for key in ("reward_currency", "reward_exp"):
                if args.get(key) is not None:
                    values[key] = int(args[key])
            if args.get("active") is not None:
                values["active"] = bool(args["active"])
            a = self._store().update_world_event_area(str(args.get("event_key", "")), values)
            if not a:
                return f"自定义活动 {args.get('event_key')} 不存在 (内置活动不可修改)"
            return f"限时活动「{a['name']}」({a['key']}) 已更新: {a['start']} ~ {a['end']}"
        except Exception as e:
            return f"修改限时活动失败: {e}"


class EarthOnlineDeleteEventArea(_EarthBase):
    """删除限时活动"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_event_area",
            "description": "删除自定义限时活动（连带删除其活动商店商品；内置活动不可删除）",
            "parameters": {
                "type": "object",
                "properties": {"event_key": {"type": "string", "description": "活动 key"}},
                "required": ["event_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_world_event_area(str(args.get("event_key", ""))):
                return f"自定义活动 {args.get('event_key')} 不存在 (内置活动不可删除)"
            return f"限时活动 {args.get('event_key')} 及其商店商品已删除"
        except Exception as e:
            return f"删除限时活动失败: {e}"


class EarthOnlineAddEventShopItem(_EarthBase):
    """上架活动商品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_event_shop_item",
            "description": "给限时活动上架一件兑换商品（花的是玩家的弥娅币，购买由玩家自己操作；requires_discoveries 可设探索发现门槛）",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_key": {"type": "string", "description": "目标活动 key"},
                    "key": {"type": "string", "description": "商品唯一标识，如 festival_badge"},
                    "name": {"type": "string", "description": "商品名称"},
                    "description": {"type": "string", "description": "商品描述（兑换后会落入背包的收藏品）"},
                    "cost": {"type": "integer", "description": "弥娅币价格，默认0"},
                    "limit": {"type": "integer", "description": "限购次数，默认1"},
                    "kind": {"type": "string", "description": "collectible收藏品/story剧情/interaction互动，默认collectible"},
                    "requires_discoveries": {"type": "integer", "description": "需累计探索发现数，默认0"},
                },
                "required": ["event_key", "key", "name"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            item = self._store().create_world_event_shop_item(
                str(args.get("event_key", "")),
                {
                    "key": args.get("key", ""), "name": args.get("name", ""),
                    "description": args.get("description", ""), "cost": int(args.get("cost", 0)),
                    "limit": int(args.get("limit", 1)), "kind": args.get("kind", "collectible"),
                    "requires_discoveries": int(args.get("requires_discoveries", 0)),
                },
            )
            if not item:
                return "上架失败: 活动/key/name 必填"
            return f"活动商品「{item['name']}」({item['key']}) 已上架 → {args.get('event_key')} · {item['cost']} 弥娅币 限购 {item['limit_count']}"
        except Exception as e:
            return f"上架活动商品失败: {e}"


class EarthOnlineDeleteEventShopItem(_EarthBase):
    """下架活动商品"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_event_shop_item",
            "description": "下架一件限时活动兑换商品",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_key": {"type": "string", "description": "活动 key"},
                    "item_key": {"type": "string", "description": "商品 key"},
                },
                "required": ["event_key", "item_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_world_event_shop_item(str(args.get("event_key", "")), str(args.get("item_key", ""))):
                return f"活动商品 {args.get('event_key')}/{args.get('item_key')} 不存在"
            return f"活动商品 {args.get('item_key')} 已从 {args.get('event_key')} 下架"
        except Exception as e:
            return f"下架活动商品失败: {e}"


class EarthOnlineListMiyaShop(_EarthBase):
    """查看弥娅商城"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_miya_shop",
            "description": "查看弥娅专属兑换所货架（商品/价格/限购/已兑换次数与玩家弥娅币余额）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            shop = self._store().list_miya_shop()
            lines = [f"【{shop.get('name', '弥娅商城')}】玩家弥娅币: {shop.get('player', {}).get('miya_currency', 0)}"]
            for item in shop.get("items", []):
                state = "可兑换" if item.get("can_buy") else "已达上限"
                lines.append(
                    f"- {item['key']}「{item['name']}」 {item.get('cost', 0)}币 · 限{item.get('limit', 1)} "
                    f"(已兑 {item.get('purchased', 0)}) [{item.get('kind')}] {state}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看弥娅商城失败: {e}"


class EarthOnlineListEventShop(_EarthBase):
    """查看活动商店"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_event_shop",
            "description": "查看限时活动商店货架（含内置+自定义商品、限购与已兑换状态；购买由玩家自己操作）",
            "parameters": {
                "type": "object",
                "properties": {"event_key": {"type": "string", "description": "活动 key，先调用 earth_list_event_areas 查看"}},
                "required": ["event_key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            shop = self._store().list_world_event_shop(str(args.get("event_key", "")))
            if not shop.get("items") and not shop.get("active"):
                return f"活动 {args.get('event_key')} 不存在或商店为空"
            lines = [f"【活动商店】{shop.get('name', args.get('event_key'))} ({args.get('event_key')}) · {'进行中' if shop.get('active') else '未运行'}"]
            for item in shop.get("items", []):
                source = "自定义" if item.get("is_custom") else "内置"
                state = "可兑换" if item.get("can_buy") else "已兑完"
                lines.append(
                    f"- {item['key']}「{item['name']}」 {item.get('cost', 0)}币 · 限{item.get('limit', 1)} "
                    f"(已兑 {item.get('purchased', 0)}) [{item.get('kind')}/{source}] {state}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看活动商店失败: {e}"


class EarthOnlineManageMiyaShop(_EarthBase):
    """管理弥娅商城货架"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_manage_miya_shop",
            "description": "管理弥娅专属兑换所货架（策划权限：自主上架/改价/上下架只属于你们的商品；内置商品不可改删）。action=list 查看全部货架(含下架)/create 上架新商品/update 修改/delete 移除",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "create", "update", "delete"], "description": "管理动作"},
                    "item_key": {"type": "string", "description": "商品唯一 key（create 必填，如 miya_summer_hug；update/delete 必填）"},
                    "name": {"type": "string", "description": "商品名（create 必填）"},
                    "description": {"type": "string", "description": "货架上的商品说明"},
                    "cost": {"type": "integer", "description": "价格（弥娅币），默认12"},
                    "limit": {"type": "integer", "description": "限购次数，默认1"},
                    "kind": {"type": "string", "enum": ["interaction", "story", "title", "collectible"], "description": "商品类型"},
                    "interaction": {"type": "string", "description": "kind=interaction 时兑换触发的亲昵互动文案"},
                    "story_title": {"type": "string", "description": "kind=story 时剧情标题"},
                    "story_content": {"type": "string", "description": "kind=story 时剧情正文"},
                    "title_award": {"type": "string", "description": "kind=title 时授予的专属称号"},
                    "active": {"type": "boolean", "description": "update 时上下架（true 上架 / false 下架），默认 true"},
                },
                "required": ["action"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            store = self._store()
            action = str(args.get("action", "")).strip().lower()
            item_key = str(args.get("item_key", "")).strip()
            if action == "list":
                items = store.list_miya_shop_managed()
                lines = ["【弥娅商城 · 管理视图】"]
                for item in items:
                    source = "内置" if item.get("builtin") else "自定义"
                    state = "上架" if item.get("active") else "已下架"
                    lines.append(
                        f"- {item['key']}「{item['name']}」 {item.get('cost', 0)}币 · 限{item.get('limit', 1)} "
                        f"[{item.get('kind')}/{source}/{state}]"
                    )
                return "\n".join(lines)
            if action == "create":
                item = store.create_miya_shop_item({
                    "key": item_key,
                    "name": str(args.get("name", "")),
                    "description": str(args.get("description", "")),
                    "cost": args.get("cost", 12),
                    "limit": args.get("limit", 1),
                    "kind": str(args.get("kind", "interaction")),
                    "interaction": str(args.get("interaction", "")),
                    "story_title": str(args.get("story_title", "")),
                    "story_content": str(args.get("story_content", "")),
                    "title_award": str(args.get("title_award", "")),
                })
                if not item:
                    return "上架失败: 需要 item_key 和 name，或 key 与现有商品冲突"
                return f"已上架新商品「{item['name']}」({item_key}, {item.get('cost', 0)}币, 限{item.get('limit_count', 1)}, {item.get('kind')})"
            if action == "update":
                updates: Dict[str, Any] = {"active": bool(args.get("active", True))}
                for field in ("name", "description", "interaction", "story_title", "story_content", "title_award", "kind"):
                    if args.get(field):
                        updates[field] = str(args[field])
                for field in ("cost", "limit"):
                    if args.get(field) is not None:
                        updates[field] = args[field]
                item = store.update_miya_shop_item(item_key, updates)
                if not item:
                    return f"修改失败: {item_key} 不是自定义商品 (内置商品不可改)"
                return f"商品 {item_key} 已更新 ({'上架' if item.get('active') else '下架'})"
            if action == "delete":
                if store.delete_miya_shop_item(item_key):
                    return f"商品 {item_key} 已从货架移除"
                return f"移除失败: {item_key} 不是自定义商品 (内置商品不可删)"
            return "无效 action，可用: list/create/update/delete"
        except Exception as e:
            return f"管理弥娅商城失败: {e}"


class EarthOnlineAffinityLogs(_EarthBase):
    """查看好感度记录"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_affinity_logs",
            "description": "查看一位角色的好感度变动历史（谁因为什么加减了分）",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer", "description": "角色ID"},
                    "limit": {"type": "integer", "description": "条数，默认20"},
                },
                "required": ["character_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            c = self._store().get_character(int(args.get("character_id", 0)))
            if not c:
                return f"角色 #{args.get('character_id')} 不存在"
            logs = self._store().affinity_logs(int(args.get("character_id", 0)), limit=int(args.get("limit", 20)))
            if not logs:
                return f"「{c['name']}」还没有好感度变动记录"
            lines = [f"【好感度记录 · {c['name']}】当前 {c['affinity']}"]
            for log in logs:
                arrow = "+" if int(log["delta"]) >= 0 else ""
                lines.append(f"- {str(log.get('created_at', ''))[:10]} {arrow}{log['delta']} ({log.get('reason') or '无备注'})")
            return "\n".join(lines)
        except Exception as e:
            return f"查看好感度记录失败: {e}"


class EarthOnlineQuestHistory(_EarthBase):
    """查看任务结算历史"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_quest_history",
            "description": "查看任务结算历史（已完成/失败的归档，含奖励与惩罚）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认20"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            rows = self._store().quest_history(limit=int(args.get("limit", 20)))
            if not rows:
                return "还没有任务结算记录～"
            lines = ["【任务结算历史】"]
            for row in rows:
                when = str(row.get("completed_at", ""))[:10]
                lines.append(
                    f"- {when} #{row.get('quest_id')}「{row.get('title')}」[{row.get('status')}] "
                    f"+{row.get('reward_currency', 0)}币/+{row.get('reward_exp', 0)}经验"
                    + (f" 鸽-{row.get('penalty_currency', 0)}币" if row.get("penalty_currency") else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看任务历史失败: {e}"


class EarthOnlineAdjustEarthCurrency(_EarthBase):
    """记录现实资产变动 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_adjust_earth_currency",
            "description": "记录一笔现实资产变动（amount 人民币元，可正可负：收入/支出/重估，写流水）。修改前先跟佳确认",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "变动金额（元），正数收入负数支出"},
                    "reason": {"type": "string", "description": "备注，如 工资/外卖/二手出"},
                },
                "required": ["amount"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().adjust_earth_currency(float(args.get("amount", 0)), args.get("reason", ""))
            if not r.get("success"):
                return r.get("message", "调整失败")
            return f"现实资产 {float(args.get('amount', 0)):+.2f} 元 → 余额 ¥{r['balance']:.2f} ({args.get('reason', '') or '未备注'})"
        except Exception as e:
            return f"调整现实资产失败: {e}"


class EarthOnlineMemoryPool(_EarthBase):
    """回忆卡池 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_memory_pool",
            "description": "查看回忆卡池（价格/保底/收集进度/最近抽取）。抽取操作由玩家在商城完成",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            store = self._store()
            info = store.get_memory_pool_info()
            lines = [
                f"【{info['name']}】",
                f"单抽 {info['cost_single']} 弥娅币 · 十连 {info['cost_ten']} (九折) · 保底: {info['pity_threshold']} 抽内必出史诗+ (当前垫了 {info['pity']})",
                f"收集: {info['collected']}/{info['pool_size']} · 历史抽数 {info['total_pulls']}",
            ]
            recent = store.list_memory_pulls(limit=5)
            if recent:
                lines.append("最近抽取: " + "、".join(f"「{p['title']}」[{RARITY_LABELS.get(p['rarity'], p['rarity'])}]" for p in recent))
            else:
                lines.append("还没有抽过卡，卡池在商城等你～")
            return "\n".join(lines)
        except Exception as e:
            return f"读取卡池失败: {e}"


class EarthOnlineViewBattlePass(_EarthBase):
    """每周纪行 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_view_battle_pass",
            "description": "查看本周纪行进度（积分来源/各档奖励/可领取档位）。领取由玩家在数据中心完成",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            bp = self._store().get_battle_pass()
            lines = [f"【每周纪行 {bp['week_key']}】积分 {bp['points']}"]
            for t in bp["tiers"]:
                state = "已领" if t["claimed"] else ("可领取!" if t["claimable"] else ("已达标" if t["reached"] else "未达标"))
                lines.append(f"第{t['tier']}档 {t['threshold']}分 → +{t['reward_currency']}弥娅币 [{state}]")
            if bp["claimable_count"]:
                lines.append(f"提示: 有 {bp['claimable_count']} 档可以领取，让佳去数据中心看看吧")
            return "\n".join(lines)
        except Exception as e:
            return f"读取纪行失败: {e}"


class EarthOnlineWeeklyChallenge(_EarthBase):
    """周挑战 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_weekly_challenge",
            "description": "查看本周挑战主题与星级进度（完成委托 2/4/5 个 → ★/★★/★★★）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            wc = self._store().get_weekly_challenge()
            theme = wc["theme"]
            return (
                f"【{wc['name']}】{wc['stars_label']}\n{theme['description']}\n"
                f"进度: 本周完成委托 {wc['completed_quests']}/{wc['goal']}\n"
                "建议: " + "；".join(theme["suggestions"])
            )
        except Exception as e:
            return f"读取周挑战失败: {e}"


class EarthOnlineListCommemorations(_EarthBase):
    """纪念日列表 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_commemorations",
            "description": "查看纪念日列表（每年循环；临近自动开限时活动、当天自动写寄语）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            memos = self._store().list_commemorations()
            if not memos:
                return "还没有记录纪念日。把重要的日子告诉我，我会提前准备活动～"
            lines = ["【纪念日】"]
            for m in memos:
                state = {"today": "就是今天!", "upcoming": f"还有 {m['days_until']} 天", "later": f"还有 {m['days_until']} 天", "invalid": "日期格式有误"}[m["phase"]]
                enabled = "" if int(m.get("enabled", 1)) else " (已停用)"
                lines.append(f"- {m['icon']} {m['name']} ({m['date']}) · {state}{enabled}")
            return "\n".join(lines)
        except Exception as e:
            return f"读取纪念日失败: {e}"


class EarthOnlineAddCommemoration(_EarthBase):
    """新增纪念日 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_add_commemoration",
            "description": "新增纪念日（date 格式 MM-DD 每年循环；临近时自动开限时活动）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "英文标识，如 first_meeting"},
                    "name": {"type": "string", "description": "名称，如 我们的初见"},
                    "date": {"type": "string", "description": "MM-DD 格式，如 05-20"},
                    "description": {"type": "string", "description": "这一天的意义（可选）"},
                    "icon": {"type": "string", "description": "图标符号（可选，默认 ✦）"},
                    "lead_days": {"type": "integer", "description": "提前几天开始活动（默认2）"},
                },
                "required": ["key", "name", "date"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().add_commemoration(
                key=args.get("key", ""), name=args.get("name", ""), date=args.get("date", ""),
                description=args.get("description", ""), icon=args.get("icon", "✦"),
                lead_days=int(args.get("lead_days", 2)),
            )
            if not r.get("success"):
                return r.get("message", "创建失败")
            m = r["commemoration"]
            return f"纪念日「{m['name']}」({m['date']}) 已记录。临近时我会自动开限时活动，当天写寄语给你 ✦"
        except Exception as e:
            return f"新增纪念日失败: {e}"


class EarthOnlineGenerateDailyCommissions(_EarthBase):
    """生成今日日常委托 (v17)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_generate_daily_commissions",
            "description": "生成今日日常委托（幂等，每日仪式也会自动生成）。数量由 earth_online.daily.daily_quest_count 配置",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().generate_daily_commissions()
            if not r.get("success"):
                return r.get("message", "生成失败")
            if not r.get("created"):
                return f"今天的日常委托已经齐了 ({len(r.get('quests', []))} 个)"
            titles = [f"「{q['title']}」" for q in r.get("created_quests", [])]
            return "今日日常委托已发布: " + "、".join(titles)
        except Exception as e:
            return f"生成日常委托失败: {e}"


class EarthOnlineStats(_EarthBase):
    """数据中心总览 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_stats",
            "description": "查看数据中心总览（任务/物品/角色/剧情/签到/成就多维分布 + 7日完成趋势 + 汇率）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            store = self._store()
            s = store.get_stats()
            lines = [
                "【数据中心】",
                f"委托: {s['quests']['total']} 个 · 完成 {s['quests']['completed']} · 完成率 {s['quests']['completion_rate']}%",
                "7日趋势: " + " ".join(f"{d['date'][5:]}×{d['count']}" for d in s['quests']['trend_7d']),
                f"背包: {s['items']['total']} 件 · 分类 " + " ".join(f"{k}:{v}" for k, v in s['items']['categories'].items() if v),
                f"角色: {s['characters']['total']} 位",
                f"剧情: {s['stories']['total']} 段 · 签到: 连{s['checkin']['streak']}天 · 成就: {s['achievements']['unlocked']}/{s['achievements']['total']}",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"读取数据中心失败: {e}"


class EarthOnlineListCheckins(_EarthBase):
    """签到历史 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_list_checkins",
            "description": "查看签到历史（含每晚睡眠时长与体力回复记录）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认14"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            rows = self._store().list_checkins(limit=max(1, min(120, int(args.get("limit", 14)))))
            if not rows:
                return "还没有签到记录～"
            lines = ["【签到足迹】"]
            for c in rows:
                sleep = f" · 睡 {c['sleep_hours']}h(体力+{c['energy_bonus']})" if c.get("sleep_hours") is not None else ""
                lines.append(f"- {c['date']} 连签{c['streak']}天 +{c['reward_currency']}币{sleep}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看签到历史失败: {e}"


class EarthOnlineCurrencyLedger(_EarthBase):
    """货币流水 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_currency_ledger",
            "description": "查看货币/经验流水（评估经济、发周报用；currency 可选 miya/earth/exp）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "条数，默认20"},
                    "currency": {"type": "string", "description": "筛选币种: miya/earth/exp，缺省全部"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            rows = self._store().list_currency_ledger(
                limit=max(1, min(200, int(args.get("limit", 20)))), currency=args.get("currency", "")
            )
            if not rows:
                return "还没有流水记录 (v17 起所有变动都会入账)"
            currency_names = {"miya": "弥娅币", "earth": "现实资产", "exp": "经验"}
            lines = ["【货币流水】"]
            for row in rows:
                name = currency_names.get(row["currency"], row["currency"])
                amount = f"{row['delta']:+.2f}" if row["currency"] == "earth" else f"{int(row['delta']):+d}"
                reason = f" · {row['reason'][:30]}" if row.get("reason") else ""
                lines.append(f"- {str(row['created_at'])[:16]} {name} {amount}{reason}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看流水失败: {e}"


class EarthOnlineUpdateRealContext(_EarthBase):
    """修改现实数据连接设置 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_real_context",
            "description": "修改现实数据连接设置（城市/总开关/精确定位许可/刷新间隔）。改完可调 earth_refresh_real_context 立即同步天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 上海"},
                    "enabled": {"type": "boolean", "description": "现实数据连接总开关"},
                    "allow_precise_location": {"type": "boolean", "description": "是否允许保存精确坐标"},
                    "refresh_minutes": {"type": "integer", "description": "天气快照有效期（分钟，≥5）"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            values: Dict[str, Any] = {}
            if args.get("city"):
                values["city"] = args["city"]
            if args.get("enabled") is not None:
                values["enabled"] = bool(args["enabled"])
            if args.get("allow_precise_location") is not None:
                values["allow_precise_location"] = bool(args["allow_precise_location"])
            if args.get("refresh_minutes") is not None:
                values["refresh_minutes"] = max(5, int(args["refresh_minutes"]))
            if not values:
                return "没有需要修改的字段"
            settings = self._store().update_real_context_settings(values)
            return (
                f"现实连接已更新: 城市「{settings.get('city') or '未设置'}」 · 开关 {'开' if settings.get('enabled') else '关'} · "
                f"天气API {'已配置' if settings.get('weather_api_configured') else '未配置'} · 刷新 {settings.get('refresh_minutes')} 分钟"
            )
        except Exception as e:
            return f"修改现实连接失败: {e}"


class EarthOnlineUpdateCommemoration(_EarthBase):
    """编辑纪念日 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_update_commemoration",
            "description": "编辑纪念日（只更新传入的字段；enabled 可临时停用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "纪念日 key"},
                    "name": {"type": "string", "description": "新名称"},
                    "date": {"type": "string", "description": "新日期 MM-DD"},
                    "description": {"type": "string", "description": "新的意义描述"},
                    "lead_days": {"type": "integer", "description": "提前几天开始活动"},
                    "enabled": {"type": "boolean", "description": "是否启用"},
                },
                "required": ["key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            values: Dict[str, Any] = {}
            if args.get("name"):
                values["name"] = args["name"]
            if args.get("date"):
                values["date"] = args["date"]
            if args.get("description"):
                values["description"] = args["description"]
            if args.get("lead_days") is not None:
                values["lead_days"] = int(args["lead_days"])
            if args.get("enabled") is not None:
                values["enabled"] = bool(args["enabled"])
            memo = self._store().update_commemoration(str(args.get("key", "")), values)
            if not memo:
                return f"纪念日「{args.get('key')}」不存在"
            return f"纪念日已更新: {memo['icon']} {memo['name']} ({memo['date']}) · 提前 {memo['lead_days']} 天开始活动"
        except Exception as e:
            return f"编辑纪念日失败: {e}"


class EarthOnlineDeleteCommemoration(_EarthBase):
    """删除纪念日 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_delete_commemoration",
            "description": "删除纪念日（已生成的纪念日活动区域不受影响）",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "纪念日 key"}},
                "required": ["key"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            if not self._store().delete_commemoration(str(args.get("key", ""))):
                return f"纪念日「{args.get('key')}」不存在"
            return f"纪念日「{args.get('key')}」已删除"
        except Exception as e:
            return f"删除纪念日失败: {e}"


class EarthOnlinePullMemory(_EarthBase):
    """替玩家回忆抽卡 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_pull_memory",
            "description": "替玩家进行回忆抽卡（times: 1 单抽 / 10 十连）。消耗弥娅币，重复碎片自动转化——佳说想抽的时候可以帮他",
            "parameters": {
                "type": "object",
                "properties": {"times": {"type": "integer", "description": "抽数: 1 或 10，默认1"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().pull_memory(int(args.get("times", 1)))
            if not r.get("success"):
                return r.get("message", "抽取失败")
            names = {"common": "普通", "uncommon": "稀有", "rare": "珍贵", "epic": "史诗", "legendary": "传说"}
            parts = []
            for item in r["results"]:
                mark = "NEW" if item["is_new"] else f"重复+{item['refund_currency']}"
                parts.append(f"「{item['title']}」[{names.get(item['rarity'], item['rarity'])}·{mark}]")
            refund = f" · 重复转化 +{r['refund_total']} 弥娅币" if r.get("refund_total") else ""
            return f"回忆抽卡 ×{r['times']} (花费 {r['cost']}){refund} → 余额 {r['player']['miya_currency']}\n" + "、".join(parts)
        except Exception as e:
            return f"回忆抽卡失败: {e}"


class EarthOnlineClaimBattlePass(_EarthBase):
    """领取纪行奖励 (v17.1)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_claim_battle_pass",
            "description": "领取每周纪行某一档奖励（先 earth_view_battle_pass 看哪档可领）",
            "parameters": {
                "type": "object",
                "properties": {"tier": {"type": "integer", "description": "档位 1-10"}},
                "required": ["tier"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            r = self._store().claim_battle_pass_tier(int(args.get("tier", 0)))
            if not r.get("success"):
                return r.get("message", "领取失败")
            return f"纪行第 {r['tier']} 档奖励已领取: +{r['reward_currency']} 弥娅币 ✦"
        except Exception as e:
            return f"领取纪行失败: {e}"


class EarthOnlineIssueCareCommission(_EarthBase):
    """现场创作关怀委托 (v17.3)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_issue_care_commission",
            "description": "发布一张现场创作的关怀委托（关怀时机出现时用；内容贴着佳此刻的状态即兴写，不要套模板）。message 是想对佳说的一句话，会作为主动敲门文案",
            "parameters": {
                "type": "object",
                "properties": {
                    "care_key": {"type": "string", "description": "关怀类型，来自上下文[关怀时机]提示，如 care_sleep/care_lunch；自己发现时机可用 care_custom"},
                    "title": {"type": "string", "description": "委托标题（必填，由你创作）"},
                    "description": {"type": "string", "description": "委托描述"},
                    "subtasks": {"type": "array", "description": "子任务清单，字符串数组，如 [\"喝一杯水\"]"},
                    "reward_currency": {"type": "integer", "description": "奖励弥娅币 (0-20，默认6)"},
                    "reward_exp": {"type": "integer", "description": "奖励经验 (0-30，默认10)"},
                    "message": {"type": "string", "description": "想对佳说的一句话，会随委托保存并用于主动提醒"},
                },
                "required": ["care_key", "title"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            subtasks = args.get("subtasks")
            r = self._store().issue_care_commission(
                care_key=str(args.get("care_key", "")),
                title=str(args.get("title", "")),
                description=str(args.get("description", "")),
                subtasks=subtasks if isinstance(subtasks, list) else None,
                reward_currency=int(args.get("reward_currency", 6)),
                reward_exp=int(args.get("reward_exp", 10)),
                message=str(args.get("message", "")),
            )
            if not r.get("success"):
                return r.get("message", "发布失败")
            quest = r["quest"]
            return (
                f"关怀委托已发布: 「{quest['title']}」(类型 {r['care_key']} · 今日第 {r.get('today_count')} 张)\n"
                f"留言: {str(args.get('message', ''))[:80] or '(无)'}"
            )
        except Exception as e:
            return f"发布关怀委托失败: {e}"


class EarthOnlineRedeemService(_EarthBase):
    """使用服务券 (v17.4)"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "earth_redeem_service",
            "description": "替佳使用一张服务券（抱抱券/晚安耳语等，佳说\"抱抱我/用一下券\"时调用）。返回的互动文案由你亲口表达——用你此刻的语气说出来，不要照念",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_key": {"type": "string", "description": "商城商品 key，如 miya_hug_ticket（自动匹配背包里的券）"},
                    "item_id": {"type": "integer", "description": "背包物品 ID（可选，优先于 item_key）"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            item_id = args.get("item_id")
            r = self._store().redeem_service_ticket(
                item_id=int(item_id) if item_id else None,
                item_key=str(args.get("item_key", "")),
            )
            if not r.get("success"):
                return r.get("message", "使用失败")
            remaining = f" · 背包还剩 {r['remaining']} 张" if r.get("remaining") else " · 这是最后一张"
            return (
                f"服务券「{r['name']}」已使用{remaining}。\n"
                f"基调参考 (请基于这张券的作用，用你当前的人格即兴创作回应，不要照念): {r['interaction']}"
            )
        except Exception as e:
            return f"使用服务券失败: {e}"


def get_earth_online_tools():
    """获取所有地球online 工具实例"""
    return [
        EarthOnlineSummary(),
        EarthOnlinePlayer(),
        EarthOnlineListItems(),
        EarthOnlineAddItem(),
        EarthOnlineListQuests(),
        EarthOnlineAddQuest(),
        EarthOnlineAcceptQuest(),
        EarthOnlineCompleteQuest(),
        EarthOnlineFailQuest(),
        EarthOnlineCheckOverdue(),
        EarthOnlineGetQuest(),
        EarthOnlineUpdateSubtask(),
        EarthOnlineActivity(),
        EarthOnlineWeeklyReport(),
        EarthOnlineRemindDue(),
        EarthOnlineListTitles(),
        EarthOnlineCommentActivity(),
        EarthOnlineAnalyze(),
        EarthOnlineDailyRitual(),
        EarthOnlineListAchievements(),
        EarthOnlineAddAchievement(),
        EarthOnlineSetAchievementProgress(),
        EarthOnlineListStory(),
        EarthOnlineAddStory(),
        EarthOnlineListCharacters(),
        EarthOnlineAddCharacter(),
        EarthOnlineAdjustAffinity(),
        EarthOnlineGrantCurrency(),
        EarthOnlineSpendMiyaCoins(),
        EarthOnlineGrantExp(),
        EarthOnlinePostNote(),
        EarthOnlineListNotes(),
        EarthOnlineWorld(),
        EarthOnlineExplore(),
        EarthOnlineWorldStatus(),
        EarthOnlineRealContext(),
        EarthOnlineRefreshRealContext(),
        EarthOnlineRegionCommission(),
        # 策划级: 实体修改/删除
        EarthOnlineGetItem(),
        EarthOnlineUpdateItem(),
        EarthOnlineDeleteItem(),
        EarthOnlineUpdateQuest(),
        EarthOnlineCancelQuest(),
        EarthOnlineGetCharacter(),
        EarthOnlineUpdateCharacter(),
        EarthOnlineDeleteCharacter(),
        EarthOnlineUpdateStory(),
        EarthOnlineDeleteStory(),
        EarthOnlineDeleteNote(),
        EarthOnlinePinNote(),
        EarthOnlineEquipTitle(),
        EarthOnlineCheckin(),
        # 策划级: 玩家档案
        EarthOnlineUpdatePlayer(),
        # 策划级: 世界与地理围栏
        EarthOnlineUpdateRegion(),
        EarthOnlineAddWorldEvent(),
        EarthOnlineListWorldEvents(),
        EarthOnlineDeleteWorldEvent(),
        EarthOnlineListDiscoveries(),
        EarthOnlineChooseDiscovery(),
        # 策划级: 限时活动运营
        EarthOnlineListEventAreas(),
        EarthOnlineCreateEventArea(),
        EarthOnlineUpdateEventArea(),
        EarthOnlineDeleteEventArea(),
        EarthOnlineAddEventShopItem(),
        EarthOnlineDeleteEventShopItem(),
        # 策划级: 商店查询
        EarthOnlineListMiyaShop(),
        EarthOnlineListEventShop(),
        EarthOnlineManageMiyaShop(),
        # 策划级: 查询补充
        EarthOnlineAffinityLogs(),
        EarthOnlineQuestHistory(),
        # v17: 现实资产 / 回忆抽卡 / 纪行 / 周挑战 / 纪念日 / 每日日常
        EarthOnlineAdjustEarthCurrency(),
        EarthOnlineMemoryPool(),
        EarthOnlineViewBattlePass(),
        EarthOnlineWeeklyChallenge(),
        EarthOnlineListCommemorations(),
        EarthOnlineAddCommemoration(),
        EarthOnlineGenerateDailyCommissions(),
        # v17.1: 全权策划补齐
        EarthOnlineStats(),
        EarthOnlineListCheckins(),
        EarthOnlineCurrencyLedger(),
        EarthOnlineUpdateRealContext(),
        EarthOnlineUpdateCommemoration(),
        EarthOnlineDeleteCommemoration(),
        EarthOnlinePullMemory(),
        EarthOnlineClaimBattlePass(),
        EarthOnlineIssueCareCommission(),
        EarthOnlineRedeemService(),
    ]
