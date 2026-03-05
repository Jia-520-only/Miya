"""
学习效果评估器
评估增量学习和人格进化的效果
"""
from typing import Dict


class LearningEvaluator:
    """学习效果评估器"""

    def __init__(self):
        self.metrics = {}

    async def evaluate_learning(self, before_state: Dict,
                               after_state: Dict) -> Dict:
        """评估学习效果"""

        # 1. 人格稳定性
        personality_stability = self._evaluate_personality_stability(
            before_state, after_state
        )

        # 2. 知识保留
        knowledge_retention = self._evaluate_knowledge_retention(
            before_state, after_state
        )

        # 3. 性能提升
        performance_improvement = self._evaluate_performance(
            before_state, after_state
        )

        # 4. 用户满意度
        user_satisfaction = self._evaluate_satisfaction(after_state)

        metrics = {
            'personality_stability': personality_stability,
            'knowledge_retention': knowledge_retention,
            'performance_improvement': performance_improvement,
            'user_satisfaction': user_satisfaction
        }

        # 计算总分
        total_score = sum(metrics.values()) / len(metrics)

        return {
            'metrics': metrics,
            'total_score': round(total_score, 3),
            'evaluation_summary': self._generate_summary(metrics)
        }

    def _evaluate_personality_stability(self, before: Dict, after: Dict) -> float:
        """评估人格稳定性"""
        before_vectors = before.get('personality_vectors', {})
        after_vectors = after.get('personality_vectors', {})

        if not before_vectors or not after_vectors:
            return 0.5

        # 计算向量变化
        total_diff = 0.0
        count = 0

        for key in before_vectors:
            if key in after_vectors:
                diff = abs(before_vectors[key] - after_vectors[key])
                total_diff += diff
                count += 1

        if count == 0:
            return 0.5

        avg_diff = total_diff / count
        stability = 1.0 - min(avg_diff, 1.0)

        return stability

    def _evaluate_knowledge_retention(self, before: Dict, after: Dict) -> float:
        """评估知识保留"""
        before_count = before.get('knowledge_count', 0)
        after_count = after.get('knowledge_count', 0)

        if before_count == 0:
            return 0.5

        # 知识应该增加或保持
        if after_count >= before_count:
            return 1.0
        else:
            return after_count / before_count

    def _evaluate_performance(self, before: Dict, after: Dict) -> float:
        """评估性能提升"""
        before_score = before.get('performance_score', 0.5)
        after_score = after.get('performance_score', 0.5)

        if after_score > before_score:
            improvement = (after_score - before_score) / (1.0 - before_score)
            return round(min(improvement + 0.5, 1.0), 3)
        else:
            return 0.5

    def _evaluate_satisfaction(self, after: Dict) -> float:
        """评估用户满意度"""
        # 简化实现：从状态中提取满意度
        return after.get('user_satisfaction', 0.8)

    def _generate_summary(self, metrics: Dict) -> str:
        """生成评估摘要"""
        lines = [
            "【学习效果评估】",
            f"人格稳定性：{metrics['personality_stability']:.2f}",
            f"知识保留：{metrics['knowledge_retention']:.2f}",
            f"性能提升：{metrics['performance_improvement']:.2f}",
            f"用户满意度：{metrics['user_satisfaction']:.2f}"
        ]

        return "\n".join(lines)
