"""
弥娅记忆增强系统 (Memory Enhancer)

功能：
1. 记忆关联挖掘 - 自动发现记忆间的关联，建立记忆网络
2. 情感记忆强化 - 强化情绪敏感度，记住情感交互
3. 记忆遗忘机制 - 模拟人类遗忘曲线，动态调整记忆权重
4. 长期记忆精炼 - 定期合并相似记忆，去重提纯
5. 记忆可视化 - 提供记忆网络图谱数据

作者: MIYA
日期: 2026-04-28
"""

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ==================== 情感类型定义 ====================


class EmotionType(Enum):
    """情感类型"""

    JOY = "joy"  # 开心
    SADNESS = "sadness"  # 难过
    ANGER = "anger"  # 生气
    FEAR = "fear"  # 害怕
    SURPRISE = "surprise"  # 惊讶
    DISGUST = "disgust"  # 厌恶
    LOVE = "love"  # 喜欢
    ANTICIPATION = "anticipation"  # 期盼
    NEUTRAL = "neutral"  # 中性


EMOTION_KEYWORDS = {
    EmotionType.JOY: [
        "开心",
        "快乐",
        "高兴",
        "幸福",
        "太好了",
        "棒",
        "喜欢",
        "么么哒",
        "爱你",
        "哈哈",
        "笑",
    ],
    EmotionType.SADNESS: [
        "难过",
        "伤心",
        "哭",
        "郁闷",
        "难过",
        "不舒服",
        "烦",
        "沮丧",
        "失落",
        "委屈",
    ],
    EmotionType.ANGER: [
        "生气",
        "气",
        "愤怒",
        "讨厌",
        "烦",
        "讨厌",
        "可恶",
        "过分",
        "怒",
    ],
    EmotionType.FEAR: ["害怕", "担心", "紧张", "焦虑", "不安", "慌", "怕"],
    EmotionType.SURPRISE: ["惊讶", "意外", "震惊", "没想到", "哇", "居然", "竟然"],
    EmotionType.DISGUST: ["恶心", "讨厌", "无聊", "服了", "无语", "嫌弃"],
    EmotionType.LOVE: ["爱", "喜欢", "心动", "甜蜜", "幸福", "么么", "亲亲", "抱抱"],
    EmotionType.ANTICIPATION: ["期待", "希望", "想要", "想要", "希望", "憧憬", "盼望"],
}


# ==================== 数据结构 ====================


@dataclass
class MemoryLink:
    """记忆关联"""

    source_id: str
    target_id: str
    link_type: str  # "semantic", "temporal", "emotion", "entity"
    strength: float = 0.5  # 关联强度 0-1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EmotionScore:
    """情感评分"""

    primary: EmotionType = EmotionType.NEUTRAL
    intensity: float = 0.5  # 0-1
    keywords_found: List[str] = field(default_factory=list)


@dataclass
class MemoryWeight:
    """记忆权重（用于遗忘机制）"""

    base_weight: float = 0.5
    decay_factor: float = 1.0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    emotional_boost: float = 0.0  # 情感增强


# ==================== 记忆增强器 ====================


class MemoryEnhancer:
    """
    记忆增强器

    为 MiyaMemoryCore 提供增强功能：
    - 关联挖掘
    - 情感分析
    - 遗忘模拟
    - 记忆精炼
    """

    def __init__(self, data_dir: str = None):
        from memory import DEFAULT_MEMORY_DIR

        if data_dir is None:
            data_dir = DEFAULT_MEMORY_DIR
        self.data_dir = data_dir
        self._link_file = f"{data_dir}/memory_links.json"
        self._weight_file = f"{data_dir}/memory_weights.json"
        self._links: Dict[str, List[MemoryLink]] = defaultdict(list)
        self._weights: Dict[str, MemoryWeight] = {}
        self._initialized = False

        self._load_config()

    def _load_config(self):
        """从配置文件加载增强器参数"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "memory_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                enh_cfg = cfg.get("enhancer", {})
                self.decay_rate = enh_cfg.get("decay_rate", 0.05)
                self.emotion_boost_threshold = enh_cfg.get("emotion_boost_threshold", 0.7)
                self.similarity_threshold = enh_cfg.get("similarity_threshold", 0.85)
                self.refine_interval = enh_cfg.get("refine_interval", 86400)
                return
        except Exception:
            pass
        self.decay_rate = 0.05
        self.emotion_boost_threshold = 0.7
        self.similarity_threshold = 0.85
        self.refine_interval = 86400

    async def initialize(self):
        """初始化"""
        os.makedirs(self.data_dir, exist_ok=True)

        await self._load_links()
        await self._load_weights()

        self._initialized = True
        logger.info("[MemoryEnhancer] 记忆增强器初始化完成")

    # ==================== 关联挖掘 ====================

    async def _load_links(self):
        """加载记忆关联"""
        try:
            if os.path.exists(self._link_file):
                with open(self._link_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for source_id, links in data.items():
                        self._links[source_id] = [
                            MemoryLink(
                                source_id=l["source_id"],
                                target_id=l["target_id"],
                                link_type=l["link_type"],
                                strength=l.get("strength", 0.5),
                                created_at=l.get("created_at", datetime.now().isoformat()),
                            )
                            for l in links
                        ]
                logger.info(f"[MemoryEnhancer] 加载了 {len(self._links)} 个记忆关联")
        except Exception as e:
            logger.warning(f"[MemoryEnhancer] 加载关联失败: {e}")

    async def _save_links(self):
        """保存记忆关联"""
        try:
            data = {
                source_id: [
                    {
                        "source_id": link.source_id,
                        "target_id": link.target_id,
                        "link_type": link.link_type,
                        "strength": link.strength,
                        "created_at": link.created_at,
                    }
                    for link in links
                ]
                for source_id, links in self._links.items()
            }
            with open(self._link_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[MemoryEnhancer] 保存关联失败: {e}")

    async def analyze_and_link(
        self, memory_item: "MemoryItem", existing_memories: List["MemoryItem"]
    ) -> List[MemoryLink]:
        """分析记忆并建立关联"""
        new_links = []

        for existing in existing_memories:
            if existing.id == memory_item.id:
                continue

            # 1. 语义关联 - 检查内容相似度
            semantic_score = self._calc_semantic_similarity(memory_item.content, existing.content)
            if semantic_score > 0.6:
                link = MemoryLink(
                    source_id=memory_item.id,
                    target_id=existing.id,
                    link_type="semantic",
                    strength=semantic_score,
                )
                new_links.append(link)

            # 2. 实体关联 - 检查共同实体
            entities1 = self._extract_entities(memory_item.content)
            entities2 = self._extract_entities(existing.content)
            common_entities = entities1 & entities2
            if len(common_entities) >= 2:
                link = MemoryLink(
                    source_id=memory_item.id,
                    target_id=existing.id,
                    link_type="entity",
                    strength=min(0.8, 0.3 + 0.1 * len(common_entities)),
                )
                new_links.append(link)

            # 3. 时间关联 - 检查时间邻近
            if memory_item.source == "dialogue" and existing.source == "dialogue":
                time_diff = abs(
                    self._parse_time(memory_item.created_at) - self._parse_time(existing.created_at)
                ).total_seconds()
                if time_diff < 3600:  # 1小时内
                    link = MemoryLink(
                        source_id=memory_item.id,
                        target_id=existing.id,
                        link_type="temporal",
                        strength=max(0.3, 0.6 - time_diff / 3600),
                    )
                    new_links.append(link)

        # 4. 情感关联 - 检查情感关联
        emotion1 = self._analyze_emotion(memory_item.content)
        emotion2 = self._analyze_emotion(existing.content)
        if emotion1.primary == emotion2.primary and emotion1.intensity > 0.5:
            link = MemoryLink(
                source_id=memory_item.id,
                target_id=existing.id,
                link_type="emotion",
                strength=0.7,
            )
            new_links.append(link)

        # 保存新关联
        for link in new_links:
            self._links[link.source_id].append(link)

        if new_links:
            await self._save_links()

        return new_links

    def _calc_semantic_similarity(self, text1: str, text2: str) -> float:
        """计算语义相似度（简化版）"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        jaccard = len(intersection) / len(union) if union else 0

        # 考虑共同关键词
        keywords = ["喜欢", "讨厌", "希望", "害怕", "爱", "生气", "开心", "难过"]
        keyword_match = sum(1 for k in keywords if k in text1 and k in text2)
        keyword_boost = min(0.3, keyword_match * 0.1)

        return min(1.0, jaccard + keyword_boost)

    def _extract_entities(self, text: str) -> Set[str]:
        """提取实体（简化版）"""
        entities = set()

        # 人称提取
        persons = ["我", "你", "他", "她", "我们", "你们", "他们", "佳", "弥娅"]
        for p in persons:
            if p in text:
                entities.add(p)

        # 关键词提取
        important_words = ["喜欢", "讨厌", "想", "要", "去", "吃", "做", "买"]
        for word in text:
            if word in important_words:
                entities.add(word)

        return entities

    def _parse_time(self, time_str: str) -> datetime:
        """解析时间"""
        try:
            return datetime.fromisoformat(time_str)
        except:
            return datetime.now()

    def get_related_memories(self, memory_id: str) -> List[Dict]:
        """获取关联记忆"""
        links = self._links.get(memory_id, [])
        result = []
        for link in links:
            result.append(
                {
                    "memory_id": link.target_id,
                    "link_type": link.link_type,
                    "strength": link.strength,
                }
            )
        return result

    # ==================== 情感记忆强化 ====================

    def _analyze_emotion(self, text: str) -> EmotionScore:
        """分析文本情感"""
        found_emotions = []

        for emotion_type, keywords in EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    found_emotions.append((emotion_type, len(keyword)))

        if not found_emotions:
            return EmotionScore()

        # 按匹配长度排序
        found_emotions.sort(key=lambda x: x[1], reverse=True)
        primary = found_emotions[0][0]

        # 计算强度
        intensity = min(1.0, 0.3 + len(found_emotions) * 0.15)

        return EmotionScore(
            primary=primary,
            intensity=intensity,
            keywords_found=[e[0].value for e in found_emotions],
        )

    async def enhance_emotion_memory(self, memory_item: "MemoryItem") -> "MemoryItem":
        """增强情感记忆"""
        emotion = self._analyze_emotion(memory_item.content)

        if emotion.intensity > self.emotion_boost_threshold:
            memory_item.metadata["emotion"] = {
                "type": emotion.primary.value,
                "intensity": emotion.intensity,
                "keywords": emotion.keywords_found,
            }

            # 情感强化 - 提高优先级
            memory_item.priority = min(1.0, memory_item.priority + 0.2)

            # 更新权重
            weight = self._weights.get(memory_item.id, MemoryWeight())
            weight.emotional_boost = emotion.intensity * 0.3
            self._weights[memory_item.id] = weight
            await self._save_weights()

            logger.info(f"[MemoryEnhancer] 情感强化: {memory_item.id} - {emotion.primary.value}")

        return memory_item

    def get_emotion_memories(self, user_id: str, emotion_type: Optional[EmotionType] = None) -> List[Dict]:
        """获取情感记忆"""
        result = []

        memory_ids_with_emotion = [mid for mid, w in self._weights.items() if w.emotional_boost > 0]

        for mid in memory_ids_with_emotion:
            weight = self._weights.get(mid)
            if not weight:
                continue
            result.append(
                {
                    "memory_id": mid,
                    "emotional_boost": weight.emotional_boost,
                    "last_accessed": weight.last_accessed,
                    "base_weight": weight.base_weight,
                }
            )

        result.sort(key=lambda x: x["emotional_boost"], reverse=True)
        return result

    # ==================== 记忆遗忘机制 ====================

    async def _load_weights(self):
        """加载记忆权重"""
        try:
            if os.path.exists(self._weight_file):
                with open(self._weight_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for mem_id, w in data.items():
                        self._weights[mem_id] = MemoryWeight(
                            base_weight=w.get("base_weight", 0.5),
                            decay_factor=w.get("decay_factor", 1.0),
                            last_accessed=w.get("last_accessed", datetime.now().isoformat()),
                            emotional_boost=w.get("emotional_boost", 0.0),
                        )
                logger.info(f"[MemoryEnhancer] 加载了 {len(self._weights)} 个记忆权重")
        except Exception as e:
            logger.warning(f"[MemoryEnhancer] 加载权重失败: {e}")

    async def _save_weights(self):
        """保存记忆权重"""
        try:
            data = {
                mem_id: {
                    "base_weight": w.base_weight,
                    "decay_factor": w.decay_factor,
                    "last_accessed": w.last_accessed,
                    "emotional_boost": w.emotional_boost,
                }
                for mem_id, w in self._weights.items()
            }
            with open(self._weight_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[MemoryEnhancer] 保存权重失败: {e}")

    def calculate_decay_weight(self, memory_id: str, created_at: str) -> float:
        """计算衰减后的记忆权重"""
        weight = self._weights.get(memory_id, MemoryWeight())

        created_time = self._parse_time(created_at)
        days_since = (datetime.now() - created_time).total_seconds() / 86400

        # 艾宾浩斯遗忘曲线模拟
        decay = weight.decay_factor * (1 - self.decay_rate * days_since)

        # 应用情感boost
        effective_weight = decay + weight.emotional_boost

        return max(0.1, min(1.0, effective_weight))

    async def on_memory_accessed(self, memory_id: str):
        """记忆被访问时的处理"""
        if memory_id in self._weights:
            self._weights[memory_id].last_accessed = datetime.now().isoformat()
            # 访问强化 - 稍微增加权重
            self._weights[memory_id].decay_factor = min(1.5, self._weights[memory_id].decay_factor + 0.05)
            await self._save_weights()

    def get_fading_memories(self, threshold: float = 0.3) -> List[str]:
        """获取即将遗忘的记忆"""
        fading = []
        for mem_id, weight in self._weights.items():
            if weight.decay_factor < threshold:
                fading.append(mem_id)
        return fading

    # ==================== 长期记忆精炼 ====================

    async def refine_long_term_memories(self, memories: List["MemoryItem"]) -> List[str]:
        """精炼长期记忆 - 合并相似记忆（增强版：集成 QualityScorer 三维去重）"""
        if len(memories) < 2:
            return []

        merged_ids = []
        to_remove = set()

        try:
            from memory.quality_scorer import get_quality_scorer

            quality = get_quality_scorer()
        except ImportError:
            quality = None

        user_memories: Dict[str, List[MemoryItem]] = defaultdict(list)
        for mem in memories:
            if mem.level.value == "long_term":
                user_memories[mem.user_id].append(mem)

        for _user_id, user_mems in user_memories.items():
            for i, mem1 in enumerate(user_mems):
                if mem1.id in to_remove:
                    continue

                for _j, mem2 in enumerate(user_mems[i + 1 :]):
                    if mem2.id in to_remove:
                        continue

                    if quality:
                        # 用 QualityScorer 三维度检测冗余
                        redundant = quality.detect_redundancy(
                            mem1,
                            [mem2],
                            text_threshold=self.similarity_threshold,
                        )
                        is_redundant = len(redundant) > 0
                    else:
                        # 回退到简单词重叠判断
                        similarity = self._calc_semantic_similarity(mem1.content, mem2.content)
                        is_redundant = similarity >= self.similarity_threshold

                    if is_redundant:
                        if mem1.created_at > mem2.created_at:
                            merged_ids.append(f"{mem1.id} <- {mem2.id}")
                            to_remove.add(mem2.id)
                        else:
                            merged_ids.append(f"{mem2.id} <- {mem1.id}")
                            to_remove.add(mem1.id)

        if merged_ids:
            logger.info(f"[MemoryEnhancer] 精炼了 {len(merged_ids)} 组相似记忆")

        return list(to_remove)

    # ==================== 记忆可视化 ====================

    def get_memory_network(self, user_id: str, limit: int = 50) -> Dict:
        """获取记忆网络数据（用于可视化）"""
        nodes = []
        edges = []

        visited = set()
        link_count = 0

        # 遍历关联构建网络
        for source_id, links in self._links.items():
            for link in links[:5]:  # 限制每个记忆的关联数
                if link_count >= limit:
                    break

                if source_id not in visited:
                    nodes.append(
                        {
                            "id": source_id,
                            "label": f"记忆_{source_id[:8]}",
                            "type": link.link_type,
                        }
                    )
                    visited.add(source_id)

                edges.append(
                    {
                        "source": link.source_id,
                        "target": link.target_id,
                        "type": link.link_type,
                        "strength": link.strength,
                    }
                )
                link_count += 1

            if link_count >= limit:
                break

        return {
            "nodes": nodes,
            "edges": edges,
            "total_links": len(edges),
            "total_nodes": len(nodes),
        }

    def get_memory_stats(self) -> Dict:
        """获取记忆统计"""
        return {
            "total_links": sum(len(links) for links in self._links.values()),
            "total_weights": len(self._weights),
            "link_types": self._count_link_types(),
            "emotion_distribution": self._get_emotion_distribution(),
        }

    def _count_link_types(self) -> Dict[str, int]:
        """统计关联类型"""
        counts = defaultdict(int)
        for links in self._links.values():
            for link in links:
                counts[link.link_type] += 1
        return dict(counts)

    def _get_emotion_distribution(self) -> Dict[str, int]:
        """获取情感分布"""
        emotion_counts = defaultdict(int)
        for weight in self._weights.values():
            if weight.emotional_boost > 0.5:
                emotion_counts["high_emotion"] += 1
            elif weight.emotional_boost > 0.2:
                emotion_counts["medium_emotion"] += 1
            else:
                emotion_counts["low_emotion"] += 1
        return dict(emotion_counts)


# 全局实例
_enhancer: Optional[MemoryEnhancer] = None


async def get_memory_enhancer(data_dir: str = "data/memory") -> MemoryEnhancer:
    """获取记忆增强器"""
    global _enhancer
    if _enhancer is None:
        _enhancer = MemoryEnhancer(data_dir)
        await _enhancer.initialize()
    return _enhancer
