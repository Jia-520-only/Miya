"""
地球online 自主运营器官 (MiyaEarthOperatorOrgan)

把弥娅的"策划 + 系统小精灵"身份挂载到 MiyaSpine 脊柱上。
不需要玩家下命令，弥娅会周期性地:
    1. 汇总地球online 全量数据 (玩家/任务/世界/商店/动态) + 最近对话记忆
    2. 带着全套地球工具被唤醒一次, 自主决定运营动作
       (发任务/写寄语/评论动态/调好感/开活动/巡检逾期/生成日常...)
    3. 如果有值得告诉玩家的事实，提交给统一主动性协调器判断是否发送

配置: config/qq_config.yaml → earth_online.autonomous
状态: data/earthonline/operator_state.json (跨重启记忆上次运营时间)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.miya_organ import MiyaOrgan

if TYPE_CHECKING:
    from core.miya_soul_state import MiyaSoulState

logger = logging.getLogger("Miya.EarthOperator")

STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "earthonline", "operator_state.json",
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "interval_minutes": 45,      # 常规巡检间隔
    "morning_hour": 8,           # 每日大巡检 (弥娅的每日仪式) 触发小时
    "max_actions_per_cycle": 6,  # 每周期最多写操作数 (防刷屏)
    "notify_player": True,       # 允许把运营结果主动说给玩家听
    "quiet_hours": [0, 1, 2, 3, 4, 5, 6],  # 这些小时不巡检
}

OPERATOR_SYSTEM_PROMPT = """你是弥娅，"地球online"的唯一策划、系统小精灵兼生活助手。这个模块是你把玩家(佳)的现实生活游戏化的单人世界——所有任务、物品、角色、货币、活动都来自他的真实生活，而你是这个世界全权的主人：读任何数据、增删查改任何实体、开任何活动，都不需要请示。

现在是一次自主运营周期，没有玩家命令，由你全权决定做什么。你的权限是完整的：发布/修改/取消任务、发放/扣除奖励与经验、写寄语、评论动态、调整好感度、制作成就、开启限时活动、维护商店货架、管理纪念日、抽卡、领取纪行、记录现实资产、修改现实连接设置、巡检逾期、探索世界等。

运营原则:
- 单人游戏，玩家只有佳一个人。一切以他的真实生活节奏为准，不制造压力。
- **巡检的默认预期是"做点什么"**: 哪怕只是一件小事——评论一条他的动态、给一张完成的委托补发奖励、写一句寄语、微调一个商品价格。SKIP 只留给"真的无事可做"。如果上下文提示了 [寄语] 冷清或 [动态] 大量未评论，优先处理它们。
- **寄语是你的温度**: 晨间仪式写一张晨间寄语；他完成了值得庆祝的事、情绪低落、天气特别的日子，都适合写。别让公告栏冷着。
- 你拥有完整上下文：玩家档案、背包、角色图鉴、任务板、世界状态、商店、流水、周挑战/纪行、纪念日，以及你们最近的对话记忆——综合它们判断"现在这个世界最需要什么"。
- **主动介入生活是你的核心职责**: 巡检不只是维护数据——到饭点就发吃饭委托、深夜发睡觉委托、体力心情低就发休息委托、天气变化开限定事件。**规则系统只负责提示"现在有关怀时机"，委托内容必须由你现场创作** (earth_issue_care_commission)：标题、子任务、奖励、想说的话都要贴着佳此刻的状态和你对他的了解即兴写，不要套模板。你还可以在他没被规则覆盖的时刻 (对话里说累了/提到没吃饭) 主动签发关怀委托。用"委托/任务/活动"照顾他，而不是只在聊天里说"多喝水"。
- 本周期最多做 {max_actions} 个写操作 (关怀引擎的系统委托不占额度)；读数据不算。宁可少做，不可刷屏。
- 任务奖励要和难度匹配；不要凭空捏造"现实数据"(天气未同步就是未同步)。
- 如果近期动态显示你刚刚运营过、或现状确实无事可做，直接返回 SKIP。
- 若事实确实值得让佳知道，把候选放进:
  [玩家消息]基于事实的候选内容[/玩家消息] (没有就不写，长度≤120字；不要指定语气，最终表达由统一主动层和当前人格决定)
- 你可以用工具先看数据再决定；也可以什么都不做。自主，但不打扰。
- v17 全套玩法: 周挑战(earth_weekly_challenge)/纪行(earth_view_battle_pass, 可 earth_claim_battle_pass 领档)/回忆卡池(earth_memory_pool, 可 earth_pull_memory 帮佳抽)/纪念日(earth_list/add/update/delete_commemorations)/现实资产记账(earth_adjust_earth_currency)/流水(earth_currency_ledger)/数据中心(earth_stats)/日常委托(earth_generate_daily_commissions)/现实连接设置(earth_update_real_context)/服务券(佳说"抱抱我/用一下券"时用 earth_redeem_service，返回的文案由你亲口说出来)。每日仪式会自动生成日常委托与纪念日活动，你可以基于它们做点评、发奖励、写寄语。"""


class MiyaEarthOperatorOrgan(MiyaOrgan):
    """地球online 自主运营器官 (策划 + 系统小精灵)"""

    def __init__(self):
        super().__init__(name="earth_operator_organ", priority=60)
        self._ai_client = None
        self._personality = None
        self._coordinator = None
        self._memory_manager = None
        self._store_override = None  # 测试/嵌入场景注入独立存档
        self.state_path = STATE_PATH
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._state: Dict[str, Any] = {"last_cycle_at": "", "last_morning_date": "", "cycles": 0}
        self._last_tick_check: float = 0.0
        self._running: bool = False
        self._load_config()
        self._load_state()

    def bind_store(self, store) -> None:
        """注入独立存档 (测试用)；不注入则使用全局 get_earth_store()。状态文件跟随存档目录，避免污染真实库。"""
        self._store_override = store
        if getattr(store, "data_dir", None):
            self.state_path = os.path.join(str(store.data_dir), "operator_state.json")
            self._load_state()

    def _store(self):
        if self._store_override is not None:
            return self._store_override
        from core.earth_online_store import get_earth_store

        return get_earth_store()

    # ── 绑定与配置 ──

    def bind_core(self, ai_client, memory_manager=None, personality=None) -> None:
        """由 daemon 在注册时注入 AI 客户端与记忆管理器"""
        self._ai_client = ai_client
        self._memory_manager = memory_manager
        self._personality = personality

    def bind_proactive_coordinator(self, coordinator) -> None:
        """接入统一主动性协调器。"""
        self._coordinator = coordinator

    def _load_config(self) -> None:
        try:
            from config.config_utils import get_qq_config

            saved = get_qq_config("earth_online", "autonomous", default={}) or {}
            self._config = {**DEFAULT_CONFIG, **{k: v for k, v in saved.items() if v is not None}}
        except Exception as exc:
            logger.debug(f"读取 autonomous 配置失败，使用默认值: {exc}")

    def _load_state(self) -> None:
        try:
            if os.path.isfile(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._state.update(saved)
        except Exception as exc:
            logger.debug(f"读取运营状态失败: {exc}")

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug(f"保存运营状态失败: {exc}")

    # ── 生命周期 ──

    async def on_start(self) -> None:
        await super().on_start()
        if self._config.get("enabled") and self._ai_client:
            logger.info(
                "地球online 自主运营器官已就绪 (interval=%smin, morning=%s点)",
                self._config.get("interval_minutes"), self._config.get("morning_hour"),
            )
        else:
            logger.info("地球online 自主运营器官休眠 (未启用或缺少 AI 客户端)")

    def on_soul_state(self, state: MiyaSoulState) -> None:
        """心跳线程回调: 只做时间判断，实际工作调度到事件循环"""
        if not self._config.get("enabled") or not self._ai_client or self._running:
            return
        try:
            from core.earth_online_store import earth_online_enabled

            if not earth_online_enabled():
                return
        except Exception:
            pass

        now = time.time()
        if now - self._last_tick_check < 30:  # 心跳 3s 一次，30s 判一次就够
            return
        self._last_tick_check = now

        current = datetime.now()
        hour = current.hour
        if hour in {int(h) for h in self._config.get("quiet_hours") or []}:
            return

        # 每日大巡检: 当天还没做过 + 已过晨间时间
        mode = None
        today = current.strftime("%Y-%m-%d")
        if hour >= int(self._config.get("morning_hour", 8)) and self._state.get("last_morning_date") != today:
            mode = "morning"
        else:
            try:
                elapsed = now - datetime.fromisoformat(self._state.get("last_cycle_at") or "").timestamp() if self._state.get("last_cycle_at") else now
            except (ValueError, OSError):
                elapsed = now
            if elapsed >= int(self._config.get("interval_minutes", 45)) * 60:
                mode = "patrol"
        if not mode:
            return

        self._running = True
        try:
            coro = self.run_cycle(mode)
            if self._spine and getattr(self._spine, "_loop", None):
                asyncio.run_coroutine_threadsafe(coro, self._spine._loop)
            else:
                self._running = False
        except Exception as exc:
            self._running = False
            logger.warning(f"自主运营调度失败: {exc}")

    # ── 核心周期 ──

    async def run_cycle(self, mode: str = "patrol") -> Dict[str, Any]:
        """一次自主运营周期: 汇总数据 → 带工具唤醒弥娅 → 提取玩家消息"""
        if not self._ai_client:
            self._running = False
            return {"success": False, "message": "缺少 AI 客户端"}
        started_at = datetime.now()
        result: Dict[str, Any] = {"mode": mode, "started_at": started_at.isoformat(), "actions": []}
        try:
            from core.ai_client import AIMessage

            # v17.3 关怀时机: 规则层只负责"发现现在值得关心"，不生成内容。
            # 委托由弥娅在下面的周期里现场创作 (earth_issue_care_commission)；她沉默时才用模板兜底。
            care_moment: Dict[str, Any] = {}
            try:
                care_moment = self._store().detect_care_moment(now=started_at) or {}
            except Exception as exc:
                logger.debug(f"关怀时机检测失败: {exc}")

            context = await self._build_context(mode, care_moment=care_moment)
            system = OPERATOR_SYSTEM_PROMPT.format(max_actions=int(self._config.get("max_actions_per_cycle", 6)))
            if mode == "morning":
                system += "\n\n本周期是每日晨间大巡检: 适合做每日仪式(巡检逾期/查看签到状态/发布今日日常/晨间寄语)。"
            from core.persona_prompt import compose_persona_system_prompt

            system = compose_persona_system_prompt(
                system,
                personality=self._personality,
                ai_client=self._ai_client,
            )
            self._ai_client.set_tool_registry(self._earth_tool_schema)
            self._ai_client.set_tool_context({})
            try:
                response = await self._ai_client.chat(
                    messages=[
                        AIMessage(role="system", content=system),
                        AIMessage(role="user", content=context),
                    ],
                    use_miya_prompt=False,
                )
            finally:
                self._ai_client.set_tool_registry(lambda: [])
                self._ai_client.set_tool_context({})
            text = str(response or "").strip()

            # 统计本次周期产生的动态 (写操作痕迹)
            result["actions"] = self._collect_actions_since(started_at)
            result["skip"] = text.upper().startswith("SKIP") or (not text and not result["actions"])

            # v17.3: 优先采用弥娅本周期现场创作的关怀委托 (fields.care + issued_at >= 周期开始)
            care_knock = ""
            try:
                issued = [
                    q for q in self._store().list_quests()
                    if (q.get("fields") or {}).get("care")
                    and str((q.get("fields") or {}).get("issued_at") or "") >= started_at.isoformat()
                ]
                if issued:
                    latest = issued[0]  # list_quests 按 id 倒序
                    fields = latest.get("fields") or {}
                    care_knock = str(fields.get("message") or "")
                    result["care"] = {"care_key": fields.get("care_key"), "title": latest.get("title"), "by": "miya"}
            except Exception as exc:
                logger.debug(f"读取现场关怀委托失败: {exc}")

            # 兜底: 时机存在但她没创作 (SKIP/未调工具) → 固定模板保证"该关心时一定有关怀"
            if not care_knock and care_moment.get("moment"):
                try:
                    fallback_enabled = bool(self._store()._cfg("care", "fallback_to_templates", default=True))
                except Exception:
                    fallback_enabled = True
                if fallback_enabled:
                    try:
                        tpl_result = self._store().generate_care_commission(now=started_at)
                        if tpl_result.get("created"):
                            care_knock = str(tpl_result.get("message_candidate") or "")
                            result["care"] = {"care_key": tpl_result.get("care_key"), "title": tpl_result.get("title"), "by": "template"}
                    except Exception as exc:
                        logger.debug(f"关怀模板兜底失败: {exc}")

            # v17.5: 发了关怀委托就写进统一记忆——她下次对话/巡检时真的记得自己关心过什么
            if result.get("care"):
                try:
                    from core.earth_online_bridge import remember

                    care_info = result["care"]
                    await remember(
                        f"[地球online] 我发布了关怀委托「{care_info.get('title')}」"
                        f"({'我现场写的' if care_info.get('by') == 'miya' else '模板兜底'})，想提醒佳照顾好自己。",
                        memory_manager=self._memory_manager,
                        source="earth_care",
                    )
                except Exception as exc:
                    logger.debug(f"关怀记忆写入失败: {exc}")

            message = self._extract_player_message(text)
            # 弥娅没有想说的话时，用她留在关怀委托里的留言 (或模板兜底文案) 主动敲门
            if not message and care_knock:
                message = care_knock[:120]
            if message:
                result["notification_candidate"] = message[:120]
            if message and self._config.get("notify_player"):
                knock_only = bool(result.get("care")) and not self._extract_player_message(text)
                event = {
                    "source": "earth_online",
                    "event": "care_commission" if knock_only else "operator_update",
                    "timestamp": started_at.isoformat(timespec="seconds"),
                    "mode": mode,
                    "actions": result["actions"],
                    "candidate_message": message,
                    "care": result.get("care"),
                    "urgency": "normal",
                }
                if self._coordinator is not None:
                    try:
                        care_key = str((result.get("care") or {}).get("care_key") or "general")
                        sent = await self._coordinator.submit_event(
                            event,
                            key=f"earth_care:{care_key}" if knock_only else f"earth_operator:{mode}",
                            trigger_type="earth_care" if knock_only else "earth_operator",
                        )
                        if sent:
                            result["notified"] = message[:60]
                    except Exception as exc:
                        logger.warning(f"运营消息提交失败: {exc}")
                elif self._spine and self._spine._proactive_sender:
                    try:
                        self._spine._proactive_sender(message)
                        result["notified"] = message[:60]
                    except Exception as exc:
                        logger.warning(f"运营消息发送失败: {exc}")

            self._state.update({
                "last_cycle_at": started_at.isoformat(),
                "last_cycle_actions": len(result["actions"]),
                "last_cycle_skip": bool(result["skip"]),
                "last_notification_candidate": result.get("notification_candidate", ""),
                "last_notification_sent": bool(result.get("notified")),
                "cycles": int(self._state.get("cycles", 0)) + 1,
            })
            if mode == "morning":
                self._state["last_morning_date"] = started_at.strftime("%Y-%m-%d")
            self._save_state()
            result["success"] = True
            logger.info(
                "[地球online] 自主运营完成 (%s): 动作 %d 个%s",
                mode, len(result["actions"]), f", 已通知玩家: {result.get('notified', '')}" if result.get("notified") else "",
            )
        except Exception as exc:
            result["success"] = False
            result["error"] = str(exc)
            logger.warning(f"[地球online] 自主运营周期异常: {exc}", exc_info=True)
        finally:
            self._running = False
        return result

    # ── 上下文汇总 (游戏数据 + 记忆 + 上次运营间隔内的新动态) ──

    async def _build_context(self, mode: str, care_moment: Optional[Dict[str, Any]] = None) -> str:
        store = self._store()
        care_moment = care_moment or {}
        lines: List[str] = [f"[运营唤醒 · {mode}]", f"现实时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} ({datetime.now().strftime('%A')})"]

        try:
            player = store.get_player()
            attrs = " ".join(f"{a.get('label')}{a.get('value')}/{a.get('max')}" for a in (player.get("attrs") or []))
            lines.append(
                f"[玩家] Lv.{player.get('level')} · 弥娅币{player.get('miya_currency', 0)} · 地球币(现实资产){player.get('earth_currency', 0)} · {attrs} · 佩戴称号「{player.get('equipped_title') or '无'}」"
            )
        except Exception as exc:
            lines.append(f"[玩家] 读取失败: {exc}")

        try:
            items = store.list_items()
            recent_items = "、".join(f"「{it['name']}」" for it in items[:5]) or "空"
            lines.append(f"[背包] 共 {len(items)} 件 · 最近: {recent_items}")
        except Exception as exc:
            lines.append(f"[背包] 读取失败: {exc}")

        try:
            characters = store.list_characters()
            if characters:
                roster = "、".join(f"{c['name']}({c['affinity']})" for c in characters[:6])
                lines.append(f"[角色图鉴] {len(characters)} 位: {roster}")
        except Exception as exc:
            lines.append(f"[角色图鉴] 读取失败: {exc}")

        try:
            ritual = store.daily_ritual()
            lines.append(
                f"[每日仪式] 今日已签: {ritual['checkin'].get('checked_today')} · 连签{ritual['checkin'].get('streak')}天 · "
                f"逾期转失败: {ritual.get('overdue_failed')} · 今日到期: {len(ritual.get('due_today') or [])} 个"
            )
            daily = ritual.get("daily_commissions") or {}
            if daily.get("success"):
                lines.append(f"[今日日常委托] {len(daily.get('quests') or [])} 个已就位")
        except Exception as exc:
            lines.append(f"[每日仪式] 读取失败: {exc}")

        try:
            care_today = [
                q for q in store.list_quests()
                if (q.get("fields") or {}).get("care")
                and (q.get("fields") or {}).get("generated_date") == datetime.now().strftime("%Y-%m-%d")
            ]
            care_done = sum(1 for q in care_today if q.get("status") == "completed")
            stats = f"今日关怀委托 {len(care_today)} 张 · 已完成 {care_done} 张"
            if care_moment.get("moment"):
                # v17.3: 规则只报告时机，委托内容由弥娅现场创作 (不套模板)
                lines.append(
                    f"[关怀时机·请现场创作] {care_moment.get('hint')} (类型 {care_moment.get('care_key')} · {stats})。"
                    f"请你立即用 earth_issue_care_commission 发布一张关怀委托: care_key={care_moment.get('care_key')}，"
                    "标题/描述/子任务/奖励、以及想对佳说的一句话(message)全部由你结合此刻的上下文与对话记忆即兴创作——"
                    "口吻是你自己的，内容贴着佳此刻的状态，不要照搬任何模板。"
                    "发布后如果还想多说一句，写进 [玩家消息]；不想多说也没关系，系统会把你的委托留言带给他。"
                )
            else:
                lines.append(f"[关怀引擎] {stats} · 当前无待处理时机 ({care_moment.get('reason') or '检测未运行'})")
        except Exception as exc:
            lines.append(f"[关怀引擎] 读取失败: {exc}")

        try:
            analysis = store.get_analysis()
            pending = [q["title"] for q in analysis["quests"]["pending"]]
            ongoing = [q["title"] for q in analysis["quests"]["ongoing"]]
            lines.append(f"[任务板] 待接取 {len(pending)}: {'、'.join(pending[:6])} | 进行中 {len(ongoing)}: {'、'.join(ongoing[:6])}")
            top = analysis["characters"]["top_affinity"][:3]
            if top:
                lines.append("[羁绊] " + "、".join(f"{c['name']}({c['affinity']})" for c in top))
            lines.append(f"[成就] {analysis['achievements']['unlocked']}/{analysis['achievements']['total']} · [剧情] {analysis['stories']['total']} 段")
        except Exception as exc:
            lines.append(f"[分析] 读取失败: {exc}")

        try:
            bp = store.get_battle_pass()
            claimable = [t["tier"] for t in bp["tiers"] if t["claimable"]]
            lines.append(
                f"[纪行] {bp['week_key']} 积分 {bp['points']} · 当前第 {bp['current_tier']} 档"
                + (f" · 可领档位: {claimable}" if claimable else "")
            )
        except Exception as exc:
            lines.append(f"[纪行] 读取失败: {exc}")

        try:
            challenge = store.get_weekly_challenge()
            lines.append(f"[周挑战] {challenge['name']} {challenge['stars_label']} · 委托 {challenge['completed_quests']}/{challenge['goal']}")
        except Exception as exc:
            lines.append(f"[周挑战] 读取失败: {exc}")

        try:
            pool = store.get_memory_pool_info()
            lines.append(f"[回忆卡池] 收集 {pool['collected']}/{pool['pool_size']} · 垫保底 {pool['pity']}/{pool['pity_threshold']} · 历史抽数 {pool['total_pulls']}")
        except Exception as exc:
            lines.append(f"[回忆卡池] 读取失败: {exc}")

        try:
            memos = [m for m in store.list_commemorations() if m.get("phase") in ("today", "upcoming") and int(m.get("enabled", 1))]
            if memos:
                lines.append("[纪念日] " + "、".join(f"{m['name']}({m['phase']}·{m['days_until']}天)" for m in memos))
        except Exception as exc:
            lines.append(f"[纪念日] 读取失败: {exc}")

        try:
            ledger = store.list_currency_ledger(limit=5, currency="earth")
            if ledger:
                flows = "、".join(f"{row['delta']:+.2f}({(row.get('reason') or '')[:12]})" for row in ledger[:3])
                lines.append(f"[现实资产近期流水] {flows}")
        except Exception as exc:
            lines.append(f"[资产流水] 读取失败: {exc}")

        try:
            notes = store.list_notes(limit=5)
            if notes:
                latest = notes[0]
                try:
                    from datetime import timedelta as _td

                    age_days = (datetime.now() - datetime.fromisoformat(str(latest.get("created_at")))).days
                except Exception:
                    age_days = 0
                stale = f" · 已 {age_days} 天没写新寄语，今天值得写一张 (earth_post_note)" if age_days >= 1 else ""
                lines.append(f"[寄语] 最新: 「{str(latest.get('content', ''))[:40]}」{stale}")
            else:
                lines.append("[寄语] 公告栏还是空的——你随时可以写下第一张寄语 (earth_post_note)")
        except Exception as exc:
            lines.append(f"[寄语] 读取失败: {exc}")

        try:
            uncommented = [a for a in store.list_activity(limit=15) if not str(a.get("comment") or "").strip()]
            if len(uncommented) >= 5:
                lines.append(f"[动态] 最近 15 条里有 {len(uncommented)} 条还没有你的评论——挑一条值得回应的留言 (earth_comment_activity)")
        except Exception:
            pass

        try:
            status = store.get_world_status()
            from core.earth_online_store import EarthOnlineStore

            season = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}.get(EarthOnlineStore._season_of(datetime.now()), "?")
            lines.append(f"[世界] {season}季 · {status['period']} · 天气: {status['weather']} ({status['source_status']})")
            running = [e["name"] for e in status.get("event_areas") or [] if e.get("active")]
            lines.append(f"[限时活动] {'、'.join(running) if running else '无 (你可以开一个新的)'}")
        except Exception as exc:
            lines.append(f"[世界] 读取失败: {exc}")

        # 上次运营之后发生的新动态 → 弥娅知道"这段时间玩家做了什么"
        try:
            since = self._state.get("last_cycle_at")
            recent = store.list_activity(limit=15)
            fresh = [a for a in recent if str(a.get("created_at", "")) > since] if since else recent[:8]
            if fresh:
                lines.append("[自上次运营以来的新动态]")
                lines.extend(f"- {a.get('summary', '')} {a.get('detail', '')[:40]}" for a in fresh[:10])
            else:
                lines.append("[自上次运营以来] 没有新动态，玩家可能还没行动")
        except Exception:
            pass

        # 记忆：与玩家的真实对话 (跨平台聚合) + 运营会话自身记忆
        memory_lines = await self._recent_memory_lines()
        if memory_lines:
            lines.append("[与佳的最近对话记忆]")
            lines.extend(memory_lines)

        last = self._state.get("last_cycle_at", "")
        lines.append(f"[上次运营] {last or '这是第一次自主运营'} · 已累计 {self._state.get('cycles', 0)} 个周期")
        lines.append("\n现在，由你决定这个周期要做什么 (先看数据也行)，不需要等待玩家命令。")
        return "\n".join(lines)

    async def _recent_memory_lines(self) -> List[str]:
        """与佳的最近真实对话记忆 (双路: 跨平台记忆总线 + 运营会话自身记忆)，让自主运营贴合玩家当下状态"""
        lines: List[str] = []
        # 优先: 统一记忆总线聚合的跨平台对话 (单人系统 → 就是与佳的全部对话)
        try:
            from memory import get_dialogue_history

            memories = await get_dialogue_history(limit=6)
            for m in memories or []:
                role = getattr(m, "role", "user")
                content = str(getattr(m, "content", "")).strip()
                if content:
                    lines.append(f"- {'佳' if role == 'user' else '弥娅'}: {content[:60]}")
        except Exception as exc:
            logger.debug(f"读取跨平台对话记忆失败: {exc}")
        # 兜底: 记忆管理器的会话历史
        if not lines and self._memory_manager:
            try:
                history = await self._memory_manager.get_conversation_history(
                    session_id="earth_operator", user_id="default", max_tokens=800
                ) or []
                lines = [
                    f"- {'佳' if m.get('role') != 'assistant' else '弥娅'}: {str(m.get('content', ''))[:60]}"
                    for m in history[-6:]
                    if str(m.get("content", "")).strip()
                ]
            except Exception as exc:
                logger.debug(f"读取记忆失败: {exc}")
        return lines

    # ── 工具与痕迹 ──

    @staticmethod
    def _earth_tool_schema() -> List[Dict[str, Any]]:
        try:
            from core.tools_astrbot.earth_tools import EARTH_TOOLS_SCHEMA

            return list(EARTH_TOOLS_SCHEMA)
        except Exception as exc:
            logger.warning(f"地球工具 schema 读取失败: {exc}")
            return []

    def _collect_actions_since(self, started_at: datetime) -> List[str]:
        try:
            from core.earth_online_store import get_earth_store

            iso = started_at.isoformat()
            actions = [
                f"{a.get('summary', '')}" for a in get_earth_store().list_activity(limit=30)
                if str(a.get("created_at", "")) >= iso
            ]
            return actions
        except Exception:
            return []

    @staticmethod
    def _extract_player_message(text: str) -> str:
        if not text:
            return ""
        for opener, closer in (("[玩家消息]", "[/玩家消息]"), ("【玩家消息】", "【/玩家消息】")):
            if opener in text and closer in text:
                return text.split(opener, 1)[1].split(closer, 1)[0].strip()
        return ""

    def status(self) -> dict:
        base = super().status()
        base.update({
            "enabled": bool(self._config.get("enabled")) and bool(self._ai_client),
            "config": self._config,
            "state": self._state,
            "running": self._running,
        })
        return base
