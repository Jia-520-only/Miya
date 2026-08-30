# -*- coding: utf-8 -*-
"""重装电脑后恢复弥娅记忆：从记忆文件 + 旧数据库备份 + 每周备份重建索引与 SQLite 库。

用法（必须先停止弥娅守护进程）：
    python scripts/restore_memory_from_backup.py [--dry-run]
"""
import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEM_DIR = ROOT / "data" / "memory"
DB_PATH = MEM_DIR / "miya_memory.db"
INDEX_PATH = MEM_DIR / "index.json"
TAG_INDEX_PATH = MEM_DIR / "tag_index.json"
OLD_DB = ROOT / "data" / "backups" / "miya_memory_before_identity_merge_20260817_195556.db"
WEEKLY_DIR = MEM_DIR / "backups"
LEVEL_DIRS = ["dialogue", "short_term", "long_term", "semantic", "knowledge"]

COLUMNS = [
    "id", "content", "level", "priority", "user_id", "session_id", "group_id",
    "tags", "created_at", "expires_at", "source", "platform", "role",
    "event_type", "location", "conversation_partner", "emotional_tone",
    "significance", "metadata", "subject", "predicate", "obj", "vector",
    "access_count", "last_accessed", "is_archived", "is_pinned",
]
JSON_LIST_COLS = {"tags"}
JSON_DICT_COLS = {"metadata"}


def norm_field(col: str, v):
    if v is None:
        # expires_at 必须为 NULL 而非 ''：查询过滤 (expires_at IS NULL OR expires_at > ?)
        # 会把 '' 判为已过期，导致记忆被整体过滤
        return None if col in ("expires_at", "last_accessed") else ""
    if col in JSON_LIST_COLS and isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    if col in JSON_DICT_COLS and isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    if col in ("vector",) and isinstance(v, list):
        return json.dumps(v)
    if col in ("is_archived", "is_pinned") and isinstance(v, bool):
        return 1 if v else 0
    return v


def row_from_record(rec: dict):
    return tuple(norm_field(c, rec.get(c, "")) for c in COLUMNS)


def load_file_records():
    """扫描所有记忆文件，返回 (records, index_entries)"""
    records, index_entries = {}, {}
    for level in LEVEL_DIRS:
        for fp in glob.glob(str(MEM_DIR / level / "**" / "*.json"), recursive=True):
            try:
                d = json.load(open(fp, encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict) or not d.get("id") or not d.get("content"):
                continue
            records[d["id"]] = d
            index_entries[d["id"]] = {
                "level": d.get("level", level),
                "user_id": d.get("user_id", ""),
                "session_id": d.get("session_id", ""),
                "group_id": d.get("group_id", ""),
                "tags": d.get("tags", []),
                "created_at": d.get("created_at", ""),
                "file_path": str(Path(fp).resolve()),
                "priority": d.get("priority", 0.5),
            }
    return records, index_entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records, index_entries = load_file_records()
    print(f"[1/4] 扫描记忆文件: {len(records)} 条有效记录")

    # 旧数据库（8月17日 identity merge 前的完整库）
    old_db_rows = 0
    if OLD_DB.exists():
        src = sqlite3.connect(str(OLD_DB))
        cur = src.execute(f"SELECT {', '.join(COLUMNS)} FROM memories")
        for row in cur:
            rid = row[0]
            if rid not in records:
                records[rid] = dict(zip(COLUMNS, row, strict=True))
                old_db_rows += 1
        src.close()
    print(f"[2/4] 从旧库补充（文件中缺失的）: {old_db_rows} 条")

    # 每周备份（含向量），补充文件中缺失的
    weekly_rows = 0
    for wf in sorted(WEEKLY_DIR.glob("*.json")):
        try:
            items = json.load(open(wf, encoding="utf-8"))
        except Exception:
            continue
        for it in items if isinstance(items, list) else []:
            rid = it.get("id")
            if rid and rid not in records:
                records[rid] = it
                weekly_rows += 1
    print(f"[3/4] 从每周备份补充: {weekly_rows} 条, 总计 {len(records)} 条")

    if args.dry_run:
        dates = sorted(str(r.get("created_at", ""))[:10] for r in records.values() if r.get("created_at"))
        print(f"[dry-run] 日期范围: {dates[0]} ~ {dates[-1]}")
        print("[dry-run] 未写入任何数据")
        return

    # 写 SQLite
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("BEGIN")
    ph = ", ".join(["?"] * len(COLUMNS))
    cols = ", ".join(COLUMNS)
    n = 0
    for rid, rec in records.items():
        conn.execute(f"INSERT OR REPLACE INTO memories ({cols}) VALUES ({ph})", row_from_record(rec))
        n += 1
    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
    conn.commit()
    total, lo, hi = conn.execute(
        "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM memories").fetchone()
    conn.close()
    print(f"[4/4] SQLite 写入 {n} 条, 现共 {total} 条 ({lo[:10]} ~ {hi[:10]})")

    # 重建 index.json / tag_index.json（仅文件能提供 file_path）
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index_entries, f, ensure_ascii=False, indent=2)
    tag_index = {}
    for rid, e in index_entries.items():
        for t in e.get("tags", []):
            tag_index.setdefault(t, []).append(rid)
    with open(TAG_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(tag_index, f, ensure_ascii=False, indent=2)
    print(f"索引重建完成: {len(index_entries)} 条索引, {len(tag_index)} 个标签")
    print("\n完成！请重新启动弥娅守护进程。")


if __name__ == "__main__":
    sys.exit(main())
