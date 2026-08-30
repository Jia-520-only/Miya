"""
MIYA 数据库层

提供 SQLite 数据库支持，用于存储会话、配置、对话历史等数据
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """会话"""

    session_id: str
    user_id: str
    platform: str
    group_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    """对话消息"""

    session_id: str
    role: str
    content: str
    id: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatabaseManager:
    """
    MIYA 数据库管理器

    功能:
    - SQLite 数据库连接
    - 会话管理
    - 对话历史存储
    - 配置存储
    """

    def __init__(self, db_path: str = "data/miya.db"):
        self.db_path = db_path
        self._db = None
        self._use_sqlite3 = False
        self._lock = asyncio.Lock()
        logger.info(f"[DatabaseManager] 初始化: {db_path}")

    async def initialize(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        try:
            import aiosqlite
        except ImportError:
            logger.warning("[DatabaseManager] aiosqlite 未安装，使用 sqlite3")
            import sqlite3

            self._use_sqlite3 = True
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._create_tables()
            logger.info("[DatabaseManager] SQLite3 初始化完成")
            return

        self._use_sqlite3 = False
        self._db = await aiosqlite.connect(self.db_path)
        self._create_tables()
        logger.info("[DatabaseManager] aiosqlite 初始化完成")

    def _create_tables(self):
        """创建表"""
        cursor = self._conn.cursor() if self._use_sqlite3 else self._db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                group_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        if self._use_sqlite3:
            self._conn.commit()

    async def close(self):
        """关闭数据库"""
        if self._db:
            await self._db.close()
        elif self._use_sqlite3 and self._conn:
            self._conn.close()
        logger.info("[DatabaseManager] 已关闭")

    async def create_session(self, session: Session) -> bool:
        """创建会话"""
        async with self._lock:
            try:
                now = datetime.now().isoformat()
                if self._use_sqlite3:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            session.session_id,
                            session.user_id,
                            session.platform,
                            session.group_id,
                            session.created_at.isoformat(),
                            now,
                            json.dumps(session.metadata),
                        ),
                    )
                    self._conn.commit()
                else:
                    await self._db.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            session.session_id,
                            session.user_id,
                            session.platform,
                            session.group_id,
                            session.created_at.isoformat(),
                            now,
                            json.dumps(session.metadata),
                        ),
                    )
                    await self._db.commit()
                logger.info(f"[DatabaseManager] 创建会话: {session.session_id}")
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] 创建会话失败: {e}")
                return False

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        if self._use_sqlite3:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
        else:
            cursor = await self._db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = await cursor.fetchone()

        if row:
            return Session(
                session_id=row[0],
                user_id=row[1],
                platform=row[2],
                group_id=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                metadata=json.loads(row[6] or "{}"),
            )
        return None

    async def update_session(self, session: Session) -> bool:
        """更新会话"""
        async with self._lock:
            try:
                now = datetime.now().isoformat()
                if self._use_sqlite3:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?",
                        (now, json.dumps(session.metadata), session.session_id),
                    )
                    self._conn.commit()
                else:
                    await self._db.execute(
                        "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?",
                        (now, json.dumps(session.metadata), session.session_id),
                    )
                    await self._db.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] 更新会话失败: {e}")
                return False

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if self._db is None and not self._use_sqlite3:
            return False  # 未初始化（无持久化 DB），无记录可删
        async with self._lock:
            try:
                if self._use_sqlite3:
                    cursor = self._conn.cursor()
                    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    cursor.execute(
                        "DELETE FROM conversation_messages WHERE session_id = ?",
                        (session_id,),
                    )
                    self._conn.commit()
                else:
                    await self._db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    await self._db.execute(
                        "DELETE FROM conversation_messages WHERE session_id = ?",
                        (session_id,),
                    )
                    await self._db.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] 删除会话失败: {e}")
                return False

    async def add_message(self, message: ConversationMessage) -> bool:
        """添加消息"""
        async with self._lock:
            try:
                if self._use_sqlite3:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "INSERT INTO conversation_messages (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                        (
                            message.session_id,
                            message.role,
                            message.content,
                            message.timestamp.isoformat(),
                            json.dumps(message.metadata),
                        ),
                    )
                    self._conn.commit()
                else:
                    await self._db.execute(
                        "INSERT INTO conversation_messages (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                        (
                            message.session_id,
                            message.role,
                            message.content,
                            message.timestamp.isoformat(),
                            json.dumps(message.metadata),
                        ),
                    )
                    await self._db.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] 添加消息失败: {e}")
                return False

    async def get_messages(self, session_id: str, limit: int = 100) -> List[ConversationMessage]:
        """获取消息历史"""
        if self._use_sqlite3:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM conversation_messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
            rows = cursor.fetchall()
        else:
            cursor = await self._db.execute(
                "SELECT * FROM conversation_messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
            rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                ConversationMessage(
                    id=row[0],
                    session_id=row[1],
                    role=row[2],
                    content=row[3],
                    timestamp=datetime.fromisoformat(row[4]),
                    metadata=json.loads(row[5] or "{}"),
                )
            )
        messages.reverse()
        return messages

    async def set_config(self, key: str, value: Any) -> bool:
        """设置配置"""
        async with self._lock:
            try:
                now = datetime.now().isoformat()
                if self._use_sqlite3:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value), now),
                    )
                    self._conn.commit()
                else:
                    await self._db.execute(
                        "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value), now),
                    )
                    await self._db.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] 设置配置失败: {e}")
                return False

    async def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        if self._use_sqlite3:
            cursor = self._conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
        else:
            cursor = await self._db.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = await cursor.fetchone()

        if row:
            return json.loads(row[0])
        return default


_db_manager = None


def get_db_manager(db_path: str = "data/miya.db") -> DatabaseManager:
    """获取数据库管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager


__all__ = [
    "Session",
    "ConversationMessage",
    "DatabaseManager",
    "get_db_manager",
]
