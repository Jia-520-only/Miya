"""
认知缓存区管理器 - 在内存中维护最近的认知记录

用于让弥娅在当前对话中能快速访问刚思考过的内容，
形成连贯的思维链。
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CognitionRecord:
    """单条认知记录"""

    id: str
    timestamp: float
    user_id: str
    thinking: str
    emotions: Dict[str, int]
    inner_thought: str
    attribution: str
    reflection: str
    message_preview: str = ""  # 对应的用户消息预览


class CognitionCache:
    """
    认知缓存区 - 内存中的近期认知记录

    特点：
    - 只保留最近 N 条记录（默认5条）
    - 按用户ID隔离
    - 自动清理过期记录（默认5分钟）
    """

    def __init__(self, max_per_user: int = 5, ttl_seconds: float = 300):
        self.max_per_user = max_per_user
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, deque] = {}
        self._lock: Optional[asyncio.Lock] = None

    async def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def add(self, record: CognitionRecord) -> None:
        """添加认知记录"""
        async with await self._get_lock():
            user_id = record.user_id
            if user_id not in self._cache:
                self._cache[user_id] = deque(maxlen=self.max_per_user)

            self._cache[user_id].append(record)
            logger.info(f"[认知缓存] 新增记录: user={user_id}, thoughts={record.inner_thought[:30]}")

    async def get_recent(self, user_id: str, limit: int = 3) -> List[CognitionRecord]:
        """获取用户最近的认知记录"""
        async with await self._get_lock():
            if user_id not in self._cache:
                return []

            # 获取最近的记录
            records = list(self._cache[user_id])
            return records[-limit:][::-1]  # 最新在前

    async def get_context_for_ai(self, user_id: str, limit: int = 2) -> str:
        """获取适合注入AI的上下文（格式化后的字符串）"""
        records = await self.get_recent(user_id, limit)
        if not records:
            return ""

        parts = ["【近期思维参考】"]
        for i, rec in enumerate(records, 1):
            if rec.inner_thought:
                parts.append(f"{i}. 心里想: {rec.inner_thought[:50]}")
            if rec.thinking and rec.thinking != rec.inner_thought:
                parts.append(f"   思考: {rec.thinking[:80]}")

        return "\n".join(parts)

    async def clear_expired(self) -> None:
        """清理过期记录"""
        now = time.time()
        async with await self._get_lock():
            for user_id in list(self._cache.keys()):
                records = self._cache[user_id]
                # 过滤过期记录
                valid = [r for r in records if now - r.timestamp < self.ttl_seconds]
                if valid:
                    self._cache[user_id] = deque(valid, maxlen=self.max_per_user)
                else:
                    del self._cache[user_id]

    async def clear_user(self, user_id: str) -> None:
        """清除指定用户的缓存"""
        async with await self._get_lock():
            if user_id in self._cache:
                del self._cache[user_id]


# 全局单例
_cognition_cache: Optional[CognitionCache] = None


def get_cognition_cache() -> CognitionCache:
    """获取认知缓存单例"""
    global _cognition_cache
    if _cognition_cache is None:
        _cognition_cache = CognitionCache(max_per_user=5, ttl_seconds=300)
    return _cognition_cache
