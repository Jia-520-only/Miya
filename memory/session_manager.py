"""
会话管理器 (SessionManager)

职责：
- 管理会话生命周期
- 提供对话历史查询（统一按 user_id 检索）
- 与统一记忆系统集成
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from memory import get_dialogue_history, get_user_dialogue, store_dialogue


class SessionCategory(Enum):
    """会话类别"""

    DIALOGUE = "dialogue"
    TASK = "task"
    SYSTEM = "system"
    CREATIVE = "creative"
    QQ = "qq"
    TERMINAL = "terminal"
    WEB = "web"


class SessionManager:
    """会话管理器 —— platform 仅作元数据，user_id 为主键"""

    def __init__(self):
        self._active_sessions: Dict[str, Dict] = {}

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        platform: str = "unknown",
        category: SessionCategory = SessionCategory.DIALOGUE,
    ) -> str:
        """创建新会话 —— session_key 不再包含 platform 前缀"""
        session_key = f"user_{user_id}" if user_id else session_id
        self._active_sessions[session_key] = {
            "session_id": session_id,
            "user_id": user_id,
            "platform": platform,
            "category": category.value if isinstance(category, SessionCategory) else category,
            "created_at": datetime.now().isoformat(),
            "message_count": 0,
        }
        return session_key

    async def get_session(self, session_id: str, platform: str = "unknown") -> Optional[Dict]:
        """获取会话信息 —— 直接按 session_id 查找"""
        return self._active_sessions.get(session_id)

    async def get_conversation_messages(
        self, session_id: str = "", user_id: str = "", platform: str = "unknown", limit: int = 50
    ) -> List[Dict]:
        """获取会话消息 —— 优先按 user_id 统一检索"""
        try:
            if user_id:
                mems = await get_user_dialogue(user_id=user_id, platform=platform, limit=limit)
            else:
                mems = await get_dialogue_history(session_id=session_id, platform=platform, limit=limit)
            return [{"role": m.role, "content": m.content} for m in mems]
        except Exception:
            return []

    async def save_session(
        self,
        session_id: str,
        platform: str,
        messages: List[Dict],
        category: SessionCategory = SessionCategory.DIALOGUE,
    ) -> Dict:
        """保存会话到记忆系统"""
        stored = 0
        for msg in messages:
            try:
                await store_dialogue(
                    content=msg.get("content", ""),
                    role=msg.get("role", "user"),
                    user_id=msg.get("user_id", "unknown"),
                    session_id=session_id,
                    platform=platform,
                    metadata=msg.get("metadata", {}),
                )
                stored += 1
            except Exception:
                continue

        session_key = session_id
        if session_key in self._active_sessions:
            self._active_sessions[session_key]["message_count"] = stored

        return {
            "success": True,
            "message": f"已保存 {stored}/{len(messages)} 条消息",
            "session_id": session_id,
            "platform": platform,
        }

    async def close_session(self, session_id: str, platform: str = "unknown") -> bool:
        """关闭会话"""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            return True
        return False

    def get_active_sessions(self) -> List[Dict]:
        """获取所有活跃会话"""
        return list(self._active_sessions.values())


def get_session_manager() -> SessionManager:
    return SessionManager()


def init_session_manager() -> SessionManager:
    return SessionManager()


__all__ = [
    "SessionManager",
    "SessionCategory",
    "get_session_manager",
    "init_session_manager",
]
