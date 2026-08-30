"""
多引擎绘画管理器 — 路由、调度与故障转移
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from .providers import PROVIDER_REGISTRY, ArtGenerationResult, ArtProvider

logger = logging.getLogger("artnet.manager")

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "artnet"


class ArtProviderManager:
    """多引擎绘画管理器

    职责：
    - 根据配置加载和初始化各绘画引擎
    - 按优先级路由生成请求
    - 故障自动转移
    - 管理生成任务状态
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_DIR / "providers.json"
        self._providers: dict[str, ArtProvider] = {}
        self._active_tasks: dict[str, ArtGenerationResult] = {}

    def load_providers(self) -> dict[str, ArtProvider]:
        """加载配置并初始化所有已启用的引擎"""
        config = self._read_config()
        providers: dict[str, ArtProvider] = {}

        for name, provider_config in config.get("providers", {}).items():
            if not provider_config.get("enabled", False):
                continue
            cls = PROVIDER_REGISTRY.get(name)
            if cls is None:
                logger.warning(f"[ArtNet] 未知引擎: {name}")
                continue
            try:
                provider = cls(provider_config)
                providers[name] = provider
                logger.info(f"[ArtNet] 引擎已加载: {provider.display_name}")
            except Exception as e:
                logger.error(f"[ArtNet] 引擎加载失败 ({name}): {e}")

        self._providers = providers
        return providers

    def get_providers(self) -> dict[str, ArtProvider]:
        return self._providers

    def get_provider(self, name: str) -> Optional[ArtProvider]:
        return self._providers.get(name)

    def get_provider_infos(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "enabled": p.enabled,
            }
            for p in self._providers.values()
        ]

    async def check_availability(self) -> dict[str, bool]:
        result = {}
        for name, provider in self._providers.items():
            result[name] = await provider.is_available()
        return result

    async def generate(
        self,
        prompt: str,
        *,
        provider: str = "",
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
        if provider:
            p = self._providers.get(provider)
            if p is None:
                return ArtGenerationResult(
                    task_id="",
                    provider=provider,
                    model="",
                    prompt=prompt,
                    error=f"引擎 {provider} 不可用",
                )
            return await p.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed,
                num_images=num_images,
                style=style,
                **kwargs,
            )

        priority = self._read_config().get("priority", [])
        ordered = []
        for name in priority:
            if name in self._providers:
                ordered.append(name)
        for name in self._providers:
            if name not in ordered:
                ordered.append(name)

        last_error = ""
        for name in ordered:
            p = self._providers[name]
            try:
                available = await p.is_available()
                if not available:
                    continue
                result = await p.generate(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                    num_images=num_images,
                    style=style,
                    **kwargs,
                )
                if result.success:
                    return result
                last_error = result.error or "未知错误"
                logger.warning(f"[ArtNet] {name} 生成失败: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"[ArtNet] {name} 异常: {e}")

        return ArtGenerationResult(
            task_id="",
            provider="all_failed",
            model="",
            prompt=prompt,
            error=f"所有引擎生成失败: {last_error}",
        )

    def _read_config(self) -> dict:
        if not self.config_path.exists():
            return DEFAULT_CONFIG
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[ArtNet] 加载配置失败，使用默认: {e}")
            return DEFAULT_CONFIG


DEFAULT_CONFIG: dict = {
    "priority": ["stable_diffusion", "dalle", "novelai", "cogview", "tongyi", "comfyui"],
    "providers": {
        "stable_diffusion": {
            "enabled": False,
            "base_url": "http://127.0.0.1:7860",
            "sampler": "Euler a",
            "timeout": 120,
        },
        "dalle": {
            "enabled": False,
            "model": "dall-e-3",
            "quality": "standard",
            "timeout": 120,
        },
        "cogview": {
            "enabled": False,
            "model": "cogview-3-plus",
            "timeout": 120,
        },
        "tongyi": {
            "enabled": False,
            "model": "wanx2.1-t2i-turbo",
            "timeout": 120,
        },
        "comfyui": {
            "enabled": False,
            "base_url": "http://127.0.0.1:8188",
            "timeout": 300,
        },
        "novelai": {
            "enabled": False,
            "model": "nai-diffusion-4-5-full",
            "sampler": "k_euler_ancestral",
            "timeout": 180,
        },
    },
}
