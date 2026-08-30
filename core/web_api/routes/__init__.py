"""
WebAPI v9.0 路由聚合

弥娅 v9.0 重构：拆分 2883 行 miya_api.py 为独立路由模块

路由模块:
- system:   系统状态、监控、配置、日志
- chat:     对话 SSE 流式
- memory:   记忆 CRUD
- personality: 人格管理
- models:   模型池管理
- auth:     认证管理
- health:   健康检查
"""

from fastapi import APIRouter

from core.web_api.routes import auth, chat, memory_routes, models_routes, personality, system

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(chat.router)
api_router.include_router(memory_routes.router)
api_router.include_router(personality.router)
api_router.include_router(models_routes.router)
api_router.include_router(auth.router)

# 健康检查
health_router = APIRouter()


@health_router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "9.0.0"}


@health_router.get("/api/health")
async def api_health_check():
    return {"status": "healthy", "version": "9.0.0"}


__all__ = ["api_router", "health_router"]
