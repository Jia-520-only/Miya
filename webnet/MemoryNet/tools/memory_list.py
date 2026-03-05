"""
列出所有手动长期记忆（统一接口层）

本工具整合 Undefined 记忆系统和弥娅原生记忆系统
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class MemoryList(BaseTool):
    """MemoryList - 统一记忆接口层"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_list",
            "description": "列出所有手动长期记忆，支持按标签筛选和限制数量。当用户说'查看记忆'、'列出记忆'、'显示所有记忆'、'记忆列表'等时必须调用此工具。重要：此工具返回的记忆结果包含完整的用户信息(如生日、喜好等)，AI 必须仔细阅读工具返回的内容并基于这些信息回答用户问题。不要重复询问工具中已提供的信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "tag": {
                        "type": "string",
                        "description": "按标签筛选记忆"
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "记忆类型：auto(自动选择), undefined(Undefined轻量记忆), cognitive(认知记忆), tide(潮汐记忆)",
                        "enum": ["auto", "undefined", "cognitive", "tide"],
                        "default": "auto"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具 - 统一调用记忆系统"""
        limit = args.get("limit", 10)
        tag = args.get("tag")
        memory_type = args.get("memory_type", "auto")

        # 优先级 1: Undefined 轻量记忆系统
        if memory_type in ['auto', 'undefined']:
            try:
                from memory.undefined_memory import get_undefined_memory_adapter
                adapter = get_undefined_memory_adapter()

                if tag:
                    memories = await adapter.get_by_tag(tag, limit)
                else:
                    memories = await adapter.get_all(limit)

                if not memories:
                    return f"📭 Undefined轻量记忆中暂无记忆"

                result = f"📚 记忆列表（Undefined轻量记忆）\n共 {len(memories)} 条\n\n"
                for i, mem in enumerate(memories, 1):
                    content_preview = mem.fact[:100] + "..." if len(mem.fact) > 100 else mem.fact
                    tags_str = ", ".join(mem.tags) if mem.tags else "无"
                    result += f"{i}. **{mem.uuid}**\n"
                    result += f"   时间: {mem.created_at}\n"
                    result += f"   内容: {content_preview}\n"
                    result += f"   标签: {tags_str}\n\n"

                return result
            except ImportError:
                logger.debug("Undefined 记忆系统不可用，尝试其他记忆系统")
            except Exception as e:
                logger.error(f"调用 Undefined 记忆系统失败: {e}", exc_info=True)

        # 优先级 2: 认知记忆系统
        if memory_type in ['auto', 'cognitive']:
            cognitive_memory = getattr(context, 'cognitive_memory', None)
            if cognitive_memory:
                try:
                    results = await cognitive_memory.search(
                        query=tag if tag else "",
                        limit=limit,
                        memory_type="pinned"
                    )

                    if not results:
                        return f"📭 认知记忆系统中暂无记忆"

                    result = f"📚 记忆列表（认知记忆系统）\n共 {len(results)} 条\n\n"
                    for i, mem in enumerate(results, 1):
                        content_preview = mem.get('content', '')[:100] + "..." if len(mem.get('content', '')) > 100 else mem.get('content', '')
                        result += f"{i}. **{mem.get('id', 'unknown')}**\n"
                        result += f"   内容: {content_preview}\n"
                        tags = mem.get('tags', [])
                        tag_str = ", ".join(tags) if tags else "无"
                        result += f"   标签: {tag_str}\n\n"

                    return result
                except Exception as e:
                    logger.error(f"调用认知记忆系统失败: {e}", exc_info=True)

        # 优先级 3: 记忆引擎
        memory_engine = context.memory_engine
        if memory_engine:
            try:
                memories = memory_engine.dream_memory

                if not memories:
                    return "📭 记忆引擎中暂无长期记忆"

                memory_list = []
                for memory_id, content in memories.items():
                    memory_data = content if isinstance(content, dict) else {'content': str(content)}

                    if tag:
                        memory_tags = memory_data.get('tags', [])
                        if tag not in memory_tags and f"tag:{tag}" not in str(memory_tags):
                            continue

                    memory_list.append({
                        'id': memory_id,
                        'content': memory_data.get('content', str(content)),
                        'tags': memory_data.get('tags', []),
                        'type': memory_data.get('type', 'unknown')
                    })

                memory_list = memory_list[:limit]

                if not memory_list:
                    return f"📭 未找到匹配的记忆（标签: {tag if tag else '全部'}）"

                result = f"📚 记忆列表（记忆引擎）\n共 {len(memory_list)} 条\n\n"
                for i, mem in enumerate(memory_list, 1):
                    tags_str = ", ".join(mem['tags']) if mem['tags'] else "无"
                    content_preview = mem['content'][:100] + "..." if len(mem['content']) > 100 else mem['content']
                    result += f"{i}. **{mem['id']}**\n"
                    result += f"   内容: {content_preview}\n"
                    result += f"   标签: {tags_str}\n\n"

                return result
            except Exception as e:
                logger.error(f"调用记忆引擎失败: {e}", exc_info=True)

        return "⚠️ 记忆系统未初始化，无法列出记忆"
