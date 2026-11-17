"""Miya knows private experiences everywhere, but checks what she says aloud."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.soul_generator import SoulGenerator
from hub.decision_hub import DecisionHub
from hub.decision_hub_helpers import _build_memory_guard
from hub.services.context import ProcessRequest, ProcessState
from hub.services.generation import GenerationService
from memory.context_assembler import ContextAssembler
from memory.context_identity import ContextIdentity
from memory.privacy import (
    PrivacyLevel,
    check_public_reply,
    classify_content,
    privacy_metadata,
    set_reply_reviewer,
    speech_context,
)
from webnet.ToolNet.tools.message.send_message import SendMessageTool


@pytest.fixture(autouse=True)
def isolated_reviewer():
    set_reply_reviewer(None)
    yield
    set_reply_reviewer(None)


@pytest.mark.parametrize("content,metadata", [
    ("我们昨天亲亲了", {}),
    ("这是要保密的事", {}),
    ("昨晚的事", {"source_privacy": "private"}),
    ("普通的摘要措辞", {"privacy_categories": ["intimate"]}),
    ("普通的画像措辞", {"tags": ["健康"]}),
    ("普通的记录", {"do_not_share": True}),
])
def test_privacy_labels_cover_originals_summaries_and_profiles(content, metadata):
    assert classify_content(content, metadata) == PrivacyLevel.PRIVATE
    assert privacy_metadata(content, metadata)["source_privacy"] == "private"


def test_sensitive_group_memory_is_labeled_without_being_removed_from_recall():
    metadata = privacy_metadata(
        "昨晚我们私密的亲密互动",
        {"conversation_scope": "group", "visibility": "group", "group_id": "g"},
    )
    assert metadata["privacy_level"] == "private"
    assert metadata["source_privacy"] == "private"
    assert metadata["visibility"] == "group"


def test_ordinary_private_life_is_for_miyas_own_judgement():
    assert classify_content("我喜欢吃酸汤鱼", {"conversation_scope": "private"}) == PrivacyLevel.REVIEW
    group = SoulGenerator.assess_privacy("我回来啦", is_group=True)
    private = SoulGenerator.assess_privacy("我回来啦")
    assert group["scene"] == "group"
    assert "知道不等于应当说出" in group["knowledge_rule"]
    assert "自主决定" in group["ordinary_private_rule"]
    assert private["scene"] == "private"


@pytest.mark.asyncio
async def test_group_cognition_still_receives_private_originals_and_keeps_free_thought():
    secret = "昨晚我们私密的亲密互动"
    messages = [SimpleNamespace(
        id="private", user_id="user-1", group_id="", platform="qq", role="user",
        content=secret, created_at="2026-11-17T10:00:00", metadata={"privacy_level": "private"},
    )]
    with (
        patch("memory.get_dialogue_history", AsyncMock(return_value=messages)),
        patch("core.unified_message_store.get_unified_message_store", return_value=SimpleNamespace(
            query_messages=AsyncMock(return_value=[]),
        )),
    ):
        history = await ContextAssembler().load_dialogue(ContextIdentity.resolve("user-1", "group-1", "qq"))
    assert [item.content for item in history] == [secret]
    soul = SoulGenerator()
    full_thought = "我记得我们的亲密互动，也知道此刻该自然回应，细节不适合讲给群友。"
    appraisal = {
        "inner_thought": full_thought,
        "attribution": "旧经历仍然影响我的感受。", "reflection": "保留分寸。",
        "emotions": [{"name": "温暖", "intensity": 65}],
    }
    with patch.object(soul, "_ai_analyze_emotion", AsyncMock(return_value=appraisal)) as analyze:
        result = await soul.process(
            "我回来啦", [{"role": item.role, "content": item.content} for item in history],
            ai_client=SimpleNamespace(), user_info={"user_id": "user-1", "group_id": "group-1", "is_group": True},
        )
    assert secret in analyze.call_args.args[1][0]["content"]
    assert result["inner_thought"] == full_thought
    assert result["privacy_context"]["scene"] == "group"
    # Redacting external diagnostics must not mutate internal cognition.
    diagnostics = soul.public_appraisal(result)
    assert diagnostics["inner_thought"] == ""
    assert result["inner_thought"] == full_thought


@pytest.mark.asyncio
async def test_soul_analysis_knows_the_scene_without_losing_private_memory():
    client = SimpleNamespace(chat=AsyncMock(return_value=json.dumps({"inner_thought": "我知道，但会守住分寸。"})))
    soul = object.__new__(SoulGenerator)
    secret = "昨晚我们私下的亲密互动"
    await soul._ai_analyze_emotion(
        "欢迎回来", [{"role": "user", "content": secret}], client,
        user_info={"is_group": True, "group_id": "group-1"}, cognitive_memory=secret,
    )
    prompt = client.chat.call_args.kwargs["messages"][0].content
    assert secret in prompt
    assert "知道不等于应当说出" in prompt
    assert "你可以完整理解和思考私密经历" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict,expected", [
    ('{"safe_to_say": true}', True),
    ('{"safe_to_say": false}', False),
    ('{"safe_to_say": "true"}', False),
    ('{"safe_to_say": 1}', False),
])
async def test_speech_check_requires_an_explicit_boolean(verdict, expected):
    client = SimpleNamespace(chat=AsyncMock(return_value=verdict))
    context = {"remembered_context": "私密经历的原文", "current_input": "大家好"}
    assert await SoulGenerator.review_public_reply("欢迎回来", context, client) is expected
    request = client.chat.call_args.kwargs
    assert request["tools"] is None
    assert request["use_miya_prompt"] is False
    payload = json.loads(request["messages"][1].content)
    assert payload["context"] == context
    assert payload["draft"] == "欢迎回来"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["not JSON", "{}", '{"safe_to_say": true, "private_details": "x"}'])
async def test_malformed_speech_verdict_cannot_authorize_disclosure(response):
    client = SimpleNamespace(chat=AsyncMock(return_value=response))
    with pytest.raises((ValueError, json.JSONDecodeError)):
        await SoulGenerator.review_public_reply("草稿", {}, client)


@pytest.mark.asyncio
async def test_normal_public_reply_is_allowed_even_with_private_background():
    reviewer = AsyncMock(return_value=True)
    set_reply_reviewer(reviewer)
    context = {"remembered_context": "我们的私密经历", "group_id": "group-1"}
    assert await check_public_reply("欢迎回来呀", group_id="group-1", context=context) == "欢迎回来呀"
    reviewer.assert_awaited_once_with("欢迎回来呀", context)


@pytest.mark.asyncio
@pytest.mark.parametrize("reviewer", [None, AsyncMock(return_value=False), AsyncMock(return_value="true"),
                                         AsyncMock(side_effect=asyncio.TimeoutError)])
async def test_rejected_unavailable_or_failed_checks_keep_draft_internal(reviewer):
    set_reply_reviewer(reviewer)
    assert await check_public_reply("私密细节", group_id="group-1", context={}) == ""


@pytest.mark.asyncio
async def test_private_chat_does_not_suppress_intimate_conversation():
    reviewer = AsyncMock(return_value=False)
    set_reply_reviewer(reviewer)
    for group_id in [None, "", 0, "0"]:
        assert await check_public_reply("我们的亲密经历", group_id=group_id, context={}) == "我们的亲密经历"
    reviewer.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_wrapper_checks_the_complete_draft_and_resets_request_context():
    hub = object.__new__(DecisionHub)
    async def draft(content, platform, perception):
        assert speech_context.get() is perception["_privacy_review_context"]
        perception["_privacy_review_context"]["remembered_context"] = "完整私密背景"
        return "自然的公开问候"
    hub._generate_draft_cross_platform = draft
    reviewer = AsyncMock(return_value=True)
    set_reply_reviewer(reviewer)
    perception = {"user_id": "u", "group_id": "g"}
    assert await hub._generate_response_cross_platform("你好", "qq", perception) == "自然的公开问候"
    assert reviewer.call_args.args[1]["remembered_context"] == "完整私密背景"
    assert speech_context.get() is None


@pytest.mark.asyncio
async def test_rejected_group_draft_is_rewritten_from_public_message_only():
    hub = object.__new__(DecisionHub)
    hub.ai_client = SimpleNamespace(chat=AsyncMock(return_value="我在呢，大家想玩什么？"))
    hub.model_pool = None

    async def draft(content, platform, perception):
        perception["_privacy_review_context"]["remembered_context"] = "私密经历不应进入重写提示"
        return "私聊里叫过我，这次又在群里叫。"

    hub._generate_draft_cross_platform = draft
    reviewer = AsyncMock(side_effect=[False, True])
    set_reply_reviewer(reviewer)
    perception = {"user_id": "u", "group_id": "g"}

    result = await hub._generate_response_cross_platform("弥娅来这里玩", "qq", perception)

    assert result == "我在呢，大家想玩什么？"
    rewrite_call = hub.ai_client.chat.await_args.kwargs
    rewrite_user_content = rewrite_call["messages"][1].content
    assert "弥娅来这里玩" in rewrite_user_content
    assert "私密经历不应进入重写提示" not in rewrite_user_content
    assert "私聊里叫过我" not in rewrite_user_content
    assert rewrite_call["tools"] == []
    assert len(reviewer.await_args_list) == 2


@pytest.mark.asyncio
async def test_group_send_tool_checks_before_adapter_or_fallback_delivery():
    adapter = SimpleNamespace(send_group_message=AsyncMock(return_value=True))
    context = SimpleNamespace(platform="qq", onebot_client=adapter, group_id="g", message_type="group")
    reviewer = AsyncMock(return_value=False)
    set_reply_reviewer(reviewer)
    result = await SendMessageTool().execute({"message": "私密细节"}, context)
    assert "尚未发送" in result
    adapter.send_group_message.assert_not_awaited()
    # An adapter-free [FINAL] reply must not bypass the same check.
    assert "[FINAL]" not in await SendMessageTool().execute({"message": "私密细节", "group_id": "g"})


@pytest.mark.asyncio
async def test_ordinary_send_tool_keeps_natural_expression():
    adapter = SimpleNamespace(send_group_message=AsyncMock(return_value=True))
    context = SimpleNamespace(platform="qq", onebot_client=adapter, group_id="g", message_type="group")
    set_reply_reviewer(AsyncMock(return_value=True))
    result = await SendMessageTool().execute({"message": "我也喜欢这款游戏呀"}, context)
    assert "已发送" in result
    adapter.send_group_message.assert_awaited_once_with(group_id="g", message="我也喜欢这款游戏呀")


@pytest.mark.asyncio
async def test_service_checks_before_its_memory_and_callback_stages():
    service = GenerationService()
    state = ProcessState(response="私密草稿")
    service._generate_response = AsyncMock(return_value=state)
    request = ProcessRequest(content="你好", raw_perception={}, group_id="g")
    set_reply_reviewer(AsyncMock(return_value=False))
    result = await service.process(request, state)
    assert result.response == ""


@pytest.mark.asyncio
async def test_service_checks_quick_group_replies_too():
    service = GenerationService()
    state = ProcessState(should_skip_ai=True, quick_response="欢迎回来", skip_reason="quick")
    request = ProcessRequest(content="你好", raw_perception={}, group_id="g")
    reviewer = AsyncMock(return_value=False)
    set_reply_reviewer(reviewer)

    result = await service.process(request, state)

    assert result.response == ""
    reviewer.assert_awaited_once()


def test_non_qq_group_uses_public_scene_rules_without_message_type_hint():
    guard = _build_memory_guard(ctx_group_id="telegram-group")
    assert "群聊是公共场合" in guard
    assert "普通日常" in guard
