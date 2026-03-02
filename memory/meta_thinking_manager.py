"""
弥娅 - 元思考递归推理链管理器
从VCPToolBox浪潮RAG V3整合
实现多阶段向量融合的递归推理系统
"""

import asyncio
import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ThinkingChainConfig:
    """思维链配置"""
    name: str
    clusters: List[str]  # 簇名称列表
    k_sequence: List[int]  # 每个簇的召回数量序列


@dataclass
class ChainExecutionResult:
    """思维链执行结果"""
    chain_name: str
    stages: List[Dict]  # 每个阶段的结果
    final_content: str
    vcp_info: Dict  # 可视化调试信息


class MetaThinkingManager:
    """
    元思考递归推理链管理器

    核心原理：
    用户输入 → 向量化 →
      ↓
    阶段1: 前思维簇 (k=2) → 召回2个元逻辑 → 向量融合(40%上下文 + 60%结果)
      ↓
    阶段2: 逻辑推理簇 (k=1) → 召回1个元逻辑 → 向量融合
      ↓
    阶段3: 反思簇 (k=1) → 召回1个元逻辑 → 向量融合
      ↓
    阶段4: 结果辩证簇 (k=1) → 召回1个元逻辑 → 向量融合
      ↓
    阶段5: 陈词总结梳理簇 (k=1) → 召回1个元逻辑 → 完整思维链

    每一阶段的结果都会影响下一阶段的查询方向。
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化元思考管理器

        Args:
            config_dir: 配置文件目录路径
        """
        self.chains: Dict[str, ThinkingChainConfig] = {}
        self.chain_vectors: Dict[str, List[float]] = {}  # 链主题向量缓存
        self._config_dir = config_dir or Path(__file__).parent
        self._load_promise = None

        # 融合权重
        self.context_weight = 0.4  # 上下文权重
        self.result_weight = 0.6   # 结果权重

        logger.info("[MetaThinkingManager] 初始化完成")

    async def load_config(self):
        """加载配置"""
        if self._load_promise:
            return await self._load_promise

        self._load_promise = self._do_load_config()
        return await self._load_promise

    async def _do_load_config(self):
        """执行配置加载"""
        try:
            config_path = self._config_dir / 'meta_thinking_chains.json'
            cache_path = self._config_dir / 'meta_chain_vector_cache.json'

            if not config_path.exists():
                logger.warning("[MetaThinkingManager] 配置文件不存在")
                # 创建默认配置
                self._create_default_config(config_path)
                return

            # 读取链配置
            with open(config_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)

            self.chains = {}
            for chain_name, chain_info in chain_data.get('chains', {}).items():
                self.chains[chain_name] = ThinkingChainConfig(
                    name=chain_name,
                    clusters=chain_info,
                    k_sequence=[1] * len(chain_info)  # 默认k=1
                )

            logger.info(
                f"[MetaThinkingManager] 加载了 {len(self.chains)} 个思维链"
            )

            # 加载向量缓存
            if cache_path.exists():
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.chain_vectors = cache_data.get('vectors', {})
                    logger.info(
                        f"[MetaThinkingManager] 加载了 {len(self.chain_vectors)} 个主题向量缓存"
                    )

        except Exception as e:
            logger.error(f"[MetaThinkingManager] 加载配置失败: {e}")
            self.chains = {}
            self.chain_vectors = {}

    def _create_default_config(self, config_path: Path):
        """创建默认配置"""
        default_config = {
            "chains": {
                "default": [
                    "前思维簇",
                    "逻辑推理簇",
                    "反思簇",
                    "结果辩证簇",
                    "陈词总结梳理簇"
                ]
            }
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

        self.chains = {
            "default": ThinkingChainConfig(
                name="default",
                clusters=default_config["chains"]["default"],
                k_sequence=[1] * 5
            )
        }

        logger.info("[MetaThinkingManager] 创建了默认思维链配置")

    async def process_chain(
        self,
        chain_name: str,
        query_vector: List[float],
        user_content: str,
        ai_content: str,
        retrieve_func: callable,
        k_sequence: Optional[List[int]] = None,
        context_vector: Optional[List[float]] = None
    ) -> ChainExecutionResult:
        """
        处理元思考链

        Args:
            chain_name: 思维链名称
            query_vector: 查询向量
            user_content: 用户输入
            ai_content: AI回复
            retrieve_func: 检索函数 (vector, k, cluster_name) -> List[Dict]
            k_sequence: K值序列（覆盖配置中的k_sequence）
            context_vector: 初始上下文向量（可选）

        Returns:
            ChainExecutionResult: 执行结果
        """
        await self.load_config()

        if chain_name not in self.chains:
            logger.warning(f"[MetaThinkingManager] 链不存在: {chain_name}，使用默认链")
            chain_name = 'default'

        chain = self.chains[chain_name]
        k_seq = k_sequence or chain.k_sequence

        logger.info(
            f"[MetaThinkingManager] 开始执行思维链: {chain_name} "
            f"(簇数: {len(chain.clusters)}, K序列: {k_seq})"
        )

        current_vector = query_vector.copy()
        if context_vector:
            # 初始融合
            current_vector = self._fuse_vectors(context_vector, current_vector)

        stages = []
        vcp_info = {
            'chain_name': chain_name,
            'chain_path': ' → '.join(chain.clusters),
            'stages': []
        }

        # 逐阶段执行
        for i, (cluster_name, k) in enumerate(zip(chain.clusters, k_seq)):
            stage_result = await self._execute_stage(
                stage_index=i,
                cluster_name=cluster_name,
                k=k,
                current_vector=current_vector,
                retrieve_func=retrieve_func,
                context_vector=context_vector
            )

            stages.append(stage_result)
            vcp_info['stages'].append(stage_result.get('vcp_info', {}))

            # 更新当前向量（用于下一阶段）
            if stage_result['result_vector']:
                current_vector = stage_result['result_vector']

        # 构建最终内容
        final_content = self._build_final_content(stages)

        result = ChainExecutionResult(
            chain_name=chain_name,
            stages=stages,
            final_content=final_content,
            vcp_info=vcp_info
        )

        logger.info(f"[MetaThinkingManager] 思维链执行完成: {chain_name}")
        return result

    async def _execute_stage(
        self,
        stage_index: int,
        cluster_name: str,
        k: int,
        current_vector: List[float],
        retrieve_func: callable,
        context_vector: Optional[List[float]] = None
    ) -> Dict:
        """
        执行单个阶段

        Args:
            stage_index: 阶段索引
            cluster_name: 簇名称
            k: 召回数量
            current_vector: 当前查询向量
            retrieve_func: 检索函数
            context_vector: 上下文向量（可选）

        Returns:
            阶段结果
        """
        logger.debug(f"[MetaThinkingManager] 执行阶段 {stage_index}: {cluster_name} (k={k})")

        # 检索
        try:
            retrieved = retrieve_func(current_vector, k, cluster_name)
        except Exception as e:
            logger.error(f"[MetaThinkingManager] 检索失败: {e}")
            retrieved = []

        if not retrieved:
            logger.warning(f"[MetaThinkingManager] 未检索到结果: {cluster_name}")
            return {
                'stage_index': stage_index,
                'cluster_name': cluster_name,
                'retrieved': [],
                'result_vector': None,
                'content': '',
                'vcp_info': {
                    'stage': cluster_name,
                    'k': k,
                    'retrieved_count': 0,
                    'status': 'no_results'
                }
            }

        # 计算结果向量（多个结果的平均）
        vectors = [item.get('vector', []) for item in retrieved if item.get('vector')]
        if vectors:
            result_vector = self._average_vectors(vectors)
        else:
            result_vector = None

        # 向量融合
        if result_vector and context_vector:
            fused_vector = self._fuse_vectors(context_vector, result_vector)
        else:
            fused_vector = result_vector

        # 构建内容
        contents = [item.get('content', '') for item in retrieved]
        stage_content = '\n\n'.join(contents)

        # VCP信息
        vcp_info = {
            'stage': cluster_name,
            'k': k,
            'retrieved_count': len(retrieved),
            'has_vector': result_vector is not None,
            'status': 'success'
        }

        logger.debug(
            f"[MetaThinkingManager] 阶段 {stage_index} 完成 - "
            f"召回 {len(retrieved)} 个结果"
        )

        return {
            'stage_index': stage_index,
            'cluster_name': cluster_name,
            'retrieved': retrieved,
            'result_vector': fused_vector,
            'content': stage_content,
            'vcp_info': vcp_info
        }

    def _fuse_vectors(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> List[float]:
        """
        向量融合

        Args:
            vec1: 向量1（通常是上下文向量）
            vec2: 向量2（通常是结果向量）

        Returns:
            融合后的向量
        """
        if len(vec1) != len(vec2):
            logger.warning(
                f"[MetaThinkingManager] 向量维度不匹配: {len(vec1)} vs {len(vec2)}"
            )
            # 截断或填充
            min_len = min(len(vec1), len(vec2))
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]

        # 加权融合: 40% vec1 + 60% vec2
        fused = [
            v1 * self.context_weight + v2 * self.result_weight
            for v1, v2 in zip(vec1, vec2)
        ]

        return fused

    def _average_vectors(self, vectors: List[List[float]]) -> List[float]:
        """
        计算向量平均值

        Args:
            vectors: 向量列表

        Returns:
            平均向量
        """
        if not vectors:
            return []

        # 转换为numpy数组
        arr = np.array(vectors)

        # 计算平均值
        avg = np.mean(arr, axis=0)

        return avg.tolist()

    def _build_final_content(self, stages: List[Dict]) -> str:
        """
        构建最终思维链内容

        Args:
            stages: 各阶段结果

        Returns:
            格式化的思维链内容
        """
        parts = []

        for stage in stages:
            if stage['content']:
                parts.append(
                    f"## {stage['cluster_name']}\n\n{stage['content']}"
                )

        if not parts:
            return '[元思考链未生成内容]'

        return '\n\n'.join(parts)


# 全局管理器实例
_manager_instance = None


def get_meta_thinking_manager(config_dir: Optional[str] = None) -> MetaThinkingManager:
    """获取元思考管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MetaThinkingManager(config_dir)
    return _manager_instance
