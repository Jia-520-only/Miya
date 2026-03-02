"""
情绪调控与染色
实现情绪状态管理和情绪染色机制
"""
from typing import Dict, List
import random


class Emotion:
    """情绪系统"""

    def __init__(self):
        # 基础情绪状态
        self.base_emotions = {
            'joy': 0.5,
            'sadness': 0.2,
            'anger': 0.1,
            'fear': 0.1,
            'surprise': 0.3,
            'disgust': 0.05
        }

        # 当前情绪状态（受染色影响）
        self.current_emotions = self.base_emotions.copy()

        # 情绪染色层
        self.coloring_layer = {}

        # 情绪历史
        self.emotion_history = []

    def get_dominant_emotion(self) -> str:
        """获取主导情绪"""
        return max(self.current_emotions, key=self.current_emotions.get)

    def apply_coloring(self, emotion_type: str, intensity: float) -> None:
        """
        应用情绪染色

        Args:
            emotion_type: 情绪类型
            intensity: 染色强度 (0-1)
        """
        if emotion_type in self.current_emotions:
            # 叠加染色效果
            self.current_emotions[emotion_type] = min(1.0,
                self.current_emotions[emotion_type] * (1 + intensity))

            # 更新染色层
            self.coloring_layer[emotion_type] = intensity

            # 记录历史
            self._record_emotion_change(emotion_type, intensity)

    def decay_coloring(self, decay_rate: float = 0.1) -> None:
        """
        情绪染色衰减

        Args:
            decay_rate: 衰减率
        """
        for emotion_type in list(self.coloring_layer.keys()):
            old_intensity = self.coloring_layer[emotion_type]
            new_intensity = max(0, old_intensity - decay_rate)

            if new_intensity > 0:
                self.coloring_layer[emotion_type] = new_intensity
                # 恢复基础情绪
                self.current_emotions[emotion_type] = self.base_emotions[emotion_type] * (1 + new_intensity)
            else:
                del self.coloring_layer[emotion_type]
                self.current_emotions[emotion_type] = self.base_emotions[emotion_type]

    def influence_response(self, response: str) -> str:
        """
        情绪对响应的染色影响

        Returns:
            染色后的响应文本
        """
        dominant = self.get_dominant_emotion()
        intensity = self.current_emotions[dominant]

        if intensity > 0.7:
            # 强情绪染色
            modifiers = {
                'joy': ['😊', '真棒！', '太好了！'],
                'sadness': ['😢', '我理解', '抱歉'],
                'anger': ['😠', '请注意'],
                'fear': ['😨', '小心'],
                'surprise': ['😮', '哇！'],
                'disgust': ['😖']
            }
            modifier = random.choice(modifiers.get(dominant, ['']))
            return f"{modifier} {response}"

        return response

    def reset_to_base(self) -> None:
        """重置为基础情绪状态"""
        self.current_emotions = self.base_emotions.copy()
        self.coloring_layer.clear()

    def _record_emotion_change(self, emotion: str, intensity: float) -> None:
        """记录情绪变化"""
        self.emotion_history.append({
            'emotion': emotion,
            'intensity': intensity,
            'dominant': self.get_dominant_emotion()
        })

        # 只保留最近100条
        if len(self.emotion_history) > 100:
            self.emotion_history = self.emotion_history[-100:]

    def get_emotion_state(self) -> Dict:
        """获取当前情绪状态"""
        return {
            'current': self.current_emotions.copy(),
            'dominant': self.get_dominant_emotion(),
            'coloring': self.coloring_layer.copy(),
            'intensity': self.current_emotions[self.get_dominant_emotion()]
        }
