"""
更新一条手动长期记忆（统一接口层）

本工具整合 Undefined 记忆系统和弥娅原生记忆系统
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class MemoryUpdate(BaseTool):
    """MemoryUpdate - 统一记忆接口层"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_update",
            "description": "更新一条手动长期记忆的内容或标签",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID（可以使用 memory_list 查询）"
                    },
                    "content": {
                        "type": "string",
                        "description": "新的记忆内容"
                    },
                    "priority": {
                        "type": "number",
                        "description": "新的优先级 (0-1)",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "tags": {
                        "type": "array",
                        "description": "新的标签，会替换原有标签",
                        "items": {"type": "string"}
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "记忆类型：auto(自动选择), undefined(Undefined轻量记忆), cognitive(认知记忆), tide(潮汐记忆)",
                        "enum": ["auto", "undefined", "cognitive", "tide"],
                        "default": "auto"
                    }
                },
                "required": ["memory_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具 - 统一调用记忆系统"""
        memory_id = args.get("memory_id", "").strip()
        content = args.get("content")
        priority = args.get("priority")
        tags = args.get("tags")
        memory_type = args.get("memory_type", "auto")

        if not memory_id:
            return "❌ 记忆ID不能为空"

        if content is None and priority is None and tags is None:
            return "❌ 至少需要提供 content、priority 或 tags 中的一个参数"

        # 优先级 1: Undefined 轻量记忆系统
        if memory_type in ['auto', 'undefined']:
            try:
                from memory.undefined_memory import get_undefined_memory_adapter
                adapter = get_undefined_memory_adapter()
                success = await adapter.update(memory_id, content, tags)

                if success:
                    changes = []
                    if content is not None:
                        changes.append(f"内容已更新")
                    if tags is not None:
                        changes.append(f"标签: {tags}")

                    return f"✅ 已更新记忆（Undefined轻量记忆）\nUUID: {memory_id}\n变更: {', '.join(changes)}"
            except ImportError:
                logger.debug("Undefined 记忆系统不可用，尝试其他记忆系统")
            except Exception as e:
                logger.error(f"调用 Undefined 记忆系统失败: {e}", exc_info=True)

        # 优先级 2: 认知记忆系统
        if memory_type in ['auto', 'cognitive']:
            cognitive_memory = getattr(context, 'cognitive_memory', None)
            if cognitive_memory:
                try:
                    success = await cognitive_memory.update_memo(
                        memo_id=memory_id,
                        content=content,
                        priority=priority,
                        tags=tags
                    )

                    if success:
                        changes = []
                        if content is not None:
                            changes.append(f"内容已更新")
                        if priority is not None:
                            changes.append(f"优先级: {priority}")
                        if tags is not None:
                            changes.append(f"标签: {tags}")

                        return f"✅ 已更新记忆（认知记忆系统）\nID: {memory_id}\n变更: {', '.join(changes)}"
                except Exception as e:
                    logger.error(f"调用认知记忆系统失败: {e}", exc_info=True)

        # 优先级 3: 记忆引擎
        memory_engine = context.memory_engine
        if memory_engine:
            try:
                # 检查记忆是否存在
                if memory_id not in memory_engine.dream_memory:
                    # 尝试在潮汐记忆中查找
                    if memory_id in memory_engine.tide_memory:
                        old_memory = memory_engine.tide_memory[memory_id]
                        new_memory = old_memory.copy()

                        if content is not None:
                            new_memory['content'] = content
                        if priority is not None:
                            memory_engine.memory_metadata[memory_id]['priority'] = priority
                        if tags is not None:
                            new_memory['tags'] = tags
                            memory_engine.compress_to_dream(memory_id)

                        memory_engine.tide_memory[memory_id] = new_memory

                        changes = []
                        if content is not None:
                            changes.append(f"内容: {content}")
                        if priority is not None:
                            changes.append(f"优先级: {priority}")
                        if tags is not None:
                            changes.append(f"标签: {tags}")

                        return f"✅ 已更新记忆（记忆引擎）\nID: {memory_id}\n变更: {', '.join(changes)}"
                    else:
                        return f"❌ 未找到记忆: {memory_id}"

                # 更新梦境记忆
                old_memory = memory_engine.dream_memory[memory_id]
                new_memory = old_memory.copy() if isinstance(old_memory, dict) else {'content': str(old_memory)}

                if content is not None:
                    new_memory['content'] = content
                if tags is not None:
                    new_memory['tags'] = tags

                memory_engine.dream_memory[memory_id] = new_memory

                if priority is not None:
                    metadata = memory_engine.memory_metadata.get(memory_id, {})
                    metadata['priority'] = priority
                    memory_engine.memory_metadata[memory_id] = metadata

                changes = []
                if content is not None:
                    changes.append(f"内容已更新")
                if priority is not None:
                    changes.append(f"优先级: {priority}")
                if tags is not None:
                    changes.append(f"标签: {tags}")

                return f"✅ 已更新记忆（记忆引擎）\nID: {memory_id}\n变更: {', '.join(changes)}"
            except Exception as e:
                logger.error(f"调用记忆引擎失败: {e}", exc_info=True)

        return "⚠️ 记忆系统未初始化，无法更新记忆"
