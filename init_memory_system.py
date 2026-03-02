"""
记忆系统快速初始化脚本
用于立即启用对话历史持久化和 Undefined 记忆系统
"""
import asyncio
import logging
import sys
from pathlib import Path

# 修复 Windows 编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.memory_system_initializer import get_memory_system_initializer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    print("=" * 60)
    print("弥娅记忆系统快速初始化")
    print("=" * 60)

    try:
        # 初始化记忆系统
        initializer = await get_memory_system_initializer()

        # 获取统计信息
        print("\n" + "=" * 60)
        print("记忆系统状态")
        print("=" * 60)

        stats = await initializer.get_statistics()
        print(f"\n对话历史:")
        print(f"  • 总会话数: {stats['conversation_history']['total_sessions']}")
        print(f"  • 总消息数: {stats['conversation_history']['total_messages']}")
        print(f"  • 缓存会话: {stats['conversation_history']['cached_sessions']}")

        print(f"\nUndefined 记忆:")
        print(f"  • 记忆数量: {stats['undefined_memory']['count']}")
        print(f"  • 存储文件: {stats['undefined_memory']['file']}")

        print(f"\n潮汐记忆:")
        print(f"  • 记忆数量: {stats['tide_memory']['count']}")
        print(f"  • Redis: {'已连接' if stats['tide_memory']['redis_available'] else '模拟模式'}")

        print(f"\n梦境压缩:")
        print(f"  • 记忆数量: {stats['dream_memory']['count']}")
        print(f"  • Milvus: {'已连接' if stats['dream_memory']['milvus_available'] else '模拟模式'}")

        print("\n" + "=" * 60)
        print("✅ 记忆系统初始化成功！")
        print("=" * 60)

        # 提示信息
        print("\n提示:")
        print("  • 对话历史已持久化到: data/conversations/")
        print("  • Undefined 记忆已启用")
        print("  • 可选配置: Redis/ChromaDB 作为后端")
        print("  • 运行 export_memory.py 导出所有记忆数据")

        return 0

    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"\n❌ 初始化失败: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
