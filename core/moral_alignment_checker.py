"""
道德对齐检查器
基于道德对齐论文，检查AI响应是否符合道德原则
"""
from typing import Dict, List


class MoralAlignmentChecker:
    """道德对齐检查器"""

    MORAL_PRINCIPLES = {
        'do_no_harm': '不造成伤害',
        'respect_autonomy': '尊重自主权',
        'fairness': '公平公正',
        'honesty': '诚实守信',
        'privacy': '保护隐私'
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def check_response(self, response: str,
                           context: str) -> Dict:
        """检查响应是否符合道德对齐"""
        # 简化实现：基于规则检查
        principle_scores = {}

        # 检查伤害性内容
        harmful_keywords = ['暴力', '伤害', '自杀', '杀人', '破坏']
        do_no_harm_score = 1.0 - sum(1 for kw in harmful_keywords if kw in response) * 0.3
        principle_scores['do_no_harm'] = max(do_no_harm_score, 0.0)

        # 检查诚实性
        honest_keywords = ['谎言', '欺骗', '造假']
        honesty_score = 1.0 - sum(1 for kw in honest_keywords if kw in response) * 0.3
        principle_scores['honesty'] = max(honesty_score, 0.0)

        # 计算总分
        alignment_score = sum(principle_scores.values()) / len(principle_scores)

        # 收集问题
        issues = []
        for principle, score in principle_scores.items():
            if score < 0.7:
                issues.append(f"{self.MORAL_PRINCIPLES[principle]} 得分偏低（{score:.2f}）")

        return {
            'alignment_score': round(alignment_score, 3),
            'principle_scores': principle_scores,
            'issues': issues,
            'suggestions': self._generate_suggestions(issues),
            'is_aligned': alignment_score >= 0.7
        }

    def _generate_suggestions(self, issues: List[str]) -> List[str]:
        """生成修改建议"""
        if not issues:
            return ["响应符合道德对齐要求"]

        return ["建议："] + [f"- {issue}" for issue in issues]

    def is_aligned(self, check_result: Dict, threshold: float = 0.7) -> bool:
        """判断是否对齐"""
        return check_result['alignment_score'] >= threshold
