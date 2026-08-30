#!/usr/bin/env python3
"""
MCP 文件系统服务 - 提供文件操作能力
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict


class FilesystemService:
    """MCP 文件系统服务"""

    def __init__(self):
        self.name = "filesystem"
        self.description = "文件操作服务 - 读取、写入、删除文件"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """处理工具调用"""
        tool_name = tool_call.get("tool_name", "")
        tool_call.get("message", "")

        if tool_name == "read_file" or "read" in tool_name.lower():
            return await self._read_file(tool_call)
        elif tool_name == "write_file" or "write" in tool_name.lower():
            return await self._write_file(tool_call)
        elif tool_name == "delete_file" or "delete" in tool_name.lower():
            return await self._delete_file(tool_call)
        elif tool_name == "list_files" or "list" in tool_name.lower():
            return await self._list_files(tool_call)
        elif tool_name == "search_files" or "search" in tool_name.lower():
            return await self._search_files(tool_call)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"})

    async def _read_file(self, tool_call: Dict[str, Any]) -> str:
        """读取文件"""
        file_path = tool_call.get("file_path", "")
        offset = tool_call.get("offset", 0)
        limit = tool_call.get("limit")

        if not file_path:
            return json.dumps({"error": "缺少 file_path 参数"})

        try:
            path = Path(file_path)
            if not path.exists():
                return json.dumps({"error": f"文件不存在: {file_path}"})

            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")

            if offset > 0:
                lines = lines[offset:]
            if limit:
                lines = lines[:limit]

            return json.dumps(
                {
                    "success": True,
                    "file_path": str(path),
                    "total_lines": len(content.split("\n")),
                    "content": "\n".join(lines),
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _write_file(self, tool_call: Dict[str, Any]) -> str:
        """写入文件"""
        file_path = tool_call.get("file_path", "")
        content = tool_call.get("content", "")

        if not file_path:
            return json.dumps({"error": "缺少 file_path 参数"})

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            return json.dumps({"success": True, "file_path": str(path), "bytes_written": len(content)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _delete_file(self, tool_call: Dict[str, Any]) -> str:
        """删除文件"""
        file_path = tool_call.get("file_path", "")
        recursive = tool_call.get("recursive", False)

        if not file_path:
            return json.dumps({"error": "缺少 file_path 参数"})

        try:
            path = Path(file_path)
            if not path.exists():
                return json.dumps({"error": f"文件不存在: {file_path}"})

            if path.is_dir():
                if recursive:
                    import shutil

                    shutil.rmtree(path)
                else:
                    return json.dumps({"error": "是目录，使用 recursive=true"})
            else:
                path.unlink()

            return json.dumps({"success": True, "deleted": str(path)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _list_files(self, tool_call: Dict[str, Any]) -> str:
        """列出文件"""
        dir_path = tool_call.get("path", ".")
        pattern = tool_call.get("pattern", "*")
        recursive = tool_call.get("recursive", False)

        try:
            path = Path(dir_path)
            if not path.exists():
                return json.dumps({"error": f"目录不存在: {dir_path}"})

            files = [str(p) for p in path.rglob(pattern)] if recursive else [str(p) for p in path.glob(pattern)]

            return json.dumps(
                {
                    "success": True,
                    "path": str(path),
                    "count": len(files),
                    "files": files[:100],
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _search_files(self, tool_call: Dict[str, Any]) -> str:
        """搜索文件内容"""
        pattern = tool_call.get("pattern", "")
        path = tool_call.get("path", ".")
        include = tool_call.get("include", "*")

        if not pattern:
            return json.dumps({"error": "缺少 pattern 参数"})

        try:
            import re

            results = []

            for file_path in Path(path).rglob(include):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        matches = re.findall(f".*{re.escape(pattern)}.*", content, re.IGNORECASE)
                        if matches:
                            results.append({"file": str(file_path), "matches": matches[:5]})
                    except:
                        pass

            return json.dumps({"success": True, "pattern": pattern, "results": results[:20]})
        except Exception as e:
            return json.dumps({"error": str(e)})


service = FilesystemService()


if __name__ == "__main__":

    async def test():
        result = await service.handle_handoff(
            {
                "tool_name": "read_file",
                "file_path": "core/terminal_ultra.py",
                "limit": 10,
            }
        )
        print(result)

    asyncio.run(test())
