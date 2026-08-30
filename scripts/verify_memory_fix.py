"""
V4.1.12 记忆系统修复验证脚本（临时目录，不影响线上数据）
"""
import asyncio
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TEMP_DIR = Path("data/test_memory_fix_v4112")


async def main():
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    from memory import get_memory_core, reset_memory_core
    from memory.models import MemoryLevel

    reset_memory_core()
    core = await get_memory_core(str(TEMP_DIR))
    await core.initialize(lazy_load=False)

    print("=" * 64)
    print("[1] 跨平台身份归一存储")
    print("=" * 64)
    # 佳在三个平台各存一条记忆（不同平台 ID）
    await core.store(content="佳在QQ上说他喜欢青色", user_id="1523878699", level=MemoryLevel.LONG_TERM, tags=["喜好"])
    await core.store(content="佳在桌面端说他喜欢薄荷牙膏", user_id="desktop_user", level=MemoryLevel.LONG_TERM, tags=["喜好"])
    await core.store(content="佳在微信说他喜欢桂花香", user_id="o9cq806WYR-N8Zxxg94EyHYgUXwY@im.wechat", level=MemoryLevel.LONG_TERM, tags=["喜好"])

    # 从任意平台 ID 检索都应能跨平台命中全部三条
    for probe_id in ["1523878699", "desktop_user", "default", "0"]:
        results = await core.retrieve(query="", user_id=probe_id, limit=50)
        contents = [r.content for r in results]
        print(f"  检索 user_id={probe_id!r}: {len(results)} 条 -> {contents}")
        assert len(results) >= 3, f"FAIL: {probe_id} 未跨平台命中全部记忆"

    print()
    print("=" * 64)
    print("[2] 中文关键词召回（FTS 修复）")
    print("=" * 64)
    await core.store(content="佳喜欢喝椰奶、茉莉蜜茶和草莓味香飘飘", user_id="1523878699", level=MemoryLevel.LONG_TERM, tags=["喜好", "饮品"])
    await core.store(content="佳的生日是2005年3月20日", user_id="1523878699", level=MemoryLevel.LONG_TERM, tags=["生日"])

    for q in ["椰奶", "香飘飘", "生日", "佳喜欢喝什么", "喜欢什么颜色"]:
        results = await core.retrieve(query=q, user_id="1523878699", limit=10)
        contents = [r.content[:30] for r in results]
        print(f"  查询 {q!r}: {len(results)} 条 -> {contents}")

    results = await core.retrieve(query="椰奶", user_id="1523878699", limit=10)
    assert any("椰奶" in r.content for r in results), "FAIL: 中文关键词召回失败"
    results = await core.retrieve(query="生日", user_id="1523878699", limit=10)
    assert any("生日" in r.content for r in results), "FAIL: 生日召回失败"

    print()
    print("=" * 64)
    print("[3] 记忆锚点加载幂等性")
    print("=" * 64)
    n1 = await core.reload_memory_anchors()
    n2 = await core.reload_memory_anchors()
    print(f"  第一次重载新增: {n1}, 第二次重载新增: {n2}")
    assert n2 == 0, "FAIL: 锚点重复加载"

    # 用户锚点应可从任意平台 ID 检索到（规范桶）
    results = await core.retrieve(query="", user_id="desktop_user", tags=["健康"], limit=50)
    print(f"  从 desktop_user 检索健康锚点: {len(results)} 条")
    assert any("心脏病" in r.content for r in results), "FAIL: 锚点跨平台不可见"

    print()
    print("=" * 64)
    print("[4] 群聊软过滤（跨群召回）")
    print("=" * 64)
    await core.store(content="佳在群里A说最近在研究网络安全", user_id="1523878699", group_id="10001", level=MemoryLevel.LONG_TERM)
    results = await core.retrieve(query="网络安全", user_id="1523878699", group_id="20002", limit=10)
    print(f"  群B(20002)检索群A(10001)的记忆: {len(results)} 条 -> {[r.content[:20] for r in results]}")
    assert len(results) >= 1, "FAIL: 群聊间记忆分裂未修复"

    print()
    print("=" * 64)
    print("[5] 非佳用户隔离（隐私不受影响）")
    print("=" * 64)
    await core.store(content="路人甲的偏好：喜欢咖啡", user_id="2911746585", level=MemoryLevel.LONG_TERM, tags=["喜好"])
    results = await core.retrieve(query="", user_id="1523878699", tags=["喜好"], limit=100)
    assert not any("路人甲" in r.content for r in results), "FAIL: 用户隔离被破坏"
    results = await core.retrieve(query="", user_id="2911746585", limit=50)
    assert any("路人甲" in r.content for r in results), "FAIL: 其他用户记忆丢失"
    print("  佳的记忆桶不含路人甲内容 ✓ ; 路人甲自己的记忆可检索 ✓")

    print()
    print("ALL FIX CHECKS PASSED ✓")


if __name__ == "__main__":
    asyncio.run(main())
