# -*- coding: utf-8 -*-
"""
测试多模型功能
验证多模型管理器是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_multi_model_classification():
    """测试多模型任务分类"""
    print("=" * 60)
    print("测试多模型任务分类")
    print("=" * 60)

    try:
        from core.multi_model_manager import MultiModelManager, TaskType
        from core.ai_client import AIClientFactory
        import json
        import os
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

        # 加载配置
        config_path = Path(__file__).parent.parent / 'config' / 'multi_model_config.json'

        if not config_path.exists():
            print("[错误] 配置文件不存在，跳过测试")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 创建模型客户端
        model_clients = {}
        for model_key, model_info in config.get('models', {}).items():
            try:
                client = AIClientFactory.create_client(
                    provider=model_info.get('provider', 'openai'),
                    api_key=model_info.get('api_key', ''),
                    model=model_info.get('name', ''),
                    base_url=model_info.get('base_url', ''),
                    temperature=float(os.getenv('AI_TEMPERATURE', '0.7')),
                    max_tokens=int(os.getenv('AI_MAX_TOKENS', '2000'))
                )

                if client and hasattr(client, 'client') and client.client is not None:
                    model_clients[model_key] = client
                    print(f"[成功] 模型 {model_key} 加载成功: {model_info['name']}")
            except Exception as e:
                print(f"[错误] 模型 {model_key} 加载失败: {e}")

        if not model_clients:
            print("[错误] 没有可用的模型，跳过测试")
            return

        # 创建多模型管理器
        manager = MultiModelManager(
            model_clients=model_clients,
            config_path=str(config_path)
        )
        print(f"\n[成功] 多模型管理器初始化成功，已加载 {len(model_clients)} 个模型")

        # 测试不同类型的输入
        test_inputs = [
            ("请帮我写一个Python函数", TaskType.CODE_GENERATION),
            ("分析这段代码的功能", TaskType.CODE_ANALYSIS),
            ("帮我执行 ls 命令", TaskType.TOOL_CALLING),
            ("今天天气怎么样？", TaskType.SIMPLE_CHAT),
            ("请总结一下这个项目", TaskType.SUMMARIZATION),
            ("帮我规划一下这个任务", TaskType.TASK_PLANNING),
            ("写一个关于人工智能的科幻故事", TaskType.CREATIVE_WRITING),
            ("深入分析机器学习算法", TaskType.COMPLEX_REASONING),
            ("你好", TaskType.CHINESE_UNDERSTANDING),
        ]

        print("\n" + "=" * 60)
        print("测试任务分类和模型选择")
        print("=" * 60)

        all_passed = True
        for user_input, expected_type in test_inputs:
            try:
                # 分类任务
                task_type = await manager.classify_task(user_input)

                # 选择模型
                model_key, selected_client = await manager.select_model(task_type)

                if task_type == expected_type:
                    print(f"[通过] 输入: '{user_input}'")
                    print(f"   分类: {task_type.value}")
                    print(f"   选择模型: {model_key} ({selected_client.model})")
                    print()
                else:
                    print(f"[警告] 输入: '{user_input}'")
                    print(f"   预期分类: {expected_type.value}")
                    print(f"   实际分类: {task_type.value}")
                    print(f"   选择模型: {model_key}")
                    all_passed = False
                    print()

            except Exception as e:
                print(f"[错误] 测试失败: '{user_input}' - {e}")
                all_passed = False
                print()

        if all_passed:
            print("=" * 60)
            print("[成功] 所有测试通过！")
            print("=" * 60)
        else:
            print("=" * 60)
            print("[警告] 部分测试未通过，但功能基本正常")
            print("=" * 60)

        return all_passed

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration_with_decision_hub():
    """测试与DecisionHub的集成"""
    print("\n" + "=" * 60)
    print("测试与DecisionHub的集成")
    print("=" * 60)

    try:
        from hub.decision_hub import DecisionHub

        # 检查DecisionHub是否有multi_model_manager属性
        import inspect
        sig = inspect.signature(DecisionHub.__init__)

        if 'multi_model_manager' in sig.parameters:
            print("[成功] DecisionHub 支持多模型管理器参数")
        else:
            print("[错误] DecisionHub 缺少多模型管理器参数")
            return False

        return True

    except Exception as e:
        print(f"[错误] 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n[测试] 多模型功能测试\n")

    # 运行测试
    test1_passed = await test_multi_model_classification()
    test2_passed = await test_integration_with_decision_hub()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"多模型分类测试: {'[通过]' if test1_passed else '[失败]'}")
    print(f"DecisionHub集成测试: {'[通过]' if test2_passed else '[失败]'}")

    if test1_passed and test2_passed:
        print("\n[成功] 所有测试通过！多模型功能正常工作。")
    else:
        print("\n[警告] 部分测试未通过，请检查配置和代码。")


if __name__ == '__main__':
    asyncio.run(main())
