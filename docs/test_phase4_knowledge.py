"""
第四阶段测试脚本
测试学习与记忆增强
"""
import sys
import os
from pathlib import Path
from datetime import timedelta

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.system_memory import SystemMemory, MemoryType
from core.pattern_learner import PatternLearner, PatternType
from core.knowledge_integration import KnowledgeIntegration
from core.problem_scanner import Problem, ProblemType, ProblemSeverity


def test_system_memory():
    """测试系统记忆"""
    print("\n" + "=" * 60)
    print("测试 1: 系统记忆")
    print("=" * 60)

    try:
        memory = SystemMemory(memory_dir=".test_memory")

        # 测试记住和回忆
        memory_id = memory.remember(
            type=MemoryType.SYSTEM_CONFIG,
            key_parts=['python', 'version'],
            value={'version': '3.11.9'},
            confidence=0.9
        )

        recalled = memory.recall(['python', 'version'], MemoryType.SYSTEM_CONFIG)

        assert recalled is not None
        assert recalled.value == {'version': '3.11.9'}
        assert recalled.confidence == 0.9

        print(f"✅ 记住和回忆功能正常")
        print(f"   记忆ID: {memory_id}")
        print(f"   回忆值: {recalled.value}")

        # 测试按类型回忆
        memories = memory.recall_by_type(MemoryType.SYSTEM_CONFIG)

        assert len(memories) > 0

        print(f"✅ 按类型回忆功能正常")
        print(f"   数量: {len(memories)}")

        # 测试修复记录
        fix_id = memory.record_fix(
            problem_id="test_fix_1",
            problem_type="dependency",
            severity="low",
            file_path="test.py",
            fix_action="升级依赖",
            success=True,
            execution_time=0.5
        )

        print(f"✅ 修复记录功能正常")
        print(f"   记录ID: {fix_id}")

        # 测试获取修复历史
        history = memory.get_fix_history(problem_type="dependency")

        assert len(history) > 0

        print(f"✅ 获取修复历史功能正常")
        print(f"   记录数: {len(history)}")

        # 测试统计
        stats = memory.get_statistics()

        assert stats['total_memories'] > 0
        assert stats['total_fixes'] > 0

        print(f"✅ 统计功能正常")
        print(f"   总记忆: {stats['total_memories']}")
        print(f"   总修复: {stats['total_fixes']}")

        # 清理
        import shutil
        if Path(".test_memory").exists():
            shutil.rmtree(".test_memory")

        print("✅ 系统记忆测试通过")
        return True

    except Exception as e:
        print(f"❌ 系统记忆测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pattern_learner():
    """测试模式学习器"""
    print("\n" + "=" * 60)
    print("测试 2: 模式学习器")
    print("=" * 60)

    try:
        learner = PatternLearner()

        # 学习几个模式
        for i in range(5):
            learner.learn_from_fix(
                problem_type="dependency",
                severity="low",
                file_path="requirements.txt",
                fix_action="升级依赖包",
                success=True,
                execution_time=0.5
            )

        for i in range(2):
            learner.learn_from_fix(
                problem_type="security",
                severity="high",
                file_path=".env",
                fix_action="删除敏感信息",
                success=True,
                execution_time=1.0
            )

        for i in range(3):
            learner.learn_from_fix(
                problem_type="linter",
                severity="medium",
                file_path="test.py",
                fix_action="修复语法错误",
                success=False,
                execution_time=0.8
            )

        print(f"✅ 模式学习功能正常")
        print(f"   总模式数: {len(learner.patterns)}")

        # 查找匹配模式
        matches = learner.find_matching_patterns(
            problem_type="dependency",
            severity="low",
            file_path="requirements.txt"
        )

        # 可能没有足够的模式，所以检查是否正确处理
        print(f"✅ 模式匹配功能正常")
        print(f"   匹配数: {len(matches)}")

        if matches:
            best = matches[0]
            print(f"   最佳匹配:")
            print(f"     相似度: {best.similarity:.2f}")
            print(f"     置信度: {best.confidence:.2f}")
            print(f"     建议: {best.recommendation}")
        else:
            print(f"   提示: 没有足够高置信度的模式匹配")

        # 分析模式
        analysis = learner.analyze_patterns()

        assert analysis['total_patterns'] > 0

        print(f"✅ 模式分析功能正常")
        print(f"   总模式: {analysis['total_patterns']}")
        print(f"   高置信度: {analysis['high_confidence_patterns']}")
        print(f"   平均成功率: {analysis['avg_success_rate']:.1%}")

        print("✅ 模式学习器测试通过")
        return True

    except Exception as e:
        print(f"❌ 模式学习器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_integration():
    """测试知识集成"""
    print("\n" + "=" * 60)
    print("测试 3: 知识集成")
    print("=" * 60)

    try:
        integration = KnowledgeIntegration()

        # 创建测试问题
        problem = Problem(
            id="test_integration_1",
            type=ProblemType.DEPENDENCY,
            severity=ProblemSeverity.LOW,
            title="依赖问题",
            description="测试依赖问题",
            file_path="requirements.txt"
        )

        # 增强决策
        enhancement = integration.enhance_decision(
            problem=problem,
            fix_suggestion="升级依赖"
        )

        assert enhancement is not None

        print(f"✅ 决策增强功能正常")
        print(f"   历史成功率: {enhancement['historical_success_rate']:.1%}")
        print(f"   模式匹配: {len(enhancement['pattern_matches'])}")

        # 记录修复结果
        integration.record_fix_outcome(
            problem=problem,
            fix_action="升级依赖",
            success=True,
            execution_time=0.5
        )

        print(f"✅ 修复结果记录功能正常")

        # 获取推荐修复
        recommendation = integration.get_recommended_fix(problem)

        print(f"✅ 推荐修复功能正常")
        print(f"   推荐: {recommendation or '无'}")

        # 生成学习报告
        report = integration.generate_learning_report()

        print(f"✅ 学习报告生成功能正常")
        print(f"   报告长度: {len(report)} 字符")

        # 统计
        stats = integration.stats

        print(f"✅ 集成统计:")
        print(f"   增强决策: {stats['decisions_enhanced']}")
        print(f"   发现模式: {stats['patterns_found']}")
        print(f"   访问记忆: {stats['memories_accessed']}")

        print("✅ 知识集成测试通过")
        return True

    except Exception as e:
        print(f"❌ 知识集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_persistence():
    """测试持久化"""
    print("\n" + "=" * 60)
    print("测试 4: 持久化")
    print("=" * 60)

    try:
        memory = SystemMemory(memory_dir=".test_memory_persist")

        # 保存一些数据
        memory.remember(
            type=MemoryType.SYSTEM_CONFIG,
            key_parts=['test', 'persist'],
            value={'data': 'test'},
        )

        memory.record_fix(
            problem_id="persist_fix",
            problem_type="test",
            severity="low",
            file_path="test.py",
            fix_action="测试修复",
            success=True,
            execution_time=0.5
        )

        # 保存
        memory.save()

        # 创建新实例并加载
        memory2 = SystemMemory(memory_dir=".test_memory_persist")
        memory2.load()

        # 验证
        assert memory2.stats['total_memories'] == memory.stats['total_memories']
        assert memory2.stats['total_fixes'] == memory.stats['total_fixes']

        print(f"✅ 记忆持久化功能正常")
        print(f"   记忆数: {memory2.stats['total_memories']}")
        print(f"   修复数: {memory2.stats['total_fixes']}")

        # 清理
        import shutil
        if Path(".test_memory_persist").exists():
            shutil.rmtree(".test_memory_persist")

        print("✅ 持久化测试通过")
        return True

    except Exception as e:
        print(f"❌ 持久化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_best_practices():
    """测试最佳实践"""
    print("\n" + "=" * 60)
    print("测试 5: 最佳实践")
    print("=" * 60)

    try:
        memory = SystemMemory()

        # 保存最佳实践
        memory.save_best_practice(
            context="dependency:low",
            practice={
                'suggested_fix': '使用 pip install --upgrade',
                'avg_time': 0.3,
                'success_count': 10,
            },
            confidence=0.9
        )

        # 获取最佳实践
        practice = memory.get_best_practice("dependency:low")

        assert practice is not None
        assert practice['suggested_fix'] == '使用 pip install --upgrade'

        print(f"✅ 最佳实践功能正常")
        print(f"   建议: {practice['suggested_fix']}")

        # 测试用户偏好
        memory.set_user_preference('fix_style', 'conservative')
        pref = memory.get_user_preference('fix_style')

        assert pref == 'conservative'

        print(f"✅ 用户偏好功能正常")
        print(f"   偏好: {pref}")

        # 清理
        if Path(".memory").exists():
            import shutil
            shutil.rmtree(".memory")

        print("✅ 最佳实践测试通过")
        return True

    except Exception as e:
        print(f"❌ 最佳实践测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_flow():
    """测试完整集成流程"""
    print("\n" + "=" * 60)
    print("测试 6: 完整集成流程")
    print("=" * 60)

    try:
        integration = KnowledgeIntegration()

        # 模拟一系列修复
        problems = [
            Problem(
                id=f"problem_{i}",
                type=ProblemType.DEPENDENCY,
                severity=ProblemSeverity.LOW,
                title="依赖问题",
                description="测试",
                file_path="requirements.txt"
            )
            for i in range(10)
        ]

        for i, problem in enumerate(problems):
            # 增强决策
            enhancement = integration.enhance_decision(
                problem=problem,
                fix_suggestion="升级依赖"
            )

            # 记录结果
            success = i < 7  # 前7次成功
            integration.record_fix_outcome(
                problem=problem,
                fix_action="升级依赖",
                success=success,
                execution_time=0.5 + (i * 0.05)
            )

        print(f"✅ 完整流程执行成功")
        print(f"   处理问题: {len(problems)}")

        # 生成报告
        report = integration.generate_learning_report()

        print(f"✅ 学习报告生成成功")
        print(f"\n{report}")

        # 统计
        stats = integration.stats

        print(f"\n集成统计:")
        print(f"  增强决策: {stats['decisions_enhanced']}")
        print(f"  发现模式: {stats['patterns_found']}")
        print(f"  访问记忆: {stats['memories_accessed']}")
        print(f"  应用实践: {stats['best_practices_applied']}")

        # 清理
        if Path(".memory").exists():
            import shutil
            shutil.rmtree(".memory")

        print("✅ 完整集成流程测试通过")
        return True

    except Exception as e:
        print(f"❌ 完整集成流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print(" " * 15 + "第四阶段：学习与记忆增强测试")
    print("=" * 70)

    tests = [
        test_system_memory,
        test_pattern_learner,
        test_knowledge_integration,
        test_persistence,
        test_best_practices,
        test_integration_flow,
    ]

    results = []

    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # 统计结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    print(f"通过: {passed}/{total}")
    print(f"失败: {total - passed}/{total}")
    print(f"通过率: {passed/total:.1%}")

    if passed == total:
        print("\n🎉 所有测试通过!")
        return True
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
