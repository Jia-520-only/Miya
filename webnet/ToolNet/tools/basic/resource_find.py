"""
通用资源搜索工具

一个工具替代 image_search + apk_search + 未来所有文件类搜索：
- 搜索引擎找页面 → 爬虫提取资源链接 → 按类型分类返回
- 支持: image / video / apk / document / archive / audio / any
"""

import asyncio
import contextlib
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
}

_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"


def _get_proxy() -> Optional[str]:
    """读取 web_search.proxy 配置（如 http://127.0.0.1:7890），未配置返回 None"""
    try:
        from config.config_utils import get_qq_config

        p = get_qq_config("web_search", "proxy", default="") or ""
        return str(p).strip() or None
    except Exception:
        return None


def _find_chrome() -> Optional[str]:
    """定位 Chrome/Chromium 可执行文件，找不到返回 None"""
    for name in ("chrome", "chromium", "google-chrome", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


async def _open_page(url: str):
    """打开浏览器并加载页面，返回 (page, browser, playwright)；无 Chrome 返回 None"""
    chrome = _find_chrome()
    if not chrome:
        logger.warning("未找到 Chrome/Chromium，跳过浏览器兜底")
        return None
    from playwright.async_api import async_playwright

    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=chrome,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=_BROWSER_UA,
            locale="zh-CN",
        )
        # stealth 伪装（提高 Cloudflare JS 挑战通过率）
        try:
            from playwright_stealth import Stealth

            await Stealth().apply_stealth_async(context)
        except Exception:
            pass
        page = await context.new_page()
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        return page, browser, p
    except Exception:
        with contextlib.suppress(Exception):
            await p.stop()
        return None


_TYPE_EXTRACTORS = {
    "image": [
        r'<img[^>]*src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']',
        r'<img[^>]*src=["\'](//[^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']',
        r'<meta[^>]*property="og:image"[^>]*content="(https?://[^"]+)"',
        r'https?://[^"\s]+\.(?:jpg|jpeg|png|webp|gif)\?[^"\s]*',
    ],
    "video": [
        r'https?://[^"\'\s]+\.(?:mp4|mkv|webm|avi|mov|flv)[^"\'\s]*',
        r'<video[^>]*src=["\'](https?://[^"\']+)["\']',
        r'<source[^>]*src=["\'](https?://[^"\']+\.(?:mp4|webm)[^"\']*)["\']',
        r'<meta[^>]*property="og:video"[^>]*content="(https?://[^"]+)"',
    ],
    "apk": [
        r'https?://[^"\'\s]+\.apk[^"\'\s]*',
        r'https?://imtt\.dd\.qq\.com[^"\'\s]+',
        r'"apkUrl"\s*:\s*"([^"]+)"',
        r'"downloadUrl"\s*:\s*"([^"]+)"',
        r'data-apk-url\s*=\s*"([^"]+)"',
    ],
    "program": [
        r'https?://[^"\'\s]+\.(?:exe|msi|dmg|pkg|deb|rpm|AppImage|sh|run|bin|appxbundle|msixbundle)[^"\'\s]*',
        r'<a[^>]*href="([^"]+\.(?:exe|msi|dmg|deb|rpm|AppImage)[^"]*)"[^>]*>',
        r'"downloadUrl"\s*:\s*"([^"]+\.(?:exe|msi)[^"]*)"',
    ],
    "document": [
        r'https?://[^"\'\s]+\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|epub|mobi|rtf|odt|ods|odp)[^"\'\s]*',
        r'<a[^>]*href="([^"]+\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|epub)[^"]*)"[^>]*>',
    ],
    "archive": [
        r'https?://[^"\'\s]+\.(?:zip|rar|7z|tar|gz|bz2|xz|zst|lz4|iso|cab)[^"\'\s]*',
    ],
    "audio": [
        r'https?://[^"\'\s]+\.(?:mp3|wav|flac|aac|ogg|m4a|opus|wma|mid|midi)[^"\'\s]*',
        r'<audio[^>]*src=["\'](https?://[^"\']+)["\']',
    ],
}

_EXCLUDE_DOMAINS = [
    "google.com",
    "facebook.com",
    "twitter.com",
    "doubleclick",
    "analytics",
    "pixel",
    "bing.com",
    "microsoft.com",
    # 广告/统计/垃圾域名（命中直接过滤）
    "googlesyndication",
    "googletagmanager",
    "adnxs",
    "taboola",
    "outbrain",
    "addthis",
    "sharethis",
    "onesignal",
    "hm.baidu",
    "cnzz.com",
    "umeng.com",
    "51.la",
]

# 官方/可信资源域名（排序加分）
_PREFERRED_DOMAINS = [
    "github.com",
    "gitee.com",
    "gitlab.com",
    "apkpure.com",
    "apkmirror.com",
    "coolapk.com",
    "uptodown.com",
    "f-droid.org",
    "microsoft.com",
    "apple.com",
    "adobe.com",
    "python.org",
    "pypi.org",
    "npmjs.com",
    "rust-lang.org",
    "golang.org",
    "docker.com",
    "archive.org",
    "wikipedia.org",
    "pixiv.net",
    "danbooru.donmai.us",
    "yande.re",
    "bilibili.com",
    "app.mi.com",
    "sj.qq.com",
]

# 用户可见消息模板（可在 text_config.json 的 resource_search 节覆盖）
_DEFAULT_MESSAGES = {
    "query_required": "❌ 请输入搜索关键词",
    "found_header": "🔍 关于「{query}」找到 {count} 个资源（智能扩展了 {nq} 组查询，{ns} 个来源）",
    "section_direct": "【直链资源 · 可直接下载】",
    "section_crawled": "【页面提取 · 来自搜索结果页】",
    "recommend_hint": "💡 推荐优先尝试第 {index} 个（{reason}）",
    "download_hint": "💡 下载: download_file(url=<链接>) | 发送: send_platform_file",
    "no_result": "🔍 未找到关于「{query}」的资源",
    "no_result_with_pages": "🔍 未找到「{query}」的直接{resource_type}链接。以下为相关页面：",
    "site_hint": "\n💡 指定站点「{site}」未取到资源，可能是被墙或需要登录，建议去掉 site 参数改用全网搜索",
    "error": "❌ 搜索失败: {error}",
}


def _msg(key: str, **kwargs) -> str:
    """读取消息模板（text_config.json 优先，内置默认兜底）"""
    tpl = get_text_message("resource_search", key, **kwargs)
    if tpl:
        return tpl
    default = _DEFAULT_MESSAGES.get(key, "")
    try:
        return default.format(**kwargs) if kwargs else default
    except KeyError:
        return default


async def _tavily_search(query: str, include_images: bool = False) -> List[Dict[str, str]]:
    from config.config_utils import get_api_key

    api_key = get_api_key("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        from webnet.ToolNet.tools.network.tavily_search import TavilyAISearch

        searcher = TavilyAISearch(api_key=api_key)
        data = await searcher.search_async(
            query=query,
            max_results=8,
            search_depth="advanced",
            include_images=include_images,
            include_image_descriptions=include_images,
        )
        if not data.get("success"):
            return []
        results = []

        # 文本搜索结果
        for r in data.get("results", []):
            u = r.get("url", "")
            if u:
                results.append({"title": r.get("title", ""), "url": u, "source": "Tavily"})

        # Tavily 原生图片结果（仅图片类搜索需要）
        if include_images:
            for img in data.get("images", []):
                url = img.get("url", "")
                if url:
                    results.append({"title": img.get("description", ""), "url": url, "source": "Tavily-Image"})

        return results[:10]
    except Exception:
        return []


# ── 智能多引擎搜索（Tavily 优先 + 免费引擎兜底 + 查询增强） ──


async def _smart_web_search(query: str, resource_type: str) -> List[Dict[str, str]]:
    """智能网页搜索：查询增强并行 + Tavily 优先 + bing_cn/baidu 免费兜底。

    即使没有配置 TAVILY_API_KEY，也能通过免费引擎找到相关页面，
    解决此前「无 key 时非图片资源搜索全灭」的问题。
    """
    try:
        from webnet.ToolNet.tools.network.query_optimizer import build_queries

        queries = build_queries(query, resource_type)
    except Exception:
        queries = []
    if not queries:
        queries = [query.strip()]

    has_tavily = False
    try:
        from config.config_utils import get_api_key

        has_tavily = bool(get_api_key("TAVILY_API_KEY"))
    except Exception:
        pass

    loop = asyncio.get_event_loop()
    tasks = []
    want_images = resource_type in ("image", "any")

    # Tavily（最强，付费）：只跑前 2 个增强查询，控制配额消耗
    if has_tavily:
        for q in queries[:2]:
            tasks.append(_tavily_search(q, include_images=want_images))

    # 免费引擎：全部增强查询都跑，保证无 key 也有结果
    try:
        from webnet.ToolNet.tools.network.web_search import EnhancedWebSearch

        searcher = EnhancedWebSearch()
        for q in queries:
            tasks.append(loop.run_in_executor(None, searcher.search, q, ["bing_cn", "baidu"], 8))
    except Exception:
        logger.warning("免费引擎搜索不可用，仅依赖 Tavily", exc_info=True)

    groups = await asyncio.gather(*tasks, return_exceptions=True)

    merged: List[Dict[str, str]] = []
    seen = set()
    for group in groups:
        if isinstance(group, BaseException) or not isinstance(group, list):
            continue
        for r in group:
            if not isinstance(r, dict):
                continue
            u = (r.get("url") or "").strip()
            if not u:
                continue
            clean = re.sub(r"\?.*", "", u).rstrip("/").lower()
            if clean in seen:
                continue
            seen.add(clean)
            merged.append({"title": r.get("title", ""), "url": u, "source": r.get("source", "Web")})
        if len(merged) >= 20:
            break

    return merged


def _rank_resource_results(items: List[Dict[str, str]], resource_type: str = "any") -> List[Dict[str, str]]:
    """资源结果排序：直链优先 > 官方域名加分 > 深层/页面提取。

    Args:
        items: [{title, url, source}]
        resource_type: 资源类型（用于扩展名匹配加分）
    """
    type_exts = {
        "image": (".jpg", ".jpeg", ".png", ".webp", ".gif"),
        "video": (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"),
        "apk": (".apk",),
        "program": (".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"),
        "document": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".mobi", ".txt", ".md"),
        "archive": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"),
        "audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus"),
    }
    exts = type_exts.get(resource_type, ())

    for it in items:
        url = (it.get("url") or "").lower()
        src = str(it.get("source", ""))
        score = 0.0

        # 来源置信度
        if any(
            k in src
            for k in (
                "直链",
                "Tavily-Image",
                "yande.re",
                "konachan",
                "safebooru",
                "nhentai",
                "rule34",
                "gelbooru",
                "pixiv",
                "iwara",
                "pornhub",
                "禁漫",
                "B站",
                "应用宝",
                "浏览器-",
            )
        ):
            score += 3.0
        elif "深层提取" in src:
            score += 1.5
        elif "页面提取" in src or "兜底爬取" in src:
            score += 1.0

        # 扩展名与类型精确匹配
        if exts and any(url.endswith(e) or f"{e}?" in url or f"{e}&" in url for e in exts):
            score += 2.0

        # 官方/可信域名加分，垃圾域名减分
        if any(d in url for d in _PREFERRED_DOMAINS):
            score += 1.5
        if any(d in url for d in _EXCLUDE_DOMAINS):
            score -= 3.0

        it["_score"] = score

    return sorted(items, key=lambda x: float(x.get("_score", 0.0)), reverse=True)


def _is_direct_source(src: str) -> bool:
    """判断是否为可直接下载的直链来源"""
    return any(
        k in src
        for k in (
            "直链",
            "Tavily-Image",
            "yande.re",
            "konachan",
            "safebooru",
            "nhentai",
            "rule34",
            "gelbooru",
            "pixiv",
            "iwara",
            "pornhub",
            "禁漫",
            "B站",
            "应用宝",
            "浏览器-",
        )
    )


async def _moe_booru_search(query: str, count: int, site: str = "yande.re") -> List[Dict[str, str]]:
    """搜索 moebooru 系图板（yande.re / konachan，含 NSFW；同一 post.json API）"""
    api_map = {
        "yande.re": "https://yande.re/post.json",
        "konachan": "https://konachan.com/post.json",
    }
    api = api_map.get(site)
    if not api:
        return []
    try:
        tags = query.strip().replace(" ", "_").replace("，", "_").replace("、", "_")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api,
                params={"tags": tags, "limit": min(count + 5, 30)},
                headers=_HEADERS,
                proxy=_get_proxy(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        results = []
        seen = set()
        for post in data:
            if len(results) >= count:
                break
            url = post.get("file_url", "") or post.get("sample_url", "")
            if url and url not in seen:
                seen.add(url)
                tags_str = post.get("tags", "")
                rating = post.get("rating", "")
                results.append(
                    {
                        "title": f"[{rating}] {tags_str[:60]}",
                        "url": url,
                        "source": site,
                    }
                )
        return results
    except asyncio.TimeoutError:
        logger.warning(f"{site} 搜索超时（已跳过）")
        return []
    except Exception as e:
        logger.warning(f"{site} 搜索失败: {type(e).__name__}: {e}")
        return []


async def _yandere_search(query: str, count: int) -> List[Dict[str, str]]:
    """搜索 yande.re（兼容包装）"""
    return await _moe_booru_search(query, count, "yande.re")


async def _safebooru_search(query: str, count: int) -> List[Dict[str, str]]:
    """搜索 Safebooru（SFW，dapi XML 接口）"""
    try:
        import xml.etree.ElementTree as ET

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://safebooru.org/index.php",
                params={
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "tags": query.strip().replace(" ", "+"),
                    "limit": min(count + 5, 30),
                },
                headers=_HEADERS,
                proxy=_get_proxy(),
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                xml_text = await resp.text()
        root = ET.fromstring(xml_text)
        results = []
        seen = set()
        for post in root.findall("post"):
            if len(results) >= count:
                break
            file_url = post.get("file_url", "")
            if file_url and file_url not in seen:
                seen.add(file_url)
                tags_str = (post.get("tags") or "")[:60]
                results.append({"title": tags_str, "url": file_url, "source": "safebooru"})
        return results
    except asyncio.TimeoutError:
        logger.warning("safebooru 搜索超时（已跳过）")
        return []
    except Exception as e:
        logger.warning(f"safebooru 搜索失败: {type(e).__name__}: {e}")
        return []


# ── Pixiv ──


async def _pixiv_search(query: str, count: int) -> List[Dict[str, str]]:
    """Pixiv ajax 搜索（无需登录可搜 SFW；配置 PIXIV_COOKIE 后含 R18）"""
    try:
        from urllib.parse import quote

        from config.config_utils import get_api_key

        cookie = (get_api_key("PIXIV_COOKIE") or "").strip()
        headers = {**_HEADERS, "Referer": "https://www.pixiv.net/"}
        if cookie:
            headers["Cookie"] = cookie

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.pixiv.net/ajax/search/artworks/{quote(query)}",
                params={"word": query, "order": "date_d", "mode": "all", "p": 1, "lang": "zh"},
                headers=headers,
                proxy=_get_proxy(),
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                data = await resp.json()
            items = ((data.get("body") or {}).get("illustManga") or {}).get("data") or []

            # 并发拿原图直链
            async def _detail(pid: str) -> str:
                try:
                    async with session.get(
                        f"https://www.pixiv.net/ajax/illust/{pid}",
                        headers=headers,
                        proxy=_get_proxy(),
                        timeout=aiohttp.ClientTimeout(total=12),
                    ) as r2:
                        d2 = await r2.json()
                    return (d2.get("body") or {}).get("urls", {}).get("original", "")
                except Exception:
                    return ""

            picked = items[:count]
            originals = await asyncio.gather(*(_detail(str(it.get("id", ""))) for it in picked), return_exceptions=True)

        results = []
        for it, orig in zip(picked, originals, strict=False):
            pid = str(it.get("id", ""))
            title = (it.get("title") or f"pid-{pid}").strip()
            if isinstance(orig, Exception):
                orig = ""
            results.append(
                {
                    "title": f"{title} (pid:{pid})",
                    "url": orig or it.get("url", ""),
                    "page": f"https://www.pixiv.net/artworks/{pid}",
                    "source": "pixiv",
                }
            )
        return results
    except asyncio.TimeoutError:
        logger.warning("pixiv 搜索超时（已跳过）")
        return []
    except Exception as e:
        logger.warning(f"pixiv 搜索失败: {type(e).__name__}: {e}")
        return []


# ── Iwara（Cloudflare 防护，走浏览器） ──


async def _iwara_search(query: str, count: int) -> List[Dict[str, str]]:
    """Iwara 视频搜索：浏览器打开搜索页提取视频链接（配合 video_download 下载）"""
    try:
        from urllib.parse import quote

        url = f"https://www.iwara.tv/search?type=video&query={quote(query)}"
        opened = await _open_page(url)
        if not opened:
            return []
        page, browser, p = opened
        await asyncio.sleep(5)
        items = await page.evaluate(
            """() => {
                const r = []; const seen = new Set();
                document.querySelectorAll('a[href*="/video/"]').forEach(a => {
                    const m = (a.getAttribute('href') || '').match(/\\/video\\/([\\w-]+)/);
                    if (m && !seen.has(m[1])) { seen.add(m[1]); r.push({id: m[1], t: (a.getAttribute('title') || a.textContent || '').trim()}); }
                });
                return r.slice(0, 30);
            }"""
        )
        await browser.close()
        await p.stop()
        results = []
        for it in items:
            if len(results) >= count:
                break
            vid = it.get("id", "")
            if not vid:
                continue
            results.append(
                {
                    "title": (it.get("t") or f"iwara-{vid}")[:60],
                    "url": f"https://www.iwara.tv/video/{vid}",
                    "source": "iwara",
                }
            )
        return results
    except Exception as e:
        logger.warning(f"iwara 搜索失败: {type(e).__name__}: {e}")
        return []


# ── 禁漫 JMComic（Cloudflare 防护，走浏览器） ──


async def _jmcomic_search(query: str, count: int) -> List[Dict[str, str]]:
    """禁漫天堂搜索：优先用 jmcomic 库（自动更新域名），失败回退浏览器"""
    # 首选：jmcomic 库（走移动端 API 域名，可绕过网站 Cloudflare 拦截）
    try:
        loop = asyncio.get_event_loop()

        def _lib_search() -> List[tuple]:
            import logging as _logging

            _logging.getLogger("jmcomic").setLevel(_logging.WARNING)
            import jmcomic

            option = jmcomic.JmOption.default()
            client = option.new_jm_client()
            page = client.search_site(query, page=1)
            return [(str(aid), str(t)[:60]) for aid, t in list(page.iter_id_title())[:count]]

        rows = await loop.run_in_executor(None, _lib_search)
        if rows:
            return [
                {"title": t, "url": f"https://18comic.vip/photo/{aid}/", "source": "禁漫"}
                for aid, t in rows
            ]
    except Exception as e:
        logger.warning(f"禁漫库搜索失败（回退浏览器）: {type(e).__name__}: {e}")

    # 兜底：浏览器打开搜索页提取本子链接
    try:
        from urllib.parse import quote

        url = f"https://18comic.vip/search/photos?search_query={quote(query)}"
        opened = await _open_page(url)
        if not opened:
            return []
        page, browser, p = opened
        await asyncio.sleep(5)
        items = await page.evaluate(
            """() => {
                const r = []; const seen = new Set();
                document.querySelectorAll('a[href*="/photo/"]').forEach(a => {
                    const m = (a.getAttribute('href') || '').match(/\\/photo\\/(\\d+)/);
                    if (m && !seen.has(m[1])) { seen.add(m[1]); r.push({id: m[1], t: (a.getAttribute('title') || a.textContent || '').trim()}); }
                });
                return r.slice(0, 30);
            }"""
        )
        await browser.close()
        await p.stop()
        results = []
        for it in items:
            if len(results) >= count:
                break
            aid = it.get("id", "")
            if not aid:
                continue
            results.append(
                {
                    "title": (it.get("t") or f"album-{aid}")[:60],
                    "url": f"https://18comic.vip/photo/{aid}/",
                    "source": "禁漫",
                }
            )
        return results
    except Exception as e:
        logger.warning(f"禁漫搜索失败: {type(e).__name__}: {e}")
        return []


# ── Pornhub（需代理，配合 video_download 下载） ──


async def _pornhub_search(query: str, count: int) -> List[Dict[str, str]]:
    """Pornhub 视频搜索：webmasters JSON API → HTML 解析 → 浏览器，三级回退"""
    try:
        from urllib.parse import quote

        q = quote(query)

        # 1) hubtraffic webmasters JSON API（无年龄门槛，最稳）
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://cn.pornhub.com/webmasters/search",
                    params={"search": query, "thumbsize": "large", "page": 1},
                    headers=_HEADERS,
                    proxy=_get_proxy(),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
            vids = (data.get("videos") or [])[:count]
            if vids:
                return [
                    {
                        "title": (v.get("title") or v.get("video_id", "")).strip()[:60],
                        "url": v.get("url") or f"https://cn.pornhub.com/view_video.php?viewkey={v.get('video_id', '')}",
                        "source": "pornhub",
                    }
                    for v in vids
                    if (v.get("url") or v.get("video_id"))
                ]
        except Exception:
            pass  # 回退 HTML

        # 2) 搜索页 HTML 解析（服务端渲染的视频卡片）
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://cn.pornhub.com/video/search",
                    params={"search": query},
                    headers=_HEADERS,
                    proxy=_get_proxy(),
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        html = ""
                    else:
                        html = await resp.text()
            if html:
                results: List[Dict[str, str]] = []
                seen = set()
                # 卡片: <a href="/view_video.php?viewkey=phxxx" title="...">
                for m in re.finditer(r'<a[^>]+href="(/view_video\.php\?viewkey=([\w]+))"[^>]*>', html):
                    path, key = m.group(1), m.group(2)
                    if key in seen:
                        continue
                    seen.add(key)
                    tmatch = re.search(r'<a[^>]+href="' + re.escape(path) + r'"[^>]*title="([^"]+)"', html)
                    title = (tmatch.group(1) if tmatch else f"video-{key}").strip()[:60]
                    results.append(
                        {"title": title, "url": f"https://cn.pornhub.com{path}", "source": "pornhub"}
                    )
                    if len(results) >= count:
                        break
                if results:
                    return results
        except Exception:
            pass  # 回退浏览器

        # 3) 浏览器兜底
        opened = await _open_page(f"https://cn.pornhub.com/video/search?search={q}")
        if not opened:
            return []
        page, browser, p = opened
        await asyncio.sleep(5)
        items = await page.evaluate(
            """() => {
                const r = []; const seen = new Set();
                document.querySelectorAll('a[href*="/view_video.php?"]').forEach(a => {
                    const m = (a.getAttribute('href') || '').match(/viewkey=([\\w]+)/);
                    if (m && !seen.has(m[1])) { seen.add(m[1]); r.push({k: m[1], t: (a.getAttribute('title') || a.textContent || '').trim()}); }
                });
                return r.slice(0, 30);
            }"""
        )
        await browser.close()
        await p.stop()
        results = []
        for it in items:
            if len(results) >= count:
                break
            key = it.get("k", "")
            if not key:
                continue
            results.append(
                {
                    "title": (it.get("t") or f"video-{key}")[:60],
                    "url": f"https://cn.pornhub.com/view_video.php?viewkey={key}",
                    "source": "pornhub",
                }
            )
        return results
    except Exception as e:
        logger.warning(f"pornhub 搜索失败: {type(e).__name__}: {e}")
        return []


# ── nhentai 本子库 ──


async def _nhentai_search(query: str, count: int) -> List[Dict[str, str]]:
    """搜索 nhentai 本子库（官方 JSON API，无需登录）。

    返回本子信息：标题、作品页链接、封面直链、页数。
    整本逐页直链格式: https://i.nhentai.net/galleries/{media_id}/{page}.{ext}
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://nhentai.net/api/galleries/search",
                params={"query": query.strip(), "page": 1, "sort": "popular"},
                headers=_HEADERS,
                proxy=_get_proxy(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        results = []
        for g in data.get("result", []):
            if len(results) >= count:
                break
            gid = g.get("id")
            media_id = g.get("media_id")
            if not gid:
                continue
            title = (
                (g.get("title") or {}).get("pretty")
                or (g.get("title") or {}).get("english")
                or (g.get("title") or {}).get("japanese")
                or f"gallery-{gid}"
            )
            cover = ""
            images = g.get("images") or {}
            cover_info = images.get("cover") or {}
            if media_id and cover_info.get("t"):
                cover = f"https://t.nhentai.net/galleries/{media_id}/cover.{cover_info['t']}"
            num_pages = len(images.get("pages") or []) or g.get("num_pages", 0)
            results.append(
                {
                    "title": f"{title} ({num_pages}P)",
                    "url": f"https://nhentai.net/g/{gid}/",
                    "cover": cover,
                    "source": "nhentai",
                }
            )
        return results
    except asyncio.TimeoutError:
        logger.warning("nhentai 搜索超时（已跳过）")
        return []
    except Exception as e:
        logger.warning(f"nhentai 搜索失败: {type(e).__name__}: {e}")
        return []


# ── Booru 图源（国内可直连网页版，支持 R18；JSON API 需认证故走 HTML 解析） ──

_BOORU_SITES = {
    "rule34": "https://rule34.xxx/index.php?page=post&s=list&tags={tags}",
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=list&tags={tags}",
}


def _thumb_to_full(url: str) -> str:
    """缩略图 URL → 原图 URL（booru 通用规则：thumbnails→images、去 thumbnail_ 前缀与查询串）"""
    url = url.split("?", 1)[0]
    if "/thumbnails/" in url:
        url = url.replace("/thumbnails/", "/images/").replace("/thumbnail_", "/")
    elif "/samples/" in url:
        url = url.replace("/samples/", "/images/")
    return url


async def _booru_search(query: str, count: int, site: str) -> List[Dict[str, str]]:
    """抓取 booru 列表页 HTML，提取缩略图并推导原图 URL（国内可直连，支持 R18）"""
    list_tpl = _BOORU_SITES.get(site)
    if not list_tpl:
        return []
    tags = re.sub(r"[\s，、]+", "+", query.strip())
    if not tags:
        return []
    url = list_tpl.format(tags=tags)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_HEADERS, proxy=_get_proxy(), timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        thumbs = re.findall(r'https?://[^"\'\s]+/thumbnails/[^"\'\s]+', html, re.I)
        results = []
        seen = set()
        for t in thumbs:
            if len(results) >= count:
                break
            full = _thumb_to_full(t)
            if full not in seen:
                seen.add(full)
                results.append({"title": f"{site} 原图", "url": full, "source": site})
        return results
    except Exception as e:
        logger.warning(f"{site} 搜索失败: {type(e).__name__}: {e}")
        return []


# ── B站 API ──


async def _bilibili_images(query: str, count: int) -> List[Dict[str, str]]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "video", "keyword": query, "order": "totalrank", "page": 1},
                headers={**_HEADERS, "Referer": "https://www.bilibili.com/"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        if data.get("code") != 0:
            return []
        results = []
        seen = set()
        for item in data["data"]["result"]:
            if len(results) >= count:
                break
            pic = item.get("pic", "")
            if pic:
                if pic.startswith("//"):
                    pic = f"https:{pic}"
                if pic not in seen:
                    seen.add(pic)
                    title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
                    results.append({"title": title, "url": pic, "source": "B站视频封面"})
        return results
    except Exception:
        return []


async def _bilibili_videos(query: str, count: int) -> List[Dict[str, str]]:
    """B站视频搜索：返回视频页链接（配合 video_download 工具下载）"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "video", "keyword": query, "order": "totalrank", "page": 1},
                headers={**_HEADERS, "Referer": "https://www.bilibili.com/"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        if data.get("code") != 0:
            return []
        results = []
        seen = set()
        for item in (data.get("data") or {}).get("result", []):
            if len(results) >= count:
                break
            bvid = item.get("bvid", "")
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            title = (item.get("title") or "").replace('<em class="keyword">', "").replace("</em>", "")
            play = item.get("play", 0)
            duration = item.get("duration", "")
            extra = ""
            if play:
                extra = f" | 播放:{play}"
            if duration:
                extra += f" | {duration}"
            results.append(
                {
                    "title": f"{title}{extra}",
                    "url": f"https://www.bilibili.com/video/{bvid}",
                    "source": "B站视频",
                }
            )
        return results
    except Exception:
        return []


async def _yingyongbao_apk(package_name: str) -> List[Dict[str, str]]:
    if not package_name:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://sj.qq.com/appdetail/{package_name}",
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                html = await resp.text() if resp.status == 200 else ""
        results = []
        seen = set()
        patterns = [
            r'https?://[^"\'\s]+\.apk[^"\'\s]*',
            r'https?://imtt\.dd\.qq\.com[^"\'\s]+',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.I):
                url = match.group(0).replace("&amp;", "&").replace("\\/", "/")
                if url not in seen:
                    seen.add(url)
                    results.append({"title": "应用宝 APK", "url": url, "source": "应用宝"})
                    if len(results) >= 3:
                        break
            if len(results) >= 3:
                break
        return results
    except Exception:
        return []


# ── 特定网站搜索 ──

_SITE_SEARCH = {
    "pixiv": "https://www.pixiv.net/tags/{query}/artworks",
    "danbooru": "https://danbooru.donmai.us/posts?tags={query}",
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=list&tags={query}",
    "yande.re": "https://yande.re/post?tags={query}",
    "konachan": "https://konachan.com/post?tags={query}",
    "safebooru": "https://safebooru.org/index.php?page=post&s=list&tags={query}",
    "nhentai": "https://nhentai.net/search/?q={query}",
    "iwara": "https://www.iwara.tv/search?type=video&query={query}",
    "jmcomic": "https://18comic.vip/search/photos?search_query={query}",
    "pornhub": "https://cn.pornhub.com/video/search?search={query}",
    "bilibili": "https://search.bilibili.com/all?keyword={query}",
    "zhihu": "https://www.zhihu.com/search?type=content&q={query}",
    "weibo": "https://s.weibo.com/weibo?q={query}",
    "github": "https://github.com/search?q={query}",
    "steam": "https://store.steampowered.com/search/?term={query}",
}

_SITE_KNOWN = {
    "p站": "pixiv",
    "pixiv": "pixiv",
    "b站": "bilibili",
    "bilibili": "bilibili",
    "微博": "weibo",
    "weibo": "weibo",
    "知乎": "zhihu",
    "zhihu": "zhihu",
    "github": "github",
    "steam": "steam",
    "蒸汽": "steam",
    "rule34": "rule34",
    "r34": "rule34",
    "gelbooru": "gelbooru",
    "danbooru": "danbooru",
    "yande.re": "yande.re",
    "yande": "yande.re",
    "konachan": "konachan",
    "k站": "konachan",
    "safebooru": "safebooru",
    "nhentai": "nhentai",
    "nh": "nhentai",
    "本子": "nhentai",
    "本子库": "nhentai",
    "iwara": "iwara",
    "jmcomic": "jmcomic",
    "禁漫": "jmcomic",
    "禁漫天堂": "jmcomic",
    "18comic": "jmcomic",
    "pornhub": "pornhub",
    "ph": "pornhub",
    "porn": "pornhub",
}


def _resolve_site(raw: str) -> Optional[str]:
    if not raw:
        return None
    return _SITE_KNOWN.get(raw.strip().lower(), raw.strip().lower())


async def _site_browse(site: str, query: str, count: int) -> List[Dict[str, str]]:
    """用浏览器打开特定网站搜索页，提取资源链接"""
    url_template = _SITE_SEARCH.get(site)
    if not url_template:
        return []
    url = url_template.format(query=query)
    try:
        opened = await _open_page(url)
        if not opened:
            return []
        page, browser, p = opened
        await asyncio.sleep(4)

        # 提取图片和链接
        items = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('img[src]').forEach(i => {
                let s = i.src || ''; if (s.startsWith('http') && s.length > 50) r.push(s);
            });
            document.querySelectorAll('a[href]').forEach(a => {
                let h = a.href; if (h && h.length > 30) r.push(h);
            });
            return [...new Set(r)].slice(0, 100);
        }""")

        results = []
        seen = set()
        for item in items:
            if item not in seen:
                seen.add(item)
                results.append({"title": f"{site} 搜索结果", "url": item, "source": f"浏览器-{site}"})
                if len(results) >= count:
                    break

        await browser.close()
        await p.stop()
        return results
    except Exception as e:
        logger.warning(f"站点 {site} 搜索失败: {e}")
        return []


# ── 浏览器兜底: Chrome 打开 Bing 图片搜索直接提图 ──


async def _browser_bing_images(query: str, count: int) -> List[Dict[str, str]]:
    urls_to_try = [
        ("Baidu", f"https://image.baidu.com/search/index?tn=baiduimage&word={query}"),
        ("Bing", f"https://www.bing.com/images/search?q={query}&first=1"),
    ]
    for name, search_url in urls_to_try:
        try:
            opened = await _open_page(search_url)
            if not opened:
                continue
            page, browser, p = opened
            await asyncio.sleep(3)

            imgs = await page.evaluate("""() => {
                const r = []; const seen = new Set();
                document.querySelectorAll('img[src]').forEach(i => {
                    let s = i.src || ''; if (s.startsWith('http') && s.length > 50 && !s.includes('data:image')) { if (!seen.has(s)) { seen.add(s); r.push({src: s, alt: i.alt || ''}); } }
                });
                document.querySelectorAll('a').forEach(a => {
                    let h = a.href; if (h) { let m = h.match(/objURL=([^&]+)/); if (m) { let u = decodeURIComponent(m[1]); if (!seen.has(u)) { seen.add(u); r.push({src: u, alt: ''}); } } }
                });
                return r.slice(0, 50);
            }""")

            results = []
            seen = set()
            for img in imgs:
                u = img.get("src", "")
                if u and u not in seen and not u.endswith(".svg"):
                    seen.add(u)
                    results.append({"title": img.get("alt", ""), "url": u, "source": f"浏览器-{name}"})
                    if len(results) >= count:
                        break

            await browser.close()
            await p.stop()

            if results:
                return results
        except Exception as e:
            logger.warning(f"[{name}] 浏览器兜底搜索失败: {e}")

    return []


# ── 页面爬取 ──


async def _crawl_page(url: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=_HEADERS,
                proxy=_get_proxy(),
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                return await resp.text() if resp.status == 200 else ""
    except Exception:
        return ""


def _extract_urls(html: str, extractors: List[str]) -> List[str]:
    results = []
    seen = set()
    for pattern in extractors:
        for match in re.finditer(pattern, html, re.I):
            url = match.group(1) if match.lastindex else match.group(0)
            url = url.replace("&amp;", "&").replace("\\/", "/")
            # 清理 JS 语句残留（如从 window.open('...'); 中提取的 URL 带 ); 尾巴）
            url = url.rstrip("`);'\" ,")
            if url.startswith("//"):
                url = f"https:{url}"
            if any(d in url.lower() for d in _EXCLUDE_DOMAINS):
                continue
            if len(url) < 15:
                continue
            if url not in seen:
                seen.add(url)
                results.append(url)
    return results


def _extract_subpage_links(html: str, base_url: str = "") -> List[str]:
    """提取所有可能指向下载页面的链接（用于深层爬取）"""
    results = []
    seen = set()
    patterns = [
        r'href="([^"]*(?:down|download|dl|apk|exe|setup|install)[^"]*)"',
        r'href="([^"]*)"[^>]*>(?:下载|下載|Download|立即下载|普通下载|高速下载|点击下载|安全下载|本地下载)',
        r"(?:window\.location|location\.href|window\.open)\s*[=(]\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.I):
            url = match.group(1).replace("&amp;", "&").replace("\\/", "/")
            if url.startswith("//"):
                url = f"https:{url}"
            elif url and not url.startswith("http") and base_url:
                url = urljoin(base_url, url)
            if any(d in url.lower() for d in _EXCLUDE_DOMAINS):
                continue
            if url.startswith("#") or url.startswith("javascript:"):
                continue
            if url not in seen:
                seen.add(url)
                results.append(url)
    return results[:5]


def _get_extractors(resource_type: str) -> List[str]:
    if resource_type == "any" or resource_type not in _TYPE_EXTRACTORS:
        all_patterns = []
        for v in _TYPE_EXTRACTORS.values():
            all_patterns.extend(v)
        return all_patterns
    return _TYPE_EXTRACTORS[resource_type]


# ── 官网下载页推断 ──

_DOWNLOAD_PATHS = ["/download", "/downloads", "/Download", "/get", "/releases", "/latest"]


def _guess_download_pages(search_results: List[Dict[str, str]], core_query: str = "") -> List[str]:
    """从搜索结果域名推断官网下载页候选 URL（品牌域名优先）。

    很多软件的安装包只在官网下载页提供（如 obsidian.md/download），
    而搜索引擎返回的往往是帮助/介绍页。这里按主域名拼接标准下载路径，
    并优先选择域名中包含搜索品牌词的站点（更可能是官网）。
    """
    # 提取品牌词候选（英文最长 token；中文查询无法匹配域名时退回全量）
    brand = ""
    if core_query:
        tokens = re.findall(r"[a-zA-Z0-9]+", core_query.lower())
        if tokens:
            brand = max(tokens, key=len)

    candidates: List[str] = []
    seen = set()

    def _emit(base: str) -> None:
        if base in seen:
            return
        seen.add(base)
        for path in _DOWNLOAD_PATHS:
            candidates.append(base + path)

    # 第一轮：品牌域名优先
    if brand:
        for r in search_results:
            u = r.get("url", "")
            if not u.startswith("http"):
                continue
            try:
                from urllib.parse import urlsplit

                parts = urlsplit(u)
            except Exception:
                continue
            netloc = parts.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if "github" in netloc:
                continue  # GitHub 的 releases 直链在搜索结果页即可提取
            if any(d in netloc for d in _EXCLUDE_DOMAINS):
                continue
            if brand in netloc:
                _emit(f"{parts.scheme}://{parts.netloc}")

    # 第二轮：其余域名补齐
    for r in search_results:
        u = r.get("url", "")
        if not u.startswith("http"):
            continue
        try:
            from urllib.parse import urlsplit

            parts = urlsplit(u)
        except Exception:
            continue
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        if "github" in netloc or any(d in netloc for d in _EXCLUDE_DOMAINS):
            continue
        _emit(f"{parts.scheme}://{parts.netloc}")
        if len(candidates) >= 12:
            break

    return candidates


class ResourceFindTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "resource_find",
            "description": (
                "通用资源搜索。一个工具搜索所有文件类型："
                "图片(image)、视频(video)、安卓安装包(apk)、电脑程序(program)、文档(document)、压缩包(archive)、音频(audio)、全部(any)。"
                "当用户要求「找图」「搜视频」「下载安装包」「找exe」「搜文档」等任何资源搜索时必须使用此工具。"
                "内置智能查询扩展（自动补全「下载/最新版/官方」等关键词、中英双语）与多引擎并行搜索，"
                "无需担心关键词写得太简单；query 直接写用户想要的东西即可。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如「镜流 壁纸」「红果短剧 APK」「VSCode 下载」「Python 安装包」",
                    },
                    "resource_type": {
                        "type": "string",
                        "enum": ["image", "video", "apk", "program", "document", "archive", "audio", "any"],
                        "description": "资源类型",
                        "default": "any",
                    },
                    "package_name": {"type": "string", "description": "安卓包名 (apk 搜索时可选)，如 com.phoenix.read"},
                    "site": {
                        "type": "string",
                        "description": (
                            "限定搜索特定网站。支持: pixiv(P站), danbooru, gelbooru, rule34, yande.re, konachan, safebooru, "
                            "nhentai(本子库), iwara(3D视频), jmcomic(禁漫天堂), pornhub(需代理), bilibili, zhihu, github。"
                            "找R18/涩图建议 rule34/gelbooru/yande.re/konachan/pixiv；找本子用 nhentai 或 jmcomic；找3D视频用 iwara。不指定则全网络搜索"
                        ),
                    },
                    "count": {"type": "integer", "description": "最大返回数量", "default": 10},
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        query = args.get("query", "").strip()
        resource_type = args.get("resource_type", "any")
        count = min(args.get("count", 10), 30)
        site = _resolve_site(args.get("site", ""))

        if not query:
            return _msg("query_required")

        try:
            # Phase 1: 智能多引擎搜索（查询扩展 + Tavily 优先 + 免费引擎兜底）
            search_results = await _smart_web_search(query, resource_type)

            # Phase 1.5: 图片额外查 booru/pixiv 图源
            booru_results = []
            bili_results = []
            pixiv_results = []
            booru_extra = []
            if resource_type in ("image", "any"):
                booru_results, bili_results, pixiv_results, r34, gel, kon, safe = await asyncio.gather(
                    _yandere_search(query, count),
                    _bilibili_images(query, count),
                    _pixiv_search(query, count),
                    _booru_search(query, count, "rule34"),
                    _booru_search(query, count, "gelbooru"),
                    _moe_booru_search(query, count, "konachan"),
                    _safebooru_search(query, count),
                    return_exceptions=True,
                )
                if isinstance(booru_results, Exception):
                    booru_results = []
                if isinstance(bili_results, Exception):
                    bili_results = []
                if isinstance(pixiv_results, Exception):
                    pixiv_results = []
                for extra in (r34, gel, kon, safe):
                    if isinstance(extra, Exception):
                        continue
                    booru_extra.extend(extra)

            # Phase 1.55: 视频类型额外查 B站 + Iwara + Pornhub（配合 video_download 下载）
            bili_video_results = []
            iwara_results = []
            ph_results = []
            if resource_type in ("video", "any"):
                bili_video_results, iwara_results, ph_results = await asyncio.gather(
                    _bilibili_videos(query, count),
                    _iwara_search(query, count),
                    _pornhub_search(query, count),
                    return_exceptions=True,
                )
                if isinstance(bili_video_results, Exception):
                    bili_video_results = []
                if isinstance(iwara_results, Exception):
                    iwara_results = []
                if isinstance(ph_results, Exception):
                    ph_results = []

            # Phase 1.6: APK 额外查应用宝
            yyb_results = []
            package_name = args.get("package_name", "")
            if resource_type in ("apk", "any") and package_name:
                yyb_results = await _yingyongbao_apk(package_name)

            # Phase 1.7: 指定网站搜索
            site_results = []
            if site:
                if site in _BOORU_SITES:
                    site_results = await _booru_search(query, count, site)
                elif site == "nhentai":
                    site_results = await _nhentai_search(query, count)
                elif site in ("yande.re", "konachan"):
                    site_results = await _moe_booru_search(query, count, site)
                elif site == "safebooru":
                    site_results = await _safebooru_search(query, count)
                elif site == "pixiv":
                    site_results = await _pixiv_search(query, count)
                elif site == "iwara":
                    site_results = await _iwara_search(query, count)
                elif site == "jmcomic":
                    site_results = await _jmcomic_search(query, count)
                elif site == "pornhub":
                    site_results = await _pornhub_search(query, count)
                else:
                    site_results = await _site_browse(site, query, count)
                if not site_results:
                    logger.warning(f"指定站点 {site} 未取到资源（可能被墙或需要登录），已跳过")

            if (
                not search_results
                and not site_results
                and not booru_extra
                and not bili_video_results
                and not iwara_results
                and not ph_results
                and not pixiv_results
            ):
                hint = ""
                if site:
                    hint = _msg("site_hint", site=site)
                return _msg("no_result", query=query) + hint

            # Phase 2: 爬取页面 + 提取
            extractors = _get_extractors(resource_type)
            crawl_urls = [r["url"] for r in search_results[:6]]
            page_tasks = [_crawl_page(u) for u in crawl_urls]
            pages_html = await asyncio.gather(*page_tasks, return_exceptions=True)

            # 从首页结果中也提取（Tavily-Image 已含直链；仅图片类搜索接受图片直链）
            direct_urls: List[Dict[str, str]] = []
            seen = set()
            for r in search_results:
                if (
                    r["source"] == "Tavily-Image"
                    and resource_type in ("image", "any")
                    and r["url"] not in seen
                ):
                    seen.add(r["url"])
                    direct_urls.append({"title": r.get("title", ""), "url": r["url"], "source": "直链"})

            # 合并 booru + pixiv + B站 + iwara + 应用宝 + nhentai 结果
            for r in booru_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in booru_extra:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in bili_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in pixiv_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in bili_video_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in iwara_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in ph_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in yyb_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)
            for r in site_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    direct_urls.append(r)

            # 从爬取页面提取
            crawled_urls: List[Dict[str, str]] = []
            for html in pages_html:
                if isinstance(html, Exception) or not html:
                    continue
                extracted = _extract_urls(html, extractors)
                for u in extracted:
                    if u not in seen:
                        seen.add(u)
                        crawled_urls.append({"title": "", "url": u, "source": "页面提取"})
                        if len(crawled_urls) >= count:
                            break
                if len(crawled_urls) >= count:
                    break

            # Phase 2.5: 对 apk/program 类型做深一层爬取
            # 下载页面的直链往往在子页面中（如 down.php?id=123）
            if resource_type in ("apk", "program", "any") and len(crawled_urls) < count:
                sub_urls = []
                # 官网下载页推断优先（如 obsidian.md/download 含 AppImage/deb 直链）
                if resource_type in ("program", "any"):
                    try:
                        from webnet.ToolNet.tools.network.query_optimizer import extract_core_query

                        core_q = extract_core_query(query, resource_type)
                    except Exception:
                        core_q = query
                    sub_urls.extend(_guess_download_pages(search_results, core_q))
                # 页面内的下载子链接（如 down.php?id=123）
                for i, html in enumerate(pages_html):
                    if isinstance(html, Exception) or not html:
                        continue
                    base = crawl_urls[i] if i < len(crawl_urls) else ""
                    sub_urls.extend(_extract_subpage_links(html, base))
                # 去重
                sub_urls = list(dict.fromkeys(sub_urls))[:8]
                if sub_urls:
                    sub_tasks = [_crawl_page(u) for u in sub_urls]
                    sub_htmls = await asyncio.gather(*sub_tasks, return_exceptions=True)
                    for html in sub_htmls:
                        if isinstance(html, Exception) or not html:
                            continue
                        extracted = _extract_urls(html, extractors)
                        for u in extracted:
                            if u not in seen:
                                seen.add(u)
                                crawled_urls.append({"title": "", "url": u, "source": "深层提取"})
                                if len(crawled_urls) >= count:
                                    break
                        if len(crawled_urls) >= count:
                            break

            # Phase 2.6: 兜底 — Bing 文本搜索 → 爬取页面提取
            all_results = direct_urls + crawled_urls
            if not all_results and resource_type in ("image", "any"):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://www.bing.com/search",
                            params={"q": f"{query} images", "count": 5, "setmkt": "zh-CN"},
                            headers=_HEADERS,
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp:
                            bing_html = await resp.text() if resp.status == 200 else ""
                    bing_urls = list(dict.fromkeys(re.findall(r'<a[^>]*href="(https?://[^"]+)"', bing_html)))
                    bing_urls = [
                        u
                        for u in bing_urls
                        if not any(d in u for d in ["bing.com", "microsoft.com", "google.com", "facebook.com"])
                    ][:5]
                    if bing_urls:
                        bing_tasks = [_crawl_page(u) for u in bing_urls[:4]]
                        bing_htmls = await asyncio.gather(*bing_tasks, return_exceptions=True)
                        for bhtml in bing_htmls:
                            if isinstance(bhtml, Exception) or not bhtml:
                                continue
                            extracted = _extract_urls(bhtml, _get_extractors("image"))
                            for u in extracted:
                                if u not in seen:
                                    seen.add(u)
                                    direct_urls.append({"title": "", "url": u, "source": "兜底爬取"})
                                    if len(direct_urls) >= count:
                                        break
                            if len(direct_urls) >= count:
                                break
                except Exception as e:
                    logger.warning(f"兜底搜索失败: {e}")

            # Phase 2.7: 最终兜底 — 浏览器打开 Bing 图片搜
            all_results = direct_urls + crawled_urls
            if not all_results and resource_type in ("image", "any"):
                browser_imgs = await _browser_bing_images(query, count)
                for r in browser_imgs:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        direct_urls.append(r)

            # Phase 3: 排序 + 分组返回（直链优先，官方域名加分）
            all_results = _rank_resource_results(direct_urls + crawled_urls, resource_type)

            try:
                from webnet.ToolNet.tools.network.query_optimizer import build_queries

                nq = len(build_queries(query, resource_type) or [query])
            except Exception:
                nq = 1

            def _fmt(r: Dict[str, str], i: int) -> str:
                title = (r.get("title") or "").strip()[:50] or "(无标题)"
                line = f"{i}. [{r.get('source', '资源')}] {title}\n   {r['url']}"
                cover = (r.get("cover") or "").strip()
                if cover:
                    line += f"\n   封面: {cover}"
                page = (r.get("page") or "").strip()
                if page:
                    line += f"\n   页面: {page}"
                return line

            if not all_results:
                lines = [_msg("no_result_with_pages", query=query, resource_type=resource_type)]
                for i, r in enumerate(search_results[:5], 1):
                    title = (r.get("title") or "").strip()[:60] or r["url"]
                    lines.append(f"{i}. {title}\n   {r['url']}")
            else:
                ns = len({str(r.get("source", "?")) for r in all_results})
                lines = [_msg("found_header", query=query, count=len(all_results), nq=nq, ns=ns), ""]
                idx = 1

                direct_part = [r for r in all_results if _is_direct_source(str(r.get("source", "")))]
                direct_url_set = {r["url"] for r in direct_part}
                crawled_part = [r for r in all_results if r["url"] not in direct_url_set]

                if direct_part:
                    lines.append(_msg("section_direct"))
                    for r in direct_part[:count]:
                        lines.append(_fmt(r, idx))
                        lines.append("")
                        idx += 1
                    top_url = direct_part[0]["url"]
                    top_src = str(direct_part[0].get("source", ""))
                    if top_src == "nhentai" or top_src == "禁漫":
                        reason = "本子作品页，打开即可在线看，逐页直链可用 download_file 下载"
                    elif top_src in ("B站视频", "iwara", "pornhub"):
                        reason = "视频页，用 video_download 工具下载"
                    elif top_src == "pixiv":
                        reason = "Pixiv 原图直链，可直接下载"
                    else:
                        reason = "直链可直接下载"
                    lines.append(_msg("recommend_hint", index=1, reason=reason))
                else:
                    top_url = ""

                if crawled_part and idx <= count:
                    lines.append(_msg("section_crawled"))
                    for r in crawled_part[: count - idx + 1]:
                        lines.append(_fmt(r, idx))
                        lines.append("")
                        idx += 1
                    if not direct_part:
                        lines.append(_msg("recommend_hint", index=1, reason="页面提取资源，可能需要进入页面后再下载"))

                # 补充输出 top 推荐直链（供后续 download_file 使用）
                if top_url:
                    lines.append(f"📌 首选链接: {top_url}")

            has_video_page = any(str(r.get("source", "")) in ("B站视频", "iwara", "pornhub") for r in all_results)
            lines.append(_msg("download_hint"))
            if has_video_page:
                lines.append("🎬 视频页链接: 用 video_download(url=<视频链接>) 下载")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"资源搜索失败: {e}", exc_info=True)
            return _msg("error", error=str(e))
