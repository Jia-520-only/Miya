#!/usr/bin/env python3
"""
娜迦网络社区认证模块 (NagaCAS)

实现 NagaBusiness 双 Token 认证：
- access_token: 30 分钟有效期 (Authorization Bearer)
- refresh_token: 7 天有效期 (Cookie 传输，后端持久化)

特性：
- 自动 Token 刷新（遇到 401 时）
- Token 持久化（跨进程重启恢复）
- 并发刷新互斥锁
"""

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("naga_community.auth")

# === 常量 ===
NAGA_BUSINESS_URL = os.getenv("NAGA_BUSINESS_URL", "http://62.234.131.204:30031")
MIYA_DATA_DIR = Path.home() / ".miya" / "naga_community"
AUTH_SESSION_FILE = MIYA_DATA_DIR / "auth_session.json"


class NagaAuth:
    """
    娜迦网络认证客户端。

    管理 access_token / refresh_token 的生命周期，
    自动刷新、持久化恢复。
    """

    def __init__(self, base_url: str = NAGA_BUSINESS_URL):
        self._base_url = base_url.rstrip("/")
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_time: float = 0.0

        # 启动时恢复会话
        self._restore_session()

    # ===== 属性 =====

    @property
    def is_logged_in(self) -> bool:
        return self._access_token is not None or self._refresh_token is not None

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    @property
    def user_info(self) -> Optional[Dict[str, Any]]:
        return self._user_info

    @property
    def base_url(self) -> str:
        return self._base_url

    # ===== 会话持久化 =====

    def _save_session(self) -> None:
        """持久化 refresh_token 到文件"""
        if not self._refresh_token:
            return

        MIYA_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "refresh_token": self._refresh_token,
                "user_info": self._user_info,
                "base_url": self._base_url,
            }
            AUTH_SESSION_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("[NagaAuth] 会话已持久化")
        except Exception as e:
            logger.error(f"[NagaAuth] 持久化会话失败: {e}")

    def _restore_session(self) -> bool:
        """从文件恢复 refresh_token"""
        if not AUTH_SESSION_FILE.exists():
            return False

        try:
            data = json.loads(AUTH_SESSION_FILE.read_text(encoding="utf-8"))
            self._refresh_token = data.get("refresh_token", "")
            self._user_info = data.get("user_info")
            if data.get("base_url"):
                self._base_url = data["base_url"]

            if self._refresh_token:
                logger.info(
                    f"[NagaAuth] 已恢复会话: user={self._user_info.get('username', '?') if self._user_info else '?'}"
                )
                # 异步刷新获取新 access_token
                return True
        except Exception as e:
            logger.warning(f"[NagaAuth] 恢复会话失败: {e}")

        return False

    def _clear_session(self) -> None:
        """清除本地会话"""
        self._access_token = None
        self._refresh_token = None
        self._user_info = None
        with contextlib.suppress(Exception):
            AUTH_SESSION_FILE.unlink(missing_ok=True)

    # ===== HTTP 客户端 =====

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    def _auth_headers(self) -> Dict[str, str]:
        """获取认证请求头"""
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    # ===== API 请求 =====

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """
        发送 API 请求，自动处理 Token 刷新。

        Args:
            method: HTTP 方法
            path: API 路径 (如 /api/forum/posts)
            json_data: JSON 请求体
            params: Query 参数
            auto_refresh: 是否自动刷新 Token（遇到 401 时）

        Returns:
            {"success": bool, "data": ..., "error": ...}
        """
        client = await self._get_client()
        url = f"{self._base_url}{path}"
        headers = self._auth_headers()

        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=json_data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=json_data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                return {"success": False, "error": f"不支持的 HTTP 方法: {method}"}

            # 401 自动刷新
            if response.status_code == 401 and auto_refresh and self._refresh_token:
                refreshed = await self.refresh_token()
                if refreshed:
                    # 使用新 token 重试
                    headers = self._auth_headers()
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(url, headers=headers, json=json_data)
                    elif method.upper() == "PUT":
                        response = await client.put(url, headers=headers, json=json_data)
                    elif method.upper() == "DELETE":
                        response = await client.delete(url, headers=headers)

            if response.status_code >= 400:
                error_detail = ""
                try:
                    error_body = response.json()
                    error_detail = error_body.get("detail", response.text[:500])
                except Exception:
                    error_detail = response.text[:500]

                return {
                    "success": False,
                    "error": error_detail,
                    "status_code": response.status_code,
                }

            try:
                data = response.json()
                return {"success": True, "data": data}
            except Exception:
                return {"success": True, "data": response.text}

        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"无法连接到 {self._base_url}，请检查网络",
            }
        except httpx.TimeoutException:
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            logger.exception(f"[NagaAuth] 请求异常: {method} {path}")
            return {"success": False, "error": str(e)}

    # ===== 认证操作 =====

    async def login(
        self,
        username: str,
        password: str,
        captcha_id: str = "",
        captcha_answer: str = "",
    ) -> Dict[str, Any]:
        """
        登录娜迦网络。

        POST /api/auth/login
        refresh_token 优先从 Set-Cookie 提取，其次从响应体
        """
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}

        json_data: Dict[str, Any] = {"username": username, "password": password}
        if captcha_id and captcha_answer:
            json_data["captcha_id"] = captcha_id
            json_data["captcha_answer"] = captcha_answer

        try:
            response = await client.post(
                f"{self._base_url}/api/auth/login",
                headers=headers,
                json=json_data,
            )
        except Exception as e:
            return {"success": False, "error": f"登录请求失败: {e}"}

        if response.status_code >= 400:
            error_detail = ""
            try:
                error_body = response.json()
                error_detail = error_body.get("detail", response.text[:500])
            except Exception:
                error_detail = response.text[:500]
            return {
                "success": False,
                "error": error_detail,
                "status_code": response.status_code,
            }

        data = response.json()
        self._access_token = data.get("access_token", "")
        self._user_info = data.get("user", {})

        # refresh_token 优先从 Set-Cookie 提取，其次从响应体
        self._refresh_token = (
            response.cookies.get("refresh_token", "") or data.get("refresh_token", "") or data.get("refreshToken", "")
        )

        if not self._access_token:
            return {"success": False, "error": "登录响应中缺少 access_token"}

        self._save_session()
        logger.info(f"[NagaAuth] 登录成功: {username}, refresh_token={'已获取' if self._refresh_token else '未获取'}")

        return {
            "success": True,
            "data": {
                "username": self._user_info.get("username", username),
                "id": self._user_info.get("id", ""),
                "message": "登录成功",
            },
        }

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        verification_code: str,
    ) -> Dict[str, Any]:
        """
        注册娜迦网络账号。

        POST /api/auth/register
        """
        result = await self._request(
            "POST",
            "/api/auth/register",
            json_data={
                "username": username,
                "email": email,
                "password": password,
                "verification_code": verification_code,
            },
            auto_refresh=False,
        )

        if result["success"]:
            logger.info(f"[NagaAuth] 注册成功: {username}")
            result["data"] = {"message": "注册成功，请登录", "username": username}

        return result

    async def send_verification_code(
        self,
        email: str,
        username: str,
    ) -> Dict[str, Any]:
        """
        发送邮箱验证码。

        POST /api/auth/send-verification
        """
        return await self._request(
            "POST",
            "/api/auth/send-verification",
            json_data={"email": email, "username": username},
            auto_refresh=False,
        )

    async def get_me(self) -> Dict[str, Any]:
        """获取当前用户信息"""
        result = await self._request("GET", "/api/auth/me")

        if result["success"]:
            self._user_info = result["data"]
            self._save_session()

        return result

    async def refresh_token(self) -> bool:
        """
        刷新 access_token。

        使用 refresh_token 获取新的 access_token。
        加互斥锁防止并发刷新。
        """
        async with self._refresh_lock:
            if not self._refresh_token:
                logger.warning("[NagaAuth] 无 refresh_token，无法刷新")
                return False

            # 10 秒保护窗口
            import time

            now = time.time()
            if now - self._last_refresh_time < 10:
                logger.debug("[NagaAuth] 刷新保护窗口内，跳过")
                return True

            logger.info("[NagaAuth] 正在刷新 token...")

            try:
                client = await self._get_client()
                response = await client.post(
                    f"{self._base_url}/api/auth/refresh",
                    headers={"Content-Type": "application/json"},
                    cookies={"refresh_token": self._refresh_token},
                )

                if response.status_code != 200:
                    logger.error(f"[NagaAuth] 刷新 token 失败: {response.status_code}")
                    self._clear_session()
                    return False

                data = response.json()
                new_access = data.get("access_token", "")
                new_refresh = data.get("refresh_token", "")

                if new_access:
                    self._access_token = new_access
                if new_refresh:
                    self._refresh_token = new_refresh

                self._last_refresh_time = now
                if new_refresh:
                    self._save_session()

                logger.info("[NagaAuth] Token 刷新成功")
                return True

            except Exception as e:
                logger.error(f"[NagaAuth] 刷新 token 异常: {e}")
                return False

    async def logout(self) -> Dict[str, Any]:
        """登出"""
        self._clear_session()
        logger.info("[NagaAuth] 已登出")
        return {"success": True, "data": {"message": "已登出"}}

    async def get_captcha(self) -> Dict[str, Any]:
        """获取验证码挑战"""
        result = await self._request("GET", "/api/auth/captcha", auto_refresh=False)
        if result.get("success"):
            return {"success": True, "data": result["data"]}
        return result

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ===== 全局单例 =====

_auth_instance: Optional[NagaAuth] = None


def get_auth() -> NagaAuth:
    """获取全局 NagaAuth 单例"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = NagaAuth()
    return _auth_instance
