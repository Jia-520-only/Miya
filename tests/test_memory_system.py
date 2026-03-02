"""
记忆系统测试脚本
验证对话历史持久化和 Undefined 记忆系统
"""
import asyncio
import sys
from pathlib import Path

# 修复 Windows 编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_system_initializer import get_memory_system_initializer


async def test_conversation_history():
    """测试对话历史持久化"""
    print("\n" + "=" * 60)
    print("测试对话历史持久化")
    print("=" * 60)

    initializer = await get_memory_system_initializer()
    history_manager = await initializer.get_conversation_history_manager()

    # 测试添加消息
    session_id = "test_session_001"
    await history_manager.add_message(
        session_id=session_id,
        role="user",
        content="你好，弥娅！",
        agent_id="miya_default"
    )

    await history_manager.add_message(
        session_id=session_id,
        role="assistant",
        content="你好！我是弥娅，很高兴见到你。",
        agent_id="miya_default"
    )

    # 测试获取历史
    messages = await history_manager.get_history(session_id)
    print(f"\n✓ 添加了 {len(messages)} 条消息")

    for msg in messages:
        print(f"  - [{msg.role}] {msg.content[:50]}...")

    # 测试统计
    stats = await history_manager.get_statistics()
    print(f"\n✓ 统计信息:")
    print(f"  总会话: {stats['total_sessions']}")
    print(f"  总消息: {stats['total_messages']}")

    print("\n✅ 对话历史持久化测试通过！")


async def test_undefined_memory():
    """测试 Undefined 记忆系统"""
    print("\n" + "=" * 60)
    print("测试 Undefined 记忆系统")
    print("=" * 60)

    initializer = await get_memory_system_initializer()
    undefined_memory = await initializer.get_undefined_memory()

    # 测试添加记忆
    uuid1 = await undefined_memory.add(
        fact="用户喜欢使用 Python 编程",
        tags=["编程", "Python", "偏好"]
    )

    uuid2 = await undefined_memory.add(
        fact="用户喜欢吃巧克力",
        tags=["食物", "偏好"]
    )

    print(f"\n✓ 添加了 2 条记忆")
    print(f"  - {uuid1}")
    print(f"  - {uuid2}")

    # 测试查询记忆
    all_memories = await undefined_memory.get_all()
    print(f"\n✓ 当前记忆数量: {len(all_memories)}")

    for mem in all_memories:
        print(f"  - [{mem.tags}] {mem.fact}")

    # 测试搜索
    results = await undefined_memory.search("Python")
    print(f"\n✓ 搜索 'Python': {len(results)} 条结果")

    for mem in results:
        print(f"  - {mem.fact}")

    print("\n✅ Undefined 记忆系统测试通过！")


async def test_integration():
    """测试集成功能"""
    print("\n" + "=" * 60)
    print("测试记忆系统集成")
    print("=" * 60)

    initializer = await get_memory_system_initializer()

    # 获取所有统计信息
    stats = await initializer.get_statistics()

    print("\n✓ 完整统计信息:")
    print(f"\n对话历史:")
    print(f"  • 总会话: {stats['conversation_history']['total_sessions']}")
    print(f"  • 总消息: {stats['conversation_history']['total_messages']}")
    print(f"  • 缓存会话: {stats['conversation_history']['cached_sessions']}")

    print(f"\nUndefined 记忆:")
    print(f"  • 数量: {stats['undefined_memory']['count']}")
    print(f"  • 文件: {stats['undefined_memory']['file']}")

    print(f"\n潮汐记忆:")
    print(f"  • 数量: {stats['tide_memory']['count']}")
    print(f"  • Redis: {stats['tide_memory']['redis_available']}")

    print(f"\n梦境压缩:")
    print(f"  • 数量: {stats['dream_memory']['count']}")
    print(f"  • Milvus: {stats['dream_memory']['milvus_available']}")

    print("\n✅ 集成测试通过！")


async def main():
    """主函数"""
    print("=" * 60)
    print("弥娅记忆系统测试")
    print("=" * 60)

    try:
        # 运行测试
        await test_conversation_history()
        await test_undefined_memory()
        await test_integration()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
