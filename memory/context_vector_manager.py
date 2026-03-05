"""
弥娅 - 上下文向量衰减聚合管理器
从VCPToolBox浪潮RAG V3整合
实现上下文向量的动态衰减聚合，支持模糊匹配
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VectorEntry:
    """向量条目"""
    vector: List[float]
    role: str  # 'user' or 'assistant'
    original_text: str
    timestamp: float  # Unix timestamp


class ContextVectorManager:
    """
    上下文向量对应映射管理器

    功能：
    1. 维护当前会话中所有消息的向量映射
    2. 提供模糊匹配技术，处理微小编辑
    3. 实现上下文向量衰减聚合
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.85,
        decay_rate: float = 0.75,
        max_context_window: int = 10
    ):
        """
        初始化上下文向量管理器

        Args:
            fuzzy_threshold: 模糊匹配阈值 (0.0 ~ 1.0)
            decay_rate: 衰减率（用于聚合）
            max_context_window: 最大聚合窗口（最近N条）
        """
        self.vector_map: Dict[str, VectorEntry] = {}  # hash -> VectorEntry

        # 按角色分类的历史向量（按时间顺序）
        self.history_assistant_vectors: List[VectorEntry] = []
        self.history_user_vectors: List[VectorEntry] = []

        self.fuzzy_threshold = fuzzy_threshold
        self.decay_rate = decay_rate
        self.max_context_window = max_context_window

        logger.info(
            f"[ContextVectorManager] 初始化完成 - "
            f"fuzzy={fuzzy_threshold}, decay={decay_rate}, window={max_context_window}"
        )

    def _normalize(self, text: str) -> str:
        """
        文本归一化处理

        Args:
            text: 原始文本

        Returns:
            归一化后的文本
        """
        if not text:
            return ''

        # 移除HTML标签
        import re
        text = re.sub(r'<[^>]+>', '', text)

        # 移除工具标记（如【工具调用:xxx】）
        text = re.sub(r'【工具调用:[^】]+】', '', text)
        text = re.sub(r'【工具结果:[^】]+】', '', text)

        # 移除表情符号（简化版）
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

        # 转小写，移除多余空格
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)

        return text

    def _generate_hash(self, text: str) -> str:
        """
        生成内容哈希

        Args:
            text: 原始文本

        Returns:
            SHA256哈希字符串
        """
        normalized = self._normalize(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        计算字符串相似度（Dice系数）

        Args:
            str1: 字符串1
            str2: 字符串2

        Returns:
            相似度 0.0 ~ 1.0
        """
        if str1 == str2:
            return 1.0
        if len(str1) < 2 or len(str2) < 2:
            return 0

        # 生成二元组
        def get_bigrams(s: str) -> set:
            return {s[i:i+2] for i in range(len(s) - 1)}

        bigrams1 = get_bigrams(str1)
        bigrams2 = get_bigrams(str2)

        if not bigrams1 or not bigrams2:
            return 0

        # 计算交集
        intersection = len(bigrams1 & bigrams2)

        # Dice系数
        dice = (2.0 * intersection) / (len(bigrams1) + len(bigrams2))

        return dice

    def _find_fuzzy_match(self, normalized_text: str) -> Optional[List[float]]:
        """
        尝试在现有缓存中寻找模糊匹配的向量

        Args:
            normalized_text: 归一化后的文本

        Returns:
            匹配到的向量，未找到返回None
        """
        for entry in self.vector_map.values():
            similarity = self._calculate_similarity(
                normalized_text,
                self._normalize(entry.original_text)
            )
            if similarity >= self.fuzzy_threshold:
                logger.debug(
                    f"[ContextVectorManager] 模糊匹配成功 "
                    f"(相似度={similarity:.3f})"
                )
                return entry.vector

        return None

    def update_context(
        self,
        messages: List[Dict],
        get_embedding_func: Optional[callable] = None
    ) -> Tuple[List[VectorEntry], List[VectorEntry]]:
        """
        更新上下文映射

        Args:
            messages: 消息列表，格式: [{'role': 'user'|'assistant', 'content': '...'}, ...]
            get_embedding_func: 获取向量的函数 (text -> List[float])，可选

        Returns:
            (assistant_vectors, user_vectors) - 更新后的向量列表
        """
        if not isinstance(messages, list):
            return self.history_assistant_vectors, self.history_user_vectors

        # 识别最后的消息索引
        last_user_idx = None
        last_assistant_idx = None
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user':
                last_user_idx = i
            elif msg.get('role') == 'assistant':
                last_assistant_idx = i

        new_assistant_vectors = []
        new_user_vectors = []

        # 处理每条消息
        for idx, msg in enumerate(messages):
            role = msg.get('role', '')
            content = msg.get('content', '')

            # 跳过系统消息和最后一条用户/AI消息
            if role == 'system':
                continue
            if idx == last_user_idx or idx == last_assistant_idx:
                continue

            if not content or len(content) < 2:
                continue

            # 提取文本（处理content可能是数组的情况）
            if isinstance(content, list):
                text_parts = [
                    part.get('text', '')
                    for part in content
                    if part.get('type') == 'text'
                ]
                text = ''.join(text_parts)
            else:
                text = str(content)

            normalized = self._normalize(text)
            content_hash = self._generate_hash(text)

            # 尝试获取向量
            vector = None

            # 1. 精确匹配
            if content_hash in self.vector_map:
                vector = self.vector_map[content_hash].vector
                logger.debug(f"[ContextVectorManager] 精确匹配: {text[:30]}...")

            # 2. 模糊匹配
            else:
                vector = self._find_fuzzy_match(normalized)

                # 3. 使用外部embedding函数
                if not vector and get_embedding_func:
                    try:
                        vector = get_embedding_func(text)
                        logger.debug(f"[ContextVectorManager] 获取新向量: {text[:30]}...")

                        # 存入映射
                        self.vector_map[content_hash] = VectorEntry(
                            vector=vector,
                            role=role,
                            original_text=text,
                            timestamp=datetime.now().timestamp()
                        )
                    except Exception as e:
                        logger.error(f"[ContextVectorManager] 获取向量失败: {e}")

            # 添加到历史记录
            if vector:
                entry = VectorEntry(
                    vector=vector,
                    role=role,
                    original_text=text,
                    timestamp=datetime.now().timestamp()
                )

                if role == 'assistant':
                    new_assistant_vectors.append(entry)
                elif role == 'user':
                    new_user_vectors.append(entry)

        # 更新历史记录
        self.history_assistant_vectors = new_assistant_vectors
        self.history_user_vectors = new_user_vectors

        logger.info(
            f"[ContextVectorManager] 上下文更新完成 - "
            f"assistant: {len(new_assistant_vectors)}, user: {len(new_user_vectors)}"
        )

        return new_assistant_vectors, new_user_vectors

    def aggregate_context_vector(
        self,
        role: str = 'all',
        apply_decay: bool = True
    ) -> Optional[List[float]]:
        """
        聚合上下文向量（带衰减）

        Args:
            role: 'user' | 'assistant' | 'all'
            apply_decay: 是否应用衰减

        Returns:
            聚合后的向量，未找到返回None
        """
        vectors = []

        if role in ['all', 'assistant']:
            vectors.extend(self.history_assistant_vectors)
        if role in ['all', 'user']:
            vectors.extend(self.history_user_vectors)

        if not vectors:
            return None

        # 限制聚合窗口
        vectors = vectors[-self.max_context_window:]

        if not vectors:
            return None

        # 计算衰减权重
        num_vectors = len(vectors)
        if apply_decay:
            # 指数衰减：最新的权重最大
            weights = [self.decay_rate ** (num_vectors - i - 1) for i in range(num_vectors)]
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]  # 归一化
        else:
            # 平均权重
            weights = [1.0 / num_vectors] * num_vectors

        # 加权平均向量
        vector_dim = len(vectors[0].vector)
        aggregated = [0.0] * vector_dim

        for i, entry in enumerate(vectors):
            weight = weights[i]
            for j in range(vector_dim):
                aggregated[j] += entry.vector[j] * weight

        logger.debug(
            f"[ContextVectorManager] 聚合向量 - "
            f"count={num_vectors}, role={role}, decay={apply_decay}"
        )

        return aggregated

    def clear(self):
        """清空所有缓存"""
        self.vector_map.clear()
        self.history_assistant_vectors.clear()
        self.history_user_vectors.clear()
        logger.info("[ContextVectorManager] 缓存已清空")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_cached': len(self.vector_map),
            'assistant_vectors': len(self.history_assistant_vectors),
            'user_vectors': len(self.history_user_vectors),
            'fuzzy_threshold': self.fuzzy_threshold,
            'decay_rate': self.decay_rate,
            'max_context_window': self.max_context_window
        }


# 全局管理器实例
_manager_instance = None


def get_context_manager(
    fuzzy_threshold: float = 0.85,
    decay_rate: float = 0.75,
    max_context_window: int = 10
) -> ContextVectorManager:
    """获取上下文向量管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ContextVectorManager(
            fuzzy_threshold, decay_rate, max_context_window
        )
    return _manager_instance
