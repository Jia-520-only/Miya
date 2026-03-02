"""
记忆数据导出脚本
导出所有记忆系统（对话历史、Undefined 记忆、潮汐记忆）
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

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
    print("弥娅记忆数据导出")
    print("=" * 60)

    try:
        # 获取记忆系统初始化器
        initializer = await get_memory_system_initializer()

        # 导出所有数据
        export_dir = Path("data/export")
        export_files = await initializer.export_all(export_dir)

        print("\n" + "=" * 60)
        print("导出完成")
        print("=" * 60)

        print(f"\n导出目录: {export_dir}")
        print(f"\n导出文件 ({len(export_files)} 个):")
        for name, path in export_files.items():
            print(f"  • {name}: {path}")

        return 0

    except Exception as e:
        logger.error(f"导出失败: {e}", exc_info=True)
        print(f"\n❌ 导出失败: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
