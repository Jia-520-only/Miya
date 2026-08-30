#!/usr/bin/env python3
"""
QQ功能使用示例
展示如何使用新实现的QQ功能
"""

import asyncio
import logging
import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def example_image_send():
    """示例：图片发送"""
    logger.info("示例：图片发送功能")

    from webnet.ToolNet.base import ToolContext
    from webnet.ToolNet.tools.message.send_platform_file import SendPlatformFileTool

    SendPlatformFileTool()
    ToolContext()

    # 示例1：发送本地图片
    example_args = {
        "target_type": "group",
        "target_id": 123456789,
        "image_source": "local",
        "image_path": "examples/qq/test_image.jpg",
        "caption": "这是一张测试图片",
    }

    logger.info(f"发送图片: {example_args}")

    # 在实际环境中，这会调用QQ客户端发送图片
    # result = await tool.execute(example_args, context)
    # logger.info(f"结果: {result}")

    print("✅ 图片发送功能示例完成")


async def example_file_read():
    """示例：文件读取"""
    logger.info("示例：文件读取功能")

    from webnet.ToolNet.base import ToolContext
    from webnet.ToolNet.tools.qq.qq_file_reader import QQFileReaderTool

    QQFileReaderTool()
    ToolContext()

    # 示例：读取文本文件
    example_args = {"action": "read", "file_path": "examples/qq/sample.txt", "max_length": 500}

    # 创建示例文件
    sample_content = """这是一个示例文本文件
包含多行内容
用于测试文件读取功能

弥娅QQ端文件读取功能特点：
1. 支持多种文件格式（TXT, PDF, DOCX等）
2. 自动编码检测
3. 内容预览和摘要
4. 关键词搜索功能
"""

    os.makedirs("examples/qq", exist_ok=True)
    with open("examples/qq/sample.txt", "w", encoding="utf-8") as f:
        f.write(sample_content)

    logger.info(f"读取文件: {example_args}")

    # 在实际环境中，这会读取并分析文件内容
    # result = await tool.execute(example_args, context)
    # logger.info(f"结果: {result}")

    print("✅ 文件读取功能示例完成")


async def example_image_analysis():
    """示例：图片分析"""
    logger.info("示例：图片分析功能")

    from webnet.ToolNet.base import ToolContext
    from webnet.ToolNet.tools.qq.qq_image_analyzer import QQImageAnalyzerTool

    QQImageAnalyzerTool()
    ToolContext()

    # 示例：分析图片中的文字
    example_args = {
        "action": "ocr",
        "image_source": "local",
        "image_path": "examples/qq/ocr_test.jpg",
        "detail_level": "basic",
    }

    logger.info(f"分析图片: {example_args}")

    # 在实际环境中，这会使用OCR识别图片中的文字
    # result = await tool.execute(example_args, context)
    # logger.info(f"结果: {result}")

    print("✅ 图片分析功能示例完成")


async def example_active_chat():
    """示例：主动聊天"""
    logger.info("示例：主动聊天功能")

    from webnet.ToolNet.tools.qq.qq_active_chat import QQActiveChatTool

    from webnet.ToolNet.base import ToolContext

    QQActiveChatTool()
    ToolContext()

    # 示例：设置早安消息
    example_args = {
        "action": "setup",
        "trigger_type": "time",
        "schedule": "08:00",
        "message_template": "早安！{username}，新的一天开始啦！{random_emoji}",
        "target_type": "group",
        "target_id": 123456789,
    }

    logger.info(f"设置主动聊天: {example_args}")

    # 在实际环境中，这会创建定时任务
    # result = await tool.execute(example_args, context)
    # logger.info(f"结果: {result}")

    print("✅ 主动聊天功能示例完成")


async def example_enhanced_scheduler():
    """示例：增强定时任务"""
    logger.info("示例：增强定时任务功能")

    try:
        from webnet.ToolNet.tools.core.task_scheduler_enhanced import EnhancedTaskScheduler

        EnhancedTaskScheduler()

        # 示例任务配置
        task_config = {
            "type": "qq_message",
            "name": "每日提醒",
            "schedule": "0 9 * * *",  # 每天上午9点
            "target_type": "group",
            "target_id": 123456789,
            "message": "大家早上好！记得完成每日任务哦～",
            "repeat": "daily",
            "max_retries": 3,
        }

        logger.info(f"创建定时任务: {task_config['name']}")

        # 在实际环境中，这会创建定时任务
        # task_id = await scheduler.create_task(task_config)
        # logger.info(f"任务ID: {task_id}")

        print("✅ 增强定时任务功能示例完成")
    except ImportError as e:
        logger.warning(f"增强定时任务模块未找到: {e}")


async def run_all_examples():
    """运行所有示例"""
    logger.info("=" * 60)
    logger.info("弥娅QQ功能使用示例")
    logger.info("=" * 60)

    examples = [
        ("图片发送", example_image_send),
        ("文件读取", example_file_read),
        ("图片分析", example_image_analysis),
        ("主动聊天", example_active_chat),
        ("增强定时任务", example_enhanced_scheduler),
    ]

    for name, example_func in examples:
        logger.info(f"\n运行示例: {name}")
        try:
            await example_func()
            logger.info(f"✓ {name} 示例完成")
        except Exception as e:
            logger.error(f"✗ {name} 示例失败: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("所有示例运行完成！")

    # 显示使用说明
    print("\n[使用说明]:")
    print("1. 配置 config/qq_config.yaml")
    print("2. 启动 OneBot 服务（如 go-cqhttp）")
    print("3. 启动弥娅: python run/start.py")
    print("4. 通过QQ与弥娅交互")

    print("\n[可用命令示例]:")
    print("- 发送图片: '发一张图片'")
    print("- 发送文件: '发送这个文件'")
    print("- 读取文件: '这个文件说了什么？'")
    print("- 分析图片: '图片里有什么文字？'")
    print("- 设置提醒: '每天早上8点提醒我'")

    print("\n[详细文档]: docs/qq_features_guide.md")


def main():
    """主函数"""
    try:
        # 切换到项目根目录
        os.chdir(project_root)

        # 运行示例
        asyncio.run(run_all_examples())

    except KeyboardInterrupt:
        logger.info("\n示例被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"示例运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
