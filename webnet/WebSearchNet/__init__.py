"""
WebSearchNet - Web 搜索子网

弥娅 Web 搜索能力子网：
- DuckDuckGo 搜索（免费）
- Bing 搜索（需 API Key）
- Google 搜索（需 API Key）
"""
from .tools.web_search import WebSearch, GetAvailableSearchEngines, GetSearchHistory

__all__ = [
    'WebSearch',
    'GetAvailableSearchEngines',
    'GetSearchHistory'
]
