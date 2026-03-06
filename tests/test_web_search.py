"""
测试 Web 搜索功能
"""
import asyncio
import logging
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.web_search import get_web_search_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_web_search():
    """测试 Web 搜索功能"""

    # 获取 Web 搜索工具实例
    web_search_tool = get_web_search_tool()

    logger.info("=== Web 搜索工具测试 ===\n")

    # 显示可用搜索引擎
    engines = web_search_tool.get_available_engines()
    logger.info(f"✅ 可用的搜索引擎: {engines}\n")

    # 测试搜索
    test_queries = [
        "AI 最新进展 2024",
        "OpenAI Claude 3.5",
        "DeepSeek 模型",
        "Python 编程技巧"
    ]

    for query in test_queries:
        logger.info(f"\n搜索: {query}")
        logger.info("-" * 50)

        try:
            result = await web_search_tool.search(query, max_results=3)
            formatted = web_search_tool.format_results(result)

            print(formatted)

            # 等待一下，避免请求过快
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            print(f"❌ 搜索失败: {e}\n")

    # 显示搜索历史
    logger.info("\n\n=== 搜索历史 ===\n")
    history = web_search_tool.get_search_history(limit=10)

    if history:
        for i, record in enumerate(reversed(history), 1):
            logger.info(f"{i}. {record.get('query')}")
            logger.info(f"   引擎: {record.get('engine')}")
            logger.info(f"   结果数: {record.get('results_count')}")
            logger.info(f"   时间: {record.get('timestamp')}")
            logger.info("")
    else:
        logger.info("暂无搜索历史")


if __name__ == '__main__':
    asyncio.run(test_web_search())
