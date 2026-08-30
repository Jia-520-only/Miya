"""
弥娅渲染工具 — Playwright 驱动的 HTML/图片渲染

提供:
- 浏览器单例管理（惰性初始化，共享复用）
- HTML → 图片渲染（Playwright Chromium 截图）
- 渲染缓存（SHA256 键值，避免重复渲染）
- 安全离线模式（阻止所有网络请求）
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_playwright = None
_browser = None
_browser_lock = asyncio.Lock()
_render_semaphore = asyncio.Semaphore(2)

_DEFAULT_CACHE_DIR = Path("data/cache/render")
_DEFAULT_CACHE_MAX_ENTRIES = 50
_DEFAULT_CACHE_MAX_SIZE_MB = 50


def _get_browser_executable() -> Optional[str]:
    import os
    import shutil

    candidates = [
        "chromium",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "chromium-browser",
        "msedge",
    ]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    if os.name == "nt":
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for p in paths:
            if os.path.isfile(p):
                return p

    return None


async def _get_browser():
    global _playwright, _browser
    if _browser:
        return _browser
    async with _browser_lock:
        if _browser:
            return _browser
        from playwright.async_api import async_playwright

        _playwright = await async_playwright().start()
        launch_opts = {"headless": True}

        executable = _get_browser_executable()
        if executable:
            launch_opts["executable_path"] = executable

        _browser = await _playwright.chromium.launch(**launch_opts)
        logger.info("[渲染] Playwright 浏览器已启动: executable=%s", executable or "内置")
        return _browser


async def close_browser() -> None:
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("[渲染] 浏览器已关闭")


async def _abort_render_network_request(route):
    await route.abort()


async def render_html_to_image(
    html_content: str,
    output_path: str | Path,
    *,
    viewport_width: int = 800,
    full_page: bool = True,
    device_scale_factor: int = 2,
    timeout_ms: int = 30000,
    cache_enabled: bool = True,
) -> Optional[Path]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cache_key = _compute_cache_key(html_content, viewport_width)
    if cache_enabled:
        cached_path = _get_cached(cache_key)
        if cached_path and cached_path.exists():
            if output != cached_path:
                shutil.copy2(cached_path, output)
            logger.debug("[渲染] 缓存命中: %s", output)
            return output

    async with _render_semaphore:
        browser = await _get_browser()
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": 800},
            device_scale_factor=device_scale_factor,
            offline=True,
        )
        page = await context.new_page()
        await page.route("**/*", _abort_render_network_request)

        try:
            await page.set_content(html_content, timeout=timeout_ms)
            await page.wait_for_timeout(300)
            await page.screenshot(path=str(output), full_page=full_page)
            logger.info("[渲染] 截图已保存: %s (width=%s, full_page=%s)", output, viewport_width, full_page)
        finally:
            await context.close()

    if cache_enabled:
        _set_cache(cache_key, output)

    return output


def _compute_cache_key(html_content: str, viewport_width: int) -> str:
    data = f"{html_content}|{viewport_width}".encode()
    return hashlib.sha256(data).hexdigest()


def _get_cache_dir() -> Path:
    cache_dir = _DEFAULT_CACHE_DIR / "html"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cached(cache_key: str) -> Optional[Path]:
    cache_path = _get_cache_dir() / f"{cache_key}.png"
    return cache_path if cache_path.exists() else None


def _set_cache(cache_key: str, source_path: Path) -> None:
    cache_dir = _get_cache_dir()
    cache_path = cache_dir / f"{cache_key}.png"
    if source_path != cache_path:
        shutil.copy2(source_path, cache_path)

    _prune_cache(cache_dir)


def _prune_cache(cache_dir: Path) -> None:
    try:
        files = sorted(cache_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
        if len(files) > _DEFAULT_CACHE_MAX_ENTRIES:
            for old in files[_DEFAULT_CACHE_MAX_ENTRIES:]:
                old.unlink(missing_ok=True)

        total_size = sum(f.stat().st_size for f in cache_dir.glob("*.png"))
        max_bytes = _DEFAULT_CACHE_MAX_SIZE_MB * 1024 * 1024
        if total_size > max_bytes:
            for old in sorted(files, key=lambda f: f.stat().st_mtime):
                if total_size <= max_bytes:
                    break
                total_size -= old.stat().st_size
                old.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("[渲染] 缓存清理异常: %s", exc)


async def render_profile_to_image(
    entity_type: str,
    entity_id: str,
    profile_content: str,
    output_dir: str | Path = "data/cache/render",
) -> Optional[Path]:
    type_label = "用户" if entity_type == "user" else "群聊"
    escaped_body = _html_escape(profile_content)
    body_html = "".join(
        f'<div class="line">{_html_escape(line) or "&#8203;"}</div>' for line in escaped_body.split("\n")
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif;
    background: #f9f5f1;
    padding: 24px;
    display: flex;
    justify-content: center;
}}
.card {{
    width: 100%;
    max-width: 460px;
    background: white;
    border-radius: 12px;
    border: 1px solid #e6e0d8;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.card-header {{
    background: linear-gradient(135deg, #8b6f5c 0%, #a08b7a 100%);
    color: white;
    padding: 16px 20px;
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.card-header .icon {{ font-size: 18px; }}
.meta {{
    padding: 12px 20px;
    background: #faf8f5;
    border-bottom: 1px solid #eeeae2;
    font-size: 12px;
    color: #8b7355;
    display: flex;
    gap: 16px;
}}
.meta span {{ white-space: nowrap; }}
.meta strong {{ color: #5c4a3a; }}
.body {{
    padding: 16px 20px;
    font-size: 14px;
    line-height: 1.8;
    color: #3c3c3c;
    white-space: pre-wrap;
    word-break: break-all;
}}
.line {{ min-height: 1.2em; }}
.divider {{
    height: 1px;
    background: #e6e0d8;
    margin: 8px 20px;
}}
.tag {{
    display: inline-block;
    padding: 2px 8px;
    margin: 2px 4px 2px 0;
    background: #f0ebe3;
    border-radius: 4px;
    font-size: 11px;
    color: #8b6f5c;
}}
.footer {{
    padding: 10px 20px;
    font-size: 10px;
    color: #c4b5a5;
    text-align: right;
    background: #faf8f5;
    border-top: 1px solid #eeeae2;
}}
</style>
</head>
<body>
<div class="card">
<div class="card-header">
    <span class="icon">{"👤" if entity_type == "user" else "👥"}</span>
    <span>{type_label}侧写 — {entity_id}</span>
</div>
<div class="meta">
    <span>类型: <strong>{type_label}</strong></span>
    <span>ID: <strong>{entity_id}</strong></span>
</div>
<div class="body">
{body_html}
</div>
<div class="footer">弥娅 · 认知记忆系统 · {time.strftime("%Y-%m-%d %H:%M")}</div>
</div>
</body>
</html>"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    unique_id = uuid.uuid4().hex[:8]
    output_path = output_dir / f"profile_{entity_type}_{entity_id}_{unique_id}.png"

    return await render_html_to_image(html, output_path, viewport_width=480)


async def render_markdown_to_image(
    markdown_content: str,
    output_path: str | Path,
    *,
    viewport_width: int = 800,
    title: str = "",
) -> Optional[Path]:
    escaped_body = _html_escape(markdown_content)
    body_html = "\n".join(
        f'<div class="line">{_html_escape(line) or "&#8203;"}</div>' for line in escaped_body.split("\n")
    )

    title_html = ""
    if title:
        title_html = f'<div class="page-title">{_html_escape(title)}</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    background: #ffffff;
    padding: 28px;
    color: #24292e;
    font-size: 14px;
    line-height: 1.7;
}}
.page-title {{
    font-size: 22px;
    font-weight: 700;
    color: #1a1a2e;
    border-bottom: 2px solid #8b6f5c;
    padding-bottom: 10px;
    margin-bottom: 20px;
}}
.line {{
    min-height: 1.4em;
    white-space: pre-wrap;
    word-break: break-all;
}}
.divider {{
    height: 1px;
    background: #e1e4e8;
    margin: 12px 0;
}}
.footer {{
    margin-top: 20px;
    padding-top: 12px;
    border-top: 1px solid #e1e4e8;
    font-size: 10px;
    color: #8b949e;
    text-align: right;
}}
</style>
</head>
<body>
{title_html}
<div class="content">
{body_html}
</div>
<div class="footer">弥娅 · 渲染输出 · {time.strftime("%Y-%m-%d %H:%M")}</div>
</body>
</html>"""

    return await render_html_to_image(html, output_path, viewport_width=viewport_width)


async def render_html_direct(
    html_content: str,
    output_path: str | Path,
    *,
    viewport_width: int = 800,
) -> Optional[Path]:
    return await render_html_to_image(html_content, output_path, viewport_width=viewport_width)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def get_profile_image_path(entity_type: str, entity_id: str) -> Path:
    return _DEFAULT_CACHE_DIR / f"profile_latest_{entity_type}_{entity_id}.png"
