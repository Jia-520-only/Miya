"""
/stats 命令 — 从 config 读取消息
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List

from config.config_utils import get_command_message

logger = logging.getLogger(__name__)


async def execute(args: List[str], context: Any) -> str:
    days = 7
    for arg in args:
        arg = arg.strip()
        if arg.endswith("d"):
            days = int(arg[:-1])
        elif arg.endswith("w"):
            days = int(arg[:-1]) * 7
        elif arg.endswith("m"):
            days = int(arg[:-1]) * 30
        elif arg.isdigit():
            days = int(arg)
    days = max(1, min(365, days))

    lines = [get_command_message("stats_header", days=days)]

    try:
        from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

        store = get_knowledge_store()
        kstats = await store.get_stats()
        lines.append(f"\n知识库: {kstats['total_entries']} 条记录, {len(kstats['categories'])} 个分类")
        if kstats["has_chroma"]:
            lines.append(f"向量存储: ChromaDB ({kstats['chroma_entries']} 条)")
        embed_status = "已启用" if kstats["has_embedding"] else "未启用 (仅关键词搜索)"
        lines.append(f"Embedding: {embed_status}")
    except Exception:
        pass

    try:
        from core.command_system import get_command_registry

        registry = get_command_registry()
        lines.append(f"\n命令系统: {len(registry.get_command_names())} 个可用命令")
    except Exception:
        pass

    faq_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "faq.json"
    if faq_path.exists():
        try:
            import json

            faq_data = json.loads(faq_path.read_text(encoding="utf-8"))
            lines.append(f"FAQ: {len(faq_data.get('entries', {}))} 条")
        except Exception:
            pass

    try:
        import psutil

        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        lines.append(f"\n系统: CPU {cpu:.0f}% | 内存 {mem.percent:.0f}% ({mem.available // (1024**2)}MB 可用)")
    except Exception:
        pass

    lines.append(f"\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
