"""
弥娅微信 iLink 独立登录工具
用法: python weixin_ilink_login.py
功能: 终端显示二维码，微信扫码登录后将凭据保存到弥娅的凭据存储中
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from weixin_ilink_client import (
    JsonCredentialStore,
    QrLoginManager,
    QrStatus,
    WeixinCredentials,
    default_state_dir,
)


def _get_store_dir() -> Path:
    import os

    state_env = os.environ.get("WEIXIN_ILINK_STATE_DIR", "")
    if state_env:
        return Path(state_env)
    return default_state_dir()


async def _save_credentials_safe(
    credential_store: JsonCredentialStore,
    store_dir: Path,
    alias: str,
    cred: WeixinCredentials,
) -> bool:
    import glob as _glob

    stale_tmps = list(store_dir.glob("*.tmp"))
    for f in stale_tmps:
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass

    for attempt in range(3):
        try:
            await credential_store.save(alias, cred)
            print(f"  [OK] 凭据已保存到: {store_dir / 'credentials.json'}")
            return True
        except Exception as e:
            if attempt < 2:
                print(f"  [!] 保存失败 (尝试 {attempt + 1}/3): {e}")
                await asyncio.sleep(1)
            else:
                import json

                fallback_path = store_dir / "credentials_fallback.json"
                data = {
                    "version": 1,
                    "accounts": {
                        alias: {
                            "account_id": cred.account_id,
                            "bot_token": cred.bot_token,
                            "base_url": cred.base_url,
                            "user_id": cred.user_id,
                            "saved_at": "",
                        }
                    },
                }
                fallback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                print(f"  [OK] 凭据已保存到: {fallback_path} (兜底模式)")
    return False


async def do_login(store_dir: Path) -> WeixinCredentials | None:
    manager = QrLoginManager(bot_type="3")
    credential_store = JsonCredentialStore(store_dir / "credentials.json")
    alias = "weixin_ilink"

    local_tokens: list[str] = []
    try:
        local = await credential_store.local_tokens(limit=5)
        local_tokens = [t for t in local if t]
        if local_tokens:
            print(f"[*] 发现 {len(local_tokens)} 个历史 token，尝试快速重连...")
    except Exception:
        pass

    session = await manager.start(local_tokens=local_tokens)
    print()
    print("=" * 60)
    print("  微信 iLink 扫码登录")
    print("=" * 60)
    print()
    print(f"  QR 图片地址: {session.qrcode_url}")
    print()
    print("  请在手机微信中扫描二维码登录")
    print("  (也可以浏览器打开上面的地址查看二维码)")
    print()
    print("=" * 60)

    try:
        while True:
            manager.ensure_fresh(session)
            result = await manager.poll(session)

            status = result.status
            msg = result.message

            if status == QrStatus.WAIT:
                print(f"\r  [*] 等待扫码... {msg or ''}", end="", flush=True)
            elif status == QrStatus.SCANNED:
                print(f"\r  [*] 已扫描，请在手机上确认登录... {msg or ''}", end="", flush=True)
            elif status == QrStatus.SCANNED_REDIRECT:
                print(f"\r  [*] 重定向中... {msg or ''}", end="", flush=True)
            elif status == QrStatus.NEED_VERIFY_CODE:
                print(f"\n  [!] 需要验证码: {msg}")
                code = input("  请输入验证码: ").strip()
                if code:
                    manager.submit_verify_code(session, code)
            elif status == QrStatus.EXPIRED:
                print(f"\n  [!] QR 码已过期，正在刷新...")
                session = await manager.refresh(session, local_tokens=local_tokens)
                print(f"  [*] 新 QR 地址: {session.qrcode_url}")
                print(f"  请重新扫描。")
            elif status == QrStatus.CONFIRMED:
                print(f"\n  [OK] 登录确认!")
                if result.credentials:
                    cred = result.credentials
                    print(f"  account_id: {cred.account_id}")
                    print(f"  user_id:    {cred.user_id}")

                    await _save_credentials_safe(credential_store, store_dir, alias, cred)
                    return cred
                break
            elif status == QrStatus.ALREADY_BOUND:
                print(f"\n  [!] 该账号已绑定: {msg}")
                return None
            else:
                print(f"\n  [?] 未知状态: {status} - {msg}")

            await asyncio.sleep(1.5)

    except KeyboardInterrupt:
        print("\n\n  [!] 用户取消")
        return None
    finally:
        await manager.aclose()

    return None


def main() -> int:
    store_dir = _get_store_dir()
    store_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] 凭据存储目录: {store_dir}")

    try:
        credentials = asyncio.run(do_login(store_dir))
    except KeyboardInterrupt:
        print("\n[!] 已取消")
        return 1
    except Exception as e:
        print(f"\n[!] 错误: {e}")
        return 1

    if credentials:
        print()
        print("=" * 60)
        print("  登录成功！")
        print("=" * 60)
        print(f"  account_id: {credentials.account_id}")
        print(f"  base_url:   {credentials.base_url}")
        print()
        print("  现在可以启动弥娅，weixin_ilink 适配器将自动加载凭据。")
        return 0

    print("\n[*] 未获取到凭据，可能是已登录或取消。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
