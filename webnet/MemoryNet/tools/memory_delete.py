"""
删除一条手动长期记忆（统一接口层）

本工具整合 Undefined 记忆系统和弥娅原生记忆系统
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class MemoryDelete(BaseTool):
    """MemoryDelete - 统一记忆接口层"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_delete",
            "description": "删除一条手动长期记忆。当用户明确要求删除某条记忆、移除记忆时必须调用此工具。重要：此工具执行实际删除记忆操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID（可以使用 memory_list 查询）"
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
        memory_type = args.get("memory_type", "auto")

        if not memory_id:
            return "❌ 记忆ID不能为空"

        # 优先级 1: Undefined 轻量记忆系统
        if memory_type in ['auto', 'undefined']:
            try:
                from memory.undefined_memory import get_undefined_memory_adapter
                adapter = get_undefined_memory_adapter()
                success = await adapter.delete(memory_id)

                if success:
                    return f"✅ 已删除记忆（Undefined轻量记忆）\nUUID: {memory_id}"
            except ImportError:
                logger.debug("Undefined 记忆系统不可用，尝试其他记忆系统")
            except Exception as e:
                logger.error(f"调用 Undefined 记忆系统失败: {e}", exc_info=True)

        # 优先级 2: 认知记忆系统
        if memory_type in ['auto', 'cognitive']:
            cognitive_memory = getattr(context, 'cognitive_memory', None)
            if cognitive_memory:
                try:
                    success = await cognitive_memory.delete_memo(memory_id)
                    if success:
                        return f"✅ 已删除记忆（认知记忆系统）\nID: {memory_id}"
                except Exception as e:
                    logger.error(f"调用认知记忆系统失败: {e}", exc_info=True)

        # 优先级 3: 记忆引擎
        memory_engine = context.memory_engine
        if memory_engine:
            try:
                deleted = False
                deleted_from = []

                # 检查潮汐记忆
                if memory_id in memory_engine.tide_memory:
                    del memory_engine.tide_memory[memory_id]
                    if memory_id in memory_engine.memory_metadata:
                        del memory_engine.memory_metadata[memory_id]
                    deleted = True
                    deleted_from.append("短期记忆")

                # 检查梦境记忆
                if memory_id in memory_engine.dream_memory:
                    del memory_engine.dream_memory[memory_id]
                    if memory_id in memory_engine.memory_metadata:
                        del memory_engine.memory_metadata[memory_id]
                    deleted = True
                    deleted_from.append("长期记忆")

                if deleted:
                    from_str = ", ".join(deleted_from)
                    return f"✅ 已删除记忆（记忆引擎）\nID: {memory_id}\n来源: {from_str}"

                # 模糊搜索
                similar_ids = [
                    mid for mid in memory_engine.dream_memory.keys()
                    if memory_id.lower() in mid.lower()
                ]
                if similar_ids:
                    return f"❌ 未找到精确匹配的记忆: {memory_id}\n\n相似的记忆ID: {', '.join(similar_ids[:5])}"

                return f"❌ 未找到记忆: {memory_id}\n\n提示: 使用 memory_list 查看所有记忆ID"
            except Exception as e:
                logger.error(f"调用记忆引擎失败: {e}", exc_info=True)

        return "⚠️ 记忆系统未初始化，无法删除记忆"
