"""
OpenAI Provider 实现

支持 OpenAI API 兼容的所有模型
"""

import logging
from typing import AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from .bridge import (
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ProviderConfig,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI Provider 实现"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[AsyncOpenAI] = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
            logger.info(f"[OpenAIProvider] 初始化完成: {self.config.id}")
        except Exception as e:
            logger.error(f"[OpenAIProvider] 初始化失败: {e}")

    def create_ai_client(self):
        """创建工具调用 AI 客户端（复用 provider 的 HTTP 连接）"""
        from core.ai_client import AIClientFactory

        return AIClientFactory.from_provider(self)

    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> ChatResponse:
        """发送聊天请求"""
        if not self._client:
            raise RuntimeError("OpenAI client 未初始化")

        # 转换消息格式
        openai_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            openai_messages.append(msg_dict)

        try:
            # 构建请求参数
            request_params = {
                "model": self.config.model,
                "messages": openai_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice

            # 发送请求
            response = await self._client.chat.completions.create(**request_params)

            # 解析响应
            content = response.choices[0].message.content or ""
            tool_calls = None
            if response.choices[0].message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response.choices[0].message.tool_calls
                ]

            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return ChatResponse(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                model=response.model,
            )
        except Exception as e:
            logger.error(f"[OpenAIProvider] Chat请求失败: {e}")
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
            raise RuntimeError("OpenAI client 未初始化")

        openai_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            openai_messages.append(msg_dict)

        try:
            stream = await self._client.chat.completions.create(
                model=self.config.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield ChatResponse(
                        content=chunk.choices[0].delta.content,
                        model=chunk.model,
                    )
        except Exception as e:
            logger.error(f"[OpenAIProvider] 流式请求失败: {e}")
            raise

    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入"""
        if not self._client:
            raise RuntimeError("OpenAI client 未初始化")

        try:
            response = await self._client.embeddings.create(
                model=self.config.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"[OpenAIProvider] Embedding请求失败: {e}")
            raise

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入"""
        if not self._client:
            raise RuntimeError("OpenAI client 未初始化")

        try:
            response = await self._client.embeddings.create(
                model=self.config.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"[OpenAIProvider] Batch Embedding请求失败: {e}")
            raise
