"""
Web 搜索工具模块
为弥娅提供实时信息检索能力
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str
    timestamp: datetime
    relevance: float

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'relevance': self.relevance
        }


class WebSearchEngine:
    """Web 搜索引擎基类"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化搜索引擎

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        self.enabled = self.config.get('enabled', False)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "zh-CN"
    ) -> List[SearchResult]:
        """
        搜索 Web

        Args:
            query: 搜索查询
            max_results: 最大结果数量
            language: 语言设置

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        raise NotImplementedError

    def format_results(self, results: List[SearchResult]) -> str:
        """
        格式化搜索结果

        Args:
            results: 搜索结果列表

        Returns:
            str: 格式化的结果
        """
        if not results:
            return "未找到相关结果"

        formatted = f"📊 搜索结果 ({len(results)} 条):\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result.title}\n"
            formatted += f"   📍 {result.url}\n"
            formatted += f"   📄 {result.snippet}\n"
            formatted += f"   🎯 相关度: {result.relevance:.2f}\n\n"

        return formatted


class DuckDuckGoSearchEngine(WebSearchEngine):
    """DuckDuckGo 搜索引擎（免费，无需 API Key）"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.name = "DuckDuckGo"
        self.enabled = True  # DuckDuckGo 默认启用

    async def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "zh-CN"
    ) -> List[SearchResult]:
        """使用 DuckDuckGo 搜索"""
        try:
            # 使用 duckduckgo-search 库
            from duckduckgo_search import DDGS

            results = []
            async with DDGS() as ddgs:
                # 执行搜索
                search_results = ddgs.text(
                    query,
                    max_results=max_results
                )

                if not search_results:
                    logger.warning(f"DuckDuckGo 未找到结果: {query}")
                    return []

                # 转换为 SearchResult 对象
                for result in search_results:
                    search_result = SearchResult(
                        title=result.get('title', ''),
                        url=result.get('href', ''),
                        snippet=result.get('body', ''),
                        source='DuckDuckGo',
                        timestamp=datetime.now(),
                        relevance=0.85  # DuckDuckGo 默认相关度
                    )
                    results.append(search_result)

            logger.info(f"DuckDuckGo 搜索完成: {query}, 找到 {len(results)} 条结果")
            return results

        except ImportError:
            logger.error("duckduckgo-search 库未安装，请运行: pip install duckduckgo-search")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            return []


class BingSearchEngine(WebSearchEngine):
    """Bing 搜索引擎（需要 API Key）"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.name = "Bing"
        self.api_key = self.config.get('api_key', '')
        self.enabled = bool(self.api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "zh-CN"
    ) -> List[SearchResult]:
        """使用 Bing 搜索 API"""
        if not self.enabled:
            logger.warning("Bing 搜索未配置 API Key")
            return []

        try:
            import aiohttp

            headers = {
                'Ocp-Apim-Subscription-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            params = {
                'q': query,
                'count': max_results,
                'mkt': language,
                'safeSearch': 'Moderate'
            }

            url = "https://api.bing.microsoft.com/v7.0/search"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Bing API 错误: {response.status}")
                        return []

                    data = await response.json()

            results = []
            web_pages = data.get('webPages', {}).get('value', [])

            for page in web_pages:
                search_result = SearchResult(
                    title=page.get('name', ''),
                    url=page.get('url', ''),
                    snippet=page.get('snippet', ''),
                    source='Bing',
                    timestamp=datetime.now(),
                    relevance=0.90  # Bing 默认相关度
                )
                results.append(search_result)

            logger.info(f"Bing 搜索完成: {query}, 找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            return []


class GoogleSearchEngine(WebSearchEngine):
    """Google 搜索引擎（需要 API Key）"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.name = "Google"
        self.api_key = self.config.get('api_key', '')
        self.cse_id = self.config.get('cse_id', '')
        self.enabled = bool(self.api_key and self.cse_id)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "zh-CN"
    ) -> List[SearchResult]:
        """使用 Google Custom Search API"""
        if not self.enabled:
            logger.warning("Google 搜索未配置 API Key 或 CSE ID")
            return []

        try:
            import aiohttp

            params = {
                'key': self.api_key,
                'cx': self.cse_id,
                'q': query,
                'num': max_results,
                'lr': f'lang_{language.split("-")[0]}'
            }

            url = "https://www.googleapis.com/customsearch/v1"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Google API 错误: {response.status}")
                        return []

                    data = await response.json()

            results = []
            items = data.get('items', [])

            for item in items:
                search_result = SearchResult(
                    title=item.get('title', ''),
                    url=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                    source='Google',
                    timestamp=datetime.now(),
                    relevance=0.95  # Google 默认相关度
                )
                results.append(search_result)

            logger.info(f"Google 搜索完成: {query}, 找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"Google 搜索失败: {e}")
            return []


class WebSearchTool:
    """Web 搜索工具（统一接口）"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Web 搜索工具

        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.engines: List[WebSearchEngine] = []
        self.search_history: List[Dict] = []

        # 初始化搜索引擎
        self._init_engines()

        logger.info(f"Web 搜索工具初始化完成，已加载 {len(self.engines)} 个搜索引擎")

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置文件"""
        if config_path is None:
            # 默认配置路径
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'config' / 'web_search_config.json'

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认配置
            return {
                'engines': {
                    'duckduckgo': {'enabled': True},
                    'bing': {'enabled': False, 'api_key': ''},
                    'google': {'enabled': False, 'api_key': '', 'cse_id': ''}
                },
                'default_engine': 'duckduckgo',
                'max_results': 5,
                'cache_enabled': True,
                'cache_ttl': 3600
            }

    def _init_engines(self):
        """初始化搜索引擎"""
        engines_config = self.config.get('engines', {})

        # DuckDuckGo（免费，默认启用）
        if engines_config.get('duckduckgo', {}).get('enabled', True):
            try:
                self.engines.append(DuckDuckGoSearchEngine(engines_config.get('duckduckgo')))
                logger.info("  ✅ DuckDuckGo 搜索引擎已启用")
            except Exception as e:
                logger.warning(f"  ❌ DuckDuckGo 搜索引擎初始化失败: {e}")

        # Bing（需要 API Key）
        bing_config = engines_config.get('bing', {})
        if bing_config.get('enabled', False) and bing_config.get('api_key'):
            try:
                self.engines.append(BingSearchEngine(bing_config))
                logger.info("  ✅ Bing 搜索引擎已启用")
            except Exception as e:
                logger.warning(f"  ❌ Bing 搜索引擎初始化失败: {e}")

        # Google（需要 API Key）
        google_config = engines_config.get('google', {})
        if google_config.get('enabled', False) and google_config.get('api_key') and google_config.get('cse_id'):
            try:
                self.engines.append(GoogleSearchEngine(google_config))
                logger.info("  ✅ Google 搜索引擎已启用")
            except Exception as e:
                logger.warning(f"  ❌ Google 搜索引擎初始化失败: {e}")

    async def search(
        self,
        query: str,
        engine: Optional[str] = None,
        max_results: Optional[int] = None,
        language: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        执行 Web 搜索

        Args:
            query: 搜索查询
            engine: 指定搜索引擎（None = 使用默认）
            max_results: 最大结果数量（None = 使用配置默认值）
            language: 语言设置

        Returns:
            Dict[str, Any]: 搜索结果字典
        """
        if not self.engines:
            logger.warning("没有可用的搜索引擎")
            return {
                'success': False,
                'query': query,
                'results': [],
                'message': '没有可用的搜索引擎'
            }

        # 选择搜索引擎
        selected_engine = self._select_engine(engine)

        if not selected_engine:
            logger.warning(f"未找到指定的搜索引擎: {engine}")
            return {
                'success': False,
                'query': query,
                'results': [],
                'message': f'未找到指定的搜索引擎: {engine}'
            }

        # 执行搜索
        max_results = max_results or self.config.get('max_results', 5)
        results = await selected_engine.search(query, max_results, language)

        # 记录搜索历史
        search_record = {
            'query': query,
            'engine': selected_engine.name,
            'results_count': len(results),
            'timestamp': datetime.now().isoformat()
        }
        self.search_history.append(search_record)

        # 返回结果
        return {
            'success': True,
            'query': query,
            'engine': selected_engine.name,
            'results': [r.to_dict() for r in results],
            'results_count': len(results),
            'timestamp': datetime.now().isoformat()
        }

    def _select_engine(self, engine_name: Optional[str]) -> Optional[WebSearchEngine]:
        """
        选择搜索引擎

        Args:
            engine_name: 搜索引擎名称

        Returns:
            WebSearchEngine: 选中的搜索引擎
        """
        if engine_name:
            # 按名称选择
            for engine in self.engines:
                if engine.name.lower() == engine_name.lower():
                    return engine
            return None
        else:
            # 使用默认引擎
            default_name = self.config.get('default_engine', 'duckduckgo')
            for engine in self.engines:
                if engine.name.lower() == default_name.lower():
                    return engine
            # 如果默认引擎不可用，使用第一个可用引擎
            return self.engines[0] if self.engines else None

    def format_results(self, search_result: Dict[str, Any]) -> str:
        """
        格式化搜索结果（用于展示给用户）

        Args:
            search_result: 搜索结果字典

        Returns:
            str: 格式化的结果
        """
        if not search_result.get('success'):
            return f"❌ {search_result.get('message', '搜索失败')}"

        results = search_result.get('results', [])
        if not results:
            return f"🔍 未找到关于「{search_result.get('query')}」的相关结果"

        formatted = f"🌐 使用 {search_result.get('engine')} 搜索「{search_result.get('query')}」\n\n"
        formatted += f"📊 找到 {len(results)} 条相关结果:\n\n"

        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result.get('title', '无标题')}\n"
            formatted += f"   📍 {result.get('url', '无链接')}\n"
            formatted += f"   📄 {result.get('snippet', '无描述')}\n"
            formatted += f"   🎯 相关度: {result.get('relevance', 0):.2f}\n\n"

        return formatted.strip()

    def get_search_history(self, limit: int = 10) -> List[Dict]:
        """
        获取搜索历史

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict]: 搜索历史列表
        """
        return self.search_history[-limit:]

    def get_available_engines(self) -> List[str]:
        """获取可用的搜索引擎列表"""
        return [engine.name for engine in self.engines]


# 创建全局实例（单例模式）
_global_web_search_tool: Optional[WebSearchTool] = None


def get_web_search_tool(config_path: Optional[str] = None) -> WebSearchTool:
    """
    获取 Web 搜索工具实例（单例）

    Args:
        config_path: 配置文件路径

    Returns:
        WebSearchTool: Web 搜索工具实例
    """
    global _global_web_search_tool

    if _global_web_search_tool is None:
        _global_web_search_tool = WebSearchTool(config_path)

    return _global_web_search_tool


# 便捷函数
async def web_search(
    query: str,
    engine: Optional[str] = None,
    max_results: int = 5,
    language: str = "zh-CN"
) -> str:
    """
    便捷的 Web 搜索函数

    Args:
        query: 搜索查询
        engine: 搜索引擎
        max_results: 最大结果数
        language: 语言

    Returns:
        str: 格式化的搜索结果
    """
    tool = get_web_search_tool()
    result = await tool.search(query, engine, max_results, language)
    return tool.format_results(result)
