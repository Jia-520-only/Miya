"""
统一记忆系统接口

整合所有记忆系统，提供统一的访问接口：
- MemoryEngine: 潮汐/梦境记忆（Redis + Milvus + Neo4j）
- CognitiveMemorySystem: 认知记忆（三层架构）
- LifeNet: 生活记忆管理
- GRAGMemory: 五元组图谱记忆

设计目标：
1. 统一接口，简化调用
2. 自动路由到合适的记忆系统
3. 保持各系统独立性
4. 支持记忆融合和迁移
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    TIDE = "tide"  # 潮汐记忆（短期）
    DREAM = "dream"  # 梦境记忆（压缩）
    COGNITIVE_SHORT = "cognitive_short"  # 认知短期
    COGNITIVE_COGNITIVE = "cognitive_cognitive"  # 认知观察
    COGNITIVE_PINNED = "cognitive_pinned"  # 置顶备忘
    LIFEBOOK = "lifebook"  # 生活记忆
    GRAG = "grag"  # 五元组图谱


class UnifiedMemoryInterface:
    """
    统一记忆系统接口

    整合所有记忆系统，提供统一的访问接口
    """

    def __init__(
        self,
        memory_engine=None,
        cognitive_memory=None,
        lifebook_manager=None,
        grag_memory=None
    ):
        """
        初始化统一记忆接口

        Args:
            memory_engine: MemoryEngine 实例（潮汐/梦境）
            cognitive_memory: CognitiveMemorySystem 实例
            lifebook_manager: LifeBookManager 实例
            grag_memory: GRAGMemory 实例
        """
        self.memory_engine = memory_engine
        self.cognitive_memory = cognitive_memory
        self.lifebook_manager = lifebook_manager
        self.grag_memory = grag_memory

        logger.info("[统一记忆] 初始化完成")

    # ========== 存储操作 ==========

    async def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.TIDE,
        metadata: Optional[Dict[str, Any]] = None,
        priority: float = 0.5,
        ttl: int = 3600
    ) -> str:
        """
        存储记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型
            metadata: 元数据
            priority: 优先级 (0-1)
            ttl: 生存时间（秒）

        Returns:
            记忆ID
        """
        import time
        import os

        memory_id = f"{int(time.time() * 1000)}_{os.urandom(8).hex()}"

        try:
            # 根据类型路由到对应的记忆系统
            if memory_type in [MemoryType.TIDE, MemoryType.DREAM]:
                if self.memory_engine:
                    self.memory_engine.store_tide(
                        memory_id,
                        {'text': content, **(metadata or {})},
                        priority=priority,
                        ttl=ttl
                    )
                    logger.debug(f"[统一记忆] 存储潮汐记忆: {memory_id}")

            elif memory_type == MemoryType.COGNITIVE_SHORT:
                if self.cognitive_memory:
                    job_id = await self.cognitive_memory.enqueue_job(
                        memo=content,
                        context=metadata or {}
                    )
                    logger.debug(f"[统一记忆] 存储认知短期记忆: {job_id}")

            elif memory_type == MemoryType.COGNITIVE_PINNED:
                if self.cognitive_memory:
                    key = metadata.get('key', memory_id)
                    await self.cognitive_memory.add_pinned_memory(key, content)
                    logger.debug(f"[统一记忆] 存储置顶备忘: {key}")

            elif memory_type == MemoryType.LIFEBOOK:
                if self.lifebook_manager:
                    # 生活记忆特殊处理
                    from webnet.LifeNet.tools.life_add_diary import LifeAddDiary
                    # 这里应该调用LifeNet工具
                    pass

            return memory_id

        except Exception as e:
            logger.error(f"[统一记忆] 存储失败: {e}")
            return ""

    # ========== 检索操作 ==========

    async def retrieve(
        self,
        memory_id: str,
        memory_type: Optional[MemoryType] = None
    ) -> Optional[Dict[str, Any]]:
        """
        检索记忆

        Args:
            memory_id: 记忆ID
            memory_type: 记忆类型（可选，用于优化查询）

        Returns:
            记忆内容或None
        """
        # 先尝试潮汐记忆
        if self.memory_engine:
            result = self.memory_engine.retrieve_tide(memory_id)
            if result:
                return result

        # 尝试认知记忆
        if self.cognitive_memory:
            # 短期记忆
            for mem in self.cognitive_memory.get_short_term_memories():
                if memory_id in str(mem):
                    return mem

            # 置顶备忘
            pinned = self.cognitive_memory.get_pinned_memories()
            if memory_id in pinned:
                return {'content': pinned[memory_id], 'type': 'pinned'}

        return None

    async def search(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        top_k: int = 10,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            query: 查询文本
            memory_types: 要搜索的记忆类型（None表示全部）
            top_k: 返回数量
            user_id: 用户ID过滤
            group_id: 群ID过滤

        Returns:
            记忆列表
        """
        results = []

        # 确定要搜索的类型
        types_to_search = memory_types or list(MemoryType)

        # 搜索梦境记忆
        if MemoryType.DREAM in types_to_search and self.memory_engine:
            try:
                dream_results = self.memory_engine.search_dream(query, top_k)
                for r in dream_results:
                    r['memory_type'] = MemoryType.DREAM.value
                results.extend(dream_results)
            except Exception as e:
                logger.warning(f"梦境记忆搜索失败: {e}")

        # 搜索认知记忆
        if MemoryType.COGNITIVE_COGNITIVE in types_to_search and self.cognitive_memory:
            try:
                cognitive_results = await self.cognitive_memory.search_cognitive_events(
                    query=query,
                    user_id=user_id or "",
                    group_id=group_id or "",
                    top_k=top_k
                )
                for r in cognitive_results:
                    results.append({
                        'content': r.content,
                        'memory_type': MemoryType.COGNITIVE_COGNITIVE.value,
                        'user_id': r.user_id,
                        'group_id': r.group_id,
                        'timestamp': r.timestamp_utc
                    })
            except Exception as e:
                logger.warning(f"认知记忆搜索失败: {e}")

        # 排序并返回top_k
        # 简化版：按出现顺序
        return results[:top_k]

    # ========== 统计操作 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        stats = {
            'total_memory': 0,
            'by_type': {}
        }

        # 潮汐记忆统计
        if self.memory_engine:
            mem_stats = self.memory_engine.get_memory_stats()
            stats['by_type'][MemoryType.TIDE.value] = mem_stats['tide_count']
            stats['by_type'][MemoryType.DREAM.value] = mem_stats['dream_count']
            stats['total_memory'] += mem_stats['tide_count'] + mem_stats['dream_count']

        # 认知记忆统计
        if self.cognitive_memory:
            short_count = len(self.cognitive_memory.short_term_memories)
            cognitive_count = len(self.cognitive_memory.cognitive_events)
            pinned_count = len(self.cognitive_memory.pinned_memories)

            stats['by_type'][MemoryType.COGNITIVE_SHORT.value] = short_count
            stats['by_type'][MemoryType.COGNITIVE_COGNITIVE.value] = cognitive_count
            stats['by_type'][MemoryType.COGNITIVE_PINNED.value] = pinned_count
            stats['total_memory'] += short_count + cognitive_count + pinned_count

        # 生活记忆统计
        if self.lifebook_manager:
            stats['by_type'][MemoryType.LIFEBOOK.value] = len(self.lifebook_manager.nodes)
            stats['total_memory'] += len(self.lifebook_manager.nodes)

        return stats

    # ========== 维护操作 ==========

    async def cleanup(self):
        """清理过期记忆"""
        # 清理潮汐记忆
        if self.memory_engine:
            expired_count = self.memory_engine.cleanup_expired()
            if expired_count > 0:
                logger.info(f"[统一记忆] 清理了 {expired_count} 条过期潮汐记忆")

        # 清理认知记忆资源
        if self.cognitive_memory:
            await self.cognitive_memory.cleanup()

        logger.info("[统一记忆] 清理完成")

    async def compress_tide_to_dream(self, memory_id: str) -> bool:
        """将潮汐记忆压缩为梦境记忆"""
        if not self.memory_engine:
            return False

        try:
            self.memory_engine.compress_to_dream(memory_id)
            logger.info(f"[统一记忆] 压缩记忆: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"[统一记忆] 压缩失败: {e}")
            return False


# 全局单例
_unified_memory: Optional[UnifiedMemoryInterface] = None


def get_unified_memory(
    memory_engine=None,
    cognitive_memory=None,
    lifebook_manager=None,
    grag_memory=None
) -> UnifiedMemoryInterface:
    """
    获取统一记忆系统单例

    Args:
        memory_engine: MemoryEngine 实例
        cognitive_memory: CognitiveMemorySystem 实例
        lifebook_manager: LifeBookManager 实例
        grag_memory: GRAGMemory 实例

    Returns:
        UnifiedMemoryInterface 实例
    """
    global _unified_memory
    if _unified_memory is None:
        _unified_memory = UnifiedMemoryInterface(
            memory_engine=memory_engine,
            cognitive_memory=cognitive_memory,
            lifebook_manager=lifebook_manager,
            grag_memory=grag_memory
        )
    return _unified_memory
