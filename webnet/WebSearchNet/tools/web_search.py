"""
Web 搜索工具 - ToolNet 集成
"""
import logging
from typing import Dict, Any
from tools.web_search import get_web_search_tool
from webnet.tools.base import BaseTool


logger = logging.getLogger(__name__)


class WebSearch(BaseTool):
    """Web 搜索工具"""

    def __init__(self):
        """初始化 Web 搜索工具"""
        super().__init__()

        self._config = {
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
                        'maximum': 10
                    }
                },
                'required': ['query']
            }
        }

        # 获取 Web 搜索工具实例
        self.web_search_tool = get_web_search_tool()

    @property
    def config(self) -> Dict[str, Any]:
        """获取工具配置"""
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """
        执行 Web 搜索

        Args:
            args: 参数字典
            context: 工具执行上下文

        Returns:
            str: 搜索结果
        """
        query = args.get('query')
        engine = args.get('engine')
        max_results = args.get('max_results', 5)

        if not query:
            return "❌ 搜索查询不能为空"

        logger.info(f"Web 搜索请求: {query}")

        try:
            result = await self.web_search_tool.search(
                query=query,
                engine=engine,
                max_results=max_results
            )

            return self.web_search_tool.format_results(result)

        except Exception as e:
            logger.error(f"Web 搜索失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"


class GetAvailableSearchEngines(BaseTool):
    """获取可用搜索引擎"""

    def __init__(self):
        """初始化工具"""
        super().__init__()

        self._config = {
            'name': 'get_available_search_engines',
            'description': '获取当前可用的搜索引擎列表',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': []
            }
        }

        self.web_search_tool = get_web_search_tool()

    @property
    def config(self) -> Dict[str, Any]:
        """获取工具配置"""
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """
        获取可用搜索引擎

        Args:
            args: 参数字典
            context: 工具执行上下文

        Returns:
            str: 搜索引擎列表
        """
        engines = self.web_search_tool.get_available_engines()
        if engines:
            return f"🌐 可用的搜索引擎: {', '.join(engines)}"
        else:
            return "❌ 无可用搜索引擎"


class GetSearchHistory(BaseTool):
    """获取搜索历史"""

    def __init__(self):
        """初始化工具"""
        super().__init__()

        self._config = {
            'name': 'get_search_history',
            'description': '获取最近的搜索历史记录',
            'parameters': {
                'type': 'object',
                'properties': {
                    'limit': {
                        'type': 'integer',
                        'description': '返回数量（默认 10）',
                        'minimum': 1,
                        'maximum': 50
                    }
                },
                'required': []
            }
        }

        self.web_search_tool = get_web_search_tool()

    @property
    def config(self) -> Dict[str, Any]:
        """获取工具配置"""
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """
        获取搜索历史

        Args:
            args: 参数字典
            context: 工具执行上下文

        Returns:
            str: 搜索历史
        """
        limit = args.get('limit', 10)
        history = self.web_search_tool.get_search_history(limit)

        if not history:
            return "📜 暂无搜索历史"

        formatted = "📜 搜索历史（最近 10 条）:\n\n"
        for i, record in enumerate(reversed(history), 1):
            formatted += f"{i}. {record.get('query')}\n"
            formatted += f"   🔍 引擎: {record.get('engine')}\n"
            formatted += f"   📊 结果数: {record.get('results_count')}\n"
            formatted += f"   ⏰ 时间: {record.get('timestamp')}\n\n"

        return formatted.strip()
