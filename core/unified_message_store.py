"""
统一跨平台消息存储

提供所有平台消息的持久化存储和查询能力。
使用 SQLite 直接读写，不依赖外部 ORM。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.UnifiedMessageStore")

_DDL = """
CREATE TABLE IF NOT EXISTS platform_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT,
    content TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'in',
    message_id TEXT,
    reply_to_message_id TEXT,
    group_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pm_platform ON platform_messages(platform_id);
CREATE INDEX IF NOT EXISTS idx_pm_user ON platform_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_pm_direction ON platform_messages(direction);
CREATE INDEX IF NOT EXISTS idx_pm_message_id ON platform_messages(message_id);
CREATE INDEX IF NOT EXISTS idx_pm_created ON platform_messages(created_at);
"""


class UnifiedMessageStore:
    """
    跨平台统一消息存储

    功能：
    - 记录所有入站/出站消息
    - 支持按平台、用户、方向、时间范围查询
    - 支持回复关联 (reply_to_message_id)
    - 基于 SQLite，零外部依赖
    """

    def __init__(self, db_path: str = "data/messages.db"):
        self._db_path = db_path
        self._conn: Any = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        os.makedirs(os.path.dirname(self._db_path) or "data", exist_ok=True)

        try:
            import aiosqlite

            self._db = await aiosqlite.connect(self._db_path)
            self._use_async = True
            statements = [s.strip() for s in _DDL.split(";") if s.strip()]
            for stmt in statements:
                await self._db.execute(stmt)
            await self._db.commit()
        except ImportError:
            import sqlite3

            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._use_async = False
            self._conn.executescript(_DDL)
            self._conn.commit()

        self._initialized = True
        logger.info(f"[UnifiedMessageStore] 初始化完成: {self._db_path}")

    async def _exec_write(self, sql: str, params: tuple = ()) -> Optional[int]:
        """执行写操作，返回 lastrowid"""
        if self._use_async:
            cursor = await self._db.execute(sql, params)
            await self._db.commit()
            return cursor.lastrowid
        else:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor.lastrowid

    async def _exec_fetch(self, sql: str, params: tuple = ()) -> list:
        """查询并返回结果"""
        if self._use_async:
            cursor = await self._db.execute(sql, params) if params else await self._db.execute(sql)
            rows = await cursor.fetchall()
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            return [dict(zip(cols, row, strict=False)) for row in rows]
        else:
            cursor = self._conn.execute(sql, params) if params else self._conn.execute(sql)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            return [dict(zip(cols, row, strict=False)) for row in rows]

    async def _exec_one(self, sql: str, params: tuple = ()):
        """查询单条"""
        if self._use_async:
            cursor = await self._db.execute(sql, params) if params else await self._db.execute(sql)
            row = await cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                return dict(zip(cols, row, strict=False))
            return None
        else:
            cursor = self._conn.execute(sql, params) if params else self._conn.execute(sql)
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                return dict(zip(cols, row, strict=False))
            return None

    async def record_message(
        self,
        platform_id: str,
        user_id: str,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        content: Optional[Dict] = None,
        direction: str = "in",
        message_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        group_id: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Optional[int]:
        """
        记录一条消息到跨平台存储
        """
        try:
            if not self._initialized:
                await self.initialize()

            msg_content = content or {}
            if text and not msg_content.get("text"):
                msg_content["text"] = text
            if message_id:
                msg_content["message_id"] = message_id
            if direction:
                msg_content["direction"] = direction
            if reply_to_message_id:
                msg_content["reply_to_message_id"] = reply_to_message_id
            if group_id:
                msg_content["group_id"] = group_id

            content_json = json.dumps(msg_content, ensure_ascii=False)
            user_key = f"{platform_id}:{user_id}"
            if group_id:
                user_key = f"{user_key}:{group_id}"
            created_at = datetime.now().isoformat()

            row_id = await self._exec_write(
                """INSERT INTO platform_messages
                   (platform_id, user_id, sender_id, sender_name, content, direction, message_id, reply_to_message_id, group_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    platform_id,
                    user_key,
                    sender_id or "",
                    sender_name or "",
                    content_json,
                    direction,
                    message_id or "",
                    reply_to_message_id or "",
                    group_id or "",
                    created_at,
                ),
            )

            logger.debug(
                f"[MessageStore] 记录消息 #{row_id}: {platform_id}/{direction} from={sender_name or sender_id}"
            )
            return row_id

        except Exception as e:
            logger.error(f"[MessageStore] 记录消息失败: {e}")
            return None

    async def query_messages(
        self,
        platform_id: Optional[str] = None,
        user_id: Optional[str] = None,
        direction: Optional[str] = None,
        sender_name: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        查询跨平台消息
        """
        try:
            if not self._initialized:
                await self.initialize()

            conditions = []
            params: list = []

            if platform_id:
                conditions.append("platform_id = ?")
                params.append(platform_id)
            if user_id:
                conditions.append("user_id LIKE ?")
                params.append(f"%{user_id}%")
            if direction:
                conditions.append("direction = ?")
                params.append(direction)
            if sender_name:
                conditions.append("sender_name LIKE ?")
                params.append(f"%{sender_name}%")
            if since:
                conditions.append("created_at >= ?")
                params.append(since.isoformat())
            if until:
                conditions.append("created_at <= ?")
                params.append(until.isoformat())

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.extend([limit, offset])

            rows = await self._exec_fetch(
                f"""SELECT * FROM platform_messages {where}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                tuple(params),
            )

            messages = []
            for row in rows:
                try:
                    content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
                except (json.JSONDecodeError, TypeError):
                    content = {"text": str(row["content"])}

                messages.append(
                    {
                        "id": row["id"],
                        "message_id": content.get("message_id", str(row["id"])),
                        "platform_id": row["platform_id"],
                        "user_id": row["user_id"],
                        "sender_id": row["sender_id"],
                        "sender_name": row["sender_name"],
                        "content": content.get("text", str(content)),
                        "raw_content": content,
                        "direction": row["direction"],
                        "reply_to_message_id": content.get("reply_to_message_id"),
                        "timestamp": content.get("timestamp", row["created_at"]),
                        "created_at": row["created_at"],
                    }
                )

            return messages

        except Exception as e:
            logger.error(f"[MessageStore] 查询消息失败: {e}")
            return []

    async def query_as_conversation(
        self,
        platform_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """按对话时序查询消息"""
        messages = await self.query_messages(
            platform_id=platform_id,
            user_id=user_id,
            limit=limit,
        )
        messages.sort(key=lambda m: m.get("created_at", ""))
        return messages

    async def get_message_count(
        self,
        platform_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """获取消息总数"""
        try:
            if not self._initialized:
                await self.initialize()

            conditions = []
            params: list = []
            if platform_id:
                conditions.append("platform_id = ?")
                params.append(platform_id)
            if since:
                conditions.append("created_at >= ?")
                params.append(since.isoformat())

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            row = await self._exec_one(
                f"SELECT COUNT(*) as cnt FROM platform_messages {where}",
                tuple(params) if params else (),
            )
            return row["cnt"] if row else 0

        except Exception as e:
            logger.error(f"[MessageStore] 获取消息数失败: {e}")
            return 0

    async def search_messages(
        self,
        keyword: str,
        platform_id: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按关键字搜索消息内容"""
        try:
            if not self._initialized:
                await self.initialize()

            conditions = ["(content LIKE ? OR sender_name LIKE ?)"]
            params: list = [f"%{keyword}%", f"%{keyword}%"]

            if platform_id:
                conditions.append("platform_id = ?")
                params.append(platform_id)
            if direction:
                conditions.append("direction = ?")
                params.append(direction)

            where = f"WHERE {' AND '.join(conditions)}"
            params.extend([limit, offset])

            rows = await self._exec_fetch(
                f"""SELECT * FROM platform_messages {where}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                tuple(params),
            )

            messages = []
            for row in rows:
                try:
                    content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
                except (json.JSONDecodeError, TypeError):
                    content = {"text": str(row["content"])}

                messages.append(
                    {
                        "id": row["id"],
                        "message_id": content.get("message_id", str(row["id"])),
                        "platform_id": row["platform_id"],
                        "user_id": row["user_id"],
                        "sender_id": row["sender_id"],
                        "sender_name": row["sender_name"],
                        "content": content.get("text", str(content)),
                        "raw_content": content,
                        "direction": row["direction"],
                        "reply_to_message_id": content.get("reply_to_message_id"),
                        "timestamp": content.get("timestamp", row["created_at"]),
                        "created_at": row["created_at"],
                    }
                )

            return messages

        except Exception as e:
            logger.error(f"[MessageStore] 搜索消息失败: {e}")
            return []

    async def record_miya_reply(
        self,
        platform_id: str,
        user_id: str,
        content_text: str,
        reply_to_message_id: Optional[str] = None,
        sender_name: str = "弥娅",
        group_id: Optional[str] = None,
    ) -> Optional[int]:
        """记录弥娅发出的回复（出站消息）"""
        return await self.record_message(
            platform_id=platform_id,
            user_id=user_id,
            sender_id="miya",
            sender_name=sender_name,
            content={"text": content_text},
            direction="out",
            reply_to_message_id=reply_to_message_id,
            group_id=group_id,
            text=content_text,
        )


_unified_message_store: Optional[UnifiedMessageStore] = None


def get_unified_message_store() -> UnifiedMessageStore:
    """获取全局统一消息存储实例"""
    global _unified_message_store
    if _unified_message_store is None:
        _unified_message_store = UnifiedMessageStore()
    return _unified_message_store
