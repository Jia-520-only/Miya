"""
Stable Diffusion WebUI / Forge API 适配器
"""

import asyncio
import json
import logging
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.sd")


class StableDiffusionProvider(ArtProvider):
    """Stable Diffusion (AUTOMATIC1111 / Forge) API"""

    name = "stable_diffusion"
    display_name = "Stable Diffusion"
    description = "本地 Stable Diffusion WebUI / Forge API"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://127.0.0.1:7860").rstrip("/")
        self.timeout = config.get("timeout", 120)
        self.default_model = config.get("model", "")
        self.default_sampler = config.get("sampler", "Euler a")
        self.auth = config.get("auth", "")

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/sdapi/v1/options",
                    headers=self._headers(),
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
        self._log_progress(task_id, f"开始生成 (SD): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt or "",
                "steps": steps,
                "cfg_scale": cfg_scale,
                "width": width,
                "height": height,
                "batch_size": num_images,
                "sampler_name": self.default_sampler,
                "seed": seed if seed is not None else -1,
            }

            if self.default_model:
                payload["override_settings"] = {"sd_model_checkpoint": self.default_model}

            headers = self._headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            images = [bytes.fromhex(img_b64_str) for img_b64_str in data.get("images", [])]
            generation_time = asyncio.get_event_loop().time() - t_start

            info = json.loads(data.get("info", "{}"))
            actual_seed = info.get("seed", seed)

            self._log_progress(task_id, f"生成完成 ({generation_time:.1f}s)")

            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.default_model or "SD",
                prompt=prompt,
                negative_prompt=negative_prompt,
                images=images,
                seed=actual_seed,
                width=width,
                height=height,
                generation_time=generation_time,
                metadata={"sampler": self.default_sampler, "steps": steps, "cfg_scale": cfg_scale},
            )

        except Exception as e:
            logger.error(f"[SD] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.default_model or "SD",
                prompt=prompt,
                error=str(e),
            )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.auth:
            import base64

            h["Authorization"] = f"Basic {base64.b64encode(self.auth.encode()).decode()}"
        return h
