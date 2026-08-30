#!/usr/bin/env python3
"""
AI表情包标签生成脚本
使用多模型视觉分析为所有表情包生成语义标签
"""

import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """运行AI标签生成"""
    from utils.emoji_manager import get_smart_emoji_manager

    print("\n" + "=" * 60)
    print("AI表情包标签生成工具")
    print("=" * 60 + "\n")

    manager = get_smart_emoji_manager()

    stats = manager.get_stats()
    print("当前表情包状态:")
    print(f"  表情包总数: {stats['total_emojis']}")
    print(f"  已标记标签: {stats['total_tags']}")
    print(f"  可用分类: {', '.join(stats['categories'])}")

    print("\n开始AI视觉分析生成标签...")
    print("(这可能需要几分钟，取决于表情包数量和API响应速度)\n")

    result = await manager.generate_ai_tags_for_all(batch_size=3, delay=2.0)

    print("\n" + "-" * 40)
    print("AI标签生成结果:")
    print(f"  需要处理: {result['total']}")
    print(f"  成功: {result['success']}")
    print(f"  失败: {result['failed']}")
    print(f"  跳过: {result['skipped']}")

    print("\n更新后的标签示例:")
    for path, tags in list(manager.emoji_tags.items())[:5]:
        name = os.path.basename(path)
        print(f"  {name}: {tags}")

    print("\n" + "=" * 60)
    print("AI标签生成完成！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"AI标签生成失败: {e}", exc_info=True)
        sys.exit(1)
