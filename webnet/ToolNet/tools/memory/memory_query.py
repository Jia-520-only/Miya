"""
弥娅记忆查询工具 - QQ端

提供记忆统计、搜索、查看等功能
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class MemoryQueryTool(BaseTool):
    """记忆查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_query",
            "description": """记忆查询工具，用于查看弥娅的记忆状态。

可用功能：
1. 统计 - 查看记忆总数、各层级数量、用户数
2. 搜索 - 搜索记忆内容
3. 用户 - 查看特定用户的记忆
4. 最近 - 查看最近的记忆
5. 标签 - 查看热门标签

使用方式：
- 记忆统计 / 记忆有多少 / 记得什么
- 记忆搜索 [关键词]
- 记忆用户 [用户ID]
- 记忆最近 [数量]
- 记忆标签 / 热门标签""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型: stats/search/user/recent/tags",
                        "enum": ["stats", "search", "user", "recent", "tags"],
                    },
                    "query": {"type": "string", "description": "搜索关键词或用户ID"},
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制",
                        "default": 10,
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行记忆查询"""
        action = args.get("action", "stats")
        query = args.get("query", "")
        limit = args.get("limit", 10)

        try:
            # 获取用户ID
            user_id = context.sender_id if hasattr(context, "sender_id") else query

            if action == "stats":
                return await self._get_stats()
            elif action == "search":
                return await self._search_memory(query, limit)
            elif action == "user":
                return await self._get_user_memory(user_id, limit)
            elif action == "recent":
                return await self._get_recent(limit)
            elif action == "tags":
                return await self._get_tags()
            else:
                return "未知操作类型"
        except Exception as e:
            logger.error(f"记忆查询失败: {e}")
            return f"查询失败: {str(e)[:100]}"

    async def _get_stats(self) -> str:
        """获取统计"""
        from memory import get_memory_core

        core = await get_memory_core("data/memory")
        stats = await core.get_statistics()

        total = stats.get("total_cached", 0)
        by_level = stats.get("by_level", {})
        user_count = stats.get("by_user", 0)
        tag_count = stats.get("by_tag", 0)

        lines = ["📊 记忆统计", "=" * 30]
        lines.append(f"总记忆数: {total}")
        lines.append(f"用户数: {user_count}")
        lines.append(f"标签数: {tag_count}")
        lines.append("")
        lines.append("📁 层级分布:")

        for level, count in sorted(by_level.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  {level:12} {count:4} ({pct:.1f}%)")

        return "\n".join(lines)

    async def _search_memory(self, keyword: str, limit: int) -> str:
        """搜索记忆"""
        if not keyword:
            return "请提供搜索关键词"

        from memory import get_memory_core

        core = await get_memory_core("data/memory")

        results = await core.retrieve(query=keyword, limit=limit)

        if not results:
            return f"未找到关于「{keyword}」的记忆"

        lines = [f"🔍 搜索「{keyword}」找到 {len(results)} 条", "=" * 40]

        for i, mem in enumerate(results[:10], 1):
            content = mem.content[:60] + "..." if len(mem.content) > 60 else mem.content
            tags = " ".join(f"[{t}]" for t in mem.tags[:3]) if mem.tags else ""
            lines.append(f"{i}. {content}")
            if tags:
                lines.append(f"   {tags}")

        return "\n".join(lines)

    async def _get_user_memory(self, user_id: str, limit: int) -> str:
        """获取用户记忆"""
        if not user_id:
            return "请指定用户ID"

        from memory import get_memory_core

        core = await get_memory_core("data/memory")

        results = await core.search_by_user(user_id, limit=limit)

        if not results:
            return f"未找到用户 {user_id} 的记忆"

        by_level = {}
        for mem in results:
            lvl = mem.level.value
            by_level[lvl] = by_level.get(lvl, 0) + 1

        lines = [f"👤 用户 {user_id} 的记忆 ({len(results)}条)", "=" * 40]
        lines.append(f"层级分布: {by_level}")
        lines.append("")

        for mem in results[:5]:
            content = mem.content[:50] + "..." if len(mem.content) > 50 else mem.content
            lines.append(f"• {content}")

        if len(results) > 5:
            lines.append(f"... 还有 {len(results) - 5} 条")

        return "\n".join(lines)

    async def _get_recent(self, limit: int) -> str:
        """获取最近记忆"""
        from memory import get_memory_core
        from memory.core import MemoryQuery

        core = await get_memory_core("data/memory")

        q = MemoryQuery(query="", limit=limit, sort_by="created_at", sort_order="desc")
        sorted_mems = await core.retrieve(q)

        if not sorted_mems:
            return "暂无记忆"

        lines = [f"📝 最近 {len(sorted_mems)} 条记忆", "=" * 40]

        for i, mem in enumerate(sorted_mems, 1):
            content = mem.content[:50] + "..." if len(mem.content) > 50 else mem.content
            user = mem.user_id[:8] if mem.user_id else "unknown"
            lines.append(f"{i}. [{mem.level.value}] {content}")
            lines.append(f"   👤{user} | {mem.created_at[:16]}")

        return "\n".join(lines)

    async def _get_tags(self) -> str:
        """获取热门标签 - 使用内存索引统计，避免全量加载"""
        from memory import get_memory_core

        core = await get_memory_core("data/memory")

        tag_counts = {}
        for tag, mem_ids in core._tag_index.items():
            tag_counts[tag] = len(mem_ids)

        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:20]

        if not sorted_tags:
            return "暂无标签"

        lines = ["🏷️ 热门标签", "=" * 40]

        for tag, count in sorted_tags:
            lines.append(f"  {tag} ({count})")

        return "\n".join(lines)


# 注册工具
TOOL_CLASS = MemoryQueryTool
