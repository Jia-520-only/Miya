"""
Web 搜索工具 - ToolNet 集成
将 Web 搜索能力注册到 ToolNet 工具子网
"""
import logging
from typing import Dict, Any, Optional
from .web_search import WebSearchTool, get_web_search_tool

logger = logging.getLogger(__name__)


class WebSearchToolAdapter:
    """Web 搜索工具适配器（用于 ToolNet）"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Web 搜索工具适配器

        Args:
            config_path: 配置文件路径
        """
        self.web_search_tool = get_web_search_tool(config_path)
        logger.info("Web 搜索工具适配器初始化完成")

    async def web_search(
        self,
        query: str,
        engine: Optional[str] = None,
        max_results: int = 5
    ) -> str:
        """
        Web 搜索

        Args:
            query: 搜索查询
            engine: 搜索引擎（可选）
            max_results: 最大结果数量

        Returns:
            str: 格式化的搜索结果
        """
        logger.info(f"Web 搜索请求: {query}")

        result = await self.web_search_tool.search(
            query=query,
            engine=engine,
            max_results=max_results
        )

        return self.web_search_tool.format_results(result)

    def get_available_engines(self) -> str:
        """
        获取可用的搜索引擎

        Returns:
            str: 搜索引擎列表
        """
        engines = self.web_search_tool.get_available_engines()
        return f"可用的搜索引擎: {', '.join(engines)}" if engines else "无可用搜索引擎"

    def get_search_history(self, limit: int = 10) -> str:
        """
        获取搜索历史

        Args:
            limit: 返回数量

        Returns:
            str: 搜索历史
        """
        history = self.web_search_tool.get_search_history(limit)
        if not history:
            return "暂无搜索历史"

        formatted = "搜索历史（最近 10 条）:\n\n"
        for i, record in enumerate(reversed(history), 1):
            formatted += f"{i}. {record.get('query')}\n"
            formatted += f"   引擎: {record.get('engine')}\n"
            formatted += f"   结果数: {record.get('results_count')}\n"
            formatted += f"   时间: {record.get('timestamp')}\n\n"

        return formatted


def register_web_search_tools(tool_registry: Any, context: Optional[Dict] = None):
    """
    注册 Web 搜索工具到 ToolNet

    Args:
        tool_registry: ToolNet 工具注册表
        context: 工具执行上下文
    """
    adapter = WebSearchToolAdapter()

    # 定义工具函数
    tools = [
        {
            'type': 'function',
            'function': {
                'name': 'web_search',
                'description': '执行 Web 搜索，获取实时信息。当用户询问关于新闻、天气、实时事件、最新资讯、技术更新等内容时使用此工具。',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': '搜索查询内容，应简洁明确'
                        },
                        'engine': {
                            'type': 'string',
                            'description': '搜索引擎（可选，默认使用 DuckDuckGo）',
                            'enum': ['duckduckgo', 'bing', 'google']
                        },
                        'max_results': {
                            'type': 'integer',
                            'description': '最大结果数量（默认 5）',
                            'minimum': 1,
                            'maximum': 10,
                            'default': 5
                        }
                    },
                    'required': ['query']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_available_search_engines',
                'description': '获取当前可用的搜索引擎列表',
                'parameters': {
                    'type': 'object',
                    'properties': {}
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_search_history',
                'description': '获取最近的搜索历史记录',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {
                            'type': 'integer',
                            'description': '返回数量（默认 10）',
                            'minimum': 1,
                            'maximum': 50,
                            'default': 10
                        }
                    }
                }
            }
        }
    ]

    # 注册工具
    for tool in tools:
        tool_name = tool['function']['name']
        tool_registry.register(tool_name, adapter, context)
        logger.info(f"已注册 Web 搜索工具: {tool_name}")

    logger.info("Web 搜索工具注册完成")
    return tools
