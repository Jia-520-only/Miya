#!/usr/bin/env python3
"""
Provider 实体定义

参考 AstrBot 实现，包含 LLMResponse、TokenUsage 等数据结构
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token 使用统计"""

    input_other: int = 0  # 非缓存输入 Token
    input_cached: int = 0  # 缓存输入 Token
    output: int = 0  # 输出 Token

    @property
    def total_input(self) -> int:
        """总输入 Token"""
        return self.input_other + self.input_cached

    @property
    def total(self) -> int:
        """总 Token"""
        return self.total_input + self.output


@dataclass
class ToolCallsResult:
    """工具调用结果"""

    tool_call_id: str
    content: str
    tool_name: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM 响应"""

    role: str = "assistant"
    completion_text: str = ""
    reasoning_content: Optional[str] = None
    tools_call_args: List[Dict] = field(default_factory=list)
    tools_call_name: List[str] = field(default_factory=list)
    tools_call_ids: List[str] = field(default_factory=list)
    tools_call_extra_content: Dict[str, Any] = field(default_factory=dict)
    usage: Optional[TokenUsage] = None
    raw_completion: Any = None
    id: str = ""
    is_chunk: bool = False  # 是否是流式片段

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return bool(self.tools_call_args)

    @property
    def tool_calls(self) -> List[Dict]:
        """获取工具调用列表"""
        if not self.has_tool_calls:
            return []
        result = []
        for i, name in enumerate(self.tools_call_name):
            result.append(
                {
                    "id": self.tools_call_ids[i] if i < len(self.tools_call_ids) else "",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": self.tools_call_args[i] if i < len(self.tools_call_args) else {},
                    },
                }
            )
        return result


@dataclass
class ProviderMeta:
    """Provider 元数据"""

    id: str
    model: str
    type: str
    provider_type: str


@dataclass
class RerankResult:
    """Rerank 结果"""

    index: int
    score: float
    text: str = ""


# ===== 便捷函数 =====


def usage_from_dict(data: Dict) -> TokenUsage:
    """从字典创建 TokenUsage"""
    return TokenUsage(
        input_other=data.get("prompt_tokens", 0) or data.get("input_other", 0),
        input_cached=data.get("cached_tokens", 0),
        output=data.get("completion_tokens", 0) or data.get("output", 0),
    )


def llm_response_from_text(text: str) -> LLMResponse:
    """从文本创建简单的 LLMResponse"""
    return LLMResponse(
        role="assistant",
        completion_text=text,
    )
