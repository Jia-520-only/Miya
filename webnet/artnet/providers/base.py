"""
绘画引擎抽象基类
"""

import base64
import hashlib
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("artnet.provider")


@dataclass
class ArtGenerationResult:
    """绘画生成结果"""

    task_id: str
    provider: str
    model: str
    prompt: str
    negative_prompt: str = ""
    images: list[bytes] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    seed: Optional[int] = None
    width: int = 1024
    height: int = 1024
    generation_time: float = 0.0
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.images) > 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "provider": self.provider,
            "model": self.model,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "image_count": len(self.images),
            "image_urls": self.image_urls,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "generation_time": self.generation_time,
            "metadata": self.metadata,
            "error": self.error,
            "success": self.success,
        }

    def get_image_b64(self, index: int = 0) -> Optional[str]:
        """获取指定图片的 base64 编码"""
        if 0 <= index < len(self.images):
            return base64.b64encode(self.images[index]).decode("utf-8")
        return None


class ArtProvider(ABC):
    """绘画引擎抽象基类"""

    name: str = "base"
    display_name: str = "基础引擎"
    description: str = ""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        cfg_scale: float = 7.0,
        seed: Optional[int] = None,
        num_images: int = 1,
        style: str = "",
        **kwargs,
    ) -> ArtGenerationResult:
        """生成图片"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查引擎是否可用"""
        ...

    def create_task_id(self) -> str:
        return f"art_{uuid.uuid4().hex[:12]}"

    def _hash_image(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]

    def _log_progress(self, task_id: str, message: str):
        logger.info(f"[Art/{self.name}] {task_id}: {message}")

    async def cancel(self, task_id: str) -> bool:
        return True
