"""Her camera reading must actually reach the model that answers Jia.

This is a regression test for a specific failure. The camera loop ran, the
presence and activity trackers filled up, and Miya produced readings of Jia's
face - yet asked "did you see me in the camera", she answered that the camera was
not connected to her. Every piece worked; nothing joined them to her reply.

An earlier round of this bug was the opposite: the cards existed, but only the
proactive-chat path consumed them, so the reply path stayed blind. These tests
pin the join in both directions.
"""

from __future__ import annotations

import time

import pytest

from mcpserver.screen_vision import vision_context
from mcpserver.screen_vision.vision_stream import ObservationEvent, get_vision_stream


@pytest.fixture(autouse=True)
def _clean_stream():
    """Reset every global tracker, not just the stream.

    These are process-wide singletons, so state left by another test made "no
    observation yet" look like an active reading. The suite passing alone but
    failing together was exactly this.
    """
    from mcpserver.screen_vision.activity import get_activity_tracker
    from mcpserver.screen_vision.presence import get_presence_tracker

    def clear_all() -> None:
        from core.vision_context import get_vision_context

        get_vision_context().clear()
        get_vision_stream().clear()
        get_presence_tracker().reset()
        get_activity_tracker().reset()

    clear_all()
    yield
    clear_all()


def _record_observation(**kwargs) -> None:
    payload = {
        "id": "",
        "at": time.time(),
        "cameras_used": [0],
        "reading": {"faces": True, "action": {"kind": "still", "label": "安静待着"}},
        "reading_text": "看到你在画面里，嘴是张着的，头向左歪着。",
        "expression_text": "嘴是张着的，头向左歪着",
        "interpreted": True,
        "interpreter": "deepseek-v4-flash",
        "summary": "佳还坐在电脑前，歪着头张着嘴，还是困得发懵的样子。",
        "activity": "在电脑前犯困发呆",
        "mood": "困倦迷糊",
        "attention": "在电脑前",
        "intent_texts": ["想留意佳在不在电脑前"],
    }
    payload.update(kwargs)
    get_vision_stream().record(ObservationEvent(**payload))


# --- the card carries what she sees ----------------------------------------


def test_no_observation_at_all_produces_no_card():
    """A machine with no camera must not get a phantom "you cannot see" note."""
    assert vision_context.vision_context_card() == ""


def test_browser_observation_is_shared_without_claiming_the_camera_is_blind():
    from core.vision_context import get_vision_context

    moment = time.time()
    get_vision_context().add({"source": "camera", "summary": "浏览器看到人在敲键盘", "timestamp": moment})
    card = vision_context.vision_context_card(now=moment)
    assert "浏览器看到人在敲键盘" in card
    assert "现在看不到" not in card
    assert "浏览器看到人在敲键盘" not in vision_context.vision_context_card(now=moment + 181)


def test_the_card_carries_her_reading_face_and_intents():
    _record_observation()
    card = vision_context.vision_context_card()
    assert "摄像头" in card
    assert "困得发懵" in card, "她的判断必须进上下文"
    assert "嘴是张着的" in card, "量到的表情必须进上下文"
    assert "在不在电脑前" in card, "她自己在留意什么也要在里面"


def test_the_card_never_contains_image_data():
    """The long-standing promise: derived text only, never a frame."""
    stream = get_vision_stream()
    stream.set_thumbnails_enabled(True)
    stream.record(ObservationEvent(
        id="", at=time.time(), interpreted=True, summary="看到她",
        thumbnails=[{"index": 0, "data_url": "data:image/jpeg;base64,AAAA"}],
    ))
    card = vision_context.vision_context_card()
    assert "data:image" not in card
    assert "base64" not in card
    stream.set_thumbnails_enabled(False)


def test_an_uninterpreted_observation_says_so_rather_than_pretending():
    """Local-only cues must not be presented as a finished reading."""
    _record_observation(interpreted=False, degraded_reason="视觉模型暂时不可用",
                        summary="", expression_text="")
    card = vision_context.vision_context_card()
    assert "没有成功解读" in card
    assert "视觉模型暂时不可用" in card


def test_a_stale_observation_is_flagged_as_not_current():
    """Otherwise she would describe a moment from twenty minutes ago as now."""
    _record_observation()
    get_vision_stream()._events[-1].at = time.time() - 1200
    card = vision_context.vision_context_card()
    assert "没在看他" in card, "过期时必须提醒不要当成现在的情形"


def test_a_blank_frame_is_reported_as_blindness_not_as_absence_of_jia():
    """A black frame means the camera failed, not that Jia left."""
    _record_observation(interpreted=False, degraded_reason="有一路摄像头全黑，这次没有解读",
                        blank_frame=True)
    card = vision_context.vision_context_card()
    assert "全黑" in card
    assert "不是佳不在了" in card, "必须明确区分'看不到'和'不在'"


# --- human age, without a "0 hours ago" ------------------------------------


@pytest.mark.parametrize("seconds,expected", [
    (5, "刚刚"),
    (89, "刚刚"),
    (900, "15 分钟前"),
    (3600, "1 小时前"),
    (7200, "2 小时前"),
    (90000, "1 天前"),
])
def test_human_age_never_says_zero(seconds: float, expected: str):
    assert vision_context._human_age(seconds) == expected


# --- the join into her reply prompt ----------------------------------------


def test_the_card_reaches_the_reply_prompt():
    """The actual regression: this text must land in the prompt she reads."""
    from core.prompt_manager import PromptManager

    _record_observation()
    card = vision_context.vision_context_card()
    assert card

    info = PromptManager().build_full_prompt(
        user_input="弥娅，你在摄像头里看到我了嘛",
        additional_context={"vision_context": card, "platform": "weixin_ilink"},
    )
    combined = str(info.get("user") or "") + str(info.get("system") or "")
    assert "摄像头所见" in combined, "摄像头上下文没有进入她读到的 prompt"
    assert "困得发懵" in combined, "她的判断没有进入她读到的 prompt"


def test_the_reply_path_actually_supplies_the_card():
    """Guards the wiring itself, not just the card: the reply path must call us."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "hub" / "decision_hub.py").read_text(encoding="utf-8")
    assert "vision_context_card" in source, "回复路径不再读取摄像头上下文"
    assert '"vision_context": vision_context' in source, "摄像头上下文没有传给 prompt 构建器"


def test_the_prompt_builder_keeps_camera_and_screen_separate():
    """Different senses: merging them made her conflate the monitor with Jia."""
    from core.prompt_manager import PromptManager

    info = PromptManager().build_full_prompt(
        user_input="test",
        additional_context={
            "screen_context": "窗口是 MIYA v4.1.11",
            "vision_context": "[弥娅的摄像头所见]\n- 在场：佳坐在电脑前",
            "platform": "weixin_ilink",
        },
    )
    combined = str(info.get("user") or "") + str(info.get("system") or "")
    assert "弥娅看向屏幕" in combined
    assert "摄像头所见" in combined
    # The camera block must not be swallowed by the screen heading.
    assert "弥娅看向屏幕] " + "[弥娅的摄像头所见]" not in combined
