"""
Undefined 风格的轻量记忆系统

> 本模块整合了 Undefined 项目的记忆系统，作为弥娅手动记忆工具的后端
> 特点：简单高效、自动去重、数量控制、UUID管理
>
> 用途：
> - 手动添加的备忘录
> - 用户显式要求记录的内容
> - 与弥娅认知记忆系统互补（认知记忆用于AI自动提取）
>
> 原始来源：Undefined/src/Undefined/memory.py
"""

import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class SimpleMemory:
    """简单记忆数据结构"""
    uuid: str
    fact: str
    created_at: str
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class UndefinedMemoryAdapter:
    """Undefined 记忆系统的弥娅适配器

    特点：
    - 简单高效的 JSON 文件存储
    - 自动去重（相同内容不重复）
    - 数量限制（默认500条）
    - UUID 精确管理
    - 异步 IO 不阻塞主线程
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        max_memories: int = 500,
        filename: str = "undefined_memory.json"
    ):
        self.data_dir = data_dir or Path("data/memory")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_memories = max_memories
        self.filename = filename
        self._memories: List[SimpleMemory] = []
        self._loaded = False

    def _get_storage_path(self) -> Path:
        return self.data_dir / self.filename

    async def _load(self):
        """从文件加载记忆"""
        if self._loaded:
            return

        storage_path = self._get_storage_path()
        if storage_path.exists():
            try:
                async with aiofiles.open(storage_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                    self._memories = [SimpleMemory(**m) for m in data]
                logger.info(f"已加载 {len(self._memories)} 条记忆")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")
                self._memories = []
        else:
            self._memories = []

        self._loaded = True

    async def _save(self):
        """保存记忆到文件"""
        storage_path = self._get_storage_path()
        try:
            data = [asdict(m) for m in self._memories]
            async with aiofiles.open(storage_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            logger.debug(f"已保存 {len(self._memories)} 条记忆")
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")

    async def add(self, fact: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加记忆

        Args:
            fact: 记忆内容
            tags: 标签列表（可选）

        Returns:
            新记忆的 UUID，如果已存在则返回已有 UUID
        """
        await self._load()

        # 去重
        for m in self._memories:
            if m.fact == fact:
                logger.debug(f"记忆已存在，跳过添加: {fact[:50]}...")
                return m.uuid

        # 添加新记忆
        memory = SimpleMemory(
            uuid=str(uuid.uuid4()),
            fact=fact,
            created_at=datetime.now().isoformat(),
            tags=tags or []
        )
        self._memories.append(memory)

        # 数量限制：删除最早的
        if len(self._memories) > self.max_memories:
            removed = self._memories.pop(0)
            logger.info(f"记忆达到上限，删除最早记录: {removed.uuid}")

        await self._save()
        logger.info(f"已添加新记忆: {memory.uuid}")
        return memory.uuid

    async def update(self, uuid: str, fact: Optional[str] = None, tags: Optional[List[str]] = None) -> bool:
        """更新记忆

        Args:
            uuid: 记忆 UUID
            fact: 新的内容（可选）
            tags: 新的标签（可选）

        Returns:
            是否更新成功
        """
        await self._load()

        for m in self._memories:
            if m.uuid == uuid:
                if fact is not None:
                    m.fact = fact
                if tags is not None:
                    m.tags = tags
                await self._save()
                logger.info(f"已更新记忆: {uuid}")
                return True

        logger.warning(f"未找到记忆: {uuid}")
        return False

    async def delete(self, uuid: str) -> bool:
        """删除记忆

        Args:
            uuid: 记忆 UUID

        Returns:
            是否删除成功
        """
        await self._load()

        for i, m in enumerate(self._memories):
            if m.uuid == uuid:
                self._memories.pop(i)
                await self._save()
                logger.info(f"已删除记忆: {uuid}")
                return True

        logger.warning(f"未找到记忆: {uuid}")
        return False

    async def get_all(self, limit: Optional[int] = None) -> List[SimpleMemory]:
        """获取所有记忆（按时间排序）

        Args:
            limit: 最大返回数量（可选）

        Returns:
            记忆列表
        """
        await self._load()

        memories = sorted(self._memories, key=lambda m: m.created_at, reverse=True)
        if limit:
            memories = memories[:limit]

        return memories

    async def get_by_uuid(self, uuid: str) -> Optional[SimpleMemory]:
        """根据 UUID 获取记忆

        Args:
            uuid: 记忆 UUID

        Returns:
            记忆对象，不存在则返回 None
        """
        await self._load()

        for m in self._memories:
            if m.uuid == uuid:
                return m

        return None

    async def search(self, keyword: str, limit: Optional[int] = None) -> List[SimpleMemory]:
        """搜索记忆（简单关键词匹配）

        Args:
            keyword: 搜索关键词
            limit: 最大返回数量（可选）

        Returns:
            匹配的记忆列表
        """
        await self._load()

        results = [m for m in self._memories if keyword.lower() in m.fact.lower()]
        results = sorted(results, key=lambda m: m.created_at, reverse=True)

        if limit:
            results = results[:limit]

        return results

    async def get_by_tag(self, tag: str, limit: Optional[int] = None) -> List[SimpleMemory]:
        """根据标签获取记忆

        Args:
            tag: 标签
            limit: 最大返回数量（可选）

        Returns:
            包含该标签的记忆列表
        """
        await self._load()

        results = [m for m in self._memories if tag in m.tags]
        results = sorted(results, key=lambda m: m.created_at, reverse=True)

        if limit:
            results = results[:limit]

        return results

    def count(self) -> int:
        """获取记忆数量"""
        return len(self._memories)

    async def clear(self):
        """清空所有记忆"""
        await self._load()
        self._memories.clear()
        await self._save()
        logger.info("已清空所有记忆")


# 全局适配器实例（单例）
_global_adapter: Optional[UndefinedMemoryAdapter] = None


def get_undefined_memory_adapter() -> UndefinedMemoryAdapter:
    """获取全局适配器实例（单例）"""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = UndefinedMemoryAdapter()
    return _global_adapter
