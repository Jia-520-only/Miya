"""
认知记忆系统适配器

将CognitiveMemorySystem适配到统一记忆接口
"""
import logging
from typing import List, Dict, Any, Optional

from memory.memory_interface import (
    MemoryType, MemoryItem, BaseMemoryInterface
)
from memory.cognitive_memory_system import CognitiveMemorySystem, CognitiveJob


logger = logging.getLogger(__name__)


class CognitiveMemoryAdapter(BaseMemoryInterface):
    """
    认知记忆适配器
    
    将CognitiveMemorySystem适配到统一记忆接口
    """
    
    def __init__(self, cognitive_memory: CognitiveMemorySystem):
        """初始化适配器"""
        self.cognitive_memory = cognitive_memory
    
    async def add_memory(self, memory: MemoryItem) -> str:
        """添加记忆"""
        if memory.memory_type == MemoryType.SHORT_TERM:
            # 添加短期记忆
            await self.cognitive_memory.enqueue_job(
                memo=memory.content,
                context={
                    "user_id": memory.user_id,
                    "group_id": memory.group_id,
                    **memory.metadata
                }
            )
            return f"short_{memory.timestamp}"
        
        elif memory.memory_type == MemoryType.PINNED:
            # 添加置顶记忆
            key = f"pinned_{memory.timestamp}"
            await self.cognitive_memory.add_pinned_memory(key, memory.content)
            return key
        
        elif memory.memory_type == MemoryType.COGNITIVE:
            # 添加认知记忆
            await self.cognitive_memory.enqueue_job(
                observations=[memory.content],
                context={
                    "user_id": memory.user_id,
                    "group_id": memory.group_id,
                    **memory.metadata
                }
            )
            return f"cognitive_{memory.timestamp}"
        
        else:
            logger.warning(f"认知记忆系统不支持类型: {memory.memory_type}")
            return ""
    
    async def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆"""
        if memory_id.startswith("pinned_"):
            # 从置顶记忆获取
            key = memory_id
            content = self.cognitive_memory.get_pinned_memories().get(key)
            if content:
                return MemoryItem(
                    content=content,
                    memory_type=MemoryType.PINNED,
                    timestamp=0.0
                )
        
        elif memory_id.startswith("short_"):
            # 从短期记忆获取
            timestamp = float(memory_id.split("_")[1])
            memories = self.cognitive_memory.get_short_term_memories()
            for mem in memories:
                if mem["timestamp"] == timestamp:
                    return MemoryItem(
                        content=mem["content"],
                        memory_type=MemoryType.SHORT_TERM,
                        timestamp=timestamp,
                        metadata=mem.get("context", {})
                    )
        
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
        if memory_type == MemoryType.COGNITIVE:
            # 搜索认知事件
            events = await self.cognitive_memory.search_cognitive_events(
                query, user_id, group_id, top_k
            )
            return [
                MemoryItem(
                    content=event.content,
                    memory_type=MemoryType.COGNITIVE,
                    timestamp=event.timestamp_epoch,
                    user_id=event.user_id,
                    group_id=event.group_id,
                    metadata={
                        "sender_id": event.sender_id,
                        "request_type": event.request_type,
                        "perspective": event.perspective,
                        "is_absolute": event.is_absolute,
                    }
                )
                for event in events
            ]
        
        elif memory_type == MemoryType.PINNED:
            # 搜索置顶记忆
            pinned = self.cognitive_memory.get_pinned_memories()
            results = []
            for key, content in pinned.items():
                if query.lower() in content.lower():
                    results.append(
                        MemoryItem(
                            content=content,
                            memory_type=MemoryType.PINNED,
                            timestamp=0.0
                        )
                    )
            return results[:top_k]
        
        elif memory_type == MemoryType.SHORT_TERM:
            # 搜索短期记忆
            short_memories = self.cognitive_memory.get_short_term_memories()
            results = []
            for mem in short_memories:
                if query.lower() in mem["content"].lower():
                    results.append(
                        MemoryItem(
                            content=mem["content"],
                            memory_type=MemoryType.SHORT_TERM,
                            timestamp=mem["timestamp"],
                            metadata=mem.get("context", {})
                        )
                    )
            return results[:top_k]
        
        else:
            # 搜索所有类型
            all_results = []
            
            # 搜索认知记忆
            cognitive_results = await self.search_memories(
                query, MemoryType.COGNITIVE, user_id, group_id, top_k
            )
            all_results.extend(cognitive_results)
            
            # 搜索置顶记忆
            pinned_results = await self.search_memories(
                query, MemoryType.PINNED, user_id, group_id, top_k
            )
            all_results.extend(pinned_results)
            
            # 搜索短期记忆
            short_results = await self.search_memories(
                query, MemoryType.SHORT_TERM, user_id, group_id, top_k
            )
            all_results.extend(short_results)
            
            # 按时间戳排序
            all_results.sort(key=lambda m: m.timestamp, reverse=True)
            return all_results[:top_k]
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id.startswith("pinned_"):
            key = memory_id
            await self.cognitive_memory.remove_pinned_memory(key)
            return True
        
        return False
    
    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        # 认知记忆系统不支持更新
        logger.warning("认知记忆系统不支持更新操作")
        return False
    
    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        """获取最近记忆"""
        if memory_type == MemoryType.SHORT_TERM or memory_type is None:
            short_memories = self.cognitive_memory.get_short_term_memories()
            return [
                MemoryItem(
                    content=mem["content"],
                    memory_type=MemoryType.SHORT_TERM,
                    timestamp=mem["timestamp"],
                    metadata=mem.get("context", {})
                )
                for mem in short_memories[-limit:]
            ]
        
        return []
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "short_term_count": len(self.cognitive_memory.short_term_memories),
            "pinned_count": len(self.cognitive_memory.pinned_memories),
            "cognitive_count": len(self.cognitive_memory.cognitive_events),
            "queue_length": len(self.cognitive_memory.job_queue),
        }
    
    async def clear_memory(self, memory_type: Optional[MemoryType] = None) -> bool:
        """清空记忆"""
        if memory_type == MemoryType.SHORT_TERM:
            self.cognitive_memory.short_term_memories.clear()
            return True
        
        elif memory_type == MemoryType.PINNED:
            self.cognitive_memory.pinned_memories.clear()
            await self.cognitive_memory._save_pinned_memories()
            return True
        
        return False


def create_cognitive_adapter(
    cognitive_memory: CognitiveMemorySystem
) -> CognitiveMemoryAdapter:
    """创建认知记忆适配器"""
    return CognitiveMemoryAdapter(cognitive_memory)


__all__ = [
    'CognitiveMemoryAdapter',
    'create_cognitive_adapter',
]
