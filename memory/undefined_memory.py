"""
Legacy undefined_memory - 已迁移到新版记忆系统 (MiyaMemoryCore V3.1)
兼容旧接口

@deprecated: 新代码请直接使用 memory.MiyaMemory 或 memory 包的便捷函数
              (store_important, search_memory, update_memory, delete_memory 等)
              本模块将在 v9.0 中移除。
"""

import logging
import warnings
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UndefinedMemoryAdapter:
    """Undefined记忆适配器 - 兼容旧接口

    @deprecated: 委托给 MiyaMemoryCore，新代码请直接使用 memory 包便捷函数。
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        """初始化"""
        self._initialized = True

    async def _load(self):
        """加载记忆 - 兼容旧接口"""
        await self.initialize()

    def count(self) -> int:
        """获取记忆数量"""
        return 0  # 适配层，实际数据由 MiyaMemoryCore 管理

    async def add_memory(self, content: str, user_id: str, **kwargs) -> str:
        """添加记忆"""
        from memory import store_important

        return await store_important(content, user_id, tags=kwargs.get("tags", []))

    async def add(self, fact: str = "", content: str = "", tags: list = None, user_id: str = "global", **kwargs) -> str:
        """添加记忆（兼容 auto_extract_memory 调用）"""
        from memory import store_important

        text = fact or content
        uid = kwargs.get("user_id", user_id)
        return await store_important(text, uid, tags=tags or [])

    async def update(self, memory_id: str, content: str, tags: list = None, **kwargs) -> bool:
        """更新记忆"""
        from memory import update_memory

        return await update_memory(memory_id, content=content, tags=tags or [])

    async def delete(self, memory_id: str, **kwargs) -> bool:
        """删除记忆"""
        from memory import delete_memory

        return await delete_memory(memory_id)

    async def search_memory(self, query: str, user_id: Optional[str] = None, **kwargs) -> List[Dict]:
        """搜索记忆"""
        from memory import search_memory

        results = await search_memory(query, user_id=user_id)
        return [
            {
                "id": r.id,
                "content": r.content,
                "tags": r.tags,
                "created_at": r.created_at,
            }
            for r in results
        ]

    async def get_all(self, limit: int = 10) -> List[Dict]:
        """获取所有记忆（兼容方法）"""
        # 使用空查询获取最近的记忆
        results = await self.search_memory(query="", user_id=None)
        return results[:limit]

    async def get_by_tag(self, tag: str, limit: int = 10) -> List[Dict]:
        """按标签获取记忆（兼容方法）"""
        # 使用标签作为查询
        results = await self.search_memory(query=tag, user_id=None)
        return results[:limit]


# 全局单例
_adapter: Optional[UndefinedMemoryAdapter] = None


def get_undefined_memory_adapter() -> UndefinedMemoryAdapter:
    """获取Undefined记忆适配器"""
    global _adapter
    if _adapter is None:
        _adapter = UndefinedMemoryAdapter()
    return _adapter


def get_undefined_memory_backend():
    """获取后端"""
    return get_undefined_memory_adapter()


def get_unified_memory_backend():
    """获取统一记忆后端（新系统兼容别名）"""
    from memory import search_memory

    return get_undefined_memory_adapter()


__all__ = [
    "UndefinedMemoryAdapter",
    "get_undefined_memory_adapter",
    "get_undefined_memory_backend",
    "get_unified_memory_backend",
]
