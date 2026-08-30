"""
/faq 命令 — 从 config 读取消息
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

FAQ_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "faq.json"


def _load_faq() -> dict:
    if FAQ_FILE.exists():
        try:
            return json.loads(FAQ_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": {}, "next_id": 1}


def _save_faq(data: dict) -> None:
    FAQ_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FAQ_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, FAQ_FILE)


async def execute(args: List[str], context: Any) -> str:
    subcommand = getattr(context, "subcommand", "") or (args[0] if args else "")

    if subcommand in ("ls", "list", ""):
        data = _load_faq()
        entries = list(data["entries"].values())[:20]
        if not entries:
            return get_command_message("faq_empty")
        lines = [get_command_message("faq_list_header")]
        for e in entries:
            lines.append(f"  [{e['id']}] {e['question'][:60]}")
        return "\n".join(lines)

    elif subcommand == "view":
        faq_id = args[1] if len(args) > 1 else args[0] if args else ""
        data = _load_faq()
        entry = data["entries"].get(faq_id)
        if not entry:
            return get_command_message("faq_not_found", id=faq_id)
        return f"【FAQ: {faq_id}】\n问: {entry['question']}\n答: {entry['answer']}"

    elif subcommand == "search":
        keyword = " ".join(args[1:] if len(args) > 1 else args)
        if not keyword:
            return "请提供搜索关键词"
        data = _load_faq()
        results = [
            e
            for e in data["entries"].values()
            if keyword.lower() in e["question"].lower() or keyword.lower() in e.get("answer", "").lower()
        ]
        if not results:
            return get_command_message("faq_no_results", keyword=keyword)
        lines = [get_command_message("faq_search_header", keyword=keyword, count=len(results))]
        for r in results[:10]:
            lines.append(f"  [{r['id']}] {r['question'][:60]}")
            lines.append(f"    {r.get('answer', '')[:100]}...")
        return "\n".join(lines)

    elif subcommand == "add":
        if not context.check_permission("admin"):
            return get_command_message("permission_denied", command="faq", permission="admin")
        full_text = " ".join(args[1:] if len(args) > 1 else args)
        parts = full_text.split("|", 1)
        question = parts[0].strip()
        answer = parts[1].strip() if len(parts) > 1 else ""
        if not question:
            return get_command_message("faq_usage")
        data = _load_faq()
        faq_id = datetime.now().strftime("%Y%m%d") + f"-{data['next_id']:03d}"
        data["entries"][faq_id] = {
            "id": faq_id,
            "question": question,
            "answer": answer,
            "created_by": str(context.sender_id),
            "created_at": datetime.now().isoformat(),
        }
        data["next_id"] += 1
        _save_faq(data)
        return get_command_message("faq_added", id=faq_id, question=question)

    elif subcommand == "del":
        if not context.check_permission("admin"):
            return get_command_message("permission_denied", command="faq", permission="admin")
        faq_id = args[1] if len(args) > 1 else args[0] if args else ""
        data = _load_faq()
        if faq_id not in data["entries"]:
            return get_command_message("faq_not_found", id=faq_id)
        entry = data["entries"].pop(faq_id)
        _save_faq(data)
        return get_command_message("faq_deleted", id=faq_id, question=entry["question"])

    return get_command_message("faq_unknown_sub", sub=subcommand)
