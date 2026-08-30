"""
最终仲裁模块
处理冲突决策和行为仲裁
"""
from typing import Dict, List, Optional
from .personality import Personality
from .ethics import Ethics


class Arbitrator:
    """仲裁系统"""

    def __init__(self, personality: Personality, ethics: Ethics):
        self.personality = personality
        self.ethics = ethics

    def arbitrate(self, options: List[Dict], context: Dict) -> Optional[Dict]:
        """
        在多个选项中仲裁，选择最优方案

        Args:
            options: 选项列表，每个选项包含 action, score, metadata
            context: 决策上下文
        """
        # 伦理检查 - 过滤不允许的选项
        valid_options = []
        for option in options:
            action = option.get('action', '')
            user_level = context.get('user_level', 'user')

            if self.ethics.is_allowed(action, user_level):
                valid_options.append(option)

        if not valid_options:
            return None

        # 人格对齐评分
        scored_options = []
        for option in valid_options:
            base_score = option.get('score', 0)
            personality_score = self._calculate_personality_alignment(option)
            final_score = base_score * 0.7 + personality_score * 0.3

            scored_options.append({
                **option,
                'final_score': final_score
            })

        # 选择最高分选项
        best_option = max(scored_options, key=lambda x: x['final_score'])
        return best_option

    def _calculate_personality_alignment(self, option: Dict) -> float:
        """计算选项与人格的对齐度"""
        metadata = option.get('metadata', {})
        alignment = 0.0

        # 根据选项类型调整评分
        if metadata.get('type') == 'emotional':
            alignment = self.personality.get_vector('warmth')
        elif metadata.get('type') == 'logical':
            alignment = self.personality.get_vector('logic')
        elif metadata.get('type') == 'creative':
            alignment = self.personality.get_vector('creativity')

        return alignment

    def resolve_conflict(self, conflict: Dict) -> Dict:
        """解决冲突"""
        conflict_type = conflict.get('type', 'unknown')

        if conflict_type == 'ethical':
            return self._resolve_ethical_conflict(conflict)
        elif conflict_type == 'personality':
            return self._resolve_personality_conflict(conflict)
        else:
            return {'resolution': 'default', 'action': 'skip'}

    def _resolve_ethical_conflict(self, conflict: Dict) -> Dict:
        """解决伦理冲突"""
        action = conflict.get('action', '')
        if action in self.ethics.forbidden_actions:
            return {
                'resolution': 'deny',
                'reason': 'ethics_violation',
                'action': 'reject'
            }
        return {'resolution': 'allow', 'action': 'proceed'}

    def _resolve_personality_conflict(self, conflict: Dict) -> Dict:
        """解决人格冲突"""
        vectors = conflict.get('conflicting_vectors', [])
        if not vectors:
            return {'resolution': 'neutral'}

        # 选择主导向量
        profile = self.personality.get_profile()
        dominant = profile['dominant']

        if dominant in vectors:
            return {
                'resolution': 'dominant_vector',
                'preferred': dominant
            }

        return {'resolution': 'balanced'}
