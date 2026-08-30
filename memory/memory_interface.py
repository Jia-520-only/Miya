"""
记忆系统统一接口

定义记忆系统的统一接口标准，支持第一阶段统一：
- 统一的记忆查询接口
- 统一的记忆添加接口
- 统一的记忆删除接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"       # 短期记忆
    COGNITIVE = "cognitive"         # 认知记忆
    EPISODIC = "episodic"           # 情景记忆
    SEMANTIC = "semantic"           # 语义记忆
    PINNED = "pinned"               # 置顶备忘
    EMOTIONAL = "emotional"         # 情感记忆


@dataclass
class MemoryItem:
    """记忆项"""
    content: str                    # 记忆内容
    memory_type: MemoryType         # 记忆类型
    timestamp: float               # 时间戳
    importance: float = 0.5         # 重要性（0-1）
    user_id: str = ""              # 用户ID
    group_id: str = ""             # 群组ID
    tags: List[str] = None         # 标签
    metadata: Dict[str, Any] = None  # 元数据
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class BaseMemoryInterface(ABC):
    """记忆系统基础接口"""
    
    @abstractmethod
    async def add_memory(self, memory: MemoryItem) -> str:
        """
        添加记忆
        
        Args:
            memory: 记忆项
        
        Returns:
            记忆ID
        """
        pass
    
    @abstractmethod
    async def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """
        获取记忆
        
        Args:
            memory_id: 记忆ID
        
        Returns:
            记忆项，不存在返回None
        """
        pass
    
    @abstractmethod
    async def search_memories(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[MemoryItem]:
        """
        搜索记忆
        
        Args:
            query: 查询文本
            memory_type: 记忆类型过滤
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            top_k: 返回数量
        
        Returns:
            记忆列表
        """
        pass
    
    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
        
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            updates: 更新字段
        
        Returns:
            是否更新成功
        """
        pass
    
    @abstractmethod
    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        """
        获取最近记忆
        
        Args:
            limit: 数量限制
            memory_type: 记忆类型过滤
        
        Returns:
            记忆列表
        """
        pass
    
    @abstractmethod
    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        pass
    
    @abstractmethod
    async def clear_memory(self, memory_type: Optional[MemoryType] = None) -> bool:
        """
        清空记忆
        
        Args:
            memory_type: 记忆类型，None表示清空所有
        
        Returns:
            是否清空成功
        """
        pass


class MemoryManager:
    """
    记忆管理器（第一阶段实现）
    
    统一管理不同类型的记忆，提供统一访问接口
    """
    
    def __init__(self):
        """初始化记忆管理器"""
        self._memory_stores: Dict[MemoryType, BaseMemoryInterface] = {}
    
    def register_memory_store(
        self,
        memory_type: MemoryType,
        store: BaseMemoryInterface
    ):
        """注册记忆存储"""
        self._memory_stores[memory_type] = store
    
    async def add_memory(self, memory: MemoryItem) -> str:
        """添加记忆"""
        store = self._memory_stores.get(memory.memory_type)
        if store is None:
            raise ValueError(f"未注册的记忆类型: {memory.memory_type}")
        return await store.add_memory(memory)
    
    async def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆（从所有存储中查找）"""
        for store in self._memory_stores.values():
            memory = await store.get_memory(memory_id)
            if memory:
                return memory
        return None
    
    async def search_memories(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[MemoryItem]:
        """搜索记忆"""
        if memory_type:
            # 只搜索指定类型
            store = self._memory_stores.get(memory_type)
            if store:
                return await store.search_memories(
                    query, memory_type, user_id, group_id, top_k
                )
            return []
        else:
            # 搜索所有类型
            all_results = []
            for mtype, store in self._memory_stores.items():
                results = await store.search_memories(
                    query, mtype, user_id, group_id, top_k
                )
                all_results.extend(results)
            
            # 按重要性和时间排序
            all_results.sort(
                key=lambda m: (m.importance, -m.timestamp),
                reverse=True
            )
            
            return all_results[:top_k]
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        for store in self._memory_stores.values():
            success = await store.delete_memory(memory_id)
            if success:
                return True
        return False
    
    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        for store in self._memory_stores.values():
            success = await store.update_memory(memory_id, updates)
            if success:
                return True
        return False
    
    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        """获取最近记忆"""
        if memory_type:
            store = self._memory_stores.get(memory_type)
            if store:
                return await store.get_recent_memories(limit, memory_type)
            return []
        else:
            # 从所有类型获取
            all_memories = []
            for mtype, store in self._memory_stores.items():
                memories = await store.get_recent_memories(limit, mtype)
                all_memories.extend(memories)
            
            # 按时间排序
            all_memories.sort(key=lambda m: m.timestamp, reverse=True)
            return all_memories[:limit]
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        stats = {}
        for mtype, store in self._memory_stores.items():
            stats[mtype.value] = await store.get_memory_stats()
        return stats
    
    async def clear_memory(self, memory_type: Optional[MemoryType] = None) -> bool:
        """清空记忆"""
        if memory_type:
            store = self._memory_stores.get(memory_type)
            if store:
                return await store.clear_memory(memory_type)
            return False
        else:
            # 清空所有
            success = True
            for store in self._memory_stores.values():
                if not await store.clear_memory():
                    success = False
            return success


# 全局记忆管理器实例
_global_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局记忆管理器"""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager


__all__ = [
    'MemoryType',
    'MemoryItem',
    'BaseMemoryInterface',
    'MemoryManager',
    'get_memory_manager',
]
