"""
OpenAI DALL·E 3 / DALL·E 2 适配器
"""

import asyncio
import base64
import logging
import os
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.dalle")


class DalleProvider(ArtProvider):
    """OpenAI DALL·E 图片生成"""

    name = "dalle"
    display_name = "DALL·E"
    description = "OpenAI DALL·E 3 / DALL·E 2"

    def __init__(self, config: dict):
        super().__init__(config)
        env_key = config.get("env_key", "OPENAI_API_KEY")
        self.api_key = config.get("api_key", "") or os.getenv(env_key, "")
        base_url = config.get("base_url", "https://api.openai.com").rstrip("/")
        self.api_url = f"{base_url}/v1/images/generations"
        self.model = config.get("model", "dall-e-3")
        self.quality = config.get("quality", "standard")
        self.timeout = config.get("timeout", 120)

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        cfg_scale: float = 7.0,
        seed: int | None = None,
        num_images: int = 1,
        style: str = "",
        **kwargs,
    ) -> ArtGenerationResult:
        task_id = self.create_task_id()
        self._log_progress(task_id, f"开始生成 (DALL·E): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            size_map = {
                (1024, 1024): "1024x1024",
                (1792, 1024): "1792x1024",
                (1024, 1792): "1024x1792",
            }
            size = size_map.get((width, height), "1024x1024")

            n = 1 if self.model == "dall-e-3" else min(num_images, 10)

            payload = {
                "model": self.model,
                "prompt": prompt,
                "n": n,
                "size": size,
                "quality": self.quality if self.model == "dall-e-3" else None,
                "style": style or "vivid",
                "response_format": "b64_json",
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            images = []
            image_urls = []
            for item in data.get("data", []):
                if "b64_json" in item:
                    images.append(base64.b64decode(item["b64_json"]))
                if "url" in item:
                    image_urls.append(item["url"])
                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            img_resp = await client.get(item["url"])
                            if img_resp.status_code == 200:
                                images.append(img_resp.content)
                    except Exception:
                        pass

            generation_time = asyncio.get_event_loop().time() - t_start
            self._log_progress(task_id, f"生成完成 ({generation_time:.1f}s, {len(images)} 张)")

            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                images=images,
                image_urls=image_urls,
                width=width,
                height=height,
                generation_time=generation_time,
                metadata={"quality": self.quality, "size": size, "style": style},
            )

        except Exception as e:
            logger.error(f"[DALL·E] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                error=str(e),
            )
