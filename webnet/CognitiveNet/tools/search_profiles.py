"""
语义搜索侧写
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SearchProfiles(BaseTool):
    """SearchProfiles"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_profiles",
            "description": "根据特征或关键词搜索用户/群聊侧写",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询（如：'活跃', '喜欢游戏', '技术群'）"
                    },
                    "profile_type": {
                        "type": "string",
                        "description": "侧写类型",
                        "enum": ["user", "group", "all"],
                        "default": "all"
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
        profile_type = args.get("profile_type", "all")
        limit = args.get("limit", 10)

        if not query:
            return "❌ 查询不能为空"

        try:
            results = []

            if context.memory_engine:
                # 搜索梦境记忆
                for memory_id, memory_data in context.memory_engine.dream_memory.items():
                    if not memory_id.startswith("profile_"):
                        continue

                    # 类型过滤
                    if profile_type != "all":
                        if f"profile_{profile_type}_" not in memory_id:
                            continue

                    # 匹配查询
                    if isinstance(memory_data, dict):
                        # 转换为字符串进行匹配
                        data_str = str(memory_data).lower()
                        if query in data_str:
                            results.append({
                                'id': memory_id,
                                'type': memory_data.get('type', 'unknown'),
                                'id_num': memory_data.get('id', 'unknown'),
                                'data': memory_data
                            })

                # 搜索潮汐记忆
                for memory_id, memory_data in context.memory_engine.tide_memory.items():
                    if not memory_id.startswith("profile_"):
                        continue

                    if profile_type != "all":
                        if f"profile_{profile_type}_" not in memory_id:
                            continue

                    if isinstance(memory_data, dict):
                        data_str = str(memory_data).lower()
                        if query in data_str:
                            results.append({
                                'id': memory_id,
                                'type': memory_data.get('type', 'unknown'),
                                'id_num': memory_data.get('id', 'unknown'),
                                'data': memory_data
                            })

            if not results:
                return f"🔍 未找到匹配的侧写: '{query}'"

            # 限制结果并格式化
            results = results[:limit]

            result = f"🔍 侧写搜索结果: '{query}'\n共 {len(results)} 个匹配\n\n"
            for i, r in enumerate(results, 1):
                result += f"{i}. **{r['type']}_{r['id_num']}**\n"
                # 显示匹配的相关信息
                data = r['data']
                for key, value in data.items():
                    if key in ['id', 'type', 'created_at']:
                        continue
                    if query in str(value).lower():
                        result += f"   {key}: {value}\n"
                result += "\n"

            return result

        except Exception as e:
            logger.error(f"搜索侧写失败: {e}", exc_info=True)
            return f"❌ 搜索侧写失败: {str(e)}"
