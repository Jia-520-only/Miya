"""
弥娅记忆总线 (MemoryBus) V4.0 — 系统唯一记忆入口
================================================

设计原则:
1. *强制* 单点接入 — 所有模块只能通过 MemoryBus 操作记忆
2. 完整服务层 — 存储/检索/注入/认知/技能/维护 全部内聚
3. 智能路由 — 自动选择最优存储/检索策略
4. 异步非阻塞 — 不阻塞主响应路径
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from memory.models import MemoryItem, MemoryLevel, MemoryPriority, MemoryQuery, MemorySource

logger = logging.getLogger("Miya.MemoryBus")

DEFAULT_DATA_DIR = "data/memory"


# ==================== 请求/响应数据类 ====================


@dataclass
class RecallRequest:
    """统一检索请求"""

    query: str = ""
    user_id: str = ""
    group_id: str = ""
    session_id: str = ""
    platform: str = "unknown"
    tags: Optional[List[str]] = None
    level: Optional[MemoryLevel] = None
    levels: Optional[List[MemoryLevel]] = None
    min_priority: float = 0.0
    limit: int = 20
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    conversation_history: List[Dict] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecallResult:
    """统一检索结果"""

    memories: List[MemoryItem] = field(default_factory=list)
    context_text: str = ""
    total_found: int = 0
    query_time_ms: float = 0.0


# ==================== MemoryBus V4.0 ====================


class MemoryBus:
    """
    弥娅记忆总线 V4.0

    完整的记忆服务体系，所有记忆操作必须通过此总线。

    用法:
        bus = await MemoryBus.instance()
        await bus.store_dialogue("你好", role="user", user_id="123")
        result = await bus.recall("偏好", user_id="123")
    """

    _instance: Optional[MemoryBus] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._core = None
        self._cognitive_engine = None
        self._injection_pipeline = None
        self._working_memory = None
        self._historian = None
        self._enhancer = None
        self._skill_manager = None
        self._initialized = False
        self._heartbeat_task = None
        self._data_dir: Path = Path(DEFAULT_DATA_DIR)

    # ==================== 单例 ====================

    @classmethod
    async def instance(cls, data_dir: Optional[Union[str, Path]] = None) -> MemoryBus:
        """获取全局 MemoryBus 单例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    bus = cls()
                    if data_dir:
                        bus._data_dir = Path(data_dir)
                    await bus._initialize()
                    cls._instance = bus
        return cls._instance

    @classmethod
    def reset(cls):
        """重置单例 (测试用)"""
        if cls._instance:
            asyncio.ensure_future(cls._instance.stop_heartbeat())
        cls._instance = None

    # ==================== 初始化 ====================

    async def _initialize(self):
        """初始化所有子系统"""
        if self._initialized:
            return

        logger.info("[MemoryBus] 初始化记忆服务体系...")

        from memory.core import get_memory_core
        from memory.cognitive_engine import get_cognitive_engine
        from memory.injection_pipeline import get_injection_pipeline
        from memory.default_hooks import register_default_hooks
        from memory.working_memory import WorkingMemoryManager

        self._core = await get_memory_core(data_dir=str(self._data_dir))
        self._cognitive_engine = get_cognitive_engine()
        self._injection_pipeline = register_default_hooks()
        self._working_memory = WorkingMemoryManager()
        self._initialized = True

        logger.info("[MemoryBus] 记忆服务就绪")

    async def _ensure_init(self):
        if not self._initialized:
            await self._initialize()

    async def _ensure_core(self):
        await self._ensure_init()
        return self._core

    # ==================== 存储 API ====================

    async def store(
        self,
        content: str,
        user_id: str = "global",
        level: Optional[MemoryLevel] = None,
        priority: float = 0.5,
        tags: Optional[List[str]] = None,
        session_id: str = "",
        group_id: str = "",
        platform: str = "unknown",
        source: MemorySource = MemorySource.SYSTEM,
        role: str = "",
        event_type: str = "",
        location: str = "",
        conversation_partner: str = "",
        emotional_tone: str = "",
        significance: float = 0.5,
        ttl: Optional[int] = None,
        metadata: Optional[Dict] = None,
        subject: str = "",
        predicate: str = "",
        obj: str = "",
    ) -> str:
        """通用存储 — 自动分类 + JSON/SQLite 双写"""
        core = await self._ensure_core()
        return await core.store(
            content=content,
            level=level,
            priority=priority,
            tags=tags,
            user_id=user_id,
            session_id=session_id,
            group_id=group_id,
            platform=platform,
            source=source,
            role=role,
            event_type=event_type,
            location=location,
            conversation_partner=conversation_partner,
            emotional_tone=emotional_tone,
            significance=significance,
            ttl=ttl,
            metadata=metadata,
            subject=subject,
            predicate=predicate,
            obj=obj,
        )

    async def store_dialogue(
        self,
        content: str,
        role: str,
        user_id: str,
        session_id: str = "",
        platform: str = "unknown",
        group_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """存储对话记录"""
        return await self.store(
            content=content,
            level=MemoryLevel.DIALOGUE,
            user_id=user_id,
            session_id=session_id,
            platform=platform,
            source=MemorySource.DIALOGUE,
            role=role,
            tags=tags,
            group_id=group_id or "",
            metadata=metadata,
        )

    async def store_important(
        self,
        content: str,
        user_id: str,
        tags: Optional[List[str]] = None,
        priority: float = 0.7,
        metadata: Optional[Dict] = None,
    ) -> str:
        """存储重要记忆 (长期)"""
        return await self.store(
            content=content,
            level=MemoryLevel.LONG_TERM,
            priority=priority,
            tags=tags or [],
            user_id=user_id,
            source=MemorySource.MANUAL,
            metadata=metadata,
        )

    async def store_auto(
        self,
        content: str,
        user_id: str,
        tags: Optional[List[str]] = None,
        priority: float = 0.5,
        metadata: Optional[Dict] = None,
    ) -> str:
        """自动提取存储"""
        return await self.store(
            content=content,
            priority=priority,
            tags=tags or [],
            user_id=user_id,
            source=MemorySource.AUTO_EXTRACT,
            metadata=metadata,
        )

    async def store_knowledge(
        self,
        subject: str,
        predicate: str,
        obj: str,
        context: str,
        user_id: str = "global",
        metadata: Optional[Dict] = None,
    ) -> str:
        """存储知识图谱条目"""
        return await self.store(
            content=context,
            level=MemoryLevel.KNOWLEDGE,
            user_id=user_id,
            source=MemorySource.SYSTEM,
            subject=subject,
            predicate=predicate,
            obj=obj,
            metadata=metadata,
        )

    # ==================== 检索 API ====================

    async def recall(
        self,
        request: Union[str, RecallRequest],
        user_id: str = "",
        group_id: str = "",
        limit: int = 20,
    ) -> RecallResult:
        """
        统一记忆检索

        支持方式:
            await bus.recall("关键词", user_id="...", limit=10)
            await bus.recall(RecallRequest(query="...", user_id="..."))
        """
        await self._ensure_init()

        t0 = time.time()

        if isinstance(request, str):
            req = RecallRequest(query=request, user_id=user_id, group_id=group_id, limit=limit)
        else:
            req = request

        q = MemoryQuery(
            query=req.query,
            user_id=req.user_id or None,
            group_id=req.group_id or None,
            session_id=req.session_id or None,
            tags=req.tags,
            level=req.level,
            levels=req.levels,
            min_priority=req.min_priority,
            limit=req.limit,
            start_time=req.start_time,
            end_time=req.end_time,
        )

        core = await self._ensure_core()
        memories = await core.retrieve(q)

        context_text = ""
        if memories:
            context_text = "\n".join(f"- [{getattr(m, 'created_at', '')[:10]}] {m.content[:200]}" for m in memories[:5])

        elapsed = (time.time() - t0) * 1000
        return RecallResult(
            memories=memories,
            context_text=context_text,
            total_found=len(memories),
            query_time_ms=elapsed,
        )

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        level: Optional[MemoryLevel] = None,
        limit: int = 20,
    ) -> List[MemoryItem]:
        """关键词搜索"""
        core = await self._ensure_core()
        return await core.retrieve(query=query, user_id=user_id, tags=tags, level=level, limit=limit)

    async def get_user_memories(
        self,
        user_id: str,
        level: Optional[MemoryLevel] = None,
        limit: int = 20,
    ) -> List[MemoryItem]:
        """获取用户所有记忆 (跨平台)"""
        core = await self._ensure_core()
        return await core.get_user_memory(user_id, level=level, limit=limit)

    async def get_user_dialogue(
        self,
        user_id: str,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryItem]:
        """获取用户对话历史 (跨平台聚合)"""
        core = await self._ensure_core()
        return await core.get_dialogue(user_id=user_id, platform=platform, limit=limit)

    async def get_dialogue_history(
        self,
        session_id: str = "",
        user_id: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryItem]:
        """获取对话历史 (优先按 user_id)"""
        core = await self._ensure_core()
        return await core.get_dialogue(session_id=session_id, user_id=user_id, platform=platform, limit=limit)

    # ==================== 会话上下文 ====================

    async def session_context(
        self,
        session_id: str,
        user_id: str = "",
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取会话级上下文"""
        await self._ensure_init()
        core = await self._ensure_core()
        memories = await core.get_dialogue(user_id=user_id or None, session_id=session_id, limit=max_messages)

        result = []
        for m in memories or []:
            result.append(
                {
                    "role": getattr(m, "role", "user"),
                    "content": getattr(m, "content", ""),
                    "timestamp": getattr(m, "created_at", ""),
                    "metadata": getattr(m, "metadata", {}),
                }
            )
        return result

    # ==================== 用户画像 ====================

    async def user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户画像"""
        core = await self._ensure_core()
        try:
            profile = await core.get_user_profile(user_id)
            return profile
        except Exception as e:
            logger.debug(f"[MemoryBus] 用户画像获取失败: {e}")
            return {"user_id": user_id, "memories": []}

    # ==================== 管理 API ====================

    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: Optional[float] = None,
        is_pinned: Optional[bool] = None,
    ) -> bool:
        """更新记忆"""
        core = await self._ensure_core()
        return await core.update(memory_id, content, tags, priority, is_pinned)

    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        core = await self._ensure_core()
        return await core.delete(memory_id)

    async def cleanup_expired(self) -> int:
        """清理过期记忆"""
        core = await self._ensure_core()
        return await core.delete_expired()

    async def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        core = await self._ensure_core()
        return await core.get_statistics()

    # ==================== Prompt 注入 ====================

    async def inject(
        self,
        user_id: str = "",
        group_id: str = "",
        session_id: str = "",
        platform: str = "unknown",
        user_input: str = "",
        conversation_history: Optional[List[Dict]] = None,
        available_tools: Optional[List[str]] = None,
        is_first_turn: bool = False,
        system_prompt: str = "",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        统一 Prompt 组装。

        返回: {"system": "完整系统提示", "user_context": {...}}
        """
        await self._ensure_init()

        from memory.injection_pipeline import HookContext

        ctx = HookContext(
            user_id=user_id,
            group_id=group_id,
            session_id=session_id,
            platform=platform,
            user_input=user_input,
            conversation_history=conversation_history or [],
            available_tools=available_tools or [],
            metadata=metadata or {},
            is_first_turn=is_first_turn,
        )

        result = await self._injection_pipeline.assemble_prompt(
            system_prompt=system_prompt or "",
            ctx=ctx,
        )
        return result

    # ==================== 认知 API ====================

    async def store_cognition(
        self,
        thinking: str = "",
        emotions: Optional[Dict[str, int]] = None,
        inner_thought: str = "",
        attribution: str = "",
        reflection: str = "",
        user_id: str = "global",
        group_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """存储认知记忆 (AI思考过程、情绪、内心独白)"""
        import json

        if emotions is None:
            emotions = {}

        cognition_content = (
            f"【认知记录】\n"
            f"思考过程: {thinking[:500] if thinking else '无'}\n"
            f"情绪分析: {json.dumps(emotions, ensure_ascii=False) if emotions else '无'}\n"
            f"内心独白: {inner_thought}\n"
            f"归因分析: {attribution}\n"
            f"反思: {reflection}"
        )

        core = await self._ensure_core()
        memory_id = await core.store(
            content=cognition_content,
            level=MemoryLevel.SHORT_TERM,
            user_id=user_id,
            group_id=group_id or "",
            source=MemorySource.AUTO_EXTRACT,
            tags=["cognition", "thinking", "emotion_record"],
            priority=0.6,
            metadata={
                **(metadata or {}),
                "thinking": thinking,
                "emotions": emotions,
                "inner_thought": inner_thought,
                "attribution": attribution,
                "reflection": reflection,
            },
        )

        # JSON 文件备份 (方便可视化)
        try:
            json_path = Path(DEFAULT_DATA_DIR) / "cognitive_memories.json"
            json_path.parent.mkdir(parents=True, exist_ok=True)

            existing = []
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.insert(
                0,
                {
                    "id": memory_id,
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id,
                    "thinking": thinking,
                    "emotions": emotions,
                    "inner_thought": inner_thought,
                    "attribution": attribution,
                    "reflection": reflection,
                },
            )
            existing = existing[:50]

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"[认知记忆] JSON备份失败: {e}")

        return memory_id

    async def recall_cognition(
        self,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索最近的认知记忆"""
        core = await self._ensure_core()
        results = await core.retrieve(query="", tags=["cognition"], limit=limit, user_id=user_id)

        out = []
        for item in results:
            meta = item.metadata or {}
            out.append(
                {
                    "id": item.id,
                    "timestamp": item.created_at,
                    "thinking": meta.get("thinking", ""),
                    "emotions": meta.get("emotions", {}),
                    "inner_thought": meta.get("inner_thought", ""),
                    "attribution": meta.get("attribution", ""),
                    "reflection": meta.get("reflection", ""),
                    "content": item.content,
                }
            )
        return out

    async def search_cognition(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """按关键词搜索认知记忆"""
        core = await self._ensure_core()
        results = await core.retrieve(query=query, tags=["cognition"], limit=limit, user_id=user_id)

        out = []
        for item in results:
            meta = item.metadata or {}
            out.append(
                {
                    "id": item.id,
                    "timestamp": item.created_at,
                    "thinking": meta.get("thinking", ""),
                    "emotions": meta.get("emotions", {}),
                    "inner_thought": meta.get("inner_thought", ""),
                    "attribution": meta.get("attribution", ""),
                    "reflection": meta.get("reflection", ""),
                    "content": item.content,
                }
            )
        return out

    # ==================== 维护 ====================

    async def heartbeat(self) -> Dict[str, Any]:
        """定期维护: 过期清理 + SQLite 一致性 + 统计"""
        await self._ensure_init()

        core = await self._ensure_core()
        result = {}

        try:
            result["expired_cleaned"] = await core.delete_expired()
        except Exception as e:
            logger.warning(f"[MemoryBus] 过期清理失败: {e}")
            result["expired_cleaned"] = 0

        try:
            result["sqlite_reconciled"] = await core._reconcile_sqlite_backend()
        except Exception as e:
            logger.warning(f"[MemoryBus] 同步修复失败: {e}")
            result["sqlite_reconciled"] = 0

        # V4.1.12: 定期重载记忆锚点（幂等，保证锚点文件变更后能生效）
        try:
            result["anchors_reloaded"] = await core.reload_memory_anchors()
        except Exception as e:
            logger.warning(f"[MemoryBus] 锚点重载失败: {e}")
            result["anchors_reloaded"] = 0

        try:
            result["stats"] = await core.get_statistics()
        except Exception as e:
            logger.warning(f"[MemoryBus] 统计失败: {e}")

        return result

    async def start_heartbeat(self, interval: int = 300):
        """启动定期维护"""
        if self._heartbeat_task:
            return

        async def _loop():
            while True:
                try:
                    await self.heartbeat()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(interval)

        self._heartbeat_task = asyncio.create_task(_loop())
        logger.info(f"[MemoryBus] 定期维护启动 (间隔 {interval}s)")

    async def stop_heartbeat(self):
        """停止定期维护"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    # ==================== 内部属性 ====================

    @property
    def core(self):
        """直接访问 MiyaMemoryCore (供内部 bridge 使用, 不建议外部调用)"""
        return self._core

    @property
    def cognitive_engine(self):
        return self._cognitive_engine

    @property
    def injection_pipeline(self):
        return self._injection_pipeline


# ==================== 模块级便捷获取 ====================


async def get_memory_bus(data_dir: Optional[Union[str, Path]] = None) -> MemoryBus:
    """获取全局 MemoryBus 单例"""
    return await MemoryBus.instance(data_dir=data_dir)


def reset_memory_bus():
    """重置 MemoryBus"""
    MemoryBus.reset()
