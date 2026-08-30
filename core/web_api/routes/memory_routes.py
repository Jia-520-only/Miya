"""
WebAPI 路由 — 记忆 CRUD 与查询（V4.1.11: 接入 MemoryBus）
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from memory.api.bus import get_memory_bus
from memory.models import MemoryLevel, MemoryQuery

logger = logging.getLogger("Miya.WebAPI.MemoryRoutes")
router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryAddRequest(BaseModel):
    content: str
    user_id: str = "default"
    tags: Optional[list[str]] = None
    level: Optional[str] = None
    priority: float = 0.5


@router.get("/stats")
async def memory_stats():
    try:
        bus = await get_memory_bus()
        stats = await bus.stats()
        return {"ok": True, "data": stats}
    except Exception as e:
        logger.error(f"[MemoryRoutes] stats 失败: {e}")
        return {"ok": False, "error": str(e), "data": {}}


@router.get("/list")
async def memory_list(
    user_id: str = Query(default=""),
    level: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    try:
        bus = await get_memory_bus()
        core = bus.core
        if not core:
            return {"ok": True, "memories": [], "total": 0}

        mem_level = MemoryLevel(level) if level else None
        q = MemoryQuery(user_id=user_id or None, level=mem_level, limit=limit)
        results = await core.retrieve(q)
        return {
            "ok": True,
            "memories": [m.to_dict() for m in results] if results else [],
            "total": len(results) if results else 0,
        }
    except Exception as e:
        logger.error(f"[MemoryRoutes] list 失败: {e}")
        return {"ok": False, "error": str(e), "memories": [], "total": 0}


@router.get("/search")
async def memory_search(
    query: str = Query(default="", min_length=1),
    user_id: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=100),
):
    try:
        bus = await get_memory_bus()
        result = await bus.recall(query=query, user_id=user_id, limit=limit)
        return {
            "ok": True,
            "results": [m.to_dict() for m in result.memories] if result.memories else [],
            "query": query,
            "total": result.total_found,
            "query_time_ms": result.query_time_ms,
        }
    except Exception as e:
        logger.error(f"[MemoryRoutes] search 失败: {e}")
        return {"ok": False, "error": str(e), "results": [], "query": query}


@router.post("/add")
async def memory_add(req: MemoryAddRequest):
    try:
        bus = await get_memory_bus()
        level = MemoryLevel(req.level) if req.level else None
        memory_id = await bus.store(
            content=req.content,
            user_id=req.user_id,
            level=level,
            priority=req.priority,
            tags=req.tags or [],
        )
        return {"ok": True, "memory_id": memory_id, "content": req.content}
    except Exception as e:
        logger.error(f"[MemoryRoutes] add 失败: {e}")
        return {"ok": False, "error": str(e), "memory_id": ""}


@router.delete("/{memory_id}")
async def memory_delete(memory_id: str):
    try:
        bus = await get_memory_bus()
        ok = await bus.delete(memory_id)
        return {"ok": ok, "memory_id": memory_id}
    except Exception as e:
        logger.error(f"[MemoryRoutes] delete 失败: {e}")
        return {"ok": False, "error": str(e), "memory_id": memory_id}
