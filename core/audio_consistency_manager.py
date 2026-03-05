"""
音频一致性管理器
基于Amphion和Bark原理，维持语音音色和风格一致性
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


class AudioConsistencyLevel(Enum):
    """音频一致性级别"""
    LOW = 0.3      # 低一致性（仅基本音色）
    MEDIUM = 0.6    # 中等一致性（主要音色特征）
    HIGH = 0.8       # 高一致性（所有音色特征）
    ULTRA = 1.0      # 超高一致性（完全一致）


@dataclass
class SpeakerReference:
    """说话人参考"""
    speaker_id: str
    audio_samples: List[bytes] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class AudioConsistencyManager:
    """音频一致性管理器"""

    def __init__(self, storage_path: str = "data/audio_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # 说话人参考库
        self.speaker_references: Dict[str, SpeakerReference] = {}

        # 默认一致性级别
        self.default_consistency_level = AudioConsistencyLevel.HIGH

        # 音频特征缓存
        self.feature_cache: Dict[str, List[float]] = {}

    def add_speaker_reference(
        self,
        speaker_id: str,
        audio_sample: bytes,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加说话人参考音频

        Args:
            speaker_id: 说话人ID
            audio_sample: 参考音频
            attributes: 说话人属性（音调、语速、情感等）

        Returns:
            是否成功
        """
        try:
            if speaker_id not in self.speaker_references:
                self.speaker_references[speaker_id] = SpeakerReference(
                    speaker_id=speaker_id
                )

            ref = self.speaker_references[speaker_id]
            ref.audio_samples.append(audio_sample)
            ref.updated_at = time.time()

            if attributes:
                ref.attributes.update(attributes)

            # 提取嵌入（简化版）
            embedding = self._extract_embedding_mock(audio_sample)
            if ref.embedding is None:
                ref.embedding = embedding
            else:
                # 平均嵌入
                ref.embedding = [
                    (e + embedding[i]) / 2
                    for i, e in enumerate(ref.embedding)
                ]

            # 保存到磁盘
            self._save_reference(speaker_id, ref)

            logger.info(f"[Audio] 添加说话人参考: {speaker_id}")
            return True

        except Exception as e:
            logger.error(f"[Audio] 添加说话人参考失败: {e}")
            return False

    def generate_consistent_tts(
        self,
        text: str,
        speaker_id: str,
        consistency_level: Optional[AudioConsistencyLevel] = None,
        emotion: Optional[str] = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        生成一致的文本转语音

        Args:
            text: 待合成文本
            speaker_id: 说话人ID
            consistency_level: 一致性级别
            emotion: 情感（happy, sad, angry等）
            **kwargs: 其他参数

        Returns:
            生成的音频（bytes）
        """
        if speaker_id not in self.speaker_references:
            logger.warning(f"[Audio] 说话人参考不存在: {speaker_id}")
            return None

        ref = self.speaker_references[speaker_id]
        level = consistency_level or self.default_consistency_level

        # 获取说话人嵌入
        embedding = ref.embedding

        # 应用情感（如果指定）
        emotion_attributes = ref.attributes.get('emotions', {})
        if emotion and emotion in emotion_attributes:
            embedding = self._apply_emotion(
                embedding,
                emotion_attributes[emotion]
            )

        # 注意：这里需要实际的TTS模型（如Amphion、Bark等）
        # 当前返回模拟结果
        logger.info(f"[Audio] 生成TTS: {speaker_id}, 情感: {emotion}, 级别: {level.value}")
        return self._generate_tts_mock(text, embedding, **kwargs)

    def generate_consistent_vc(
        self,
        source_audio: bytes,
        target_speaker_id: str,
        consistency_level: Optional[AudioConsistencyLevel] = None
    ) -> Optional[bytes]:
        """
        生成一致的语音转换

        Args:
            source_audio: 源音频
            target_speaker_id: 目标说话人ID
            consistency_level: 一致性级别

        Returns:
            转换后的音频（bytes）
        """
        if target_speaker_id not in self.speaker_references:
            logger.warning(f"[Audio] 说话人参考不存在: {target_speaker_id}")
            return None

        ref = self.speaker_references[target_speaker_id]
        level = consistency_level or self.default_consistency_level

        # 获取目标嵌入
        target_embedding = ref.embedding

        # 注意：这里需要实际的VC模型
        # 当前返回模拟结果
        logger.info(f"[Audio] 生成VC: {target_speaker_id}, 级别: {level.value}")
        return self._generate_vc_mock(source_audio, target_embedding)

    def generate_audio_sequence(
        self,
        speaker_id: str,
        texts: List[str],
        consistency_level: Optional[AudioConsistencyLevel] = None
    ) -> List[Optional[bytes]]:
        """
        生成音频序列（用于长文本配音）

        Args:
            speaker_id: 说话人ID
            texts: 文本列表
            consistency_level: 一致性级别

        Returns:
            音频序列
        """
        if speaker_id not in self.speaker_references:
            return [None] * len(texts)

        audio_sequence = []
        for text in texts:
            audio = self.generate_consistent_tts(
                text, speaker_id, consistency_level
            )
            audio_sequence.append(audio)

        logger.info(f"[Audio] 生成序列: {speaker_id}, {len(texts)}段")
        return audio_sequence

    def calculate_consistency_score(
        self,
        audio1: bytes,
        audio2: bytes
    ) -> float:
        """
        计算两段音频的一致性分数

        Args:
            audio1: 音频1
            audio2: 音频2

        Returns:
            一致性分数（0-1）
        """
        # 简化实现：比较音频哈希和长度
        hash1 = hashlib.md5(audio1).hexdigest()
        hash2 = hashlib.md5(audio2).hexdigest()

        # 计算汉明距离
        hamming = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        max_hamming = len(hash1) * 4

        hash_score = 1.0 - (hamming / max_hamming)

        # 考虑长度差异
        length_diff = abs(len(audio1) - len(audio2))
        max_length = max(len(audio1), len(audio2))
        length_score = 1.0 - (length_diff / max_length) if max_length > 0 else 1.0

        # 综合分数
        consistency = (hash_score * 0.5 + length_score * 0.5)
        return round(consistency, 3)

    def extract_speaker_embedding(
        self,
        audio_sample: bytes
    ) -> Optional[List[float]]:
        """
        提取说话人嵌入

        Args:
            audio_sample: 音频样本

        Returns:
            嵌入向量
        """
        return self._extract_embedding_mock(audio_sample)

    def maintain_speaker_library(self):
        """维护说话人库（清理过期引用）"""
        current_time = time.time()
        expiry_days = 30

        to_remove = []
        for speaker_id, ref in self.speaker_references.items():
            if (current_time - ref.updated_at) > expiry_days * 86400:
                to_remove.append(speaker_id)

        for speaker_id in to_remove:
            del self.speaker_references[speaker_id]
            logger.info(f"[Audio] 清理过期说话人: {speaker_id}")

    def _extract_embedding_mock(self, audio: bytes) -> List[float]:
        """模拟嵌入提取（实际需要Amphion等模型）"""
        # 返回一个虚拟嵌入（128维）
        import random
        random.seed(hash(audio))
        return [random.random() for _ in range(128)]

    def _apply_emotion(
        self,
        embedding: List[float],
        emotion_params: Dict[str, float]
    ) -> List[float]:
        """应用情感参数"""
        if not emotion_params:
            return embedding

        # 简化实现：根据情感参数调整嵌入
        adjusted = embedding.copy()

        if 'pitch_shift' in emotion_params:
            shift = emotion_params['pitch_shift']
            adjusted = [v + shift for v in adjusted]

        if 'speed_factor' in emotion_params:
            factor = emotion_params['speed_factor']
            adjusted = [v * factor for v in adjusted]

        return adjusted

    def _generate_tts_mock(self, text: str, embedding: List[float], **kwargs) -> bytes:
        """模拟TTS生成（实际需要Amphion、Bark等模型）"""
        mock_data = f"MOCK_TTS: {text}".encode()
        return mock_data

    def _generate_vc_mock(self, source_audio: bytes, target_embedding: List[float]) -> bytes:
        """模拟VC生成（实际需要VC模型）"""
        mock_data = f"MOCK_VC: len={len(source_audio)}".encode()
        return mock_data

    def _save_reference(self, ref_id: str, ref: SpeakerReference):
        """保存参考到磁盘"""
        directory = self.storage_path / "speakers"
        directory.mkdir(exist_ok=True)

        filepath = directory / f"{ref_id}.json"

        data = {
            'speaker_id': ref.speaker_id,
            'audio_hashes': [
                hashlib.md5(audio).hexdigest()
                for audio in ref.audio_samples
            ],
            'attributes': ref.attributes,
            'created_at': ref.created_at,
            'updated_at': ref.updated_at
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_reference(self, ref_id: str) -> bool:
        """从磁盘加载参考"""
        directory = self.storage_path / "speakers"
        filepath = directory / f"{ref_id}.json"

        if not filepath.exists():
            return False

        try:
            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            ref = SpeakerReference(
                speaker_id=data['speaker_id'],
                attributes=data.get('attributes', {}),
                created_at=data.get('created_at', time.time()),
                updated_at=data.get('updated_at', time.time())
            )

            self.speaker_references[ref_id] = ref
            return True

        except Exception as e:
            logger.error(f"[Audio] 加载参考失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_speakers': len(self.speaker_references),
            'total_samples': sum(
                len(ref.audio_samples)
                for ref in self.speaker_references.values()
            )
        }
