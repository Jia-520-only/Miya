# -*- coding: utf-8 -*-
"""从本地浏览器提取 pixiv 的 PHPSESSID Cookie（写入 config/.env）

用法: python scripts/get_pixiv_cookie.py
支持 Chrome / Edge 的 Default 与 Profile* 配置，浏览器运行中也能尝试只读提取。
"""
import contextlib
import os
import shutil
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, ".")

CHROME_COOKIES = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies")
EDGE_COOKIES = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies")
CHROME_ROOT = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
EDGE_ROOT = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")


def _iter_cookie_dbs() -> list:
    """收集所有候选 Cookie 库路径（Default + Profile N）"""
    dbs = []
    for root in (CHROME_ROOT, EDGE_ROOT):
        if not os.path.isdir(root):
            continue
        for profile in sorted(os.listdir(root)):
            if profile not in ("Default",) and not profile.startswith("Profile"):
                continue
            db = os.path.join(root, profile, "Network", "Cookies")
            if os.path.exists(db):
                dbs.append(db)
    return dbs


def extract_phpsessid() -> str:
    for db_path in _iter_cookie_dbs():
        value = _try_extract(db_path)
        if value:
            return value
    print("\n[提示] 未找到 pixiv 的 PHPSESSID。请确认浏览器已登录 pixiv（国内需挂代理）。")
    return ""


def _try_extract(db_path: str) -> str:
    """尝试提取：复制库 → 只读直连 → 只读 immutable，三重回退"""
    # 1) 复制到临时文件（浏览器锁定时会失败）
    for attempt in range(3):
        tmp = os.path.join(tempfile.gettempdir(), f"miya_ck_{os.getpid()}_{attempt}.db")
        try:
            shutil.copyfile(db_path, tmp)
            value = _query(tmp)
            if value:
                return value
        except PermissionError:
            if attempt == 0:
                print(f"[提示] {os.path.basename(os.path.dirname(os.path.dirname(db_path)))} 运行中，尝试只读直连...")
        except Exception as e:
            print(f"[提取] {db_path} 复制失败: {e}")
            break
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        time.sleep(0.5)

    # 2) 只读直连原库（WAL 模式下可能被锁）
    try:
        value = _query(db_path, read_only=True)
        if value:
            return value
    except Exception as e:
        print(f"[提取] 只读直连失败: {e}")

    return ""


def _query(db_path: str, read_only: bool = False) -> str:
    if read_only:
        uri = f"file:{db_path.replace(os.sep, '/')}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%pixiv.net' AND name='PHPSESSID'"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return ""
    import win32crypt

    for name, enc in rows:
        try:
            value = win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1].decode("utf-8", "ignore")
            if value:
                return value
        except Exception as e:
            print(f"[提取] 解密失败（可能是新版浏览器应用层加密）: {e}")
    return ""


def update_env(cookie: str) -> None:
    env_path = os.path.abspath("config/.env")
    if not os.path.exists(env_path):
        print("[写入] config/.env 不存在")
        return
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    line = f"PIXIV_COOKIE=PHPSESSID={cookie}"
    import re

    if re.search(r"^PIXIV_COOKIE=.*$", content, re.M):
        content = re.sub(r"^PIXIV_COOKIE=.*$", line, content, flags=re.M)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += line + "\n"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[写入] PIXIV_COOKIE 已更新到 config/.env")


if __name__ == "__main__":
    ck = extract_phpsessid()
    if ck:
        print(f"[提取] 成功，PHPSESSID 前 12 位: {ck[:12]}... (长度 {len(ck)})")
        update_env(ck)
        sys.exit(0)

    print("\n⏳ 进入等待模式：请关闭所有 Chrome / Edge 浏览器窗口（任务栏右键退出），")
    print("   弥娅每 3 秒自动重试，最长等待 90 秒...")
    for i in range(30):
        time.sleep(3)
        ck = extract_phpsessid()
        if ck:
            print(f"\n[提取] 成功！PHPSESSID 前 12 位: {ck[:12]}... (长度 {len(ck)})")
            update_env(ck)
            sys.exit(0)
        print(f"   ({(i + 1) * 3}s) 仍在等待浏览器关闭...")

    print("\n[超时] 自动提取失败。手动获取方式:")
    print("浏览器 F12 → Console 输入 document.cookie 回车，")
    print("把输出里的 PHPSESSID=xxx 部分填到 config/.env:")
    print("  PIXIV_COOKIE=PHPSESSID=xxx")
    print("（登录 pixiv 后 cookie 才会存在；国内需挂代理访问）")
