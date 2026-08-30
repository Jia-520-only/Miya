"""
Anthropic Claude Provider 实现

支持 Claude 模型
"""

import logging
from typing import AsyncIterator, List, Optional

import anthropic

from .bridge import (
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ProviderConfig,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude Provider"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._initialize_client()

    def _initialize_client(self):
        """初始化客户端"""
        try:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
            logger.info(f"[AnthropicProvider] 初始化完成: {self.config.id}")
        except Exception as e:
            logger.error(f"[AnthropicProvider] 初始化失败: {e}")

    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[dict]] = None,
        **kwargs,
    ) -> ChatResponse:
        """发送聊天请求"""
        if not self._client:
            raise RuntimeError("Anthropic client 未初始化")

        # 转换消息格式 (Anthropic 格式)
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                # Anthropic 使用 system 消息格式
                continue
            msg_dict = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            anthropic_messages.append(msg_dict)

        # 提取 system prompt
        system_prompt = None
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                break

        try:
            # 构建请求参数
            request_params = {
                "model": self.config.model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system_prompt:
                request_params["system"] = system_prompt

            # 发送请求
            response = await self._client.messages.create(**request_params)

            # 解析响应
            content = ""
            tool_calls = None
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    if not tool_calls:
                        tool_calls = []
                    tool_calls.append(
                        {
                            "id": block.id,
                            "function": {
                                "name": block.name,
                                "arguments": block.input,
                            },
                        }
                    )

            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

            return ChatResponse(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                model=response.model,
            )
        except Exception as e:
            logger.error(f"[AnthropicProvider] Chat请求失败: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        """流式聊天"""
        if not self._client:
            raise RuntimeError("Anthropic client 未初始化")

        anthropic_messages = []
        system_prompt = None
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            anthropic_messages.append(msg_dict)

        try:
            request_params = {
                "model": self.config.model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if system_prompt:
                request_params["system"] = system_prompt

            async with self._client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield ChatResponse(content=text, model=self.config.model)
        except Exception as e:
            logger.error(f"[AnthropicProvider] 流式请求失败: {e}")
            raise
