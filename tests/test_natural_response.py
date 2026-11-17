"""Regression coverage for natural-language response cleanup and prompt targets."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.prompt_manager import PromptManager
from core.ai_client import OpenAIClient
from hub.decision_hub_helpers import _build_integrated_status, _format_reply_context
from hub.response_generator import ResponseGenerator


def test_prompt_manager_appends_configured_conversation_contract():
    prompt = PromptManager().build_full_prompt(
        user_input="我回来啦",
        additional_context={"platform": "qq", "sender_name": "佳"},
    )

    system = prompt["system"]
    assert "【当前消息】" in prompt["user"]
    assert "【日常表达】" in system
    assert "不把问句当作每轮结尾" in system
    assert "不抠字眼" in system
    assert "情绪、偏好、边界、关系感受和明确承诺" in system
    assert system.rstrip().endswith("被问身份或能力时如实回答。")


def test_response_normalization_removes_transport_residue_only():
    assert ResponseGenerator._normalize_user_response("弥娅：嗯，我在呢。") == "嗯，我在呢。"
    assert ResponseGenerator._normalize_user_response("Miya: 好。\n\n[常态|casual]") == "好。"
    assert ResponseGenerator._normalize_user_response("请看 [重点]") == "请看 [重点]"


@pytest.mark.asyncio
async def test_no_model_fallback_uses_configured_intro_and_identity():
    generator = ResponseGenerator(
        personality=SimpleNamespace(get_profile=lambda: {"vectors": {}}),
        identity=SimpleNamespace(name="测试弥娅"),
    )

    response = await generator.generate_response("你是谁", "telegram", {})

    assert "测试弥娅" in response
    assert "{name}" not in response


def test_integrated_status_preserves_subjective_state_and_tentative_attribution():
    feelings = "我还有些委屈，但愿意听佳解释；我不想答应这件事。"
    status = _build_integrated_status(
        "策略提示",
        feelings + "\n- 可能的互动方向（不确定）: 他可能只是分享",
        "question_back",
        "normal",
        "share",
    )

    assert "当前消息优先" in status
    assert feelings in status
    assert "对方意图只是暂时猜测，不是事实" in status
    assert "回复要与之保持一致" in status
    assert "问句不是默认要求" in status


def test_quoted_message_is_additional_context_only():
    context = _format_reply_context(
        {"sender_name": "旧消息的人", "content": "之前的话", "image_url": "https://example.invalid/a"}
    )

    assert "旧消息的人" in context
    assert "之前的话" in context
    assert "https://example.invalid/a" in context


def test_local_rewrite_instructions_discourage_overthinking(monkeypatch):
    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")
    monkeypatch.setattr(client, "_load_rewrite_prompt", lambda: "rewrite instructions")

    rewritten = client._apply_local_rewrite([], "嗯，先歇会儿。")
    instruction = rewritten[0].content

    assert "不审问动机" in instruction
    assert "不自动追加问题" in instruction
    assert "保留草稿里的情绪、偏好、边界和立场" in instruction
    assert "不把拒绝改成答应" in instruction


@pytest.mark.asyncio
async def test_soul_appraisal_receives_correction_and_keeps_feelings_in_reply_context():
    from core.soul_generator import SoulGenerator
    from hub.decision_hub_helpers import _get_emotion_guidance

    subjective_state = {
        "emotions": [{"name": "失落", "intensity": 50}],
        "inner_thought": "知道是误会了，但我还需要缓缓。",
        "attribution": "佳说刚才是在忙，我接受这个解释。",
        "reflection": "我仍然在意佳，也想把这份失落说清楚。",
    }
    client = AsyncMock()
    client.chat.return_value = json.dumps(subjective_state, ensure_ascii=False)
    soul = object.__new__(SoulGenerator)
    soul._last_emotion = "失落"
    correction = "我刚才是在忙，没有故意不理你。"
    appraisal = await soul._ai_analyze_emotion(
        correction, [{"role": "assistant", "content": "我有些失落。"}], client,
    )

    model_input = client.chat.call_args.kwargs["messages"][0].content
    assert correction in model_input
    assert "及时更新判断" in model_input
    assert "后续回复应自然承接这些感受与立场" in model_input
    assert appraisal == subjective_state

    guidance = _get_emotion_guidance()
    emotion_context = (
        guidance["inner_thought"].format(inner_thought=appraisal["inner_thought"])
        + guidance["attribution"].format(attribution=appraisal["attribution"])
        + guidance["reflection"].format(reflection=appraisal["reflection"])
        + guidance["footer"]
    )
    status = _build_integrated_status("", emotion_context, "", "normal", "chat")
    for field in ("inner_thought", "reflection", "attribution"):
        assert appraisal[field] in status
    assert "回复要与之保持一致" in status
    assert "用户情绪" not in guidance["user_emotion"]
