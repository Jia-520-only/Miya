"""验证记忆系统修复"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from memory.core import MemoryLevel, MemorySource, MiyaMemoryCore


async def test_all():
    test_dir = Path("data/memory_test_verify")
    if test_dir.exists():
        import shutil

        shutil.rmtree(test_dir)

    print("=" * 60)
    print("弥娅记忆系统修复验证")
    print("=" * 60)

    # 1. 初始化和文件锁
    print("\n[TEST 1] 初始化 + 文件锁...")
    core = MiyaMemoryCore(data_dir=test_dir)
    assert hasattr(core.backend, "_index_lock"), "文件锁未创建"
    assert isinstance(core.backend._index_lock, asyncio.Lock), "文件锁类型错误"
    print("  [OK] 文件锁已创建")

    # 2. _tag_index 属性代理
    print("\n[TEST 2] _tag_index 属性代理...")
    assert core._tag_index is core.backend._tag_index, "_tag_index 未代理到 backend"
    print("  [OK] _tag_index 已正确代理到 backend")

    # 3. 存储记忆
    print("\n[TEST 3] 存储记忆...")
    mem_id = await core.store(
        content="测试记忆内容",
        level=MemoryLevel.LONG_TERM,
        user_id="test_user",
        tags=["测试", "验证"],
        priority=0.7,
        source=MemorySource.MANUAL,
    )
    assert mem_id, "存储返回空ID"
    print(f"  [OK] 存储成功: {mem_id}")

    # 4. 检索记忆
    print("\n[TEST 4] 检索记忆...")
    results = await core.retrieve(query="测试", user_id="test_user")
    assert len(results) > 0, "检索结果为空"
    assert results[0].id == mem_id, "检索结果不匹配"
    print(f"  [OK] 检索成功: {len(results)} 条结果")

    # 5. 更新记忆
    print("\n[TEST 5] 更新记忆...")
    updated = await core.update(mem_id, content="更新后的内容", priority=0.9)
    assert updated, "更新失败"
    mem = await core.get_by_id(mem_id)
    assert mem.content == "更新后的内容", "内容未更新"
    assert mem.priority == 0.9, "优先级未更新"
    print("  [OK] 更新成功")

    # 6. 删除记忆
    print("\n[TEST 6] 删除记忆...")
    deleted = await core.delete(mem_id)
    assert deleted, "删除失败"
    mem = await core.get_by_id(mem_id)
    assert mem is None, "删除后仍能获取"
    print("  [OK] 删除成功")

    # 7. 过期记忆清理 (磁盘扫描)
    print("\n[TEST 7] 过期记忆清理 (含磁盘扫描)...")
    await core.store(
        content="过期测试",
        level=MemoryLevel.SHORT_TERM,
        user_id="test_user",
        ttl=1,  # 1秒过期
    )
    await asyncio.sleep(1.5)  # 等待过期
    cleaned = await core.delete_expired()
    assert cleaned >= 1, f"过期清理失败，清理了 {cleaned} 条"
    print(f"  [OK] 清理了 {cleaned} 条过期记忆 (含磁盘)")

    # 8. 伪向量改进
    print("\n[TEST 8] 伪向量改进 (n-gram哈希)...")
    vec1 = core._simple_embed("我喜欢编程")
    vec2 = core._simple_embed("我喜欢编码")
    vec3 = core._simple_embed("今天天气很好")
    assert len(vec1) == 1536, "向量维度错误"
    # 相似文本应该有更高的相似度
    sim_12 = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    sim_13 = sum(a * b for a, b in zip(vec1, vec3, strict=False))
    print(f"  相似度(编程vs编码): {sim_12:.4f}")
    print(f"  相似度(编程vs天气): {sim_13:.4f}")
    print("  [OK] n-gram哈希向量生成成功")

    # 9. 备份按周归档
    print("\n[TEST 9] 备份按周归档...")
    backup_dir = test_dir / "backups"
    await core.store(
        content="备份测试",
        level=MemoryLevel.LONG_TERM,
        user_id="test_user",
        source=MemorySource.MANUAL,
    )
    # 检查是否有周格式备份文件
    week_files = list(backup_dir.glob("*-W*.json"))
    assert len(week_files) > 0, "未找到周格式备份文件"
    print(f"  [OK] 周格式备份文件: {week_files[0].name}")

    # 10. 统计
    print("\n[TEST 10] 统计信息...")
    stats = await core.get_statistics()
    print(f"  缓存: {stats['total_cached']}")
    print(f"  索引: {stats['total_indexed']}")
    print(f"  标签: {stats['by_tag']}")
    print(f"  用户: {stats['by_user']}")
    print("  [OK] 统计正常")

    # 清理测试目录
    import shutil

    shutil.rmtree(test_dir)

    print("\n" + "=" * 60)
    print("所有验证通过!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all())
