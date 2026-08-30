"""
网络搜索增强工具 - 弥娅核心模块
支持多引擎搜索、结果去重、智能摘要
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from config.config_utils import get_api_key, get_qq_config
from core.system_config import get_api_url

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = get_qq_config("web_search", "timeout", default=10)
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 排序权重（可从 qq_config.yaml web_search.ranking 覆盖）
_RANK_CFG = get_qq_config("web_search", "ranking", default={}) or {}
if not isinstance(_RANK_CFG, dict):
    _RANK_CFG = {}
_TITLE_WEIGHT = float(_RANK_CFG.get("title_match_weight", 3))
_SNIPPET_WEIGHT = float(_RANK_CFG.get("snippet_match_weight", 1))
_URL_WEIGHT = float(_RANK_CFG.get("url_match_weight", 1.5))
_AUTHORITY_BONUS = float(_RANK_CFG.get("authority_bonus", 2))
_OFFICIAL_BONUS = float(_RANK_CFG.get("official_domain_bonus", 1))

# 权威/官方域名关键词（用于排序加分）
_AUTHORITY_TLDS = (".gov", ".edu")
_OFFICIAL_HINTS = ("github.com", "docs.", "download.", "store.", "official", "www.", "developer.")


class EnhancedWebSearch:
    """增强版网络搜索工具"""

    def __init__(self):
        # 搜索引擎配置（优先免费无密钥引擎）
        self.search_engines = {
            "baidu": {
                "name": "百度",
                "url": "https://www.baidu.com/s",
                "params": {"wd": "", "rn": 10},
                "key_required": False,
                "parser": "_parse_baidu_response",
                "method": "GET",
                "headers": {
                    "User-Agent": _DEFAULT_USER_AGENT,
                },
            },
            "bing_cn": {
                "name": "Bing 国际 (中文)",
                "url": "https://www.bing.com/search",
                "params": {"q": "", "count": 10, "setmkt": "zh-CN"},
                "key_required": False,
                "parser": "_parse_bing_cn_response",
                "method": "GET",
                "headers": {
                    "User-Agent": _DEFAULT_USER_AGENT,
                },
            },
            "duckduckgo_html": {
                "name": "DuckDuckGo HTML",
                "url": "https://html.duckduckgo.com/html/",
                "params": {"q": ""},
                "key_required": False,
                "parser": "_parse_duckduckgo_html_response",
                "method": "POST",
            },
            "duckduckgo_api": {
                "name": "DuckDuckGo API",
                "url": get_api_url("duckduckgo") or "https://api.duckduckgo.com/",
                "params": {"q": "", "format": "json"},
                "key_required": False,
                "parser": "_parse_duckduckgo_response",
                "method": "GET",
            },
            "serpapi": {
                "name": "SerpAPI",
                "url": get_api_url("serpapi") or "https://serpapi.com/search",
                "params": {"q": "", "engine": "google", "num": 10},
                "key_required": True,
                "api_key_env": "SERPAPI_API_KEY",
                "parser": "_parse_serpapi_response",
                "method": "GET",
            },
            "tavily": {
                "name": "Tavily AI",
                "url": "https://api.tavily.com/search",
                "params": {
                    "query": "",
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 5,
                },
                "key_required": True,
                "api_key_env": "TAVILY_API_KEY",
                "parser": "_parse_tavily_response",
                "method": "POST",
                "json_body": True,
            },
        }
        # 默认免费引擎（duckduckgo_html 国内基本不可达，仅供显式指定）
        self._free_engines = ["baidu", "bing_cn"]

        # 如果配置了 TAVILY_API_KEY，优先使用 Tavily
        if self._has_tavily_key():
            self._free_engines.insert(0, "tavily")

    def search(self, query: str, engines: List[str] = None, num_results: int = 10) -> List[Dict[str, Any]]:
        if engines is None:
            engines = self._free_engines

        # 缓存命中直接返回（引擎结果较稳定，TTL 内无需重复请求）
        try:
            from webnet.ToolNet.tools.network.search_cache import get_search_cache

            cache = get_search_cache()
            cache_key = cache.make_key("web", query, engines, "")
            cached = cache.get(cache_key)
            if cached is not None:
                logger.info(f"搜索结果缓存命中: {query}")
                return list(cached)
        except Exception:
            cache = None
            cache_key = None

        # 多引擎并行请求（串行时一个引擎超时会拖慢整体）
        all_results = []
        engine_groups: Dict[str, List[Dict[str, Any]]] = {}
        if len(engines) > 1:
            try:
                with ThreadPoolExecutor(max_workers=min(len(engines), 6)) as pool:
                    futures = {
                        pool.submit(self._search_engine, query, engine, num_results): engine for engine in engines
                    }
                    for fut in as_completed(futures):
                        engine = futures[fut]
                        try:
                            engine_groups[engine] = fut.result() or []
                        except Exception as e:
                            logger.error(f"{engine}引擎搜索失败: {e}")
                            engine_groups[engine] = []
                for engine in engines:
                    engine_results = engine_groups.get(engine, [])
                    all_results.extend(engine_results)
                    logger.info(f"{engine}引擎返回 {len(engine_results)} 个结果")
            except Exception:
                logger.warning("并行搜索失败，回退串行执行")
                engine_groups = {}
        if not engine_groups:
            for engine in engines:
                try:
                    engine_results = self._search_engine(query, engine, num_results)
                    all_results.extend(engine_results)
                    logger.info(f"{engine}引擎返回 {len(engine_results)} 个结果")
                except Exception as e:
                    logger.error(f"{engine}引擎搜索失败: {e}")
        deduplicated = self._deduplicate_results(all_results)
        ranked = self._rank_results(deduplicated, query)
        logger.info(f"搜索完成，去重后 {len(ranked)} 个结果")

        if cache is not None and ranked:
            try:
                cache.set(cache_key, ranked)
            except Exception:
                pass

        return ranked

    def search_expanded(
        self,
        query: str,
        engines: List[str] = None,
        num_results: int = 10,
        resource_type: str = "any",
    ) -> List[Dict[str, Any]]:
        """智能扩展搜索：先构造多组增强查询，再合并去重。

        例: "红果短剧" (apk) → ["红果短剧", "红果短剧 APK 下载", "红果短剧 安卓版 下载 最新版", "红果短剧 apk download"]
        """
        try:
            from webnet.ToolNet.tools.network.query_optimizer import build_queries

            queries = build_queries(query, resource_type)
        except Exception:
            queries = [query]

        merged: List[Dict[str, Any]] = []
        seen = set()
        for q in queries:
            for r in self.search(q, engines=engines, num_results=num_results):
                url = (r.get("url") or "").strip()
                key = url or f"t:{r.get('title', '')}"
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                merged.append(r)
        return merged

    def _has_tavily_key(self) -> bool:
        return bool(get_api_key("TAVILY_API_KEY"))

    def _search_engine(self, query: str, engine: str, num_results: int) -> List[Dict[str, Any]]:
        if engine == "tavily":
            return self._search_tavily_core(query, num_results)

        if engine not in self.search_engines:
            logger.error(f"不支持的搜索引擎: {engine}")
            return []

        config = self.search_engines[engine]

        # 构建请求
        params = config["params"].copy()
        headers = config.get("headers", {}).copy()
        json_body = config.get("json_body", False)

        # 设置查询参数（兼容不同引擎的 query key）
        query_key = "query" if json_body else ("wd" if "wd" in params else "q")
        params[query_key] = query
        if "count" in params:
            params["count"] = num_results
        if "num" in params:
            params["num"] = num_results
        if "max_results" in params:
            params["max_results"] = min(num_results, 10)

        # 检查是否需要 API 密钥
        if config["key_required"]:
            api_key = get_api_key(config["api_key_env"])
            if not api_key:
                logger.warning(f"{engine}引擎需要API密钥: {config['api_key_env']}")
                return []
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            method = config.get("method", "GET")
            if method == "POST":
                if json_body:
                    response = requests.post(config["url"], json=params, timeout=_DEFAULT_TIMEOUT, headers=headers)
                else:
                    response = requests.post(config["url"], data=params, timeout=_DEFAULT_TIMEOUT, headers=headers)
            else:
                response = requests.get(config["url"], params=params, timeout=_DEFAULT_TIMEOUT, headers=headers)
            response.raise_for_status()

            # 使用配置指定的解析器
            parser_name = config.get("parser")
            if parser_name and hasattr(self, parser_name):
                parser_fn = getattr(self, parser_name)
                results = parser_fn(
                    response.text
                    if method == "POST"
                    else response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else response.text
                )
            else:
                # 旧的硬编码解析逻辑（向后兼容）
                data = response.json()
                if engine == "duckduckgo_api":
                    results = self._parse_duckduckgo_response(data)
                elif engine == "serpapi":
                    results = self._parse_serpapi_response(data)
                else:
                    results = []

            return results

        except requests.exceptions.Timeout:
            logger.error(f"{engine}引擎请求超时")
            return []
        except Exception as e:
            logger.error(f"{engine}引擎请求失败: {e}")
            return []

    def _parse_duckduckgo_html_response(self, html: str) -> List[Dict[str, Any]]:
        """解析 DuckDuckGo HTML 搜索结果（免费，无需 API）"""
        results = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select(".result"):
                title_el = item.select_one(".result__title a")
                snippet_el = item.select_one(".result__snippet")
                if title_el:
                    results.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": title_el.get("href", ""),
                            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                            "source": "duckduckgo_html",
                        }
                    )
        except Exception as e:
            logger.error(f"DuckDuckGo HTML 解析失败: {e}")
        return results

    def _parse_duckduckgo_response(self, data) -> List[Dict[str, Any]]:
        """解析 DuckDuckGo API JSON 响应"""
        results = []
        try:
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict) and "RelatedTopics" in data:
                for item in data["RelatedTopics"][:10]:
                    if isinstance(item, dict):
                        results.append(
                            {
                                "title": item.get("Text", item.get("Result", "")),
                                "url": item.get("FirstURL", ""),
                                "snippet": item.get("Text", item.get("Result", ""))[:200],
                                "source": "duckduckgo_api",
                            }
                        )
        except Exception:
            pass
        return results

    def _parse_tavily_response(self, data: Dict) -> List[Dict[str, Any]]:
        """解析 Tavily AI 搜索响应"""
        results = []
        try:
            if isinstance(data, str):
                data = json.loads(data)
            for item in data.get("results", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", item.get("snippet", ""))[:300],
                        "source": "tavily",
                    }
                )
            # 添加 AI 生成的答案
            if data.get("answer"):
                results.insert(
                    0,
                    {
                        "title": "AI 摘要",
                        "url": "",
                        "snippet": data["answer"][:500],
                        "source": "tavily_ai",
                    },
                )
        except Exception as e:
            logger.error(f"Tavily 解析失败: {e}")
        return results

    def _search_tavily_core(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Tavily 引擎复用 TavilyAISearch 单一实现"""
        try:
            from webnet.ToolNet.tools.network.tavily_search import TavilyAISearch

            searcher = TavilyAISearch()
            result = searcher.search(
                query=query,
                max_results=min(num_results, 20),
                search_depth="basic",
                include_answer=True,
            )
            if not result.get("success"):
                return []

            results = []
            for r in result.get("results", []):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", "")[:300],
                        "source": "tavily",
                    }
                )
            if result.get("answer"):
                results.insert(
                    0,
                    {
                        "title": "AI 摘要",
                        "url": "",
                        "snippet": result["answer"][:500],
                        "source": "tavily_ai",
                    },
                )
            return results
        except Exception as e:
            logger.error(f"Tavily 核心搜索失败: {e}")
            return []

    def _parse_baidu_response(self, html: str) -> List[Dict[str, Any]]:
        """解析百度 HTML 搜索结果（免费，无需 API，国内可用）"""
        results = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select(".result, .c-container"):
                title_el = item.select_one("h3 a") or item.select_one(".t a")
                snippet_el = item.select_one(".c-abstract") or item.select_one(".c-span-last p")
                if title_el:
                    url = str(title_el.get("href", ""))
                    if url and not url.startswith("http"):
                        url = "https://www.baidu.com" + url
                    results.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": url,
                            "snippet": snippet_el.get_text(strip=True)[:200] if snippet_el else "",
                            "source": "baidu",
                        }
                    )
        except Exception as e:
            logger.error(f"百度解析失败: {e}")
        return results

    def _parse_bing_cn_response(self, html: str) -> List[Dict[str, Any]]:
        """解析必应中国 HTML 搜索结果（免费，国内可用）"""
        results = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select("li.b_algo"):
                title_el = item.select_one("h2 a")
                snippet_el = item.select_one(".b_caption p") or item.select_one("p")
                if title_el:
                    results.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": title_el.get("href", ""),
                            "snippet": snippet_el.get_text(strip=True)[:200] if snippet_el else "",
                            "source": "bing_cn",
                        }
                    )
        except Exception as e:
            logger.error(f"必应中国解析失败: {e}")
        return results

    def _parse_serpapi_response(self, data: Dict) -> List[Dict[str, Any]]:
        """解析SerpAPI响应"""
        results = []

        if "organic_results" not in data:
            return results

        for item in data["organic_results"]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "displayUrl": item.get("link", ""),
                    "source": "serpapi",
                }
            )

        return results

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """搜索结果去重"""
        seen = set()
        deduplicated = []

        for result in results:
            # 使用URL作为唯一标识
            url = result.get("url", "")

            # 简化URL（去掉查询参数）
            clean_url = re.sub(r"\?.*", "", url)
            clean_url = clean_url.rstrip("/")

            if clean_url not in seen:
                seen.add(clean_url)
                deduplicated.append(result)

        return deduplicated

    @staticmethod
    def _tokenize(query: str) -> List[str]:
        """查询分词：拉丁词按空格切分，中文生成 2-gram（兼顾匹配粒度）"""
        tokens: List[str] = []
        latin = re.findall(r"[a-zA-Z0-9.+_\-]+", query.lower())
        tokens.extend(latin)
        cjk = re.findall(r"[\u4e00-\u9fff]+", query)
        for word in cjk:
            if len(word) == 1:
                tokens.append(word)
            else:
                tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
        return [t for t in tokens if t.strip()]

    def _rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """搜索结果排序和评分（多因子：标题/摘要/URL 命中 + 域名权威 + 摘要质量）"""
        query_keywords = self._tokenize(query)

        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            url = result.get("url", "").lower()
            source = result.get("source", "")

            # AI 摘要永远置顶
            if source in ("tavily_ai", "tavily-ai", "ai_summary"):
                result["relevance_score"] = 1000
                continue

            score = 0.0

            # 标题 / 摘要 / URL 关键词命中
            title_match = sum(1 for kw in query_keywords if kw in title)
            snippet_match = sum(1 for kw in query_keywords if kw in snippet)
            url_match = sum(1 for kw in query_keywords if kw in url)
            score += title_match * _TITLE_WEIGHT
            score += snippet_match * _SNIPPET_WEIGHT
            score += url_match * _URL_WEIGHT

            # 域名权威性
            if any(t in url for t in _AUTHORITY_TLDS):
                score += _AUTHORITY_BONUS
            elif "wikipedia.org" in url:
                score += _AUTHORITY_BONUS * 0.75
            if any(h in url for h in _OFFICIAL_HINTS):
                score += _OFFICIAL_BONUS

            # 摘要质量（过短/缺失的摘要降权；垃圾跟踪参数降权）
            if len(snippet) >= 30:
                score += 0.5
            elif not snippet:
                score -= 1
            if "utm_" in url or "spm=" in url:
                score -= 0.5

            result["relevance_score"] = round(score, 2)

        # 按分数排序（AI 摘要自然在最前）
        ranked = sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)

        return ranked

    @staticmethod
    def format_results_for_ai(results: List[Dict[str, Any]], max_items: int = 8, max_snippet: int = 120) -> str:
        """把搜索结果格式化为 AI 友好的可读文本（避免裸 repr 字典喂给 LLM）"""
        if not results:
            return "未找到相关结果"
        lines = []
        for i, r in enumerate(results[:max_items], 1):
            title = r.get("title") or "(无标题)"
            url = r.get("url") or ""
            snippet = (r.get("snippet") or "").replace("\n", " ").strip()
            if len(snippet) > max_snippet:
                snippet = snippet[:max_snippet] + "..."
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   链接: {url}")
            if snippet:
                lines.append(f"   摘要: {snippet}")
        return "\n".join(lines)

    def generate_summary(self, results: List[Dict[str, Any]], max_length: int = 500) -> str:
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
            summary_text = summary_text[: max_length - 3] + "..."

        return summary_text

    def search_with_ai_context(self, query: str, context: str, engines: List[str] = None) -> Dict[str, Any]:
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
        context_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}", context))

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
            "相关结果数": len(relevant_results),
        }


def search_command(query: str, engines: List[str] = None, options: Dict[str, Any] = None) -> Dict[str, Any]:
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
        results = searcher.search_with_ai_context(query, options["with_context"], engines)
    else:
        results_list = searcher.search(query, engines, options.get("num_results", 10))

        # 去重
        if options.get("deduplicate", True):
            results_list = searcher._deduplicate_results(results_list)

        results = {"搜索结果": results_list}

    # 生成摘要
    if options.get("generate_summary", False):
        results["摘要"] = searcher.generate_summary(results_list, options.get("max_summary_length", 500))

    # 添加元数据
    results["查询"] = query
    results["结果数"] = len(results_list)
    results["使用的引擎"] = engines or "全部"

    return results


# 别名，用于向后兼容
WebSearch = EnhancedWebSearch
