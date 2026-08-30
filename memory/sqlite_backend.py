"""
弥娅记忆系统 - SQLite 后端
与 JSON 后端并存，提供高性能查询能力
JSON 保持可视化，SQLite 用于快速检索
所有配置从 text_config.json 加载，无硬编码
"""

import json
import logging
import math
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .core import MemoryBackend, MemoryItem, MemoryLevel, MemoryQuery, MemorySource

logger = logging.getLogger(__name__)

# 列定义（按顺序，与 INSERT 语句对应）
COLUMNS = [
    "id",
    "content",
    "level",
    "priority",
    "user_id",
    "session_id",
    "group_id",
    "tags",
    "created_at",
    "expires_at",
    "source",
    "platform",
    "role",
    "event_type",
    "location",
    "conversation_partner",
    "emotional_tone",
    "significance",
    "metadata",
    "subject",
    "predicate",
    "obj",
    "vector",
    "access_count",
    "last_accessed",
    "is_archived",
    "is_pinned",
]

COLUMN_TYPES = {
    "id": "TEXT PRIMARY KEY",
    "content": "TEXT NOT NULL",
    "level": "TEXT NOT NULL",
    "priority": "REAL",
    "user_id": "TEXT",
    "session_id": "TEXT",
    "group_id": "TEXT",
    "tags": "TEXT",
    "created_at": "TEXT NOT NULL",
    "expires_at": "TEXT",
    "source": "TEXT",
    "platform": "TEXT",
    "role": "TEXT",
    "event_type": "TEXT",
    "location": "TEXT",
    "conversation_partner": "TEXT",
    "emotional_tone": "TEXT",
    "significance": "REAL",
    "metadata": "TEXT",
    "subject": "TEXT",
    "predicate": "TEXT",
    "obj": "TEXT",
    "vector": "TEXT",
    "access_count": "INTEGER",
    "last_accessed": "TEXT",
    "is_archived": "INTEGER",
    "is_pinned": "INTEGER",
}


def _load_sqlite_config() -> dict:
    """从 memory_config.json 或 text_config.json 加载 SQLite 配置"""
    config_dir = Path(__file__).parent.parent / "config"
    try:
        memory_config_path = config_dir / "memory_config.json"
        text_config_path = config_dir / "text_config.json"

        if memory_config_path.exists():
            with open(memory_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            db_config = config.get("sqlite_backend")
            if db_config:
                return db_config

        if text_config_path.exists():
            with open(text_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("sqlite_backend", {})
    except Exception as e:
        logger.warning(f"[SQLiteBackend] 配置加载失败: {e}")
    return {}


class SQLiteBackend(MemoryBackend):
    """SQLite 记忆后端 - 高性能查询"""

    def __init__(self, db_path: Optional[str] = None):
        self._config = _load_sqlite_config()
        self._enabled = self._config.get("enabled", False)

        if not self._enabled:
            logger.info("[SQLiteBackend] 未启用，跳过初始化")
            self._conn = None
            return

        # 从配置读取路径
        cfg_path = db_path or self._config.get("db_path", "data/memory/miya_memory.db")
        self.db_path = Path(cfg_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._table_name = self._config.get("table", {}).get("name", "memories")
        self._fts_enabled = self._config.get("table", {}).get("fts_enabled", True)
        self._fts_name = self._config.get("table", {}).get("fts_name", "memories_fts")
        self._fts_columns = self._config.get("table", {}).get("fts_columns", ["content", "tags"])
        self._indexes = self._config.get("indexes", [])
        self._defaults = self._config.get("defaults", {})
        self._order_clause = self._config.get("query", {}).get("default_order", "priority DESC, created_at DESC")
        self._like_prefix = self._config.get("query", {}).get("like_pattern_prefix", "%")
        self._like_suffix = self._config.get("query", {}).get("like_pattern_suffix", "%")

        self._init_db()

    @property
    def enabled(self) -> bool:
        return self._enabled and self._conn is not None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._apply_pragma()
        return self._conn

    def _apply_pragma(self):
        pragma = self._config.get("pragma", {})
        for key, value in pragma.items():
            if isinstance(value, bool):
                value = 1 if value else 0
            self._conn.execute(f"PRAGMA {key}={value}")

    def _init_db(self):
        conn = self._get_conn()

        # 建表语句从配置动态生成
        col_defs = []
        for col in COLUMNS:
            col_type = COLUMN_TYPES.get(col, "TEXT")
            default = self._defaults.get(col)
            if default is not None:
                if isinstance(default, str):
                    col_defs.append(f"{col} {col_type} DEFAULT '{default}'")
                else:
                    col_defs.append(f"{col} {col_type} DEFAULT {default}")
            else:
                col_defs.append(f"{col} {col_type}")

        create_sql = f"CREATE TABLE IF NOT EXISTS {self._table_name} ({', '.join(col_defs)})"
        conn.execute(create_sql)

        # 创建索引
        for idx in self._indexes:
            idx_name = idx.get("name", f"idx_{self._table_name}_{idx.get('column', '')}")
            idx_col = idx.get("column", "")
            if idx_col:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self._table_name}({idx_col})")

        # FTS 虚拟表
        if self._fts_enabled and self._fts_columns:
            fts_cols = ", ".join(self._fts_columns)
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {self._fts_name} USING fts5("
                f"{fts_cols}, content='{self._table_name}', content_rowid='rowid'"
                f")"
            )

        conn.commit()
        logger.info(f"[SQLiteBackend] 数据库初始化完成: {self.db_path}")

    def _build_values(self, memory: MemoryItem) -> tuple:
        """根据列顺序构建 INSERT 值元组"""
        # 处理 metadata 中可能存在的枚举
        metadata_str = "{}"
        if memory.metadata:
            try:
                # 使用 MemoryItem 的序列化方法处理枚举
                serialized_metadata = memory._serialize_dict(memory.metadata)
                metadata_str = json.dumps(serialized_metadata, ensure_ascii=False)
            except Exception:
                metadata_str = json.dumps(str(memory.metadata), ensure_ascii=False)

        field_map = {
            "id": memory.id,
            "content": memory.content,
            "level": memory.level.value,
            "priority": memory.priority,
            "user_id": memory.user_id,
            "session_id": memory.session_id,
            "group_id": memory.group_id,
            "tags": json.dumps(memory.tags, ensure_ascii=False),
            "created_at": memory.created_at,
            "expires_at": memory.expires_at,
            "source": memory.source.value if memory.source else self._defaults.get("source", ""),
            "platform": memory.platform,
            "role": memory.role,
            "event_type": memory.event_type or "",
            "location": memory.location or "",
            "conversation_partner": memory.conversation_partner or "",
            "emotional_tone": memory.emotional_tone or "",
            "significance": memory.significance,
            "metadata": metadata_str,
            "subject": memory.subject or "",
            "predicate": memory.predicate or "",
            "obj": memory.obj or "",
            "vector": json.dumps(memory.vector) if memory.vector else "",
            "access_count": memory.access_count,
            "last_accessed": memory.last_accessed,
            "is_archived": 1 if memory.is_archived else 0,
            "is_pinned": 1 if memory.is_pinned else 0,
        }
        return tuple(field_map.get(col, "") for col in COLUMNS)

    async def save(self, memory: MemoryItem) -> bool:
        if not self.enabled:
            return False
        try:
            conn = self._get_conn()
            placeholders = ", ".join(["?"] * len(COLUMNS))
            columns_str = ", ".join(COLUMNS)
            conn.execute(f"DELETE FROM {self._table_name} WHERE id = ?", (memory.id,))
            conn.execute(
                f"INSERT INTO {self._table_name} ({columns_str}) VALUES ({placeholders})",
                self._build_values(memory),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"[SQLiteBackend] 保存记忆失败: {e}")
            return False

    async def load(self, memory_id: str) -> Optional[MemoryItem]:
        if not self.enabled:
            return None
        try:
            conn = self._get_conn()
            row = conn.execute(f"SELECT * FROM {self._table_name} WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            return self._row_to_memory(row)
        except Exception as e:
            logger.error(f"[SQLiteBackend] 加载记忆失败: {e}")
            return None

    async def delete(self, memory_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            conn = self._get_conn()
            conn.execute(f"DELETE FROM {self._table_name} WHERE id = ?", (memory_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"[SQLiteBackend] 删除记忆失败: {e}")
            return False

    async def query(self, query: MemoryQuery) -> List[MemoryItem]:
        if not self.enabled:
            return []
        try:
            conn = self._get_conn()
            conditions = []
            params = []

            if query.user_ids:
                placeholders = ", ".join(["?"] * len(query.user_ids))
                conditions.append(f"user_id IN ({placeholders})")
                params.extend(query.user_ids)
            elif query.user_id:
                conditions.append("user_id = ?")
                params.append(query.user_id)
            if query.group_id:
                conditions.append("group_id = ?")
                params.append(query.group_id)
            if query.platform:
                conditions.append("platform = ?")
                params.append(query.platform)
            if query.level:
                conditions.append("level = ?")
                params.append(query.level.value)
            if query.levels:
                placeholders = ", ".join(["?"] * len(query.levels))
                conditions.append(f"level IN ({placeholders})")
                params.extend(lv.value for lv in query.levels)
            if query.session_id:
                conditions.append("session_id = ?")
                params.append(query.session_id)
            if query.min_priority > 0:
                conditions.append("priority >= ?")
                params.append(query.min_priority)
            if query.max_priority < 1.0:
                conditions.append("priority <= ?")
                params.append(query.max_priority)
            if query.min_significance > 0:
                conditions.append("significance >= ?")
                params.append(query.min_significance)
            if query.max_significance < 1.0:
                conditions.append("significance <= ?")
                params.append(query.max_significance)
            if not query.include_archived:
                conditions.append("is_archived = 0")
            if not query.include_expired:
                conditions.append("(expires_at IS NULL OR expires_at > ?)")
                params.append(datetime.now().isoformat())
            if query.is_pinned is not None:
                conditions.append("is_pinned = ?")
                params.append(1 if query.is_pinned else 0)
            if query.event_type:
                conditions.append("event_type = ?")
                params.append(query.event_type)
            if query.location:
                conditions.append("location = ?")
                params.append(query.location)
            if query.conversation_partner:
                conditions.append("conversation_partner = ?")
                params.append(query.conversation_partner)
            if query.emotional_tone:
                conditions.append("emotional_tone = ?")
                params.append(query.emotional_tone)
            if query.start_time:
                conditions.append("created_at >= ?")
                params.append(query.start_time.isoformat())
            if query.end_time:
                conditions.append("created_at <= ?")
                params.append(query.end_time.isoformat())
            if query.query:
                clean = re.sub(r"[^\w\s]", " ", query.query)
                clean = re.sub(r"\s+", " ", clean).strip()
                if clean:
                    # FTS5 默认 unicode61 分词器把连续中文视为单一 token，
                    # 中文短语/词组匹配会全部落空 —— 这是历史上"检索不到记忆"的根因。
                    # 修复策略：
                    #   1) 拉丁语系：拆词后用 FTS OR 匹配（带引号防语法错误）
                    #   2) 中文：生成字符二元组，用 content LIKE '%bigram%' OR 匹配
                    #   3) 始终保留整串子串 LIKE 兜底，与 JSON 后端 _match_query 语义一致
                    latin_terms = [t for t in clean.split(" ") if re.search(r"[A-Za-z0-9]", t)][:8]
                    cjk_bigrams = self._cjk_bigrams(clean)[:12]
                    like_patterns = []

                    fts_terms = []
                    for term in latin_terms:
                        escaped_term = term.replace('"', '""')
                        fts_terms.append(f'"{escaped_term}"')
                        like_patterns.append(f"%{term}%")

                    for bigram in cjk_bigrams:
                        like_patterns.append(f"%{bigram}%")

                    # 整串兜底（覆盖长子串/精确片段）
                    if clean not in like_patterns:
                        like_patterns.append(f"%{clean}%")

                    or_parts = []
                    if fts_terms:
                        fts_or = " OR ".join(fts_terms)
                        or_parts.append(
                            f"rowid IN (SELECT rowid FROM {self._fts_name} WHERE {self._fts_name} MATCH ?)"
                        )
                        params.append(fts_or)
                    for pattern in like_patterns:
                        or_parts.append("content LIKE ?")
                        params.append(pattern)

                    conditions.append(f"({' OR '.join(or_parts)})")
            if query.tags:
                if query.any_tag:
                    tag_conditions = []
                    for tag in query.tags:
                        tag_conditions.append("tags LIKE ?")
                        params.append(f'%"{tag}"%')
                    conditions.append(f"({' OR '.join(tag_conditions)})")
                else:
                    for tag in query.tags:
                        conditions.append("tags LIKE ?")
                        params.append(f'%"{tag}"%')

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            limit_clause = f"LIMIT {query.limit}"
            offset_clause = f"OFFSET {query.offset}" if query.offset > 0 else ""

            sql = (
                f"SELECT * FROM {self._table_name} WHERE {where_clause} "
                f"ORDER BY {self._order_clause} {limit_clause} {offset_clause}"
            )
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_memory(row) for row in rows]
        except Exception as e:
            logger.error(f"[SQLiteBackend] 查询失败: {e}")
            return []

    async def count(self, user_id: Optional[str] = None, level: Optional[str] = None) -> int:
        if not self.enabled:
            return 0
        try:
            conn = self._get_conn()
            conditions = []
            params = []
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            if level:
                conditions.append("level = ?")
                params.append(level)
            where = " AND ".join(conditions) if conditions else "1=1"
            row = conn.execute(f"SELECT COUNT(*) FROM {self._table_name} WHERE {where}", params).fetchone()
            return row[0]
        except Exception as e:
            logger.error(f"[SQLiteBackend] 计数失败: {e}")
            return 0

    async def count_by_level(self) -> Dict[str, int]:
        """按层级统计记忆数量"""
        if not self.enabled:
            return {}
        try:
            conn = self._get_conn()
            rows = conn.execute(f"SELECT level, COUNT(*) FROM {self._table_name} GROUP BY level").fetchall()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.error(f"[SQLiteBackend] 按层级统计失败: {e}")
            return {}

    async def bulk_save(self, memories: List[MemoryItem]) -> int:
        if not self.enabled:
            return 0
        try:
            conn = self._get_conn()
            placeholders = ", ".join(["?"] * len(COLUMNS))
            columns_str = ", ".join(COLUMNS)
            for memory in memories:
                conn.execute(
                    f"INSERT OR REPLACE INTO {self._table_name} ({columns_str}) VALUES ({placeholders})",
                    self._build_values(memory),
                )
            conn.commit()
            return len(memories)
        except Exception as e:
            logger.error(f"[SQLiteBackend] 批量保存失败: {e}")
            return 0

    async def delete_expired(self) -> int:
        if not self.enabled:
            return 0
        try:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            cursor = conn.execute(
                f"DELETE FROM {self._table_name} WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(f"[SQLiteBackend] 清理了 {count} 条过期记忆")
            return count
        except Exception as e:
            logger.error(f"[SQLiteBackend] 清理过期记忆失败: {e}")
            return 0

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def get_all_ids(self) -> List[str]:
        """获取 SQLite 中所有记忆 ID"""
        if not self.enabled:
            return []
        try:
            conn = self._get_conn()
            rows = conn.execute(f"SELECT id FROM {self._table_name}").fetchall()
            return [row["id"] for row in rows]
        except Exception as e:
            logger.error(f"[SQLiteBackend] 获取全部ID失败: {e}")
            return []

    @staticmethod
    def _cjk_bigrams(text: str) -> List[str]:
        """生成中文二元组用于 LIKE 子串匹配

        "佳喜欢什么颜色" → ["佳喜","喜欢","欢什","什么","么颜","颜色"]
        """
        cjk_runs = re.findall(r"[\u4e00-\u9fff]+", text)
        bigrams: List[str] = []
        for run in cjk_runs:
            if len(run) == 1:
                bigrams.append(run)
            else:
                for i in range(len(run) - 1):
                    bigrams.append(run[i : i + 2])
        return bigrams

    async def vector_search(
        self,
        query_vector: List[float],
        user_id: Optional[str] = None,
        user_ids: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[MemoryItem]:
        """向量相似度搜索 - Python 计算余弦相似度"""
        if not self.enabled:
            return []
        try:
            conn = self._get_conn()
            conditions = ["vector IS NOT NULL AND vector != ''"]
            params = []

            if user_ids:
                placeholders = ", ".join(["?"] * len(user_ids))
                conditions.append(f"user_id IN ({placeholders})")
                params.extend(user_ids)
            elif user_id:
                conditions.append("user_id = ?")
                params.append(user_id)

            where_clause = " AND ".join(conditions)
            sql = f"SELECT * FROM {self._table_name} WHERE {where_clause} ORDER BY priority DESC LIMIT {limit * 3}"
            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return []

            import json as _json

            scored = []
            for row in rows:
                try:
                    stored_vector = _json.loads(row["vector"])
                    if len(stored_vector) != len(query_vector):
                        continue
                    similarity = self._cosine_similarity(query_vector, stored_vector)
                    if similarity >= threshold:
                        item = self._row_to_memory(row)
                        scored.append((item, similarity))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

            scored.sort(key=lambda x: x[1], reverse=True)
            results = [item for item, _ in scored[:limit]]
            return results
        except Exception as e:
            logger.error(f"[SQLiteBackend] 向量搜索失败: {e}")
            return []

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _row_to_memory(self, row) -> Optional[MemoryItem]:
        """将 SQLite 行转换为 MemoryItem"""
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            vector = json.loads(row["vector"]) if row["vector"] else None
            source_str = row["source"] or self._defaults.get("source", "auto_extract")
            try:
                source = MemorySource(source_str)
            except ValueError:
                source = MemorySource.AUTO_EXTRACT

            return MemoryItem(
                id=row["id"],
                content=row["content"],
                level=MemoryLevel(row["level"]),
                priority=row["priority"],
                tags=tags,
                user_id=row["user_id"] or "",
                session_id=row["session_id"] or "",
                group_id=row["group_id"] or "",
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                source=source,
                platform=row["platform"] or "",
                role=row["role"] or self._defaults.get("role", "user"),
                event_type=row["event_type"] or "",
                location=row["location"] or "",
                conversation_partner=row["conversation_partner"] or "",
                emotional_tone=row["emotional_tone"] or "",
                significance=row["significance"],
                metadata=metadata,
                subject=row["subject"] or "",
                predicate=row["predicate"] or "",
                obj=row["obj"] or "",
                vector=vector,
                access_count=row["access_count"] or 0,
                last_accessed=row["last_accessed"],
                is_archived=bool(row["is_archived"]),
                is_pinned=bool(row["is_pinned"]),
            )
        except Exception as e:
            logger.error(f"[SQLiteBackend] 行转换失败: {e}")
            return None
