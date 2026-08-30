"""
弥娅 RRF 混合搜索融合 (Reciprocal Rank Fusion)

参考 TencentDB Agent Memory 的混合搜索设计，用科学的多源重排序
替换原有的简单权重叠加。

RRF 公式: score(d) = Σ 1 / (k + rank_i(d))
- k=60 (标准RRF参数，平滑排名差异)
- 多源融合: 关键词匹配 + 向量语义 + BM25近似 + 上下文加权

优势：
1. 无需归一化各源分数，排名即可融合
2. 对极端排名不敏感，抗噪声能力强
3. 天然支持任意数量检索源的融合
"""

import logging
import math
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from memory.models import MemoryItem, MemoryQuery

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


class BM25Scorer:
    """
    轻量级 BM25 近似实现，用于对记忆内容进行关键词相关性评分。
    基于 TF-IDF 原理，不需要外部依赖。
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._corpus_docs: List[List[str]] = []
        self._avg_dl: float = 0.0
        self._df: Dict[str, int] = Counter()
        self._total_docs: int = 0

    def fit(self, documents: List[str]):
        self._corpus_docs = []
        self._df.clear()
        doc_lengths = []

        for doc in documents:
            tokens = self._tokenize(doc)
            self._corpus_docs.append(tokens)
            doc_lengths.append(len(tokens))
            for token in set(tokens):
                self._df[token] = self._df.get(token, 0) + 1

        self._total_docs = len(documents)
        self._avg_dl = sum(doc_lengths) / max(1, len(doc_lengths))

    def score(self, query: str, document: str) -> float:
        query_tokens = self._tokenize(query)
        doc_tokens = self._tokenize(document)
        doc_len = len(doc_tokens)
        term_freqs = Counter(doc_tokens)
        total_score = 0.0

        for token in query_tokens:
            tf = term_freqs.get(token, 0)
            if tf == 0:
                continue
            df = self._df.get(token, 0)
            if df == 0:
                continue
            idf = math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(1, self._avg_dl))
            total_score += idf * numerator / denominator

        return total_score

    def score_all(self, query: str, documents: List[str]) -> List[float]:
        return [self.score(query, doc) for doc in documents]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text.lower())
        tokens = text.split()
        if not tokens:
            return []

        result = list(tokens)
        for i in range(len(text) - 1):
            bigram = text[i : i + 2]
            if len(bigram.strip()) == 2 and "\u4e00" <= bigram[0] <= "\u9fff" and "\u4e00" <= bigram[1] <= "\u9fff":
                result.append(bigram)

        return result


class RRFusion:
    """
    RRF 混合搜索融合引擎

    将多个排名列表融合为统一的最终排名。
    参考 TencentDB Agent Memory 的 hybrid search + RRF 设计。
    """

    def __init__(self, k: int = DEFAULT_RRF_K):
        self.k = k
        self.bm25 = BM25Scorer()
        self._similarity_cache: Dict[str, Dict[str, float]] = {}

    def fuse(
        self,
        ranked_lists: List[List[Tuple[str, float]]],
        weights: Optional[List[float]] = None,
    ) -> List[Tuple[str, float]]:
        """
        融合多个排名列表。

        Args:
            ranked_lists: 多个排名列表，每个元素为 [(id, score), ...]
            weights: 各排名列表的权重，None 则等权

        Returns:
            [(id, fused_score), ...] 按融合分数降序排列
        """
        if not ranked_lists:
            return []

        if weights is None:
            weights = [1.0] * len(ranked_lists)

        rrf_scores: Dict[str, float] = {}

        for list_idx, ranked_list in enumerate(ranked_lists):
            weight = weights[list_idx] if list_idx < len(weights) else 1.0
            for rank, (item_id, _score) in enumerate(ranked_list):
                rrf_contribution = weight / (self.k + rank + 1)
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_contribution

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items

    def hybrid_search(
        self,
        memories: List[MemoryItem],
        query_text: str,
        query_vector: Optional[List[float]] = None,
        context_weights: Optional[Dict[str, Any]] = None,
        keyword_weight: float = 1.0,
        vector_weight: float = 1.0,
        context_weight: float = 0.3,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        混合搜索 — 融合关键词 + 向量 + 上下文 三个维度。

        Args:
            memories: 候选记忆列表
            query_text: 查询文本
            query_vector: 查询向量 (可选，无则降级为纯关键词)
            context_weights: 上下文加权参数 {user_id, group_id, tags, ...}
            keyword_weight: 关键词搜索权重
            vector_weight: 向量搜索权重
            context_weight: 上下文加权权重

        Returns:
            [(MemoryItem, fused_score), ...] 按分数降序排列
        """
        if not memories:
            return []

        item_ids = [m.id for m in memories]

        # 1. 关键词 BM25 排名 (Rank 1)
        keyword_ranked = self._rank_by_keyword(memories, query_text)

        # 2. 向量语义排名 (Rank 2)
        vector_ranked = self._rank_by_vector(memories, query_vector) if query_vector else []

        # 3. 上下文加权排名 (Rank 3)
        context_ranked = self._rank_by_context(memories, context_weights or {}, query_text)

        # 4. 时间衰减排名 (Rank 4)
        time_ranked = self._rank_by_time(memories)

        # 5. RRF 融合
        ranked_lists = [
            [(item_ids[i], s) for i, s in keyword_ranked],
            [(item_ids[i], s) for i, s in vector_ranked] if vector_ranked else [],
            [(item_ids[i], s) for i, s in context_ranked],
            [(item_ids[i], s) for i, s in time_ranked],
        ]

        weights = [keyword_weight, vector_weight if query_vector else 0, context_weight, 0.15]

        ranked_lists = [rl for rl in ranked_lists if rl]
        weights = [w for rl, w in zip(ranked_lists, weights, strict=False) if rl]

        fused = self.fuse(ranked_lists, weights)

        id_to_memory = {m.id: m for m in memories}
        results = []
        for item_id, score in fused:
            mem = id_to_memory.get(item_id)
            if mem:
                results.append((mem, score))

        return results

    def _rank_by_keyword(self, memories: List[MemoryItem], query_text: str) -> List[Tuple[int, float]]:
        """BM25 关键词排名"""
        if not query_text:
            return [(i, 0.0) for i in range(len(memories))]

        contents = [m.content for m in memories]
        try:
            self.bm25.fit(contents)
        except Exception:
            pass

        scores = self.bm25.score_all(query_text, contents)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked

    def _rank_by_vector(self, memories: List[MemoryItem], query_vector: List[float]) -> List[Tuple[int, float]]:
        """向量余弦相似度排名"""
        if not query_vector:
            return []

        scored = []
        for i, mem in enumerate(memories):
            if mem.vector and len(mem.vector) == len(query_vector):
                sim = self._cosine_similarity(query_vector, mem.vector)
                scored.append((i, sim))
            else:
                scored.append((i, 0.0))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _rank_by_context(
        self, memories: List[MemoryItem], context: Dict[str, Any], query_text: str = ""
    ) -> List[Tuple[int, float]]:
        """上下文加权排名"""
        user_id = context.get("user_id", "")
        group_id = context.get("group_id", "")
        tags = context.get("tags", [])
        group_boost = context.get("group_boost", 1.5)
        user_boost = context.get("user_boost", 1.3)
        tag_boost = context.get("tag_boost", 1.2)

        scored = []
        for i, mem in enumerate(memories):
            score = mem.priority

            if group_id and mem.group_id == group_id:
                score *= group_boost
            if user_id and mem.user_id == user_id:
                score *= user_boost

            tag_match_count = 0
            if tags:
                for t in tags:
                    if t in mem.tags or t.lower() in mem.content.lower():
                        tag_match_count += 1
                if tag_match_count > 0:
                    score *= 1.0 + (tag_boost - 1.0) * tag_match_count

            if mem.is_pinned:
                score *= 1.5

            score += mem.significance * 0.1

            if query_text and query_text.lower() in mem.content.lower():
                score *= 1.1

            scored.append((i, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _rank_by_time(self, memories: List[MemoryItem]) -> List[Tuple[int, float]]:
        """时间衰减排名 — 越新的记忆排名越高"""
        from datetime import datetime

        now = datetime.now()
        scored = []
        for i, mem in enumerate(memories):
            try:
                mem_time = datetime.fromisoformat(mem.created_at)
                hours_ago = (now - mem_time).total_seconds() / 3600
                time_score = 1.0 / (1.0 + hours_ago / 24.0)
            except Exception:
                time_score = 0.5
            scored.append((i, time_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def fused_retrieve(
        self,
        memories: List[MemoryItem],
        query: MemoryQuery,
        query_vector: Optional[List[float]] = None,
    ) -> List[MemoryItem]:
        """
        一站式 RRF 融合检索 — 可替代 MiyaMemoryCore.retrieve 的排序逻辑。

        Args:
            memories: 已过滤的候选记忆列表
            query: 查询条件
            query_vector: 查询向量 (可选)

        Returns:
            融合排序后的记忆列表
        """
        results = self.hybrid_search(
            memories=memories,
            query_text=query.query,
            query_vector=query_vector,
            context_weights={
                "user_id": query.user_id or "",
                "group_id": query.group_id or "",
                "tags": query.tags or [],
            },
        )

        sorted_memories = [m for m, _ in results]
        return sorted_memories


_global_rrf: Optional[RRFusion] = None


def get_rrf_fusion() -> RRFusion:
    global _global_rrf
    if _global_rrf is None:
        _global_rrf = RRFusion()
    return _global_rrf
