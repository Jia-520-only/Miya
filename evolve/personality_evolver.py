"""
人格进化机制
支持从交互中学习和进化人格
"""
from typing import Dict
import time


class PersonalityEvolver:
    """人格进化器"""

    def __init__(self, personality):
        self.personality = personality
        self.evolution_history = []

    async def evolve_from_interaction(self, interaction: Dict) -> Dict:
        """从交互中进化人格"""

        # 1. 分析交互对人格的影响
        impact = await self._analyze_impact(interaction)

        # 2. 计算人格调整
        adjustments = self._calculate_adjustments(impact)

        # 3. 应用调整
        for vector, delta in adjustments.items():
            self.personality.update_vector(vector, delta)

        # 4. 记录进化历史
        self.evolution_history.append({
            'timestamp': time.time(),
            'interaction_id': interaction.get('id', ''),
            'adjustments': adjustments,
            'impact': impact
        })

        return {
            'evolved': bool(adjustments),
            'adjustments': adjustments
        }

    async def _analyze_impact(self, interaction: Dict) -> Dict:
        """分析交互影响"""
        interaction_type = interaction.get('type', 'general')
        emotion = interaction.get('emotion', {})

        # 基于类型确定影响
        impacts = {
            'positive_interaction': {'warmth': 0.02, 'empathy': 0.01},
            'negative_interaction': {'warmth': -0.02, 'empathy': 0.01},
            'creative_task': {'creativity': 0.02, 'logic': 0.01},
            'analytical_task': {'logic': 0.02, 'warmth': -0.01},
            'crisis_situation': {'resilience': 0.02, 'empathy': 0.01}
        }

        return impacts.get(interaction_type, {})

    def _calculate_adjustments(self, impact: Dict) -> Dict[str, float]:
        """计算人格调整"""
        # 简化实现：限制调整幅度，避免人格突变
        max_adjustment = 0.05

        adjustments = {}
        for vector, delta in impact.items():
            # 限制最大调整幅度
            adjusted_delta = max(min(delta, max_adjustment), -max_adjustment)
            adjustments[vector] = round(adjusted_delta, 3)

        return adjustments

    def get_evolution_history(self) -> List[Dict]:
        """获取进化历史"""
        return self.evolution_history.copy()
