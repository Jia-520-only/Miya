"""
网络搜索工具 - web_agent 专用
统一使用弥娅多引擎搜索（tavily/baidu/bing_cn）
"""

import logging

logger = logging.getLogger(__name__)


async def execute(args, context=None, **kwargs) -> str:
    """执行网络搜索

    兼容多种签名：
    - execute(args: Dict, context: ToolContext)
    - execute(context, **kwargs)
    - execute(**kwargs)
    """
    query = ""
    count = 5

    if isinstance(args, dict):
        query = args.get("query", "")
        count = args.get("count", 5)
    elif hasattr(args, "__dataclass_fields__"):
        query = kwargs.get("query", "")
        count = kwargs.get("count", 5)
    else:
        query = kwargs.get("query", "")
        count = kwargs.get("count", 5)

    if not query:
        query = kwargs.get("query", "")
    if not count:
        count = kwargs.get("count", 5)

    if not query:
        return "请提供搜索关键词"

    try:
        from webnet.ToolNet.tools.network.web_search import EnhancedWebSearch

        searcher = EnhancedWebSearch()
        engines = ["tavily", "bing_cn", "baidu"]

        results = searcher.search(query, engines=engines, num_results=count)
        summary = searcher.generate_summary(results, max_length=800)

        if not results:
            return f"未找到与'{query}'相关的搜索结果"

        return summary

    except Exception as e:
        logger.error(f"网络搜索失败: {e}")
        return f"搜索失败: {str(e)[:50]}"
