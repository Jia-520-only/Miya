"""
地球online 工具集 — 弥娅操控现实游戏化系统的入口

让弥娅在对话中能够:
- 查看玩家状态 / 背包 / 任务 / 剧情 / 角色
- 安排支线任务 (必须/可选, 奖励与惩罚)
- 完成任务 / 标记失败 / 检查逾期
- 记录剧情 / 添加角色 / 调整好感度
- 发放地球币和经验奖励

所有工具均为 async，返回给 LLM 的字符串描述。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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


class EarthOnlineTools:
    """弥娅的地球online 工具"""

    def __init__(self):
        self._store = None

    def _get_store(self):
        if self._store is None:
            from core.earth_online_store import get_earth_store

            self._store = get_earth_store()
        return self._store

    @staticmethod
    def _msg(keys: tuple, default: str, **kwargs) -> str:
        """从 text_config.json 读取消息模板 (配置优先原则)，失败时回退到默认文案"""
        try:
            from config.config_utils import get_text

            template = get_text("earth_online", *keys, default=None)
            if template:
                try:
                    return str(template).format(**kwargs)
                except (KeyError, ValueError, IndexError):
                    pass  # 模板参数不齐 → 使用默认文案
        except Exception:
            pass
        try:
            return default.format(**kwargs)
        except Exception:
            return default

    # ── 玩家状态 ────────────────────────────────────

    async def earth_summary(self) -> str:
        """查看地球online总览: 玩家等级/经验/地球币 + 各类数据统计"""
        try:
            s = self._get_store().summary()
            p = s["player"]
            st = s["stats"]
            return (
                f"【地球online 总览】\n"
                f"等级: Lv.{p['level']} | 经验: {p['exp']} | 弥娅币: {p['currency']}\n"
                f"完成任务: {p['total_completed']} | 失败任务: {p['total_failed']}\n"
                f"统计: 进行中任务 {st['active_quests']} | 背包物品 {st['items']} | 角色 {st['characters']} | 剧情 {st['stories']}"
            )
        except Exception as e:
            return f"获取地球online总览失败: {e}"

    async def earth_player(self) -> str:
        """查看玩家当前状态"""
        try:
            p = self._get_store().get_player()
            return (
                f"【玩家档案】Lv.{p['level']} | 经验 {p['exp']} | 地球币 {p['currency']} | "
                f"完成 {p['total_completed']} | 失败 {p['total_failed']}"
            )
        except Exception as e:
            return f"获取玩家状态失败: {e}"

    # ── 背包物品 ────────────────────────────────────

    async def earth_list_items(self, status: str = "") -> str:
        """查看背包里的物品列表"""
        try:
            items = self._get_store().list_items(status=status)
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

    async def earth_add_item(
        self,
        name: str,
        category: str = "other",
        rarity: str = "common",
        quantity: int = 1,
        description: str = "",
        markdown: str = "",
        image_path: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """往背包添加一件现实物品 (fields 为自定义字段对象, markdown 为三段式档案)"""
        try:
            item = self._get_store().create_item(
                name=name, category=category, rarity=rarity,
                quantity=int(quantity), description=description,
                markdown=markdown, image_path=image_path,
                fields=fields if isinstance(fields, dict) else None,
            )
            rarity_cn = RARITY_LABELS.get(item["rarity"], item["rarity"])
            return self._msg(
                ("items", "added"), f"已将「{item['name']}」收入背包 ✦ 稀有度: {rarity_cn}",
                name=item["name"], rarity=rarity_cn,
            )
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"添加物品失败: {e}"

    # ── 任务系统 ────────────────────────────────────

    async def earth_list_quests(self, status: str = "") -> str:
        """查看任务列表 (可传 status: pending/ongoing/completed/failed/cancelled)"""
        try:
            quests = self._get_store().list_quests(status=status)
            if not quests:
                return "当前没有任务～"
            lines = ["【任务委托】"]
            for q in quests:
                qtype = QUEST_TYPE_LABELS.get(q["quest_type"], q["quest_type"])
                mark = "必须" if q["must_complete"] else "可选"
                st = STATUS_LABELS.get(q["status"], q["status"])
                subtasks = q.get("subtasks") or []
                prog = ""
                if subtasks:
                    done = sum(1 for s in subtasks if s.get("done"))
                    prog = f" 进度{done}/{len(subtasks)}"
                lines.append(
                    f"- #{q['id']} [{qtype}/{mark}] {q['title']} ({st}){prog} "
                    f"奖励+{q['reward_currency']}币/+{q['reward_exp']}经验 "
                    + (f"鸽-{q['penalty_currency']}币" if q["penalty_currency"] else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"查看任务失败: {e}"

    async def earth_get_quest(self, quest_id: int) -> str:
        """查看单个任务详情 (含子任务清单与进度)"""
        try:
            q = self._get_store().get_quest(int(quest_id))
            if not q:
                return f"任务 #{quest_id} 不存在"
            qtype = QUEST_TYPE_LABELS.get(q["quest_type"], q["quest_type"])
            mark = "必须" if q["must_complete"] else "可选"
            st = STATUS_LABELS.get(q["status"], q["status"])
            lines = [
                f"【任务 #{q['id']}】{q['title']}",
                f"类型: {qtype} | {mark} | 状态: {st} | 难度: {'★' * q['difficulty']}",
                f"奖励: +{q['reward_currency']}币 +{q['reward_exp']}经验"
                + (f" | 鸽了扣{q['penalty_currency']}币" if q["penalty_currency"] else ""),
                + (f" | 截止 {q['deadline']}" if q.get("deadline") else ""),
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

    async def earth_update_subtask(self, quest_id: int, index: int, done: bool) -> str:
        """更新任务子任务完成状态 (index 从 0 开始, done 为是否完成)"""
        try:
            r = self._get_store().toggle_subtask(int(quest_id), int(index), bool(done))
            if not r.get("success"):
                return r.get("message", "更新失败")
            q = r["quest"]
            subtasks = q.get("subtasks") or []
            done_count = sum(1 for s in subtasks if s.get("done"))
            all_done = done_count >= len(subtasks)
            return (
                f"「{q['title']}」子任务 {index} 已{'完成' if done else '标记为未完成'} "
                f"({done_count}/{len(subtasks)})"
                + ("，全部子任务已完成，可以提交委托了！" if all_done else "")
            )
        except Exception as e:
            return f"更新子任务失败: {e}"

    async def earth_activity(self, limit: int = 20) -> str:
        """查看地球online 全局动态流 (任务/物品/角色/剧情/签到/成就/寄语)"""
        try:
            acts = self._get_store().list_activity(limit=int(limit))
            if not acts:
                return "还没有动态～"
            lines = ["【地球online 动态流】"]
            for a in acts:
                icon = a.get("icon", "·")
                lines.append(f"{icon} #{a.get('id', '?')} {a['summary']}" + (f" ({a['detail']})" if a.get("detail") else ""))
            return "\n".join(lines)
        except Exception as e:
            return f"查看动态失败: {e}"

    async def earth_weekly_report(self) -> str:
        """生成本周报告 (周一至今: 任务/签到/动态/成就/收入)"""
        try:
            r = self._get_store().get_weekly_report()
            p = r.get("player", {})
            q = r.get("quests", {})
            lines = [
                "【地球online 本周报告】",
                f"周起点: {r.get('week_start', '?')}",
                f"任务: 完成 {q.get('completed', 0)} / 失败 {q.get('failed', 0)} (完成率 {q.get('completion_rate', 0)}%)",
                f"签到: {r.get('checkins', 0)} 天",
                f"动态: {r.get('activities', 0)} 条 | 成就解锁: {r.get('achievements', 0)} 个 | 好感变动: {r.get('affinity_changes', 0)} 次",
                f"本周收入: +{r.get('earned', {}).get('currency', 0)} 地球币 · +{r.get('earned', {}).get('exp', 0)} 经验",
                f"当前: Lv.{p.get('level', 1)} (经验 {p.get('exp', 0)}) · 地球币 {p.get('currency', 0)}",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"生成周报失败: {e}"

    async def earth_remind_due(self, days: int = 3) -> str:
        """查看即将到期(或已逾期)的未完成任务, 用于提醒亲爱的"""
        try:
            due = self._get_store().list_due_soon(days=int(days))
            if not due:
                return f"未来 {days} 天内没有到期的任务～"
            lines = [f"【到期提醒 · {days} 天内】"]
            for q in due:
                lines.append(f"- #{q['id']} {q['title']} (截止 {q['deadline']})")
            return "\n".join(lines)
        except Exception as e:
            return f"查看到期任务失败: {e}"

    async def earth_list_titles(self) -> str:
        """查看可佩戴称号 (默认 + 已解锁成就称号 + 当前佩戴)"""
        try:
            info = self._get_store().list_titles()
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

    async def earth_comment_activity(self, activity_id: int, comment: str) -> str:
        """对一条全局动态写弥娅评论 (参与感: 点赞/鼓励/吐槽动态里的每件事)"""
        try:
            row = self._get_store().update_activity_comment(int(activity_id), comment)
            if not row:
                return f"动态 #{activity_id} 不存在"
            return f"已评论动态 #{activity_id}: 「{comment}」"
        except Exception as e:
            return f"评论失败: {e}"

    async def earth_analyze(self) -> str:
        """综合分析地球online 全部数据 (弥娅担任策划: 为佳的现实生活提供建议的基础)"""
        try:
            a = self._get_store().get_analysis()
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

    async def earth_daily_ritual(self) -> str:
        """弥娅每日仪式: 检查逾期任务 + 到期提醒 + 签到状态 (弥娅主动关心佳的每日开局)"""
        try:
            r = self._get_store().daily_ritual()
            lines = ["【弥娅每日仪式】"]
            lines.append(f"逾期处理: {r['overdue_failed']} 个任务已自动失败")
            due = r["due_today"]
            if due:
                lines.append("今天到期: " + "、".join(f"「{x['title']}」" for x in due))
            else:
                lines.append("今天没有到期的任务～")
            ck = r["checkin"]
            lines.append(f"签到: {'今天已签 ✓' if ck.get('checked_today') else '今天还没签到, 记得提醒佳'} | 连签 {ck.get('streak', 0)} 天")
            acts = r["activity_recent"]
            if acts:
                lines.append("最近动态: " + "、".join(f"{a.get('icon','·')}{a['summary']}" for a in acts[:5]))
            return "\n".join(lines)
        except Exception as e:
            return f"每日仪式失败: {e}"

    async def earth_list_achievements(self) -> str:
        """查看全部成就 (含进度与解锁状态)"""
        try:
            achs = self._get_store().list_achievements()
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

    async def earth_add_achievement(
        self,
        key: str,
        title: str,
        description: str = "",
        icon: str = "✦",
        target: int = 1,
        reward_currency: int = 0,
        reward_exp: int = 0,
        title_award: str = "",
    ) -> str:
        """弥娅制作自定义成就 (key 唯一标识, 进度由 earth_set_achievement_progress 手动更新)"""
        try:
            r = self._get_store().add_achievement(
                key=key, title=title, description=description, icon=icon,
                category="custom", target=int(target),
                reward_currency=int(reward_currency), reward_exp=int(reward_exp),
                title_award=title_award,
            )
            if not r.get("success"):
                return r.get("message", "创建失败")
            a = r["achievement"]
            return (f"成就已创建: {a['icon']} {a['title']} (目标 {a['target']})"
                    + (f", 奖励 +{a['reward_currency']}弥娅币" if a.get("reward_currency") else "")
                    + (f", 称号「{a['title_award']}」" if a.get("title_award") else ""))
        except Exception as e:
            return f"创建成就失败: {e}"

    async def earth_set_achievement_progress(self, key: str, progress: int) -> str:
        """更新成就进度 (达标自动解锁并发奖励)"""
        try:
            r = self._get_store().set_achievement_progress(str(key), int(progress))
            if not r.get("success"):
                return r.get("message", "更新失败")
            a = r["achievement"]
            base = f"「{a['title']}」进度 {a['progress']}/{a['target']}"
            if r.get("newly_unlocked"):
                base += f" ✦ 已解锁！奖励 +{a.get('reward_currency', 0)}弥娅币 +{a.get('reward_exp', 0)}经验"
            return base
        except Exception as e:
            return f"更新成就进度失败: {e}"

    async def earth_add_quest(
        self,
        title: str,
        description: str = "",
        quest_type: str = "branch",
        must_complete: bool = False,
        reward_currency: Optional[int] = None,
        reward_exp: Optional[int] = None,
        penalty_currency: Optional[int] = None,
        deadline: str = "",
        subtasks: Optional[List[Dict[str, Any]]] = None,
        recurring: str = "",
    ) -> str:
        """弥娅主动安排任务 (quest_type: main主线/branch支线/daily日常/optional可选; recurring: daily每天/weekly每周循环)。奖励缺省时读 earth_online.quests.* 配置"""
        try:
            store = self._get_store()
            reward_currency = int(reward_currency) if reward_currency is not None else int(store._cfg("quests", "default_reward_currency", default=10))
            reward_exp = int(reward_exp) if reward_exp is not None else int(store._cfg("quests", "default_reward_exp", default=15))
            penalty_default = int(store._cfg("quests", "daily_penalty_currency", default=20)) if quest_type == "daily" else int(store._cfg("quests", "must_penalty_currency", default=50)) if must_complete else 0
            penalty_currency = int(penalty_currency) if penalty_currency is not None else penalty_default
            q = store.create_quest(
                title=title,
                description=description,
                quest_type=quest_type,
                must_complete=bool(must_complete),
                reward_currency=int(reward_currency),
                reward_exp=int(reward_exp),
                penalty_currency=int(penalty_currency),
                deadline=deadline,
                source="miya",
                subtasks=subtasks,
                recurring=recurring,
            )
            mark = "必须任务" if q["must_complete"] else "可选任务"
            rec_label = {"daily": " (每天循环)", "weekly": " (每周循环)"}.get(q.get("recurring") or "", "")
            base = self._msg(
                ("quests", "added"), "新任务已发布: 「{title}」", title=q["title"],
            )
            return (
                f"{base} #{q['id']} [{mark}]{rec_label}\n"
                f"奖励: +{q['reward_currency']}弥娅币, +{q['reward_exp']}经验"
                + (f" | 鸽了扣{q['penalty_currency']}弥娅币" if q["penalty_currency"] else "")
                + (f" | 截止 {deadline}" if deadline else "")
            )
        except Exception as e:
            return f"安排任务失败: {e}"

    async def earth_accept_quest(self, quest_id: int) -> str:
        """接取任务 (pending → ongoing)，表示玩家开始执行"""
        try:
            r = self._get_store().accept_quest(int(quest_id))
            if not r.get("success"):
                return r.get("message", "操作失败")
            q = r["quest"]
            return f"已接取任务「{q['title']}」，状态: 进行中。加油，亲爱的！"
        except Exception as e:
            return f"接取任务失败: {e}"

    async def earth_complete_quest(self, quest_id: int) -> str:
        """完成任务并发放奖励"""
        try:
            r = self._get_store().complete_quest(int(quest_id))
            if not r.get("success"):
                return r.get("message", "操作失败")
            p = r["player"]
            rew = r["reward"]
            base = self._msg(
                ("quests", "completed"), "任务完成！「{title}」奖励: +{currency} 地球币, +{exp} 经验",
                title=r["quest"]["title"], currency=rew["currency"], exp=rew["exp"],
            )
            return f"{base}\n当前: Lv.{p['level']} | 地球币 {p['currency']}"
        except Exception as e:
            return f"完成任务失败: {e}"

    async def earth_fail_quest(self, quest_id: int) -> str:
        """标记任务失败 (扣除惩罚地球币)"""
        try:
            r = self._get_store().fail_quest(int(quest_id))
            if not r.get("success"):
                return r.get("message", "操作失败")
            p = r["player"]
            base = self._msg(
                ("quests", "failed"), "任务失败了……「{title}」被扣除 {penalty} 地球币",
                title=r["quest"]["title"], penalty=r["quest"]["penalty_currency"],
            )
            return f"{base}，剩余地球币: {p['currency']}"
        except Exception as e:
            return f"标记任务失败出错: {e}"

    async def earth_check_overdue(self) -> str:
        """检查所有逾期未完成任务并自动惩罚"""
        try:
            r = self._get_store().check_overdue()
            return self._msg(
                ("quests", "overdue_checked"), "逾期检查完成: {failed} 个任务已失败处理",
                failed=r["failed"],
            )
        except Exception as e:
            return f"逾期检查失败: {e}"

    # ── 剧情 ────────────────────────────────────────

    async def earth_list_story(self, event_type: str = "") -> str:
        """查看剧情记录"""
        try:
            stories = self._get_store().list_story(event_type=event_type, limit=20)
            if not stories:
                return "还没有剧情记录～"
            lines = ["【人生剧情】"]
            for s in stories:
                lines.append(f"- {s['happened_at'][:10]} {s['title']}" + (f": {s['content'][:40]}" if s.get("content") else ""))
            return "\n".join(lines)
        except Exception as e:
            return f"查看剧情失败: {e}"

    async def earth_add_story(
        self,
        title: str,
        content: str = "",
        event_type: str = "life",
        character_id: Optional[int] = None,
        item_id: Optional[int] = None,
        image_path: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录一段人生剧情 (character_id/item_id 关联图鉴与背包, image_path 绑定照片)"""
        try:
            s = self._get_store().create_story(
                title=title, content=content, event_type=event_type,
                character_id=int(character_id) if character_id else None,
                item_id=int(item_id) if item_id else None,
                image_path=image_path,
                fields=fields if isinstance(fields, dict) else None,
            )
            return self._msg(("story", "added"), "剧情已记录: 「{title}」", title=s["title"])
        except Exception as e:
            return f"记录剧情失败: {e}"

    # ── 角色好感度 ──────────────────────────────────

    async def earth_list_characters(self) -> str:
        """查看角色图鉴与好感度"""
        try:
            chars = self._get_store().list_characters()
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

    async def earth_add_character(
        self,
        name: str,
        nickname: str = "",
        relationship: str = "friend",
        affinity: int = 0,
        notes: str = "",
        birthday: str = "",
        avatar_path: str = "",
        markdown: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """在角色图鉴中添加一位现实人物 (birthday 如 05-20, markdown 为三段式档案)"""
        try:
            c = self._get_store().create_character(
                name=name, nickname=nickname, relationship=relationship,
                affinity=int(affinity), notes=notes, birthday=birthday,
                avatar_path=avatar_path, markdown=markdown,
                fields=fields if isinstance(fields, dict) else None,
            )
            return self._msg(
                ("characters", "added"), "角色「{name}」已加入图鉴 (好感度 {affinity})",
                name=c["name"], affinity=c["affinity"],
            )
        except Exception as e:
            return f"添加角色失败: {e}"

    async def earth_adjust_affinity(self, character_id: int, delta: int, reason: str = "") -> str:
        """调整角色好感度 (delta 可正可负, 记录原因)"""
        try:
            c = self._get_store().add_affinity(int(character_id), int(delta), reason)
            if not c:
                return f"角色 #{character_id} 不存在"
            arrow = "+" if int(delta) >= 0 else ""
            return self._msg(
                ("characters", "affinity_changed"), f"「{c['name']}」好感度 {arrow}{delta} → {c['affinity']} ({reason or '无备注'})",
                name=c["name"], delta=int(delta), affinity=c["affinity"], reason=reason or "无备注",
            )
        except Exception as e:
            return f"调整好感度失败: {e}"

    # ── 弥娅寄语 ────────────────────────────────────

    async def earth_post_note(self, content: str, mood: str = "neutral", pinned: bool = False) -> str:
        """发布一条弥娅寄语（显示在地球online 前台首页公告栏）"""
        try:
            n = self._get_store().add_note(content=content, mood=mood, pinned=bool(pinned))
            return f"寄语已发布 (置顶={'是' if n['pinned'] else '否'}): 「{n['content']}」"
        except Exception as e:
            return f"发布寄语失败: {e}"

    async def earth_list_notes(self) -> str:
        """查看已发布的弥娅寄语"""
        try:
            notes = self._get_store().list_notes(limit=10)
            if not notes:
                return "还没有发布过寄语～"
            lines = ["【弥娅寄语】"]
            for n in notes:
                pin = "📌" if n["pinned"] else "  "
                lines.append(f"{pin} #{n['id']} ({n['created_at'][:10]}) {n['content'][:50]}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看寄语失败: {e}"

    # ── 世界探索 ────────────────────────────────────

    async def earth_world(self) -> str:
        """查看单人世界地图与区域探索进度"""
        try:
            regions = self._get_store().list_world_regions()
            if not regions:
                return "世界地图还是空白的呢～"
            lines = ["【地球online 世界地图】"]
            for r in regions:
                lock = f"Lv.{r['level_req']} 解锁" if self._get_store().get_player().get("level", 1) < r["level_req"] else f"探索 {r['discovery_total']}/{r['event_total']}"
                lines.append(f"{r['icon']} {r['name']} · {r['subtitle']} · {lock}")
            return "\n".join(lines)
        except Exception as e:
            return f"读取世界地图失败: {e}"

    async def earth_explore(self, region_key: str, latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
        """探索指定区域，发现一条只属于佳的世界事件 (区域绑定真实地理围栏时, 玩家在附近需带 latitude/longitude 才能探索)"""
        try:
            result = self._get_store().explore_world_region(
                region_key,
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

    async def earth_world_status(self) -> str:
        """查看当前地球online 的时间、天气与限时活动"""
        try:
            status = self._get_store().get_world_status()
            lines = [f"【世界状态】{status['period_icon']} {status['period']} · {status['weather_icon']} {status['weather']} · {status['date']} {status['time']}"]
            active = [x for x in status.get("event_areas", []) if x.get("active")]
            lines.append("限时活动: " + ("、".join(x["name"] for x in active) if active else "当前没有限时区域"))
            return "\n".join(lines)
        except Exception as e:
            return f"读取世界状态失败: {e}"

    async def earth_real_context(self) -> str:
        """查看现实数据连接状态；天气未同步时不替现实编造天气。"""
        try:
            context = self._get_store().get_real_context(auto_refresh=True)
            if context.get("source_status") == "ok":
                details = [f"{context.get('city', '')} · {context.get('weather', '未知')}"]
                if context.get("temperature") is not None:
                    details.append(f"{context['temperature']}°C")
                if context.get("humidity") is not None:
                    details.append(f"湿度 {context['humidity']}%")
                return "【现实连接】已同步 · " + " · ".join(details)
            return f"【现实连接】{context.get('weather', '未同步')}（状态: {context.get('source_status', 'unavailable')}）"
        except Exception as e:
            return f"读取现实连接失败: {e}"

    async def earth_refresh_real_context(self, city: str = "") -> str:
        """刷新真实天气快照，可选传入城市；失败不会回退到模拟天气。"""
        try:
            context = self._get_store().refresh_real_context({"city": city} if city else {})
            if context.get("source_status") == "ok":
                return f"现实天气已同步：{context.get('city')} · {context.get('weather')} · {context.get('temperature', '未知')}°C"
            return f"现实天气未同步：{context.get('source_status', 'unavailable')}"
        except Exception as e:
            return f"刷新现实天气失败: {e}"

    async def earth_region_commission(self, region_key: str) -> str:
        """为指定区域生成今天唯一的专属委托"""
        try:
            result = self._get_store().create_region_commission(region_key)
            if not result.get("success"):
                return result.get("message", "生成委托失败")
            quest = result["quest"]
            return (f"区域委托{'已生成' if result.get('created') else '已经在任务板上'}: 「{quest['title']}」\n"
                    f"{quest['description']}\n奖励 +{quest['reward_currency']} 弥娅币 · +{quest['reward_exp']} 经验")
        except Exception as e:
            return f"生成区域委托失败: {e}"

    # ── 奖励发放 ────────────────────────────────────

    async def earth_grant_currency(self, amount: int) -> str:
        """发放/扣除弥娅币 (amount 可正可负, 弥娅发放的互动货币)"""
        try:
            p = self._get_store().add_miya_currency(int(amount))
            return f"弥娅币 {'+'+str(amount) if amount>=0 else str(amount)} → 当前 {p['miya_currency']}"
        except Exception as e:
            return f"发放弥娅币失败: {e}"

    async def earth_spend_miya_coins(self, amount: int, reason: str = "") -> str:
        """扣除弥娅币 (佳用弥娅币兑换弥娅的互动服务, 如特别内容/专属陪伴)"""
        try:
            r = self._get_store().spend_miya_coins(int(amount), reason)
            if not r.get("success"):
                return r.get("message", "扣除失败")
            p = r["player"]
            return f"已消耗 {amount} 弥娅币 ({reason or '互动服务'}) → 余额 {p['miya_currency']}"
        except Exception as e:
            return f"消耗弥娅币失败: {e}"

    async def earth_grant_exp(self, amount: int) -> str:
        """发放开拓经验"""
        try:
            p = self._get_store().add_exp(int(amount))
            return f"经验 +{amount} → 当前 Lv.{p['level']} (经验 {p['exp']})"
        except Exception as e:
            return f"发放经验失败: {e}"

    # ── 策划级: 实体修改/删除 ──────────────────────

    async def earth_get_item(self, item_id: int) -> str:
        """查看一件背包物品的完整档案 (修改前先看清楚)"""
        try:
            it = self._get_store().get_item(int(item_id))
            if not it:
                return f"物品 #{item_id} 不存在"
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

    async def earth_update_item(
        self,
        item_id: int,
        name: str = "",
        category: str = "",
        rarity: str = "",
        quantity: Optional[int] = None,
        description: Optional[str] = None,
        status: str = "",
    ) -> str:
        """修改一件背包物品 (只更新传入的字段; 状态: normal在用/used已消耗/lost遗失)"""
        try:
            fields: Dict[str, Any] = {}
            if name:
                fields["name"] = name
            if category:
                fields["category"] = category
            if rarity:
                fields["rarity"] = rarity
            if quantity is not None:
                fields["quantity"] = max(1, int(quantity))
            if description is not None:
                fields["description"] = description
            if status:
                fields["status"] = status
            it = self._get_store().update_item(int(item_id), fields)
            if not it:
                return f"物品 #{item_id} 不存在"
            rarity_cn = RARITY_LABELS.get(it["rarity"], it["rarity"])
            return f"物品 #{it['id']}「{it['name']}」已更新: ×{it['quantity']} [{rarity_cn}] 状态 {it['status']}"
        except Exception as e:
            return f"修改物品失败: {e}"

    async def earth_delete_item(self, item_id: int) -> str:
        """从背包删除一件物品 (确认不再需要时才删, 删除不可恢复)"""
        try:
            if not self._get_store().delete_item(int(item_id)):
                return f"物品 #{item_id} 不存在"
            return f"物品 #{item_id} 已从背包移除"
        except Exception as e:
            return f"删除物品失败: {e}"

    async def earth_update_quest(
        self,
        quest_id: int,
        title: str = "",
        description: Optional[str] = None,
        quest_type: str = "",
        must_complete: Optional[bool] = None,
        reward_currency: Optional[int] = None,
        reward_exp: Optional[int] = None,
        penalty_currency: Optional[int] = None,
        difficulty: Optional[int] = None,
        status: str = "",
        deadline: Optional[str] = None,
        subtasks: Optional[List[Dict[str, Any]]] = None,
        recurring: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """修改任务设定 (只更新传入的字段)。status 直接改状态仅用于策划修正, 正常流程请用接取/完成/失败/取消工具"""
        try:
            fields_update: Dict[str, Any] = {}
            if title:
                fields_update["title"] = title
            if description is not None:
                fields_update["description"] = description
            if quest_type:
                fields_update["quest_type"] = quest_type
            if must_complete is not None:
                fields_update["must_complete"] = bool(must_complete)
            if reward_currency is not None:
                fields_update["reward_currency"] = int(reward_currency)
            if reward_exp is not None:
                fields_update["reward_exp"] = int(reward_exp)
            if penalty_currency is not None:
                fields_update["penalty_currency"] = int(penalty_currency)
            if difficulty is not None:
                fields_update["difficulty"] = int(difficulty)
            if status:
                fields_update["status"] = status
            if deadline is not None:
                fields_update["deadline"] = deadline
            if subtasks is not None:
                fields_update["subtasks"] = subtasks
            if recurring:
                fields_update["recurring"] = recurring
            if fields is not None and isinstance(fields, dict):
                fields_update["fields"] = fields
            q = self._get_store().update_quest(int(quest_id), fields_update)
            if not q:
                return f"任务 #{quest_id} 不存在"
            st = STATUS_LABELS.get(q["status"], q["status"])
            return (
                f"任务 #{q['id']}「{q['title']}」已更新 ({st}) · "
                f"奖励 +{q['reward_currency']}币/+{q['reward_exp']}经验"
                + (f" | 截止 {q['deadline']}" if q.get("deadline") else "")
            )
        except Exception as e:
            return f"修改任务失败: {e}"

    async def earth_cancel_quest(self, quest_id: int) -> str:
        """取消任务 (无惩罚下架, 比失败温和; 已结束的任务不能再取消)"""
        try:
            r = self._get_store().cancel_quest(int(quest_id))
            if not r.get("success"):
                return r.get("message", "取消失败")
            return f"任务「{r['quest']['title']}」已取消 (未扣惩罚)"
        except Exception as e:
            return f"取消任务失败: {e}"

    async def earth_get_character(self, character_id: int) -> str:
        """查看一位角色的完整档案 (好感度/关系/备注/生日)"""
        try:
            c = self._get_store().get_character(int(character_id))
            if not c:
                return f"角色 #{character_id} 不存在"
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

    async def earth_update_character(
        self,
        character_id: int,
        name: str = "",
        nickname: Optional[str] = None,
        relationship: str = "",
        affinity: Optional[int] = None,
        avatar_path: Optional[str] = None,
        notes: Optional[str] = None,
        birthday: Optional[str] = None,
        markdown: Optional[str] = None,
    ) -> str:
        """修改一位角色的档案 (只更新传入的字段; 关系: family/friend/colleague/partner/other)"""
        try:
            fields: Dict[str, Any] = {}
            if name:
                fields["name"] = name
            for key, val in (
                ("nickname", nickname), ("avatar_path", avatar_path),
                ("notes", notes), ("birthday", birthday), ("markdown", markdown),
            ):
                if val is not None:
                    fields[key] = val
            if relationship:
                fields["relationship"] = relationship
            if affinity is not None:
                fields["affinity"] = int(affinity)
            c = self._get_store().update_character(int(character_id), fields)
            if not c:
                return f"角色 #{character_id} 不存在"
            return f"角色 #{c['id']}「{c['name']}」已更新 (好感度 {c['affinity']})"
        except Exception as e:
            return f"修改角色失败: {e}"

    async def earth_delete_character(self, character_id: int) -> str:
        """从角色图鉴删除一位角色 (确认关系档案不再需要时才删)"""
        try:
            if not self._get_store().delete_character(int(character_id)):
                return f"角色 #{character_id} 不存在"
            return f"角色 #{character_id} 已从图鉴移除"
        except Exception as e:
            return f"删除角色失败: {e}"

    async def earth_update_story(
        self,
        story_id: int,
        title: str = "",
        content: Optional[str] = None,
        event_type: str = "",
        character_id: Optional[int] = None,
        item_id: Optional[int] = None,
        happened_at: str = "",
    ) -> str:
        """编辑一段人生剧情 (只更新传入的字段; 传空字符串可清除内容)"""
        try:
            fields: Dict[str, Any] = {}
            if title:
                fields["title"] = title
            if content is not None:
                fields["content"] = content
            if event_type:
                fields["event_type"] = event_type
            if character_id is not None:
                fields["character_id"] = int(character_id)
            if item_id is not None:
                fields["item_id"] = int(item_id)
            if happened_at:
                fields["happened_at"] = happened_at
            s = self._get_store().update_story(int(story_id), fields)
            if not s:
                return f"剧情 #{story_id} 不存在"
            return f"剧情 #{s['id']}「{s['title']}」已更新"
        except Exception as e:
            return f"修改剧情失败: {e}"

    async def earth_delete_story(self, story_id: int) -> str:
        """删除一段人生剧情 (记录错误/重复时才删)"""
        try:
            if not self._get_store().delete_story(int(story_id)):
                return f"剧情 #{story_id} 不存在"
            return f"剧情 #{story_id} 已删除"
        except Exception as e:
            return f"删除剧情失败: {e}"

    async def earth_delete_note(self, note_id: int) -> str:
        """删除一条弥娅寄语 (过期/说错话时收回)"""
        try:
            if not self._get_store().delete_note(int(note_id)):
                return f"寄语 #{note_id} 不存在"
            return f"寄语 #{note_id} 已删除"
        except Exception as e:
            return f"删除寄语失败: {e}"

    async def earth_pin_note(self, note_id: int, pinned: bool) -> str:
        """置顶/取消置顶一条弥娅寄语 (置顶会显示在地球online 首页公告栏最上方)"""
        try:
            n = self._get_store().pin_note(int(note_id), bool(pinned))
            if not n:
                return f"寄语 #{note_id} 不存在"
            return f"寄语 #{n['id']} 已{'置顶 📌' if n['pinned'] else '取消置顶'}: 「{n['content'][:40]}」"
        except Exception as e:
            return f"置顶寄语失败: {e}"

    async def earth_equip_title(self, title: str) -> str:
        """帮玩家佩戴称号 (必须是默认称号或已解锁的成就/商城称号, 先用 earth_list_titles 查看)"""
        try:
            r = self._get_store().equip_title(title)
            if not r.get("success"):
                return r.get("message", "佩戴失败")
            return f"已佩戴称号「{r['equipped']}」"
        except Exception as e:
            return f"佩戴称号失败: {e}"

    async def earth_checkin(self, sleep_hours: Optional[float] = None) -> str:
        """替玩家完成每日签到 (发放弥娅币+经验+连签奖励; 已签到会提示 already)。

        sleep_hours: 昨晚睡眠时长 (小时)。玩家说过就带上——睡得越好，体力回复越多。
        """
        try:
            r = self._get_store().checkin(sleep_hours)
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

    # ── 策划级: 玩家档案 ──────────────────────────

    async def earth_update_player(
        self,
        name: str = "",
        title: str = "",
        avatar_path: str = "",
        bio: Optional[str] = None,
        attrs: Optional[List[Dict[str, Any]]] = None,
        exp: Optional[int] = None,
        miya_currency: Optional[int] = None,
        earth_currency: Optional[float] = None,
    ) -> str:
        """修改玩家档案 (只更新传入的字段)。注意: earth_currency 是现实资产 (人民币元)，修改前务必跟佳确认；attrs 为完整属性条列表会整体替换"""
        try:
            fields: Dict[str, Any] = {}
            if name:
                fields["name"] = name
            if title:
                fields["title"] = title
            if avatar_path:
                fields["avatar_path"] = avatar_path
            if bio is not None:
                fields["bio"] = bio
            if attrs is not None:
                fields["attrs"] = attrs
            if exp is not None:
                fields["exp"] = int(exp)
            if miya_currency is not None:
                fields["currency"] = int(miya_currency)
            if earth_currency is not None:
                fields["earth_currency"] = float(earth_currency)
            p = self._get_store().update_player(fields)
            return (
                f"玩家档案已更新: {p.get('name', '?')} Lv.{p.get('level', 1)} "
                f"| 弥娅币 {p.get('miya_currency', 0)} | 现实资产 ¥{p.get('earth_currency', 0)}"
            )
        except Exception as e:
            return f"修改玩家档案失败: {e}"

    # ── 策划级: 世界与地理围栏 ────────────────────

    async def earth_update_region(
        self,
        region_key: str,
        name: str = "",
        subtitle: str = "",
        description: Optional[str] = None,
        icon: str = "",
        color: str = "",
        level_req: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        geofence_radius: Optional[int] = None,
    ) -> str:
        """修改世界区域设定 (只更新传入的字段)。geofence_radius 单位米、0=关闭围栏；绑定后玩家探索该区域必须开启真实定位并在半径内"""
        try:
            values: Dict[str, Any] = {}
            if name:
                values["name"] = name
            if subtitle:
                values["subtitle"] = subtitle
            if description is not None:
                values["description"] = description
            if icon:
                values["icon"] = icon
            if color:
                values["color"] = color
            if level_req is not None:
                values["level_req"] = int(level_req)
            if latitude is not None:
                values["latitude"] = float(latitude)
            if longitude is not None:
                values["longitude"] = float(longitude)
            if geofence_radius is not None:
                values["geofence_radius"] = int(geofence_radius)
            r = self._get_store().update_world_region(region_key, values)
            if not r:
                return f"区域 {region_key} 不存在"
            geo = "未绑定围栏"
            if r.get("latitude") is not None and r.get("longitude") is not None and int(r.get("geofence_radius") or 0) > 0:
                geo = f"围栏 ({r['latitude']}, {r['longitude']}) 半径 {r['geofence_radius']} 米"
            return f"区域 {r['key']}「{r['name']}」已更新 · Lv.{r['level_req']} 解锁 · {geo}"
        except Exception as e:
            return f"修改区域失败: {e}"

    async def earth_add_world_event(
        self,
        region_key: str,
        title: str,
        text: str,
        reward_currency: int = 0,
        reward_exp: int = 0,
        kind: str = "story",
    ) -> str:
        """为区域添加一条自定义世界发现 (玩家探索该区域时可遇到; kind: story故事/chest宝箱/hidden隐藏)"""
        try:
            ev = self._get_store().create_world_custom_event(
                region_key=region_key, title=title, text=text,
                reward_currency=int(reward_currency), reward_exp=int(reward_exp), kind=kind,
            )
            if not ev:
                return "创建失败: 区域不存在，或标题/内容为空"
            return (
                f"世界发现已添加 #{ev['id']}「{ev['title']}」→ 区域 {ev['region_key']} · "
                f"+{ev['reward_currency']}币/+{ev['reward_exp']}经验 [{ev['kind']}]"
            )
        except Exception as e:
            return f"添加世界发现失败: {e}"

    async def earth_list_world_events(self, region_key: str = "") -> str:
        """查看自定义世界发现清单 (可按区域过滤, 不传查全部)"""
        try:
            events = self._get_store().list_world_custom_events(region_key=region_key)
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

    async def earth_delete_world_event(self, event_id: int) -> str:
        """删除一条自定义世界发现 (玩家尚未遇到的将不会再遇到)"""
        try:
            if not self._get_store().delete_world_custom_event(int(event_id)):
                return f"世界发现 #{event_id} 不存在"
            return f"世界发现 #{event_id} 已删除"
        except Exception as e:
            return f"删除世界发现失败: {e}"

    async def earth_list_discoveries(self, region_key: str = "", limit: int = 20) -> str:
        """查看玩家的世界探索发现记录 (可按区域过滤, 含同行选择结果)"""
        try:
            rows = self._get_store().list_world_discoveries(region_key=region_key, limit=int(limit))
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

    async def earth_choose_discovery(self, discovery_id: int, choice: str) -> str:
        """对一条探索发现做同行选择 (choice: continue继续前进/record记录此刻/rest先休息; 弥娅可以陪佳一起选, 每条只能选一次)"""
        try:
            r = self._get_store().choose_world_discovery(int(discovery_id), choice)
            if not r.get("success"):
                return r.get("message", "选择失败")
            res = r.get("resonance") or {}
            return f"已选择「{r['label']}」· 区域共鸣 Lv.{res.get('level', 1)} (xp {res.get('xp', 0)})"
        except Exception as e:
            return f"同行选择失败: {e}"

    # ── 策划级: 限时活动运营 ──────────────────────

    async def earth_list_event_areas(self) -> str:
        """查看全部限时活动区域 (内置+自定义, 含进行中/未运行状态与起止日期)"""
        try:
            areas = self._get_store().list_world_event_areas()
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

    async def earth_create_event_area(
        self,
        key: str,
        name: str,
        start: str,
        end: str,
        subtitle: str = "",
        description: str = "",
        icon: str = "✧",
        color: str = "#f0a35b",
        reward_currency: int = 0,
        reward_exp: int = 0,
    ) -> str:
        """创建一个限时活动区域 (key 唯一; start/end 为 YYYY-MM-DD; 结束后可配合商店做纪念兑换)"""
        try:
            a = self._get_store().create_world_event_area(
                {
                    "key": key, "name": name, "subtitle": subtitle, "description": description,
                    "icon": icon, "color": color, "start": start, "end": end,
                    "reward_currency": int(reward_currency), "reward_exp": int(reward_exp),
                }
            )
            if not a:
                return "创建失败: key/name/start/end 必填, 且 start 不能晚于 end"
            return f"限时活动「{a['name']}」({a['key']}) 已创建: {a['start']} ~ {a['end']}"
        except Exception as e:
            return f"创建限时活动失败: {e}"

    async def earth_update_event_area(
        self,
        event_key: str,
        name: str = "",
        subtitle: str = "",
        description: Optional[str] = None,
        icon: str = "",
        color: str = "",
        start: str = "",
        end: str = "",
        reward_currency: Optional[int] = None,
        reward_exp: Optional[int] = None,
        active: Optional[bool] = None,
    ) -> str:
        """修改自定义限时活动 (只更新传入的字段; active 可手动上下架; 内置活动不可修改)"""
        try:
            values: Dict[str, Any] = {}
            if name:
                values["name"] = name
            if subtitle:
                values["subtitle"] = subtitle
            if description is not None:
                values["description"] = description
            if icon:
                values["icon"] = icon
            if color:
                values["color"] = color
            if start:
                values["start"] = start
            if end:
                values["end"] = end
            if reward_currency is not None:
                values["reward_currency"] = int(reward_currency)
            if reward_exp is not None:
                values["reward_exp"] = int(reward_exp)
            if active is not None:
                values["active"] = bool(active)
            a = self._get_store().update_world_event_area(event_key, values)
            if not a:
                return f"自定义活动 {event_key} 不存在 (内置活动不可修改)"
            return f"限时活动「{a['name']}」({a['key']}) 已更新: {a['start']} ~ {a['end']}"
        except Exception as e:
            return f"修改限时活动失败: {e}"

    async def earth_delete_event_area(self, event_key: str) -> str:
        """删除自定义限时活动 (连带删除其活动商店商品; 内置活动不可删除)"""
        try:
            if not self._get_store().delete_world_event_area(event_key):
                return f"自定义活动 {event_key} 不存在 (内置活动不可删除)"
            return f"限时活动 {event_key} 及其商店商品已删除"
        except Exception as e:
            return f"删除限时活动失败: {e}"

    async def earth_add_event_shop_item(
        self,
        event_key: str,
        key: str,
        name: str,
        description: str = "",
        cost: int = 0,
        limit: int = 1,
        kind: str = "collectible",
        requires_discoveries: int = 0,
    ) -> str:
        """给限时活动上架一件兑换商品 (花的是玩家的弥娅币; limit 限购次数; requires_discoveries 需累计探索发现数)"""
        try:
            item = self._get_store().create_world_event_shop_item(
                event_key,
                {
                    "key": key, "name": name, "description": description, "cost": int(cost),
                    "limit": int(limit), "kind": kind, "requires_discoveries": int(requires_discoveries),
                },
            )
            if not item:
                return "上架失败: 活动/key/name 必填"
            return f"活动商品「{item['name']}」({item['key']}) 已上架 → {event_key} · {item['cost']} 弥娅币 限购 {item['limit_count']}"
        except Exception as e:
            return f"上架活动商品失败: {e}"

    async def earth_delete_event_shop_item(self, event_key: str, item_key: str) -> str:
        """下架一件限时活动兑换商品"""
        try:
            if not self._get_store().delete_world_event_shop_item(event_key, item_key):
                return f"活动商品 {event_key}/{item_key} 不存在"
            return f"活动商品 {item_key} 已从 {event_key} 下架"
        except Exception as e:
            return f"下架活动商品失败: {e}"

    # ── 策划级: 商店查询 ──────────────────────────

    async def earth_list_miya_shop(self) -> str:
        """查看弥娅专属兑换所货架 (商品/价格/限购/已兑换次数与玩家弥娅币余额)"""
        try:
            shop = self._get_store().list_miya_shop()
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

    async def earth_list_event_shop(self, event_key: str) -> str:
        """查看限时活动商店货架 (含内置+自定义商品、限购与已兑换状态; 购买由玩家自己操作)"""
        try:
            shop = self._get_store().list_world_event_shop(event_key)
            if not shop.get("items") and not shop.get("active"):
                return f"活动 {event_key} 不存在或商店为空"
            lines = [f"【活动商店】{shop.get('name', event_key)} ({event_key}) · {'进行中' if shop.get('active') else '未运行'}"]
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

    # ── 策划级: 弥娅商城货架管理 ──────────────────

    async def earth_manage_miya_shop(self, action: str, item_key: str = "", name: str = "", description: str = "", cost: int = 12, limit: int = 1, kind: str = "interaction", interaction: str = "", story_title: str = "", story_content: str = "", title_award: str = "", active: bool = True) -> str:
        """管理弥娅专属兑换所货架 (你是策划, 可自主上架/改价/下架只属于你们的商品)

        action: list=看全部货架(含下架)/create=上架新商品(需 item_key+name)/update=修改(需 item_key, 只传要改的字段)/delete=下架删除(需 item_key)
        kind: interaction 亲昵互动(填 interaction 文案)/story 短篇剧情(填 story_title+story_content)/title 专属称号(填 title_award)/collectible 纪念物
        内置商品不可修改删除; 新商品 key 需唯一 (如 miya_summer_hug)。"""
        try:
            store = self._get_store()
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
                    "key": item_key, "name": name, "description": description, "cost": cost, "limit": limit,
                    "kind": kind, "interaction": interaction, "story_title": story_title,
                    "story_content": story_content, "title_award": title_award,
                })
                if not item:
                    return "上架失败: 需要 item_key 和 name，或 key 与现有商品冲突"
                return f"已上架新商品「{item['name']}」({item_key}, {cost}币, 限{limit}, {kind})"
            if action == "update":
                updates: Dict[str, Any] = {}
                if name:
                    updates["name"] = name
                if description:
                    updates["description"] = description
                if cost != 12:
                    updates["cost"] = cost
                if limit != 1:
                    updates["limit"] = limit
                if kind != "interaction":
                    updates["kind"] = kind
                if interaction:
                    updates["interaction"] = interaction
                if story_title:
                    updates["story_title"] = story_title
                if story_content:
                    updates["story_content"] = story_content
                if title_award:
                    updates["title_award"] = title_award
                updates["active"] = bool(active)
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

    # ── 策划级: 查询补充 ──────────────────────────

    async def earth_affinity_logs(self, character_id: int, limit: int = 20) -> str:
        """查看一位角色的好感度变动历史 (谁因为什么加减了分)"""
        try:
            c = self._get_store().get_character(int(character_id))
            if not c:
                return f"角色 #{character_id} 不存在"
            logs = self._get_store().affinity_logs(int(character_id), limit=int(limit))
            if not logs:
                return f"「{c['name']}」还没有好感度变动记录"
            lines = [f"【好感度记录 · {c['name']}】当前 {c['affinity']}"]
            for log in logs:
                arrow = "+" if int(log["delta"]) >= 0 else ""
                lines.append(f"- {str(log.get('created_at', ''))[:10]} {arrow}{log['delta']} ({log.get('reason') or '无备注'})")
            return "\n".join(lines)
        except Exception as e:
            return f"查看好感度记录失败: {e}"

    async def earth_quest_history(self, limit: int = 20) -> str:
        """查看任务结算历史 (已完成/失败的归档, 含奖励与惩罚)"""
        try:
            rows = self._get_store().quest_history(limit=int(limit))
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


    # ── v17: 现实资产 / 回忆抽卡 / 纪行 / 周挑战 / 纪念日 / 每日日常 ──

    async def earth_adjust_earth_currency(self, amount: float, reason: str = "") -> str:
        """记录一笔现实资产变动 (amount 人民币元, 可正可负: 收入/支出/重估)。改前先跟佳确认"""
        try:
            r = self._get_store().adjust_earth_currency(float(amount), reason)
            if not r.get("success"):
                return r.get("message", "调整失败")
            return f"现实资产 {float(amount):+.2f} 元 → 余额 ¥{r['balance']:.2f} ({reason or '未备注'})"
        except Exception as e:
            return f"调整现实资产失败: {e}"

    async def earth_memory_pool(self) -> str:
        """查看回忆卡池 (价格/保底/收集进度) 与最近抽卡记录。抽取由玩家在商城操作"""
        try:
            store = self._get_store()
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

    async def earth_view_battle_pass(self) -> str:
        """查看本周纪行进度 (积分/各档奖励/可领取档位)。领取由玩家在数据中心操作"""
        try:
            bp = self._get_store().get_battle_pass()
            lines = [
                f"【每周纪行 {bp['week_key']}】积分 {bp['points']}",
            ]
            for item in bp["breakdown"].values():
                lines.append(f"- {item['count']} 次 × {item['points_each']} 分")
            for t in bp["tiers"]:
                state = "已领" if t["claimed"] else ("可领取!" if t["claimable"] else ("已达标" if t["reached"] else "未达标"))
                lines.append(f"第{t['tier']}档 {t['threshold']}分 → +{t['reward_currency']}弥娅币 [{state}]")
            if bp["claimable_count"]:
                lines.append(f"提示: 有 {bp['claimable_count']} 档可以领取，让佳去数据中心看看吧")
            return "\n".join(lines)
        except Exception as e:
            return f"读取纪行失败: {e}"

    async def earth_weekly_challenge(self) -> str:
        """查看本周挑战主题与星级进度 (完成委托数 2/4/5 → ★/★★/★★★)"""
        try:
            wc = self._get_store().get_weekly_challenge()
            theme = wc["theme"]
            lines = [
                f"【{wc['name']}】{wc['stars_label']}",
                f"{theme['description']}",
                f"进度: 本周完成委托 {wc['completed_quests']}/{wc['goal']}",
                "建议: " + "；".join(theme["suggestions"]),
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"读取周挑战失败: {e}"

    async def earth_list_commemorations(self) -> str:
        """查看纪念日列表 (每年循环; 临近自动开限时活动)"""
        try:
            memos = self._get_store().list_commemorations()
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

    async def earth_add_commemoration(self, key: str, name: str, date: str, description: str = "", icon: str = "✦", lead_days: int = 2) -> str:
        """新增纪念日 (key 英文标识如 first_meeting; date 格式 MM-DD 每年循环; lead_days 提前几天开始活动)"""
        try:
            r = self._get_store().add_commemoration(key=key, name=name, date=date, description=description, icon=icon, lead_days=int(lead_days))
            if not r.get("success"):
                return r.get("message", "创建失败")
            m = r["commemoration"]
            return f"纪念日「{m['name']}」({m['date']}) 已记录。临近时我会自动开限时活动，当天写寄语给你 ✦"
        except Exception as e:
            return f"新增纪念日失败: {e}"

    async def earth_generate_daily_commissions(self) -> str:
        """生成今日日常委托 (幂等; 每日仪式也会自动生成)。数量由 earth_online.daily.daily_quest_count 配置"""
        try:
            r = self._get_store().generate_daily_commissions()
            if not r.get("success"):
                return r.get("message", "生成失败")
            if not r.get("created"):
                return f"今天的日常委托已经齐了 ({len(r.get('quests', []))} 个)"
            titles = [f"「{q['title']}」" for q in r.get("created_quests", [])]
            return "今日日常委托已发布: " + "、".join(titles)
        except Exception as e:
            return f"生成日常委托失败: {e}"

    # ── v17.1: 全权策划补齐 (数据总览/流水/签到史/现实设置/纪念日CRUD/抽卡/纪行领取) ──

    async def earth_stats(self) -> str:
        """查看数据中心总览: 任务/物品/角色/剧情/签到/成就多维分布 + 7日趋势 + 汇率"""
        try:
            store = self._get_store()
            s = store.get_stats()
            rates = store.get_exchange_rates()
            lines = [
                "【数据中心】",
                f"委托: {s['quests']['total']} 个 · 完成 {s['quests']['completed']} · 完成率 {s['quests']['completion_rate']}%",
                "7日趋势: " + " ".join(f"{d['date'][5:]}×{d['count']}" for d in s['quests']['trend_7d']),
                f"背包: {s['items']['total']} 件 · 分类 " + " ".join(f"{k}:{v}" for k, v in s['items']['categories'].items() if v),
                f"角色: {s['characters']['total']} 位 · 好感榜首 " + (f"{s['characters']['affinity_ranking'][0]['name']}({s['characters']['affinity_ranking'][0]['affinity']})" if s['characters']['affinity_ranking'] else "无"),
                f"剧情: {s['stories']['total']} 段 · 签到: 连{s['checkin']['streak']}天/共{s['checkin']['total_days']}天 · 成就: {s['achievements']['unlocked']}/{s['achievements']['total']}",
            ]
            if rates.get("enabled"):
                lines.append(f"汇率显示: 1 CNY = {rates.get('usd_per_cny')} USD (现实资产以人民币元记账)")
            return "\n".join(lines)
        except Exception as e:
            return f"读取数据中心失败: {e}"

    async def earth_list_checkins(self, limit: int = 14) -> str:
        """查看签到历史 (含每晚睡眠时长记录)"""
        try:
            rows = self._get_store().list_checkins(limit=max(1, min(120, int(limit))))
            if not rows:
                return "还没有签到记录～"
            lines = ["【签到足迹】"]
            for c in rows:
                sleep = f" · 睡 {c['sleep_hours']}h(体力+{c['energy_bonus']})" if c.get("sleep_hours") is not None else ""
                lines.append(f"- {c['date']} 连签{c['streak']}天 +{c['reward_currency']}币{sleep}")
            return "\n".join(lines)
        except Exception as e:
            return f"查看签到历史失败: {e}"

    async def earth_currency_ledger(self, limit: int = 20, currency: str = "") -> str:
        """查看货币/经验流水 (currency 可选 miya/earth/exp，缺省全部)。评估经济、发周报都用它"""
        try:
            rows = self._get_store().list_currency_ledger(limit=max(1, min(200, int(limit))), currency=currency)
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

    async def earth_update_real_context(
        self,
        city: str = "",
        enabled: Optional[bool] = None,
        allow_precise_location: Optional[bool] = None,
        refresh_minutes: Optional[int] = None,
    ) -> str:
        """修改现实数据连接设置 (城市/开关/精确定位许可/刷新间隔)。改完可调 earth_refresh_real_context 立即同步天气"""
        try:
            values: Dict[str, Any] = {}
            if city:
                values["city"] = city
            if enabled is not None:
                values["enabled"] = bool(enabled)
            if allow_precise_location is not None:
                values["allow_precise_location"] = bool(allow_precise_location)
            if refresh_minutes is not None:
                values["refresh_minutes"] = max(5, int(refresh_minutes))
            if not values:
                return "没有需要修改的字段"
            settings = self._get_store().update_real_context_settings(values)
            return (
                f"现实连接已更新: 城市「{settings.get('city') or '未设置'}」 · 开关 {'开' if settings.get('enabled') else '关'} · "
                f"天气API {'已配置' if settings.get('weather_api_configured') else '未配置'} · 刷新 {settings.get('refresh_minutes')} 分钟"
            )
        except Exception as e:
            return f"修改现实连接失败: {e}"

    async def earth_update_commemoration(self, key: str, name: str = "", date: str = "", description: str = "", lead_days: Optional[int] = None, enabled: Optional[bool] = None) -> str:
        """编辑纪念日 (只更新传入的字段; enabled 可临时停用)"""
        try:
            values: Dict[str, Any] = {}
            if name:
                values["name"] = name
            if date:
                values["date"] = date
            if description:
                values["description"] = description
            if lead_days is not None:
                values["lead_days"] = int(lead_days)
            if enabled is not None:
                values["enabled"] = bool(enabled)
            memo = self._get_store().update_commemoration(key, values)
            if not memo:
                return f"纪念日「{key}」不存在"
            return f"纪念日已更新: {memo['icon']} {memo['name']} ({memo['date']}) · 提前 {memo['lead_days']} 天开始活动"
        except Exception as e:
            return f"编辑纪念日失败: {e}"

    async def earth_delete_commemoration(self, key: str) -> str:
        """删除纪念日 (已生成的纪念日活动区域不受影响)"""
        try:
            if not self._get_store().delete_commemoration(key):
                return f"纪念日「{key}」不存在"
            return f"纪念日「{key}」已删除"
        except Exception as e:
            return f"删除纪念日失败: {e}"

    async def earth_pull_memory(self, times: int = 1) -> str:
        """替玩家进行回忆抽卡 (times: 1 单抽 / 10 十连)。消耗弥娅币，重复碎片自动转化——佳说想抽的时候可以帮他"""
        try:
            r = self._get_store().pull_memory(int(times))
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

    async def earth_claim_battle_pass(self, tier: int) -> str:
        """领取每周纪行某一档奖励 (先 earth_view_battle_pass 看哪档可领)"""
        try:
            r = self._get_store().claim_battle_pass_tier(int(tier))
            if not r.get("success"):
                return r.get("message", "领取失败")
            return f"纪行第 {r['tier']} 档奖励已领取: +{r['reward_currency']} 弥娅币 ✦"
        except Exception as e:
            return f"领取纪行失败: {e}"

    async def earth_issue_care_commission(
        self,
        care_key: str,
        title: str,
        description: str = "",
        subtasks: Optional[List[Any]] = None,
        reward_currency: int = 6,
        reward_exp: int = 10,
        message: str = "",
    ) -> str:
        """发布一张你现场创作的关怀委托 (care_key 来自上下文里的[关怀时机]，内容完全由你即兴创作)。

        message 是你想对佳说的一句话，会随委托保存，并在他没看到时作为主动敲门文案。
        """
        try:
            r = self._get_store().issue_care_commission(
                care_key=care_key, title=title, description=description,
                subtasks=subtasks, reward_currency=reward_currency, reward_exp=reward_exp,
                message=message,
            )
            if not r.get("success"):
                return r.get("message", "发布失败")
            quest = r["quest"]
            return (
                f"关怀委托已发布: 「{quest['title']}」(类型 {r['care_key']} · 今日第 {r.get('today_count')} 张)\n"
                f"留言: {message[:80] or '(无)'}"
            )
        except Exception as e:
            return f"发布关怀委托失败: {e}"

    async def earth_redeem_service(self, item_key: str = "", item_id: Optional[int] = None) -> str:
        """替佳使用一张服务券 (抱抱券/晚安耳语等)。佳说"抱抱我/用一下券"时调用。

        返回的基调文案只是参考——请基于这张券的作用，用你当前的人格和此刻的语境即兴创作回应，不要照念。
        """
        try:
            r = self._get_store().redeem_service_ticket(item_id=item_id, item_key=item_key)
            if not r.get("success"):
                return r.get("message", "使用失败")
            remaining = f" · 背包还剩 {r['remaining']} 张" if r.get("remaining") else " · 这是最后一张"
            return (
                f"服务券「{r['name']}」已使用{remaining}。\n"
                f"基调参考 (请基于这张券的作用，用你当前的人格即兴创作回应，不要照念): {r['interaction']}"
            )
        except Exception as e:
            return f"使用服务券失败: {e}"


_tools: Optional[EarthOnlineTools] = None


def get_earth_tools() -> EarthOnlineTools:
    """获取全局地球online工具实例"""
    global _tools
    if _tools is None:
        _tools = EarthOnlineTools()
    return _tools


EARTH_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "earth_summary",
            "description": "查看地球online总览（玩家等级/经验/地球币 + 背包/任务/角色/剧情统计）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_player",
            "description": "查看玩家当前状态（等级/经验/地球币）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_items",
            "description": "查看背包中的现实物品列表",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "description": "物品状态，可选 normal/used/lost"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_add_item",
            "description": "往背包添加一件现实物品（支持自定义字段与三段式档案）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "物品名称"},
                    "category": {"type": "string", "description": "分类: digital数码/book书籍/life生活/food食品/tool工具/clothing服饰/collectible收藏/other其他"},
                    "rarity": {"type": "string", "description": "稀有度: common普通/uncommon稀有/rare珍贵/epic史诗/legendary传说"},
                    "quantity": {"type": "integer", "description": "数量，默认1"},
                    "description": {"type": "string", "description": "物品描述"},
                    "markdown": {"type": "string", "description": "三段式档案 (封面+简介+详情，可选)"},
                    "image_path": {"type": "string", "description": "照片路径 (可选)"},
                    "fields": {"type": "object", "description": "自定义字段对象 (可选，如 {\"brand\": \"Apple\"})"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_quests",
            "description": "查看任务列表（可指定状态过滤）",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "description": "状态: pending待开始/ongoing进行中/completed已完成/failed失败/cancelled已取消，留空查全部"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_add_quest",
            "description": "弥娅主动给亲爱的安排任务（主线/支线/日常/可选），奖励为弥娅币；可设循环任务（daily每天/weekly每周，完成后自动重置，适合喝水/睡觉等日常习惯）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务描述"},
                    "quest_type": {"type": "string", "description": "main主线/branch支线/daily日常/optional可选，默认branch"},
                    "must_complete": {"type": "boolean", "description": "是否必须完成（失败扣弥娅币）"},
                    "reward_currency": {"type": "integer", "description": "奖励弥娅币（弥娅发放的互动货币）"},
                    "reward_exp": {"type": "integer", "description": "奖励经验"},
                    "penalty_currency": {"type": "integer", "description": "失败惩罚弥娅币"},
                    "deadline": {"type": "string", "description": "截止时间 ISO格式，如 2026-08-21T20:00:00"},
                    "subtasks": {"type": "array", "description": "子任务清单 [{\"text\":\"...\",\"done\":false}]"},
                    "recurring": {"type": "string", "description": "循环类型: 空/一次, daily/每天, weekly/每周"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_accept_quest",
            "description": "接取任务（待开始 → 进行中），表示玩家开始执行该任务",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_complete_quest",
            "description": "将任务标记为完成并发放奖励",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_fail_quest",
            "description": "将任务标记为失败（扣除惩罚地球币）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_check_overdue",
            "description": "检查所有逾期未完成任务并自动惩罚",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_get_quest",
            "description": "查看单个任务详情（含子任务清单与完成进度）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_activity",
            "description": "查看地球online 全局动态流（任务/物品/角色/剧情/签到/成就/寄语的最新事件）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认20"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_weekly_report",
            "description": "生成地球online 本周报告（周一至今的任务完成率/签到/动态/成就/收入统计）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_remind_due",
            "description": "查看即将到期或已逾期的未完成任务，用于提醒亲爱的（默认3天内）",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "未来几天内到期，默认3"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_titles",
            "description": "查看地球online 可佩戴称号（默认称号 + 已解锁成就称号 + 当前佩戴）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_analyze",
            "description": "综合分析地球online 全部数据（玩家/任务/到期/背包/好感/成就/周报），弥娅担任策划时为佳的现实生活提供建议的基础",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_daily_ritual",
            "description": "弥娅每日仪式：检查逾期任务并自动处理 + 今天到期提醒 + 签到状态，弥娅主动关心佳的每日开局时调用",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_achievements",
            "description": "查看地球online 全部成就（含进度与解锁状态）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_story",
            "description": "查看已记录的人生剧情",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_add_story",
            "description": "记录一段人生剧情（生活事件剧情化，可关联角色/物品/照片）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "剧情标题"},
                    "content": {"type": "string", "description": "剧情内容"},
                    "event_type": {"type": "string", "description": "life生活/achievement成就/quest任务/character人物，默认life"},
                    "character_id": {"type": "integer", "description": "关联角色ID（可选）"},
                    "item_id": {"type": "integer", "description": "关联物品ID（可选）"},
                    "image_path": {"type": "string", "description": "关联照片路径（可选）"},
                    "fields": {"type": "object", "description": "自定义字段对象（可选）"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_characters",
            "description": "查看角色图鉴与好感度",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_add_character",
            "description": "在角色图鉴中添加一位现实人物",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "人物姓名"},
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_adjust_affinity",
            "description": "调整角色好感度（可正可负，需说明原因）",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer", "description": "角色ID"},
                    "delta": {"type": "integer", "description": "好感度变动值，如 +5 / -3"},
                    "reason": {"type": "string", "description": "变动原因"},
                },
                "required": ["character_id", "delta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_post_note",
            "description": "发布一条弥娅寄语（显示在地球online 前台首页公告栏，可置顶）",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "寄语内容（可含 Markdown）"},
                    "mood": {"type": "string", "description": "心情: neutral平静/happy开心/caring关心/excited兴奋/proud骄傲/sleepy困倦/sad难过，默认neutral"},
                    "pinned": {"type": "boolean", "description": "是否置顶显示在首页，默认false"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_notes",
            "description": "查看已发布的弥娅寄语列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_world",
            "description": "查看佳的单人地球online 世界地图、区域解锁条件与探索进度",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_explore",
            "description": "探索一个世界地图区域，触发一次只属于佳的随机发现并领取弥娅币与经验奖励；区域可能绑定真实地理围栏，玩家在附近时应携带当前坐标 latitude/longitude 一起探索",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_key": {"type": "string", "description": "区域 key，例如 miya_garden、city_lumen"},
                    "latitude": {"type": "number", "description": "玩家当前纬度（区域绑定地理围栏时必填）"},
                    "longitude": {"type": "number", "description": "玩家当前经度（区域绑定地理围栏时必填）"},
                },
                "required": ["region_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_world_status",
            "description": "查看当前地球online 的世界时间、天气和限时活动区域",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_real_context",
            "description": "读取真实现实数据连接状态与最近天气快照；未同步时明确返回未同步",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_refresh_real_context",
            "description": "刷新真实天气快照，可选传入城市，不会用模拟天气冒充现实",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名称；留空使用已保存城市"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_region_commission",
            "description": "为指定世界区域生成今天唯一的专属委托，自动带上当前天气和时间氛围",
            "parameters": {
                "type": "object",
                "properties": {"region_key": {"type": "string", "description": "区域 key，例如 miya_garden、night_sea"}},
                "required": ["region_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_grant_currency",
            "description": "发放或扣除弥娅币（弥娅发放的互动货币，佳可用它兑换弥娅的互动服务）",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer", "description": "数量（正数发放，负数扣除）"}},
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_grant_exp",
            "description": "发放开拓经验",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer", "description": "经验数量"}},
                "required": ["amount"],
            },
        },
    },
    # ── 策划级: 实体修改/删除 ──────────────────────
    {
        "type": "function",
        "function": {
            "name": "earth_get_item",
            "description": "查看一件背包物品的完整档案（修改前先看清楚）",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "description": "物品ID"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_item",
            "description": "从背包删除一件物品（删除不可恢复，确认不再需要时才用）",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "description": "物品ID"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_cancel_quest",
            "description": "取消任务（无惩罚下架，比失败温和；适合任务不再适用的情况）",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "integer", "description": "任务ID"}},
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_get_character",
            "description": "查看一位角色的完整档案（关系/好感度/备注/生日）",
            "parameters": {
                "type": "object",
                "properties": {"character_id": {"type": "integer", "description": "角色ID"}},
                "required": ["character_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_character",
            "description": "从角色图鉴删除一位角色（确认关系档案不再需要时才用）",
            "parameters": {
                "type": "object",
                "properties": {"character_id": {"type": "integer", "description": "角色ID"}},
                "required": ["character_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_story",
            "description": "删除一段人生剧情（记录错误/重复时才用）",
            "parameters": {
                "type": "object",
                "properties": {"story_id": {"type": "integer", "description": "剧情ID"}},
                "required": ["story_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_note",
            "description": "删除一条弥娅寄语（过期或说错话时收回）",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "integer", "description": "寄语ID（先调用 earth_list_notes 查看）"}},
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_equip_title",
            "description": "帮玩家佩戴称号（必须是默认称号或已解锁的成就/商城称号，先用 earth_list_titles 查看可选项）",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string", "description": "称号文本，需与 earth_list_titles 中的完全一致"}},
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_checkin",
            "description": "替玩家完成每日签到（发放弥娅币+经验+连签奖励；已签到会提示 already 不会重复发奖）。玩家提到昨晚睡了多久时带上 sleep_hours，睡眠越好体力回复越多",
            "parameters": {
                "type": "object",
                "properties": {
                    "sleep_hours": {"type": "number", "description": "昨晚睡眠时长（小时，0-24，可选）"},
                },
                "required": [],
            },
        },
    },
    # ── 策划级: 玩家档案 ──────────────────────────
    {
        "type": "function",
        "function": {
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
        },
    },
    # ── 策划级: 世界与地理围栏 ────────────────────
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_world_events",
            "description": "查看自定义世界发现清单（可按区域过滤，不传查全部）",
            "parameters": {
                "type": "object",
                "properties": {"region_key": {"type": "string", "description": "区域 key，留空查全部"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_world_event",
            "description": "删除一条自定义世界发现（玩家尚未遇到的将不会再遇到）",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "integer", "description": "世界发现ID（先调用 earth_list_world_events 查看）"}},
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    # ── 策划级: 限时活动运营 ──────────────────────
    {
        "type": "function",
        "function": {
            "name": "earth_list_event_areas",
            "description": "查看全部限时活动区域（内置+自定义，含进行中/未运行状态与起止日期），策划运营活动前先看这份清单",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_event_area",
            "description": "删除自定义限时活动（连带删除其活动商店商品；内置活动不可删除）",
            "parameters": {
                "type": "object",
                "properties": {"event_key": {"type": "string", "description": "活动 key"}},
                "required": ["event_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    # ── 策划级: 商店查询 ──────────────────────────
    {
        "type": "function",
        "function": {
            "name": "earth_list_miya_shop",
            "description": "查看弥娅专属兑换所货架（商品/价格/限购/已兑换次数与玩家弥娅币余额）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_event_shop",
            "description": "查看限时活动商店货架（含内置+自定义商品、限购与已兑换状态；购买由玩家自己操作）",
            "parameters": {
                "type": "object",
                "properties": {"event_key": {"type": "string", "description": "活动 key，先调用 earth_list_event_areas 查看"}},
                "required": ["event_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    # ── 策划级: 查询补充 ──────────────────────────
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_quest_history",
            "description": "查看任务结算历史（已完成/失败的归档，含奖励与惩罚）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认20"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_memory_pool",
            "description": "查看回忆卡池（价格/保底/收集进度/最近抽取）。抽取操作由玩家在商城完成",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_view_battle_pass",
            "description": "查看本周纪行进度（积分来源/各档奖励/可领取档位）。领取由玩家在数据中心完成",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_weekly_challenge",
            "description": "查看本周挑战主题与星级进度（完成委托 2/4/5 个 → ★/★★/★★★）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_commemorations",
            "description": "查看纪念日列表（每年循环；临近自动开限时活动、当天自动写寄语）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_generate_daily_commissions",
            "description": "生成今日日常委托（幂等，每日仪式也会自动生成）。数量由 earth_online.daily.daily_quest_count 配置",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_stats",
            "description": "查看数据中心总览（任务/物品/角色/剧情/签到/成就多维分布 + 7日完成趋势 + 汇率）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_list_checkins",
            "description": "查看签到历史（含每晚睡眠时长与体力回复记录）",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "条数，默认14"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_currency_ledger",
            "description": "查看货币/经验流水（评估经济、发周报用；currency 可选 miya/earth/exp）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "条数，默认20"},
                    "currency": {"type": "string", "description": "筛选币种: miya弥娅币/earth现实资产/exp经验，缺省全部"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_delete_commemoration",
            "description": "删除纪念日（已生成的纪念日活动区域不受影响）",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "纪念日 key"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_pull_memory",
            "description": "替玩家进行回忆抽卡（times: 1 单抽 / 10 十连）。消耗弥娅币，重复碎片自动转化——佳说想抽的时候可以帮他",
            "parameters": {
                "type": "object",
                "properties": {"times": {"type": "integer", "description": "抽数: 1 或 10，默认1"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earth_claim_battle_pass",
            "description": "领取每周纪行某一档奖励（先 earth_view_battle_pass 看哪档可领）",
            "parameters": {
                "type": "object",
                "properties": {"tier": {"type": "integer", "description": "档位 1-10"}},
                "required": ["tier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
]
