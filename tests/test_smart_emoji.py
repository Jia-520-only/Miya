#!/usr/bin/env python3
"""
智能表情包系统演示
测试语义分析、智能匹配和自动标签功能
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def test_smart_emoji_system():
    """测试智能表情包系统"""
    from utils.emoji_manager import get_emoji_manager

    print("\n" + "=" * 60)
    print("智能表情包系统 v2.0 - 功能演示")
    print("=" * 60 + "\n")

    em = get_emoji_manager()

    print("1. 表情包仓库状态")
    print("-" * 40)
    stats = em.get_stats()
    print(f"   表情包总数: {stats['total_emojis']}")
    print(f"   贴纸总数: {stats['total_stickers']}")
    print(f"   已标记标签: {stats['total_tags']}")
    print(f"   可用分类: {', '.join(stats['categories'])}")

    print("\n2. 语义标签示例")
    print("-" * 40)
    for path, tags in list(em.emoji_tags.items())[:3]:
        name = os.path.basename(path)
        print(f"   {name}: {tags}")

    print("\n3. 消息语义分析测试")
    print("-" * 40)

    test_messages = [
        ("今天好开心啊！", "开心情感"),
        ("我好难过...", "难过情感"),
        ("你这个人真讨厌！", "生气情感"),
        ("哇，好厉害！", "惊讶+得意"),
        ("早安！", "问候场景"),
        ("谢谢你的帮助", "感谢场景"),
        ("生日快乐！", "祝福场景"),
        ("你好呀", "普通问候"),
        ("嗯嗯，我知道了", "确认回复"),
        ("哈哈哈哈哈", "强烈开心"),
    ]

    for msg, desc in test_messages:
        analysis = em.analyze_message(msg)
        should = "发送" if analysis["should_send"] else "跳过"
        tags = ", ".join(analysis["suggested_tags"][:2]) if analysis["suggested_tags"] else "无"
        sentiment = ", ".join(list(analysis["sentiment"].keys())[:2]) if analysis["sentiment"] else "无"
        print(f"   [{should:4s}] {msg:15s} | {desc:10s} | 情感:{sentiment:8s} | 标签:{tags}")

    print("\n4. 语义检索测试")
    print("-" * 40)

    search_queries = [
        "弥娅好可爱",
        "今天好开心",
        "生日快乐",
        "谢谢",
        "加油努力",
    ]

    for query in search_queries:
        results = em.smart_search(query, limit=3)
        print(f'\n   搜索: "{query}"')
        if results:
            for i, r in enumerate(results[:3], 1):
                tags = em.emoji_tags.get(r["path"], [])
                print(f"      {i}. {r['name']} [标签: {', '.join(tags[:3])}]")
        else:
            print("      (无匹配结果)")

    print("\n5. 上下文感知测试")
    print("-" * 40)

    context_tests = [
        "我今天考试考砸了...",
        "太好了！我的代码终于跑通了！",
        "你好，我是新来的",
        "这台电脑的配置真差",
        "晚安，祝你做个好梦",
    ]

    for msg in context_tests:
        emoji = em.get_emoji_by_context(msg)
        if emoji:
            print(f'   "{msg}"')
            print(f"     -> 推荐: {emoji['name']}")
            print(f"     -> 标签: {em.emoji_tags.get(emoji['path'], [])}")
        else:
            print(f'   "{msg}" -> 不发送表情包')

    print("\n" + "=" * 60)
    print("智能表情包系统测试完成！")
    print("=" * 60 + "\n")

    print("功能说明:")
    print("- 自动为表情包生成语义标签")
    print("- 根据用户消息情感选择合适的表情包")
    print("- 支持关键词匹配和语义检索")
    print("- 上下文感知触发，无需明确请求")
    print("\n使用方式:")
    print("- 用户: '发个表情包' / '随机表情'")
    print("- 弥娅自动判断: 根据对话内容自动发送")
    print("- 管理: '分析一下这句话' -> 查看语义分析详情")


def main():
    try:
        test_smart_emoji_system()
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
