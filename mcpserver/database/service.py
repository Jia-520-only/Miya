#!/usr/bin/env python3
"""
MCP Database 服务 - 轻量级数据库操作
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


class DatabaseService:
    """MCP Database 服务 - SQLite 操作"""

    def __init__(self):
        self.name = "database"
        self.description = "数据库操作服务 (SQLite)"
        self.version = "1.0.0"
        self._db_path = Path(".miya/database.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS miya_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """处理工具调用"""
        tool_name = tool_call.get("tool_name", "")

        if "query" in tool_name.lower() or "select" in tool_name.lower():
            return await self._query(tool_call)
        elif (
            "execute" in tool_name.lower()
            or "insert" in tool_name.lower()
            or "update" in tool_name.lower()
            or "delete" in tool_name.lower()
        ):
            return await self._execute(tool_call)
        elif "table" in tool_name.lower() or "schema" in tool_name.lower():
            return await self._schema(tool_call)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"})

    async def _query(self, tool_call: Dict[str, Any]) -> str:
        """查询数据"""
        sql = tool_call.get("sql", "")

        if not sql:
            return json.dumps({"error": "缺少 sql 参数"})

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()

            return json.dumps({"success": True, "count": len(results), "results": results[:100]})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _execute(self, tool_call: Dict[str, Any]) -> str:
        """执行 SQL"""
        sql = tool_call.get("sql", "")

        if not sql:
            return json.dumps({"error": "缺少 sql 参数"})

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.execute(sql)
            conn.commit()
            affected = cursor.rowcount
            conn.close()

            return json.dumps(
                {
                    "success": True,
                    "affected_rows": affected,
                    "message": f"执行成功，影响 {affected} 行",
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _schema(self, tool_call: Dict[str, Any]) -> str:
        """获取表结构"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                schema[table] = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return json.dumps({"success": True, "tables": schema})
        except Exception as e:
            return json.dumps({"error": str(e)})


service = DatabaseService()


if __name__ == "__main__":
    import asyncio

    async def test():
        result = await service.handle_handoff({"tool_name": "schema"})
        print(result)

    asyncio.run(test())
