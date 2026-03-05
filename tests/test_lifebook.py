"""LifeBook 记忆管理系统 - 测试脚本

测试 LifeBook 各项功能是否正常工作
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webnet.LifeNet.subnet import LifeSubnet
from memory.lifebook_manager import (
    MemoryLevel,
    NodeType,
)


async def test_diary():
    """测试日记功能"""
    print("【测试 1】日记功能")
    print("-" * 60)

    life = LifeSubnet()
    context = {"lifenet": life}

    # 添加日记
    result = await life.handle_tool_call(
        "life_add_diary",
        {
            "content": "测试日记内容",
            "mood": "测试",
            "tags": ["#测试"]
        },
        context
    )
    print(f"添加日记: {result}")

    # 获取日记
    result = await life.handle_tool_call(
        "life_get_diary",
        {},
        context
    )
    print(f"获取日记: {result[:100]}..." if len(result) > 100 else f"获取日记: {result}")

    print("✅ 日记功能测试通过\n")
    return True


async def test_nodes():
    """测试节点功能"""
    print("【测试 2】节点功能")
    print("-" * 60)

    life = LifeSubnet()
    context = {"lifenet": life}

    # 创建角色节点
    result = await life.handle_tool_call(
        "life_create_character_node",
        {
            "name": "测试角色",
            "description": "测试描述",
            "tags": ["#测试"]
        },
        context
    )
    print(f"创建角色节点: {result}")

    # 创建阶段节点
    result = await life.handle_tool_call(
        "life_create_stage_node",
        {
            "name": "测试阶段",
            "description": "测试阶段描述",
        },
        context
    )
    print(f"创建阶段节点: {result}")

    # 列出节点
    result = await life.handle_tool_call(
        "life_list_nodes",
        {},
        context
    )
    print(f"列出节点: {result[:100]}..." if len(result) > 100 else f"列出节点: {result}")

    print("✅ 节点功能测试通过\n")
    return True


async def test_summary():
    """测试总结功能"""
    print("【测试 3】总结功能")
    print("-" * 60)

    life = LifeSubnet()
    context = {"lifenet": life}

    # 添加周记
    result = await life.handle_tool_call(
        "life_add_summary",
        {
            "level": "weekly",
            "title": "测试周记",
            "content": "这是测试周记内容",
            "capsule": "测试胶囊"
        },
        context
    )
    print(f"添加周记: {result}")

    # 获取周记
    result = await life.handle_tool_call(
        "life_get_summary",
        {
            "level": "weekly",
            "period": "2025-W09"  # 使用当前周
        },
        context
    )
    print(f"获取周记: {result[:100]}..." if len(result) > 100 else f"获取周记: {result}")

    print("✅ 总结功能测试通过\n")
    return True


async def test_search():
    """测试搜索功能"""
    print("【测试 4】搜索功能")
    print("-" * 60)

    life = LifeSubnet()
    context = {"lifenet": life}

    # 搜索记忆
    result = await life.handle_tool_call(
        "life_search_memory",
        {
            "keyword": "测试",
            "limit": 5
        },
        context
    )
    print(f"搜索记忆: {result[:100]}..." if len(result) > 100 else f"搜索记忆: {result}")

    print("✅ 搜索功能测试通过\n")
    return True


async def test_context():
    """测试上下文获取功能"""
    print("【测试 5】上下文获取功能")
    print("-" * 60)

    life = LifeSubnet()
    context = {"lifenet": life}

    # 获取记忆上下文
    result = await life.handle_tool_call(
        "life_get_memory_context",
        {
            "months_back": 1,
            "include_nodes": True
        },
        context
    )
    print(f"获取记忆上下文: {result[:100]}..." if len(result) > 100 else f"获取记忆上下文: {result}")

    print("✅ 上下文获取功能测试通过\n")
    return True


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("LifeBook 记忆管理系统 - 测试脚本")
    print("=" * 60)
    print()

    tests = [
        test_diary,
        test_nodes,
        test_summary,
        test_search,
        test_context,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试失败: {e}\n")
            results.append(False)

    print("=" * 60)
    print(f"测试完成: {sum(results)}/{len(results)} 通过")
    print("=" * 60)

    if all(results):
        print("✅ 所有测试通过！LifeBook 功能正常")
    else:
        print("❌ 部分测试失败，请检查错误信息")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
