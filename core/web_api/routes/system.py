"""
WebAPI 路由 — 系统状态与监控
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
async def system_info():
    return {"version": "9.0.0", "name": "MIYA", "status": "running"}


@router.get("/status")
async def system_status():
    return {"healthy": True, "uptime": 0, "memory_mb": 0}


@router.get("/logs")
async def system_logs(limit: int = 50):
    return {"logs": [], "total": 0}
