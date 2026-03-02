"""
记忆-情绪耦合回路
实现记忆与情绪的双向影响机制
"""
from typing import Dict, List, Optional
from datetime import datetime


class MemoryEmotion:
    """记忆-情绪耦合系统"""

    def __init__(self):
        self.coupling_matrix = {}
        self.emotional_tags = {}  # 记忆ID -> 情绪标签
        self.memory_influence = {}  # 记忆ID -> 情绪影响权重

    def link_emotion(self, memory_id: str, emotion: str, intensity: float) -> None:
        """
        将记忆与情绪关联

        Args:
            memory_id: 记忆ID
            emotion: 情绪类型
            intensity: 情绪强度 (0-1)
        """
        if memory_id not in self.emotional_tags:
            self.emotional_tags[memory_id] = []

        self.emotional_tags[memory_id].append({
            'emotion': emotion,
            'intensity': intensity,
            'timestamp': datetime.now()
        })

        # 更新耦合矩阵
        key = f"{memory_id}:{emotion}"
        self.coupling_matrix[key] = intensity

    def retrieve_emotion(self, memory_id: str) -> List[Dict]:
        """获取记忆关联的情绪"""
        return self.emotional_tags.get(memory_id, [])

    def influence_current_state(self, memory_id: str) -> Dict:
        """
        记忆对当前情绪状态的影响

        Returns:
            情绪影响向量
        """
        if memory_id not in self.emotional_tags:
            return {}

        emotions = self.emotional_tags[memory_id]
        influence = {}

        for emo in emotions:
            emotion_type = emo['emotion']
            intensity = emo['intensity']
            # 考虑时间衰减
            time_delta = (datetime.now() - emo['timestamp']).total_seconds()
            decay = max(0, 1 - time_delta / (30 * 24 * 3600))  # 30天衰减

            influence[emotion_type] = influence.get(emotion_type, 0) + intensity * decay

        return influence

    def reinforce_memory(self, memory_id: str, positive: bool = True) -> None:
        """
        强化或弱化记忆

        Args:
            memory_id: 记忆ID
            positive: True为强化，False为弱化
        """
        if memory_id not in self.memory_influence:
            self.memory_influence[memory_id] = 0.5

        if positive:
            self.memory_influence[memory_id] = min(1.0,
                self.memory_influence[memory_id] + 0.1)
        else:
            self.memory_influence[memory_id] = max(0.0,
                self.memory_influence[memory_id] - 0.1)

    def get_coupling_strength(self, memory_id: str, emotion: str) -> float:
        """获取记忆与情绪的耦合强度"""
        key = f"{memory_id}:{emotion}"
        return self.coupling_matrix.get(key, 0.0)
