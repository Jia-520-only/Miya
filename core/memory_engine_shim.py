"""
旧 MemoryEngine 兼容层 — 将 tide_memory/dream_memory 等旧 API
委托给新的 MiyaMemoryCore V3.1 统一记忆系统。

所有旧代码中的 MemoryEngine 实例可替换为 MemoryEngineShim 实例，
tool_context 中的 memory_engine 访问不受影响。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger("miya.memory_compat")


class MemoryEngineShim:
    """
    兼容旧 MemoryEngine API 的适配器，底层使用 MiyaMemoryCore。

    旧代码通过 context.memory_engine.tide_memory[key] 直接访问 ——
    这些属性现在委托给 MiyaMemoryCore 的标准 API。
    """

    def __init__(self, memory_core=None):
        self._core = memory_core
        self._tide: dict[str, Any] = {}
        self._dream: dict[str, Any] = {}
        self._metadata: dict[str, dict] = defaultdict(dict)
        self._stats: dict = {"total_tides": 0, "total_dreams": 0, "last_compression": time.time()}
        self._initialized = False

    async def initialize(self) -> None:
        """从 MiyaMemoryCore 加载已有数据"""
        if self._initialized:
            return
        try:
            core = await self._get_core()
            if core:
                recent = await core.get_recent(limit=200)
                for item in recent:
                    mid = getattr(item, "memory_id", str(id(item)))
                    content = getattr(item, "content", "")
                    tags = list(getattr(item, "tags", []) or [])
                    self._tide[mid] = {
                        "content": content,
                        "tags": tags,
                        "created_at": getattr(item, "created_at", ""),
                    }
            self._initialized = True
            logger.info("MemoryEngineShim initialized from MiyaMemoryCore")
        except Exception as e:
            logger.warning(f"MemoryEngineShim init failed: {e}")
            self._initialized = True

    async def _get_core(self):
        if self._core is not None:
            return self._core
        try:
            from memory import get_memory_core

            self._core = await get_memory_core()
            return self._core
        except Exception:
            return None

    # ── 旧 API: 属性访问 ──

    @property
    def tide_memory(self) -> dict[str, Any]:
        return self._tide

    @property
    def dream_memory(self) -> dict[str, Any]:
        return self._dream

    @property
    def memory_metadata(self) -> dict[str, dict]:
        return self._metadata

    # ── 旧 API: 方法 ──

    def get_memory_stats(self) -> dict:
        self._stats.update(
            {
                "total_tides": len(self._tide),
                "total_dreams": len(self._dream),
            }
        )
        return self._stats

    def store_tide(
        self, memory_id: str, content: str, priority: float = 0.5, ttl: float | None = None, **kwargs
    ) -> None:
        self._tide[memory_id] = {
            "content": content,
            "priority": priority,
            "ttl": ttl,
            "created_at": time.time(),
            **kwargs,
        }

    def store_dream(self, memory_id: str, content: str, **kwargs) -> None:
        self._dream[memory_id] = {
            "content": content,
            "created_at": time.time(),
            **kwargs,
        }

    def store(self, memory_id: str, content: str, **kwargs) -> None:
        self.store_tide(memory_id, content, **kwargs)

    def search_tides(self, query: str, limit: int = 5) -> list[dict]:
        query_lower = query.lower()
        results = []
        for mid, data in self._tide.items():
            if query_lower in str(data.get("content", "")).lower():
                results.append({"memory_id": mid, **data})
        return results[:limit]

    def compress_to_dream(self, memory_id: str) -> None:
        data = self._tide.pop(memory_id, None)
        if data:
            self._dream[memory_id] = {**data, "compressed_at": time.time()}

    async def get_context(self, query: str = "", limit: int = 10) -> list[dict]:
        return self.search_tides(query, limit)

    async def add_conversation(self, role: str, content: str, **kwargs) -> None:
        mid = f"conv_{int(time.time() * 1000)}_{hash(content) & 0xFFFF}"
        self.store_tide(mid, content, role=role, **kwargs)

    @property
    def scheduler(self):
        return self

    def __contains__(self, key: str) -> bool:
        return key in self._tide or key in self._dream
