"""
QQ端记忆查询快捷命令

用户可以通过以下命令查询记忆（配置在 qq_command_config.json 中）：
- /记忆统计 - 查看记忆总数
- /记忆搜索 [关键词] - 搜索记忆
- /记忆最近 - 查看最近记忆
- /记忆标签 - 查看热门标签
- /我的记忆 - 查看自己的记忆
"""

from typing import Optional

from core.text_loader import get_text


async def _get_memory_core():
    """获取记忆核心"""
    from memory import get_memory_core, DEFAULT_MEMORY_DIR

    return await get_memory_core(DEFAULT_MEMORY_DIR)


def _get_memory_aliases():
    """从 text_config.json 获取记忆命令别名"""
    from core.text_loader import get_command_keywords

    cmd = get_command_keywords()
    return {
        "stats": cmd.get("memory_stats", []),
        "search": cmd.get("memory_search", []),
        "recent": cmd.get("memory_recent", []),
        "tags": cmd.get("memory_tags", []),
        "my": cmd.get("memory_my", []),
    }


class MemoryCommandHandler:
    """记忆命令处理器"""

    def __init__(self):
        self.core = None
        self._memory_aliases = None

    def _get_aliases(self):
        """获取记忆命令别名缓存"""
        if self._memory_aliases is None:
            self._memory_aliases = _get_memory_aliases()
        return self._memory_aliases

    async def _get_core(self):
        """获取记忆核心"""
        if self.core is None:
            self.core = await _get_memory_core()
        return self.core

    async def handle(self, message: str, user_id: str) -> Optional[str]:
        """处理命令"""
        message = message.strip()

        aliases = self._get_aliases()
        is_memory_cmd = False
        for cmd_aliases in aliases.values():
            for alias in cmd_aliases:
                if message.startswith(alias):
                    is_memory_cmd = True
                    break
            if is_memory_cmd:
                break

        if not is_memory_cmd and not message.startswith("/"):
            return None

        action = None
        query = ""
        cmd = message.lstrip("/").strip()

        for cmd_type, cmd_aliases in aliases.items():
            for alias in cmd_aliases:
                if cmd.startswith(alias):
                    action = cmd_type
                    query = cmd.replace(alias, "").strip()
                    break
            if action:
                break

        if not action:
            return None

        try:
            if action == "stats":
                return await self._cmd_stats()
            elif action == "search":
                return await self._cmd_search(query)
            elif action == "recent":
                return await self._cmd_recent()
            elif action == "tags":
                return await self._cmd_tags()
            elif action == "my":
                return await self._cmd_my(user_id)
            else:
                return self._help()
        except Exception as e:
            return f"[ERROR] {str(e)[:50]}"

    async def _cmd_stats(self) -> str:
        """记忆统计"""
        core = await self._get_core()
        stats = await core.get_statistics()

        # 优先使用数据库实际数量，避免缓存未加载时显示 0
        total = max(
            stats.get("total_cached", 0),
            stats.get("total_sqlite", 0),
            stats.get("total_indexed", 0),
        )
        by_level = stats.get("by_level", {})
        # 如果 by_level 全为 0，尝试从 SQLite 统计
        level_total = sum(by_level.values())
        if level_total == 0 and stats.get("total_sqlite", 0) > 0:
            by_level = stats.get("by_level_db", by_level)
        users = stats.get("by_user", 0)

        lines = ["[MEMORY STATS]", "=" * 25]
        lines.append(f"Total: {total}")
        lines.append(f"Users: {users}")
        lines.append("")

        for level, count in sorted(by_level.items(), key=lambda x: -x[1]):
            if count > 0:
                pct = count / max(total, 1) * 100
                bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
                lines.append(f"{level:12} [{bar}] {count}")

        return "\n".join(lines)

    async def _cmd_search(self, keyword: str) -> str:
        """搜索记忆"""
        if not keyword:
            return get_text(
                "memory_responses.search_prompt",
                "请输入搜索关键词，例如: /记忆搜索 蓝色",
            )

        core = await self._get_core()
        results = await core.retrieve(query=keyword, limit=10)

        if not results:
            return f"没有找到 '{keyword}' 相关记忆"

        lines = [f"[SEARCH] '{keyword}' ({len(results)})", "=" * 30]

        for i, mem in enumerate(results, 1):
            content = mem.content[:50] + "..." if len(mem.content) > 50 else mem.content
            tags = " ".join(f"[{t}]" for t in mem.tags[:3]) if mem.tags else ""
            lines.append(f"{i}. {content}")
            if tags:
                lines.append(f"   {tags}")

        return "\n".join(lines)

    async def _cmd_recent(self) -> str:
        """最近记忆"""
        core = await self._get_core()
        results = await core.retrieve(query="", limit=10)

        if not results:
            return get_text("memory_responses.no_memories", "还没有记忆呢~")

        sorted_results = sorted(results, key=lambda x: x.created_at, reverse=True)[:10]

        lines = ["[RECENT MEMORIES]", "=" * 30]

        for i, mem in enumerate(sorted_results, 1):
            content = mem.content[:40] + "..." if len(mem.content) > 40 else mem.content
            time = mem.created_at[5:16] if len(mem.created_at) > 16 else mem.created_at
            lines.append(f"{i}. {content}")
            lines.append(f"   [{mem.level.value}] {time}")

        return "\n".join(lines)

    async def _cmd_tags(self) -> str:
        """热门标签"""
        core = await self._get_core()
        results = await core.retrieve(query="", limit=1000)

        tag_counts = {}
        for mem in results:
            for tag in mem.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:15]

        if not sorted_tags:
            return get_text("memory_responses.no_tags", "还没有标签呢~")

        lines = ["[TAGS]", "=" * 30]

        for tag, count in sorted_tags:
            lines.append(f"  {tag} ({count})")

        return "\n".join(lines)

    async def _cmd_my(self, user_id: str) -> str:
        """我的记忆"""
        if not user_id:
            return get_text("memory_responses.cannot_identify_user", "无法识别用户")

        core = await self._get_core()
        results = await core.search_by_user(user_id, limit=10)

        if not results:
            return get_text("memory_responses.user_no_memories", "你还没有记忆呢~")

        by_level = {}
        for mem in results:
            lvl = mem.level.value
            by_level[lvl] = by_level.get(lvl, 0) + 1

        lines = [f"[YOUR MEMORIES] ({len(results)})", "=" * 30]
        lines.append(f"Distribution: {by_level}")
        lines.append("")

        for mem in results[:5]:
            content = mem.content[:40] + "..." if len(mem.content) > 40 else mem.content
            lines.append(f"- {content}")

        return "\n".join(lines)

    def _help(self) -> str:
        """帮助"""
        return """
[MEMORY COMMANDS]

/memory stats - View memory statistics
/memory search [keyword] - Search memories
/memory recent - View recent memories
/memory tags - View popular tags
/memory my - View your memories

Example: /memory search blue
"""


# 单例
_handler: Optional[MemoryCommandHandler] = None


async def get_memory_command_handler() -> MemoryCommandHandler:
    """获取命令处理器"""
    global _handler
    if _handler is None:
        _handler = MemoryCommandHandler()
    return _handler


async def process_memory_command(message: str, user_id: str = "") -> Optional[str]:
    """处理记忆命令"""
    handler = await get_memory_command_handler()
    return await handler.handle(message, user_id)
