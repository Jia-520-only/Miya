"""
添加手动长期记忆（统一接口层）

本工具作为统一接口层，整合 Undefined 记忆系统和弥娅原生记忆系统
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


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
                    "content": {
                        "type": "string",
                        "description": "记忆内容"
                    },
                    "priority": {
                        "type": "number",
                        "description": "优先级 (0-1)，默认0.5。越高越重要",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.5
                    },
                    "tags": {
                        "type": "array",
                        "description": "标签，用于检索和分类",
                        "items": {"type": "string"}
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "记忆类型：auto(自动选择), undefined(Undefined轻量记忆), cognitive(认知记忆), tide(潮汐记忆)",
                        "enum": ["auto", "undefined", "cognitive", "tide"],
                        "default": "auto"
                    }
                },
                "required": ["content"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具 - 统一调用记忆系统"""
        content = args.get("content", "").strip()
        priority = args.get("priority", 0.5)
        tags = args.get("tags", [])
        memory_type = args.get("memory_type", "auto")

        if not content:
            return "❌ 记忆内容不能为空"

        # 优先级 1: Undefined 轻量记忆系统（适合手动备忘）
        if memory_type in ['auto', 'undefined']:
            try:
                from memory.undefined_memory import get_undefined_memory_adapter
                adapter = get_undefined_memory_adapter()
                uuid = await adapter.add(content, tags)

                tag_str = ", ".join(tags) if tags else "无"
                return f"✅ 已添加记忆（Undefined轻量记忆）\nUUID: {uuid}\n内容: {content}\n标签: {tag_str}"
            except ImportError:
                logger.debug("Undefined 记忆系统不可用，尝试其他记忆系统")
            except Exception as e:
                logger.error(f"调用 Undefined 记忆系统失败: {e}", exc_info=True)

        # 优先级 2: 认知记忆系统（弥娅原生）
        if memory_type in ['auto', 'cognitive']:
            cognitive_memory = getattr(context, 'cognitive_memory', None)
            if cognitive_memory:
                try:
                    memo_id = await cognitive_memory.add_memo(
                        content=content,
                        priority=priority,
                        tags=tags,
                        user_id=str(context.user_id) if context.user_id else None,
                        group_id=str(context.group_id) if context.group_id else None
                    )

                    tag_str = ", ".join(tags) if tags else "无"
                    return f"✅ 已添加记忆（认知记忆系统）\nID: {memo_id}\n内容: {content}\n优先级: {priority}\n标签: {tag_str}"
                except Exception as e:
                    logger.error(f"调用认知记忆系统失败: {e}", exc_info=True)

        # 优先级 3: 记忆引擎（hub/ 潮汐记忆）
        memory_engine = context.memory_engine
        if memory_engine:
            try:
                from datetime import datetime
                memory_id = f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                memory_engine.store_tide(
                    memory_id=memory_id,
                    content={
                        'content': content,
                        'tags': tags,
                        'created_by': f"user_{context.user_id}" if context.user_id else 'unknown',
                        'type': 'manual'
                    },
                    priority=priority,
                    ttl=86400 * 365  # 1年
                )

                tag_str = ", ".join(tags) if tags else "无"
                return f"✅ 已添加记忆（记忆引擎）\nID: {memory_id}\n内容: {content}\n优先级: {priority}\n标签: {tag_str}"
            except Exception as e:
                logger.error(f"调用记忆引擎失败: {e}", exc_info=True)

        # 兜底：返回友好提示
        return f"⚠️ 记忆系统未初始化\n\n记忆内容: {content}\n提示: 请确保记忆系统已正确初始化"
