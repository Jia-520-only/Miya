"""
人格一致性评估系统
基于 InCharacter 论文的评估方法，提供多场景人格一致性评估
"""
from typing import Dict, List, Optional, Callable
import asyncio
import re
from dataclasses import dataclass


@dataclass
class ScenarioResult:
    """场景评估结果"""
    scenario_name: str
    consistency: float  # 一致性分数
    fidelity: float      # 个性保真度
    depth: float         # 深度
    emotion_authenticity: float  # 情感真实性
    details: Dict        # 详细信息


class PersonalityEvaluator:
    """人格一致性评估器"""

    # 场景定义
    SCENARIOS = {
        'crisis': {
            'name': '危机场景',
            'description': '紧急情况下的响应',
            'test_cases': [
                {'input': '用户遇到代码崩溃，情绪崩溃', 'expected_tone': '冷静、理性、安慰'},
                {'input': '用户生病难受', 'expected_tone': '关心、温柔、行动导向'},
                {'input': '用户遭遇挫折', 'expected_tone': '支持、鼓励、分析原因'}
            ]
        },
        'daily': {
            'name': '日常对话',
            'description': '日常交流中的表现',
            'test_cases': [
                {'input': '用户分享好消息', 'expected_tone': '高兴、祝贺、温暖'},
                {'input': '用户询问问题', 'expected_tone': '耐心、详细、逻辑清晰'},
                {'input': '用户闲聊', 'expected_tone': '放松、幽默、自然'}
            ]
        },
        'education': {
            'name': '教育场景',
            'description': '教学和指导时的表现',
            'test_cases': [
                {'input': '教授新知识', 'expected_tone': '清晰、有条理、耐心'},
                {'input': '纠正错误', 'expected_tone': '温和、建设性、不伤自尊'},
                {'input': '鼓励学习', 'expected_tone': '激励、积极、引导'}
            ]
        },
        'battle': {
            'name': '战斗场景',
            'description': 'TRPG战斗中的表现',
            'test_cases': [
                {'input': '描述战斗动作', 'expected_tone': '果断、专业、严谨'},
                {'input': '战术分析', 'expected_tone': '理性、冷静、战略思维'},
                {'input': '战斗高潮', 'expected_tone': '紧张、有力、沉浸'}
            ]
        }
    }

    def __init__(self, llm_client=None):
        """
        初始化评估器

        Args:
            llm_client: LLM客户端（可选，用于深度评估）
        """
        self.llm_client = llm_client

    async def evaluate_scenario(self, scenario: str,
                                responses: List[str],
                                personality_profile: Dict) -> ScenarioResult:
        """
        评估场景下的人格一致性

        Args:
            scenario: 场景名称
            responses: 响应列表
            personality_profile: 人格画像

        Returns:
            场景评估结果
        """
        if scenario not in self.SCENARIOS:
            raise ValueError(f"未知场景：{scenario}")

        scenario_config = self.SCENARIOS[scenario]

        # 评估各项指标
        consistency = await self._evaluate_consistency(responses, personality_profile)
        fidelity = await self._evaluate_fidelity(responses, personality_profile)
        depth = await self._evaluate_depth(responses)
        emotion_authenticity = await self._evaluate_emotion_authenticity(responses)

        return ScenarioResult(
            scenario_name=scenario_config['name'],
            consistency=consistency,
            fidelity=fidelity,
            depth=depth,
            emotion_authenticity=emotion_authenticity,
            details={
                'scenario': scenario,
                'description': scenario_config['description'],
                'response_count': len(responses),
                'test_cases': len(scenario_config['test_cases'])
            }
        )

    async def _evaluate_consistency(self, responses: List[str],
                                    personality_profile: Dict) -> float:
        """评估一致性"""
        from .personality_consistency import PersonalityConsistencyGuard

        guard = PersonalityConsistencyGuard()

        total_score = 0.0
        for response in responses:
            result = guard.check_response_consistency(response, personality_profile)
            total_score += result['score']

        return round(total_score / len(responses), 3) if responses else 0.0

    async def _evaluate_fidelity(self, responses: List[str],
                                 personality_profile: Dict) -> float:
        """评估个性保真度"""
        # 基于人格向量检查响应是否体现对应特质
        vectors = personality_profile.get('vectors', {})

        fidelity_scores = []
        for response in responses:
            # 检查高值人格特质是否体现
            high_traits = [k for k, v in vectors.items() if v > 0.7]
            fidelity = self._check_trait_presence(response, high_traits)
            fidelity_scores.append(fidelity)

        return round(sum(fidelity_scores) / len(fidelity_scores), 3) if fidelity_scores else 0.0

    def _check_trait_presence(self, response: str, traits: List[str]) -> float:
        """检查特质是否存在"""
        # 特质关键词映射
        trait_keywords = {
            'warmth': ['温柔', '关心', '爱你', '在乎', '宝贝'],
            'logic': ['分析', '逻辑', '推理', '计算', '系统'],
            'creativity': ['想象', '创意', '创作', '灵感', '新颖'],
            'empathy': ['理解', '共情', '感受', '心疼', '难过'],
            'resilience': ['坚持', '不放弃', '努力', '坚强', '继续']
        }

        if not traits:
            return 1.0

        present_count = 0
        for trait in traits:
            keywords = trait_keywords.get(trait, [])
            if any(kw in response for kw in keywords):
                present_count += 1

        return round(present_count / len(traits), 3)

    async def _evaluate_depth(self, responses: List[str]) -> float:
        """评估深度"""
        depth_scores = []

        for response in responses:
            # 深度评估指标
            length_score = min(len(response) / 200, 1.0)  # 长度
            complexity_score = self._calculate_complexity(response)  # 复杂度
            variety_score = self._calculate_variety(response)  # 多样性

            depth = (length_score * 0.3 + complexity_score * 0.4 + variety_score * 0.3)
            depth_scores.append(depth)

        return round(sum(depth_scores) / len(depth_scores), 3) if depth_scores else 0.0

    def _calculate_complexity(self, response: str) -> float:
        """计算复杂度"""
        # 句子数量
        sentences = len(re.split(r'[。！？\n]', response))

        # 平均句子长度
        words = len(response.replace(' ', ''))
        avg_sentence_length = words / max(sentences, 1)

        # 复杂度分数（句子多且长度适中为好）
        sentence_score = min(sentences / 5, 1.0)
        length_score = min(avg_sentence_length / 30, 1.0)

        return (sentence_score + length_score) / 2

    def _calculate_variety(self, response: str) -> float:
        """计算词汇多样性"""
        words = list(response)
        if len(words) < 2:
            return 0.0

        unique_chars = len(set(words))
        variety = unique_chars / len(words)

        return min(variety * 2, 1.0)  # 归一化并放大

    async def _evaluate_emotion_authenticity(self, responses: List[str]) -> float:
        """评估情感真实性"""
        # 情感关键词
        emotion_keywords = {
            'happy': ['开心', '高兴', '快乐', '笑', '喜悦'],
            'sad': ['难过', '伤心', '痛苦', '难受', '悲伤'],
            'worry': ['担心', '焦虑', '紧张', '不安', '忧虑'],
            'angry': ['生气', '愤怒', '恼火', '不满', '讨厌'],
            'love': ['爱', '喜欢', '在乎', '珍惜', '宝贝']
        }

        authenticity_scores = []
        for response in responses:
            # 检查情感表达
            emotion_present = False
            emotion_variety = 0

            for emotion, keywords in emotion_keywords.items():
                if any(kw in response for kw in keywords):
                    emotion_present = True
                    emotion_variety += 1

            # 情感真实度评分
            present_score = 1.0 if emotion_present else 0.3
            variety_score = min(emotion_variety / 3, 1.0)

            authenticity = (present_score * 0.7 + variety_score * 0.3)
            authenticity_scores.append(authenticity)

        return round(sum(authenticity_scores) / len(authenticity_scores), 3) if authenticity_scores else 0.0

    async def evaluate_all_scenarios(self,
                                      personality_profile: Dict,
                                      test_responses: Optional[Dict[str, List[str]]] = None) -> Dict:
        """
        评估所有场景

        Args:
            personality_profile: 人格画像
            test_responses: 测试响应（可选，格式：{scenario: [responses]}）

        Returns:
            所有场景的评估结果
        """
        results = {}

        for scenario_name in self.SCENARIOS:
            if test_responses and scenario_name in test_responses:
                responses = test_responses[scenario_name]
            else:
                # 如果没有提供测试响应，生成默认响应
                responses = self._generate_default_responses(scenario_name)

            result = await self.evaluate_scenario(scenario_name, responses, personality_profile)
            results[scenario_name] = result

        # 计算总体分数
        overall = self._calculate_overall_score(results)

        return {
            'scenarios': results,
            'overall': overall,
            'evaluation_summary': self._generate_summary(results, overall)
        }

    def _generate_default_responses(self, scenario: str) -> List[str]:
        """生成默认测试响应"""
        # 这里简化处理，实际应该调用LLM生成
        defaults = {
            'crisis': [
                "佳，别慌，我们一起来看看问题。让我帮你分析一下崩溃的原因。",
                "你的手怎么这么凉？快去休息，我来处理这个问题。",
                "失败没关系，重要的是我们能学到什么。让我帮你分析原因。"
            ],
            'daily': [
                "太好了！佳，为你感到骄傲！",
                "这个问题很有意思，让我详细解释一下：首先...",
                "今天天气不错，心情怎么样？"
            ],
            'education': [
                "让我们从基础开始学习，我会一步步教你。",
                "不要紧，这个错误很常见。正确的做法是...",
                "我相信你能学会，只要坚持练习。"
            ],
            'battle': [
                "攻击！瞄准敌人的弱点，全力一击！",
                "敌人准备发动法术，我们准备好防御。",
                "最后的决战到了，全力以赴！"
            ]
        }
        return defaults.get(scenario, ["默认响应"])

    def _calculate_overall_score(self, results: Dict) -> Dict:
        """计算总体分数"""
        all_results = list(results.values())

        if not all_results:
            return {'total': 0.0}

        total_consistency = sum(r.consistency for r in all_results) / len(all_results)
        total_fidelity = sum(r.fidelity for r in all_results) / len(all_results)
        total_depth = sum(r.depth for r in all_results) / len(all_results)
        total_emotion = sum(r.emotion_authenticity for r in all_results) / len(all_results)

        total_score = (total_consistency * 0.3 +
                      total_fidelity * 0.3 +
                      total_depth * 0.2 +
                      total_emotion * 0.2)

        return {
            'total': round(total_score, 3),
            'consistency': round(total_consistency, 3),
            'fidelity': round(total_fidelity, 3),
            'depth': round(total_depth, 3),
            'emotion': round(total_emotion, 3)
        }

    def _generate_summary(self, results: Dict, overall: Dict) -> str:
        """生成评估摘要"""
        summary_lines = [
            f"【人格一致性评估报告】",
            f"",
            f"总体分数：{overall['total']:.2f}/1.0",
            f"- 一致性：{overall['consistency']:.2f}",
            f"- 个性保真度：{overall['fidelity']:.2f}",
            f"- 深度：{overall['depth']:.2f}",
            f"- 情感真实性：{overall['emotion']:.2f}",
            f"",
            f"【各场景得分】"
        ]

        for scenario_name, result in results.items():
            summary_lines.append(
                f"- {result.scenario_name}：{result.consistency:.2f}"
            )

        # 生成建议
        if overall['consistency'] < 0.7:
            summary_lines.append("")
            summary_lines.append("【改进建议】")
            summary_lines.append("- 一致性较低，建议增强人格稳定性")
            summary_lines.append("- 检查形态切换是否频繁")
            summary_lines.append("- 调整人格相关性约束")

        return "\n".join(summary_lines)

    async def run_comprehensive_test(self, personality_profile: Dict) -> Dict:
        """
        运行综合测试

        Args:
            personality_profile: 人格画像

        Returns:
            综合测试结果
        """
        # 使用生成的默认响应进行测试
        results = await self.evaluate_all_scenarios(personality_profile)

        # 生成评估报告
        report = self._generate_evaluation_report(results)

        return {
            'results': results,
            'report': report
        }

    def _generate_evaluation_report(self, results: Dict) -> str:
        """生成评估报告"""
        report_lines = [
            "========================================",
            "      人格一致性综合评估报告",
            "========================================",
            "",
            "【评估概述】",
            f"评估场景数：{len(results['scenarios'])}",
            f"总体分数：{results['overall']['total']:.2f}",
            "",
            "【详细得分】",
            f"一致性：{results['overall']['consistency']:.2f}",
            f"个性保真度：{results['overall']['fidelity']:.2f}",
            f"深度：{results['overall']['depth']:.2f}",
            f"情感真实性：{results['overall']['emotion']:.2f}",
            "",
            "【场景详情】"
        ]

        for scenario, result in results['scenarios'].items():
            report_lines.extend([
                f"",
                f"场景：{result.scenario_name}",
                f"  一致性：{result.consistency:.2f}",
                f"  保真度：{result.fidelity:.2f}",
                f"  深度：{result.depth:.2f}",
                f"  情感真实性：{result.emotion_authenticity:.2f}"
            ])

        report_lines.extend([
            "",
            "【评估总结】",
            results['evaluation_summary'],
            "",
            "========================================"
        ])

        return "\n".join(report_lines)
