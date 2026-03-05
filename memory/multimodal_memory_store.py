"""
多模态记忆存储
整合文本、图像、音频等多种模态的记忆管理
"""
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


class ModalityType(Enum):
    """模态类型"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    MULTIMODAL = "multimodal"


@dataclass
class MultiModalMemory:
    """多模态记忆"""
    memory_id: str
    modality: ModalityType
    content: Union[str, bytes, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    embedding: Optional[List[float]] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class MultiModalMemoryStore:
    """多模态记忆存储"""

    def __init__(self, storage_path: str = "data/multimodal_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # 内存存储
        self.memories: Dict[str, MultiModalMemory] = {}

        # 模态索引
        self.modality_index: Dict[ModalityType, List[str]] = {
            ModalityType.TEXT: [],
            ModalityType.IMAGE: [],
            ModalityType.AUDIO: [],
            ModalityType.VIDEO: [],
            ModalityType.MULTIMODAL: []
        }

        # 时间索引
        self.time_index: List[Tuple[float, str]] = []

        # 语义索引（简化版）
        self.semantic_index: Dict[str, List[str]] = {}

        # 向量化器（简化版）
        self.embedding_cache: Dict[str, List[float]] = {}

    def add_memory(
        self,
        content: Union[str, bytes, Dict[str, Any]],
        modality: ModalityType = ModalityType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None
    ) -> Optional[str]:
        """
        添加多模态记忆

        Args:
            content: 内容（文本/图像/音频/多模态）
            modality: 模态类型
            metadata: 元数据
            memory_id: 记忆ID（可选，自动生成）

        Returns:
            记忆ID
        """
        try:
            # 生成记忆ID
            if memory_id is None:
                memory_id = self._generate_memory_id(modality)

            # 生成嵌入
            embedding = self._compute_embedding(content, modality)

            # 创建记忆
            memory = MultiModalMemory(
                memory_id=memory_id,
                modality=modality,
                content=self._serialize_content(content, modality),
                metadata=metadata or {},
                timestamp=time.time(),
                embedding=embedding
            )

            # 添加到存储
            self.memories[memory_id] = memory

            # 更新索引
            self.modality_index[modality].append(memory_id)
            self.time_index.append((memory.timestamp, memory_id))

            # 更新语义索引
            if metadata and 'tags' in metadata:
                for tag in metadata['tags']:
                    if tag not in self.semantic_index:
                        self.semantic_index[tag] = []
                    self.semantic_index[tag].append(memory_id)

            # 保存到磁盘
            self._save_memory(memory)

            logger.info(f"[MultiModal] 添加记忆: {memory_id}, 模态: {modality.value}")
            return memory_id

        except Exception as e:
            logger.error(f"[MultiModal] 添加记忆失败: {e}")
            return None

    def get_memory(self, memory_id: str) -> Optional[MultiModalMemory]:
        """
        获取记忆

        Args:
            memory_id: 记忆ID

        Returns:
            记忆对象
        """
        if memory_id not in self.memories:
            return None

        memory = self.memories[memory_id]
        memory.access_count += 1
        memory.last_accessed = time.time()

        return memory

    def search_by_modality(
        self,
        modality: ModalityType,
        limit: int = 10,
        offset: int = 0
    ) -> List[MultiModalMemory]:
        """
        按模态搜索

        Args:
            modality: 模态类型
            limit: 返回数量
            offset: 偏移量

        Returns:
            记忆列表
        """
        memory_ids = self.modality_index.get(modality, [])
        selected_ids = memory_ids[offset:offset + limit]

        return [
            self.memories[mid]
            for mid in selected_ids
            if mid in self.memories
        ]

    def search_by_time_range(
        self,
        start_time: float,
        end_time: float,
        modality: Optional[ModalityType] = None
    ) -> List[MultiModalMemory]:
        """
        按时间范围搜索

        Args:
            start_time: 开始时间
            end_time: 结束时间
            modality: 模态类型（可选）

        Returns:
            记忆列表
        """
        results = []

        for timestamp, memory_id in self.time_index:
            if start_time <= timestamp <= end_time:
                if memory_id in self.memories:
                    memory = self.memories[memory_id]

                    if modality is None or memory.modality == modality:
                        results.append(memory)

        # 按时间排序
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results

    def search_by_semantic(
        self,
        query: str,
        modality: Optional[ModalityType] = None,
        limit: int = 10
    ) -> List[MultiModalMemory]:
        """
        语义搜索

        Args:
            query: 查询文本
            modality: 模态类型（可选）
            limit: 返回数量

        Returns:
            记忆列表
        """
        # 计算查询嵌入
        query_embedding = self._compute_text_embedding(query)

        # 计算相似度
        scored_memories = []

        for memory_id, memory in self.memories.items():
            if modality and memory.modality != modality:
                continue

            if memory.embedding:
                similarity = self._cosine_similarity(
                    query_embedding,
                    memory.embedding
                )
                scored_memories.append((similarity, memory))

        # 按相似度排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 返回top-k
        return [memory for _, memory in scored_memories[:limit]]

    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆ID

        Returns:
            是否成功
        """
        if memory_id not in self.memories:
            return False

        memory = self.memories[memory_id]

        # 从索引中移除
        self.modality_index[memory.modality].remove(memory_id)
        self.time_index = [
            (t, mid) for t, mid in self.time_index
            if mid != memory_id
        ]

        # 从语义索引中移除
        if 'tags' in memory.metadata:
            for tag in memory.metadata['tags']:
                if tag in self.semantic_index:
                    self.semantic_index[tag] = [
                        mid for mid in self.semantic_index[tag]
                        if mid != memory_id
                    ]

        # 删除磁盘文件
        self._delete_memory_file(memory_id)

        # 从内存中移除
        del self.memories[memory_id]

        logger.info(f"[MultiModal] 删除记忆: {memory_id}")
        return True

    def get_multimodal_sequence(
        self,
        base_id: str,
        modality_sequence: List[ModalityType]
    ) -> Dict[ModalityType, Optional[MultiModalMemory]]:
        """
        获取多模态序列（用于相关联的不同模态记忆）

        Args:
            base_id: 基础记忆ID
            modality_sequence: 模态序列

        Returns:
            模态到记忆的映射
        """
        result = {}

        base_memory = self.get_memory(base_id)
        if not base_memory:
            return result

        # 查找相关记忆（基于时间窗口）
        time_window = 3600  # 1小时
        start_time = base_memory.timestamp - time_window
        end_time = base_memory.timestamp + time_window

        related = self.search_by_time_range(start_time, end_time)

        # 按模态分组
        for memory in related:
            if memory.modality in modality_sequence and memory.memory_id != base_id:
                if memory.modality not in result:
                    result[memory.modality] = memory

        return result

    def compress_old_memories(self, days_threshold: int = 30) -> int:
        """
        压缩旧记忆

        Args:
            days_threshold: 天数阈值

        Returns:
            压缩的记忆数量
        """
        current_time = time.time()
        threshold = current_time - days_threshold * 86400

        to_compress = []
        for memory_id, memory in self.memories.items():
            if (current_time - memory.timestamp) > threshold:
                to_compress.append(memory_id)

        for memory_id in to_compress:
            # 保留文本，压缩图像/音频
            memory = self.memories[memory_id]
            if memory.modality in [ModalityType.IMAGE, ModalityType.AUDIO]:
                # 压缩为低质量版本（模拟）
                self._compress_memory_content(memory)

        logger.info(f"[MultiModal] 压缩旧记忆: {len(to_compress)}个")
        return len(to_compress)

    def _generate_memory_id(self, modality: ModalityType) -> str:
        """生成记忆ID"""
        import uuid
        return f"{modality.value}_{uuid.uuid4().hex[:16]}"

    def _compute_embedding(
        self,
        content: Union[str, bytes, Dict[str, Any]],
        modality: ModalityType
    ) -> Optional[List[float]]:
        """计算嵌入"""
        if modality == ModalityType.TEXT:
            return self._compute_text_embedding(content)
        elif modality == ModalityType.IMAGE:
            return self._compute_image_embedding(content)
        elif modality == ModalityType.AUDIO:
            return self._compute_audio_embedding(content)
        else:
            return None

    def _compute_text_embedding(self, text: str) -> List[float]:
        """计算文本嵌入（简化版）"""
        # 简化实现：使用字符统计
        import hashlib
        hash_digest = hashlib.md5(text.encode()).hexdigest()
        return [float(int(c, 16)) / 255.0 for c in hash_digest]

    def _compute_image_embedding(self, image: bytes) -> List[float]:
        """计算图像嵌入（简化版）"""
        import hashlib
        hash_digest = hashlib.md5(image).hexdigest()
        return [float(int(c, 16)) / 255.0 for c in hash_digest]

    def _compute_audio_embedding(self, audio: bytes) -> List[float]:
        """计算音频嵌入（简化版）"""
        import hashlib
        hash_digest = hashlib.md5(audio).hexdigest()
        return [float(int(c, 16)) / 255.0 for c in hash_digest]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _serialize_content(
        self,
        content: Union[str, bytes, Dict[str, Any]],
        modality: ModalityType
    ) -> Union[str, bytes, Dict[str, Any]]:
        """序列化内容"""
        if modality in [ModalityType.IMAGE, ModalityType.AUDIO]:
            if isinstance(content, str):
                # Base64编码的字符串
                return content
            else:
                # 转为Base64
                return base64.b64encode(content).decode()
        elif modality == ModalityType.MULTIMODAL:
            return content if isinstance(content, dict) else {}
        else:
            return content

    def _compress_memory_content(self, memory: MultiModalMemory):
        """压缩记忆内容（简化版）"""
        if isinstance(memory.content, str) and len(memory.content) > 1000:
            # 截断
            memory.content = memory.content[:1000]
            memory.metadata['compressed'] = True

    def _save_memory(self, memory: MultiModalMemory):
        """保存记忆到磁盘"""
        directory = self.storage_path / memory.modality.value
        directory.mkdir(exist_ok=True)

        filepath = directory / f"{memory.memory_id}.json"

        data = {
            'memory_id': memory.memory_id,
            'modality': memory.modality.value,
            'content': str(memory.content)[:1000] if isinstance(memory.content, str) else 'binary',
            'metadata': memory.metadata,
            'timestamp': memory.timestamp,
            'access_count': memory.access_count,
            'last_accessed': memory.last_accessed
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _delete_memory_file(self, memory_id: str):
        """删除磁盘文件"""
        for modality in self.storage_path.iterdir():
            if modality.is_dir():
                filepath = modality / f"{memory_id}.json"
                if filepath.exists():
                    filepath.unlink()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_memories': len(self.memories),
            'by_modality': {
                modality.value: len(self.modality_index[modality])
                for modality in ModalityType
            },
            'total_accesses': sum(
                m.access_count for m in self.memories.values()
            )
        }
