"""
StoryMaker/Amphion多模态库集成
提供多模态生成的一致性管理接口
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MultimodalConfig:
    """多模态配置"""
    image_model_path: Optional[str] = None
    audio_model_path: Optional[str] = None
    device: str = "cpu"
    image_size: Tuple[int, int] = (512, 512)
    audio_sample_rate: int = 22050
    consistency_level: float = 0.8


class MultimodalIntegrator:
    """多模态集成器"""

    def __init__(self, config: Optional[MultimodalConfig] = None):
        self.config = config or MultimodalConfig()

        # 组件（延迟加载）
        self._visual_manager = None
        self._audio_manager = None
        self._multimodal_store = None

    @property
    def visual_manager(self):
        """获取视觉一致性管理器"""
        if self._visual_manager is None:
            from core.visual_consistency_manager import VisualConsistencyManager
            self._visual_manager = VisualConsistencyManager()
        return self._visual_manager

    @property
    def audio_manager(self):
        """获取音频一致性管理器"""
        if self._audio_manager is None:
            from core.audio_consistency_manager import AudioConsistencyManager
            self._audio_manager = AudioConsistencyManager()
        return self._audio_manager

    @property
    def multimodal_store(self):
        """获取多模态记忆存储"""
        if self._multimodal_store is None:
            from memory.multimodal_memory_store import MultiModalMemoryStore, ModalityType
            self._multimodal_store = MultiModalMemoryStore()
        return self._multimodal_store

    def add_character_profile(
        self,
        character_id: str,
        visual_reference: Optional[bytes] = None,
        audio_reference: Optional[bytes] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        添加角色完整配置（视觉+音频）

        Args:
            character_id: 角色ID
            visual_reference: 视觉参考图像
            audio_reference: 音频参考
            attributes: 角色属性

        Returns:
            各模态添加结果
        """
        results = {
            'visual': False,
            'audio': False
        }

        if visual_reference:
            results['visual'] = self.visual_manager.add_character_reference(
                character_id,
                visual_reference,
                attributes
            )

        if audio_reference:
            results['audio'] = self.audio_manager.add_speaker_reference(
                character_id,
                audio_reference,
                attributes
            )

        # 保存到多模态记忆
        content = {
            'character_id': character_id,
            'has_visual': results['visual'],
            'has_audio': results['audio'],
            'attributes': attributes
        }

        from memory.multimodal_memory_store import ModalityType
        self.multimodal_store.add_memory(
            content=content,
            modality=ModalityType.MULTIMODAL,
            metadata=attributes or {}
        )

        logger.info(f"[Multimodal] 添加角色配置: {character_id}")
        return results

    def generate_consistent_scene(
        self,
        character_id: str,
        description: str,
        generate_image: bool = True,
        generate_audio: bool = False,
        **kwargs
    ) -> Dict[str, Optional[bytes]]:
        """
        生成一致的场景（图像+音频）

        Args:
            character_id: 角色ID
            description: 场景描述
            generate_image: 是否生成图像
            generate_audio: 是否生成音频
            **kwargs: 其他参数

        Returns:
            生成结果
        """
        result = {}

        if generate_image:
            result['image'] = self.visual_manager.generate_consistent_image(
                character_id,
                description,
                **kwargs
            )

        if generate_audio:
            result['audio'] = self.audio_manager.generate_consistent_tts(
                description,
                character_id,
                **kwargs
            )

        # 保存到多模态记忆
        if result.get('image') or result.get('audio'):
            from memory.multimodal_memory_store import ModalityType
            self.multimodal_store.add_memory(
                content={
                    'character_id': character_id,
                    'description': description,
                    'has_image': 'image' in result,
                    'has_audio': 'audio' in result
                },
                modality=ModalityType.MULTIMODAL,
                metadata={'scene': True}
            )

        return result

    def generate_story_sequence(
        self,
        character_id: str,
        scenes: List[Dict[str, Any]]
    ) -> List[Dict[str, Optional[bytes]]]:
        """
        生成故事序列（多场景）

        Args:
            character_id: 角色ID
            scenes: 场景列表 [{'text': '...', 'visual': True, 'audio': True}]

        Returns:
            生成结果列表
        """
        results = []

        for scene in scenes:
            scene_result = {}

            if scene.get('visual'):
                scene_result['image'] = self.visual_manager.generate_consistent_image(
                    character_id,
                    scene['text']
                )

            if scene.get('audio'):
                scene_result['audio'] = self.audio_manager.generate_consistent_tts(
                    scene['text'],
                    character_id
                )

            results.append(scene_result)

        logger.info(f"[Multimodal] 生成故事序列: {character_id}, {len(scenes)}场景")
        return results

    def voice_conversion(
        self,
        source_audio: bytes,
        target_character_id: str
    ) -> Optional[bytes]:
        """
        语音转换

        Args:
            source_audio: 源音频
            target_character_id: 目标角色ID

        Returns:
            转换后的音频
        """
        return self.audio_manager.generate_consistent_vc(
            source_audio,
            target_character_id
        )

    def get_character_consistency_scores(
        self,
        character_id: str,
        test_images: Optional[List[bytes]] = None,
        test_audios: Optional[List[bytes]] = None
    ) -> Dict[str, float]:
        """
        获取角色一致性分数

        Args:
            character_id: 角色ID
            test_images: 测试图像列表
            test_audios: 测试音频列表

        Returns:
            一致性分数
        """
        scores = {}

        if test_images:
            image_scores = []
            for img in test_images:
                score = self.visual_manager.calculate_consistency_score(
                    img,  # 需要参考图像
                    img  # 简化
                )
                image_scores.append(score)
            scores['visual'] = sum(image_scores) / len(image_scores) if image_scores else 0.0

        if test_audios:
            audio_scores = []
            for aud in test_audios:
                score = self.audio_manager.calculate_consistency_score(
                    aud,
                    aud  # 简化
                )
                audio_scores.append(score)
            scores['audio'] = sum(audio_scores) / len(audio_scores) if audio_scores else 0.0

        return scores

    def search_multimodal_memories(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索多模态记忆

        Args:
            query: 查询文本
            limit: 返回数量

        Returns:
            记忆列表
        """
        from memory.multimodal_memory_store import ModalityType
        memories = self.multimodal_store.search_by_semantic(
            query,
            limit=limit
        )

        return [
            {
                'memory_id': m.memory_id,
                'modality': m.modality.value,
                'metadata': m.metadata,
                'timestamp': m.timestamp
            }
            for m in memories
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'visual': self.visual_manager.get_statistics(),
            'audio': self.audio_manager.get_statistics(),
            'multimodal': self.multimodal_store.get_statistics()
        }

    def cleanup(self):
        """清理过期数据"""
        self.visual_manager.maintain_character_library()
        self.audio_manager.maintain_speaker_library()
        self.multimodal_store.compress_old_memories()
