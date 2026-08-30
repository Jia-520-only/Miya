"""
/feedback 命令 — 从 config 读取消息
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, List

from config.config_utils import get_command_message

logger = logging.getLogger(__name__)

FB_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "feedback.json"


def _load() -> dict:
    if FB_FILE.exists():
        try:
            return json.loads(FB_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": {}, "next_id": 1}


def _save(data: dict) -> None:
    FB_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, FB_FILE)


async def execute(args: List[str], context: Any) -> str:
    subcommand = getattr(context, "subcommand", "")

    if subcommand == "add" or (not subcommand and args):
        content = " ".join(args[1:] if subcommand == "add" and len(args) > 1 else args)
        if not content:
            return get_command_message("feedback_add_hint")
        data = _load()
        fb_id = datetime.now().strftime("%Y%m%d") + f"-{data['next_id']}"
        data["entries"][fb_id] = {
            "id": fb_id,
            "content": content,
            "sender_id": str(context.sender_id),
            "group_id": str(context.group_id) if context.group_id else "",
            "scope": context.scope,
            "created_at": datetime.now().isoformat(),
        }
        data["next_id"] += 1
        _save(data)
        return get_command_message("feedback_submitted", id=fb_id)

    elif subcommand == "del":
        if not context.check_permission("superadmin"):
            return get_command_message("permission_denied", command="feedback", permission="superadmin")
        fb_id = args[1] if len(args) > 1 else args[0] if args else ""
        data = _load()
        if fb_id not in data["entries"]:
            return get_command_message("feedback_not_found", id=fb_id)
        data["entries"].pop(fb_id)
        _save(data)
        return get_command_message("feedback_deleted", id=fb_id)

    else:
        data = _load()
        entries = sorted(data["entries"].values(), key=lambda x: x.get("created_at", ""), reverse=True)[:20]
        if not entries:
            return get_command_message("feedback_empty")
        is_superadmin = context.check_permission("superadmin")
        lines = [get_command_message("feedback_list_header")]
        for e in entries:
            prefix = f"  [{e['id']}] (来自 {e.get('sender_id', '?')}) " if is_superadmin else f"  [{e['id']}] "
            lines.append(f"{prefix}{e['content'][:80]}")
        return "\n".join(lines)
