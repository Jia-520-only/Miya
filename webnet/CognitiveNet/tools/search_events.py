"""
搜索历史事件
"""
from typing import Dict, Any
import logging
from datetime import datetime
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SearchEvents(BaseTool):
    """SearchEvents"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_events",
            "description": "搜索历史事件记录（重要对话、用户行为等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询（如：'生日', '会议', '约定'）"
                    },
                    "date_range": {
                        "type": "string",
                        "description": "日期范围，如 '2026-02', '最近7天'"
                    },
                    "event_type": {
                        "type": "string",
                        "description": "事件类型（如：'conversation', 'action', 'milestone'）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大结果数，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        query = args.get("query", "").strip().lower()
        date_range = args.get("date_range")
        event_type = args.get("event_type", "").lower()
        limit = args.get("limit", 10)

        if not query:
            return "❌ 查询不能为空"

        try:
            results = []

            if context.memory_engine:
                # 搜索梦境记忆中的事件
                for memory_id, memory_data in context.memory_engine.dream_memory.items():
                    if not memory_id.startswith("event_"):
                        continue

                    if not isinstance(memory_data, dict):
                        continue

                    # 类型过滤
                    if event_type and memory_data.get('type', '').lower() != event_type:
                        continue

                    # 日期过滤
                    if date_range:
                        event_date = memory_data.get('date', '')
                        if date_range not in event_date:
                            continue

                    # 查询匹配
                    data_str = str(memory_data).lower()
                    if query in data_str:
                        results.append({
                            'id': memory_id,
                            'data': memory_data
                        })

                # 搜索潮汐记忆
                for memory_id, memory_data in context.memory_engine.tide_memory.items():
                    if not memory_id.startswith("event_"):
                        continue

                    if not isinstance(memory_data, dict):
                        continue

                    if event_type and memory_data.get('type', '').lower() != event_type:
                        continue

                    if date_range:
                        event_date = memory_data.get('date', '')
                        if date_range not in event_date:
                            continue

                    data_str = str(memory_data).lower()
                    if query in data_str:
                        results.append({
                            'id': memory_id,
                            'data': memory_data
                        })

            if not results:
                # 搜索一般记忆
                if context.memory_engine:
                    for memory_id, memory_data in context.memory_engine.dream_memory.items():
                        if memory_id.startswith(('profile_', 'manual_')):
                            continue

                        if isinstance(memory_data, dict):
                            data_str = str(memory_data).lower()
                            if query in data_str:
                                results.append({
                                    'id': memory_id,
                                    'data': memory_data
                                })

                if not results:
                    return f"🔍 未找到匹配的事件: '{query}'"

            # 按日期排序（如果有日期字段）
            results.sort(key=lambda x: x['data'].get('date', ''), reverse=True)

            # 限制结果
            results = results[:limit]

            # 格式化输出
            result = f"🔍 历史事件搜索: '{query}'"
            if event_type:
                result += f" | 类型: {event_type}"
            if date_range:
                result += f" | 日期: {date_range}"
            result += f"\n共 {len(results)} 个匹配\n\n"

            for i, r in enumerate(results, 1):
                data = r['data']
                result += f"{i}. **{r['id']}**\n"
                for key, value in data.items():
                    if isinstance(value, list):
                        value_str = ", ".join(str(v)[:50] for v in value)
                    elif isinstance(value, dict):
                        value_str = "{...}"
                    else:
                        value_str = str(value)[:100]
                    result += f"   {key}: {value_str}\n"
                result += "\n"

            return result

        except Exception as e:
            logger.error(f"搜索事件失败: {e}", exc_info=True)
            return f"❌ 搜索事件失败: {str(e)}"
