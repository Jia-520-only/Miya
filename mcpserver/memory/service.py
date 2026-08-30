#!/usr/bin/env python3
"""
MCP Memory 服务 - 弥娅记忆系统（V4.1.11: 接入 MemoryBus）
"""

import json
import logging
from typing import Any, Dict

from memory.api.bus import get_memory_bus
from memory.models import MemoryLevel, MemoryQuery, MemorySource

logger = logging.getLogger("Miya.MCP.MemoryService")


class MemoryService:
    """MCP Memory 服务 - 通过 MemoryBus 持久化记忆存储"""

    def __init__(self):
        self.name = "memory"
        self.description = "记忆存储服务 - 持久化存储关键信息"
        self.version = "4.1.11"
        self._bus = None

    async def _get_bus(self):
        if self._bus is None:
            self._bus = await get_memory_bus()
        return self._bus

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        tool_name = tool_call.get("tool_name", "")

        if "store" in tool_name.lower() or "save" in tool_name.lower():
            return await self._store(tool_call)
        elif "recall" in tool_name.lower() or "get" in tool_name.lower() or "search" in tool_name.lower():
            return await self._recall(tool_call)
        elif "delete" in tool_name.lower() or "remove" in tool_name.lower():
            return await self._delete(tool_call)
        elif "list" in tool_name.lower():
            return await self._list(tool_call)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    async def _store(self, tool_call: Dict[str, Any]) -> str:
        key = tool_call.get("key", "")
        value = tool_call.get("value", "")
        tags = tool_call.get("tags", [])
        priority = tool_call.get("priority", 0.5)
        user_id = tool_call.get("user_id", "global")

        if not value:
            return json.dumps({"error": "缺少 value 参数"}, ensure_ascii=False)

        content = value if not key else f"[{key}] {value}"

        try:
            bus = await self._get_bus()
            memory_id = await bus.store(
                content=content,
                user_id=user_id,
                tags=tags,
                priority=priority,
                source=MemorySource.MANUAL,
            )
            return json.dumps(
                {
                    "success": True,
                    "id": memory_id,
                    "key": key,
                    "message": f"记忆已存储: {key or memory_id}",
                },
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error(f"[MCP Memory] store 失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _recall(self, tool_call: Dict[str, Any]) -> str:
        query = tool_call.get("query", "")
        key = tool_call.get("key", "")
        memory_id = tool_call.get("id", "")
        user_id = tool_call.get("user_id", "")
        limit = tool_call.get("limit", 10)

        try:
            bus = await self._get_bus()

            if memory_id:
                core = bus.core
                if core:
                    memory = await core.get_by_id(memory_id)
                    if memory:
                        return json.dumps(
                            {
                                "success": True,
                                "count": 1,
                                "memories": [memory.to_dict()],
                            },
                            ensure_ascii=False,
                        )
                    return json.dumps({"error": f"记忆不存在: {memory_id}"}, ensure_ascii=False)

            search_query = key or query
            if search_query:
                result = await bus.recall(query=search_query, user_id=user_id, limit=limit)
                return json.dumps(
                    {
                        "success": True,
                        "count": result.total_found,
                        "memories": [m.to_dict() for m in result.memories],
                    },
                    ensure_ascii=False,
                )

            return json.dumps({"error": "请提供 query、key 或 id 参数"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[MCP Memory] recall 失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _delete(self, tool_call: Dict[str, Any]) -> str:
        memory_id = tool_call.get("id", "")

        if not memory_id:
            return json.dumps({"error": "缺少 id 参数"}, ensure_ascii=False)

        try:
            bus = await self._get_bus()
            ok = await bus.delete(memory_id)
            if ok:
                return json.dumps({"success": True, "message": f"记忆已删除: {memory_id}"}, ensure_ascii=False)
            return json.dumps({"error": f"记忆不存在: {memory_id}"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[MCP Memory] delete 失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _list(self, tool_call: Dict[str, Any]) -> str:
        user_id = tool_call.get("user_id", "")
        limit = tool_call.get("limit", 20)
        tags = tool_call.get("tags")

        try:
            bus = await self._get_bus()
            core = bus.core
            if not core:
                return json.dumps({"success": True, "count": 0, "memories": []}, ensure_ascii=False)

            q = MemoryQuery(
                user_id=user_id or None,
                tags=list(tags) if tags else None,
                limit=limit,
                sort_by="created_at",
                sort_order="desc",
            )
            results = await core.retrieve(q)

            return json.dumps(
                {
                    "success": True,
                    "count": len(results) if results else 0,
                    "memories": [m.to_dict() for m in results][:limit] if results else [],
                },
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error(f"[MCP Memory] list 失败: {e}")
            return json.dumps({"error": str(e), "count": 0, "memories": []}, ensure_ascii=False)


service = MemoryService()


if __name__ == "__main__":
    import asyncio

    async def test():
        result = await service.handle_handoff(
            {
                "tool_name": "store",
                "key": "test_key",
                "value": "test_value",
                "user_id": "test",
            }
        )
        print(result)

    asyncio.run(test())
