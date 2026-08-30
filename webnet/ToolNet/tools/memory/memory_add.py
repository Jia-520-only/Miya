"""
添加手动长期记忆（统一接口层）

本工具优先使用新版 MiyaMemoryCore 记忆系统
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class MemoryAdd(BaseTool):
    """MemoryAdd - 统一记忆接口层"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_add",
            "description": "添加手动长期记忆，帮助AI记住重要信息。当用户明确要求记住某条信息、添加记忆、保存重要内容时必须调用此工具。重要：此工具执行实际添加记忆操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "记忆内容"},
                    "priority": {
                        "type": "number",
                        "description": "优先级 (0-1)，默认0.5。越高越重要",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.5,
                    },
                    "tags": {
                        "type": "array",
                        "description": "标签，用于检索和分类",
                        "items": {"type": "string"},
                    },
                },
                "required": ["content"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具 - 优先使用 MiyaMemoryCore"""
        content = args.get("content", "").strip()
        priority = args.get("priority", 0.5)
        tags = args.get("tags", [])
        user_id = str(context.user_id) if context.user_id else "global"

        if not content:
            return "❌ 记忆内容不能为空"

        # 优先级 1: 新版 MiyaMemoryCore（权威记忆源）
        try:
            from memory import MemoryLevel, MemorySource, get_memory_core

            core = await get_memory_core()

            await core.store(
                content=content,
                level=MemoryLevel.LONG_TERM,
                priority=priority,
                tags=tags,
                user_id=user_id,
                session_id=getattr(context, "request_id", ""),
                platform="qq",
                source=MemorySource.MANUAL,
                event_type="手动添加",
                significance=priority,
            )

            tag_str = ", ".join(tags) if tags else "无"
            return f"✅ 已添加记忆\n内容: {content}\n优先级: {priority}\n标签: {tag_str}"

        except Exception as e:
            logger.error(f"[MemoryAdd] MiyaMemoryCore 存储失败: {e}", exc_info=True)

        # 优先级 2: Undefined 轻量记忆系统（回退）
        try:
            from memory.undefined_memory import get_undefined_memory_adapter

            adapter = get_undefined_memory_adapter()
            await adapter.add_memory(content, user_id, tags=tags)

            tag_str = ", ".join(tags) if tags else "无"
            return f"✅ 已添加记忆（Undefined轻量记忆）\n内容: {content}\n标签: {tag_str}"
        except Exception as e:
            logger.error(f"[MemoryAdd] Undefined 记忆系统失败: {e}", exc_info=True)

        # 优先级 3: 认知记忆系统
        cognitive_memory = getattr(context, "cognitive_memory", None)
        if cognitive_memory:
            try:
                await cognitive_memory.add_memo(
                    content=content,
                    priority=priority,
                    tags=tags,
                    user_id=str(context.user_id) if context.user_id else None,
                    group_id=str(context.group_id) if context.group_id else None,
                )

                tag_str = ", ".join(tags) if tags else "无"
                return f"✅ 已添加记忆（认知记忆系统）\n内容: {content}\n标签: {tag_str}"
            except Exception as e:
                logger.error(f"[MemoryAdd] 认知记忆系统失败: {e}", exc_info=True)

        return f"⚠️ 记忆系统未初始化，无法保存记忆\n\n记忆内容: {content}"
