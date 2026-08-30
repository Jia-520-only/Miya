"""Message History Manager"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    id: str
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageHistoryManager:
    """消息历史管理器"""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._histories: Dict[str, List[Message]] = {}

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        if session_id not in self._histories:
            self._histories[session_id] = []

        msg = Message(
            id=f"{session_id}_{len(self._histories[session_id])}",
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._histories[session_id].append(msg)

        if len(self._histories[session_id]) > self.max_history:
            self._histories[session_id] = self._histories[session_id][-self.max_history :]

    def get_history(self, session_id: str, limit: int = 50) -> List[Message]:
        return self._histories.get(session_id, [])[-limit:]

    def clear_history(self, session_id: str):
        self._histories.pop(session_id, None)

    def search(self, session_id: str, keyword: str) -> List[Message]:
        history = self._histories.get(session_id, [])
        return [m for m in history if keyword in m.content]


_history_manager: Optional[MessageHistoryManager] = None


def get_message_history_manager(max_history: int = 100) -> MessageHistoryManager:
    global _history_manager
    if _history_manager is None:
        _history_manager = MessageHistoryManager(max_history)
    return _history_manager
