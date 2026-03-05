"""
记忆重要性评分器
基于多维度评分，决定记忆保留/压缩/遗忘
"""
from typing import Dict


class MemoryImportanceScorer:
    """记忆重要性评分器"""

    IMPORTANCE_WEIGHTS = {
        'emotion_strength': 0.4,
        'relationship_impact': 0.3,
        'access_frequency': 0.2,
        'recency': 0.1
    }

    def score_memory(self, memory: Dict) -> float:
        """计算记忆重要性分数（0-1）"""
        factors = {
            'emotion_strength': self._score_emotion(memory),
            'relationship_impact': self._score_relationship(memory),
            'access_frequency': self._score_frequency(memory),
            'recency': self._score_recency(memory)
        }

        total = sum(factors[k] * self.IMPORTANCE_WEIGHTS[k]
                    for k in self.IMPORTANCE_WEIGHTS)

        return round(total, 3)

    def _score_emotion(self, memory: Dict) -> float:
        """评估情绪强度"""
        emotion = memory.get('emotion', {})
        return emotion.get('intensity', 0.5)

    def _score_relationship(self, memory: Dict) -> float:
        """评估关系影响"""
        return memory.get('relationship_impact', 0.5)

    def _score_frequency(self, memory: Dict) -> float:
        """评估访问频率"""
        access_count = memory.get('access_count', 0)
        return min(access_count / 10.0, 1.0)

    def _score_recency(self, memory: Dict) -> float:
        """评估新鲜度"""
        import time
        timestamp = memory.get('timestamp', time.time())
        age_hours = (time.time() - timestamp) / 3600
        return max(0, 1.0 - age_hours / 168.0)  # 一周内为新鲜
