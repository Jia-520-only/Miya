"""
智谱 CogView 图片生成适配器
"""

import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.cogview")


class CogViewProvider(ArtProvider):
    """智谱 CogView / CogView-4 图片生成"""

    name = "cogview"
    display_name = "CogView (智谱)"
    description = "智谱 CogView 系列模型"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "") or os.getenv("ZHIPU_API_KEY", "") or os.getenv("ZHIPUAI_API_KEY", "")
        self.base_url = config.get("base_url", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = config.get("model", "cogview-3-plus")
        self.timeout = config.get("timeout", 120)

        self._size_map: dict[str, str] = {
            "cogview-4": "1024x1024",
            "cogview-3-plus": "1024x1024",
            "cogview-3": "1024x1024",
        }

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
        self._log_progress(task_id, f"开始生成 (CogView): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                submit_resp = await client.post(
                    f"{self.base_url}/images/generations",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "n": min(num_images, 4),
                    },
                    headers=headers,
                )
                submit_resp.raise_for_status()
                submit_data = submit_resp.json()
                task_outer_id = submit_data.get("id", "")

            images = []
            if task_outer_id:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    for _ in range(60):
                        await asyncio.sleep(2)
                        result_resp = await client.get(
                            f"{self.base_url}/async-result/{task_outer_id}",
                            headers=headers,
                        )
                        if result_resp.status_code != 200:
                            continue
                        result_data = result_resp.json()
                        task_status = result_data.get("task_status", "")
                        if task_status == "SUCCESS":
                            for item in result_data.get("data", []):
                                img_url = item.get("url", "")
                                if img_url:
                                    img_resp = await client.get(img_url)
                                    if img_resp.status_code == 200:
                                        images.append(img_resp.content)
                            break
                        elif task_status == "FAIL":
                            raise RuntimeError(result_data.get("task_status_msg", "未知错误"))

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
            logger.error(f"[CogView] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model=self.model,
                prompt=prompt,
                error=str(e),
            )
