"""Miya's own control over the camera: intents, impressions, watching loop."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from mcpserver.screen_vision import vision_agent
from mcpserver.screen_vision.service import ScreenVisionService
from mcpserver.screen_vision.vision_agent import (
    Impression,
    VisionAgency,
    build_interpreter_prompt,
    parse_interpretation,
)


@pytest.fixture()
def agency(tmp_path: Path) -> VisionAgency:
    return VisionAgency(tmp_path / "agency.json")


@pytest.fixture(autouse=True)
def _no_live_camera_inventory(monkeypatch):
    """Keep this module's agent tests away from the physical cameras.

    One test starts the real watching loop; without this it probes real devices
    from its own thread and can crash the interpreter mid-teardown.
    """
    from mcpserver.screen_vision import camera_manager

    manager = camera_manager.get_camera_manager()
    monkeypatch.setattr(manager, "usable_indices", lambda: [])
    monkeypatch.setattr(manager, "scan", lambda **_kwargs: {})
    monkeypatch.setattr(manager, "_browser_frame", None)


# --- her own words, not knobs ---------------------------------------------


def test_intent_is_stored_in_her_own_words_and_survives_a_restart(tmp_path: Path):
    path = tmp_path / "agency.json"
    first = VisionAgency(path)
    first.add_intent("想知道佳有没有离开座位", speak=True)
    first.add_intent("留意佳是不是在熬夜", speak=False, note="超过两点就说一句")

    reloaded = VisionAgency(path)
    texts = [item.text for item in reloaded.intents()]
    assert "想知道佳有没有离开座位" in texts
    assert "留意佳是不是在熬夜" in texts
    assert "image" not in path.read_text(encoding="utf-8")


def test_intent_card_separates_speak_from_silent_watching(agency: VisionAgency):
    agency.add_intent("想知道佳有没有离开座位", speak=True)
    agency.add_intent("留意佳是不是在熬夜", speak=False)
    card = agency.intent_card()
    assert "想知道佳有没有离开座位" in card
    assert "可以说出来" in card
    assert "只记录，不主动说" in card


def test_duplicate_intent_text_replaces_rather_than_piles_up(agency: VisionAgency):
    agency.add_intent("看着佳")
    agency.add_intent("看着佳")
    assert len([item for item in agency.intents() if item.text == "看着佳"]) == 1


def test_intents_can_be_retired_and_removed(agency: VisionAgency):
    intent = agency.add_intent("想知道佳有没有离开座位")
    assert intent is not None
    assert agency.set_intent_active(intent.id, False) is True
    assert agency.intents(active_only=True) == []
    assert agency.remove_intent(intent.id) is True
    assert agency.remove_intent("nonexistent") is False


def test_blank_intent_is_rejected(agency: VisionAgency):
    assert agency.add_intent("   ") is None


def test_agency_store_never_persists_an_image(agency: VisionAgency):
    agency.record(Impression(at=1.0, summary="佳在敲键盘", activity="工作"))
    payload = json.dumps(agency.describe(), ensure_ascii=False)
    assert "image" not in payload
    assert "佳在敲键盘" in payload


def test_impressions_are_bounded(agency: VisionAgency):
    for index in range(vision_agent.MAX_IMPRESSIONS + 40):
        agency.record(Impression(at=float(index), summary=f"印象 {index}"))
    kept = agency.impressions(limit=1000)
    assert len(kept) == vision_agent.MAX_IMPRESSIONS
    assert kept[-1].summary == f"印象 {vision_agent.MAX_IMPRESSIONS + 39}"


# --- interpreting a moment -------------------------------------------------


def test_interpreter_prompt_carries_intents_and_memory():
    prompt = build_interpreter_prompt(
        local_reading={"faces": True, "action": {"label": "在打键盘或动鼠标"},
                       "pose_quality": {"usable": True}, "camera_count": 2},
        intent_card="[弥娅给自己定的观察意图]\n- 想知道佳有没有离开座位",
        memory_card="[弥娅最近对佳的观察印象]\n- 21:04 佳在敲键盘",
        cadence_seconds=30,
    )
    assert "想知道佳有没有离开座位" in prompt
    assert "21:04" in prompt
    assert "2 个摄像头" in prompt or '"使用了几个摄像头": 2' in prompt
    # The model is asked for structured output, not prose.
    assert '"notable"' in prompt
    # And it must be told not to talk like a dashboard.
    assert "不要提及摄像头、模型、识别、置信度、关键点" in vision_agent.INTERPRETER_SYSTEM_PROMPT


def test_parse_interpretation_accepts_plain_json():
    parsed = parse_interpretation('{"summary":"佳在敲键盘","activity":"工作","mood":"专注",'
                                  '"attention":"看屏幕","notable":true,"say":"还在忙呀"}')
    assert parsed is not None
    assert parsed["summary"] == "佳在敲键盘"
    assert parsed["notable"] is True
    assert parsed["say"] == "还在忙呀"


def test_interpreter_context_is_background_and_cannot_supply_objects():
    prompt = build_interpreter_prompt(
        local_reading={"faces": 0, "pose_quality": {"usable": True}, "observed_at": "2026-10-05 14:13:00"},
        intent_card="留意佳有没有休息", memory_card="以前猜测佳困了",
        cadence_seconds=30, conversation_context="assistant: 那杯水凉了",
        long_term_context="佳买过零食",
    )
    assert "近期对话背景（不是当前画面证据）" in prompt
    assert "长期记忆背景（不是当前画面证据）" in prompt
    assert "历史观察印象（过去的推测，不是当前画面证据）" in prompt
    assert "不能据此确定杯子、食物、手机等物体" in prompt
    assert "那杯水凉了" in prompt and "佳买过零食" in prompt
    assert '"检测到可信人体骨架": true' in prompt
    assert "2026-10-05 14:13:00" in prompt


def test_interpretation_receives_the_unified_dialogue_and_memory(monkeypatch, agency):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    snapshot = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="刚买了零食", timestamp="2026-10-05")],
        memory_context="佳喜欢聊游戏",
    )
    provider = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(vision_agent, "_context_provider", provider)
    monkeypatch.setattr(vision_agent, "_context_provider_loop", None)
    agent = vision_agent.VisionAgent()
    call_model = AsyncMock(return_value=('{"summary":"有人坐着","notable":false}', "test"))
    monkeypatch.setattr(agent, "_call_model", call_model)

    result = asyncio.run(agent._interpret({"faces": 1}, agency))

    assert result["summary"] == "有人坐着"
    provider.assert_awaited_once()
    prompt = call_model.call_args.args[1]
    assert "user: 刚买了零食" in prompt
    assert "佳喜欢聊游戏" in prompt


def test_unified_context_provider_runs_on_its_own_loop(monkeypatch):
    import threading
    from types import SimpleNamespace

    provider_loop = asyncio.new_event_loop()
    ready = threading.Event()
    called_threads = []

    def run_provider_loop():
        asyncio.set_event_loop(provider_loop)
        provider_loop.call_soon(ready.set)
        provider_loop.run_forever()

    async def provider():
        called_threads.append(threading.current_thread().name)
        assert asyncio.get_running_loop() is provider_loop
        return SimpleNamespace(messages=[], memory_context="统一记忆")

    thread = threading.Thread(target=run_provider_loop, name="test-camera-context", daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=5)
        monkeypatch.setattr(vision_agent, "_context_provider", provider)
        monkeypatch.setattr(vision_agent, "_context_provider_loop", provider_loop)
        assert asyncio.run(vision_agent.VisionAgent._miya_context_for_interpretation()) == ("", "统一记忆")
        assert called_threads == ["test-camera-context"]
    finally:
        provider_loop.call_soon_threadsafe(provider_loop.stop)
        thread.join(timeout=5)
        provider_loop.close()


def test_unified_context_timeout_keeps_the_observer_available(monkeypatch):
    async def provider():
        await asyncio.Event().wait()

    monkeypatch.setattr(vision_agent, "_context_provider", provider)
    monkeypatch.setattr(vision_agent, "_context_provider_loop", None)
    monkeypatch.setattr(vision_agent, "get_qq_config", lambda *args, **kwargs: 0.01)
    assert asyncio.run(vision_agent.VisionAgent._miya_context_for_interpretation()) == ("", "")


def test_no_face_or_body_cannot_queue_a_hallucinated_greeting(monkeypatch, agency):
    from unittest.mock import AsyncMock

    agent = vision_agent.VisionAgent()
    monkeypatch.setattr(vision_agent, "get_vision_agency", lambda: agency)
    monkeypatch.setattr(agent, "_look", AsyncMock(return_value={
        "status": "success", "faces": 0, "pose_quality": {"usable": False},
        "message": "没有可靠的人体线索",
    }))
    monkeypatch.setattr(agent, "_interpret", AsyncMock(return_value={
        "summary": "猜测有人", "activity": "", "mood": "", "attention": "",
        "notable": True, "say": "你回来啦",
    }))
    monkeypatch.setattr(agent, "_remember_notable", AsyncMock(return_value=False))

    result = asyncio.run(agent.tick())

    assert result["impression"]["notable"] is False
    assert result["impression"]["say"] == ""
    assert agent.peek_messages() == []


def test_parse_interpretation_survives_a_fenced_reply():
    parsed = parse_interpretation('Sure.\n```json\n{"summary":"他在看手机","notable":false,"say":"SKIP"}\n```')
    assert parsed is not None
    assert parsed["summary"] == "他在看手机"
    # SKIP means she chose not to speak, not that she has nothing to say.
    assert parsed["say"] == ""


def test_parse_interpretation_rejects_unusable_replies():
    assert parse_interpretation("") is None
    assert parse_interpretation("not json") is None
    assert parse_interpretation('{"activity":"工作"}') is None  # no summary


# --- the watching loop -----------------------------------------------------


def test_agent_state_reports_her_own_cadence():
    agent = vision_agent.VisionAgent()
    state = agent.state()
    assert state["running"] is False
    assert state["interval_seconds"] == vision_agent.DEFAULT_INTERVAL_SECONDS
    assert state["last_error"] == ""


def test_agent_clamps_an_unreasonable_cadence():
    agent = vision_agent.VisionAgent()
    try:
        assert agent.start(interval_seconds=0.01)["interval_seconds"] == vision_agent.MIN_INTERVAL_SECONDS
        assert agent.start(interval_seconds=999999)["interval_seconds"] == vision_agent.MAX_INTERVAL_SECONDS
    finally:
        asyncio.run(agent.stop())


def test_agent_loop_runs_on_its_own_thread(monkeypatch):
    """Boot happens on a background thread with no running loop."""
    import threading

    agent = vision_agent.VisionAgent()
    threads: list[str] = []

    async def fake_tick(**_kwargs):
        threads.append(threading.current_thread().name)
        return {"status": "success"}

    monkeypatch.setattr(agent, "tick", fake_tick)
    try:
        assert agent.start(interval_seconds=vision_agent.MIN_INTERVAL_SECONDS)["running"] is True
        for _ in range(60):
            if threads:
                break
            time.sleep(0.05)
    finally:
        asyncio.run(agent.stop())

    assert threads, "观察循环没有在自己的线程上跑起来"
    assert threads[0] == "Miya-VisionAgent"
    assert agent.running is False


# --- boot behaviour --------------------------------------------------------


def _allow_autostart(monkeypatch, *, autonomous: bool = True, mode: str = "companion",
                     autostart: bool = True) -> None:
    from core import camera_control

    monkeypatch.setattr("core.camera_control.read_state",
                        lambda: {"mode": mode, "autonomous": autonomous, "local_only": True})
    monkeypatch.setattr(vision_agent, "_agency_config",
                        lambda: {"autostart": autostart, "autostart_delay_seconds": 0,
                                 "interval_seconds": 30, "mode": "auto",
                                 "seed_intents": ["留意佳在不在电脑前"]})


def test_autostart_is_refused_without_consent(monkeypatch):
    """Miya watching from boot must never override a "no"."""
    _allow_autostart(monkeypatch, autonomous=False)
    allowed, reason = vision_agent.should_autostart()
    assert allowed is False
    assert "自主观察尚未开启" in reason

    _allow_autostart(monkeypatch, mode="off")
    allowed, reason = vision_agent.should_autostart()
    assert allowed is False
    assert "关闭" in reason

    _allow_autostart(monkeypatch, autostart=False)
    allowed, reason = vision_agent.should_autostart()
    assert allowed is False
    assert "配置" in reason


def test_autostart_seeds_intents_in_her_own_words_and_starts_the_loop(monkeypatch):
    _allow_autostart(monkeypatch)
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agent = vision_agent.VisionAgent()
    monkeypatch.setattr(vision_agent, "_agent", agent)

    async def fake_tick(**_kwargs):
        return {"status": "success"}

    monkeypatch.setattr(agent, "tick", fake_tick)
    try:
        result = asyncio.run(vision_agent.autostart_after_delay())
        assert result["started"] is True
        assert agent.running is True
        assert agent.state()["autostarted"] is True
        # The configured intent was written down verbatim, not as a threshold.
        assert [item.text for item in agency.intents()] == ["留意佳在不在电脑前"]
    finally:
        asyncio.run(agent.stop())
        monkeypatch.setattr(vision_agent, "_agent", vision_agent.get_vision_agent())
        agency._intents = []


def test_seeding_never_overwrites_intents_she_changed_herself(monkeypatch):
    _allow_autostart(monkeypatch)
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency.add_intent("我自己想留意的事")
    seeded = vision_agent.seed_intents_from_config()
    assert seeded == []
    assert [item.text for item in agency.intents()] == ["我自己想留意的事"]
    agency._intents = []


def test_autostart_skips_when_she_is_already_watching(monkeypatch):
    _allow_autostart(monkeypatch)
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agent = vision_agent.VisionAgent()
    monkeypatch.setattr(vision_agent, "_agent", agent)

    async def fake_tick(**_kwargs):
        return {"status": "success"}

    monkeypatch.setattr(agent, "tick", fake_tick)
    try:
        first = asyncio.run(vision_agent.autostart_after_delay())
        second = asyncio.run(vision_agent.autostart_after_delay())
        assert first["started"] is True
        assert second["started"] is True
        assert second["reason"] == "已在运行"
    finally:
        asyncio.run(agent.stop())
        monkeypatch.setattr(vision_agent, "_agent", vision_agent.get_vision_agent())
        agency._intents = []


def test_consent_revoked_during_the_delay_cancels_autostart(monkeypatch):
    """Turning the camera off while boot settles must win."""
    from core import camera_control

    state = {"autonomous": True, "mode": "companion", "local_only": True}
    monkeypatch.setattr("core.camera_control.read_state", lambda: dict(state))
    monkeypatch.setattr(vision_agent, "_agency_config",
                        lambda: {"autostart": True, "autostart_delay_seconds": 0.05,
                                 "interval_seconds": 30, "mode": "auto", "seed_intents": []})
    agent = vision_agent.VisionAgent()
    monkeypatch.setattr(vision_agent, "_agent", agent)

    async def scenario():
        task = asyncio.create_task(vision_agent.autostart_after_delay())
        await asyncio.sleep(0.01)
        state["autonomous"] = False
        state["mode"] = "off"
        return await task

    try:
        result = asyncio.run(scenario())
        assert result["started"] is False
        assert agent.running is False
    finally:
        monkeypatch.setattr(vision_agent, "_agent", vision_agent.get_vision_agent())


def test_default_seed_intents_are_natural_language_not_thresholds():
    for text in vision_agent.DEFAULT_SEED_INTENTS:
        assert len(text) > 4
        assert not any(char.isdigit() for char in text)
        assert "_" not in text


def test_tick_records_an_impression_from_local_facts_when_the_model_is_absent(monkeypatch):
    agent = vision_agent.VisionAgent()
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []

    async def fake_look():
        return {"status": "success", "faces": 1, "camera_count": 1,
                "message": "看到你了，在打键盘或动鼠标。",
                "action": {"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.7},
                "pose_quality": {"usable": True}}

    async def no_model(_reading, _agency):
        return None

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", no_model)
    result = asyncio.run(agent.tick())

    assert result["interpreted"] is False
    # With no model she records only what the local layer actually supports,
    # and the source says so instead of pretending to be insight.
    assert result["impression"]["source"] == "local"
    assert "打键盘" in result["impression"]["summary"]
    agency._intents = []
    agency._impressions = []


def test_tick_with_a_model_records_her_own_interpretation(monkeypatch):
    agent = vision_agent.VisionAgent()
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []
    agency.add_intent("想知道佳有没有离开座位", speak=True)

    async def fake_look():
        return {"status": "success", "faces": 1, "camera_count": 1,
                "message": "看到你了。", "action": {"kind": "typing", "label": "在打键盘或动鼠标"},
                "pose_quality": {"usable": True}}

    async def fake_interpret(_reading, _agency):
        return {"summary": "佳正埋头敲键盘", "activity": "工作", "mood": "专注",
                "attention": "看屏幕", "notable": True, "say": "还在忙呀，我陪着你"}

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", fake_interpret)
    result = asyncio.run(agent.tick())

    assert result["interpreted"] is True
    assert result["impression"]["summary"] == "佳正埋头敲键盘"
    assert result["impression"]["mood"] == "专注"
    assert result["impression"]["source"] == "miya"
    # Her intent is linked to the impression, so attention is traceable.
    assert result["impression"]["intent_ids"]
    # And the thing she decided was worth saying is queued exactly once.
    taken = agent.take_message()
    assert taken is not None and taken["message"] == "还在忙呀，我陪着你"
    assert agent.take_message() is None
    agency._intents = []
    agency._impressions = []


def test_silent_mode_still_looks_and_remembers_but_does_not_speak(monkeypatch):
    agent = vision_agent.VisionAgent()
    agent._mode = "silent"
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []

    async def fake_look():
        return {"status": "success", "faces": 1, "camera_count": 1, "message": "看到你了。",
                "action": {"kind": "typing", "label": "在打键盘或动鼠标"}, "pose_quality": {"usable": True}}

    async def fake_interpret(_reading, _agency):
        return {"summary": "佳在敲键盘", "activity": "工作", "mood": "", "attention": "",
                "notable": True, "say": "说点什么"}

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", fake_interpret)
    result = asyncio.run(agent.tick())

    assert result["impression"]["summary"] == "佳在敲键盘"
    assert agent.peek_messages() == []
    agent._mode = "auto"
    agency._intents = []
    agency._impressions = []


def test_a_blank_camera_is_never_interpreted_as_content(monkeypatch):
    """A black rectangle must not become a confident description of Jia."""
    agent = vision_agent.VisionAgent()
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []
    interpreted = {"called": False}

    async def fake_look():
        return {"status": "unknown", "faces": 0, "camera_count": 1,
                "blank_frame": True, "message": "摄像头返回的是全黑画面。",
                "sources_used": [1], "observations": []}

    async def should_not_run(_reading, _agency):
        interpreted["called"] = True
        return {"summary": "佳在认真工作", "notable": True, "say": "加油"}

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", should_not_run)
    result = asyncio.run(agent.tick())

    assert interpreted["called"] is False
    assert result["interpreted"] is False
    assert result["impression"]["source"] == "local"
    assert "全黑" in result["impression"]["summary"]
    assert agent.peek_messages() == []
    assert "全黑" in agent.state()["last_error"]
    agency._intents = []
    agency._impressions = []


def test_fusion_flags_a_blank_frame_only_when_pixels_were_decoded():
    """A device that failed to open must not be reported as a black frame."""
    from mcpserver.screen_vision.camera_manager import fuse_observations
    from mcpserver.screen_vision.local_camera import mark_vision_result

    black = fuse_observations([{"index": 1, "result": mark_vision_result(
        {"status": "error", "blank_frame": True, "faces": 0, "observations": []})}])
    assert black["blank_frame"] is True
    assert black["blank_indices"] == [1]

    failed_open = fuse_observations([{"index": 2, "result": {
        "status": "error", "message": "无法打开摄像头", "faces": 0, "observations": []}}])
    assert failed_open["blank_frame"] is False
    assert failed_open["blank_indices"] == []


def test_fusion_reports_pixels_with_no_face_as_not_blank():
    from mcpserver.screen_vision.camera_manager import fuse_observations
    from mcpserver.screen_vision.local_camera import mark_vision_result

    fused = fuse_observations([{"index": 0, "result": mark_vision_result(
        {"status": "success", "faces": 0, "luminance": 88.0,
         "observations": [{"pose_quality": {"usable": True}}]})}])
    assert fused["blank_frame"] is False


def test_browser_frame_is_reused_so_the_backend_does_not_fight_for_the_device(monkeypatch):
    """A live preview owns the camera; the backend must see through its frame."""
    from mcpserver.screen_vision import camera_manager, local_camera

    monkeypatch.setattr("core.camera_control.read_state", lambda: {"camera_policy": "auto"})

    manager = camera_manager.get_camera_manager()
    manager._sources = {}
    manager.remember_browser_frame(index=0, data_url="data:image/jpeg;base64,ZmFrZQ==")

    stored = manager.browser_frame()
    assert stored is not None
    assert stored["index"] == 0

    # Old frames must not be presented as current reality.
    stored["at"] = 1.0
    manager._browser_frame = stored
    assert manager.browser_frame(max_age_seconds=1.0) is None

    agent = vision_agent.VisionAgent()
    manager.remember_browser_frame(index=0, data_url="data:image/jpeg;base64,ZmFrZQ==")
    monkeypatch.setattr(manager, "usable_indices", lambda: [0])
    # Never touch real hardware from a unit test.
    monkeypatch.setattr(manager, "scan", lambda **_kwargs: {})
    monkeypatch.setattr(manager, "refresh_names", lambda: None)

    def fake_analyze(_data, **_kwargs):
        return local_camera.mark_vision_result(
            {"status": "success", "faces": 1, "luminance": 90.0,
             "observations": [{"face_signals": {"count": 1, "largest_ratio": 0.06, "centered": True},
                               "pose_quality": {"usable": True},
                               "action": {"kind": "typing", "label": "在打键盘或动鼠标", "confidence": 0.7}}]}
        )

    monkeypatch.setattr(local_camera, "analyze_local_frame", fake_analyze)

    async def scenario():
        return await agent._look()

    fused = asyncio.run(scenario())
    # The browser's frame produced the reading, and the device was not opened.
    assert fused["faces"] == 1
    assert fused["action"]["kind"] == "typing"
    assert fused["sources_used"] == [0]
    manager._browser_frame = None
    manager._sources = {}


@pytest.fixture()
def single_camera_observer(monkeypatch):
    from mcpserver.screen_vision import camera_capture, camera_manager, camera_stream, local_camera

    manager = camera_manager.CameraManager()
    manager._sources = {
        0: camera_manager.CameraSource(index=0, usable=True, checked=True),
        2: camera_manager.CameraSource(index=2, checked=True, failure_count=1, next_retry_at=1.0),
    }
    pool = camera_stream.CameraFramePool()
    calls = []
    monkeypatch.setattr(camera_manager, "get_camera_manager", lambda: manager)
    monkeypatch.setattr(camera_stream, "get_camera_pool", lambda: pool)
    monkeypatch.setattr(pool, "start_reader", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(manager, "refresh_names", lambda: None)
    monkeypatch.setattr("core.camera_control.read_state", lambda: {"identity_recognition": False})
    agent = vision_agent.VisionAgent()
    agent._preferred_index = 0
    monkeypatch.setattr(agent, "_camera_selection", lambda _manager: ("single", {0}, 0, set(), None, True))

    def capture(index, **_kwargs):
        calls.append(("capture", index))
        return {"image_data": "data:image/jpeg;base64,ZmFrZQ=="}

    monkeypatch.setattr(camera_capture, "capture_camera_frame", capture)
    monkeypatch.setattr(local_camera, "analyze_local_frame", lambda *_args, **_kwargs: {
        "status": "success", "faces": 1, "luminance": 90.0, "observations": [],
    })
    return agent, manager, pool, calls


@pytest.mark.parametrize("failed_other_camera", [False, True])
def test_single_camera_keeps_a_fresh_reader_across_sweeps(single_camera_observer, monkeypatch, failed_other_camera):
    agent, manager, pool, calls = single_camera_observer
    if not failed_other_camera:
        manager._sources.pop(2)
    buffer = pool.buffer(0)
    buffer.image_data = "data:image/jpeg;base64,ZmFrZQ=="
    buffer.at = time.time()
    monkeypatch.setattr(pool, "stop_all", lambda: calls.append(("stop_all",)))
    agent._last_sweep = time.monotonic() - vision_agent.SWEEP_INTERVAL_SECONDS - 1

    result = asyncio.run(agent._look())

    assert result["faces"] == 1
    assert result["sources_used"] == [0]
    assert calls == []


def test_single_camera_ignores_a_cached_unselected_device(single_camera_observer):
    agent, _manager, pool, calls = single_camera_observer
    pool.buffer(2).image_data = "data:image/jpeg;base64,ZmFrZQ=="
    pool.buffer(2).at = time.time()

    result = asyncio.run(agent._look())

    assert result["sources_used"] == [0]
    assert calls == [("capture", 0)]


def test_single_camera_retries_its_selected_failed_device(single_camera_observer, monkeypatch):
    agent, manager, pool, calls = single_camera_observer
    manager._sources[0].usable = False
    manager._sources[0].failure_count = 1
    manager._sources[0].next_retry_at = 1.0
    monkeypatch.setattr(pool, "stop_all", lambda: calls.append(("stop_all",)))

    result = asyncio.run(agent._look())

    assert result["faces"] == 1
    assert calls == [("stop_all",), ("capture", 0)]
    assert manager._sources[0].failure_count == 0


@pytest.mark.parametrize("reader_releases", [False, True])
def test_single_camera_never_opens_behind_a_stalled_reader(single_camera_observer, monkeypatch, reader_releases):
    from types import SimpleNamespace

    agent, _manager, pool, calls = single_camera_observer
    reader = SimpleNamespace(alive=True)
    pool._readers[0] = reader
    pool.buffer(0).image_data = "data:image/jpeg;base64,ZmFrZQ=="
    pool.buffer(0).at = time.time() - 300

    def stop_reader(index):
        calls.append(("stop_reader", index))
        reader.alive = not reader_releases

    monkeypatch.setattr(pool, "stop_reader", stop_reader)
    result = asyncio.run(agent._look())

    if reader_releases:
        assert result["faces"] == 1
        assert calls == [("stop_reader", 0), ("capture", 0)]
    else:
        assert result["status"] == "unavailable"
        assert calls == [("stop_reader", 0)]
        assert "旧读帧线程" in result["failures"][0]["message"]
        assert "黑帧" not in _manager.sources()[0].reason


def test_camera_event_accepts_a_browser_frame_without_persisting_it():
    service = ScreenVisionService()
    from mcpserver.screen_vision.camera_manager import get_camera_manager

    manager = get_camera_manager()
    manager._browser_frame = None

    payload = json.loads(service._camera_event({
        "event": {"kind": "companion_frame", "summary": "陪伴视觉仍在观察"},
        "camera_index": 0,
        "image_data": "data:image/jpeg;base64,ZmFrZQ==",
    }))
    assert payload["status"] == "success"
    assert "image_data" not in json.dumps(payload)
    stored = manager.browser_frame()
    assert stored is not None and stored["index"] == 0

    # A non-image payload must be ignored rather than stored.
    manager._browser_frame = None
    service._camera_event({"event": {"kind": "x", "summary": "y"}, "image_data": "not-an-image"})
    assert manager.browser_frame() is None
    manager._browser_frame = None


def test_preview_release_clears_backend_browser_ownership():
    service = ScreenVisionService()
    from mcpserver.screen_vision.camera_manager import get_camera_manager
    from mcpserver.screen_vision.camera_stream import get_camera_pool

    manager = get_camera_manager()
    pool = get_camera_pool()
    manager._browser_frame = None
    manager._sources = {}
    pool.stop_all()
    pool._buffers = {}
    pool._browser_touched = {}

    frame = "data:image/jpeg;base64,ZmFrZQ=="
    manager.remember_browser_frame(index=0, data_url=frame)
    pool.publish_browser_frame(0, frame)
    assert pool.browser_owns(0)

    payload = json.loads(service._camera_event({
        "event": {"kind": "preview_released"},
        "camera_index": 0,
    }))

    assert payload == {"status": "success", "released": 0}
    assert manager.browser_frame() is None
    assert not pool.browser_owns(0)


def test_preview_release_with_source_ids_clears_all_browser_owned_frames():
    service = ScreenVisionService()
    from mcpserver.screen_vision.camera_manager import get_camera_manager
    from mcpserver.screen_vision.camera_stream import get_camera_pool

    manager = get_camera_manager()
    pool = get_camera_pool()
    manager._browser_frame = None
    manager._browser_frames = {}
    manager._sources = {}
    pool.stop_all()
    pool._buffers = {}
    pool._browser_touched = {}

    frame = "data:image/jpeg;base64,ZmFrZQ=="
    manager.remember_browser_frame(index=0, data_url=frame, browser_source_id="browser:one")
    manager.remember_browser_frame(index=1, data_url=frame, browser_source_id="browser:two")
    pool.publish_browser_frame(0, frame)
    pool.publish_browser_frame(1, frame)
    assert pool.browser_owns(0)
    assert pool.browser_owns(1)

    payload = json.loads(service._camera_event({
        "event": {"kind": "preview_released"},
        "camera_index": 0,
        "browser_source_ids": ["browser:one", "browser:two"],
    }))

    assert payload == {"status": "success", "released": 0}
    assert manager.browser_frames() == []
    assert not pool.browser_owns(0)
    assert not pool.browser_owns(1)


# --- her queue of things to say --------------------------------------------


def _agent_with_message(
    agent,
    at: float,
    message: str,
    summary: str = "看到佳了",
    faces: int | None = None,
):
    agent._queue_message(
        vision_agent.Impression(at=at, summary=summary, say=message, faces=faces)
    )


def test_saying_the_same_thing_twice_refreshes_instead_of_repeating():
    """Watching all evening produced three near-identical 'I see you' lines."""
    agent = vision_agent.VisionAgent()
    now = time.time()
    _agent_with_message(agent, now, "终于看到你了，这会儿没对着屏幕呢")
    _agent_with_message(agent, now + 30.0, "终于看到你了，这会儿没对着屏幕呢")
    _agent_with_message(agent, now + 60.0, "终于看到你了，这会儿没对着屏幕呢")
    pending = agent.peek_messages()
    assert len(pending) == 1
    assert pending[0]["at"] == now + 60.0, "重复的话应该刷新时间，而不是排成一列"


def test_different_messages_are_all_kept():
    agent = vision_agent.VisionAgent()
    now = time.time()
    _agent_with_message(agent, now, "终于看到你了")
    _agent_with_message(agent, now + 10.0, "你在忙什么？")
    assert len(agent.peek_messages()) == 2


def test_new_presence_state_drops_old_opposite_presence_message():
    agent = vision_agent.VisionAgent()
    now = time.time()
    _agent_with_message(agent, now, "这会儿没看到人", summary="画面里没人", faces=0)
    _agent_with_message(
        agent,
        now + 10.0,
        "看到你回来了",
        summary="看到佳了",
        faces=1,
    )
    pending = agent.peek_messages()
    assert [item["message"] for item in pending] == ["看到你回来了"]


def test_a_message_that_went_stale_is_dropped_rather_than_delivered_late():
    """The moment has passed; saying it later is worse than not saying it."""
    agent = vision_agent.VisionAgent()
    now = time.time()
    _agent_with_message(agent, now, "刚刚看到你回来了")
    assert agent.peek_messages(), "刚说的话应该在队列里"
    # Age it past the window.
    with agent._lock:
        agent._pending[0]["at"] = now - vision_agent.QUEUE_MAX_AGE_SECONDS - 1
    assert agent.peek_messages() == []
    assert agent.take_message() is None
    assert agent.next_message() is None


def test_the_queue_is_bounded_so_she_cannot_monologue():
    agent = vision_agent.VisionAgent()
    now = time.time()
    for index in range(vision_agent.QUEUE_MAX_MESSAGES + 4):
        _agent_with_message(agent, now + index * 0.01, f"第 {index} 句话在这里")
    pending = agent.peek_messages()
    assert len(pending) == vision_agent.QUEUE_MAX_MESSAGES
    # The newest survive; the oldest are the ones that lose their moment.
    assert pending[-1]["message"].startswith(f"第 {vision_agent.QUEUE_MAX_MESSAGES + 3} 句")


def test_next_message_can_be_read_without_consuming():
    agent = vision_agent.VisionAgent()
    _agent_with_message(agent, time.time(), "在忙呀")
    first = agent.next_message()
    assert first is not None and first["message"] == "在忙呀"
    # Reading twice must be idempotent, so a polling UI does not eat her words.
    assert agent.next_message() is not None
    assert len(agent.peek_messages()) == 1
    consumed = agent.next_message(consume=True)
    assert consumed is not None
    assert agent.peek_messages() == []


def test_clearing_drops_everything_and_reports_the_count():
    agent = vision_agent.VisionAgent()
    _agent_with_message(agent, time.time(), "第一句")
    _agent_with_message(agent, time.time(), "第二句话")
    assert agent.clear_messages() == 2
    assert agent.peek_messages() == []


def test_silent_mode_never_queues_a_message(monkeypatch):
    agent = vision_agent.VisionAgent()
    agent._mode = "silent"
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []

    async def fake_look():
        return {"status": "success", "faces": 1, "camera_count": 1, "message": "看到你了。",
                "action": {"kind": "typing", "label": "在打键盘或动鼠标"}, "pose_quality": {"usable": True}}

    async def fake_interpret(_reading, _agency):
        return {"summary": "佳在敲键盘", "activity": "工作", "mood": "", "attention": "",
                "notable": True, "say": "说点什么"}

    monkeypatch.setattr(agent, "_look", fake_look)
    monkeypatch.setattr(agent, "_interpret", fake_interpret)
    asyncio.run(agent.tick())

    assert agent.peek_messages() == []
    assert agent.state()["pending_messages"] == 0
    agent._mode = "auto"
    agency._intents = []
    agency._impressions = []


def test_camera_impressions_exposes_the_next_message_without_consuming():
    service = ScreenVisionService()
    agent = vision_agent.get_vision_agent()
    agent.clear_messages()
    _agent_with_message(agent, time.time(), "画面亮起来啦")

    first = json.loads(service._camera_impressions({}))
    assert first["message"]["message"] == "画面亮起来啦"
    assert len(first["pending_messages"]) == 1

    again = json.loads(service._camera_impressions({}))
    assert again["message"]["message"] == "画面亮起来啦", "读两次不该吃掉她的话"

    taken = json.loads(service._camera_impressions({"consume_message": True}))
    assert taken["message"]["message"] == "画面亮起来啦"
    assert taken["pending_messages"] == []
    agent.clear_messages()


# --- the MCP surface -------------------------------------------------------


def test_camera_watch_starts_and_stops_her_loop(monkeypatch):
    service = ScreenVisionService()
    agent = vision_agent.get_vision_agent()

    class _Loop:
        def create_task(self, coro):
            coro.close()
            return None

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: _Loop())

    async def scenario():
        started = json.loads(await service._camera_watch({"action": "start", "interval_seconds": 20}))
        assert started["agent"]["running"] is True
        assert started["agent"]["interval_seconds"] == 20
        stopped = json.loads(await service._camera_watch({"action": "stop"}))
        assert stopped["agent"]["running"] is False

    asyncio.run(scenario())
    assert agent.running is False


def test_camera_intent_tool_round_trip():
    service = ScreenVisionService()
    agency = vision_agent.get_vision_agency()
    agency._intents = []

    added = json.loads(service._camera_intent({"action": "add", "text": "留意佳有没有揉眼睛"}))
    assert added["status"] == "success"
    intent_id = added["intent"]["id"]

    disabled = json.loads(service._camera_intent({"action": "disable", "intent_id": intent_id}))
    assert disabled["intent_count"] == 0

    removed = json.loads(service._camera_intent({"action": "remove", "intent_id": intent_id}))
    assert removed["status"] == "success"

    blank = json.loads(service._camera_intent({"action": "add", "text": "  "}))
    assert blank["status"] == "error"
    agency._intents = []


def test_camera_impressions_tool_exposes_her_memory_without_images():
    service = ScreenVisionService()
    agency = vision_agent.get_vision_agency()
    agency._intents = []
    agency._impressions = []
    agency.record(Impression(at=1.0, summary="佳在敲键盘", activity="工作", mood="专注"))

    payload = json.loads(service._camera_impressions({"limit": 5}))
    assert payload["status"] == "success"
    assert payload["impressions"][0]["summary"] == "佳在敲键盘"
    assert payload["memory_card"].startswith("[弥娅最近对佳的观察印象]")
    assert "image" not in json.dumps(payload, ensure_ascii=False)
    agency._impressions = []


def test_camera_watch_tick_is_available_on_demand(monkeypatch):
    service = ScreenVisionService()
    agent = vision_agent.get_vision_agent()

    async def fake_tick(interpret=True):
        return {"reading": {"faces": True}, "interpreted": False, "impression": {"summary": "看了一眼"}}

    monkeypatch.setattr(agent, "tick", fake_tick)
    payload = json.loads(asyncio.run(service._camera_watch({"action": "tick"})))
    assert payload["status"] == "success"
    assert payload["impression"]["summary"] == "看了一眼"


def test_camera_agency_settings_are_not_boot_only(monkeypatch):
    """Cadence, adaptive pacing and the thumbnail switch belong to the setting.

    Regression: only ``autostart_after_delay`` read them, so starting her
    watching by hand silently fell back to 30 seconds, adaptive on, and the
    privacy switch ignored - the configuration looked like it worked and then
    stopped applying depending on which route started her.
    """
    monkeypatch.setattr(vision_agent, "_agency_config", lambda: {
        "autostart": True,
        "interval_seconds": 90,
        "mode": "silent",
        "adaptive": False,
        "slow_interval_seconds": 300,
        "slow_after_unchanged": 5,
        "thumbnails": True,
    })

    settings = vision_agent.configured_start_kwargs()

    assert settings["interval_seconds"] == 90
    assert settings["mode"] == "silent"
    assert settings["adaptive"] is False
    assert settings["slow_interval"] == 300
    assert settings["slow_after"] == 5
    assert settings["thumbnails"] is True


def test_the_manual_start_path_also_reads_camera_agency():
    """Source-level, because the setting was correct and simply not consulted."""
    root = Path(__file__).resolve().parents[2]
    source = (root / "mcpserver" / "screen_vision" / "service.py").read_text(encoding="utf-8")
    assert "configured_start_kwargs" in source, \
        "手动启动弥娅观察时也必须读取 camera_agency 的节奏与缩略图设置"
