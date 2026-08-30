"""
艺术画板 API 路由
提供 AI 绘画生成、画廊管理、引擎查询等接口
"""

import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import Response

logger = logging.getLogger("web_api.art")


class ArtGenerateRequest(BaseModel):
    prompt: str
    provider: str = ""
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 30
    cfg_scale: float = 7.0
    seed: Optional[int] = None
    num_images: int = 1
    style: str = ""


class ArtRoutes:
    """艺术画板 API 路由模块"""

    def __init__(self, web_net=None, decision_hub=None):
        self.web_net = web_net
        self.decision_hub = decision_hub
        self._manager = None
        self._storage = None

    @property
    def manager(self):
        if self._manager is None:
            from webnet.artnet import ArtProviderManager

            self._manager = ArtProviderManager()
            self._manager.load_providers()
        return self._manager

    @property
    def storage(self):
        if self._storage is None:
            from webnet.artnet import ArtStorage

            self._storage = ArtStorage()
        return self._storage

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/art", tags=["Art"])

        @router.get("/providers")
        async def list_providers():
            infos = self.manager.get_provider_infos()
            availability = await self.manager.check_availability()
            for info in infos:
                info["available"] = availability.get(info["name"], False)
            return {"success": True, "providers": infos}

        @router.get("/providers/refresh")
        async def refresh_providers():
            self.manager.load_providers()
            return await list_providers()

        @router.post("/generate")
        async def generate_art(req: ArtGenerateRequest):
            result = await self.manager.generate(
                prompt=req.prompt,
                provider=req.provider,
                negative_prompt=req.negative_prompt,
                width=req.width,
                height=req.height,
                steps=req.steps,
                cfg_scale=req.cfg_scale,
                seed=req.seed,
                num_images=req.num_images,
                style=req.style,
            )

            saved_entries = []
            if result.success and result.images:
                saved_entries = self.storage.save_batch(
                    result.images,
                    task_id=result.task_id,
                    provider=result.provider,
                    prompt=result.prompt,
                )

            return {
                "success": result.success,
                "task_id": result.task_id,
                "provider": result.provider,
                "model": result.model,
                "prompt": result.prompt,
                "image_count": len(result.images),
                "images": saved_entries,
                "seed": result.seed,
                "width": result.width,
                "height": result.height,
                "generation_time": result.generation_time,
                "error": result.error,
            }

        @router.get("/gallery")
        async def list_gallery(
            provider: str = "",
            limit: int = 50,
            offset: int = 0,
        ):
            images = self.storage.list_images(provider=provider, limit=limit, offset=offset)
            return {"success": True, "images": images, "total": len(images)}

        @router.get("/image/{filename}")
        async def get_image(filename: str):
            data = self.storage.get(filename)
            if data is None:
                raise HTTPException(status_code=404, detail="图片不存在")
            return Response(content=data, media_type="image/png")

        @router.get("/entry/{image_id}")
        async def get_entry(image_id: str):
            entry = self.storage.get_entry(image_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="条目不存在")
            return {"success": True, "entry": entry}

        @router.delete("/image/{image_id}")
        async def delete_image(image_id: str):
            ok = self.storage.delete(image_id)
            return {"success": ok}

        @router.delete("/gallery/clear")
        async def clear_gallery():
            count = self.storage.delete_all()
            return {"success": True, "deleted": count}

        @router.get("/stats")
        async def get_stats():
            return {"success": True, "stats": self.storage.stats()}

        @router.post("/mcp/generate")
        async def mcp_generate(req: ArtGenerateRequest):
            """供 MCP 服务内部调用 — 弥娅主动绘画"""
            return await generate_art(req)

        return router
