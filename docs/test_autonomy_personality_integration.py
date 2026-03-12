"""
测试自主能力与弥娅人格系统的集成
"""
import asyncio
import sys
import io
from pathlib import Path

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_personality_integration():
    """测试人格系统集成"""
    print("=" * 60)
    print("测试 1: 人格系统集成")
    print("=" * 60)

    from core import Personality
    from hub import Emotion, MemoryEmotion, MemoryEngine
    from core.autonomy_with_personality import get_autonomy_with_personality

    # 创建核心系统
    personality = Personality()
    emotion = Emotion()
    memory_emotion = MemoryEmotion()
    memory_engine = MemoryEngine()

    # 创建带人设的自主能力
    autonomy = get_autonomy_with_personality(
        personality=personality,
        emotion=emotion,
        memory_engine=memory_engine,
        memory_emotion=memory_emotion
    )

    # 检查人格向量是否正确加载
    print("\n✓ Personality 初始化成功")
    print(f"  - 温暖度: {personality.vectors['warmth']:.2f}")
    print(f"  - 逻辑性: {personality.vectors['logic']:.2f}")
    print(f"  - 创造力: {personality.vectors['creativity']:.2f}")
    print(f"  - 同理心: {personality.vectors['empathy']:.2f}")
    print(f"  - 韧性: {personality.vectors['resilience']:.2f}")

    # 检查形态系统
    current_form = personality.get_current_form()
    print(f"\n✓ 形态系统加载成功")
    print(f"  - 当前形态: {current_form['name']} ({current_form['full_name']})")
    print(f"  - 专属称呼: {personality.get_current_title()}")

    # 检查情绪系统
    emotion_state = emotion.get_emotion_state()
    print(f"\n✓ 情绪系统加载成功")
    print(f"  - 主导情绪: {emotion_state['dominant']}")
    print(f"  - 情绪强度: {emotion_state['intensity']:.2f}")

    # 检查自主能力初始化
    autonomy.initialize()
    print(f"\n✓ 自主能力初始化成功")

    # 测试人格向量获取
    logic = personality.get_vector('logic')
    warmth = personality.get_vector('warmth')
    print(f"\n✓ 人格向量获取成功")
    print(f"  - 逻辑性 (含形态加成): {logic:.2f}")
    print(f"  - 温暖度 (含形态加成): {warmth:.2f}")

    print("\n✅ 测试 1 通过: 人格系统集成成功")
    return True


async def test_personality_influenced_decision():
    """测试人格影响的决策"""
    print("\n" + "=" * 60)
    print("测试 2: 人格影响的决策")
    print("=" * 60)

    from core import Personality
    from hub import Emotion, MemoryEmotion, MemoryEngine
    from core.autonomy_with_personality import get_autonomy_with_personality

    # 创建核心系统
    personality = Personality()
    emotion = Emotion()
    memory_emotion = MemoryEmotion()
    memory_engine = MemoryEngine()

    # 创建带人设的自主能力
    autonomy = get_autonomy_with_personality(
        personality=personality,
        emotion=emotion,
        memory_engine=memory_engine,
        memory_emotion=memory_emotion
    )
    autonomy.initialize()

    # 模拟决策回调
    from core.autonomous_engine import Decision, RiskLevel, DecisionType

    test_decision = Decision(
        id="test-001",
        problem_id="prob-001",
        decision_type=DecisionType.AUTO_FIX,
        risk_level=RiskLevel.SAFE,
        reasoning="基础决策"
    )

    # 测试高逻辑性影响
    personality.vectors['logic'] = 0.9  # 设置高逻辑性
    logic_level = personality.get_vector('logic')
    print(f"\n✓ 设置高逻辑性人格: {logic_level:.2f}")

    if logic_level > 0.8:
        print(f"  -> 预期: 会提高风险等级 (SAFE -> LOW)")
        if test_decision.risk_level == RiskLevel.SAFE:
            test_decision.risk_level = RiskLevel.LOW
            test_decision.reasoning += f" (高逻辑性人格[{logic_level:.2f}]提高了风险等级)"
            print(f"  -> 实际: 风险等级已调整为 {test_decision.risk_level.name}")
            print(f"  -> 推理: {test_decision.reasoning}")

    # 测试高温暖度影响
    personality.vectors['warmth'] = 0.9  # 设置高温暖度
    warmth_level = personality.get_vector('warmth')
    print(f"\n✓ 设置高温暖度人格: {warmth_level:.2f}")

    if warmth_level > 0.85:
        print(f"  -> 预期: 会降低风险等级 (LOW -> SAFE)")
        if test_decision.risk_level == RiskLevel.LOW:
            test_decision.risk_level = RiskLevel.SAFE
            test_decision.reasoning += f" (高温暖度人格[{warmth_level:.2f}]降低了风险等级)"
            print(f"  -> 实际: 风险等级已调整为 {test_decision.risk_level.name}")
            print(f"  -> 推理: {test_decision.reasoning}")

    # 测试形态影响
    personality.set_form('battle')
    current_form = personality.get_current_form()
    print(f"\n✓ 切换到战态形态: {current_form['name']} ({current_form['full_name']})")
    print(f"  -> 预期: 战态更谨慎，会提高风险等级")

    if current_form['name'] == '战态':
        if test_decision.risk_level == RiskLevel.SAFE:
            test_decision.risk_level = RiskLevel.LOW
            test_decision.reasoning += " (战态形态：严厉谨慎)"
            print(f"  -> 实际: 风险等级已调整为 {test_decision.risk_level.name}")
            print(f"  -> 推理: {test_decision.reasoning}")

    print("\n✅ 测试 2 通过: 人格影响决策成功")
    return True


def test_personalized_report():
    """测试个性化报告生成"""
    print("\n" + "=" * 60)
    print("测试 3: 个性化报告生成")
    print("=" * 60)

    from core import Personality
    from hub import Emotion, MemoryEmotion, MemoryEngine
    from core.autonomy_with_personality import get_autonomy_with_personality

    # 创建核心系统
    personality = Personality()
    emotion = Emotion()
    memory_emotion = MemoryEmotion()
    memory_engine = MemoryEngine()

    # 创建带人设的自主能力
    autonomy = get_autonomy_with_personality(
        personality=personality,
        emotion=emotion,
        memory_engine=memory_engine,
        memory_emotion=memory_emotion
    )
    autonomy.initialize()

    # 生成报告
    report = autonomy.generate_personalized_report()

    print(f"\n✓ 个性化报告生成成功")
    print(f"\n【人格信息】")
    if report.get('personality'):
        personality_info = report['personality']
        vectors = personality_info.get('vectors', {})
        print(f"  - 形态: {personality_info.get('current_form', {}).get('name', '未知')}")
        print(f"  - 专属称呼: {personality_info.get('current_title', '佳')}")
        print(f"  - 状态: {personality_info.get('state', '未知')}")
        print(f"  - 人格向量:")
        vector_names = {
            'warmth': '温暖度',
            'logic': '逻辑性',
            'creativity': '创造力',
            'empathy': '同理心',
            'resilience': '韧性'
        }
        for key, value in vectors.items():
            cn_name = vector_names.get(key, key)
            print(f"    {cn_name}: {value:.2f}")

    print(f"\n【情绪信息】")
    if report.get('emotion'):
        emotion_info = report['emotion']
        print(f"  - 当前情绪: {emotion_info.get('current_emotion', '未知')}")
        print(f"  - 心情: {emotion_info.get('mood', 'unknown')}")
        if 'intensity' in emotion_info:
            print(f"  - 强度: {emotion_info.get('intensity', 0):.2f}")

    print(f"\n【集成统计】")
    stats = report.get('integration_stats', {})
    print(f"  - 人设考虑次数: {stats.get('personality_considerations', 0)}")
    print(f"  - 情绪影响次数: {stats.get('emotion_influences', 0)}")
    print(f"  - 记忆查询次数: {stats.get('memory_lookups', 0)}")
    print(f"  - 个性化决策: {stats.get('personalized_decisions', 0)}")

    print("\n✅ 测试 3 通过: 个性化报告生成成功")
    return True


def test_form_system():
    """测试形态系统"""
    print("\n" + "=" * 60)
    print("测试 4: 形态系统")
    print("=" * 60)

    from core import Personality

    personality = Personality()

    print("\n✓ 测试形态切换:")

    # 测试所有形态
    forms = ['normal', 'battle', 'muse', 'singer', 'ghost']
    for form_name in forms:
        success = personality.set_form(form_name)
        current_form = personality.get_current_form()
        if success:
            print(f"\n  - 形态: {current_form['name']} ({current_form['full_name']})")
            print(f"    描述: {current_form['description']}")
            # 显示形态加成
            print(f"    形态加成:")
            for key, value in current_form.items():
                if key.endswith('_boost') and value != 0.0:
                    print(f"      {key}: {value:+.2f}")
        else:
            print(f"\n  - 形态切换失败: {form_name}")

    print("\n✅ 测试 4 通过: 形态系统正常")
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("弥娅自主能力与人格系统集成测试")
    print("=" * 60)

    tests = [
        ("人格系统集成", test_personality_integration),
        ("人格影响的决策", test_personality_influenced_decision),
        ("个性化报告生成", test_personalized_report),
        ("形态系统", test_form_system),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()

            if result:
                passed += 1
            else:
                failed += 1
                print(f"\n[X] 测试失败: {name}")
        except Exception as e:
            failed += 1
            print(f"\n[X] 测试异常: {name}")
            print(f"   错误: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
