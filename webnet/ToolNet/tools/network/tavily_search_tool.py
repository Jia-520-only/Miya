"""
Tavily AI 搜索工具 - ToolNet 集成

专为 AI 设计的搜索引擎，返回结构化、干净的结果。
"""

import logging
from typing import Any, Dict

from config.config_utils import get_api_key
from webnet.ToolNet.base import BaseTool, ToolContext
from webnet.ToolNet.tools.network.tavily_search import TavilyAISearch

logger = logging.getLogger(__name__)


class TavilySearchTool(BaseTool):
    """Tavily AI 搜索工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "tavily_search",
            "description": """Tavily AI 搜索引擎。

当用户询问实时信息、新闻、事实查询或你不知道答案时使用此工具。
Tavily 返回结构化、干净的搜索结果，适合 AI 阅读。

适用场景:
- 实时新闻/事件查询
- 事实核查
- 技术文档搜索
- 人物/公司/产品查询
- 任何需要最新互联网信息的问题

示例:
- 搜索: 今天有什么AI新闻
- 查找: 弥娅是什么
- 查询: 2026年清明节放假安排""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询内容",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果数 (默认5)",
                        "default": 5,
                    },
                    "search_depth": {
                        "type": "string",
                        "description": "搜索深度: basic(快速) 或 advanced(深入)",
                        "enum": ["basic", "advanced"],
                        "default": "basic",
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        query = args.get("query", "").strip()
        if not query:
            return "请提供搜索内容"

        max_results = args.get("max_results", 5)
        search_depth = args.get("search_depth", "basic")

        api_key = get_api_key("TAVILY_API_KEY")
        if not api_key:
            return "Tavily 搜索功能未配置（缺少 TAVILY_API_KEY 环境变量）"

        try:
            searcher = TavilyAISearch(api_key=api_key)
            result = searcher.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True,
            )

            if result.get("success"):
                return searcher.format_for_ai(result)
            else:
                return f"Tavily 搜索失败: {result.get('error', '未知错误')}"

        except Exception as e:
            logger.error(f"[TavilySearch] 执行失败: {e}")
            return f"Tavily 搜索执行失败: {e}"
