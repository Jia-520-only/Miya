"""
高级能力集成测试脚本
测试 DecisionHub 是否正确集成了高级编排器
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_decision_hub_integration():
    """测试 DecisionHub 集成"""
    print("\n" + "="*60)
    print("测试 DecisionHub 高级能力集成")
    print("="*60)
    
    try:
        # 导入必要的模块
        from hub.decision_hub import DecisionHub
        from core.ai_client import AIClientFactory
        from core.emotion import EmotionSystem
        from core.personality import PersonalitySystem
        from core.prompt_manager import PromptManager
        from memory.memory_net import MemoryNet
        
        print("\n✅ 所有模块导入成功")
        
        # 创建模拟的组件
        print("\n📋 创建AI客户端...")
        # 这里使用模拟的API密钥，实际使用时需要配置真实的
        ai_client = AIClientFactory.create_client(
            provider="deepseek",
            api_key="test_key",
            model="deepseek-chat"
        )
        
        print("✅ AI客户端创建成功")
        
        # 创建其他组件
        print("\n📋 创建其他组件...")
        emotion = EmotionSystem()
        personality = PersonalitySystem()
        prompt_manager = PromptManager(personality=personality)
        memory_net = MemoryNet()
        
        print("✅ 其他组件创建成功")
        
        # 创建 DecisionHub
        print("\n📋 创建 DecisionHub...")
        decision_hub = DecisionHub(
            mlink=None,  # 测试时可以为None
            ai_client=ai_client,
            emotion=emotion,
            personality=personality,
            prompt_manager=prompt_manager,
            memory_net=memory_net,
            decision_engine=None,
            tool_subnet=None,
            memory_engine=None,
            scheduler=None,
            onebot_client=None,
            game_mode_adapter=None,
            identity=None
        )
        
        print("✅ DecisionHub 创建成功")
        
        # 检查高级编排器是否初始化
        print("\n📋 检查高级编排器...")
        if decision_hub.advanced_orchestrator is not None:
            print("✅ 高级编排器初始化成功")
            
            # 检查各个子模块
            orchestrator = decision_hub.advanced_orchestrator
            
            print("\n📋 检查子模块:")
            print(f"  - TaskPlanner: {'✅' if orchestrator.task_planner else '❌'}")
            print(f"  - AutonomousExplorer: {'✅' if orchestrator.explorer else '❌'}")
            print(f"  - IntelligentExecutor: {'✅' if orchestrator.executor else '❌'}")
            print(f"  - ChainOfThought: {'✅' if orchestrator.chain_of_thought else '❌'}")
            
        else:
            print("❌ 高级编排器未初始化")
            return False
        
        # 测试复杂任务检测
        print("\n📋 测试复杂任务检测...")
        test_cases = [
            ("帮我分析项目结构", True),
            ("你好", False),
            ("帮我查找所有配置文件", True),
            ("今天天气怎么样", False),
            ("请理解这段代码的逻辑", True),
            ("讲个笑话", False)
        ]
        
        all_passed = True
        for content, expected in test_cases:
            result = decision_hub._should_use_advanced_orchestration(content)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{content}': {result} (期望: {expected})")
            if result != expected:
                all_passed = False
        
        if all_passed:
            print("\n✅ 复杂任务检测测试通过")
        else:
            print("\n❌ 复杂任务检测测试失败")
        
        return all_passed
        
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        print("请确保所有模块都已正确创建")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_modules_import():
    """测试所有新模块是否可以导入"""
    print("\n" + "="*60)
    print("测试新模块导入")
    print("="*60)
    
    modules = [
        "core.task_planner",
        "core.autonomous_explorer",
        "core.intelligent_executor",
        "core.chain_of_thought",
        "core.advanced_orchestrator"
    ]
    
    all_imported = True
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            all_imported = False
    
    return all_imported


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("弥娅高级能力集成测试")
    print("="*60)
    
    # 测试模块导入
    import_result = await test_modules_import()
    
    if not import_result:
        print("\n❌ 模块导入失败，请检查文件是否存在")
        return
    
    # 测试集成
    integration_result = await test_decision_hub_integration()
    
    # 输出总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"模块导入: {'✅ 通过' if import_result else '❌ 失败'}")
    print(f"集成测试: {'✅ 通过' if integration_result else '❌ 失败'}")
    
    if import_result and integration_result:
        print("\n🎉 所有测试通过！高级能力已成功集成！")
        print("\n下一步：")
        print("1. 配置真实的API密钥")
        print("2. 运行弥娅主程序")
        print("3. 尝试发送复杂任务，如：'帮我分析项目结构'")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")


if __name__ == "__main__":
    asyncio.run(main())
