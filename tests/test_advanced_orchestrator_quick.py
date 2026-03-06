"""
快速测试高级编排器集成
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_advanced_orchestrator_import():
    """测试高级编排器导入"""
    print("测试 1: 导入高级编排器...")
    try:
        from core.advanced_orchestrator import AdvancedOrchestrator
        print("  [OK] 高级编排器导入成功")
        return True
    except Exception as e:
        print(f"  [FAIL] 高级编排器导入失败: {e}")
        return False


async def test_decision_hub_integration():
    """测试 DecisionHub 集成"""
    print("\n测试 2: DecisionHub 集成...")
    try:
        from hub.decision_hub import DecisionHub

        # 创建一个最小化的 DecisionHub 实例
        class MockClient:
            pass

        decision_hub = DecisionHub(
            mlink=None,
            ai_client=None,
            emotion=None,
            personality=None,
            prompt_manager=None,
            memory_net=None,
            decision_engine=None,
            game_mode_adapter=None,
            tool_subnet=None,
            memory_engine=None,
            scheduler=None,
            onebot_client=None,
            identity=None
        )

        # 测试懒加载方法
        orchestrator = decision_hub._get_advanced_orchestrator()
        if orchestrator is not None:
            print("  [OK] 高级编排器懒加载成功")
            return True
        else:
            print("  [WARN] 高级编排器懒加载返回 None（可能依赖未满足）")
            return False

    except Exception as e:
        print(f"  [FAIL] DecisionHub 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("高级编排器集成快速测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(await test_advanced_orchestrator_import())
    results.append(await test_decision_hub_integration())

    # 总结
    print("\n" + "=" * 60)
    print("测试结果:")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过！高级编排器集成成功！")
    else:
        print(f"\n[WARNING] {total - passed} 个测试失败，请检查依赖")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
