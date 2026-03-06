"""
第三阶段测试脚本
测试完全自主决策引擎
"""
import sys
import os
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.autonomous_engine import AutonomousEngine, RiskLevel, DecisionType
from core.decision_optimizer import DecisionOptimizer
from core.autonomy_manager import AutonomyManager


def test_autonomous_engine_initialization():
    """测试自主决策引擎初始化"""
    print("\n" + "=" * 60)
    print("测试 1: 自主决策引擎初始化")
    print("=" * 60)
    
    try:
        engine = AutonomousEngine()
        
        assert engine is not None
        assert len(engine.decisions) == 0
        assert engine.stats['total_decisions'] == 0
        assert not engine.is_running
        
        print("✅ 引擎初始化成功")
        return True
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_assessment():
    """测试风险评估"""
    print("\n" + "=" * 60)
    print("测试 2: 风险评估")
    print("=" * 60)
    
    try:
        engine = AutonomousEngine()
        
        from core.problem_scanner import Problem, ProblemType, ProblemSeverity
        
        # 创建测试问题
        safe_problem = Problem(
            id="test_safe_1",
            type=ProblemType.DEPENDENCY,
            severity=ProblemSeverity.LOW,
            title="测试问题",
            description="测试描述",
            file_path="test.py"
        )
        
        critical_problem = Problem(
            id="test_critical_1",
            type=ProblemType.SECURITY,
            severity=ProblemSeverity.CRITICAL,
            title="敏感信息泄露",
            description="在配置文件中发现敏感信息",
            file_path="config/.env"
        )
        
        # 评估风险
        safe_risk = engine.assess_risk(safe_problem, "修复依赖")
        critical_risk = engine.assess_risk(critical_problem, "删除敏感信息")
        
        print(f"安全问题风险: {safe_risk.name}")
        print(f"严重问题风险: {critical_risk.name}")
        
        assert safe_risk <= RiskLevel.LOW
        assert critical_risk >= RiskLevel.HIGH
        
        print("✅ 风险评估成功")
        return True
        
    except Exception as e:
        print(f"❌ 风险评估失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_decision_making():
    """测试决策制定"""
    print("\n" + "=" * 60)
    print("测试 3: 决策制定")
    print("=" * 60)
    
    try:
        engine = AutonomousEngine()
        
        from core.problem_scanner import Problem, ProblemType, ProblemSeverity
        
        # 创建测试问题
        problem = Problem(
            id="test_decision_1",
            type=ProblemType.DEPENDENCY,
            severity=ProblemSeverity.MEDIUM,
            title="依赖版本过旧",
            description="检测到过时的依赖包",
            file_path="test.py"
        )
        
        # 做出决策
        decision = engine.make_decision(problem, "升级依赖")
        
        print(f"决策 ID: {decision.id}")
        print(f"决策类型: {decision.decision_type.value}")
        print(f"风险等级: {decision.risk_level.name}")
        print(f"是否批准: {decision.approved}")
        print(f"是否自动批准: {decision.auto_approved}")
        print(f"推理: {decision.reasoning}")
        
        assert decision.id is not None
        assert decision.decision_type in DecisionType
        assert decision.risk_level in RiskLevel
        
        # 检查决策是否被记录
        assert len(engine.decisions) > 0
        assert engine.decisions[-1] == decision
        
        print("✅ 决策制定成功")
        return True
        
    except Exception as e:
        print(f"❌ 决策制定失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_manual_improvement():
    """测试手动改进"""
    print("\n" + "=" * 60)
    print("测试 4: 手动改进")
    print("=" * 60)

    try:
        engine = AutonomousEngine()

        # 执行手动改进（异步）
        result = await engine.manual_improvement(max_fixes=5, auto_approve=False)

        print(f"扫描状态: {result['scanned']}")
        print(f"发现问题数: {result['problems_found']}")
        print(f"决策数: {result['decisions_made']}")
        print(f"尝试修复: {result['fixes_attempted']}")
        print(f"成功修复: {result['fixes_successful']}")
        print(f"失败修复: {result['fixes_failed']}")
        print(f"错误数: {len(result['errors'])}")

        if result['errors']:
            print("\n错误详情:")
            for error in result['errors'][:3]:
                print(f"  - {error}")

        assert 'scanned' in result
        assert 'problems_found' in result

        print("✅ 手动改进测试成功")
        return True

    except Exception as e:
        print(f"❌ 手动改进失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_decision_optimizer():
    """测试决策优化器"""
    print("\n" + "=" * 60)
    print("测试 5: 决策优化器")
    print("=" * 60)
    
    try:
        engine = AutonomousEngine()
        optimizer = DecisionOptimizer(engine)
        
        # 分析决策
        patterns = optimizer.analyze_decisions()
        
        print(f"发现模式数: {len(patterns)}")
        
        if patterns:
            print("\n前3个模式:")
            for pattern in patterns[:3]:
                print(f"  - {pattern.problem_type}/{pattern.severity}")
                print(f"    成功率: {pattern.success_rate:.1%}")
                print(f"    推荐操作: {pattern.recommended_action.value}")
        
        # 优化策略
        report = optimizer.optimize_strategy()
        
        print(f"\n优化策略: {report.strategy.value}")
        print(f"分析的模式数: {report.patterns_analyzed}")
        print("\n建议:")
        for rec in report.recommendations[:5]:
            print(f"  - {rec}")
        
        assert optimizer is not None
        assert report is not None
        
        print("✅ 决策优化器测试成功")
        return True
        
    except Exception as e:
        print(f"❌ 决策优化器失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_autonomy_manager():
    """测试自主能力管理器"""
    print("\n" + "=" * 60)
    print("测试 6: 自主能力管理器")
    print("=" * 60)
    
    try:
        manager = AutonomyManager()
        
        # 初始化
        manager.initialize()
        
        assert manager.is_initialized
        assert manager.engine is not None
        assert manager.optimizer is not None
        
        print("✅ 管理器初始化成功")
        
        # 获取状态
        status = manager.get_status()
        
        print(f"\n初始化状态: {status['initialized']}")
        print(f"自动改进: {status['auto_improvement_enabled']}")
        print(f"总决策数: {status['engine']['total_decisions']}")
        
        # 生成报告
        report = manager.generate_report()
        
        print(f"\n报告时间: {report['timestamp']}")
        print(f"系统操作系统: {report.get('system', {}).get('os_name', 'N/A')}")
        
        assert 'system' in report
        assert 'autonomy' in report
        
        print("✅ 状态和报告获取成功")
        
        # 关闭
        manager.shutdown()
        
        print("✅ 管理器关闭成功")
        return True
        
    except Exception as e:
        print(f"❌ 自主能力管理器失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_persistence():
    """测试状态持久化"""
    print("\n" + "=" * 60)
    print("测试 7: 状态持久化")
    print("=" * 60)
    
    try:
        engine = AutonomousEngine()
        
        # 添加一些决策
        from core.problem_scanner import Problem, ProblemType, ProblemSeverity
        
        problem = Problem(
            id="test_persist_1",
            type=ProblemType.DEPENDENCY,
            severity=ProblemSeverity.LOW,
            title="测试问题",
            description="测试描述",
            file_path="test.py"
        )
        
        decision = engine.make_decision(problem)
        
        # 保存状态
        engine.save_state(".test_autonomous_engine_state.json")
        
        # 创建新引擎并加载状态
        engine2 = AutonomousEngine()
        engine2.load_state(".test_autonomous_engine_state.json")
        
        # 验证状态
        assert len(engine2.decisions) == len(engine.decisions)
        assert engine2.stats['total_decisions'] == engine.stats['total_decisions']
        
        print(f"原引擎决策数: {len(engine.decisions)}")
        print(f"加载后决策数: {len(engine2.decisions)}")
        
        # 清理
        if Path(".test_autonomous_engine_state.json").exists():
            Path(".test_autonomous_engine_state.json").unlink()
        
        print("✅ 状态持久化测试成功")
        return True
        
    except Exception as e:
        print(f"❌ 状态持久化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration_with_main():
    """测试与主程序集成"""
    print("\n" + "=" * 60)
    print("测试 8: 与主程序集成")
    print("=" * 60)

    try:
        # 尝试导入主程序模块
        from core.autonomy_manager import get_autonomy_manager

        # 获取管理器单例
        manager = get_autonomy_manager()

        print("✅ 成功导入自主能力模块")

        # 初始化
        manager.initialize()

        print("✅ 成功初始化自主能力")

        # 测试手动改进
        result = await manager.manual_improvement(max_fixes=3, auto_approve=False)

        print(f"✅ 手动改进测试通过")
        print(f"   发现问题: {result['problems_found']}")

        # 关闭
        manager.shutdown()

        print("✅ 集成测试成功")
        return True

    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print(" " * 15 + "第三阶段：自主决策引擎测试")
    print("=" * 70)

    # 同步测试
    sync_tests = [
        test_autonomous_engine_initialization,
        test_risk_assessment,
        test_decision_making,
        test_decision_optimizer,
        test_autonomy_manager,
        test_state_persistence,
    ]

    # 异步测试
    async_tests = [
        test_manual_improvement,
        test_integration_with_main,
    ]

    results = []

    # 运行同步测试
    for test in sync_tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # 运行异步测试
    import asyncio
    async def run_async_tests():
        async_results = []
        for test in async_tests:
            try:
                result = await test()
                async_results.append(result)
            except Exception as e:
                print(f"\n❌ 测试异常: {e}")
                import traceback
                traceback.print_exc()
                async_results.append(False)
        return async_results

    async_results = asyncio.run(run_async_tests())
    results.extend(async_results)

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
