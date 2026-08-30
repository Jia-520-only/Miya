"""
弥娅统一记忆系统 V3.1 全面测试
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest


async def test_1_init():
    """测试1: 初始化"""
    print("\n" + "=" * 60)
    print("[TEST 1] Initialization")
    print("=" * 60)

    from memory.core import get_memory_core, reset_memory_core

    reset_memory_core()

    core = await get_memory_core("data/test_memory_v31")
    print("[OK] Core initialized")
    print(f"[OK] Data dir: {core.data_dir}")

    stats = await core.get_statistics()
    print(f"[OK] Stats: {stats}")

    return core


async def test_6_bus():
    """测试6: MemoryBus 核心 API"""
    print("\n" + "=" * 60)
    print("[TEST 6] MemoryBus API")
    print("=" * 60)

    from memory import get_memory_bus

    bus = await get_memory_bus()
    print("[OK] MemoryBus initialized")

    # 存储对话
    msg_id = await bus.store_dialogue(
        content="测试消息",
        role="user",
        user_id="bus_test",
        session_id="bus_session",
    )
    print(f"[OK] store_dialogue: {msg_id}")

    # 获取会话
    messages = await bus.get_dialogue_history(session_id="bus_session")
    print(f"[OK] dialogue_history: {len(messages)} messages")

    # 存储重要记忆
    mem_id = await bus.store_important(
        content="这是测试记忆",
        user_id="bus_test",
        tags=["测试"],
    )
    print(f"[OK] store_important: {mem_id}")

    # 搜索
    result = await bus.recall("测试", user_id="bus_test", limit=10)
    print(f"[OK] recall: {result.total_found} results")

    # 统计
    stats = await bus.stats()
    print(f"[OK] stats: {stats.get('total_cached', 0)} cached")

    return bus


async def test_7_auto_extract():
    """测试7: 自动提取 (通过 MemoryBus)"""
    print("\n" + "=" * 60)
    print("[TEST 7] Auto Extract")
    print("=" * 60)

    from memory import get_memory_bus

    bus = await get_memory_bus()

    test_items = [
        ("我叫小明，喜欢唱歌", "extract_test", ["偏好", "个人信息"]),
        ("记住我的生日是5月20日", "extract_test", ["生日", "重要"]),
        ("我的电话是13800138000", "extract_test", ["联系方式"]),
        ("我讨厌数学课", "extract_test", ["偏好", "负面"]),
        ("别忘了明天开会", "extract_test", ["提醒", "事件"]),
    ]

    for content, uid, tags in test_items:
        mid = await bus.store_auto(content=content, user_id=uid, tags=tags)
        print(f"[OK] '{content[:20]}...' -> {mid}")

    # 验证可检索
    result = await bus.recall("小明", user_id="extract_test")
    print(f"[OK] recall '小明': {result.total_found} results")


async def test_8_convenience():
    """测试8: MemoryBus 便捷调用"""
    print("\n" + "=" * 60)
    print("[TEST 8] MemoryBus Convenience")
    print("=" * 60)

    from memory import get_memory_bus

    bus = await get_memory_bus()

    # 便捷存储
    d_id = await bus.store_dialogue(
        content="便捷对话",
        role="user",
        user_id="convenience",
        session_id="s1",
    )
    print(f"[OK] store_dialogue: {d_id}")

    i_id = await bus.store_important(
        content="便捷重要记忆",
        user_id="convenience",
        tags=["测试"],
    )
    print(f"[OK] store_important: {i_id}")

    # 便捷搜索
    result = await bus.search("便捷", user_id="convenience")
    print(f"[OK] search: {len(result)}")

    # 便捷获取
    mems = await bus.get_user_memories("convenience")
    print(f"[OK] get_user_memories: {len(mems)}")

    # 统计
    stats = await bus.stats()
    print(f"[OK] stats: {stats.get('total_cached', 0)} cached")


async def test_9_performance():
    """测试9: 性能测试"""
    print("\n" + "=" * 60)
    print("[TEST 9] Performance")
    print("=" * 60)

    from memory import get_memory_core, reset_memory_core

    reset_memory_core()
    core = await get_memory_core("data/test_perf")

    # 批量写入性能
    start = time.time()
    for i in range(100):
        await core.store(
            content=f"性能测试 {i}",
            user_id="perf_user",
            session_id="perf_session",
        )
    write_time = time.time() - start
    print(f"[OK] Write 100 items: {write_time:.3f}s ({100 / write_time:.1f}/s)")

    # 批量读取性能
    start = time.time()
    for i in range(100):
        await core.retrieve(query="性能", user_id="perf_user")
    read_time = time.time() - start
    print(f"[OK] Read 100 queries: {read_time:.3f}s ({100 / read_time:.1f}/s)")

    # 统计
    stats = await core.get_statistics()
    print(f"[OK] Final stats: {stats.get('total_cached', 0)} cached")


async def test_10_edge_cases():
    """测试10: 边界情况"""
    print("\n" + "=" * 60)
    print("[TEST 10] Edge Cases")
    print("=" * 60)

    from memory import get_memory_core, reset_memory_core

    reset_memory_core()
    core = await get_memory_core("data/test_edge")

    # 空内容
    try:
        await core.store(content="", user_id="test")
        print("[FAIL] Empty content should fail")
    except:
        print("[OK] Empty content rejected")

    # 特殊字符
    sid = await core.store(
        content="特殊字符: 🎉😂😢 💯👀",
        user_id="test",
    )
    print(f"[OK] Special chars: {sid}")

    # 超长内容
    long_content = "测试内容 " * 1000
    lid = await core.store(content=long_content[:5000], user_id="test")
    print(f"[OK] Long content: {lid}")

    # Unicode
    uid = await core.store(
        content="中文English日本語한국어",
        user_id="test",
    )
    print(f"[OK] Unicode: {uid}")


async def main():
    """主测试"""
    print("\n" + "=" * 60)
    print("  MIYA MEMORY SYSTEM V3.1 COMPREHENSIVE TEST")
    print("=" * 60)

    try:
        # 1. 初始化
        core = await test_1_init()

        # 2. 存储
        await test_2_store(core)

        # 3. 检索
        await test_3_retrieve(core)

        # 4. 更新删除
        await test_4_update_delete(core)

        # 5. 用户画像
        await test_5_profile(core)

        # 6. MemoryBus
        await test_6_bus()

        # 7. 自动提取
        await test_7_auto_extract()

        # 8. 便捷函数
        await test_8_convenience()

        # 9. 性能
        await test_9_performance()

        # 10. 边界情况
        await test_10_edge_cases()

        print("\n" + "=" * 60)
        print("  [SUCCESS] ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
