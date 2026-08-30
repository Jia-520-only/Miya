"""
主动聊天模块稳定性测试
"""

import asyncio
import logging
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_proactive_chat():
    """测试主动聊天系统"""
    # 重置全局实例以便测试
    import core.proactive_chat as proactive_module
    from core.proactive_chat import (
        ChatContext,
        get_proactive_chat_system,
    )

    proactive_module._proactive_system = None

    # 获取实例
    system = get_proactive_chat_system()

    # 模拟设置 AI 客户端（mock）
    class MockAIClient:
        async def chat(self, messages, max_tokens=50, temperature=0.7):
            return {"choices": [{"message": {"content": "今天过得怎么样？"}}]}

    system.set_ai_client(MockAIClient())
    system.set_personality(None)

    print("=" * 50)
    print("测试 1: 系统初始化")
    print(f"  启用状态: {system.is_enabled()}")
    print(f"  关键词触发: {system.is_trigger_enabled('keyword')}")
    print(f"  时间触发: {system.is_trigger_enabled('time')}")
    print(f"  上下文触发: {system.is_trigger_enabled('context')}")
    print(f"  情绪触发: {system.is_trigger_enabled('emotion')}")
    print(f"  关怀触发: {system.is_trigger_enabled('check_in')}")
    print(f"  AI触发: {system.is_trigger_enabled('ai')}")

    print("\n" + "=" * 50)
    print("测试 2: 关键词触发")

    # 创建上下文
    ctx = ChatContext(chat_type="group", target_id=123456, group_name="测试群", member_count=5)
    system.update_context(123456, ctx)
    await system.record_message(123456, "group", "在吗")

    result = await system.check_and_respond(123456, "在吗")
    if result:
        print(f"  触发类型: {result.trigger_type}")
        print(f"  消息: {result.message}")
    else:
        print("  无触发（可能因为冷却/重复检测）")

    print("\n" + "=" * 50)
    print("测试 3: 上下文触发（行为期望跟进）")

    # 模拟用户说"下班了"
    ctx2 = ChatContext(
        chat_type="private",
        target_id=789012,
    )
    system.update_context(789012, ctx2)
    await system.record_message(789012, "private", "我下班了")

    # 清除冷却以便测试
    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    result2 = await system.check_and_respond(789012, "我下班了")
    if result2:
        print(f"  触发类型: {result2.trigger_type}")
        print(f"  消息: {result2.message}")
    else:
        print("  无触发")

    print("\n" + "=" * 50)
    print("测试 4: 情绪触发")

    # 模拟用户表达伤心
    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    ctx3 = ChatContext(chat_type="private", target_id=111222, detected_emotion="sad")
    system.update_context(111222, ctx3)
    await system.record_message(111222, "private", "我好伤心")

    result3 = await system.check_and_respond(111222, "我好伤心")
    if result3:
        print(f"  触发类型: {result3.trigger_type}")
        print(f"  消息: {result3.message}")
    else:
        print("  无触发（情绪触发有30%概率）")

    print("\n" + "=" * 50)
    print("测试 5: 时间触发")

    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    ctx4 = ChatContext(
        chat_type="private",
        target_id=333444,
    )
    system.update_context(333444, ctx4)

    result4 = await system.check_and_respond(333444)
    if result4:
        print(f"  触发类型: {result4.trigger_type}")
        print(f"  消息: {result4.message}")
    else:
        print("  无触发（可能在静默时段或无问候语配置）")

    print("\n" + "=" * 50)
    print("测试 6: 速率限制")

    # 快速多次触发测试
    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    ctx5 = ChatContext(
        chat_type="private",
        target_id=555666,
    )
    system.update_context(555666, ctx5)

    trigger_count = 0
    for i in range(15):
        system._message_cache.clear()  # 清除重复检测以便测试速率限制
        result = await system.check_and_respond(555666)
        if result:
            trigger_count += 1
            print(f"  第{i + 1}次: 触发 - {result.message}")
        else:
            print(f"  第{i + 1}次: 被限制")

    print(f"  总触发次数: {trigger_count}/15 (每日限制: {system._max_daily})")

    print("\n" + "=" * 50)
    print("测试 7: 静默时段检测")

    from datetime import datetime

    original_quiet_hours = system._quiet_hours
    original_enabled = system._quiet_hours_enabled

    # 模拟静默时段
    system._quiet_hours = [datetime.now().hour]  # 当前小时设为静默
    system._quiet_hours_enabled = True

    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    ctx6 = ChatContext(
        chat_type="private",
        target_id=777888,
    )
    system.update_context(777888, ctx6)

    result6 = await system.check_and_respond(777888)
    if result6:
        print("  结果: 触发（异常）")
    else:
        print("  结果: 被静默时段阻止（正常）")

    # 恢复设置
    system._quiet_hours = original_quiet_hours
    system._quiet_hours_enabled = original_enabled

    print("\n" + "=" * 50)
    print("测试 8: 消息去重")

    system._last_trigger_time.clear()
    system._daily_count.clear()
    system._hourly_count.clear()
    system._message_cache.clear()

    ctx7 = ChatContext(
        chat_type="private",
        target_id=999000,
    )
    system.update_context(999000, ctx7)

    # 第一次触发
    result7a = await system.check_and_respond(999000)
    msg1 = result7a.message if result7a else None

    # 立即再次触发（应该被去重）
    result7b = await system.check_and_respond(999000)

    if result7a and not result7b:
        print(f"  第一次: {msg1}")
        print("  第二次: 被去重（正常）")
    else:
        print(f"  第一次: {msg1}")
        print(f"  第二次: {'触发' if result7b else '被阻止'}")

    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_proactive_chat())
