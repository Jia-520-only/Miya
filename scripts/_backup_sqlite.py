"""弥娅 SQLite 数据库一致性备份（在线热备份，不依赖停服）。

用法: python scripts/_backup_sqlite.py <build_root>
从项目根运行，将各数据库通过 sqlite3 backup API 写入 <build_root>。
"""
import os
import sqlite3
import sys

PAIRS = [
    (r"data\memory\miya_memory.db", r"core\data\memory\miya_memory.db"),
    (r"data\miya.db", r"core\data\miya.db"),
    (r"data\messages.db", r"core\data\messages.db"),
    (r"data\tasks.db", r"core\data\tasks.db"),
    (r"data\auth.db", r"core\data\auth.db"),
    (r"data\cognition_cache.db", r"core\data\cognition_cache.db"),
    (r"data\blog\blog.db", r"core\data\blog\blog.db"),
    (r".miya\database.db", r"core\.miya\database.db"),
]


def main() -> int:
    root = os.getcwd()
    build = sys.argv[1]
    ok = fail = 0
    for src_rel, dst_rel in PAIRS:
        src = os.path.join(root, src_rel)
        dst = os.path.join(build, dst_rel)
        if not os.path.exists(src):
            print("SKIP (不存在):", src_rel)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
                s.backup(d)
            ok += 1
            print("OK  :", src_rel)
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print("FAIL:", src_rel, "->", exc)
    print(f"完成: 成功 {ok} 个, 失败 {fail} 个")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
