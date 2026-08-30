"""
记忆统计与分类查询工具 — 使用 MiyaMemoryCore V3.1 统一 API
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class MemoryStats(BaseTool):
    """获取记忆统计信息"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_stats",
            "description": "获取记忆系统统计信息，包括各类型记忆数量、分类统计等。当用户询问记忆有多少、记得多少东西、记忆库状态时必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_categories": {
                        "type": "boolean",
                        "description": "是否包含分类统计（默认 True）",
                        "default": True,
                    }
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """获取记忆统计"""
        include_categories = args.get("include_categories", True)

        try:
            from memory import get_memory_core

            core = await get_memory_core()
            stats = await core.get_statistics() if hasattr(core, "get_statistics") else {}

            result = "📊 记忆统计\n"
            result += f"├─ 对话记忆: {stats.get('dialogue_count', 0)} 条\n"
            result += f"├─ 短期记忆: {stats.get('short_term_count', 0)} 条\n"
            result += f"├─ 长期记忆: {stats.get('long_term_count', 0)} 条\n"
            result += f"├─ 语义记忆: {stats.get('semantic_count', 0)} 条\n"
            result += f"├─ 知识记忆: {stats.get('knowledge_count', 0)} 条\n"
            result += f"├─ 置顶记忆: {stats.get('pinned_count', 0)} 条\n"
            result += f"└─ 总记忆数: {stats.get('total_count', 0)} 条\n"

            if include_categories and "level_distribution" in stats:
                dist = stats["level_distribution"]
                result += "\n📈 层级分布:\n"
                for level, count in dist.items():
                    result += f"  • {level}: {count}\n"

            return result

        except ImportError:
            return "❌ 记忆系统未初始化"
        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return f"❌ 获取统计失败: {str(e)}"


class MemorySearchByCategory(BaseTool):
    """按分类搜索记忆"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "memory_search_by_category",
            "description": "按分类搜索记忆，支持情感类、闲聊类、日常类、重要记录、任务类、知识类等分类。当用户说查看情感记忆、看看重要记录、搜索任务类记忆时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "记忆分类",
                        "enum": [
                            "emotion",
                            "chat",
                            "daily",
                            "important",
                            "task",
                            "knowledge",
                            "all",
                        ],
                        "default": "all",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制（默认 10）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """按分类搜索记忆"""
        category = args.get("category", "all")
        limit = args.get("limit", 10)

        try:
            from memory import get_memory_core

            core = await get_memory_core()

            if category == "all":
                results = await core.retrieve(limit=limit)
            else:
                results = await core.retrieve(tags=[category], limit=limit)

            if not results:
                return f"📭 暂无分类为「{category}」的记忆"

            cat_names = {
                "emotion": "💕 情感类",
                "chat": "💬 闲聊类",
                "daily": "📅 日常类",
                "important": "⭐ 重要记录",
                "task": "📋 任务类",
                "knowledge": "📚 知识类",
                "unknown": "❓ 未分类",
            }

            result = f"{cat_names.get(category, category)} 记忆 (共 {len(results)} 条)\n\n"
            for i, mem in enumerate(results, 1):
                content = mem.content if hasattr(mem, "content") else str(mem)
                content = content[:80] + "..." if len(content) > 80 else content
                result += f"{i}. {content}\n"

            return result

        except ImportError:
            return "❌ 记忆系统未初始化"
        except Exception as e:
            logger.error(f"按分类搜索记忆失败: {e}")
            return f"❌ 搜索失败: {str(e)}"
