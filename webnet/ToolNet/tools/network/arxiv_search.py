"""
多源论文搜索工具

聚合 arXiv + OpenAlex + Semantic Scholar 三大免费学术源：
- 统一返回：标题 / 年份 / 被引 / 来源 / 摘要页链接 / PDF 直链
- 可选 Sci-Hub 镜像解析（默认关闭，在 qq_config.yaml web_search.scihub 开启）
- 三个源并行搜索，失败自动降级
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from config.config_utils import get_qq_config
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_SOURCES = ("arxiv", "openalex", "semanticscholar")


def _scihub_config() -> Dict[str, Any]:
    cfg = get_qq_config("web_search", "scihub", default={}) or {}
    return cfg if isinstance(cfg, dict) else {}


def _scihub_url(doi: str) -> str:
    """根据 DOI 构造 Sci-Hub 解析链接（需在配置中开启）"""
    cfg = _scihub_config()
    if not cfg.get("enabled"):
        return ""
    mirrors = cfg.get("mirrors") or []
    doi = (doi or "").strip()
    if not mirrors or not doi:
        return ""
    return f"{mirrors[0].rstrip('/')}/{doi}"


async def _search_arxiv(query: str, max_results: int) -> List[Dict[str, str]]:
    """arXiv API（Atom XML）"""
    import xml.etree.ElementTree as ET

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={
                    # 不预编码，httpx 会自动处理 URL 编码（预编码会导致 % 被二次转义）
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results: List[Dict[str, str]] = []
        for entry in root.findall(".//atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            link = entry.find("atom:id", ns)
            published = entry.find("atom:published", ns)
            title_text = title.text.strip().replace("\n", " ") if title is not None and title.text else "无标题"
            summary_text = (summary.text or "").strip()[:200] if summary is not None else ""
            link_text = link.text if link is not None and link.text else ""
            date = published.text[:10] if published is not None and published.text else ""
            aid = link_text.rstrip("/").rsplit("/", 1)[-1]
            results.append(
                {
                    "title": title_text,
                    "year": date[:4],
                    "source": "arXiv",
                    "url": link_text,
                    "pdf": f"https://arxiv.org/pdf/{aid}" if aid else "",
                    "summary": summary_text,
                    "doi": "",
                    "cited": "",
                }
            )
        return results
    except Exception as e:
        logger.warning(f"arXiv 搜索失败: {e}")
        return []


async def _search_openalex(query: str, max_results: int) -> List[Dict[str, str]]:
    """OpenAlex 开放学术 API（全学科，免费无 key）"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.openalex.org/works",
                params={
                    "search": query,
                    "per-page": max_results,
                    "sort": "relevance_score:desc",
                    "mailto": "miya@local",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        results: List[Dict[str, str]] = []
        for w in data.get("results", []):
            title = (w.get("display_name") or w.get("title") or "无标题").strip()
            doi = (w.get("doi") or "").replace("https://doi.org/", "").strip()
            loc = w.get("primary_location") or {}
            pdf = (loc.get("pdf_url") or "") if loc else ""
            landing = (loc.get("landing_page_url") or "") if loc else ""
            oa = w.get("open_access") or {}
            if not pdf:
                pdf = oa.get("oa_url") or ""
            results.append(
                {
                    "title": title,
                    "year": str(w.get("publication_year") or ""),
                    "source": "OpenAlex",
                    "url": landing or doi,
                    "pdf": pdf,
                    "summary": "",
                    "doi": doi,
                    "cited": str(w.get("cited_by_count") or ""),
                }
            )
        return results
    except Exception as e:
        logger.warning(f"OpenAlex 搜索失败: {e}")
        return []


async def _search_semanticscholar(query: str, max_results: int) -> List[Dict[str, str]]:
    """Semantic Scholar Graph API（免费无 key，有限流；429 自动退避重试一次）"""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,url,year,citationCount,openAccessPdf,externalIds",
    }
    try:
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 429 and attempt == 1:
                        await asyncio.sleep(3)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt == 1:
                    await asyncio.sleep(3)
                    continue
                raise
        results: List[Dict[str, str]] = []
        for p in data.get("data", []):
            pdf = ((p.get("openAccessPdf") or {}).get("url") or "") if p.get("openAccessPdf") else ""
            doi = ((p.get("externalIds") or {}).get("DOI") or "").strip()
            results.append(
                {
                    "title": (p.get("title") or "无标题").strip(),
                    "year": str(p.get("year") or ""),
                    "source": "SemanticScholar",
                    "url": p.get("url") or "",
                    "pdf": pdf,
                    "summary": "",
                    "doi": doi,
                    "cited": str(p.get("citationCount") or ""),
                }
            )
        return results
    except Exception as e:
        logger.warning(f"Semantic Scholar 搜索失败: {e}")
        return []


class ArxivSearchTool(BaseTool):
    """多源论文搜索工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "arxiv_search",
            "description": (
                "多源论文搜索。聚合 arXiv、OpenAlex、Semantic Scholar 三大免费学术库，"
                "返回论文标题、年份、被引数、摘要页链接和 PDF 直链。"
                "当用户问'论文'、'找 paper'、'查文献'、'找PDF'时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或论文标题"},
                    "max_results": {
                        "type": "integer",
                        "description": "每个来源返回结果数量，默认 5",
                        "default": 5,
                    },
                    "source": {
                        "type": "string",
                        "enum": ["all", "arxiv", "openalex", "semanticscholar"],
                        "description": "搜索来源，默认 all 并行搜索",
                        "default": "all",
                    },
                    "scihub": {
                        "type": "boolean",
                        "description": "是否附带 Sci-Hub 解析链接（需在配置中开启 scihub 开关才生效）",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        query = args.get("query", "")
        max_results = min(int(args.get("max_results", 5) or 5), 20)
        source = args.get("source", "all") or "all"
        want_scihub = bool(args.get("scihub", False))

        if not query:
            return "请提供搜索关键词"

        try:
            if source not in _SOURCES:
                source = "all"
            sources = _SOURCES if source == "all" else [source]

            handlers = {
                "arxiv": _search_arxiv,
                "openalex": _search_openalex,
                "semanticscholar": _search_semanticscholar,
            }
            groups = await asyncio.gather(
                *(handlers[s](query, max_results) for s in sources),
                return_exceptions=True,
            )

            all_papers: List[Dict[str, str]] = []
            seen_titles = set()
            for group in groups:
                if isinstance(group, BaseException) or not isinstance(group, list):
                    continue
                for p in group:
                    key = p.get("title", "").strip().lower()[:80]
                    if key and key in seen_titles:
                        continue
                    if key:
                        seen_titles.add(key)
                    all_papers.append(p)

            if not all_papers:
                return f"未找到与'{query}'相关的论文"

            lines = [f"【论文搜索结果: {query}】共 {len(all_papers)} 篇\n"]
            scihub_on = want_scihub and bool(_scihub_config().get("enabled"))
            for i, p in enumerate(all_papers[: max_results * 3], 1):
                meta = []
                if p.get("year"):
                    meta.append(f"年份: {p['year']}")
                if p.get("cited"):
                    meta.append(f"被引: {p['cited']}")
                if p.get("doi"):
                    meta.append(f"DOI: {p['doi']}")
                meta_str = f" | {' | '.join(meta)}" if meta else ""
                lines.append(f"{i}. [{p.get('source', '')}] {p['title']}")
                if meta_str:
                    lines.append(f"   {meta_str.strip()}")
                if p.get("summary"):
                    lines.append(f"   摘要: {p['summary']}...")
                if p.get("url"):
                    lines.append(f"   链接: {p['url']}")
                if p.get("pdf"):
                    lines.append(f"   📄 PDF: {p['pdf']}")
                if scihub_on and p.get("doi"):
                    lines.append(f"   🔓 Sci-Hub: {_scihub_url(p['doi'])}")
                lines.append("")

            lines.append("💡 下载 PDF: download_file(url=<PDF直链>)")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"论文搜索失败: {e}")
            return f"搜索失败: {str(e)[:80]}"


def get_arxiv_search_tool():
    return ArxivSearchTool()
