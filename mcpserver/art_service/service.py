"""
艺术服务 MCP 模块 — 让弥娅能够主动调用 AI 绘画
"""

import json
import logging
from typing import Any

logger = logging.getLogger("art_service")


class ArtService:
    """艺术 MCP 服务 — 弥娅的绘画能力入口"""

    def __init__(self):
        self.name = "art_service"
        self.description = "AI 绘画 - 让弥娅主动生成图片展示在画板上"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: dict[str, Any]) -> str:
        tool_name = str(tool_call.get("tool_name", "")).strip()

        try:
            if tool_name == "generate_image":
                return await self._generate_image(tool_call)
            elif tool_name == "list_providers":
                return await self._list_providers(tool_call)
            elif tool_name == "get_gallery":
                return await self._get_gallery(tool_call)
            else:
                return json.dumps(
                    {
                        "error": f"未知工具: {tool_name}",
                        "available": ["generate_image", "list_providers", "get_gallery"],
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.exception(f"[ArtService] 工具调用异常: {tool_name}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _generate_image(self, call: dict[str, Any]) -> str:
        from webnet.artnet import ArtProviderManager, ArtStorage

        prompt = str(call.get("prompt") or call.get("content") or call.get("message") or "一幅美丽的风景画").strip()

        provider = str(call.get("provider", "")).strip()
        negative = str(call.get("negative_prompt", "")).strip()
        style = str(call.get("style", "")).strip()
        width = int(call.get("width", 1024))
        height = int(call.get("height", 1024))

        manager = ArtProviderManager()
        manager.load_providers()
        storage = ArtStorage()

        result = await manager.generate(
            prompt=prompt,
            provider=provider,
            negative_prompt=negative,
            width=width,
            height=height,
            style=style,
        )

        saved = []
        image_urls = []
        local_paths = []
        if result.success and result.images:
            saved = storage.save_batch(
                result.images,
                task_id=result.task_id,
                provider=result.provider,
                prompt=result.prompt,
            )
            for entry in saved:
                image_urls.append(f"http://localhost:8000/api/art/image/{entry['filename']}")
                import os as _os

                abs_path = str(storage.images_dir / entry["filename"])
                local_paths.append(abs_path.replace("\\", "/"))

        return json.dumps(
            {
                "status": "success" if result.success else "error",
                "message": f"已通过 {result.provider} 生成 {len(result.images)} 张图片"
                if result.success
                else f"生成失败: {result.error}",
                "provider": result.provider,
                "prompt": result.prompt,
                "image_count": len(result.images),
                "images": saved,
                "image_urls": image_urls,
                "local_paths": local_paths,
                "generation_time": result.generation_time,
                "view_url": f"在画板查看: http://localhost:8000 或桌面端打开弥娅画板页面",
            },
            ensure_ascii=False,
        )

    async def _list_providers(self, call: dict[str, Any]) -> str:
        from webnet.artnet import ArtProviderManager

        manager = ArtProviderManager()
        manager.load_providers()
        availability = await manager.check_availability()
        infos = manager.get_provider_infos()

        for info in infos:
            info["available"] = availability.get(info["name"], False)

        return json.dumps(
            {
                "status": "success",
                "providers": infos,
            },
            ensure_ascii=False,
        )

    async def _get_gallery(self, call: dict[str, Any]) -> str:
        from webnet.artnet import ArtStorage

        storage = ArtStorage()
        provider = str(call.get("provider", "")).strip()
        limit = int(call.get("limit", 20))
        images = storage.list_images(provider=provider, limit=limit)

        return json.dumps(
            {
                "status": "success",
                "images": images,
                "total": len(images),
            },
            ensure_ascii=False,
        )
