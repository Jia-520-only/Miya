"""
记忆压缩器
基于终身学习论文的压缩策略，智能压缩低重要性记忆
"""
from typing import Dict, List, Optional
import json
import random


class MemoryCompressor:
    """记忆压缩器"""

    IMPORTANCE_WEIGHTS = {
        'emotion_strength': 0.4,
        'relationship_impact': 0.3,
        'access_frequency': 0.2,
        'recency': 0.1
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def should_compress(self, memory: Dict) -> bool:
        """判断是否应该压缩记忆"""
        factors = self._calculate_compress_factors(memory)
        compress_prob = self._calculate_compress_probability(factors)
        return random.random() < compress_prob

    async def compress_memories(self, memories: List[Dict]) -> Dict:
        """压缩多条记忆为摘要"""
        if not memories:
            return {'summary': '', 'key_points': []}

        # 简化实现：不调用LLM，直接提取关键信息
        key_points = [m.get('content', m.get('output', ''))[:100]
                     for m in memories[:5]]

        summary = f"包含{len(memories)}条记忆，关键点：" + "；".join(key_points)

        return {
            'summary': summary,
            'key_points': key_points,
            'source_count': len(memories)
        }

    def _calculate_compress_factors(self, memory: Dict) -> Dict:
        """计算压缩因子"""
        return {
            'age': self._calculate_age(memory),
            'access_count': memory.get('access_count', 0),
            'emotion_intensity': memory.get('emotion_intensity', 0.5),
            'relationship_impact': memory.get('relationship_impact', 0.5)
        }

    def _calculate_age(self, memory: Dict) -> float:
        """计算记忆年龄（天）"""
        import time
        timestamp = memory.get('timestamp', time.time())
        age_seconds = time.time() - timestamp
        age_days = age_seconds / 86400
        return min(age_days / 30.0, 1.0)  # 归一化到0-1

    def _calculate_compress_probability(self, factors: Dict) -> float:
        """计算压缩概率"""
        age = factors['age']
        access = 1.0 - factors['access_count'] / 10.0  # 访问越少，概率越高
        emotion = 1.0 - factors['emotion_intensity']

        prob = (age * 0.4 + access * 0.3 + emotion * 0.3)
        return min(max(prob, 0.0), 1.0)
