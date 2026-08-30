"""
浏览器自动化工具

弥娅直接用浏览器访问网页，绕过 JS 反爬、Cloudflare、NSFW 过滤：
- 导航到任意 URL
- 截图
- 提取图片/链接
- 点击/滚动
"""

import asyncio
import logging
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_BROWSER_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "browser"
_SESSION_COUNT = 0
_playwright = None
_browser = None
_context = None
_page = None

# Chromium 网络错误码 → 中文提示（用于告诉 AI 明确"打不开"而非继续重试）
_NETWORK_ERROR_HINTS = {
    "ERR_NETWORK_CHANGED": "网络变化",
    "ERR_CONNECTION_CLOSED": "连接被关闭",
    "ERR_CONNECTION_REFUSED": "连接被拒绝",
    "ERR_CONNECTION_RESET": "连接被重置",
    "ERR_NAME_NOT_RESOLVED": "域名无法解析",
    "ERR_TIMED_OUT": "连接超时",
    "ERR_SSL_PROTOCOL_ERROR": "SSL 协议错误",
    "ERR_CERT_AUTHORITY_INVALID": "证书无效",
    "ERR_ABORTED": "请求被中止",
    "ERR_TUNNEL_CONNECTION_FAILED": "代理连接失败",
    "ERR_INTERNET_DISCONNECTED": "网络已断开",
    "ERR_ADDRESS_UNREACHABLE": "地址不可达",
}


def _network_error_hint(err: Exception) -> Optional[str]:
    """从异常信息中识别网络错误，返回提示；非网络错误返回 None"""
    msg = str(err)
    for code, hint in _NETWORK_ERROR_HINTS.items():
        if code in msg:
            return hint
    return None


def _find_chrome() -> Optional[str]:
    """跨平台查找系统已安装的 Chrome / Chromium / Edge 可执行文件"""
    system = platform.system()
    candidates: List[str] = []

    if system == "Windows":
        candidates += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    elif system == "Darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidates += [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for name in ("google-chrome", "chrome", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


async def _get_browser():
    global _SESSION_COUNT, _playwright, _browser, _context, _page
    try:
        from playwright.async_api import async_playwright

        if _page is None:
            _playwright = await async_playwright().start()

            chrome_exe = _find_chrome()
            if chrome_exe:
                logger.info(f"[浏览器] 使用系统 Chrome: {chrome_exe}")
                _browser = await _playwright.chromium.launch(
                    headless=True,
                    executable_path=chrome_exe,
                    args=[
                        "--no-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )
            else:
                logger.info("[浏览器] 未找到系统 Chrome，使用 Playwright 内置 Chromium")
                _browser = await _playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )

            _context = await _browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
            )
            _page = await _context.new_page()
            _SESSION_COUNT += 1

        return _playwright, _browser, _context, _page
    except Exception as e:
        logger.error(f"启动浏览器失败: {e}")
        raise


class BrowseWebTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "browse_web",
            "description": (
                "用真正的浏览器访问网页。能看截图、提取图片链接、点击按钮、滚动页面。"
                "可以访问需要 JS 渲染的网站、被反爬保护的网站、NSFW 内容。"
                "当用户要求「去XX网站看看」「翻几页」「点那个按钮」「截图发我」时使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["goto", "screenshot", "extract_images", "extract_links", "click", "scroll", "close"],
                        "description": "动作: goto(导航), screenshot(截图), extract_images(提取图片), extract_links(提取链接), click(点击), scroll(滚动), close(关闭)",
                    },
                    "url": {"type": "string", "description": "URL，goto 时必填"},
                    "selector": {"type": "string", "description": "CSS 选择器，click/extract 时用于定位元素"},
                    "text": {"type": "string", "description": "按钮文本，click 时可用文本匹配替代 selector"},
                    "scroll_pixels": {
                        "type": "integer",
                        "description": "滚动像素数，正数向下，负数向上",
                        "default": 800,
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "等待秒数（让页面加载），默认 3",
                        "default": 3,
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "extract 时最大返回数量",
                        "default": 20,
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        action = args.get("action", "")
        url = args.get("url", "").strip()
        selector = args.get("selector", "").strip()
        text = args.get("text", "").strip()
        scroll_pixels = args.get("scroll_pixels", 800)
        wait_seconds = args.get("wait_seconds", 3)
        max_items = min(args.get("max_items", 20), 50)

        _BROWSER_DIR.mkdir(parents=True, exist_ok=True)

        try:
            p, browser, ctx, page = await _get_browser()
        except Exception as e:
            return f"❌ 无法启动浏览器: {e}"

        try:
            if action == "goto":
                if not url:
                    return "❌ 请提供 URL"
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    hint = _network_error_hint(nav_err)
                    if hint:
                        return (
                            f"❌ 无法访问该站点（{hint}）。\n"
                            f"🔗 URL: {url}\n"
                            f"💡 可能是网络不通或该站点被墙，请换用其他站点或改用 resource_find/download_file 等其他方式，不要再重试此 URL。"
                        )
                    raise
                await asyncio.sleep(wait_seconds)
                title = await page.title()
                url_current = page.url
                return f"✅ 已打开页面\n📄 标题: {title}\n🔗 URL: {url_current}"

            elif action == "screenshot":
                path = str(_BROWSER_DIR / f"screenshot_{_SESSION_COUNT}.png")
                await page.screenshot(path=path, full_page=False)
                return f"✅ 截图已保存\n📁 {path}\n💡 使用 send_platform_file 发送截图"

            elif action == "extract_images":
                await asyncio.sleep(wait_seconds)
                imgs = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('img[src]').forEach(img => {
                        let src = img.src || img.getAttribute('data-src') || '';
                        if (src && !src.startsWith('data:') && src.length > 20 && !src.includes('1x1')) {
                            results.push({src, alt: img.alt || ''});
                        }
                    });
                    return results.slice(0, 50);
                }""")
                if not imgs:
                    return "🔍 页面未找到图片"

                lines = [f"🔍 找到 {len(imgs)} 张图片：\n"]
                seen = set()
                for i, img in enumerate(imgs):
                    u = img["src"]
                    if u in seen:
                        continue
                    seen.add(u)
                    lines.append(f"{len(seen)}. {img['alt'][:40]}\n   {u}\n")
                    if len(seen) >= max_items:
                        break

                lines.append(f"\n💡 使用 download_file(url=<链接>) 下载图片")
                return "\n".join(lines)

            elif action == "extract_links":
                await asyncio.sleep(wait_seconds)
                links = await page.evaluate(
                    """(selector) => {
                    const results = [];
                    const links = selector ? document.querySelectorAll(selector) : document.querySelectorAll('a[href]');
                    links.forEach(a => {
                        const href = a.href || '';
                        const text = (a.textContent || '').trim().substring(0, 50);
                        if (href && !href.startsWith('javascript:')) {
                            results.push({href, text});
                        }
                    });
                    return results.slice(0, 50);
                }""",
                    selector or None,
                )

                if not links:
                    return "🔍 未找到链接"

                lines = [f"🔗 找到 {len(links)} 个链接：\n"]
                seen = set()
                for link in links:
                    if link["href"] in seen:
                        continue
                    seen.add(link["href"])
                    lines.append(f"{len(seen)}. {link['text']}\n   {link['href']}\n")
                    if len(seen) >= max_items:
                        break
                return "\n".join(lines)

            elif action == "click":
                if text:
                    await page.click(f"text={text}", timeout=10000)
                elif selector:
                    await page.click(selector, timeout=10000)
                else:
                    return "❌ 请提供 selector 或 text"
                await asyncio.sleep(wait_seconds)
                title = await page.title()
                return f"✅ 已点击，当前页面: {title}"

            elif action == "scroll":
                await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
                await asyncio.sleep(1)
                scroll_y = await page.evaluate("window.scrollY")
                return f"✅ 已滚动到 y={scroll_y}"

            elif action == "close":
                global _browser, _context, _page, _playwright
                if _page:
                    await _page.close()
                    _page = None
                if _context:
                    await _context.close()
                    _context = None
                if _browser:
                    await _browser.close()
                    _browser = None
                if _playwright:
                    await _playwright.stop()
                    _playwright = None
                return "✅ 浏览器已关闭"

            else:
                return f"❌ 未知动作: {action}"

        except Exception as e:
            logger.error(f"浏览器操作失败: {e}", exc_info=True)
            return f"❌ 操作失败: {str(e)}"

        finally:
            if action == "close":
                pass  # 不自动关闭，下次复用
