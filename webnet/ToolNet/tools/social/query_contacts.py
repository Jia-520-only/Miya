"""
联系人查询工具 - 查询好友/群列表
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class QueryFriendsTool(BaseTool):
    """查询好友列表工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "query_friends",
            "description": "查询当前机器人的好友列表，可指定筛选条件。当用户问'好友列表'、'有哪些好友'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制，默认20",
                        "default": 20,
                    }
                },
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        limit = args.get("limit", 20)

        try:
            client = getattr(context, "onebot_client", None)
            if not client:
                return "OneBot 客户端不可用"

            friends = await client.get_friend_list()

            if not friends:
                return "暂无好友列表"

            lines = ["【好友列表】\n"]
            for i, f in enumerate(friends[:limit]):
                nickname = f.get("nickname", "")
                user_id = f.get("user_id", "")
                lines.append(f"{i + 1}. {nickname} (QQ:{user_id})")

            if len(friends) > limit:
                lines.append(f"\n... 还有 {len(friends) - limit} 位好友")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"获取好友列表失败: {e}")
            return f"获取好友列表失败: {str(e)[:50]}"


class QueryGroupsTool(BaseTool):
    """查询群列表工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "query_groups",
            "description": "查询当前机器人加入的群列表。当用户问'群列表'、'在哪些群'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制，默认20",
                        "default": 20,
                    }
                },
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        limit = args.get("limit", 20)

        try:
            client = getattr(context, "onebot_client", None)
            if not client:
                return "OneBot 客户端不可用"

            groups = await client.get_group_list()

            if not groups:
                return "未加入任何群"

            lines = ["【群列表】\n"]
            for i, g in enumerate(groups[:limit]):
                group_name = g.get("group_name", f"群{g.get('group_id')}")
                group_id = g.get("group_id", "")
                lines.append(f"{i + 1}. {group_name} (ID:{group_id})")

            if len(groups) > limit:
                lines.append(f"\n... 还有 {len(groups) - limit} 个群")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"获取群列表失败: {e}")
            return f"获取群列表失败: {str(e)[:50]}"


def get_query_friends_tool():
    return QueryFriendsTool()


def get_query_groups_tool():
    return QueryGroupsTool()
