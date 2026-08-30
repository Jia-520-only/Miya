#!/usr/bin/env python3
"""
测试动态消息生成系统
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_dynamic_system():
    """测试动态消息生成系统"""
    print("测试动态消息生成系统...")

    try:
        # 导入动态消息生成器
        from config.proactive_chat.config.loader import ProactiveChatConfigLoader
        from config.proactive_chat.dynamic_message_generator import (
            DynamicMessageGenerator,
        )

        print("[OK] 导入模块成功")

        # 创建配置加载器
        config_loader = ProactiveChatConfigLoader()
        print("[OK] 创建配置加载器成功")

        # 创建动态消息生成器
        generator = DynamicMessageGenerator(config_loader)
        print("[OK] 创建动态消息生成器成功")

        # 初始化生成器
        await generator.initialize()
        print("[OK] 初始化动态消息生成器成功")

        # 测试生成消息
        user_id = 123456789
        context = {"last_message": "我去上课了", "timestamp": "2026-03-28T10:00:00"}

        message = await generator.generate_message(user_id, context)
        if message:
            print(f"[OK] 生成的消息: {message}")
        else:
            print("[OK] 没有生成消息（正常情况）")

        # 获取统计信息
        stats = generator.get_stats()
        print(f"[OK] 统计信息: {stats}")

        # 关闭生成器
        await generator.shutdown()
        print("[OK] 关闭生成器成功")

        return True
    except ModuleNotFoundError as e:
        print(f"[SKIP] 模块不存在，跳过测试: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_time_awareness_plugin():
    """测试时间感知插件"""
    print("\n测试时间感知插件...")

    try:
        from config.proactive_chat.plugins.time_awareness.plugin import Plugin

        # 创建插件实例
        plugin = Plugin(config={})
        print("[OK] 创建时间感知插件成功")

        # 收集上下文
        context = await plugin.collect_context(123456789)
        print(f"[OK] 收集的上下文: {context}")

        # 生成消息
        message = await plugin.generate({"time_awareness": context})
        print(f"[OK] 生成的消息: {message}")

        return True
    except ModuleNotFoundError as e:
        print(f"[SKIP] 模块不存在，跳过测试: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 时间感知插件测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("动态消息生成系统测试")
    print("=" * 60)

    # 测试时间感知插件
    time_result = await test_time_awareness_plugin()

    # 测试完整系统
    system_result = await test_dynamic_system()

    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("=" * 60)
    print(f"时间感知插件: {'[OK] 通过' if time_result else '[ERROR] 失败'}")
    print(f"完整系统测试: {'[OK] 通过' if system_result else '[ERROR] 失败'}")

    if time_result and system_result:
        print("\n[OK] 所有测试通过！")
        return 0
    else:
        print("\n[ERROR] 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
