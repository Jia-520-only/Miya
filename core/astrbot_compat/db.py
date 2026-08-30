"""
AstrBot 数据库兼容层

提供 AstrBot 数据库接口的兼容实现。
"""

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import logger


class BaseDatabase:
    """数据库基类的兼容实现"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """初始化数据库连接"""
        async with self._lock:
            if self._connection is None:
                # 确保目录存在
                if self.db_path != ":memory:":
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

                # 创建连接
                self._connection = sqlite3.connect(self.db_path)
                self._connection.row_factory = sqlite3.Row
                logger.debug(f"Database initialized: {self.db_path}")

    async def close(self) -> None:
        """关闭数据库连接"""
        async with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                logger.debug(f"Database closed: {self.db_path}")

    async def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL 查询"""
        if not self._connection:
            await self.initialize()

        async with self._lock:
            try:
                cursor = self._connection.execute(query, params)
                self._connection.commit()
                return cursor
            except Exception as e:
                logger.error(f"Database execute error: {e}")
                raise

    async def executemany(self, query: str, params_list: List[tuple]) -> None:
        """执行多个 SQL 查询"""
        if not self._connection:
            await self.initialize()

        async with self._lock:
            try:
                self._connection.executemany(query, params_list)
                self._connection.commit()
            except Exception as e:
                logger.error(f"Database executemany error: {e}")
                raise

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """获取单行结果"""
        if not self._connection:
            await self.initialize()

        async with self._lock:
            try:
                cursor = self._connection.execute(query, params)
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            except Exception as e:
                logger.error(f"Database fetchone error: {e}")
                raise

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """获取所有结果"""
        if not self._connection:
            await self.initialize()

        async with self._lock:
            try:
                cursor = self._connection.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Database fetchall error: {e}")
                raise

    async def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = await self.fetchone(query, (table_name,))
        return result is not None

    async def create_table(self, table_name: str, schema: str) -> None:
        """创建表"""
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
        await self.execute(query)

    async def drop_table(self, table_name: str) -> None:
        """删除表"""
        query = f"DROP TABLE IF EXISTS {table_name}"
        await self.execute(query)

    async def insert(self, table_name: str, data: Dict[str, Any]) -> int:
        """插入数据"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor = await self.execute(query, tuple(data.values()))
        return cursor.lastrowid

    async def update(
        self,
        table_name: str,
        data: Dict[str, Any],
        where: str,
        where_params: tuple = (),
    ) -> int:
        """更新数据"""
        set_clause = ", ".join([f"{k} = ?" for k in data])
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where}"
        params = tuple(data.values()) + where_params
        cursor = await self.execute(query, params)
        return cursor.rowcount

    async def delete(self, table_name: str, where: str, where_params: tuple = ()) -> int:
        """删除数据"""
        query = f"DELETE FROM {table_name} WHERE {where}"
        cursor = await self.execute(query, where_params)
        return cursor.rowcount

    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器"""
        if not self._connection:
            await self.initialize()

        async with self._lock:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise


class SQLiteDatabase(BaseDatabase):
    """SQLite 数据库实现"""

    def __init__(self, db_path: str = "data/miya.db"):
        super().__init__(db_path)

    async def initialize(self) -> None:
        """初始化 SQLite 数据库"""
        await super().initialize()

        # 启用 WAL 模式以提高并发性能
        if self._connection:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._connection.execute("PRAGMA temp_store=MEMORY")


class MemoryDatabase(BaseDatabase):
    """内存数据库实现"""

    def __init__(self):
        super().__init__(":memory:")


# 导出
__all__ = [
    "BaseDatabase",
    "SQLiteDatabase",
    "MemoryDatabase",
]
