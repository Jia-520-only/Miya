"""Regression tests for cloud-draft/local-final response routing."""

import pytest

from core.ai_client import AIMessage, OpenAIClient


def test_clean_cloud_draft_does_not_skip_local_rewrite_by_default(monkeypatch):
    monkeypatch.delenv("MIYA_LOCAL_LLM_REWRITE_SKIP_CLEAN", raising=False)

    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")

    assert client._skip_clean_draft_enabled() is False


def test_clean_cloud_draft_shortcut_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("MIYA_LOCAL_LLM_REWRITE_SKIP_CLEAN", "true")

    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")

    assert client._skip_clean_draft_enabled() is True


@pytest.mark.asyncio
async def test_streaming_system_prompt_forwards_local_reply(monkeypatch):
    client = OpenAIClient(api_key="test", model="cloud-model", base_url="https://api.example.test/v1")
    seen = {}

    async def fake_chat_stream(messages, tools=None, **kwargs):
        seen["local_reply"] = kwargs.get("local_reply")
        yield {"type": "done", "data": "reply"}

    monkeypatch.setattr(client, "chat_stream", fake_chat_stream)

    chunks = [
        chunk
        async for chunk in client.chat_with_system_prompt_stream(
            system_prompt="persona",
            user_message="hello",
            local_reply=True,
        )
    ]

    assert seen["local_reply"] is True
    assert chunks[-1]["data"] == "reply"


@pytest.mark.asyncio
async def test_local_tool_requests_run_on_cloud_with_original_context(monkeypatch):
    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")
    monkeypatch.setattr(client, "_local_endpoint_ready", lambda: False)
    context = {"user_id": "user-1", "group_id": "group-1"}
    client.tool_context = context
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    seen = {}

    class CloudClient:
        tool_context = None

        async def chat(self, messages, **kwargs):
            seen.update(kwargs)
            seen["context"] = self.tool_context
            return "cloud result"

    cloud = CloudClient()
    monkeypatch.setattr(client, "_get_cloud_fallback_client", lambda: cloud)

    result = await client.chat(
        [AIMessage(role="system", content="persona"), AIMessage(role="user", content="do it")],
        tools=tools,
        local_reply=True,
    )

    assert result == "cloud result"
    assert seen["tools"] is tools
    assert seen["context"] is context


@pytest.mark.asyncio
async def test_local_streaming_tool_requests_are_delegated_to_cloud(monkeypatch):
    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")
    monkeypatch.setattr(client, "_local_endpoint_ready", lambda: False)
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    seen = {}

    class CloudClient:
        tool_context = None

        async def chat_stream(self, messages, **kwargs):
            seen.update(kwargs)
            yield {"type": "done", "data": "cloud result"}

    monkeypatch.setattr(client, "_get_cloud_fallback_client", lambda: CloudClient())

    chunks = [
        chunk
        async for chunk in client.chat_stream(
            [AIMessage(role="system", content="persona"), AIMessage(role="user", content="do it")],
            tools=tools,
        )
    ]

    assert seen["tools"] is tools
    assert chunks[-1]["data"] == "cloud result"


def test_local_context_keeps_memory_and_current_request(monkeypatch):
    monkeypatch.setenv("MIYA_LOCAL_LLM_CONTEXT_CHARS", "6000")
    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")
    messages = [
        AIMessage(role="system", content="cloud system prompt"),
        AIMessage(
            role="user",
            content="【相关记忆】用户喜欢青色。\n【最近对话】刚才讨论了晚饭。\n【当前消息】请接着刚才的话题回答。",
        ),
        AIMessage(role="assistant", content="上一轮的简短回复。"),
        AIMessage(role="user", content="当前请求：继续刚才的话题。"),
    ]

    prepared = client._prepare_local_context(messages)

    assert all(message.content != "cloud system prompt" for message in prepared)
    assert any("用户喜欢青色" in message.content for message in prepared)
    assert prepared[-1].content == "当前请求：继续刚才的话题。"
    assert [message.role for message in prepared] == ["user", "assistant", "user"]


def test_local_rewrite_includes_compact_conversation_memory(monkeypatch):
    monkeypatch.setenv("MIYA_LOCAL_LLM_CONTEXT_CHARS", "6000")
    client = OpenAIClient(api_key="test", model="local-model", base_url="http://127.0.0.1:8080/v1")
    monkeypatch.setattr(client, "_load_rewrite_prompt", lambda: "rewrite instructions")
    messages = [
        AIMessage(role="system", content="cloud system prompt"),
        AIMessage(role="user", content="【云端记忆】用户住在杭州。\n当前问题：那里天气如何？"),
        AIMessage(role="assistant", content="你是问杭州吗？"),
        AIMessage(role="user", content="对，明天呢？"),
    ]

    rewritten = client._apply_local_rewrite(messages, "杭州明天有雨。")

    assert "杭州明天有雨" in rewritten[0].content
    assert "云端记忆" in rewritten[1].content
    assert rewritten[-1].content == "对，明天呢？"
