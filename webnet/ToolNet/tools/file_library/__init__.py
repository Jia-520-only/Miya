"""
弥娅文件库操作工具

让弥娅能够：
- 列出所有已接收的文件
- 搜索文件库中的文件
- 读取文件内容
- 获取文件库统计信息
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.file_library import get_file_library
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class FileLibraryListTool(BaseTool):
    """列出来自不同平台的所有文件"""

    name = "file_library_list"
    description = "列出弥娅文件库中的所有文件。可按平台筛选，支持分页。"

    def __init__(self):
        super().__init__(name=self.name, description=self.description)

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "按平台筛选，空字符串表示全部",
                        "default": "",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回文件数上限",
                        "default": 20,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "分页偏移",
                        "default": 0,
                    },
                },
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext = None) -> str:
        library = get_file_library()
        platform = args.get("platform", "")
        limit = min(int(args.get("limit", 20)), 100)
        offset = int(args.get("offset", 0))

        entries = library.list_files(platform=platform, limit=limit, offset=offset)

        if not entries:
            return "文件库中还没有文件哦~"

        lines = [f"文件库 (共 {library.stats()['total_files']} 个文件)"]
        for e in entries:
            size_kb = e.file_size / 1024 if e.file_size else 0
            size_str = f"{size_kb / 1024:.1f}MB" if size_kb >= 1024 else f"{size_kb:.1f}KB"
            lines.append(f"  [{e.file_id[:8]}] {e.file_name} ({size_str}) - {e.platform} - {e.received_at[:16]}")
        return "\n".join(lines)


class FileLibrarySearchTool(BaseTool):
    """按文件名搜索文件库"""

    name = "file_library_search"
    description = "在弥娅文件库中按文件名搜索文件。可用于查找特定文件。"

    def __init__(self):
        super().__init__(name=self.name, description=self.description)

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（匹配文件名）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数上限",
                        "default": 10,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext = None) -> str:
        library = get_file_library()
        query = args.get("query", "").strip()
        if not query:
            return "请提供搜索关键词"

        entries = library.search_files(query, limit=min(int(args.get("limit", 10)), 50))

        if not entries:
            return f"未找到包含 '{query}' 的文件"

        lines = [f"搜索 '{query}' — {len(entries)} 个结果"]
        for e in entries:
            size_kb = e.file_size / 1024 if e.file_size else 0
            size_str = f"{size_kb / 1024:.1f}MB" if size_kb >= 1024 else f"{size_kb:.1f}KB"
            lines.append(f"  [{e.file_id[:8]}] {e.file_name} ({size_str}) - {e.received_at[:16]}")
        return "\n".join(lines)


class FileLibraryReadTool(BaseTool):
    """读取文件库中指定文件的内容"""

    name = "file_library_read"
    description = "读取弥娅文件库中指定文件的内容并自动解析。需要提供文件ID（通过 file_library_list 或 file_library_search 获取前8位即可）。"

    def __init__(self):
        super().__init__(name=self.name, description=self.description)

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "文件ID（前8位短ID即可）",
                    },
                },
                "required": ["file_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext = None) -> str:
        library = get_file_library()
        file_id = args.get("file_id", "").strip()
        if not file_id:
            return "请提供文件ID"

        entry = library.get_file(file_id)
        if not entry:
            for fid, e in library._entries.items():
                if fid.startswith(file_id):
                    entry = e
                    file_id = fid
                    break

        if not entry:
            return f"未找到文件: {file_id}"

        result = library.read_and_analyze(file_id)
        if not result:
            return f"文件 {entry.file_name} 无法读取或内容为空"

        return f"文件内容: {entry.file_name}\n\n{result[:4000]}"


class FileLibraryStatsTool(BaseTool):
    """文件库统计"""

    name = "file_library_stats"
    description = "获取弥娅文件库的统计信息：总文件数、总大小、按类型/平台分布。"

    def __init__(self):
        super().__init__(name=self.name, description=self.description)

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext = None) -> str:
        library = get_file_library()
        stats = library.stats()

        lines = [
            f"文件库统计",
            f"  总文件数: {stats['total_files']}",
            f"  总大小: {stats['total_size_kb']} KB",
        ]
        if stats.get("by_type"):
            lines.append("  按类型:")
            for t, c in stats["by_type"].items():
                lines.append(f"    {t}: {c}")
        if stats.get("by_platform"):
            lines.append("  按平台:")
            for p, c in stats["by_platform"].items():
                lines.append(f"    {p}: {c}")

        return "\n".join(lines)


def get_file_library_tools() -> list:
    """获取所有文件库工具实例"""
    return [
        FileLibraryListTool(),
        FileLibrarySearchTool(),
        FileLibraryReadTool(),
        FileLibraryStatsTool(),
    ]
