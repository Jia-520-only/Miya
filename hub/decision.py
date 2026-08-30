"""
决策引擎
综合多维因素进行决策
"""
from typing import Dict, List, Optional
from .emotion import Emotion
from core.personality import Personality
from core.ethics import Ethics


class Decision:
    """决策引擎"""

    def __init__(self, emotion: Emotion, personality: Personality, ethics: Ethics):
        self.emotion = emotion
        self.personality = personality
        self.ethics = ethics
        self.decision_history = []

    def make_decision(self, context: Dict, options: List[Dict]) -> Optional[Dict]:
        """
        综合决策

        Args:
            context: 决策上下文
            options: 可选方案列表

        Returns:
            选中的最优方案
        """
        if not options:
            return None

        # 计算每个选项的综合得分
        scored_options = []
        for option in options:
            score = self._calculate_option_score(option, context)
            scored_options.append({
                'option': option,
                'score': score
            })

        # 选择得分最高的方案
        scored_options.sort(key=lambda x: x['score'], reverse=True)
        best = scored_options[0]['option']

        # 记录决策历史
        self._record_decision(best, context)

        return best

    def _calculate_option_score(self, option: Dict, context: Dict) -> float:
        """计算选项综合得分"""
        base_score = option.get('base_score', 0.5)

        # 情绪影响
        emotion_state = self.emotion.get_emotion_state()
        emotion_factor = self._emotion_alignment(option, emotion_state)

        # 人格影响
        personality_factor = self._personality_alignment(option)

        # 伦理检查
        if not self._ethics_check(option, context):
            return 0.0

        # 综合评分
        final_score = (
            base_score * 0.4 +
            emotion_factor * 0.3 +
            personality_factor * 0.3
        )

        return round(final_score, 3)

    def _emotion_alignment(self, option: Dict, emotion_state: Dict) -> float:
        """情绪对齐度"""
        option_emotion = option.get('emotion_type', '')
        if not option_emotion:
            return 0.5

        current_emotions = emotion_state['current']
        return current_emotions.get(option_emotion, 0.5)

    def _personality_alignment(self, option: Dict) -> float:
        """人格对齐度"""
        metadata = option.get('metadata', {})
        personality_type = metadata.get('personality_type', '')

        if personality_type == 'warm':
            return self.personality.get_vector('warmth')
        elif personality_type == 'logical':
            return self.personality.get_vector('logic')
        elif personality_type == 'creative':
            return self.personality.get_vector('creativity')
        elif personality_type == 'empathetic':
            return self.personality.get_vector('empathy')
        else:
            return 0.5

    def _ethics_check(self, option: Dict, context: Dict) -> bool:
        """伦理检查"""
        action = option.get('action', '')
        user_level = context.get('user_level', 'user')
        return self.ethics.is_allowed(action, user_level)

    def _record_decision(self, decision: Dict, context: Dict) -> None:
        """记录决策"""
        self.decision_history.append({
            'decision': decision,
            'context': context,
            'emotion_state': self.emotion.get_emotion_state(),
            'timestamp': self._get_timestamp()
        })

        # 只保留最近50条
        if len(self.decision_history) > 50:
            self.decision_history = self.decision_history[-50:]

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_decision_stats(self) -> Dict:
        """获取决策统计"""
        if not self.decision_history:
            return {'total': 0}

        emotion_distribution = {}
        for record in self.decision_history:
            dominant = record['emotion_state']['dominant']
            emotion_distribution[dominant] = emotion_distribution.get(dominant, 0) + 1

        return {
            'total': len(self.decision_history),
            'emotion_distribution': emotion_distribution
        }
