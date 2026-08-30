"""
MIYA 对话管理系统

管理会话、上下文和对话历史
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db_manager import (
    ConversationMessage,
    DatabaseManager,
    Session,
    get_db_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """对话上下文"""

    session_id: str
    user_id: str
    platform: str
    group_id: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ConversationManager:
    """
    MIYA 对话管理器

    功能:
    - 会话创建/销毁
    - 对话历史管理
    - 上下文管理
    - 消息存储
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self._db = db_manager or get_db_manager()
        self._sessions: Dict[str, ConversationContext] = {}
        self._lock = asyncio.Lock()
        self._session_timeout = 3600
        logger.info("[ConversationManager] 初始化完成")

    async def initialize(self):
        """初始化"""
        await self._db.initialize()
        logger.info("[ConversationManager] 已就绪")

    async def create_session(self, user_id: str, platform: str, group_id: Optional[str] = None) -> str:
        """创建会话"""
        session_id = str(uuid.uuid4())

        session = Session(
            session_id=session_id,
            user_id=user_id,
            platform=platform,
            group_id=group_id,
        )

        await self._db.create_session(session)

        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            platform=platform,
            group_id=group_id,
        )

        async with self._lock:
            self._sessions[session_id] = context

        logger.info(f"[ConversationManager] 创建会话: {session_id}")
        return session_id

    async def get_or_create_session(self, user_id: str, platform: str, group_id: Optional[str] = None) -> str:
        """获取或创建会话"""
        async with self._lock:
            for sid, ctx in self._sessions.items():
                if ctx.user_id == user_id and ctx.platform == platform and ctx.group_id == group_id:
                    ctx.last_activity = datetime.now()
                    return sid

        session_id = await self.create_session(user_id, platform, group_id)
        return session_id

    async def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """获取对话上下文"""
        async with self._lock:
            return self._sessions.get(session_id)

    async def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """添加消息"""
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )

        await self._db.add_message(message)

        async with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                ctx.messages.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                ctx.last_activity = datetime.now()

        return True

    async def get_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取对话历史"""
        messages = await self._db.get_messages(session_id, limit)

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    async def clear_history(self, session_id: str) -> bool:
        """清除对话历史"""
        messages = await self._db.get_messages(session_id, 999999)
        for msg in messages:
            if getattr(self._db, "_use_sqlite3", False):
                cursor = self._db._conn.cursor()
                cursor.execute("DELETE FROM conversation_messages WHERE id = ?", (msg.id,))
                self._db._conn.commit()
            else:
                await self._db._db.execute("DELETE FROM conversation_messages WHERE id = ?", (msg.id,))
                await self._db._db.commit()

        async with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                ctx.messages = []

        logger.info(f"[ConversationManager] 清除历史: {session_id}")
        return True

    async def set_variable(self, session_id: str, key: str, value: Any):
        """设置会话变量"""
        async with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                ctx.variables[key] = value

    async def get_variable(self, session_id: str, key: str, default: Any = None) -> Any:
        """获取会话变量"""
        async with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                return ctx.variables.get(key, default)
        return default

    async def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        await self._db.delete_session(session_id)

        async with self._lock:
            self._sessions.pop(session_id, None)

        logger.info(f"[ConversationManager] 关闭会话: {session_id}")
        return True

    async def cleanup_old_sessions(self):
        """清理旧会话"""
        now = datetime.now()
        to_remove = []

        async with self._lock:
            for sid, ctx in self._sessions.items():
                if (now - ctx.last_activity).total_seconds() > self._session_timeout:
                    to_remove.append(sid)

        for sid in to_remove:
            await self.close_session(sid)

        if to_remove:
            logger.info(f"[ConversationManager] 清理 {len(to_remove)} 个旧会话")

    def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        result = []
        for sid, ctx in self._sessions.items():
            result.append(
                {
                    "session_id": sid,
                    "user_id": ctx.user_id,
                    "platform": ctx.platform,
                    "group_id": ctx.group_id,
                    "message_count": len(ctx.messages),
                    "last_activity": ctx.last_activity.isoformat(),
                }
            )
        return result


_conv_manager = None


def get_conversation_manager(
    db_manager: Optional[DatabaseManager] = None,
) -> ConversationManager:
    """获取对话管理器"""
    global _conv_manager
    if _conv_manager is None:
        _conv_manager = ConversationManager(db_manager)
    return _conv_manager


__all__ = [
    "ConversationContext",
    "ConversationManager",
    "get_conversation_manager",
]
