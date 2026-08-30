#!/usr/bin/env python3
"""
Provider 抽象基类

参考 AstrBot 实现，提供统一的 Provider 接口
支持：多 Key 轮换、代理配置、流式输出、错误恢复、图片预处理等
"""

import abc
import asyncio
import json
import logging
import os
import random
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Literal, Optional

from core.providers.entities import (
    LLMResponse,
    TokenUsage,
)
from core.providers.register import (
    ProviderMeta,
    ProviderType,
)

from config.config_utils import get_api_key

logger = logging.getLogger(__name__)


class Provider(abc.ABC):
    """Provider 抽象基类"""

    # 默认参数签名（由子类覆盖）
    DEFAULT_PARAMS: Dict[str, Any] = {}

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__()
        self.provider_config = provider_config
        self.provider_settings = provider_settings

        # 配置解析
        self.provider_id = provider_config.get("id", "default")
        self.model_name = provider_config.get("model", "")
        self.timeout = provider_config.get("timeout", 120)
        self.proxy = provider_config.get("proxy", "")

        # API Key 管理（支持多 Key）
        self._init_api_keys(provider_config)

        # 错误统计
        self.error_count = 0
        self.success_count = 0
        self.total_response_time = 0.0

        # 推理内容字段名
        self.reasoning_key = "reasoning_content"

    def _init_api_keys(self, provider_config: dict) -> None:
        """初始化 API Keys"""
        keys = provider_config.get("key", [])
        if isinstance(keys, str):
            keys = [keys] if keys else []
        elif not isinstance(keys, list):
            keys = []

        # 解析环境变量
        resolved_keys = []
        for key in keys:
            if isinstance(key, str) and key.startswith("$"):
                env_key = key[1:]
                if env_key.startswith("{") and env_key.endswith("}"):
                    env_key = env_key[1:-1]
                env_val = get_api_key(env_key)
                if env_val:
                    resolved_keys.append(env_val)
                else:
                    logger.warning(f"[Provider] 环境变量 {env_key} 未设置，使用空 Key")
                    resolved_keys.append("")
            else:
                resolved_keys.append(key)

        self.api_keys = resolved_keys or [""]
        self.chosen_api_key = self.api_keys[0] if self.api_keys else ""
        self.available_api_keys = self.api_keys.copy()

        logger.info(f"[Provider] {self.provider_id} 加载了 {len(self.api_keys)} 个 API Keys")

    def set_key(self, key: str) -> None:
        """设置当前 Key"""
        self.chosen_api_key = key

    def get_current_key(self) -> str:
        """获取当前 Key"""
        return self.chosen_api_key

    def get_keys(self) -> List[str]:
        """获取所有 Keys"""
        return self.api_keys.copy()

    def _rotate_key(self) -> Optional[str]:
        """轮换到下一个可用的 Key"""
        if not self.available_api_keys:
            self.available_api_keys = self.api_keys.copy()

        if len(self.available_api_keys) <= 1:
            return self.chosen_api_key

        # 随机选择一个 Key
        self.chosen_api_key = random.choice(self.available_api_keys)
        self.available_api_keys.remove(self.chosen_api_key)

        logger.info(f"[Provider] 轮换 API Key: ...{self.chosen_api_key[-6:]}")
        return self.chosen_api_key

    def _restore_key(self, key: str) -> None:
        """恢复 Key 到可用列表"""
        if key and key in self.available_api_keys:
            self.available_api_keys.append(key)

    def set_model(self, model_name: str) -> None:
        """设置模型名"""
        self.model_name = model_name

    def get_model(self) -> str:
        """获取模型名"""
        return self.model_name

    def meta(self) -> ProviderMeta:
        """获取 Provider 元数据"""
        return ProviderMeta(
            id=self.provider_id,
            model=self.get_model(),
            type=self.provider_config.get("type", ""),
            provider_type=ProviderType.CHAT_COMPLETION.value,
        )

    # ===== 抽象方法 =====

    @abc.abstractmethod
    async def text_chat(
        self,
        prompt: Optional[str] = None,
        contexts: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[Any] = None,
        tool_choice: Literal["auto", "required"] = "auto",
        **kwargs,
    ) -> LLMResponse:
        """文本对话"""
        raise NotImplementedError

    async def text_chat_stream(
        self,
        prompt: Optional[str] = None,
        contexts: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[Any] = None,
        tool_choice: Literal["auto", "required"] = "auto",
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """流式文本对话"""
        raise NotImplementedError()

    async def test(self, timeout: float = 45.0) -> None:
        """测试 Provider 可用性"""
        try:
            await asyncio.wait_for(
                self.text_chat(prompt="REPLY `PONG` ONLY"),
                timeout=timeout,
            )
        except Exception as e:
            raise Exception(f"Provider 测试失败: {e}")

    # ===== 辅助方法 =====

    @staticmethod
    def _normalize_content(content: Any, strip: bool = True) -> str:
        """规范化内容（处理各种格式）"""
        if content is None:
            return ""

        # 字典格式
        if isinstance(content, dict):
            if "text" in content:
                return str(content.get("text", ""))
            return str(content)

        # 列表格式
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            if text_parts:
                return "".join(text_parts)
            return str(content)

        # 字符串格式
        if isinstance(content, str):
            content = content.strip() if strip else content
            # 检查 JSON 编码的列表
            check = content.strip()
            if check.startswith("[") and check.endswith("]") and len(check) < 8192:
                try:
                    parsed = json.loads(check)
                    if isinstance(parsed, list):
                        text_parts = []
                        for part in parsed:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(str(part.get("text", "")))
                        if text_parts:
                            return "".join(text_parts)
                except (json.JSONDecodeError, ValueError):
                    pass
            return content

        return str(content)

    @staticmethod
    def _extract_reasoning_content(completion: Any) -> Optional[str]:
        """提取推理内容"""
        if not hasattr(completion, "choices") or not completion.choices:
            return None

        choice = completion.choices[0]
        message = choice.message if hasattr(choice, "message") else choice

        # 尝试多种字段名
        for key in ["reasoning_content", "reasoning", "thinking"]:
            attr = getattr(message, key, None)
            if attr:
                return str(attr)

        return None

    @staticmethod
    def _extract_usage(usage: Any) -> TokenUsage:
        """提取使用统计"""
        if not usage:
            return TokenUsage()

        def safe_get(attr: str, default: int = 0) -> int:
            val = getattr(usage, attr, default)
            return val if isinstance(val, int) else default

        ptd = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(ptd, "cached_tokens", 0) if ptd else 0
        cached = cached if isinstance(cached, int) else 0

        return TokenUsage(
            input_other=safe_get("prompt_tokens") - cached,
            input_cached=cached,
            output=safe_get("completion_tokens"),
        )

    def pop_record(self, context: List[Dict], count: int = 2) -> None:
        """弹出非系统消息记录"""
        if not context:
            return

        popped = 0
        indices_to_pop = []

        for idx, record in enumerate(context):
            role = record.get("role", "")
            if role == "system":
                continue
            indices_to_pop.append(idx)
            popped += 1
            if popped >= count:
                break

        for idx in reversed(indices_to_pop):
            context.pop(idx)

    def _context_contains_image(self, contexts: List[Dict]) -> bool:
        """检查上下文中是否包含图片"""
        for ctx in contexts:
            content = ctx.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") in ("image_url",):
                    return True
        return False

    def _remove_image_from_context(self, contexts: List[Dict]) -> List[Dict]:
        """从上下文中移除图片"""
        new_contexts = []

        for ctx in contexts:
            if "content" in ctx and isinstance(ctx["content"], list):
                new_content = []
                for item in ctx["content"]:
                    if isinstance(item, dict) and "image_url" in item:
                        continue
                    new_content.append(item)
                if not new_content:
                    new_content = [{"type": "text", "text": "[图片]"}]
                ctx = {**ctx, "content": new_content}
            new_contexts.append(ctx)

        return new_contexts

    async def _handle_api_error(
        self,
        e: Exception,
        payloads: Dict,
        contexts: List[Dict],
        chosen_key: str,
        available_keys: List[str],
        retry_cnt: int,
        max_retries: int,
        tools: Optional[Any] = None,
        image_fallback_used: bool = False,
    ) -> tuple:
        """处理 API 错误并恢复"""
        error_str = str(e)

        # 429 错误 - 轮换 Key
        if "429" in error_str:
            logger.warning("[Provider] API 429 错误，尝试轮换 Key")
            if chosen_key in available_keys:
                available_keys.remove(chosen_key)
            if available_keys:
                chosen_key = random.choice(available_keys)
                return (
                    False,
                    chosen_key,
                    available_keys,
                    payloads,
                    contexts,
                    tools,
                    image_fallback_used,
                )
            raise e

        # 上下文超长
        if "maximum context length" in error_str or "context_length_exceeded" in error_str:
            logger.warning("[Provider] 上下文超长，尝试压缩")
            self.pop_record(contexts)
            payloads["messages"] = contexts
            return (
                False,
                chosen_key,
                available_keys,
                payloads,
                contexts,
                tools,
                image_fallback_used,
            )

        # 模型不支持 VLM
        if "model is not a VLM" in error_str or "not a vision model" in error_str:
            if image_fallback_used or self._context_contains_image(contexts):
                raise e
            logger.warning("[Provider] 模型不支持视觉，降级到文本")
            new_contexts = self._remove_image_from_context(contexts)
            payloads["messages"] = new_contexts
            return (
                False,
                chosen_key,
                available_keys,
                payloads,
                new_contexts,
                tools,
                True,
            )

        # 内容审核拦截
        if "content filter" in error_str or "moderated" in error_str:
            raise Exception("内容被安全过滤拒绝")

        # 函数调用不支持
        if "function calling is not enabled" in error_str or ("function" in error_str and "support" in error_str):
            logger.info("[Provider] 模型不支持函数调用，自动移除工具")
            payloads.pop("tools", None)
            return (
                False,
                chosen_key,
                available_keys,
                payloads,
                contexts,
                None,
                image_fallback_used,
            )

        # 其他错误
        raise e

    def _sanitize_assistant_messages(self, messages: List[Dict]) -> None:
        """清理空的 assistant 消息"""
        if not isinstance(messages, list):
            return

        cleaned = []
        for msg in messages:
            if msg.get("role") != "assistant":
                cleaned.append(msg)
                continue

            content = msg.get("content")
            tool_calls = msg.get("tool_calls")

            # 空消息且无工具调用 - 跳过
            if not content and not tool_calls:
                logger.warning("[Provider] 跳过空 assistant 消息")
                continue

            # 空内容但有工具调用
            if not content and tool_calls:
                msg["content"] = None

            cleaned.append(msg)

        messages.clear()
        messages.extend(cleaned)
