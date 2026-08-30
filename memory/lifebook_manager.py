"""
LifeBook 管理器 — 兼容 LifeNet API，委托给真正的 LifeBook + MiyaMemoryCore

@description: 桥接层：LifeNet (webnet/life.py) → memory/lifebook.LifeBook + MiyaMemoryCore
@since: v8.1 — 修复了空壳引用问题
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryLevel(Enum):
    """记忆层级"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    DIALOGUE = "dialogue"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class NodeType(Enum):
    """节点类型"""

    CHARACTER = "character"
    STAGE = "stage"
    CHAPTER = "chapter"


@dataclass
class Entry:
    entry_id: str
    level: MemoryLevel
    title: str
    content: str
    created_at: str = ""
    tags: Optional[List[str]] = None
    mood: Optional[str] = None
    capsule: Optional[str] = None
    metadata: Optional[Dict] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.tags is None:
            self.tags = []


@dataclass
class Node:
    node_id: str
    node_type: NodeType
    name: str
    description: str = ""
    tags: Optional[List[str]] = None
    created_at: str = ""
    related_nodes: Optional[List[str]] = None
    metadata: Optional[Dict] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.tags is None:
            self.tags = []
        if self.related_nodes is None:
            self.related_nodes = []


class LifeBookManager:
    """LifeBook 管理器 — 委托给 memory/lifebook.LifeBook + MiyaMemoryCore"""

    def __init__(self, base_dir: str = "data/lifebook", ai_client=None):
        self.data_dir = base_dir
        self.ai_client = ai_client
        self._nodes: Dict[str, Node] = {}
        self._entries: Dict[str, Entry] = {}

        self._nodes_file = Path(self.data_dir) / "nodes.json"
        self._entries_file = Path(self.data_dir) / "entries.json"
        self._ensure_data_dir()
        self._load_persisted()

    def _ensure_data_dir(self):
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    def _load_persisted(self):
        if self._nodes_file.exists():
            try:
                with open(self._nodes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, nd in data.items():
                        self._nodes[name] = Node(
                            node_id=nd.get("node_id", name),
                            node_type=NodeType(nd["node_type"]),
                            name=name,
                            description=nd.get("description", ""),
                            tags=nd.get("tags", []),
                            created_at=nd.get("created_at", ""),
                            related_nodes=nd.get("related_nodes", []),
                        )
            except Exception as e:
                logger.warning(f"[LifeBookManager] 节点加载失败: {e}")

        if self._entries_file.exists():
            try:
                with open(self._entries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for eid, ed in data.items():
                        self._entries[eid] = Entry(
                            entry_id=ed.get("entry_id", eid),
                            level=MemoryLevel(ed.get("level", "daily")),
                            title=ed.get("title", ""),
                            content=ed.get("content", ""),
                            created_at=ed.get("created_at", ""),
                            tags=ed.get("tags", []),
                            mood=ed.get("mood"),
                            capsule=ed.get("capsule"),
                            metadata=ed.get("metadata"),
                        )
            except Exception as e:
                logger.warning(f"[LifeBookManager] 条目加载失败: {e}")

    def _save_nodes(self):
        try:
            data = {}
            for name, node in self._nodes.items():
                data[name] = {
                    "node_id": node.node_id,
                    "node_type": node.node_type.value,
                    "name": name,
                    "description": node.description,
                    "tags": node.tags,
                    "created_at": node.created_at,
                    "related_nodes": node.related_nodes,
                }
            with open(self._nodes_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LifeBookManager] 节点保存失败: {e}")

    def _save_entries(self):
        try:
            data = {}
            for eid, entry in self._entries.items():
                data[eid] = {
                    "entry_id": entry.entry_id,
                    "level": entry.level.value,
                    "title": entry.title,
                    "content": entry.content,
                    "created_at": entry.created_at,
                    "tags": entry.tags,
                    "mood": entry.mood,
                    "capsule": entry.capsule,
                    "metadata": entry.metadata,
                }
            with open(self._entries_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LifeBookManager] 条目保存失败: {e}")

    def _get_real_lifebook(self):
        """延迟获取真正的 LifeBook 实例"""
        try:
            from memory.lifebook import get_lifebook

            return get_lifebook()
        except Exception as e:
            logger.debug(f"[LifeBookManager] 真身LifeBook获取失败: {e}")
            return None

    async def initialize(self):
        pass

    # ==================== 条目操作 ====================

    def add_entry(
        self,
        level: MemoryLevel,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        mood: Optional[str] = None,
        capsule: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Entry:
        """添加条目"""
        import uuid

        entry_id = uuid.uuid4().hex[:12]
        entry = Entry(
            entry_id=entry_id,
            level=level,
            title=title,
            content=content,
            tags=tags or [],
            mood=mood,
            capsule=capsule,
            metadata=metadata,
        )
        self._entries[entry_id] = entry
        self._save_entries()

        # 同步写入真实 LifeBook（Markdown 日记）
        real = self._get_real_lifebook()
        if real:
            try:
                import asyncio

                if level == MemoryLevel.DAILY:
                    asyncio.ensure_future(
                        real.record_lover_thought(
                            thought=f"{title}\n{content}",
                            context=mood or "日记记录",
                        )
                    )
            except Exception as e:
                logger.debug(f"[LifeBookManager] 同步到真身LifeBook失败: {e}")

        logger.info(f"[LifeBookManager] 添加条目: {entry_id} ({level.value})")
        return entry

    def get_entry(self, level: MemoryLevel, period: str) -> Optional[Entry]:
        """获取指定层级和周期的条目"""
        for entry in self._entries.values():
            if entry.level == level:
                if period in entry.title or period in entry.created_at:
                    return entry
                if entry.entry_id.startswith(period):
                    return entry
        return None

    def search_entries(
        self,
        keyword: str,
        level: Optional[MemoryLevel] = None,
        limit: int = 10,
    ) -> List[Entry]:
        """搜索条目"""
        results = []
        keyword_lower = keyword.lower()
        for entry in self._entries.values():
            if level and entry.level != level:
                continue
            if (
                keyword_lower in entry.title.lower()
                or keyword_lower in entry.content.lower()
                or any(keyword_lower in t.lower() for t in entry.tags)
            ):
                results.append(entry)

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    # ==================== 节点操作 ====================

    async def create_node(
        self,
        name: str,
        node_type: str,
        tags: Optional[List[str]] = None,
        description: str = "",
        **kwargs,
    ) -> Node:
        """创建节点，同时持久化到 MiyaMemoryCore"""
        if isinstance(node_type, str):
            node_type = NodeType(node_type)

        import uuid

        node_id = uuid.uuid4().hex[:12]
        node = Node(
            node_id=node_id,
            node_type=node_type,
            name=name,
            description=description,
            tags=tags or [],
        )
        self._nodes[name] = node
        self._save_nodes()

        try:
            from memory import store_important

            await store_important(
                content=f"LifeBook节点 — [{node_type.value}] {name}: {description}",
                user_id="global",
                tags=["lifebook_node", node_type.value, name],
                priority=0.7,
            )
        except Exception as e:
            logger.debug(f"[LifeBookManager] 节点写入MiyaMemoryCore失败: {e}")

        logger.info(f"[LifeBookManager] 创建节点: {name} ({node_type.value})")
        return node

    def create_node_sync(
        self,
        name: str,
        node_type: str,
        tags: Optional[List[str]] = None,
        description: str = "",
        **kwargs,
    ) -> Node:
        """创建节点（同步版，内部处理事件循环）"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                future = asyncio.run_coroutine_threadsafe(
                    self.create_node(name, node_type, tags, description, **kwargs),
                    loop,
                )
                return future.result(timeout=10)
            return loop.run_until_complete(self.create_node(name, node_type, tags, description, **kwargs))
        except RuntimeError:
            return asyncio.run(self.create_node(name, node_type, tags, description, **kwargs))

    async def get_node(self, name: str) -> Optional[Node]:
        """获取节点"""
        return self._nodes.get(name)

    async def list_nodes(self, node_type: Optional[NodeType] = None) -> List[Node]:
        """列出节点"""
        if node_type:
            return [n for n in self._nodes.values() if n.node_type == node_type]
        return list(self._nodes.values())

    @property
    def _nodes_dict(self):
        """兼容旧代码访问 _nodes"""
        return self._nodes

    # ==================== 记忆 + 上下文 ====================

    async def add_memory(self, content: str, user_id: str, **kwargs) -> str:
        from memory import store_important

        return await store_important(content, user_id, tags=["lifebook"])

    async def get_memories(self, user_id: str, **kwargs) -> List[Dict]:
        from memory import get_user_memories

        mems = await get_user_memories(user_id)
        return [{"content": m.content, "tags": m.tags} for m in mems]

    async def get_core_context(self, months_back: int = 1, include_nodes: bool = True) -> str:
        """一键获取记忆上下文"""
        try:
            from datetime import datetime, timedelta

            from memory import search_memory

            cutoff = datetime.now() - timedelta(days=months_back * 30)
            lines = []

            lines.append(f"## LifeBook 记忆上下文 (回溯 {months_back} 个月)\n")

            recent_entries = [e for e in self._entries.values() if e.created_at > cutoff.isoformat()]
            recent_entries.sort(key=lambda e: e.created_at, reverse=True)
            if recent_entries:
                lines.append("### 最近记录\n")
                for entry in recent_entries[:10]:
                    lines.append(f"- [{entry.level.value}] {entry.title}")
                    lines.append(f"  {entry.content[:100]}...")
                lines.append("")

            if include_nodes:
                characters = [n for n in self._nodes.values() if n.node_type == NodeType.CHARACTER]
                stages = [n for n in self._nodes.values() if n.node_type == NodeType.STAGE]
                if characters or stages:
                    lines.append("### 重要节点\n")
                    for node in characters + stages:
                        type_name = "角色" if node.node_type == NodeType.CHARACTER else "阶段"
                        lines.append(f"- [{type_name}] {node.name}: {node.description[:80]}")
                    lines.append("")

            try:
                core_memories = await search_memory(
                    query="",
                    tags=(["lifebook", "重要"]),
                    limit=5,
                )
                if core_memories:
                    lines.append("### 核心记忆\n")
                    for m in core_memories:
                        lines.append(f"- {m.content[:120]}...")
                    lines.append("")
            except Exception:
                pass

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[LifeBookManager] 获取记忆上下文失败: {e}")
            return f"获取失败: {str(e)}"


def get_lifebook_manager() -> LifeBookManager:
    return LifeBookManager()


__all__ = [
    "LifeBookManager",
    "MemoryLevel",
    "NodeType",
    "Node",
    "Entry",
    "get_lifebook_manager",
]
