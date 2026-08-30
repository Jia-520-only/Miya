"""
AstrBot 依赖迁移脚本

将 *_astrbot 模块的 astrbot.core 依赖迁移到 core.astrbot_compat
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# 迁移映射表
IMPORT_MAPPING = {
    # 核心模块
    "from astrbot.core import logger": "from core.astrbot_compat import logger",
    "from astrbot.core import astrbot_config": "from core.astrbot_compat import astrbot_config",
    "from astrbot.core import sp": "from core.astrbot_compat import sp",
    "from astrbot.core import DEMO_MODE": "from core.astrbot_compat import DEMO_MODE",
    "from astrbot.core import VERSION": "from core.astrbot_compat import VERSION",
    # 数据库
    "from astrbot.core.db import BaseDatabase": "from core.astrbot_compat.db import BaseDatabase",
    # 工具函数
    "from astrbot.core.utils.astrbot_path import get_astrbot_root": "from core.astrbot_compat.utils import get_astrbot_root",
    "from astrbot.core.utils.astrbot_path import get_astrbot_data_path": "from core.astrbot_compat.utils import get_astrbot_data_path",
    "from astrbot.core.utils.astrbot_path import get_astrbot_temp_path": "from core.astrbot_compat.utils import get_astrbot_temp_path",
    "from astrbot.core.utils.datetime_utils import normalize_datetime_utc": "from core.astrbot_compat.utils import normalize_datetime_utc",
    "from astrbot.core.utils.error_redaction import safe_error": "from core.astrbot_compat.utils import safe_error",
    # 配置管理
    "from astrbot.core.astrbot_config_mgr import AstrBotConfigManager": "from core.astrbot_compat import AstrBotConfigManager",
}

# 多行导入模式
MULTILINE_PATTERNS = [
    # 匹配 from astrbot.core import (xxx, yyy, zzz)
    (r"from astrbot\.core import \(([^)]+)\)", "from core.astrbot_compat import (\\1)"),
    # 匹配 from astrbot.core.utils.astrbot_path import (xxx, yyy)
    (
        r"from astrbot\.core\.utils\.astrbot_path import \(([^)]+)\)",
        "from core.astrbot_compat.utils import (\\1)",
    ),
]


def migrate_file(file_path: Path) -> Tuple[bool, List[str]]:
    """
    迁移单个文件

    Returns:
        (是否修改, 修改列表)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, [f"Error reading {file_path}: {e}"]

    original_content = content
    changes = []

    # 应用简单映射
    for old_import, new_import in IMPORT_MAPPING.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            changes.append(f"  {old_import} -> {new_import}")

    # 应用多行模式
    for pattern, replacement in MULTILINE_PATTERNS:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            changes.append("  Multi-line import migrated")

    # 如果有修改，写入文件
    if content != original_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, changes
        except Exception as e:
            return False, [f"Error writing {file_path}: {e}"]

    return False, []


def migrate_directory(directory: Path) -> Dict[str, List[str]]:
    """
    迁移目录中的所有 Python 文件

    Returns:
        {文件路径: 修改列表}
    """
    results = {}

    # 只处理 *_astrbot 目录
    for astrbot_dir in directory.glob("*_astrbot"):
        if not astrbot_dir.is_dir():
            continue

        # 跳过某些目录（如 db_astrbot，因为它本身就是数据库实现）
        if astrbot_dir.name in ["db_astrbot"]:
            continue

        for py_file in astrbot_dir.rglob("*.py"):
            modified, changes = migrate_file(py_file)
            if modified:
                results[str(py_file)] = changes

    return results


def main():
    """主函数"""
    # 获取 core 目录
    core_dir = Path(__file__).parent.parent

    print(f"Migrating AstrBot dependencies in: {core_dir}")
    print("=" * 60)

    # 执行迁移
    results = migrate_directory(core_dir)

    if not results:
        print("No files were modified.")
        return

    # 输出结果
    total_files = len(results)
    total_changes = sum(len(changes) for changes in results.values())

    print(f"\nMigrated {total_files} files with {total_changes} changes:")
    print("-" * 60)

    for file_path, changes in results.items():
        print(f"\n{file_path}:")
        for change in changes:
            print(change)

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("\nNext steps:")
    print("1. Review the changes")
    print("2. Test the application")
    print("3. Fix any remaining issues")


if __name__ == "__main__":
    main()
