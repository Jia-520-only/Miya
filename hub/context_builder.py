"""
统一上下文管道 ContextBuilder

一次读取对话历史，多组件共享分配。
替代原有的 ConversationContextManager / MemoryManager / PromptManager / SoulGenerator 各自独立的上下文截断逻辑。

检索路径:
  1. MemoryNet conversation_history（快速文件缓存）
  2. MiyaMemoryCore（统一 SQLite+JSON 后端，跨平台）

用法:
    builder = ContextBuilder(memory_net)
    allocation = await builder.build(
        session_id="user_1523878699",
        user_id="1523878699",
        current_input="今天的对话内容...",
        consumers=[
            ConsumerRequest("main_prompt", max_messages=20, max_tokens=6000, priority=1),
            ConsumerRequest("soul_analysis", max_messages=24, max_tokens=3000, priority=2),
            ConsumerRequest("cognitive_search", max_messages=30, max_tokens=4000, priority=3),
        ],
    )
    # allocation.slices["main_prompt"] -> List[Dict]
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.token_utils import count_message_tokens

logger = logging.getLogger(__name__)


@dataclass
class ConsumerRequest:
    consumer: str
    max_messages: int = 20
    max_tokens: int = 6000
    priority: int = 5
    per_message_max_chars: int = 0
    include_metadata: bool = True


@dataclass
class ContextSlice:
    consumer: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    token_count: int = 0
    total_available: int = 0


@dataclass
class ContextAllocation:
    slices: Dict[str, ContextSlice] = field(default_factory=dict)
    total_messages: int = 0
    session_id: str = ""

    def get(self, consumer: str) -> List[Dict[str, Any]]:
        s = self.slices.get(consumer)
        return s.messages if s else []


class ContextBuilder:
    def __init__(self, memory_net):
        self._memory_net = memory_net

    async def build(
        self,
        session_id: str,
        user_id: str = "",
        current_input: str = "",
        consumers: Optional[List[ConsumerRequest]] = None,
        needs_recall: bool = False,
        is_deep_discussion: bool = False,
        group_id: str = "",
        platform: str = "unknown",
    ) -> ContextAllocation:
        if not consumers:
            consumers = [
                ConsumerRequest("default", max_messages=20, max_tokens=6000, priority=1),
            ]

        consumers = sorted(consumers, key=lambda c: c.priority)

        max_needed = max(c.max_messages for c in consumers)
        if needs_recall:
            max_needed = max(max_needed, 80)
        elif is_deep_discussion:
            max_needed = max(max_needed, 60)

        raw_messages = await self._load_messages(
            session_id, user_id, max_needed, group_id=group_id, platform=platform,
        )

        if not raw_messages:
            return ContextAllocation(
                slices={c.consumer: ContextSlice(consumer=c.consumer) for c in consumers},
                session_id=session_id,
            )

        allocation = ContextAllocation(
            total_messages=len(raw_messages),
            session_id=session_id,
        )

        for consumer in consumers:
            allocation.slices[consumer.consumer] = self._allocate_slice(
                raw_messages,
                consumer,
            )

        return allocation

    async def _load_messages(
        self, session_id: str, user_id: str = "", limit: int = 50, group_id: str = "", platform: str = "unknown"
    ) -> List[Any]:
        """通过统一上下文装配器合并缓存、会话、用户和群聊历史。"""
        from memory.context_assembler import ContextAssembler
        from memory.context_identity import ContextIdentity

        default_identity = ContextIdentity.resolve(user_id=user_id, group_id=group_id, platform=platform)
        identity = ContextIdentity.resolve(
            user_id=user_id,
            group_id=group_id,
            platform=platform,
            session_id="" if session_id in default_identity.session_ids else session_id,
        )
        messages = await ContextAssembler(self._memory_net).load_dialogue(identity, limit=limit)
        return [
            _MemoryItemWrapper(
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                metadata=message.metadata,
            )
            for message in messages
        ]

    def _allocate_slice(
        self,
        messages: List[Any],
        consumer: ConsumerRequest,
    ) -> ContextSlice:
        start = max(0, len(messages) - consumer.max_messages)
        window = messages[start:]

        result = []
        total_tokens = 0

        for msg in reversed(window):
            content = getattr(msg, "content", "")
            if consumer.per_message_max_chars > 0:
                content = content[: consumer.per_message_max_chars]

            token_count = count_message_tokens(content)

            if consumer.max_tokens > 0 and total_tokens + token_count > consumer.max_tokens:
                break

            entry = {
                "role": getattr(msg, "role", ""),
                "content": content,
                "timestamp": getattr(msg, "timestamp", ""),
            }
            if consumer.include_metadata:
                entry["metadata"] = getattr(msg, "metadata", None) or {}

            result.append(entry)
            total_tokens += token_count

        result.reverse()
        return ContextSlice(
            consumer=consumer.consumer,
            messages=result,
            token_count=total_tokens,
            total_available=len(messages),
        )


class _MemoryItemWrapper:
    """MemoryItem -> conversation message 兼容适配器"""

    def __init__(self, role: str, content: str, timestamp: str, metadata: Dict = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.metadata = metadata or {}
