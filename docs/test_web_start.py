"""
测试 Web 模式启动
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试必要的导入"""
    print("测试导入...")
    try:
        import asyncio
        print("  ✓ asyncio")

        import uvicorn
        print("  ✓ uvicorn")

        from fastapi import FastAPI
        print("  ✓ FastAPI")

        from fastapi.middleware.cors import CORSMiddleware
        print("  ✓ CORSMiddleware")

        print("\n✅ 所有依赖导入成功")
        return True
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        return False


def test_config():
    """测试配置文件"""
    print("\n测试配置文件...")
    try:
        from dotenv import load_dotenv
        from pathlib import Path

        env_path = project_root / 'config' / '.env'
        if not env_path.exists():
            print(f"  ❌ 配置文件不存在: {env_path}")
            return False

        load_dotenv(env_path)
        print(f"  ✓ 配置文件加载成功: {env_path}")

        # 检查必要的环境变量
        import os
        required_vars = []
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            print(f"  ⚠️  缺少环境变量: {', '.join(missing_vars)}")

        print("\n✅ 配置文件检查完成")
        return True
    except Exception as e:
        print(f"\n❌ 配置测试失败: {e}")
        return False


def test_core_system():
    """测试核心系统初始化"""
    print("\n测试核心系统初始化...")
    try:
        from run.main import Miya
        import asyncio

        print("  创建 Miya 实例...")
        miya = Miya()

        print("  ✓ Miya 实例创建成功")
        print(f"  ✓ 身份: {miya.identity.name}")

        print("\n✅ 核心系统初始化成功")
        return True
    except Exception as e:
        print(f"\n❌ 核心系统初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_web_api():
    """测试 Web API"""
    print("\n测试 Web API...")
    try:
        from core.web_api import create_web_api
        print("  ✓ Web API 导入成功")

        print("\n✅ Web API 测试完成")
        return True
    except Exception as e:
        print(f"\n❌ Web API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("        弥娅 Web 模式测试")
    print("        Miya Web Test")
    print("=" * 50)
    print()

    results = []

    # 运行测试
    results.append(("依赖导入", test_imports()))
    results.append(("配置文件", test_config()))

    # 核心系统测试（较慢）
    print("\n提示: 核心系统初始化可能需要一些时间...")
    response = input("是否继续测试核心系统? (y/n): ").lower().strip()

    if response == 'y':
        results.append(("核心系统", test_core_system()))
        results.append(("Web API", test_web_api()))

    # 显示结果
    print("\n" + "=" * 50)
    print("        测试结果汇总")
    print("=" * 50)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    print()

    # 总体结果
    all_passed = all(result for _, result in results)
    if all_passed:
        print("✅ 所有测试通过！Web 模式可以正常启动。")
        print("\n启动命令:")
        print("  Windows: run/web_start.bat")
        print("  Linux/macOS: ./run/web_start.sh")
    else:
        print("❌ 部分测试失败，请检查上述错误信息。")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
