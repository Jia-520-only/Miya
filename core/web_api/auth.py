"""
认证相关 API
处理用户注册、登录、权限验证等功能
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.config_utils import get_api_key

from .models import UserLogin, UserRegister

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "miya_sk_"


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """使用 PBKDF2-SHA256 安全哈希密码

    Returns:
        (hash_hex, salt_hex)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """验证密码"""
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


def _generate_token() -> str:
    """生成加密安全的 API token"""
    return _TOKEN_PREFIX + secrets.token_urlsafe(32)


class AuthRoutes:
    """认证路由"""

    def __init__(self, web_net, decision_hub):
        """初始化认证路由

        Args:
            web_net: WebNet 实例
            decision_hub: DecisionHub 实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub
        self.security = HTTPBearer(auto_error=False)
        self._access_token = get_api_key("MIYA_ACCESS_TOKEN") or _generate_token()
        logger.info("[AuthRoutes] 认证模块已初始化")

        # 创建独立的路由器
        self.router = APIRouter(prefix="/api/auth", tags=["Auth"])
        self._setup_routes()

    def _setup_routes(self):
        """设置认证相关路由"""
        self._setup_permission_checker()

        @self.router.post("/register")
        async def register_user(user_data: UserRegister):
            """用户注册"""
            try:
                result = await self.web_net.register_user(
                    username=user_data.username,
                    email=user_data.email,
                    password=user_data.password,
                )
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 用户注册失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/login")
        async def login_user(user_data: UserLogin):
            """用户登录"""
            username = user_data.username
            password = user_data.password

            try:
                result = await self.web_net.login_user(username=username, password=password)
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 用户登录失败: {e}")
                return {"status": "error", "message": "用户名或密码错误"}

        @self.router.post("/logout")
        async def logout_user():
            """用户登出"""
            try:
                logger.info("[WebAPI] 用户登出")
                return {"success": True, "message": "登出成功"}
            except Exception as e:
                logger.error(f"[WebAPI] 用户登出失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/me")
        async def get_current_user(
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
        ):
            """获取当前用户信息"""
            try:
                if not credentials or not credentials.credentials:
                    raise HTTPException(status_code=401, detail="未提供认证令牌")

                user_id = self._verify_token(credentials.credentials)
                if not user_id:
                    raise HTTPException(status_code=401, detail="无效的认证令牌")

                try:
                    from webnet.AuthNet.user_manager import UserManager

                    user_mgr = UserManager()
                    user_info = user_mgr.get_user_by_id(user_id)
                    if user_info:
                        return {
                            "id": user_info.get("user_id", user_id),
                            "username": user_info.get("username", user_id),
                            "email": user_info.get("email", ""),
                            "level": user_info.get("level", 1),
                            "trust_score": user_info.get("trust_score", 0),
                            "created_at": user_info.get("created_at", ""),
                            "last_login": user_info.get("last_login", ""),
                        }
                except Exception as e:
                    logger.warning(f"[WebAPI] 从数据库获取用户信息失败: {e}")

                return {
                    "id": user_id,
                    "username": user_id,
                    "email": "",
                    "level": 1,
                    "trust_score": 0,
                    "created_at": "",
                    "last_login": "",
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 获取当前用户失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _setup_permission_checker(self):
        """设置权限检查中间件"""

        async def check_api_permission(
            token: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
        ):
            """检查 API 权限"""
            try:
                if not token or not token.credentials:
                    return {"user_id": "anonymous", "web_user_id": "web_anonymous"}

                user_id = self._verify_token(token.credentials)
                if not user_id:
                    raise HTTPException(status_code=401, detail="无效的认证令牌")

                return {"user_id": user_id, "web_user_id": f"web_{user_id}"}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 权限检查失败: {e}")
                raise HTTPException(status_code=500, detail="权限检查失败")

        self.permission_checker = check_api_permission

    def _verify_token(self, token: str) -> Optional[str]:
        """验证 API token

        支持:
        1. 环境变量 MIYA_ACCESS_TOKEN
        2. webnet.AuthNet 权限系统验证
        """
        if not token or len(token) < 16:
            return None

        if secrets.compare_digest(token, self._access_token):
            return "admin"

        try:
            from webnet.AuthNet.permission_core import PermissionCore

            perm_core = PermissionCore()
            if perm_core.check_permission(f"web_{token}", "api.access"):
                return token
        except Exception as e:
            logger.warning(f"[WebAPI] 权限核心检查失败: {e}")

        return None

    def get_router(self):
        """获取路由器"""
        return self.router
