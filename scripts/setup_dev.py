#!/usr/bin/env python3
"""
开发环境设置脚本
一键设置Miya项目的开发环境
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """运行命令并显示结果"""
    print(f"🚀 {description}...")
    print(f"   $ {cmd}")

    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("   ✅ 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ 失败: {e}")
        print(f"   标准输出: {e.stdout}")
        print(f"   标准错误: {e.stderr}")
        return False


def setup_development_environment():
    """设置开发环境"""
    print("=" * 60)
    print("Miya项目开发环境设置")
    print("=" * 60)

    # 1. 检查Python版本
    print("\n1. 检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"   ❌ 需要Python 3.9+，当前版本: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"   ✅ Python版本: {version.major}.{version.minor}.{version.micro}")

    # 2. 创建虚拟环境
    print("\n2. 创建虚拟环境...")
    venv_dir = Path("venv")

    if venv_dir.exists():
        print("   ℹ️  虚拟环境已存在，跳过创建")
    else:
        if not run_command(f"{sys.executable} -m venv venv", "创建虚拟环境"):
            return False

    # 3. 激活虚拟环境并安装依赖
    print("\n3. 安装依赖...")

    # 确定激活脚本
    if sys.platform == "win32":
        pip_path = "venv\\Scripts\\pip"
        python_path = "venv\\Scripts\\python"
    else:
        pip_path = "venv/bin/pip"
        python_path = "venv/bin/python"

    # 升级pip
    if not run_command(f"{pip_path} install --upgrade pip", "升级pip"):
        return False

    # 安装核心依赖（直接安装而不是可编辑模式）
    core_deps = [
        "fastapi",
        "uvicorn[standard]",
        "pydantic",
        "python-multipart",
        "aiohttp",
        "python-dotenv",
        "pyyaml",
        "psutil",
        "watchdog",
        "requests",
        "aiofiles",
        "PyJWT",
        "cryptography",
        "typing-extensions",
    ]

    if not run_command(f"{pip_path} install {' '.join(core_deps)}", "安装核心依赖"):
        return False

    # 安装开发依赖
    dev_deps = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-mock",
        "black",
        "mypy",
        "pre-commit",
    ]

    if not run_command(f"{pip_path} install {' '.join(dev_deps)}", "安装开发依赖"):
        return False

    # 4. 安装pre-commit钩子
    print("\n4. 设置代码质量工具...")
    if not run_command(f"{python_path} -m pre_commit install", "安装pre-commit钩子"):
        return False

    if not run_command(
        f"{python_path} -m pre_commit install --hook-type commit-msg",
        "安装commit-msg钩子",
    ):
        return False

    # 5. 运行初始检查
    print("\n5. 运行初始代码检查...")

    # 运行black检查
    print("   🔍 检查代码格式...")
    if run_command(f"{python_path} -m black --check .", "Black格式检查"):
        print("   ✅ 代码格式检查通过")
    else:
        print("   ⚠️  代码格式需要调整，运行 'black .' 修复")

    # 运行mypy检查
    print("   🔍 检查类型提示...")
    if run_command(f"{python_path} -m mypy core hub run", "MyPy类型检查"):
        print("   ✅ 类型检查通过")
    else:
        print("   ⚠️  类型检查发现错误，需要修复")

    # 6. 运行测试
    print("\n6. 运行测试...")
    if run_command(f"{python_path} -m pytest tests/unit -xvs", "运行单元测试"):
        print("   ✅ 测试通过")
    else:
        print("   ⚠️  测试失败，需要修复")

    # 7. 创建默认配置文件
    print("\n7. 创建配置文件...")
    config_dir = Path("config")
    if not config_dir.exists():
        config_dir.mkdir(exist_ok=True)

    # 创建最小化的.env文件
    env_file = config_dir / ".env.example"
    env_content = """# Miya项目配置示例
# 复制此文件为 .env 并修改配置

# 应用配置
DEBUG=true
LOG_LEVEL=DEBUG

# AI配置（模型配置请编辑 config/multi_model_config.json）
AI_PROVIDER=
AI_API_KEY=
AI_MODEL=
AI_TIMEOUT=30

# 数据库配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 终端配置
TERMINAL_MAX=10
TERMINAL_DEFAULT=cmd
TERMINAL_TIMEOUT=30

# Web配置
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=change-me-in-production

# 可选：QQ机器人配置
# QQ_ENABLED=false
# QQ_ONEBOT_WS_URL=ws://localhost:3001
"""

    env_file.write_text(env_content, encoding="utf-8")
    print(f"   ✅ 创建配置文件: {env_file}")

    print("\n" + "=" * 60)
    print("🎉 开发环境设置完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 复制 config/.env.example 为 config/.env")
    print("2. 编辑 config/.env 设置你的API密钥")
    print("3. 运行测试: python -m pytest tests/")
    print("4. 启动应用: python -m run.main")
    print("\n常用命令：")
    print("  • 格式化代码: black .")
    print("  • 类型检查: mypy core hub run")
    print("  • 运行测试: pytest")
    print("  • 启动终端模式: miya-terminal")
    print("  • 启动Web模式: miya-web")

    return True


def main():
    """主函数"""
    try:
        success = setup_development_environment()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 设置过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
