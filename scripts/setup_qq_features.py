#!/usr/bin/env python3
"""
QQ功能安装和配置脚本
自动安装依赖、检查配置、创建必要目录
"""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_python_version():
    """检查Python版本"""
    logger.info("检查Python版本...")
    python_version = platform.python_version()
    major, minor, _ = map(int, python_version.split("."))

    if major < 3 or (major == 3 and minor < 8):
        logger.error(f"Python版本 {python_version} 过低，需要 3.8+")
        return False

    logger.info(f"Python版本: {python_version} ✓")
    return True


def install_dependencies():
    """安装依赖包"""
    logger.info("安装QQ功能依赖包...")

    # 基础依赖
    base_deps = [
        "pillow>=10.0.0",
        "pytesseract>=0.3.10",
        "paddleocr>=2.7.0.3",
        "paddlepaddle>=2.5.0",
        "PyPDF2>=3.0.0",
        "python-docx>=1.1.0",
        "chardet>=5.1.0",
        "python-magic>=0.4.27",
        "aiohttp>=3.8.0",
        "aiofiles>=23.0.0",
        "pyyaml>=6.0",
        "tenacity>=8.2.0",
    ]

    success_count = 0
    fail_count = 0

    for dep in base_deps:
        try:
            logger.info(f"安装 {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True, capture_output=True, text=True)
            success_count += 1
            logger.info(f"  ✓ {dep}")
        except subprocess.CalledProcessError as e:
            fail_count += 1
            logger.warning(f"  ✗ {dep}: {e.stderr}")

    if fail_count > 0:
        logger.warning(f"有 {fail_count} 个依赖包安装失败")

    logger.info(f"依赖包安装完成: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0


def check_tesseract():
    """检查Tesseract OCR引擎"""
    logger.info("检查Tesseract OCR引擎...")

    system = platform.system().lower()

    try:
        if system == "windows":
            # Windows: 检查是否安装了Tesseract
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
            ]

            found = False
            for path in tesseract_paths:
                if os.path.exists(path):
                    logger.info(f"Tesseract找到: {path}")
                    found = True
                    break

            if not found:
                logger.warning("Tesseract未安装")
                logger.warning("请从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装")
                logger.warning("或使用 paddleocr 作为备选方案")

        elif system in ["linux", "darwin"]:  # Linux 或 macOS
            try:
                subprocess.run(["tesseract", "--version"], check=True, capture_output=True)
                logger.info("Tesseract已安装 ✓")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("Tesseract未安装")
                logger.warning("安装命令:")
                logger.warning("  Ubuntu/Debian: sudo apt-get install tesseract-ocr")
                logger.warning("  macOS: brew install tesseract")

    except Exception as e:
        logger.error(f"检查Tesseract时出错: {e}")

    return True


def create_directories():
    """创建必要的目录"""
    logger.info("创建必要的目录...")

    directories = [
        "config",
        "logs",
        "downloads/qq_files",
        "temp/uploads",
        "temp/image_cache",
        "data/emojis",
        "data/backups",
    ]

    project_root = Path(__file__).parent.parent

    for dir_path in directories:
        full_path = project_root / dir_path
        try:
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"  创建目录: {dir_path}")
        except Exception as e:
            logger.error(f"  创建目录失败 {dir_path}: {e}")

    return True


def copy_config_files():
    """复制配置文件"""
    logger.info("复制配置文件...")

    project_root = Path(__file__).parent.parent
    project_root / "config" / "qq_config.yaml"
    config_dest = project_root / "config" / "qq_config.yaml"

    # 检查是否已有配置文件
    if config_dest.exists():
        logger.info("配置文件已存在，跳过复制")
        return True

    # 创建默认配置文件
    try:
        default_config = """# QQ机器人配置
# 版本: 2.0.1
# 最后更新: 2025-03-21

qq:
  # OneBot WebSocket 连接配置
  onebot:
    ws_url: "ws://localhost:6700"  # OneBot WebSocket地址
    token: ""                      # 访问令牌（可选）
    bot_qq: 0                      # 机器人QQ号
    superadmin_qq: 0               # 超级管理员QQ号
  
  # 连接设置
  connection:
    reconnect_interval: 5.0        # 重连间隔（秒）
    ping_interval: 20              # 心跳间隔（秒）
    ping_timeout: 30               # 心跳超时（秒）
    max_message_size: 104857600    # 最大消息大小（100MB）
  
  # 多媒体功能配置
  multimedia:
    # 图片处理
    image:
      max_size: 10485760           # 10MB
      allowed_formats: [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
    
    # 文件处理
    file:
      max_size: 52428800           # 50MB
      allowed_formats:
        text: [".txt", ".log", ".md", ".json", ".xml", ".html", ".csv"]
        document: [".pdf", ".doc", ".docx", ".xls", ".xlsx"]
        code: [".py", ".js", ".ts", ".java", ".cpp", ".c"]
  
  # 图片识别功能
  image_recognition:
    # OCR设置
    ocr:
      enabled: true
      engine: "auto"               # auto, paddleocr, tesseract
  
  # 主动聊天功能
  active_chat:
    enabled: true
    limits:
      max_daily_messages: 10       # 每天最多主动消息数
      min_interval: 300            # 消息最小间隔（秒）
  
  # 任务调度系统
  task_scheduler:
    enabled: true
    database:
      path: "./data/tasks.db"      # SQLite数据库路径

# 工具配置
tools:
  # QQ表情包工具
  qq_emoji:
    enabled: true
  
  # QQ文件读取工具
  qq_file_reader:
    enabled: true
  
  # QQ图片分析工具
  qq_image_analyzer:
    enabled: true
  
  # QQ主动聊天工具
  qq_active_chat:
    enabled: true
"""

        with open(config_dest, "w", encoding="utf-8") as f:
            f.write(default_config)

        logger.info("默认配置文件已创建")

        # 显示配置提示
        logger.info("\n" + "=" * 60)
        logger.info("下一步配置:")
        logger.info("1. 编辑 config/qq_config.yaml")
        logger.info("2. 设置 OneBot WebSocket 地址 (ws_url)")
        logger.info("3. 设置机器人QQ号 (bot_qq)")
        logger.info("4. 根据需要调整其他配置")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"创建配置文件失败: {e}")
        return False

    return True


def create_example_files():
    """创建示例文件"""
    logger.info("创建示例文件...")

    project_root = Path(__file__).parent.parent
    examples_dir = project_root / "examples" / "qq"

    try:
        examples_dir.mkdir(parents=True, exist_ok=True)

        # 创建示例图片
        example_image = examples_dir / "example_usage.png"
        if not example_image.exists():
            logger.info("  创建示例目录: examples/qq/")

        # 创建测试图片
        test_image = examples_dir / "test_image.jpg"
        if not test_image.exists():
            # 创建一个简单的占位符说明文件
            with open(examples_dir / "README.txt", "w", encoding="utf-8") as f:
                f.write("QQ功能示例目录\n")
                f.write("===============\n\n")
                f.write("在此目录中可以放置测试用的图片、文件等资源\n\n")
                f.write("使用方法：\n")
                f.write("1. 将图片文件放在这里用于图片识别测试\n")
                f.write("2. 将文本/PDF文件放在这里用于文件读取测试\n")
                f.write("3. 运行测试脚本: python scripts/test_qq_features.py\n")

            logger.info("  示例目录和说明已创建")

    except Exception as e:
        logger.error(f"创建示例文件失败: {e}")

    return True


def test_installation():
    """测试安装"""
    logger.info("测试安装...")

    try:
        # 测试Python包导入
        test_imports = [
            ("PIL", "pillow"),
            ("pytesseract", "pytesseract"),
            ("paddleocr", "paddleocr"),
            ("PyPDF2", "PyPDF2"),
            ("docx", "python-docx"),
            ("chardet", "chardet"),
            ("yaml", "yaml"),
        ]

        for module_name, package_name in test_imports:
            try:
                __import__(module_name)
                logger.info(f"  ✓ {package_name}")
            except ImportError:
                logger.warning(f"  ✗ {package_name} 导入失败")

        logger.info("基本安装测试完成")
        return True

    except Exception as e:
        logger.error(f"安装测试失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("弥娅QQ功能安装脚本")
    logger.info("=" * 60)

    # 切换到项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    logger.info(f"项目目录: {project_root}")

    # 执行安装步骤
    steps = [
        ("Python版本检查", check_python_version),
        ("创建必要目录", create_directories),
        ("安装依赖包", install_dependencies),
        ("检查Tesseract", check_tesseract),
        ("复制配置文件", copy_config_files),
        ("创建示例文件", create_example_files),
        ("安装测试", test_installation),
    ]

    results = []

    for step_name, step_func in steps:
        logger.info(f"\n步骤: {step_name}")
        try:
            success = step_func()
            results.append((step_name, success))

            if success:
                logger.info(f"✓ {step_name} 完成")
            else:
                logger.error(f"✗ {step_name} 失败")
        except Exception as e:
            logger.error(f"✗ {step_name} 异常: {e}")
            results.append((step_name, False))

    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("安装结果汇总:")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for step_name, success in results:
        status = "✓ 完成" if success else "✗ 失败"
        logger.info(f"  {step_name:20} {status}")

    logger.info(f"\n完成率: {passed}/{total} ({passed / total * 100:.1f}%)")

    if passed == total:
        logger.info("\n🎉 QQ功能安装完成！")
        logger.info("\n下一步操作:")
        logger.info("1. 配置 config/qq_config.yaml")
        logger.info("2. 运行测试: python scripts/test_qq_features.py")
        logger.info("3. 启动弥娅: python run/start.py")
        logger.info("\n详细文档: docs/qq_features_guide.md")
    else:
        logger.warning("\n⚠️ 安装未完全成功")
        logger.info("\n请检查失败步骤并手动修复")

    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n安装被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"安装脚本运行失败: {e}", exc_info=True)
        sys.exit(1)
