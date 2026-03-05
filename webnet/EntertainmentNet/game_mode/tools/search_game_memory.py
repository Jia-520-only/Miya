"""
检索游戏记忆工具
"""

import logging
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SearchGameMemory(BaseTool):
    """检索游戏模式下的记忆"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_game_memory",
            "description": "检索游戏模式下的记忆，包括角色卡、故事进度、存档信息等。当用户说'查看记忆'、'搜索记忆'、'查看角色卡'、'查看进度'等时必须调用此工具。重要：此工具执行实际记忆检索操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "返回数量限制，默认10条",
                        "default": 10
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
            args: 工具参数（limit, keywords）
            context: 工具执行上下文

        Returns:
            检索结果字符串
        """
        try:
            limit = args.get('limit', 10)
            keywords = args.get('keywords')

            user_id = context.user_id
            group_id = context.group_id
            game_mode = context.game_mode

            if not user_id:
                return "错误：缺少用户ID"

            if not game_mode:
                return "错误：当前不在游戏模式中"

            # 获取游戏模式管理器
            from webnet.EntertainmentNet.game_mode import get_game_mode_manager
            game_mode_manager = get_game_mode_manager()

            if not game_mode_manager:
                return "错误：游戏模式管理器未初始化"

            # 异步导入
            from ..memory_search_tools import search_and_report_game_memory

            # 异步执行
            report = await search_and_report_game_memory(
                user_id=user_id,
                group_id=group_id,
                game_mode_manager=game_mode_manager,
                limit=limit,
                keywords=keywords
            )

            return report

        except Exception as e:
            logger.error(f"[SearchGameMemory] 执行失败: {e}")
            return f"错误：{str(e)}"
