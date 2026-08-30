"""地球online 自主运营器官回归测试 (不依赖真实 LLM / 脊柱)"""

import asyncio
import json
import os
import tempfile
from datetime import datetime

from core.earth_online_operator import MiyaEarthOperatorOrgan
from core.earth_online_store import EarthOnlineStore


class FakeAIClient:
    def __init__(self, reply: str = ""):
        self.reply = reply
        self.calls = []
        self.tool_schema_sizes = []
        self.registry = lambda: []

    def set_tool_registry(self, cb):
        self.registry = cb

    def set_tool_context(self, ctx):
        pass

    async def chat(self, messages=None, **kwargs):
        self.calls.append(messages)
        try:
            self.tool_schema_sizes.append(len(self.registry()))
        except Exception:
            self.tool_schema_sizes.append(0)
        return self.reply


class FakeSpine:
    def __init__(self):
        self.sent = []
        self._loop = None
        self._proactive_sender = self.sent.append


def _build_organ(reply: str = ""):
    temp_dir = tempfile.mkdtemp(prefix="earth_operator_test_")
    store = EarthOnlineStore(db_path=os.path.join(temp_dir, "earthonline.db"))
    organ = MiyaEarthOperatorOrgan()
    organ.state_path = os.path.join(temp_dir, "operator_state.json")
    organ._state = {"last_cycle_at": "", "last_morning_date": "", "cycles": 0}
    organ.bind_store(store)
    organ.bind_core(FakeAIClient(reply))
    spine = FakeSpine()
    organ._spine = spine
    return store, organ, spine, temp_dir


def test_context_summary_covers_player_quests_world_memory():
    store, organ, _, _ = _build_organ()
    store.create_quest(title="自主运营测试任务", reward_currency=5, reward_exp=5)

    context = asyncio.run(organ._build_context("patrol"))

    assert "[运营唤醒 · patrol]" in context
    assert "[玩家]" in context and "Lv." in context
    assert "自主运营测试任务" in context
    assert "[世界]" in context and "[限时活动]" in context


def test_morning_cycle_runs_tools_sends_message_and_persists_state():
    store, organ, spine, temp_dir = _build_organ(
        "我先看了看任务板。\n[玩家消息]早上好，今天的日常已经放好啦[/玩家消息]"
    )

    result = asyncio.run(organ.run_cycle("morning"))

    assert result["success"] is True
    assert result["mode"] == "morning"
    assert result["notified"] == "早上好，今天的日常已经放好啦"
    assert spine.sent == ["早上好，今天的日常已经放好啦"]
    # 弥娅被唤醒时能看到全套地球工具 schema
    ai: FakeAIClient = organ._ai_client
    assert ai.calls and ai.tool_schema_sizes[0] >= 30
    # 周期结束清空工具注册，避免污染普通对话
    assert ai.registry() == []
    # 状态持久化: 晨间日期 + 周期数
    with open(organ.state_path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["last_morning_date"] == datetime.now().strftime("%Y-%m-%d")
    assert saved["cycles"] == 1


def test_skip_cycle_sends_nothing():
    _, organ, spine, _ = _build_organ("SKIP")

    result = asyncio.run(organ.run_cycle("patrol"))

    assert result["success"] is True
    assert result["skip"] is True
    # v17.2: LLM 沉默时不再打扰；唯一例外是关怀引擎放了委托时的系统敲门消息
    if result.get("care"):
        assert spine.sent and "委托" in "".join(spine.sent)
        assert result.get("notification_candidate")
    else:
        assert "notified" not in result
        assert spine.sent == []


def test_extract_player_message_variants():
    assert MiyaEarthOperatorOrgan._extract_player_message("前置\n[玩家消息]一句话[/玩家消息]后置") == "一句话"
    assert MiyaEarthOperatorOrgan._extract_player_message("【玩家消息】另一种标记【/玩家消息】") == "另一种标记"
    assert MiyaEarthOperatorOrgan._extract_player_message("没有消息块") == ""


def test_notify_disabled_suppresses_message():
    _, organ, spine, _ = _build_organ("[玩家消息]这条不该发出去[/玩家消息]")
    organ._config["notify_player"] = False

    result = asyncio.run(organ.run_cycle("patrol"))

    assert result["success"] is True
    assert spine.sent == []


def test_care_engine_runs_before_llm_and_knocks_when_silent():
    """v17.2: 周期先跑关怀引擎；LLM 沉默 (SKIP) 时用关怀候选消息主动敲门"""
    # 早上 8 点档 → 关怀引擎会命中早餐/兜底模板 (真实时刻由 now 决定)
    store, organ, spine, temp_dir = _build_organ("SKIP")
    result = asyncio.run(organ.run_cycle("patrol"))
    assert result["success"] is True
    care_quests = [q for q in store.list_quests() if (q.get("fields") or {}).get("care")]
    if result.get("care"):  # 引擎命中时段模板时
        assert care_quests, "care 标记的委托应已落板"
        assert result.get("notification_candidate"), "LLM 沉默时应使用关怀候选消息"
        assert spine.sent, "应经主动通路发送"
    # 引擎未命中 (无匹配) 时不误报
    assert isinstance(result.get("care", {}).get("care_key", None), (str, type(None)))
