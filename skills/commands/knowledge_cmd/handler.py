"""
/knowledge 命令 — 从 config 读取消息
"""

from __future__ import annotations

import logging
from typing import Any, List

from config.config_utils import get_command_message, get_text_message

logger = logging.getLogger(__name__)


async def execute(args: List[str], context: Any) -> str:
    subcommand = getattr(context, "subcommand", "")
    try:
        from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

        store = get_knowledge_store()
    except Exception:
        return get_text_message("knowledge_base", "not_ready")

    if subcommand == "search" or (not subcommand and args):
        query = " ".join(args[1:] if subcommand == "search" and len(args) > 1 else args)
        if not query:
            return "请提供搜索关键词"
        results = await store.search_semantic(query, limit=8)
        if not results:
            results = await store.search_keyword(query, limit=8)
        if not results:
            return get_text_message("knowledge_base", "no_results", query=query, total=0)
        lines = [get_text_message("knowledge_base", "search_header", query=query, count=len(results))]
        for i, r in enumerate(results):
            lines.append(f"{i + 1}. [{r['category']}] {r['title']}")
            lines.append(f"   {r['content'][:150]}...")
            lines.append(f"   ID: `{r['id']}`")
        return "\n".join(lines)

    elif subcommand == "add":
        if not context.check_permission("admin"):
            return get_text_message("knowledge_base", "add_denied")
        full = " ".join(args)
        parts = full.split("|", 1)
        title = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else title
        knowledge_id = await store.add(content=content, title=title, source="斜杠命令")
        return get_command_message("knowledge_added", id=knowledge_id, title=title)

    elif subcommand == "del":
        if not context.check_permission("admin"):
            return get_text_message("knowledge_base", "delete_denied")
        kid = args[1] if len(args) > 1 else args[0] if args else ""
        if await store.delete(kid):
            return get_text_message("knowledge_base", "deleted", knowledge_id=kid)
        return get_text_message("knowledge_base", "not_found", knowledge_id=kid)

    elif subcommand == "categories":
        cats = await store.list_categories()
        if not cats:
            return get_text_message("knowledge_base", "no_categories")
        return get_text_message("knowledge_base", "categories_header", count=len(cats), categories=", ".join(cats))

    else:
        stats = await store.get_stats()
        lines = [get_text_message("knowledge_base", "stats_header")]
        lines.append(get_text_message("knowledge_base", "stats_total", total=stats["total_entries"]))
        lines.append(get_text_message("knowledge_base", "stats_categories", count=len(stats["categories"])))
        chroma_label = get_text_message(
            "knowledge_base", "stats_label_chroma_on" if stats["has_chroma"] else "stats_label_chroma_off"
        )
        lines.append(
            get_text_message("knowledge_base", "stats_chroma", mode=chroma_label, count=stats.get("chroma_entries", 0))
        )
        embed_label = get_text_message(
            "knowledge_base", "stats_label_semantic_on" if stats["has_embedding"] else "stats_label_semantic_off"
        )
        lines.append(get_text_message("knowledge_base", "stats_embedding", status=embed_label))
        if stats["categories"]:
            lines.append("分类分布:")
            for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
                lines.append(f"  {cat}: {count} 条")
        return "\n".join(lines)
