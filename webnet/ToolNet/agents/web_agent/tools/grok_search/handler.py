"""
Grok搜索工具 - web_agent专用
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """执行Grok搜索"""
    query = args.get("query", "").strip()

    if not query:
        return "请提供搜索内容"

    from webnet.ToolNet.tools.network.grok_search import search_grok

    return await search_grok(query)
