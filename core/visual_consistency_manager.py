"""
视觉一致性管理器
基于StoryMaker和IP-Adapter原理，维持角色脸部、发型、服装跨帧一致性
"""
import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


class ImageConsistencyLevel(Enum):
    """图像一致性级别"""
    LOW = 0.3      # 低一致性（仅保持基本特征）
    MEDIUM = 0.6    # 中等一致性（保持主要特征）
    HIGH = 0.8       # 高一致性（保持所有特征）
    ULTRA = 1.0      # 超高一致性（像素级一致）


@dataclass
class CharacterReference:
    """角色参考"""
    character_id: str
    reference_images: List[bytes] = field(default_factory=list)
    embedding: Optional[bytes] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def get_image_hash(self, idx: int = 0) -> str:
        """获取图像哈希"""
        if idx >= len(self.reference_images):
            return ""
        return hashlib.md5(self.reference_images[idx]).hexdigest()


class VisualConsistencyManager:
    """视觉一致性管理器"""

    def __init__(self, storage_path: str = "data/visual_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # 角色参考库
        self.character_references: Dict[str, CharacterReference] = {}

        # 风格参考库
        self.style_references: Dict[str, CharacterReference] = {}

        # 默认一致性级别
        self.default_consistency_level = ImageConsistencyLevel.HIGH

    def add_character_reference(
        self,
        character_id: str,
        reference_image: bytes,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加角色参考图像

        Args:
            character_id: 角色ID
            reference_image: 参考图像（bytes）
            attributes: 角色属性（发型、服装、眼睛等）

        Returns:
            是否成功
        """
        try:
            if character_id not in self.character_references:
                self.character_references[character_id] = CharacterReference(
                    character_id=character_id
                )

            ref = self.character_references[character_id]
            ref.reference_images.append(reference_image)
            ref.updated_at = time.time()

            if attributes:
                ref.attributes.update(attributes)

            # 保存到磁盘
            self._save_reference(character_id, ref)

            logger.info(f"[Visual] 添加角色参考: {character_id}")
            return True

        except Exception as e:
            logger.error(f"[Visual] 添加角色参考失败: {e}")
            return False

    def add_style_reference(
        self,
        style_id: str,
        reference_image: bytes,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加风格参考图像

        Args:
            style_id: 风格ID
            reference_image: 参考图像
            attributes: 风格属性（画风、调色等）

        Returns:
            是否成功
        """
        try:
            if style_id not in self.style_references:
                self.style_references[style_id] = CharacterReference(
                    character_id=style_id
                )

            ref = self.style_references[style_id]
            ref.reference_images.append(reference_image)
            ref.updated_at = time.time()

            if attributes:
                ref.attributes.update(attributes)

            self._save_reference(style_id, ref, is_style=True)

            logger.info(f"[Visual] 添加风格参考: {style_id}")
            return True

        except Exception as e:
            logger.error(f"[Visual] 添加风格参考失败: {e}")
            return False

    def generate_consistent_image(
        self,
        character_id: str,
        prompt: str,
        consistency_level: Optional[ImageConsistencyLevel] = None,
        style_id: Optional[str] = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        生成一致的角色图像

        Args:
            character_id: 角色ID
            prompt: 生成提示词
            consistency_level: 一致性级别
            style_id: 风格ID（可选）
            **kwargs: 其他参数

        Returns:
            生成的图像（bytes）
        """
        if character_id not in self.character_references:
            logger.warning(f"[Visual] 角色参考不存在: {character_id}")
            return None

        ref = self.character_references[character_id]
        level = consistency_level or self.default_consistency_level

        # 构建一致性提示词
        enhanced_prompt = self._build_consistency_prompt(
            prompt, ref, level, style_id
        )

        # 注意：这里需要实际的图像生成模型（如SD、IP-Adapter等）
        # 当前返回模拟结果
        logger.info(f"[Visual] 生成一致图像: {character_id}, 级别: {level.value}")
        return self._generate_image_mock(enhanced_prompt, **kwargs)

    def generate_sequence(
        self,
        character_id: str,
        base_prompt: str,
        num_frames: int = 4,
        consistency_level: Optional[ImageConsistencyLevel] = None
    ) -> List[Optional[bytes]]:
        """
        生成图像序列（用于视频生成）

        Args:
            character_id: 角色ID
            base_prompt: 基础提示词
            num_frames: 帧数
            consistency_level: 一致性级别

        Returns:
            图像序列
        """
        if character_id not in self.character_references:
            return [None] * num_frames

        ref = self.character_references[character_id]
        level = consistency_level or self.default_consistency_level
        frames = []

        for i in range(num_frames):
            frame_prompt = f"{base_prompt}, frame {i+1}/{num_frames}"
            frame = self.generate_consistent_image(
                character_id, frame_prompt, level
            )
            frames.append(frame)

        logger.info(f"[Visual] 生成序列: {character_id}, {num_frames}帧")
        return frames

    def calculate_consistency_score(
        self,
        image1: bytes,
        image2: bytes
    ) -> float:
        """
        计算两幅图像的一致性分数

        Args:
            image1: 图像1
            image2: 图像2

        Returns:
            一致性分数（0-1）
        """
        # 简化实现：比较图像哈希
        hash1 = hashlib.md5(image1).hexdigest()
        hash2 = hashlib.md5(image2).hexdigest()

        # 计算汉明距离
        hamming = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        max_hamming = len(hash1) * 4  # 每个字符最多4位差异

        consistency = 1.0 - (hamming / max_hamming)
        return round(consistency, 3)

    def maintain_character_library(self):
        """维护角色库（清理过期引用）"""
        current_time = time.time()
        expiry_days = 30

        to_remove = []
        for char_id, ref in self.character_references.items():
            if (current_time - ref.updated_at) > expiry_days * 86400:
                to_remove.append(char_id)

        for char_id in to_remove:
            del self.character_references[char_id]
            logger.info(f"[Visual] 清理过期角色: {char_id}")

    def _build_consistency_prompt(
        self,
        prompt: str,
        ref: CharacterReference,
        level: ImageConsistencyLevel,
        style_id: Optional[str] = None
    ) -> str:
        """构建一致性提示词"""
        # 添加角色属性
        if ref.attributes:
            attr_prompts = []
            for key, value in ref.attributes.items():
                attr_prompts.append(f"{key}: {value}")

            if attr_prompts:
                prompt = f"{prompt}, {', '.join(attr_prompts)}"

        # 添加风格
        if style_id and style_id in self.style_references:
            style_ref = self.style_references[style_id]
            if style_ref.attributes:
                style_prompt = ", ".join(
                    f"{k}: {v}" for k, v in style_ref.attributes.items()
                )
                prompt = f"{prompt}, style: {style_prompt}"

        # 添加一致性指示词
        consistency_keywords = {
            ImageConsistencyLevel.LOW: ["loose consistency"],
            ImageConsistencyLevel.MEDIUM: ["moderate consistency"],
            ImageConsistencyLevel.HIGH: ["high consistency", "maintain features"],
            ImageConsistencyLevel.ULTRA: [
                "ultra consistency",
                "exact match",
                "pixel-perfect"
            ]
        }

        keywords = consistency_keywords.get(level, [])
        if keywords:
            prompt = f"{prompt}, {', '.join(keywords)}"

        return prompt

    def _generate_image_mock(self, prompt: str, **kwargs) -> bytes:
        """模拟图像生成（实际实现需要SD等模型）"""
        # 返回一个虚拟图像
        mock_data = f"MOCK_IMAGE: {prompt}".encode()
        return mock_data

    def _save_reference(
        self,
        ref_id: str,
        ref: CharacterReference,
        is_style: bool = False
    ):
        """保存参考到磁盘"""
        directory = self.storage_path / ("styles" if is_style else "characters")
        directory.mkdir(exist_ok=True)

        filepath = directory / f"{ref_id}.json"

        data = {
            'character_id': ref.character_id,
            'image_hashes': [ref.get_image_hash(i) for i in range(len(ref.reference_images))],
            'attributes': ref.attributes,
            'created_at': ref.created_at,
            'updated_at': ref.updated_at
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_reference(self, ref_id: str, is_style: bool = False) -> bool:
        """从磁盘加载参考"""
        directory = self.storage_path / ("styles" if is_style else "characters")
        filepath = directory / f"{ref_id}.json"

        if not filepath.exists():
            return False

        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            ref = CharacterReference(
                character_id=data['character_id'],
                attributes=data.get('attributes', {}),
                created_at=data.get('created_at', time.time()),
                updated_at=data.get('updated_at', time.time())
            )

            if is_style:
                self.style_references[ref_id] = ref
            else:
                self.character_references[ref_id] = ref

            return True

        except Exception as e:
            logger.error(f"[Visual] 加载参考失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_characters': len(self.character_references),
            'total_styles': len(self.style_references),
            'total_references': sum(
                len(ref.reference_images)
                for ref in self.character_references.values()
            ) + sum(
                len(ref.reference_images)
                for ref in self.style_references.values()
            )
        }
