"""
WebAPI 路由 — 认证
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def auth_login(username: str = "", password: str = ""):
    return {"token": "", "user": username}


@router.post("/logout")
async def auth_logout():
    return {"status": "logged_out"}


@router.get("/status")
async def auth_status():
    return {"authenticated": False}
