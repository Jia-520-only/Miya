"""
/admin 命令 — 从 config 读取消息
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, List

from config.config_utils import get_command_message

logger = logging.getLogger(__name__)

ADMIN_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "admin_list.json"


def _load() -> dict:
    if ADMIN_FILE.exists():
        try:
            return json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"admins": []}


def _save(data: dict) -> None:
    ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ADMIN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ADMIN_FILE)


async def execute(args: List[str], context: Any) -> str:
    subcommand = getattr(context, "subcommand", "")
    data = _load()
    admins = data.get("admins", [])

    if subcommand in ("ls", "list", ""):
        superadmin = str(context.superadmin_qq) if hasattr(context, "superadmin_qq") else ""
        lines = [get_command_message("admin_list_header")]
        if superadmin:
            lines.append(get_command_message("admin_superadmin", qq=superadmin))
        if admins:
            for a in admins:
                lines.append(get_command_message("admin_item", qq=a))
        else:
            lines.append(get_command_message("admin_empty"))
        return "\n".join(lines)

    elif subcommand == "add":
        if not context.check_permission("superadmin"):
            return get_command_message("permission_denied", command="admin", permission="superadmin")
        target = (args[1] if len(args) > 1 else args[0] if args else "").strip().lstrip("@")
        if not target.isdigit():
            return get_command_message("admin_invalid_qq", qq=target)
        if target in admins:
            return get_command_message("admin_already", qq=target)
        admins.append(target)
        data["admins"] = admins
        _save(data)
        return get_command_message("admin_added", qq=target)

    elif subcommand == "del":
        if not context.check_permission("superadmin"):
            return get_command_message("permission_denied", command="admin", permission="superadmin")
        target = (args[1] if len(args) > 1 else args[0] if args else "").strip().lstrip("@")
        if target not in admins:
            return get_command_message("admin_not_admin", qq=target)
        admins.remove(target)
        data["admins"] = admins
        _save(data)
        return get_command_message("admin_deleted", qq=target)

    return f"未知子命令: {subcommand}"
