"""
运行Miya AI集成测试的快捷脚本
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration_test_scenarios import run_all_integration_tests

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Miya AI 集成测试启动器")
    print("=" * 60)
    print()

    try:
        result = asyncio.run(run_all_integration_tests())

        # 根据测试结果设置退出码
        if result["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试运行失败: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
