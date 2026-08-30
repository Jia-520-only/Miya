"""
任务持久化存储 — SQLite 实现

支持:
- 任务 CRUD 到 SQLite
- 重启后自动恢复 pending 任务
- 任务历史查询
- 重复任务 schedule 计算
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/tasks.db")

CREATE_TASKS_SQL = """
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    platform TEXT,
    target_type TEXT,
    target_id TEXT,
    message TEXT,
    execute_at TEXT NOT NULL,
    repeat_type TEXT NOT NULL DEFAULT 'once',
    repeat_config TEXT,
    priority INTEGER DEFAULT 5,
    execution_count INTEGER DEFAULT 0,
    max_executions INTEGER,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    completed_at TEXT,
    last_error TEXT,
    action_type TEXT,
    action_times INTEGER,
    condition_type TEXT DEFAULT 'time',
    condition_data TEXT,
    follow_up_task TEXT
);
"""

CREATE_IDX_SQL = """
CREATE INDEX IF NOT EXISTS idx_tasks_status ON scheduled_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_execute_at ON scheduled_tasks(execute_at);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON scheduled_tasks(created_by);
"""

MIGRATIONS_SQL = """
ALTER TABLE scheduled_tasks ADD COLUMN condition_type TEXT DEFAULT 'time';
ALTER TABLE scheduled_tasks ADD COLUMN condition_data TEXT;
ALTER TABLE scheduled_tasks ADD COLUMN follow_up_task TEXT;
"""

REPEAT_DELTA_MAP = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


class TaskStore:
    """SQLite 任务持久化存储"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(CREATE_TASKS_SQL)
                self._run_migrations(conn)
                conn.executescript(CREATE_IDX_SQL)
                conn.commit()
                logger.info(f"[TaskStore] 数据库已初始化: {self.db_path}")
            finally:
                conn.close()

    def _run_migrations(self, conn: sqlite3.Connection):
        """safe migration: try adding columns, ignore if already exist"""
        existing = [r[1] for r in conn.execute("PRAGMA table_info(scheduled_tasks)").fetchall()]
        for col, col_type in [
            ("condition_type", "TEXT DEFAULT 'time'"),
            ("condition_data", "TEXT"),
            ("follow_up_task", "TEXT"),
        ]:
            if col not in existing:
                try:
                    conn.execute(f"ALTER TABLE scheduled_tasks ADD COLUMN {col} {col_type}")
                    logger.info(f"[TaskStore] 迁移: 添加列 {col}")
                except Exception as e:
                    logger.warning(f"[TaskStore] 迁移 {col} 失败: {e}")
        # 条件索引单独建（只在列存在时）
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_condition ON scheduled_tasks(condition_type)")
        except Exception:
            pass

    def save_task(self, task_data: Dict[str, Any]) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                now = datetime.now().isoformat()
                repeat_type = task_data.get("repeat_type") or task_data.get("repeat", "once")

                def _json_str(val):
                    if val is None:
                        return None
                    if isinstance(val, str):
                        return val
                    if isinstance(val, dict):
                        return json.dumps(val, ensure_ascii=False)
                    return str(val)

                repeat_config_str = _json_str(task_data.get("repeat_config"))
                condition_data_str = _json_str(task_data.get("condition_data"))
                follow_up_str = _json_str(task_data.get("follow_up_task"))

                conn.execute(
                    """INSERT OR REPLACE INTO scheduled_tasks
                    (task_id, task_type, status, platform, target_type, target_id,
                     message, execute_at, repeat_type, repeat_config, priority,
                     execution_count, max_executions, created_by, created_at,
                     updated_at, action_type, action_times,
                     condition_type, condition_data, follow_up_task)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_data["task_id"],
                        task_data.get("task_type", "reminder"),
                        task_data.get("status", "pending"),
                        task_data.get("platform"),
                        task_data.get("target_type"),
                        str(task_data.get("target_id", "")),
                        task_data.get("message", ""),
                        task_data.get("execute_at", ""),
                        repeat_type,
                        repeat_config_str,
                        task_data.get("priority", 5),
                        task_data.get("execution_count", 0),
                        task_data.get("max_executions"),
                        task_data.get("created_by", ""),
                        task_data.get("created_at", now),
                        now,
                        task_data.get("action_type"),
                        task_data.get("action_times", 1),
                        task_data.get("condition_type", "time"),
                        condition_data_str,
                        follow_up_str,
                    ),
                )
                conn.commit()
                logger.debug(f"[TaskStore] 保存任务: {task_data['task_id']}")
            finally:
                conn.close()

    def update_status(
        self,
        task_id: str,
        status: str,
        execute_at: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                now = datetime.now().isoformat()
                sql = "UPDATE scheduled_tasks SET status = ?, updated_at = ?"
                params: List[Any] = [status, now]

                if status == "completed":
                    sql += ", completed_at = ?, execution_count = execution_count + 1"
                    params.append(now)
                elif status == "failed" and error:
                    sql += ", last_error = ?"
                    params.append(error)

                if execute_at:
                    sql += ", execute_at = ?"
                    params.append(execute_at)

                sql += " WHERE task_id = ?"
                params.append(task_id)

                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()

    def load_pending_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM scheduled_tasks WHERE status = 'pending' ORDER BY execute_at ASC"
                ).fetchall()
                tasks = []
                for row in rows:
                    task = dict(row)
                    if task.get("repeat_config"):
                        try:
                            task["repeat_config"] = json.loads(task["repeat_config"])
                        except json.JSONDecodeError:
                            task["repeat_config"] = None
                    tasks.append(task)
                logger.info(f"[TaskStore] 加载待执行任务: {len(tasks)} 个")
                return tasks
            finally:
                conn.close()

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("DELETE FROM scheduled_tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"[TaskStore] 删除任务: {task_id}")
                return deleted
            finally:
                conn.close()

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "UPDATE scheduled_tasks SET status = 'cancelled', updated_at = ? WHERE task_id = ? AND status = 'pending'",
                    (datetime.now().isoformat(), task_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM scheduled_tasks WHERE task_id = ?", (task_id,)).fetchone()
                if row:
                    task = dict(row)
                    if task.get("repeat_config"):
                        try:
                            task["repeat_config"] = json.loads(task["repeat_config"])
                        except json.JSONDecodeError:
                            task["repeat_config"] = None
                    return task
                return None
            finally:
                conn.close()

    def list_tasks(
        self,
        status: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                conditions = []
                params: List[Any] = []
                if status:
                    conditions.append("status = ?")
                    params.append(status)
                if created_by:
                    conditions.append("created_by = ?")
                    params.append(created_by)
                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                sql = f"SELECT * FROM scheduled_tasks {where} ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def find_by_condition(self, condition_type: str, target_id: str = None) -> List[Dict[str, Any]]:
        """查找条件触发类型的 pending 任务"""
        with self._lock:
            conn = self._get_conn()
            try:
                params: List[Any] = [condition_type]
                sql = "SELECT * FROM scheduled_tasks WHERE status = 'pending' AND condition_type = ?"
                if target_id:
                    sql += " AND target_id = ?"
                    params.append(str(target_id))
                rows = conn.execute(sql, params).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            conn = self._get_conn()
            try:
                stats = {}
                rows = conn.execute("SELECT status, COUNT(*) as cnt FROM scheduled_tasks GROUP BY status").fetchall()
                for row in rows:
                    stats[row["status"]] = row["cnt"]
                return stats
            finally:
                conn.close()

    @staticmethod
    def calc_next_execute_time(
        current_execute_at: datetime,
        repeat_type: str,
        repeat_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[datetime]:
        if repeat_type == "once":
            return None
        delta = REPEAT_DELTA_MAP.get(repeat_type)
        if not delta:
            return None
        next_time = current_execute_at + delta
        if repeat_config:
            end_date = repeat_config.get("end_date")
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                    if next_time > end_dt:
                        return None
                except (ValueError, TypeError):
                    pass
        return next_time
