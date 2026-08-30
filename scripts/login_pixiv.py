# -*- coding: utf-8 -*-
"""
Pixiv 借登录提取 Cookie（绕开新版 Chrome 应用层加密）

弥娅弹出一个浏览器窗口并打开 pixiv 登录页，
亲爱的在窗口里登录成功后，弥娅自动读取会话 Cookie 写入 config/.env。

用法: python scripts/login_pixiv.py
"""

import asyncio
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"


def _find_chrome() -> str:
    for name in ("chrome", "chromium", "google-chrome"):
        path = shutil.which(name)
        if path:
            return path
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return ""


def _update_env(cookie: str) -> None:
    env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
    if not env_path.exists():
        print("[写入] config/.env 不存在")
        return
    content = env_path.read_text(encoding="utf-8")
    line = f"PIXIV_COOKIE={cookie}"
    if re.search(r"^PIXIV_COOKIE=.*$", content, re.M):
        content = re.sub(r"^PIXIV_COOKIE=.*$", line, content, flags=re.M)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += line + "\n"
    env_path.write_text(content, encoding="utf-8")
    print("[写入] PIXIV_COOKIE 已更新到 config/.env")


async def _verify_logged_in(sess: str) -> bool:
    """（保留备用）登录验证：登录用户才能访问 setting_user.php"""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as c:
            r = await c.get(
                "https://www.pixiv.net/setting_user.php",
                headers={
                    "Cookie": f"PHPSESSID={sess}",
                    "Referer": "https://www.pixiv.net/",
                    "User-Agent": _BROWSER_UA,
                },
            )
            return r.status_code == 200
    except Exception:
        return False


async def main() -> int:
    chrome = _find_chrome()
    if not chrome:
        print("[失败] 未找到 Chrome/Edge 浏览器")
        return 1

    from playwright.async_api import async_playwright

    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=chrome,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=_BROWSER_UA)
        page = await context.new_page()
        await page.goto("https://www.pixiv.net/login.php", timeout=45000, wait_until="domcontentloaded")

        print("=" * 60)
        print("弥娅已打开 pixiv 登录窗口 ✅")
        print("请在窗口里完成登录（账号密码 / 人机验证都可以慢慢来）")
        print("登录成功后弥娅会自动检测到，最多等待 5 分钟")
        print("=" * 60)

        for i in range(300):  # 最长等待 10 分钟
            await asyncio.sleep(2)
            try:
                cookies = await context.cookies("https://www.pixiv.net")
                sess = next((c["value"] for c in cookies if c.get("name") == "PHPSESSID" and c.get("value")), "")
                if not sess:
                    continue
                # 浏览器内验证（走浏览器网络会话，可过 Cloudflare）：
                # 已登录用户访问 setting_user.php 返回 200；未登录会被 302 到登录页
                try:
                    ok = await page.evaluate(
                        """async () => {
                            try {
                                const r = await fetch('https://www.pixiv.net/setting_user.php', {credentials: 'include', redirect: 'manual'});
                                return r.status === 200;
                            } catch (e) { return false; }
                        }"""
                    )
                except Exception:
                    ok = False
                if ok:
                    device = next((c["value"] for c in cookies if c.get("name") == "device_token" and c.get("value")), "")
                    cookie_line = f"PHPSESSID={sess}"
                    if device:
                        cookie_line += f"; device_token={device}"
                    await browser.close()
                    _update_env(cookie_line)
                    print(f"\n[成功] 登录确认！PHPSESSID 前 12 位: {sess[:12]}... (长度 {len(sess)})")
                    print("已写入 config/.env，重启弥娅后即可搜索 R18 作品 💕")
                    return 0
                if i % 30 == 0:
                    print(f"   ({i * 2}s) 尚未检测到登录成功，请在窗口中完成登录...")
            except Exception:
                pass
        print("\n[超时] 10 分钟内未检测到登录成功。请重新运行本脚本再试。")
        return 1
    finally:
        await p.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
