"""
检索普通记忆工具
"""

import logging
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SearchNormalMemory(BaseTool):
    """检索普通模式下的对话历史记忆"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_normal_memory",
            "description": "检索普通模式下的对话历史记忆，支持按时间范围和关键词筛选。当用户说'查看记忆'、'搜索记忆'、'查看历史'、'回忆'等时必须调用此工具。重要：此工具执行实际记忆检索操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "返回数量限制，默认10条",
                        "default": 10
                    },
                    "days_back": {
                        "type": "number",
                        "description": "检索最近几天的记忆，默认7天",
                        "default": 7
                    },
                    "keywords": {
                        "type": "array",
                        "description": "关键词列表，可选",
                        "items": {"type": "string"}
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行记忆检索

        Args:
            args: 工具参数（limit, days_back, keywords）
            context: 工具执行上下文

        Returns:
            检索结果字符串
        """
        try:
            limit = args.get('limit', 10)
            days_back = args.get('days_back', 7)
            keywords = args.get('keywords')

            user_id = context.user_id
            memory_net = context.memory_net

            if not user_id:
                return "错误：缺少用户ID"

            if not memory_net:
                return "错误：记忆系统未初始化"

            # 异步导入
            from ..memory_search_tools import search_and_report_normal_memory

            # 异步执行
            report = await search_and_report_normal_memory(
                user_id=user_id,
                memory_net=memory_net,
                limit=limit,
                days_back=days_back,
                keywords=keywords
            )

            return report

        except Exception as e:
            logger.error(f"[SearchNormalMemory] 执行失败: {e}")
            return f"错误：{str(e)}"
