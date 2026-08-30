"""
网络搜索增强工具 - 弥娅核心模块
支持多引擎搜索、结果去重、智能摘要
"""

import requests
from typing import Dict, List, Optional, Any
import re
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class EnhancedWebSearch:
    """增强版网络搜索工具"""

    def __init__(self):
        # 搜索引擎配置
        self.search_engines = {
            "bing": {
                "name": "必应",
                "url": "https://api.bing.microsoft.com/v7.0/search",
                "params": {"q": "", "count": 10},
                "key_required": True,
                "api_key_env": "BING_API_KEY"
            },
            "duckduckgo": {
                "name": "DuckDuckGo",
                "url": "https://api.duckduckgo.com/",
                "params": {"q": "", "format": "json"},
                "key_required": False
            },
            "serpapi": {
                "name": "SerpAPI",
                "url": "https://serpapi.com/search",
                "params": {"q": "", "engine": "google", "num": 10},
                "key_required": True,
                "api_key_env": "SERPAPI_API_KEY"
            }
        }

    def search(
        self,
        query: str,
        engines: List[str] = None,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            engines: 使用的搜索引擎列表（None=全部）
            num_results: 每个引擎返回的结果数

        Returns:
            去重后的搜索结果
        """
        if engines is None:
            engines = list(self.search_engines.keys())

        all_results = []

        for engine in engines:
            try:
                engine_results = self._search_engine(query, engine, num_results)
                all_results.extend(engine_results)
                logger.info(f"{engine}引擎返回 {len(engine_results)} 个结果")
            except Exception as e:
                logger.error(f"{engine}引擎搜索失败: {e}")

        # 去重
        deduplicated = self._deduplicate_results(all_results)

        # 排序（相关性评分）
        ranked = self._rank_results(deduplicated, query)

        logger.info(f"搜索完成，去重后 {len(ranked)} 个结果")
        return ranked

    def _search_engine(
        self,
        query: str,
        engine: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """调用单个搜索引擎"""
        if engine not in self.search_engines:
            logger.error(f"不支持的搜索引擎: {engine}")
            return []

        config = self.search_engines[engine]

        # 检查是否需要API密钥
        if config["key_required"]:
            import os
            api_key = os.environ.get(config["api_key_env"], "")
            if not api_key:
                logger.warning(f"{engine}引擎需要API密钥: {config['api_key_env']}")
                return []
            config["params"]["api_key"] = api_key

        # 构建请求
        params = config["params"].copy()
        params["q"] = query
        if "count" in params:
            params["count"] = num_results
        if "num" in params:
            params["num"] = num_results

        try:
            response = requests.get(config["url"], params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # 解析不同引擎的响应格式
            results = []
            if engine == "bing":
                results = self._parse_bing_response(data)
            elif engine == "duckduckgo":
                results = self._parse_duckduckgo_response(data)
            elif engine == "serpapi":
                results = self._parse_serpapi_response(data)

            return results

        except requests.exceptions.Timeout:
            logger.error(f"{engine}引擎请求超时")
            return []
        except Exception as e:
            logger.error(f"{engine}引擎请求失败: {e}")
            return []

    def _parse_bing_response(self, data: Dict) -> List[Dict[str, Any]]:
        """解析Bing API响应"""
        results = []

        if "webPages" not in data:
            return results

        for item in data["webPages"]["value"]:
            results.append({
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "displayUrl": item.get("displayUrl", ""),
                "source": "bing"
            })

        return results

    def _parse_duckduckgo_response(self, data: Dict) -> List[Dict[str, Any]]:
        """解析DuckDuckGo API响应"""
        results = []

        if "Results" not in data or "MainResults" not in data:
            return results

        # 使用RelatedTopics作为备选
        results_list = data.get("Results", data.get("MainResults", []))

        for item in results_list[:10]:
            results.append({
                "title": item.get("Text", ""),
                "url": item.get("FirstURL", ""),
                "snippet": item.get("Text", ""),
                "source": "duckduckgo"
            })

        return results

    def _parse_serpapi_response(self, data: Dict) -> List[Dict[str, Any]]:
        """解析SerpAPI响应"""
        results = []

        if "organic_results" not in data:
            return results

        for item in data["organic_results"]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "displayUrl": item.get("link", ""),
                "source": "serpapi"
            })

        return results

    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """搜索结果去重"""
        seen = set()
        deduplicated = []

        for result in results:
            # 使用URL作为唯一标识
            url = result.get("url", "")

            # 简化URL（去掉查询参数）
            clean_url = re.sub(r'\?.*', '', url)
            clean_url = clean_url.rstrip('/')

            if clean_url not in seen:
                seen.add(clean_url)
                deduplicated.append(result)

        return deduplicated

    def _rank_results(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """搜索结果排序和评分"""
        query_keywords = set(query.lower().split())

        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            url = result.get("url", "")

            # 计算相关性分数
            score = 0

            # 标题匹配
            title_match = sum(1 for kw in query_keywords if kw in title)
            score += title_match * 3

            # 摘要匹配
            snippet_match = sum(1 for kw in query_keywords if kw in snippet)
            score += snippet_match * 1

            # URL权威性加分
            if ".gov" in url or ".edu" in url:
                score += 2
            elif "wikipedia.org" in url:
                score += 1.5

            result["relevance_score"] = score

        # 按分数排序
        ranked = sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)

        return ranked

    def generate_summary(
        self,
        results: List[Dict[str, Any]],
        max_length: int = 500
    ) -> str:
        """
        生成搜索结果摘要

        Args:
            results: 搜索结果列表
            max_length: 最大摘要长度

        Returns:
            摘要文本
        """
        if not results:
            return "未找到相关结果"

        # 提取关键信息
        top_results = results[:5]  # 只总结前5个

        summary_parts = []

        for i, result in enumerate(top_results, 1):
            title = result.get("title", "未知标题")
            snippet = result.get("snippet", "")

            # 截断长摘要
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."

            summary_parts.append(f"{i}. {title}: {snippet}")

        # 组合摘要
        summary_text = "搜索结果摘要：\n" + "\n".join(summary_parts)

        # 如果超过最大长度，截断
        if len(summary_text) > max_length:
            summary_text = summary_text[:max_length-3] + "..."

        return summary_text

    def search_with_ai_context(
        self,
        query: str,
        context: str,
        engines: List[str] = None
    ) -> Dict[str, Any]:
        """
        带AI上下文的搜索

        Args:
            query: 搜索查询
            context: 上下文信息（来自之前的对话）
            engines: 搜索引擎列表

        Returns:
            搜索结果和上下文相关性分析
        """
        # 执行搜索
        results = self.search(query, engines)

        # 分析结果与上下文的相关性
        context_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', context))

        relevant_results = []
        for result in results:
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            # 检查标题和摘要中是否包含上下文关键词
            relevance = 0
            for kw in context_keywords:
                if kw in title or kw in snippet:
                    relevance += 1

            result["context_relevance"] = relevance

            if relevance > 0:
                relevant_results.append(result)

        return {
            "搜索结果": relevant_results if relevant_results else results,
            "上下文关键词": list(context_keywords),
            "相关结果数": len(relevant_results)
        }


def search_command(
    query: str,
    engines: List[str] = None,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    搜索命令统一接口

    Args:
        query: 搜索查询
        engines: 搜索引擎列表
        options:
            {
                "num_results": 10,
                "deduplicate": True,
                "generate_summary": True,
                "with_context": "",
                "max_summary_length": 500
            }

    Returns:
        搜索结果
    """
    if options is None:
        options = {}

    searcher = EnhancedWebSearch()

    # 执行搜索
    if "with_context" in options:
        results = searcher.search_with_ai_context(
            query,
            options["with_context"],
            engines
        )
    else:
        results_list = searcher.search(
            query,
            engines,
            options.get("num_results", 10)
        )

        # 去重
        if options.get("deduplicate", True):
            results_list = searcher._deduplicate_results(results_list)

        results = {"搜索结果": results_list}

    # 生成摘要
    if options.get("generate_summary", False):
        results["摘要"] = searcher.generate_summary(
            results_list,
            options.get("max_summary_length", 500)
        )

    # 添加元数据
    results["查询"] = query
    results["结果数"] = len(results_list)
    results["使用的引擎"] = engines or "全部"

    return results
