"""
弥娅 - 语义动力学记忆引擎
整合VCPToolBox浪潮RAG V3的核心能力
实现基于语义动力学的记忆检索和推理
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from .context_vector_manager import ContextVectorManager, get_context_manager
from .meta_thinking_manager import MetaThinkingManager, get_meta_thinking_manager
from .semantic_group_manager import SemanticGroupManager, get_semantic_group_manager
from .time_expression_parser import ChineseTimeExpressionParser, parse_time_expressions

logger = logging.getLogger(__name__)


@dataclass
class MemoryRetrievalResult:
    """记忆检索结果"""
    content: str
    score: float
    metadata: Dict
    time_ranges: List = None  # 匹配到的时间范围


@dataclass
class SemanticDynamicsResult:
    """语义动力学结果"""
    retrieved_memories: List[MemoryRetrievalResult]
    context_influence: float  # 上下文影响度
    semantic_groups: List[str]  # 激活的语义组
    reasoning_chain: Optional[str] = None  # 元思考链内容
    vcp_debug_info: Dict = None  # VCP调试信息


class SemanticDynamicsEngine:
    """
    语义动力学记忆引擎

    核心原理（来自VCPToolBox浪潮RAG V3）：

    1. **向量是单程票**：信息损失不可逆
    2. **逻辑在运动中**：单一状态无法捕捉过程
    3. **记忆≠知识**：动力学才是核心

    系统架构：
    - ContextVectorManager: 上下文向量衰减聚合
    - MetaThinkingManager: 元思考递归推理链
    - SemanticGroupManager: 语义组增强
    - TimeExpressionParser: 时域解析
    """

    def __init__(
        self,
        config: Optional[Dict] = None
    ):
        """
        初始化语义动力学引擎

        Args:
            config: 配置字典
        """
        self.config = config or {}

        # 初始化子模块
        self.context_manager = get_context_manager(
            fuzzy_threshold=self.config.get('fuzzy_threshold', 0.85),
            decay_rate=self.config.get('decay_rate', 0.75),
            max_context_window=self.config.get('max_context_window', 10)
        )

        self.meta_thinking = get_meta_thinking_manager()

        self.semantic_groups = get_semantic_group_manager()

        self.time_parser = ChineseTimeExpressionParser(
            timezone=self.config.get('timezone', 'Asia/Shanghai')
        )

        # 嵌入函数（需要外部设置）
        self.get_embedding_func = None

        # 检索函数（需要外部设置）
        self.retrieve_func = None

        # AI记忆处理函数（需要外部设置）
        self.ai_memo_func = None

        logger.info("[SemanticDynamicsEngine] 初始化完成")

    def set_embedding_func(self, func: callable):
        """设置嵌入函数"""
        self.get_embedding_func = func
        logger.info("[SemanticDynamicsEngine] 嵌入函数已设置")

    def set_retrieve_func(self, func: callable):
        """设置检索函数"""
        self.retrieve_func = func
        logger.info("[SemanticDynamicsEngine] 检索函数已设置")

    def set_ai_memo_func(self, func: callable):
        """设置AI记忆处理函数"""
        self.ai_memo_func = func
        logger.info("[SemanticDynamicsEngine] AI记忆函数已设置")

    async def initialize(self):
        """初始化引擎"""
        await self.semantic_groups.initialize()
        await self.meta_thinking.load_config()
        logger.info("[SemanticDynamicsEngine] 初始化成功")

    async def process_conversation(
        self,
        messages: List[Dict],
        enable_meta_thinking: bool = False,
        enable_semantic_groups: bool = True,
        meta_chain_name: str = 'default',
        meta_k_sequence: Optional[List[int]] = None
    ) -> SemanticDynamicsResult:
        """
        处理对话，执行语义动力学检索

        Args:
            messages: 消息列表
            enable_meta_thinking: 是否启用元思考链
            enable_semantic_groups: 是否启用语义组
            meta_chain_name: 元思考链名称
            meta_k_sequence: 元思考链K值序列

        Returns:
            SemanticDynamicsResult: 检索结果
        """
        if not messages:
            return SemanticDynamicsResult(
                retrieved_memories=[],
                context_influence=0.0,
                semantic_groups=[],
                vcp_debug_info={}
            )

        # 获取最后一条消息
        last_message = messages[-1]
        user_content = last_message.get('content', '')

        if isinstance(user_content, list):
            user_content = ' '.join([
                part.get('text', '')
                for part in user_content
                if part.get('type') == 'text'
            ])

        # 1. 更新上下文向量
        assistant_vectors, user_vectors = self.context_manager.update_context(
            messages,
            self.get_embedding_func
        )

        context_influence = len(assistant_vectors + user_vectors) / max(
            len(messages), 1
        )

        # 2. 解析时间表达式
        time_ranges = self.time_parser.parse(user_content)

        # 3. 匹配语义组
        activated_groups = []
        if enable_semantic_groups:
            activated_groups = self.semantic_groups.get_active_groups(
                user_content,
                threshold=self.config.get('group_threshold', 1.0),
                max_groups=self.config.get('max_groups', 3)
            )

        group_names = [g.name for g in activated_groups]

        # 4. 执行检索
        retrieved_memories = []

        if self.retrieve_func:
            try:
                # 构建查询向量
                query_vector = None
                if self.get_embedding_func and user_content:
                    query_vector = await self._safe_embedding(user_content)

                # 聚合上下文向量
                context_vector = self.context_manager.aggregate_context_vector(
                    role='all',
                    apply_decay=True
                )

                # 融合上下文和查询向量
                if context_vector and query_vector:
                    query_vector = self._fuse_vectors(
                        context_vector,
                        query_vector,
                        context_weight=0.3,
                        query_weight=0.7
                    )

                # 执行检索
                if query_vector:
                    search_params = {
                        'time_ranges': time_ranges,
                        'semantic_groups': group_names
                    }

                    raw_results = self.retrieve_func(query_vector, **search_params)

                    # 转换为MemoryRetrievalResult
                    for item in raw_results:
                        retrieved_memories.append(
                            MemoryRetrievalResult(
                                content=item.get('content', ''),
                                score=item.get('score', 0.0),
                                metadata=item.get('metadata', {}),
                                time_ranges=time_ranges
                            )
                        )

            except Exception as e:
                logger.error(f"[SemanticDynamicsEngine] 检索失败: {e}")

        # 5. 执行元思考链（可选）
        reasoning_chain = None
        vcp_info = {}

        if enable_meta_thinking and self.get_embedding_func and user_content:
            try:
                query_vector = await self._safe_embedding(user_content)

                result = await self.meta_thinking.process_chain(
                    chain_name=meta_chain_name,
                    query_vector=query_vector,
                    user_content=user_content,
                    ai_content=messages[-2].get('content', '') if len(messages) >= 2 else '',
                    retrieve_func=self._meta_thinking_retrieve,
                    k_sequence=meta_k_sequence,
                    context_vector=self.context_manager.aggregate_context_vector()
                )

                reasoning_chain = result.final_content
                vcp_info = result.vcp_info

            except Exception as e:
                logger.error(f"[SemanticDynamicsEngine] 元思考链执行失败: {e}")

        # 6. AI记忆召回（可选）
        if self.ai_memo_func:
            try:
                ai_memo_content = self.ai_memo_func(
                    user_content=user_content,
                    ai_content=messages[-2].get('content', '') if len(messages) >= 2 else ''
                )

                if ai_memo_content:
                    retrieved_memories.insert(
                        0,
                        MemoryRetrievalResult(
                            content=ai_memo_content,
                            score=1.0,
                            metadata={'type': 'ai_memo'}
                        )
                    )
            except Exception as e:
                logger.error(f"[SemanticDynamicsEngine] AI记忆处理失败: {e}")

        # 构建结果
        result = SemanticDynamicsResult(
            retrieved_memories=retrieved_memories,
            context_influence=context_influence,
            semantic_groups=group_names,
            reasoning_chain=reasoning_chain,
            vcp_debug_info=vcp_info
        )

        logger.info(
            f"[SemanticDynamicsEngine] 检索完成 - "
            f"记忆数: {len(retrieved_memories)}, "
            f"上下文影响: {context_influence:.3f}, "
            f"语义组: {group_names}"
        )

        return result

    async def _safe_embedding(self, text: str) -> Optional[List[float]]:
        """安全地获取向量（带异常处理）"""
        if not self.get_embedding_func:
            return None

        try:
            return await self.get_embedding_func(text)
        except Exception as e:
            logger.error(f"[SemanticDynamicsEngine] 获取向量失败: {e}")
            return None

    def _fuse_vectors(
        self,
        vec1: List[float],
        vec2: List[float],
        context_weight: float = 0.4,
        query_weight: float = 0.6
    ) -> List[float]:
        """向量融合"""
        if len(vec1) != len(vec2):
            min_len = min(len(vec1), len(vec2))
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]

        return [
            v1 * context_weight + v2 * query_weight
            for v1, v2 in zip(vec1, vec2)
        ]

    def _meta_thinking_retrieve(
        self,
        vector: List[float],
        k: int,
        cluster_name: str
    ) -> List[Dict]:
        """
        元思考链的检索函数

        Args:
            vector: 查询向量
            k: 召回数量
            cluster_name: 簇名称

        Returns:
            检索结果列表
        """
        # 这里需要根据实际的数据源实现
        # 示例：从语义组对应的文件中检索
        if not self.retrieve_func:
            return []

        try:
            return self.retrieve_func(vector, k=k, cluster=cluster_name)
        except Exception as e:
            logger.error(
                f"[SemanticDynamicsEngine] 元思考检索失败: "
                f"cluster={cluster_name}, error={e}"
            )
            return []

    def get_context_summary(self) -> Dict:
        """获取上下文摘要"""
        return self.context_manager.get_stats()

    def get_semantic_group_summary(self) -> Dict:
        """获取语义组摘要"""
        groups = self.semantic_groups.get_all_groups()
        return {
            'total_groups': len(groups),
            'group_names': list(groups.keys()),
            'groups': {
                name: {
                    'words': group.words,
                    'weight': group.weight
                }
                for name, group in groups.items()
            }
        }


# 全局引擎实例
_engine_instance = None


def get_semantic_dynamics_engine(
    config: Optional[Dict] = None
) -> SemanticDynamicsEngine:
    """获取语义动力学引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SemanticDynamicsEngine(config)
    return _engine_instance
