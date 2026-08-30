"""
网页爬取工具

抓取网页内容并提取正文文本，支持 Markdown 格式输出。
- 自动探测编码（响应头 → meta 标签 → chardet），避免中文乱码
- 过滤导航/脚本/样式等噪声节点，优先提取 <article>/<main> 正文
- 二进制/非网页内容直接拒绝，避免误解析
"""

import logging
import os
import re
from typing import Any, Dict, Optional

import httpx
from bs4 import BeautifulSoup

from config.config_utils import get_qq_config
from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

XXAPI_BASE_URL = os.environ.get("XXAPI_BASE_URL", get_api_url("xxapi") or "https://v2.xxapi.cn")

# 噪声标签：对正文无贡献，直接剔除
_NOISE_TAGS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "select",
    "textarea",
    "svg",
    "canvas",
    "img",
    "picture",
    "video",
    "audio",
]

# 非网页 Content-Type（返回二进制/下载内容）
_BINARY_CONTENT_TYPES = (
    "application/pdf",
    "application/zip",
    "application/octet-stream",
    "image/",
    "audio/",
    "video/",
    "application/vnd.",
    "application/x-rar",
    "application/x-7z-compressed",
    "application/gzip",
    "application/x-tar",
)


def _default_timeout() -> float:
    try:
        return float(get_qq_config("web_search", "crawl_timeout", default=30))
    except (TypeError, ValueError):
        return 30.0


def _default_ua() -> str:
    return str(
        get_qq_config(
            "web_search",
            "user_agent",
            default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
    )


def _make_soup(html: str) -> BeautifulSoup:
    """优先 lxml 解析（更快更稳），失败回退 html.parser"""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _decode_html(content: bytes, content_type: str = "") -> str:
    """按 响应头 charset → meta 标签 → chardet 探测 的顺序解码，避免乱码"""
    charset = None
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.IGNORECASE)
    if m:
        charset = m.group(1)

    if not charset:
        head = content[:2048].decode("ascii", "ignore")
        m2 = re.search(r'charset=["\']?([\w\-]+)', head, re.IGNORECASE)
        if m2:
            charset = m2.group(1)

    if charset:
        try:
            return content.decode(charset, errors="replace")
        except LookupError:
            pass

    try:
        import chardet

        guess = chardet.detect(content)
        enc = guess.get("encoding") if guess and guess.get("confidence", 0) > 0.5 else None
        if enc:
            return content.decode(enc, errors="replace")
    except Exception:
        pass

    return content.decode("utf-8", errors="replace")


def _extract_text(html: str) -> str:
    """剔除噪声节点，优先提取正文容器，输出干净文本"""
    soup = _make_soup(html)

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    text = container.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 合并过短的行，去掉相邻重复行
    cleaned: list[str] = []
    for line in lines:
        if cleaned and line == cleaned[-1]:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    meta_desc = soup.find("meta", {"name": "description"})
    if meta_desc:
        content = meta_desc.get("content", "")
        return content.strip()
    meta_og = soup.find("meta", {"property": "og:description"})
    if meta_og:
        return meta_og.get("content", "").strip()
    return ""


class CrawlWebpageTool(BaseTool):
    """网页爬取工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "crawl_webpage",
            "description": """网页内容抓取工具。

当用户需要获取特定网页的内容时使用此工具。
可以抓取网页并提取文本、标题等信息。

示例:
- 抓取: 获取百度首页的内容
- 爬取: https://example.com 的内容""",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的网页URL",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "最大字符数，默认4096",
                        "default": 4096,
                    },
                },
                "required": ["url"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        url = args.get("url", "").strip()
        if not url:
            return "请提供要抓取的URL"

        if not url.startswith(("http://", "https://")):
            return "URL必须以http://或https://开头"

        max_chars = args.get("max_chars", args.get("max_length", 4096))

        try:
            async with httpx.AsyncClient(
                timeout=_default_timeout(),
                follow_redirects=True,
                headers={"User-Agent": _default_ua()},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if any(content_type.startswith(t) for t in _BINARY_CONTENT_TYPES):
                    return f"该 URL 返回的是非网页内容（{content_type.split(';')[0]}），无法提取正文"

                html = _decode_html(response.content, content_type)

                # JSON / 纯文本 API：直接返回原始内容，不做 HTML 解析
                if content_type.startswith("application/json"):
                    text = html
                    if max_chars > 0 and len(text) > max_chars:
                        text = text[:max_chars] + "\n\n...（内容已截断）"
                    return f"# 抓取结果（JSON）\n\n**URL**: {url}\n\n```json\n{text}\n```"

                soup = _make_soup(html)

                title = _extract_title(soup)
                description = _extract_description(soup)
                text = _extract_text(html)

                if max_chars > 0 and len(text) > max_chars:
                    text = text[:max_chars] + "\n\n...（内容已截断）"

                result = "# 网页抓取结果\n\n"
                result += f"**URL**: {url}\n\n"

                if title:
                    result += f"**标题**: {title}\n\n"

                if description:
                    result += f"**描述**: {description}\n\n"

                result += "---\n\n## 内容\n\n"
                result += text

                return result

        except httpx.TimeoutException:
            logger.error(f"网页抓取超时: {url}")
            return "网页抓取超时，请稍后重试"
        except httpx.HTTPStatusError as e:
            logger.error(f"网页抓取HTTP错误: {e}")
            return f"网页抓取失败：HTTP {e.response.status_code}"
        except Exception as e:
            logger.exception(f"网页抓取失败: {e}")
            return f"网页抓取失败：{str(e)}"


def get_crawl_webpage_tool():
    return CrawlWebpageTool()
