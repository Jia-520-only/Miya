"""
弥娅认知检索引擎 (CognitiveEngine)

实现智能记忆检索：
- 根据当前对话动态检索相关记忆
- 多策略融合：关键词 + 向量 + 时间衰减
- 只返回最相关的记忆，减少干扰
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.core import MemoryItem, MemoryLevel, MemoryQuery, get_memory_core
from memory.temporal_parser import extract_temporal_keywords, parse_temporal
from memory.date_boundary import (
    classify_memory_age,
    get_date_boundary,
    time_decay_by_boundary,
)

logger = logging.getLogger("Miya.CognitiveEngine")


def _load_cognitive_config() -> Dict[str, Any]:
    """从 memory_config.json 加载 CognitiveEngine 配置"""
    try:
        from memory import load_memory_config

        config = load_memory_config()
        ce = config.get("cognitive_engine", {})
        if ce and (ce.get("topic_keywords") or ce.get("memory_triggers")):
            return ce
    except Exception:
        pass

    try:
        config_dir = Path(__file__).parent.parent / "config"
        text_config_path = config_dir / "text_config.json"
        if text_config_path.exists():
            with open(text_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("cognitive_engine", {})
    except Exception:
        pass
    return {}


class CognitiveEngine:
    """认知检索引擎（V4.1.11: 配置热加载）

    职责：
    - 分析当前对话主题
    - 智能检索相关记忆
    - 融合多种检索策略
    - 生成记忆上下文
    - 记忆关联度学习
    """

    def __init__(self, memory_core=None, embedding_client=None):
        """初始化认知引擎

        Args:
            memory_core: 记忆核心实例
            embedding_client: 向量嵌入客户端（用于语义相似度计算）
        """

        self.memory_core = memory_core
        self._memory_core_initialized = False
        self.embedding_client = embedding_client

        # 动态配置（支持热加载）
        self._config: Dict[str, Any] = {}
        self.topic_keywords: Dict[str, List[str]] = {}
        self.memory_triggers: Dict[str, List[str]] = {}
        self.ignore_patterns: List[str] = []
        self.anchor_keywords: List[str] = []
        self.anchor_tags: List[str] = []
        self.personal_patterns: List[str] = []
        self.personal_query_keywords: List[str] = []
        self.keyword_extraction_patterns: Dict[str, str] = {}
        self._reload_config()
        self._embedding_cache: Dict[str, List[float]] = {}

        # 记忆关联度学习
        self._co_occurrence: Dict[str, Dict[str, int]] = {}  # memory_id -> {related_id: count}
        self._access_frequency: Dict[str, int] = {}  # memory_id -> access count
        self._last_access_time: Dict[str, float] = {}  # memory_id -> last access timestamp (LRU)
        self._last_retrieved_ids: List[str] = []  # 上次检索到的记忆ID列表
        self._co_occurrence_max: int = 2000  # 共现表上限

    def _reload_config(self):
        """热加载认知引擎配置（V4.1.11: 替代模块级全局变量）"""
        cfg = _load_cognitive_config()
        self._config = cfg
        self.topic_keywords = cfg.get("topic_keywords", {})
        self.memory_triggers = cfg.get("memory_triggers", {})
        self.ignore_patterns = cfg.get("ignore_patterns", [])
        anchor_cfg = cfg.get("memory_anchor", {})
        self.anchor_keywords = anchor_cfg.get("anchor_keywords", [])
        self.anchor_tags = anchor_cfg.get("anchor_tags", [])
        self.personal_patterns = anchor_cfg.get("personal_patterns", [])
        self.personal_query_keywords = anchor_cfg.get("personal_query_keywords", [])
        self.keyword_extraction_patterns = anchor_cfg.get("keyword_extraction_patterns", {})
        logger.debug("[CognitiveEngine] 配置已热加载")

    def reload_config(self):
        """外部调用：重新加载配置"""
        self._reload_config()
        self._embedding_cache.clear()

    def _record_co_occurrence(self, memory_ids: List[str]):
        """记录记忆共现关系，用于关联度学习"""
        import time

        now = time.time()
        for i, mid1 in enumerate(memory_ids):
            self._access_frequency[mid1] = self._access_frequency.get(mid1, 0) + 1
            self._last_access_time[mid1] = now
            for j, mid2 in enumerate(memory_ids):
                if i != j:
                    if mid1 not in self._co_occurrence:
                        self._co_occurrence[mid1] = {}
                    self._co_occurrence[mid1][mid2] = self._co_occurrence[mid1].get(mid2, 0) + 1

        # LRU 淘汰：超出上限时移除最近最少访问的条目
        if len(self._co_occurrence) > self._co_occurrence_max:
            to_evict = self._co_occurrence_max // 4  # 淘汰 25%
            sorted_items = sorted(
                self._co_occurrence.items(),
                key=lambda x: self._last_access_time.get(x[0], 0),
            )
            for key, _ in sorted_items[:to_evict]:
                del self._co_occurrence[key]
            logger.debug(f"[CognitiveEngine] 共现表 LRU 淘汰: {to_evict} 条, 剩余 {len(self._co_occurrence)} 条")

    def _get_relevance_boost(self, memory_id: str, current_ids: List[str]) -> float:
        """获取关联度提升分数"""
        boost = 0.0

        # 1. 共现提升：与当前检索到的记忆共现频率
        for related_id in current_ids:
            if memory_id in self._co_occurrence.get(related_id, {}):
                boost += self._co_occurrence[related_id][memory_id] * 0.05

        # 2. 频率提升：高频访问的记忆权重更高
        freq = self._access_frequency.get(memory_id, 0)
        if freq > 0:
            boost += min(0.2, freq * 0.02)

        return min(0.5, boost)  # 最多提升0.5

    async def _ensure_memory_core_initialized(self):
        """确保内存核心已初始化"""
        if not self._memory_core_initialized:
            if self.memory_core is None:
                self.memory_core = await get_memory_core()
            await self.memory_core.initialize()
            self._memory_core_initialized = True

    def _extract_topics(self, text: str) -> List[str]:
        """提取对话主题"""
        text = text.lower()
        topics = []

        for topic, keywords in self.topic_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    topics.append(topic)
                    break

        return topics

    def extract_topics(self, text: str) -> List[str]:
        """公开方法：提取对话主题（V4.1.11）"""
        return self._extract_topics(text)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词 — 预定义词典 + jieba 通用分词 + 正则模式"""
        keywords = []

        for _topic, topic_keywords in self.topic_keywords.items():
            for keyword in topic_keywords:
                if keyword in text:
                    keywords.append(keyword)

        for _category, triggers in self.memory_triggers.items():
            for trigger in triggers:
                if trigger in text:
                    keywords.append(trigger)

        for keyword in self.anchor_keywords:
            if keyword in text:
                keywords.append(keyword)

        my_pattern = self.keyword_extraction_patterns.get("my_patterns", r"我的(\w{2,})")
        what_pattern = self.keyword_extraction_patterns.get("what_patterns", r"(\w{2,})是什么")
        when_pattern = self.keyword_extraction_patterns.get("when_patterns", r"(\w{2,})的时候")

        my_patterns = re.findall(my_pattern, text)
        keywords.extend(my_patterns)
        what_patterns = re.findall(what_pattern, text)
        keywords.extend(what_patterns)
        when_patterns = re.findall(when_pattern, text)
        keywords.extend(when_patterns)

        # 5. jieba 通用分词作为补充（解决新词、专有名词不在预定义词典的问题）
        try:
            import jieba

            jieba_words = jieba.lcut(text)
            for word in jieba_words:
                word = word.strip()
                if len(word) >= 2 and word not in keywords:
                    keywords.append(word)
        except Exception:
            pass

        return list(set(keywords))

    def _is_meaningful(self, text: str) -> bool:
        """判断内容是否有意义（值得记忆）

        Args:
            text: 对话内容

        Returns:
            是否有意义
        """
        text = text.strip()

        # 检查忽略模式
        for pattern in self.ignore_patterns:
            if re.match(pattern, text):
                return False

        # 太短的内容忽略
        return len(text) >= 4

    async def _get_embedding_similarity(self, text: str, memory_content: str) -> float:
        """计算语义相似度（使用embedding）

        Args:
            text: 当前输入文本
            memory_content: 记忆内容

        Returns:
            相似度分数 0-1
        """
        if not self.embedding_client:
            return 0.0

        try:
            text_hash = self._stable_hash(text)
            memory_hash = self._stable_hash(memory_content)

            if text_hash not in self._embedding_cache:
                embedding = await self.embedding_client.get_embedding(text)
                if embedding:
                    self._embedding_cache[text_hash] = embedding
            text_emb = self._embedding_cache.get(text_hash)
            if not text_emb:
                return 0.0

            if memory_hash not in self._embedding_cache:
                embedding = await self.embedding_client.get_embedding(memory_content)
                if embedding:
                    self._embedding_cache[memory_hash] = embedding
            memory_emb = self._embedding_cache.get(memory_hash)
            if not memory_emb:
                return 0.0

            # 计算余弦相似度
            return self._cosine_similarity(text_emb, memory_emb)

        except Exception as e:
            logger.debug(f"[认知引擎] 语义相似度计算失败: {e}")
            return 0.0

    @staticmethod
    def _stable_hash(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    async def _calculate_relevance(
        self,
        memory: MemoryItem,
        current_topics: List[str],
        keywords: List[str],
        current_input: str = "",
    ) -> float:
        """计算记忆与当前对话的相关度

        Args:
            memory: 记忆
            current_topics: 当前话题
            keywords: 关键词
            current_input: 当前用户输入（用于语义相似度）

        Returns:
            相关度分数 0-1
        """
        score = 0.0

        # 1. 重要性权重
        score += memory.priority * 0.3

        # 2. 关键词匹配
        for keyword in keywords:
            if keyword.lower() in memory.content.lower():
                score += 0.2
                break

        # 3. 话题匹配
        for topic in current_topics:
            if topic in memory.tags:
                score += 0.3
                break

        # 4. 时间衰减（按日期边界：今天 > 昨天 > 本周 > 更长）
        try:
            memory_time = datetime.fromisoformat(memory.created_at)
            time_weight = time_decay_by_boundary(memory_time)
            score += time_weight * 0.15
        except:
            score += 0.1

        # 5. 语义相似度（使用embedding）
        if current_input and self.embedding_client:
            semantic_score = await self._get_embedding_similarity(current_input, memory.content)
            score += semantic_score * 0.35  # 35%权重给语义相似度

        return min(1.0, score)

    async def retrieve(
        self,
        user_input: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        limit: int = 5,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> List[MemoryItem]:
        """检索相关记忆

        Args:
            user_input: 用户当前输入
            conversation_history: 对话历史（最近几条）
            limit: 返回数量限制
            user_id: 用户ID（用于过滤特定用户的记忆）
            group_id: 群ID（用于过滤特定群聊的记忆）

        Returns:
            相关记忆列表
        """
        if not user_input:
            return []

        # 确保内存核心已初始化
        await self._ensure_memory_core_initialized()

        # 1. 提取当前话题和关键词
        current_topics = self._extract_topics(user_input)
        keywords = self._extract_keywords(user_input)

        # 1.5 【新增】检测时间表达式，设置时间范围过滤
        temporal_range = parse_temporal(user_input)
        temporal_keywords = extract_temporal_keywords(user_input)
        if temporal_range:
            logger.info(
                f"[认知引擎] 检测到时间表达式: {temporal_range.label} "
                f"({temporal_range.start.strftime('%Y-%m-%d')} ~ {temporal_range.end.strftime('%Y-%m-%d')})"
            )
            # 将时间关键词加入搜索词
            for tk in temporal_keywords:
                if tk not in keywords:
                    keywords.append(tk)

        logger.info(f"[认知引擎] 当前话题: {current_topics}, 关键词: {keywords[:5]}")

        # 2. 查询记忆（全局检索，user_id/group_id 仅用于加权排序）
        # 使用 any_tag=True：任一关键词匹配即命中，避免过于限制
        if temporal_range:
            query = MemoryQuery(
                query=user_input,
                tags=current_topics + keywords,
                any_tag=True,
                levels=[
                    MemoryLevel.DIALOGUE,
                    MemoryLevel.SHORT_TERM,
                    MemoryLevel.LONG_TERM,
                    MemoryLevel.SEMANTIC,
                ],
                limit=limit * 3,
                start_time=temporal_range.start,
                end_time=temporal_range.end,
            )
        else:
            query = MemoryQuery(
                query=user_input,
                tags=current_topics + keywords,
                any_tag=True,
                limit=limit * 3,
            )

        all_memories = await self.memory_core.retrieve(query, user_id=user_id, group_id=group_id)

        # 2.5 【新增】专门搜索记忆锚点（优先级最高）
        # 如果用户输入包含个人信息相关的关键词，优先搜索记忆锚点
        user_input_lower = user_input.lower()

        # 从配置文件加载的关键词
        anchor_keywords = self.personal_query_keywords

        # 检查是否需要搜索记忆锚点
        need_anchor_search = any(kw in user_input_lower for kw in anchor_keywords)

        # 检查是否是询问个人信息的模式（从配置文件加载）
        is_personal_query = any(pattern in user_input_lower for pattern in self.personal_patterns)

        if need_anchor_search or is_personal_query:
            logger.info("[认知引擎] 检测到个人信息查询，优先搜索记忆锚点")

            # 搜索记忆锚点（全局检索，从配置文件加载的标签）
            for tag in self.anchor_tags:
                if tag in user_input_lower or tag in str(keywords):
                    anchor_query = MemoryQuery(
                        query="",
                        tags=[tag],
                        limit=limit * 2,
                    )
                    anchor_results = await self.memory_core.retrieve(anchor_query)
                    if anchor_results:
                        logger.info(f"[认知引擎] 找到 {len(anchor_results)} 条记忆锚点 (标签: {tag})")
                        return anchor_results[:limit]

            # 如果标签搜索没有找到，尝试内容搜索
            for keyword in keywords:
                if len(keyword) >= 2:  # 至少2个字符
                    content_query = MemoryQuery(
                        query=keyword,
                        limit=limit * 2,
                        user_id=user_id,
                    )
                    content_results = await self.memory_core.retrieve(content_query)
                    if content_results:
                        # 过滤出包含关键词的记忆
                        filtered_results = [m for m in content_results if keyword in m.content]
                        if filtered_results:
                            logger.info(f"[认知引擎] 找到 {len(filtered_results)} 条记忆 (内容匹配: {keyword})")
                            return filtered_results[:limit]

            # 关键词未命中锚点时，用语义检索兜底（"身体状况"→"心脏病"等语义关联）
            try:
                semantic_results = await self.memory_core.semantic_search(
                    query=user_input,
                    user_id=user_id,
                    limit=limit,
                    threshold=0.5,
                )
                if semantic_results:
                    logger.info(f"[认知引擎] 语义检索找到 {len(semantic_results)} 条记忆锚点")
                    return semantic_results[:limit]
            except Exception:
                pass

        # 3. 如果标签搜索无结果，尝试内容搜索（关键词直接匹配记忆内容）
        if not all_memories and (current_topics or keywords):
            search_terms = current_topics + keywords
            for term in search_terms:
                fallback_query = MemoryQuery(
                    query=term,
                    user_id=user_id,
                    group_id=group_id,
                    limit=limit * 2,
                    levels=[
                        MemoryLevel.DIALOGUE,
                        MemoryLevel.SHORT_TERM,
                        MemoryLevel.LONG_TERM,
                        MemoryLevel.SEMANTIC,
                    ]
                    if temporal_range
                    else None,
                    start_time=temporal_range.start if temporal_range else None,
                    end_time=temporal_range.end if temporal_range else None,
                )
                fallback_results = await self.memory_core.retrieve(fallback_query)
                if fallback_results:
                    all_memories.extend(fallback_results)
                    break  # 找到一个匹配就够了

        if not all_memories:
            return []

        # 3. 计算相关度并排序（加入关联度学习和 RRF 融合）
        scored_memories = []
        for memory in all_memories:
            relevance = await self._calculate_relevance(memory, current_topics, keywords, user_input)
            boost = self._get_relevance_boost(memory.id, [m.id for m in all_memories])
            relevance += boost
            if relevance > 0.1:
                scored_memories.append((memory, relevance))

        scored_memories.sort(key=lambda x: x[1], reverse=True)

        # 3.5 【新增】RRF 融合 — 对排序后的结果再用 RRF 进行多源融合精排
        if len(scored_memories) >= 3:
            try:
                from memory.rrf_fusion import get_rrf_fusion

                rrf = get_rrf_fusion()
                mems = [m for m, _ in scored_memories]

                query_vector = None
                if self.embedding_client:
                    try:
                        query_vector = await self.embedding_client.get_embedding(user_input)
                    except Exception:
                        pass

                context = {
                    "user_id": user_id or "",
                    "group_id": group_id or "",
                    "tags": current_topics + keywords,
                }

                fused = rrf.hybrid_search(
                    memories=mems,
                    query_text=user_input,
                    query_vector=query_vector,
                    context_weights=context,
                    keyword_weight=1.0,
                    vector_weight=1.0,
                    context_weight=0.3,
                )
                # 保留相关度分数，但用 RRF 重新排序
                rescored = []
                for mem, rrf_score in fused:
                    orig_score = next((s for m, s in scored_memories if m.id == mem.id), rrf_score)
                    combined = rrf_score * 0.6 + orig_score * 0.4
                    rescored.append((mem, combined))
                rescored.sort(key=lambda x: x[1], reverse=True)
                scored_memories = rescored
            except ImportError:
                pass

        # 4. MMR去重（最大边际相关性）- 减少相似记忆的重复
        results = self._mmr_deduplicate(scored_memories, limit)

        # 4.5 按创建时间倒序排列（统一群聊与私聊记忆的时间线）
        results.sort(key=lambda m: m.created_at if m.created_at else "", reverse=True)

        # 4.6 【新增】标注每条记忆的日期边界（今天/昨天/本周/更早）
        for memory in results:
            try:
                age_label = classify_memory_age(datetime.fromisoformat(memory.created_at))
                if not memory.metadata:
                    memory.metadata = {}
                memory.metadata["age_label"] = age_label
            except Exception:
                pass

        # 5. 记录共现关系（用于关联度学习）
        retrieved_ids = [m.id for m in results]
        if retrieved_ids:
            self._record_co_occurrence(retrieved_ids)
            self._last_retrieved_ids = retrieved_ids

        logger.info(f"[认知引擎] 检索到 {len(results)} 条相关记忆（MMR去重后）")
        if not results:
            logger.info(
                f"[认知引擎] 未找到相关记忆 (话题={current_topics}, 关键词={keywords[:5]}, 时间范围={'有' if temporal_range else '无'})"
            )

        return results

    def _mmr_deduplicate(
        self,
        scored_memories: List[tuple],
        limit: int,
        mmr_threshold: float = 0.7,
    ) -> List[MemoryItem]:
        """MMR（最大边际相关性）去重

        MMR在相关性和多样性之间取得平衡：
        - 选择相关度最高的项目
        - 同时惩罚与已选项目过于相似的项目

        Args:
            scored_memories: (MemoryItem, relevance_score) 列表
            limit: 返回数量限制
            mmr_threshold: 相似度阈值，超过则视为重复

        Returns:
            去重后的记忆列表
        """
        if len(scored_memories) <= limit:
            return [m for m, _ in scored_memories]

        selected = []
        remaining = list(scored_memories)

        while len(selected) < limit and remaining:
            best_score = -1
            best_idx = 0

            for i, (memory, relevance) in enumerate(remaining):
                # 计算与已选项目的最大相似度
                max_similarity = 0.0
                for selected_mem in selected:
                    similarity = self._calculate_similarity(memory, selected_mem)
                    max_similarity = max(max_similarity, similarity)

                # MMR公式: score = relevance - λ * similarity
                # λ = 0.5 表示在相关性和多样性之间平衡
                mmr_score = relevance - 0.5 * max_similarity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected_item = remaining[best_idx][0]
            selected.append(selected_item)
            remaining.pop(best_idx)

        return selected

    def _calculate_similarity(self, mem1: MemoryItem, mem2: MemoryItem) -> float:
        """计算两条记忆的相似度（0-1之间）

        考虑因素：
        - 向量语义相似度（优先，最准确）
        - 内容相似度（文本重叠，fallback）
        - 标签重叠度
        - 用户/群组相关性
        """
        similarity = 0.0

        # 0. 向量语义相似度（优先：embedding 余弦距离最准确）
        vec_sim = self._calc_vector_similarity(mem1, mem2)
        if vec_sim > 0:
            return min(1.0, vec_sim * 0.5 + self._calc_jaccard_similarity(mem1, mem2) * 0.3)

        # 1. 内容相似度（Jaccard 词重叠）
        similarity += self._calc_jaccard_similarity(mem1, mem2) * 0.4

        # 2. 标签重叠度
        if mem1.tags and mem2.tags:
            tag_overlap = len(set(mem1.tags) & set(mem2.tags)) / max(len(mem1.tags), len(mem2.tags))
            similarity += tag_overlap * 0.3

        # 3. 用户/群组相关性
        if mem1.user_id and mem2.user_id and mem1.user_id == mem2.user_id:
            similarity += 0.2
        if mem1.group_id and mem2.group_id and mem1.group_id == mem2.group_id:
            similarity += 0.1

        return min(1.0, similarity)

    def _calc_jaccard_similarity(self, mem1: MemoryItem, mem2: MemoryItem) -> float:
        words1 = set(mem1.content.lower().split())
        words2 = set(mem2.content.lower().split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _calc_vector_similarity(self, mem1: MemoryItem, mem2: MemoryItem) -> float:
        if mem1.vector and mem2.vector:
            return self._cosine_similarity(mem1.vector, mem2.vector)
        mem1_hash = self._stable_hash(mem1.content)
        mem2_hash = self._stable_hash(mem2.content)
        vec1 = self._embedding_cache.get(mem1_hash)
        vec2 = self._embedding_cache.get(mem2_hash)
        if vec1 and vec2:
            return self._cosine_similarity(vec1, vec2)
        return -1.0

    async def build_context(
        self,
        user_input: str,
        conversation_history: List[Dict] = None,
        limit: int = 5,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> str:
        """构建记忆上下文文本

        Args:
            user_input: 用户当前输入
            conversation_history: 对话历史
            limit: 记忆数量限制
            user_id: 用户ID（用于过滤特定用户的记忆）
            group_id: 群ID（用于过滤特定群聊的记忆）

        Returns:
            格式化的记忆上下文文本
        """
        # 确保内存核心已初始化
        await self._ensure_memory_core_initialized()

        memories = await self.retrieve(user_input, conversation_history, limit, user_id, group_id)

        if not memories:
            return ""

        context_display = self._config.get("context_display", {})
        header_text = context_display.get("header", "【弥娅记住的事情】")
        footer_text = context_display.get("footer", "（这些都是之前对话中记住的重要事情，与当前对话可能相关）")

        lines = [header_text]
        lines.append("")

        # 检测是否为时间范围查询，格式化不同
        from memory.temporal_parser import parse_temporal

        has_temporal = parse_temporal(user_input) is not None

        if has_temporal:
            # 时间范围查询 → 按天分组，显示时间线
            by_date = {}
            for memory in memories:
                date_str = memory.created_at[:10]  # YYYY-MM-DD
                time_str = memory.created_at[11:16] if len(memory.created_at) > 10 else ""
                age_label = (memory.metadata or {}).get("age_label", "")
                if date_str not in by_date:
                    by_date[date_str] = []
                entry = f"[{time_str}]" if time_str else ""
                role_tag = ""
                if memory.role == "user":
                    role_tag = f"{getattr(memory, 'sender_name', '') or '用户'}说: "
                elif memory.role == "assistant":
                    role_tag = "弥娅说: "
                by_date[date_str].append(f"    {entry} {role_tag}{memory.content[:120]}")

            for date_str, entries in sorted(by_date.items()):
                lines.append(f"【{date_str}】")
                for entry in entries[:8]:  # 每天最多8条
                    lines.append(entry)
                lines.append("")
        else:
            # 普通查询 → 按时序展示，使用日期边界标签
            for memory in memories:
                age_label = (memory.metadata or {}).get("age_label", "")
                time_str = memory.created_at[11:16] if len(memory.created_at) > 10 else ""
                date_label = (
                    age_label if age_label else (memory.created_at[:10] if len(memory.created_at) >= 10 else "")
                )
                ts = f"[{date_label} {time_str}]" if date_label else ""
                content_preview = memory.content.replace("\n", " ")[:150]
                lines.append(f"- {ts} {content_preview}")

        lines.append("")
        lines.append(footer_text)

        return "\n".join(lines)

    async def search_unified(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """统一记忆检索 — 融合 MiyaMemoryCore

        自动选择最优检索路径：MiyaMemoryCore (JSON + SQLite FTS5)
        结果去重合并后按相关度排序返回。
        """
        results: List[MemoryItem] = []

        core_results = await self.retrieve(query_text, user_id=user_id, group_id=group_id, limit=limit * 2)
        results.extend(core_results)

        if not results:
            return []

        seen_ids = set()
        deduped = []
        for mem in results:
            mid = getattr(mem, "id", "") or getattr(mem, "memory_id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                deduped.append(mem)

        deduped.sort(
            key=lambda m: (
                getattr(m, "priority", 0) or 0,
                getattr(m, "created_at", "") or "",
            ),
            reverse=True,
        )

        return deduped[:limit]

    async def should_remember(self, user_input: str, ai_response: str) -> tuple[bool, str, float]:
        """判断是否应该记忆这段对话

        Args:
            user_input: 用户输入
            ai_response: AI回复

        Returns:
            (是否记忆, 记忆内容, 重要程度)
        """
        combined = user_input + " " + ai_response

        # 1. 检查是否有意义
        if not self._is_meaningful(user_input):
            return False, "", 0.0

        # 2. 检查是否包含触发词
        importance = 0.3  # 基础重要性

        for category, triggers in self.memory_triggers.items():
            for trigger in triggers:
                if trigger in combined:
                    if category == "important_info":
                        importance = 0.9
                    elif category == "commitment":
                        importance = 0.8
                    elif category == "emotion_change":
                        importance = 0.7
                    elif category == "habit":
                        importance = 0.6
                    break

        # 3. 如果有关键词匹配，提高重要性
        keywords = self._extract_keywords(user_input)
        if len(keywords) >= 2:
            importance = min(1.0, importance + 0.2)

        # 4. 提取需要记忆的内容
        memory_content = self._extract_memory_fact(user_input, ai_response)

        if not memory_content:
            return False, "", 0.0

        return True, memory_content, importance

    def _extract_memory_fact(self, user_input: str, ai_response: str) -> str:
        """提取需要记忆的事实

        Args:
            user_input: 用户输入
            ai_response: AI回复

        Returns:
            记忆内容
        """
        # 提取用户陈述的事实
        for trigger in self.memory_triggers.get("important_info", []):
            if trigger in user_input:
                idx = user_input.find(trigger)
                fact = user_input[idx:].strip()
                for end in ["。", "？", "！", "\n"]:
                    if end in fact:
                        fact = fact[: fact.find(end)]
                if len(fact) > 3:
                    return fact

        for trigger in self.memory_triggers.get("habit", []):
            if trigger in user_input:
                idx = user_input.find(trigger)
                fact = user_input[idx:].strip()
                for end in ["。", "？", "！", "\n"]:
                    if end in fact:
                        fact = fact[: fact.find(end)]
                if len(fact) > 3:
                    return fact

        # 如果没有匹配，返回用户输入作为潜在记忆内容
        if len(user_input) > 5:
            return user_input[:100]  # 限制长度

        return ""


# 单例实例
_cognitive_engine: Optional[CognitiveEngine] = None


async def _create_default_embedding_client():
    """从模型配置自动创建 embedding 客户端"""
    try:
        json_path = Path(__file__).parent.parent / "config" / "multi_model_config.json"
        if not json_path.exists():
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            model_config = json.load(f)
        emb_config = model_config.get("embedding_config", {})
        models = model_config.get("models", {})

        from core.embedding_client import EmbeddingClient, EmbeddingProvider

        provider_map = {
            "openai": EmbeddingProvider.OPENAI,
            "siliconflow": EmbeddingProvider.SILICONFLOW,
            "deepseek": EmbeddingProvider.DEEPSEEK,
        }

        primary = emb_config.get("primary", "")
        fallback = emb_config.get("fallback", "")

        for name in [primary, fallback]:
            if not name or name not in models:
                continue
            info = models[name]
            provider = provider_map.get(info.get("provider", "openai"), EmbeddingProvider.OPENAI)
            api_key = info.get("api_key", "")
            if not api_key and info.get("env_key"):
                import os

                api_key = os.getenv(info["env_key"], "")
            client = EmbeddingClient(
                provider=provider,
                model=info["name"],
                api_key=api_key,
                base_url=info.get("base_url", ""),
            )
            await client.initialize()
            return client
    except Exception:
        pass
    return None


def get_cognitive_engine() -> CognitiveEngine:
    """获取认知引擎单例实例"""
    global _cognitive_engine
    if _cognitive_engine is None:
        _cognitive_engine = CognitiveEngine(embedding_client=None)
    return _cognitive_engine


async def get_cognitive_engine_async() -> CognitiveEngine:
    """获取认知引擎单例实例（异步初始化 embedding_client）"""
    global _cognitive_engine
    if _cognitive_engine is None:
        embedding_client = await _create_default_embedding_client()
        _cognitive_engine = CognitiveEngine(embedding_client=embedding_client)
    elif _cognitive_engine.embedding_client is None:
        _cognitive_engine.embedding_client = await _create_default_embedding_client()
    return _cognitive_engine
