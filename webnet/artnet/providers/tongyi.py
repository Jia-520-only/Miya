"""
阿里通义万相图片生成适配器
"""

import asyncio
import base64
import logging
import os
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.tongyi")


class TongyiProvider(ArtProvider):
    """阿里通义万相图片生成"""

    name = "tongyi"
    display_name = "通义万相 (阿里)"
    description = "阿里通义万相系列模型"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "") or os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = config.get("base_url", "https://dashscope.aliyuncs.com").rstrip("/")
        self.model = config.get("model", "wanx2.1-t2i-turbo")
        self.timeout = config.get("timeout", 120)

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        return True

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
        self._log_progress(task_id, f"开始生成 (通义): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            payload: dict = {
                "model": self.model,
                "input": {"prompt": prompt},
                "parameters": {
                    "size": f"{width}*{height}",
                    "n": min(num_images, 4),
                },
            }
            if negative_prompt:
                payload["input"]["negative_prompt"] = negative_prompt
            if seed is not None:
                payload["parameters"]["seed"] = seed

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                submit_resp = await client.post(
                    f"{self.base_url}/api/v1/services/aigc/text2image/image-synthesis",
                    json=payload,
                    headers=headers,
                )
                submit_resp.raise_for_status()
                submit_data = submit_resp.json()
                task_outer_id = submit_data.get("output", {}).get("task_id", "")

            images = []
            if task_outer_id:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    for _ in range(60):
                        await asyncio.sleep(2)
                        result_resp = await client.get(
                            f"{self.base_url}/api/v1/tasks/{task_outer_id}",
                            headers=headers,
                        )
                        result_resp.raise_for_status()
                        result_data = result_resp.json()
                        task_status = result_data.get("output", {}).get("task_status", "")
                        if task_status == "SUCCEEDED":
                            results = result_data.get("output", {}).get("results", [])
                            for item in results:
                                img_url = item.get("url", "")
                                if img_url:
                                    img_resp = await client.get(img_url)
                                    if img_resp.status_code == 200:
                                        images.append(img_resp.content)
                            break
                        elif task_status in ("FAILED", "ERROR"):
                            raise RuntimeError(str(result_data.get("output", {}).get("message", "未知错误")))

            generation_time = asyncio.get_event_loop().time() - t_start
            self._log_progress(task_id, f"生成完成 ({generation_time:.1f}s, {len(images)} 张)")

            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                images=images,
                width=width,
                height=height,
                generation_time=generation_time,
            )

        except Exception as e:
            logger.error(f"[通义] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                error=str(e),
            )
