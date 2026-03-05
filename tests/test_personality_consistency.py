"""
人格一致性测试用例
测试 personality.py 和 personality_consistency.py 的功能
"""
import pytest
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.personality import Personality
from core.personality_consistency import PersonalityConsistencyGuard
from core.personality_evaluator import PersonalityEvaluator


class TestPersonalityBasics:
    """人格基础功能测试"""

    def test_personality_initialization(self):
        """测试人格初始化"""
        personality = Personality()

        # 检查向量初始化
        assert 'warmth' in personality.vectors
        assert 'logic' in personality.vectors
        assert 'creativity' in personality.vectors
        assert 'empathy' in personality.vectors
        assert 'resilience' in personality.vectors

        # 检查形态
        assert personality.current_form == 'normal'
        assert personality.current_title == '佳'

    def test_form_switching(self):
        """测试形态切换"""
        personality = Personality()

        # 切换到战态
        assert personality.set_form('battle') == True
        assert personality.current_form == 'battle'
        assert personality.get_current_form()['name'] == '战态'

        # 切换回常态
        assert personality.set_form('normal') == True
        assert personality.current_form == 'normal'

        # 测试无效形态
        assert personality.set_form('invalid') == False

    def test_title_switching(self):
        """测试称呼切换"""
        personality = Personality()

        # 切换到亲昵称呼
        personality.set_title_by_mood('affectionate')
        assert personality.current_title in ['佳宝', '小可爱']

        # 切换到正式称呼
        personality.set_title_by_mood('formal')
        assert personality.current_title == '造物主'

    def test_vector_boundaries(self):
        """测试向量边界约束"""
        personality = Personality()

        # 测试上限
        original_warmth = personality.vectors['warmth']
        personality.update_vector('warmth', 0.5)
        assert personality.vectors['warmth'] <= 1.0

        # 测试下限
        personality.update_vector('warmth', -2.0)
        assert personality.vectors['warmth'] >= 0.3

    def test_stability_calculation(self):
        """测试稳定性计算"""
        personality = Personality()
        profile = personality.get_profile()

        # 检查稳定性分数
        assert 'stability' in profile
        assert 0.0 <= profile['stability'] <= 1.0


class TestPersonalityCorrelations:
    """人格相关性约束测试"""

    def test_warmth_empathy_correlation(self):
        """测试温暖度与同理心相关性"""
        personality = Personality()

        # 增加温暖度，同理心应该增加（正相关）
        old_empathy = personality.vectors['empathy']
        personality.update_vector('warmth', 0.1)

        # 同理心应该有所增加
        new_empathy = personality.vectors['empathy']
        assert new_empathy >= old_empathy

    def test_logic_warmth_correlation(self):
        """测试逻辑与温暖负相关"""
        personality = Personality()

        # 增加逻辑性，温暖度应该降低（负相关）
        old_warmth = personality.vectors['warmth']
        personality.update_vector('logic', 0.1)

        # 温暖度应该有所降低
        new_warmth = personality.vectors['warmth']
        assert new_warmth <= old_warmth

    def test_correlation_constraints(self):
        """测试相关性约束"""
        personality = Personality()

        # 验证所有相关性约束都存在
        from core.personality import Personality

        assert hasattr(Personality, 'PERSONALITY_CORRELATIONS')
        correlations = Personality.PERSONALITY_CORRELATIONS

        # 检查关键相关性
        assert ('warmth', 'empathy') in correlations
        assert ('logic', 'warmth') in correlations


class TestPersonalityConsistencyGuard:
    """人格一致性保障器测试"""

    def test_guard_initialization(self):
        """测试保障器初始化"""
        guard = PersonalityConsistencyGuard()

        assert guard.consistency_threshold == 0.7
        assert len(guard.response_history) == 0

    def test_tone_match_check(self):
        """测试语气匹配检查"""
        guard = PersonalityConsistencyGuard()
        personality = Personality()

        # 常态下的温柔响应
        gentle_response = "佳，别担心，我会陪着你的。"
        score = guard._check_tone_match(gentle_response, 'normal')
        assert score > 0.5

        # 战态下的严厉响应
        strict_response = "立即执行命令！"
        score = guard._check_tone_match(strict_response, 'battle')
        assert score > 0.5

    def test_response_consistency_check(self):
        """测试响应一致性检查"""
        guard = PersonalityConsistencyGuard()
        personality = Personality()
        profile = personality.get_profile()

        # 一致的响应
        consistent_response = "佳，我来帮你分析这个问题。"
        result = guard.check_response_consistency(consistent_response, profile)

        assert 'score' in result
        assert 'issues' in result
        assert 'suggestions' in result
        assert 'is_consistent' in result

    def test_consistency_stats(self):
        """测试一致性统计"""
        guard = PersonalityConsistencyGuard()
        personality = Personality()
        profile = personality.get_profile()

        # 添加一些响应
        for i in range(10):
            response = f"测试响应{i}"
            guard.check_response_consistency(response, profile)

        # 获取统计
        stats = guard.get_consistency_stats()

        assert 'total_responses' in stats
        assert 'violations' in stats
        assert 'avg_score' in stats
        assert stats['total_responses'] == 10


class TestPersonalityEvaluator:
    """人格一致性评估器测试"""

    @pytest.mark.asyncio
    async def test_scenario_evaluation(self):
        """测试场景评估"""
        evaluator = PersonalityEvaluator()
        personality = Personality()
        profile = personality.get_profile()

        # 评估危机场景
        responses = [
            "佳，别慌，我们一起来解决。",
            "别担心，我会帮你的。"
        ]

        result = await evaluator.evaluate_scenario('crisis', responses, profile)

        assert hasattr(result, 'consistency')
        assert hasattr(result, 'fidelity')
        assert hasattr(result, 'depth')
        assert hasattr(result, 'emotion_authenticity')

    @pytest.mark.asyncio
    async def test_all_scenarios_evaluation(self):
        """测试所有场景评估"""
        evaluator = PersonalityEvaluator()
        personality = Personality()
        profile = personality.get_profile()

        results = await evaluator.evaluate_all_scenarios(profile)

        assert 'scenarios' in results
        assert 'overall' in results
        assert 'evaluation_summary' in results

        # 检查所有场景
        assert 'crisis' in results['scenarios']
        assert 'daily' in results['scenarios']
        assert 'education' in results['scenarios']

    @pytest.mark.asyncio
    async def test_comprehensive_test(self):
        """测试综合评估"""
        evaluator = PersonalityEvaluator()
        personality = Personality()
        profile = personality.get_profile()

        result = await evaluator.run_comprehensive_test(profile)

        assert 'results' in result
        assert 'report' in result

        # 报告应该包含关键信息
        report = result['report']
        assert '人格一致性综合评估报告' in report
        assert '总体分数' in report


class TestPersonalityIntegration:
    """人格系统集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流程"""
        # 1. 创建人格
        personality = Personality()
        profile = personality.get_profile()

        # 2. 创建一致性保障器
        guard = PersonalityConsistencyGuard()

        # 3. 创建评估器
        evaluator = PersonalityEvaluator()

        # 4. 模拟对话
        test_responses = [
            "佳，别担心，我会陪着你的。",
            "让我帮你分析这个问题。",
            "我们一起学习，你一定能学会的。"
        ]

        # 5. 检查一致性
        for response in test_responses:
            result = guard.check_response_consistency(response, profile)
            assert result['score'] >= 0.5

        # 6. 综合评估
        evaluation = await evaluator.run_comprehensive_test(profile)
        assert evaluation['results']['overall']['total'] > 0

    def test_form_specific_behavior(self):
        """测试形态特定行为"""
        personality = Personality()
        guard = PersonalityConsistencyGuard()

        # 测试各形态
        forms = ['normal', 'battle', 'muse', 'singer', 'ghost']
        responses_by_form = {
            'normal': "佳，我来帮你。",
            'battle': "执行攻击！",
            'muse': "让我来描述这个场景。",
            'singer': "大家一起开心起来！",
            'ghost': "我感到一种淡淡的忧伤。"
        }

        for form in forms:
            personality.set_form(form)
            profile = personality.get_profile()

            response = responses_by_form[form]
            result = guard.check_response_consistency(response, profile)

            # 至少应该有一定分数
            assert result['tone_match'] > 0.3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
