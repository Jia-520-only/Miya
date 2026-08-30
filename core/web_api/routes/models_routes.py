"""
WebAPI 路由 — 模型池与调度
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from core.model_pool_manager import get_model_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/list")
async def models_list():
    try:
        pool = get_model_pool()
        models = pool.list_all()
        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.error(f"[models/list] 获取模型列表失败: {e}")
        return {"models": [], "count": 0}


@router.get("/status")
async def models_status():
    try:
        pool = get_model_pool()
        stats = pool.get_stats()
        return {
            "total": stats.get("total", 0),
            "enabled": stats.get("enabled", 0),
            "disabled": stats.get("total", 0) - stats.get("enabled", 0),
            "by_type": stats.get("by_type", {}),
        }
    except Exception as e:
        logger.error(f"[models/status] 获取模型状态失败: {e}")
        return {"total": 0, "enabled": 0}


@router.get("/routing")
async def models_routing(task_type: Optional[str] = Query(None)):
    try:
        pool = get_model_pool()
        if task_type:
            model = pool.select_model(task_type)
            return {
                "task_type": task_type,
                "selected": {"id": model.id, "name": model.name, "provider": model.provider} if model else None,
            }
        return {
            "task_types": [
                "simple_chat",
                "complex_reasoning",
                "code_analysis",
                "code_generation",
                "tool_calling",
                "creative_writing",
                "agent_mode",
            ]
        }
    except Exception as e:
        logger.error(f"[models/routing] 获取路由信息失败: {e}")
        return {"task_types": []}
