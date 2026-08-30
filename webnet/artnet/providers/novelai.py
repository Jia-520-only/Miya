"""
NovelAI Diffusion 图片生成适配器
"""

import asyncio
import logging
import os
import secrets
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.novelai")

DEFAULT_BASE_URL = "https://image.novelai.net"
DEFAULT_MODEL = "nai-diffusion-4-5-full"
DEFAULT_SAMPLER = "k_euler_ancestral"
DEFAULT_NEGATIVE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark"
)


class NovelAIProvider(ArtProvider):
    """NovelAI Diffusion 图片生成"""

    name = "novelai"
    display_name = "NovelAI Diffusion"
    description = "NovelAI 动漫风格图片生成"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "") or os.getenv("NOVELAI_API_KEY", "")
        self.base_url = config.get("base_url", DEFAULT_BASE_URL).rstrip("/")
        self.model = config.get("model", DEFAULT_MODEL)
        self.sampler = config.get("sampler", DEFAULT_SAMPLER)
        self.timeout = config.get("timeout", 180)

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/user/subscription",
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
        steps: int = 28,
        cfg_scale: float = 5.0,
        seed: int | None = None,
        num_images: int = 1,
        style: str = "",
        **kwargs,
    ) -> ArtGenerationResult:
        task_id = self.create_task_id()
        self._log_progress(task_id, f"开始生成 (NovelAI): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            if width < 64:
                width = 64
            if height < 64:
                height = 64
            width = max(64, round(width / 64) * 64)
            height = max(64, round(height / 64) * 64)

            if seed is None:
                seed = secrets.randbelow(2**32)

            n_samples = min(num_images, 4)
            negative = negative_prompt or DEFAULT_NEGATIVE

            parameters: dict = {
                "params_version": 3,
                "width": width,
                "height": height,
                "scale": cfg_scale,
                "cfg_rescale": 0.0,
                "sampler": self.sampler,
                "steps": min(max(steps, 1), 50),
                "n_samples": n_samples,
                "ucPreset": 0,
                "qualityToggle": True,
                "dynamic_thresholding": False,
                "legacy": False,
                "seed": seed,
                "negative_prompt": negative,
                "image_format": "png",
            }

            if "4" in self.model:
                parameters["v4_prompt"] = {
                    "caption": {"base_caption": prompt, "char_captions": []},
                    "use_coords": False,
                    "use_order": True,
                    "legacy_uc": False,
                }
                parameters["v4_negative_prompt"] = {
                    "caption": {"base_caption": negative, "char_captions": []},
                    "use_coords": False,
                    "use_order": True,
                    "legacy_uc": False,
                }

            payload = {
                "action": "generate",
                "input": prompt,
                "model": self.model,
                "parameters": parameters,
            }

            headers = self._headers()
            headers["Content-Type"] = "application/json"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/ai/generate-image",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()

            images = []
            content_type = resp.headers.get("content-type", "")
            if "application/zip" in content_type:
                import io
                import zipfile

                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                            images.append(zf.read(name))
            elif "image/" in content_type:
                images.append(resp.content)

            generation_time = asyncio.get_event_loop().time() - t_start
            self._log_progress(task_id, f"生成完成 ({generation_time:.1f}s, {len(images)} 张)")

            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                negative_prompt=negative,
                images=images,
                seed=seed,
                width=width,
                height=height,
                generation_time=generation_time,
            )

        except Exception as e:
            logger.error(f"[NovelAI] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                error=str(e),
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "MIYA/8.0 NovelAIArtTool",
        }
