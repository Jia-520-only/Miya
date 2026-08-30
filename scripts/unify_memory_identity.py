"""
统一记忆身份归并脚本 (V4.1.12)
================================

把历史上按平台/入口分裂的 user_id 记忆桶归并到规范 ID（所有者佳 → 1523878699）。

覆盖两个存储后端：
1. SQLite (data/memory/miya_memory.db) — 权威查询引擎
2. JSON 文件 + index.json — 可视化/兜底存储

运行方式:
    python scripts/unify_memory_identity.py            # 归并 + 输出统计
    python scripts/unify_memory_identity.py --dry-run  # 只统计，不修改
    python scripts/unify_memory_identity.py --backup-dir data/backups   # 指定备份目录

身份映射来源: memory/identity_resolver.py ← config/permissions.json
"""

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
LEVEL_DIRS = ["dialogue", "short_term", "long_term", "semantic", "knowledge"]


def build_alias_map():
    """构建 alias → canonical 映射（含所有者占位 ID）"""
    sys.path.insert(0, str(PROJECT_ROOT))
    from memory.identity_resolver import get_identity_resolver

    resolver = get_identity_resolver()
    return resolver._alias_to_canonical, resolver._canonical_to_aliases, resolver.owner_canonical_id


def migrate_sqlite(db_path: Path, alias_to_canonical: dict, dry_run: bool) -> dict:
    if not db_path.exists():
        return {"status": "missing", "moved": 0}

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    total_moved = 0
    details = {}
    for alias, canonical in sorted(alias_to_canonical.items()):
        if alias == canonical:
            continue
        cur.execute("SELECT COUNT(*) FROM memories WHERE user_id = ?", (alias,))
        count = cur.fetchone()[0]
        if count <= 0:
            continue
        details[f"{alias} -> {canonical}"] = count
        if not dry_run:
            cur.execute("UPDATE memories SET user_id = ? WHERE user_id = ?", (canonical, alias))
        total_moved += count

    if not dry_run:
        conn.commit()
    conn.close()
    return {"status": "ok", "moved": total_moved, "details": details}


def migrate_json(alias_to_canonical: dict, dry_run: bool) -> dict:
    index_file = MEMORY_DIR / "index.json"
    if not index_file.exists():
        return {"status": "missing_index", "moved": 0, "renamed_dirs": 0}

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    moved = 0
    renamed_dirs = 0
    for level in LEVEL_DIRS:
        level_dir = MEMORY_DIR / level
        if not level_dir.exists():
            continue
        for alias, canonical in alias_to_canonical.items():
            if alias == canonical:
                continue
            alias_dir = level_dir / alias
            if not alias_dir.is_dir():
                continue
            canonical_dir = level_dir / canonical
            if not dry_run:
                canonical_dir.mkdir(parents=True, exist_ok=True)

            files = list(alias_dir.glob("*.json"))
            for f in files:
                target = canonical_dir / f.name
                if target.exists():
                    # 记忆 ID 全局唯一，目标已存在说明是重复写入，源文件可直接丢弃
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    moved += 1
                    continue
                if not dry_run:
                    shutil.move(str(f), str(target))
                moved += 1

            # 更新 index.json 中该目录下记忆的 user_id / file_path
            alias_dir_str = str(alias_dir)
            for memory_id, info in index.items():
                fp = info.get("file_path", "")
                if not fp:
                    continue
                p = Path(fp)
                if str(p.parent) == alias_dir_str or str(p).startswith(alias_dir_str + "\\"):
                    if not dry_run:
                        info["user_id"] = canonical
                        info["file_path"] = str(canonical_dir / p.name)
            # 目录清空后移除
            if not dry_run:
                remaining = list(alias_dir.iterdir())
                if not remaining:
                    alias_dir.rmdir()
                renamed_dirs += 1
            else:
                renamed_dirs += 1

    if not dry_run:
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    return {"status": "ok", "moved": moved, "renamed_dirs": renamed_dirs}


def main():
    parser = argparse.ArgumentParser(description="统一弥娅记忆身份归并")
    parser.add_argument("--dry-run", action="store_true", help="只统计不修改")
    parser.add_argument("--backup-dir", type=str, default=None, help="备份目录（默认 data/backups）")
    args = parser.parse_args()

    alias_to_canonical, canonical_to_aliases, owner = build_alias_map()
    print("=" * 64)
    print("弥娅记忆身份归并 (V4.1.12)")
    print("=" * 64)
    print(f"所有者规范 ID: {owner or '未配置'}")
    print(f"别名映射: {len(alias_to_canonical)} 条")
    for alias, canonical in sorted(alias_to_canonical.items()):
        if alias != canonical:
            print(f"  {alias!r} -> {canonical!r}")
    print()

    if args.dry_run:
        print(">>> DRY RUN 模式：只统计，不修改数据 <<<\n")

    # 备份 SQLite
    db_path = MEMORY_DIR / "miya_memory.db"
    if db_path.exists() and not args.dry_run:
        backup_dir = Path(args.backup_dir) if args.backup_dir else PROJECT_ROOT / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"miya_memory_before_identity_merge_{stamp}.db"
        print(f"备份 SQLite → {backup_path}")
        shutil.copy2(str(db_path), str(backup_path))

        index_backup = backup_dir / f"index_before_identity_merge_{stamp}.json"
        if (MEMORY_DIR / "index.json").exists():
            shutil.copy2(str(MEMORY_DIR / "index.json"), str(index_backup))
            print(f"备份 index.json → {index_backup}")
        print()

    # 1) SQLite 归并
    sqlite_result = migrate_sqlite(db_path, alias_to_canonical, args.dry_run)
    print(f"[SQLite] 归并结果: {sqlite_result}")
    if sqlite_result.get("details"):
        for k, v in sqlite_result["details"].items():
            print(f"  {k}: {v} 条")
    print()

    # 2) JSON 归并
    json_result = migrate_json(alias_to_canonical, args.dry_run)
    print(f"[JSON] 归并结果: {json_result}")
    print()

    # 3) 归并后分布
    if not args.dry_run and db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT user_id, COUNT(*) FROM memories GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 12")
        print("归并后 user_id 分布 (前12):")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
        conn.close()

    if args.dry_run:
        print("\n>>> DRY RUN 完成，未修改任何数据。去掉 --dry-run 执行真实归并。")


if __name__ == "__main__":
    main()
