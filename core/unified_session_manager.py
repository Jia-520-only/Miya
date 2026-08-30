"""
会话管理融合模块

统一 Miya SessionManager 和 AstrBot ConversationManager
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionSource(Enum):
    """会话来源"""

    MIYA = "miya"
    ASTRBOT = "astrbot"


@dataclass
class SessionInfo:
    """会话信息"""

    session_id: str
    user_id: str
    platform: str
    source: SessionSource
    created_at: datetime
    last_active: datetime
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedSessionManager:
    """
    统一会话管理器

    功能：
    - 会话统一管理
    - 历史消息整合
    - 会话搜索
    """

    def __init__(self):
        self._sessions: Dict[str, SessionInfo] = {}
        self._histories: Dict[str, List[ChatMessage]] = {}
        self._miya_manager = None
        self._astrbot_manager = None
        self._initialized = False

    async def initialize(self):
        """初始化会话管理器"""
        logger.info("[UnifiedSessionManager] 初始化...")

        await self._init_miya_session()
        await self._init_astrbot_session()

        self._initialized = True
        logger.info(f"[UnifiedSessionManager] 初始化完成，共 {len(self._sessions)} 个会话")

    async def _init_miya_session(self):
        """初始化Miya会话管理"""
        try:
            from memory.session_manager import get_session_manager

            self._miya_manager = get_session_manager()
            logger.info("[UnifiedSessionManager] Miya会话管理器已加载")
        except Exception as e:
            logger.warning(f"[UnifiedSessionManager] Miya会话加载失败: {e}")

    async def _init_astrbot_session(self):
        """初始化AstrBot会话管理 (备用)"""
        try:
            from astrbot.core.conversation_mgr import ConversationManager

            from astrbot.core.db import BaseDatabase

            db = BaseDatabase()
            self._astrbot_manager = ConversationManager(db)
            logger.info("[UnifiedSessionManager] AstrBot会话管理器已加载 (备用)")
        except Exception as e:
            logger.info(f"[UnifiedSessionManager] AstrBot会话跳过: {e}")

    async def create_session(
        self,
        user_id: str,
        platform: str,
        source: SessionSource = SessionSource.MIYA,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建会话"""
        import uuid

        session_id = str(uuid.uuid4())

        self._sessions[session_id] = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            platform=platform,
            source=source,
            created_at=datetime.now(),
            last_active=datetime.now(),
            message_count=0,
            metadata=metadata or {},
        )

        self._histories[session_id] = []

        logger.info(f"[UnifiedSessionManager] 创建会话: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话"""
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if session_id in self._histories:
                del self._histories[session_id]
            return True
        return False

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加消息"""
        if session_id not in self._sessions:
            return False

        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        if session_id not in self._histories:
            self._histories[session_id] = []

        self._histories[session_id].append(message)

        session = self._sessions[session_id]
        session.message_count += 1
        session.last_active = datetime.now()

        return True

    async def get_history(self, session_id: str, limit: int = 50, offset: int = 0) -> List[ChatMessage]:
        """获取历史消息"""
        history = self._histories.get(session_id, [])
        return history[offset : offset + limit]

    async def search(self, keyword: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索消息"""
        results = []

        sessions = [session_id] if session_id else list(self._histories.keys())

        for sid in sessions:
            history = self._histories.get(sid, [])
            for i, msg in enumerate(history):
                if keyword.lower() in msg.content.lower():
                    results.append(
                        {
                            "session_id": sid,
                            "index": i,
                            "role": msg.role,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                        }
                    )

        return results

    async def get_or_create_session(self, user_id: str, platform: str) -> str:
        """获取或创建会话"""
        for session_id, session in self._sessions.items():
            if session.user_id == user_id and session.platform == platform:
                return session_id

        return await self.create_session(user_id, platform)

    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """获取用户的所有会话"""
        return [s for s in self._sessions.values() if s.user_id == user_id]

    async def clear_old_sessions(self, days: int = 30) -> int:
        """清理旧会话"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        to_delete = [sid for sid, session in self._sessions.items() if session.last_active < cutoff]

        for sid in to_delete:
            await self.delete_session(sid)

        logger.info(f"[UnifiedSessionManager] 清理了 {len(to_delete)} 个旧会话")
        return len(to_delete)

    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions = sorted(self._sessions.values(), key=lambda s: s.last_active, reverse=True)[:limit]

        return [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "platform": s.platform,
                "source": s.source.value,
                "created_at": s.created_at.isoformat(),
                "last_active": s.last_active.isoformat(),
                "message_count": s.message_count,
            }
            for s in sessions
        ]


_unified_session_manager: Optional[UnifiedSessionManager] = None


def get_unified_session_manager() -> UnifiedSessionManager:
    """获取全局统一会话管理器"""
    global _unified_session_manager
    if _unified_session_manager is None:
        _unified_session_manager = UnifiedSessionManager()
    return _unified_session_manager
