"""
ComfyUI 节点式工作流 API 适配器
"""

import asyncio
import json
import logging
import uuid
from typing import Optional

import httpx

from .base import ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.comfyui")


class ComfyUIProvider(ArtProvider):
    """ComfyUI API 适配器"""

    name = "comfyui"
    display_name = "ComfyUI"
    description = "ComfyUI 节点式工作流"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://127.0.0.1:8188").rstrip("/")
        self.timeout = config.get("timeout", 300)
        self.default_workflow = config.get("workflow", {})
        self.client_id = str(uuid.uuid4())

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/system_stats")
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
        self._log_progress(task_id, f"开始生成 (ComfyUI): {prompt[:50]}...")

        t_start = asyncio.get_event_loop().time()

        try:
            workflow = self._build_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt or "",
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed,
                num_images=num_images,
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                queue_resp = await client.post(
                    f"{self.base_url}/prompt",
                    json={"prompt": workflow, "client_id": self.client_id},
                )
                queue_resp.raise_for_status()
                prompt_id = queue_resp.json().get("prompt_id", "")

            images = []
            if prompt_id:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    for _ in range(120):
                        await asyncio.sleep(2)
                        history_resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                        if history_resp.status_code != 200:
                            continue
                        history = history_resp.json()
                        outputs = history.get(prompt_id, {}).get("outputs", {})
                        if not outputs:
                            continue

                        for node_id, node_output in outputs.items():
                            for item in node_output.get("images", []):
                                filename = item.get("filename", "")
                                subfolder = item.get("subfolder", "")
                                ftype = item.get("type", "")
                                if filename:
                                    params = {"filename": filename, "subfolder": subfolder, "type": ftype}
                                    img_resp = await client.get(f"{self.base_url}/view", params=params)
                                    if img_resp.status_code == 200:
                                        images.append(img_resp.content)

                        if len(images) >= num_images:
                            break

            generation_time = asyncio.get_event_loop().time() - t_start
            self._log_progress(task_id, f"生成完成 ({generation_time:.1f}s, {len(images)} 张)")

            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model="ComfyUI",
                prompt=prompt,
                images=images,
                seed=seed,
                width=width,
                height=height,
                generation_time=generation_time,
            )

        except Exception as e:
            logger.error(f"[ComfyUI] 生成失败 ({task_id}): {e}")
            return ArtGenerationResult(
                task_id=task_id,
                provider=self.name,
                model="ComfyUI",
                prompt=prompt,
                error=str(e),
            )

    def _get_available_checkpoint(self) -> str:
        """自动检测可用的 checkpoint 模型"""
        try:
            import httpx

            resp = httpx.get(
                f"{self.base_url}/object_info",
                timeout=5.0,
                follow_redirects=True,
            )
            data = resp.json()
            ckpt_info = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {})
            names_list = ckpt_info.get("ckpt_name", [])
            if isinstance(names_list, list) and len(names_list) > 0:
                first = names_list[0]
                return first if isinstance(first, str) else (first[0] if first else "sd_xl_base_1.0.safetensors")
            return "v1-5-pruned-emaonly-fp16.safetensors"
        except Exception:
            return "v1-5-pruned-emaonly-fp16.safetensors"

    def _build_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int | None,
        num_images: int,
    ) -> dict:
        """构建默认文生图工作流"""

        if self.default_workflow:
            workflow = json.loads(json.dumps(self.default_workflow))
            for node_id, node_data in workflow.items():
                inputs = node_data.get("inputs", {})
                widget_values = node_data.get("_meta", {}).get("title", "")
                cls_type = node_data.get("class_type", "")
                if cls_type == "CLIPTextEncode" and "positive" in widget_values.lower():
                    inputs["text"] = prompt
                elif cls_type == "CLIPTextEncode" and "negative" in widget_values.lower():
                    inputs["text"] = negative_prompt
                elif cls_type == "EmptyLatentImage":
                    inputs["width"] = width
                    inputs["height"] = height
                    inputs["batch_size"] = num_images
                elif cls_type == "KSampler":
                    inputs["steps"] = steps
                    inputs["cfg"] = cfg_scale
                    if seed is not None:
                        inputs["seed"] = seed
            return workflow

        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed if seed is not None else 0,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": self._get_available_checkpoint()}},
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": num_images},
            },
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}},
        }
