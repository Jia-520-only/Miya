"""持久生命事件日志；独立于对话记忆，保留行动证据与会话范围。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from core.miya_intention import life_scope, project_intention
from core.miya_life_event import LifeEventType, MiyaEvent


def default_journal_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "memory" / "life_events.sqlite3"


def normalize_group(value) -> str:
    group = str(value or "")
    return "" if group in {"0", "None", "null"} else group


class LifeEventJournal:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS life_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS life_scope
                ON life_events(platform, user_id, group_id, event_type, sequence)
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(life_events)")}
            if "session_id" not in columns:
                conn.execute("ALTER TABLE life_events ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS life_intentions (
                    intention_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    data TEXT NOT NULL
                )
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=0.25)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def append(self, event: MiyaEvent) -> bool:
        # 不持久化不可序列化的运行时对象；调用方可捕获失败并继续主流程。
        data = json.dumps(event.to_dict(), ensure_ascii=False, allow_nan=False)
        payload = event.payload
        user_id = event.actor if event.event_type == LifeEventType.USER_MESSAGE else payload.get("user_id", "")
        scope = life_scope({**payload, "user_id": user_id, "platform": payload.get("platform") or event.source})
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO life_events
                   (event_id, event_type, platform, user_id, group_id, data, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.event_type, str(payload.get("platform") or event.source),
                 str(user_id or ""), normalize_group(payload.get("group_id")), data, scope["session_id"]),
            )
            if cursor.rowcount != 1:
                return False
            intention_id = payload.get("intention_id")
            if intention_id:
                row = conn.execute(
                    "SELECT data FROM life_intentions WHERE intention_id = ?", (intention_id,),
                ).fetchone()
                record = project_intention(json.loads(row[0]) if row else None, event)
                if record is not None:
                    conn.execute(
                        """INSERT INTO life_intentions VALUES (?, ?, ?, ?)
                           ON CONFLICT(intention_id) DO UPDATE SET
                           status=excluded.status, updated_at=excluded.updated_at, data=excluded.data""",
                        (intention_id, record["status"], record["updated_at"],
                         json.dumps(record, ensure_ascii=False, allow_nan=False)),
                    )
            return True

    def load_intentions(self) -> list[dict]:
        """未完成事项独立于最近 200 条事件；只限制已收尾事项的热缓存。"""
        with self._connect() as conn:
            active = conn.execute(
                "SELECT data FROM life_intentions WHERE status NOT IN ('completed', 'abandoned')",
            ).fetchall()
            recent = conn.execute(
                """SELECT data FROM life_intentions WHERE status IN ('completed', 'abandoned')
                   ORDER BY updated_at DESC LIMIT 200""",
            ).fetchall()
        return [json.loads(row[0]) for row in active + recent]

    def recent(self, limit: int = 200) -> list[MiyaEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM life_events ORDER BY sequence DESC LIMIT ?", (max(0, min(limit, 200)),),
            ).fetchall()
        return [MiyaEvent.from_dict(json.loads(row[0])) for row in reversed(rows)]

    def recall_actions(
        self, *, user_id: str, platform: str, group_id: str = "", session_id: str = "",
        query: str = "", limit: int = 5,
    ) -> list[dict]:
        # 缺少明确范围时不做全局召回。
        if not user_id or not platform or platform == "unknown":
            return []
        scope = life_scope(dict(user_id=user_id, platform=platform, group_id=group_id, session_id=session_id))
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT data FROM life_events
                   WHERE platform = ? AND user_id = ? AND group_id = ? AND event_type = ? AND session_id = ?
                   ORDER BY sequence DESC LIMIT ?""",
                (platform, str(user_id), normalize_group(group_id), LifeEventType.ACTION_RESULT,
                 scope["session_id"], 100 if query.strip() else max(0, min(limit, 20))),
            ).fetchall()
        events = [json.loads(row[0]) for row in reversed(rows)]
        if not query.strip():
            return events
        # 小规模候选做词项匹配；中文采用相邻双字，不把无关的最新回执强行带入上下文。
        import re

        terms = set(re.findall(r"[a-zA-Z0-9_]{2,}", query.lower()))
        for phrase in re.findall(r"[\u4e00-\u9fff]+", query):
            terms.update(phrase[index:index + 2] for index in range(len(phrase) - 1))
        ranked = []
        for index, event in enumerate(events):
            payload = event["payload"]
            text = json.dumps({"action": payload.get("action"), "result": payload.get("result")},
                              ensure_ascii=False).lower()
            overlap = sum(term in text for term in terms)
            if overlap:
                ranked.append((overlap, index, event))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = ranked[:max(0, min(limit, 20))]
        return [item[2] for item in sorted(selected, key=lambda item: item[1])]
