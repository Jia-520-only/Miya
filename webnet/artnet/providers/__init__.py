"""
绘画引擎适配器注册表
"""

from .base import ArtProvider, ArtGenerationResult
from .stable_diffusion import StableDiffusionProvider
from .dalle import DalleProvider
from .cogview import CogViewProvider
from .tongyi import TongyiProvider
from .comfyui import ComfyUIProvider
from .novelai import NovelAIProvider

PROVIDER_REGISTRY: dict[str, type[ArtProvider]] = {
    "stable_diffusion": StableDiffusionProvider,
    "dalle": DalleProvider,
    "cogview": CogViewProvider,
    "tongyi": TongyiProvider,
    "comfyui": ComfyUIProvider,
    "novelai": NovelAIProvider,
}

__all__ = [
    "ArtProvider",
    "ArtGenerationResult",
    "StableDiffusionProvider",
    "DalleProvider",
    "CogViewProvider",
    "TongyiProvider",
    "ComfyUIProvider",
    "PROVIDER_REGISTRY",
]
