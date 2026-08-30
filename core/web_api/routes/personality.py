"""
WebAPI 路由 — 人格管理
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/persona", tags=["personality"])


@router.get("/list")
async def persona_list():
    return {"personalities": ["default"], "current": "default"}


@router.get("/current")
async def persona_current():
    return {"name": "default", "form": "default"}


@router.post("/switch")
async def persona_switch(personality: str = "default"):
    return {"switched_to": personality, "success": True}
