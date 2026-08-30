"""
弥娅记忆质量评分与去重系统 (Quality Scorer)

功能：
1. 记忆质量评分 — 信息量、特异性、完整性三维度评估
2. 冗余检测 — 向量相似度 + 文本重叠 + 标签重合 三重检测
3. 自动合并 — 相似记忆智能合并，保留最佳版本
4. 记忆健康报告 — 定期评估记忆库质量

评分规则：
- 信息量 (informativeness): 包含多少有价值的信息
- 特异性 (specificity): 是否是具体的、独特的记忆
- 完整性 (completeness): 记忆描述是否完整
"""

import hashlib
import json
import logging
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from memory.models import MemoryItem, MemoryLevel

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    记忆质量评分器

    在记忆入库前/后评估质量，帮助：
    - 过滤低质量记忆
    - 标记高质量记忆提升检索优先级
    - 检测和合并冗余记忆
    """

    def __init__(self):
        self._config = self._load_config()
        self._stopwords = self._config.get(
            "stopwords",
            [
                "的",
                "了",
                "是",
                "在",
                "我",
                "你",
                "他",
                "她",
                "它",
                "有",
                "和",
                "就",
                "都",
                "也",
                "不",
                "没",
                "很",
                "这",
                "那",
                "什么",
                "怎么",
                "呢",
                "啊",
                "吧",
            ],
        )

    def _load_config(self) -> Dict[str, Any]:
        try:
            config_path = Path(__file__).parent.parent / "config" / "memory_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return cfg.get("quality_scorer", {})
        except Exception:
            pass
        return {}

    def score(self, memory: MemoryItem) -> Dict[str, float]:
        """
        计算记忆质量评分。

        Returns:
            {informativeness, specificity, completeness, overall, ...}
        """
        content = memory.content or ""
        tags = memory.tags or []

        informativeness = self._score_informativeness(content)
        specificity = self._score_specificity(content, tags)
        completeness = self._score_completeness(content)

        overall = informativeness * 0.35 + specificity * 0.35 + completeness * 0.30

        return {
            "informativeness": round(informativeness, 3),
            "specificity": round(specificity, 3),
            "completeness": round(completeness, 3),
            "overall": round(overall, 3),
            "quality_level": self._quality_level(overall),
        }

    def _score_informativeness(self, content: str) -> float:
        """
        评估信息量：
        - 长度适中 (20-200字理想)
        - 包含有意义的实词比例
        - 去除停用词后的有效信息密度
        """
        content = content.strip()
        if not content:
            return 0.0

        length = len(content)

        # 长度评分 (最优 20-200 字)
        if length < 5:
            length_score = length / 10.0
        elif length <= 200:
            length_score = 1.0 - abs(length - 60) / 140.0
        else:
            length_score = max(0.3, 1.0 - (length - 200) / 500.0)

        # 有效信息密度（非停用词比例）
        words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", content)
        if not words:
            return length_score * 0.3

        content_words = sum(
            len(re.findall(r"[\u4e00-\u9fff]", w)) if re.search(r"[\u4e00-\u9fff]", w) else 1 for w in words
        )
        density = content_words / max(1, length)
        density_score = min(1.0, density * 1.5)

        # 数字/专有名词信息量加成
        has_numbers = bool(re.search(r"\d+", content))
        has_entities = bool(re.search(r"[A-Z][a-z]+|[A-Z]{2,}", content))
        bonus = 0.1 if has_numbers else 0.0
        bonus += 0.1 if has_entities else 0.0

        return min(1.0, length_score * 0.5 + density_score * 0.4 + bonus)

    def _score_specificity(self, content: str, tags: List[str]) -> float:
        """
        评估特异性：
        - 是否是泛泛而谈 (低分)
        - 是否包含具体细节 (高分)
        - 是否有明确的时间/地点/人名
        """
        content = content.strip()
        if not content:
            return 0.0

        score = 0.3  # 基础分

        # 包含时间信息
        time_patterns = [
            r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}",
            r"[今天明天昨天上周下周本月下月今年去年]",
            r"\d{1,2}[点时:]",
            r"[早上中午下午晚上凌晨]",
        ]
        if any(re.search(p, content) for p in time_patterns):
            score += 0.2

        # 包含地点
        loc_patterns = [r"在[^\s]{2,10}", r"[去来到在][^\s]{2,8}(?:家|店|公司|学校|医院)"]
        if any(re.search(p, content) for p in loc_patterns):
            score += 0.15

        # 包含数字（年龄、金额、数量）
        if re.search(r"\d+", content):
            score += 0.1

        # 包含具体人名/组织
        if re.search(r"[A-Z][a-z]+|[A-Z]{2,}", content):
            score += 0.1

        # 标签特异性
        if tags:
            tag_specificity = sum(1 for t in tags if len(t) > 2 and t not in self._stopwords)
            score += min(0.15, tag_specificity * 0.03)

        # 泛化惩罚
        generic_phrases = [
            "好的",
            "明白了",
            "知道了",
            "可以的",
            "没问题",
            "是的",
            "对",
            "嗯",
            "行",
            "好",
            "可以",
        ]
        if any(content.strip().startswith(p) for p in generic_phrases) and len(content) < 20:
            score *= 0.3

        return min(1.0, max(0.0, score))

    def _score_completeness(self, content: str) -> float:
        """
        评估完整性：
        - 是否是完整的句子/陈述
        - 是否有明确的主谓宾结构
        - 是否包含上下文
        """
        content = content.strip()
        if not content:
            return 0.0

        score = 0.3

        # 有主语的标记
        subject_starters = [
            "我",
            "你",
            "他",
            "她",
            "我们",
            "他们",
            "弥娅",
            "佳",
            "这个",
            "那个",
            "这",
            "那",
        ]
        if any(content.startswith(s) for s in subject_starters):
            score += 0.2

        # 有动词标记
        verb_indicators = ["是", "有", "在", "要", "会", "能", "想", "觉得", "认为", "说", "做", "去"]
        if any(v in content for v in verb_indicators):
            score += 0.15

        # 完整句子标记 (有标点结尾)
        if re.search(r"[。！？\.!\?]$", content.strip()):
            score += 0.15

        # 上下文丰富度
        if len(content) >= 30:
            score += 0.1
        if len(content) >= 50:
            score += 0.1

        return min(1.0, score)

    def _quality_level(self, overall: float) -> str:
        if overall >= 0.8:
            return "excellent"
        if overall >= 0.6:
            return "good"
        if overall >= 0.4:
            return "fair"
        if overall >= 0.2:
            return "poor"
        return "junk"

    def filter_high_quality(self, memories: List[MemoryItem], min_quality: float = 0.4) -> List[MemoryItem]:
        """过滤出高质量记忆"""
        return [m for m in memories if self.score(m)["overall"] >= min_quality]

    def detect_redundancy(
        self,
        memory: MemoryItem,
        existing_memories: List[MemoryItem],
        text_threshold: float = 0.75,
        tag_threshold: float = 0.6,
        vec_threshold: float = 0.85,
    ) -> List[Tuple[MemoryItem, float, Dict[str, float]]]:
        """
        检测冗余记忆 — 三维度检测。

        Returns:
            [(重复记忆, 综合相似度, {text_sim, tag_sim, vec_sim}), ...]
        """
        redundant = []

        for existing in existing_memories:
            if existing.id == memory.id:
                continue

            text_sim = self._text_similarity(memory.content, existing.content)
            tag_sim = self._tag_similarity(memory.tags, existing.tags)

            vec_sim = 0.0
            if memory.vector and existing.vector:
                vec_sim = self._vector_similarity(memory.vector, existing.vector)

            # 综合判断 (向量最可靠，文本次之，标签辅助)
            if vec_sim > 0:
                combined = vec_sim * 0.5 + text_sim * 0.3 + tag_sim * 0.2
                if vec_sim >= vec_threshold or combined >= text_threshold:
                    detail = {
                        "text_sim": round(text_sim, 3),
                        "tag_sim": round(tag_sim, 3),
                        "vec_sim": round(vec_sim, 3),
                    }
                    redundant.append((existing, combined, detail))
            else:
                combined = text_sim * 0.65 + tag_sim * 0.35
                if combined >= text_threshold:
                    detail = {"text_sim": round(text_sim, 3), "tag_sim": round(tag_sim, 3), "vec_sim": 0.0}
                    redundant.append((existing, combined, detail))

        redundant.sort(key=lambda x: x[1], reverse=True)
        return redundant

    def _text_similarity(self, text1: str, text2: str) -> float:
        """文本相似度计算 (Jaccard + 子串匹配)"""
        words1 = set(re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text1.lower()))
        words2 = set(re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text2.lower()))

        union = words1 | words2
        if not union:
            return 0.0

        intersection = words1 & words2
        jaccard = len(intersection) / len(union)

        # 子串重叠
        short, long = (text1, text2) if len(text1) <= len(text2) else (text2, text1)
        if short and long:
            if short in long:
                jaccard = max(jaccard, len(short) / len(long) * 1.2)

        return min(1.0, jaccard)

    def _tag_similarity(self, tags1: List[str], tags2: List[str]) -> float:
        """标签相似度"""
        if not tags1 or not tags2:
            return 0.0
        s1 = set(tags1)
        s2 = set(tags2)
        intersection = s1 & s2
        union = s1 | s2
        return len(intersection) / len(union) if union else 0.0

    def _vector_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def select_best(self, memories: List[MemoryItem]) -> Optional[MemoryItem]:
        """
        从一组相似记忆中选出最佳版本。

        选择标准: 完整性 > 信息量 > 优先级 > 时间
        """
        if not memories:
            return None
        if len(memories) == 1:
            return memories[0]

        scored = []
        for mem in memories:
            quality = self.score(mem)
            score = (
                quality["completeness"] * 0.35
                + quality["informativeness"] * 0.25
                + mem.priority * 0.25
                + quality["specificity"] * 0.15
            )
            scored.append((mem, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def generate_health_report(self, memories: List[MemoryItem]) -> Dict[str, Any]:
        """
        生成记忆库健康报告。

        Returns:
            {total, avg_quality, quality_distribution, redundancy_count, ...}
        """
        if not memories:
            return {"total": 0, "message": "记忆库为空"}

        scores = [self.score(m) for m in memories]
        avg_overall = sum(s["overall"] for s in scores) / len(scores)

        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "junk": 0}
        for s in scores:
            distribution[s["quality_level"]] += 1

        # 检测群组内冗余
        redundancy_pairs = 0
        for i, m1 in enumerate(memories):
            for m2 in memories[i + 1 :]:
                if m1.id == m2.id:
                    continue
                if self._text_similarity(m1.content, m2.content) > 0.85:
                    redundancy_pairs += 1

        return {
            "total": len(memories),
            "avg_quality": round(avg_overall, 3),
            "quality_distribution": distribution,
            "redundancy_pairs": redundancy_pairs,
            "redundancy_rate": round(redundancy_pairs / max(1, len(memories)), 3),
            "timestamp": datetime.now().isoformat(),
        }


_global_quality_scorer: Optional[QualityScorer] = None


def get_quality_scorer() -> QualityScorer:
    global _global_quality_scorer
    if _global_quality_scorer is None:
        _global_quality_scorer = QualityScorer()
    return _global_quality_scorer
