"""
获取用户信息工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetUserInfo(BaseTool):
    """获取用户信息工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_user_info",
            "description": "获取QQ用户的详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "用户QQ号"
                    },
                    "no_cache": {
                        "type": "boolean",
                        "description": "是否强制刷新，不使用缓存",
                        "default": False
                    }
                },
                "required": ["user_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行获取用户信息

        Args:
            args: {user_id, no_cache}
            context: 执行上下文

        Returns:
            用户信息字符串
        """
        user_id = args.get("user_id")
        no_cache = args.get("no_cache", False)

        if not user_id:
            return "用户QQ号不能为空"

        if not context.onebot_client:
            return "OneBot客户端未初始化"

        try:
            # 调用OneBot API
            info = await context.onebot_client.get_stranger_info(user_id, no_cache=no_cache)

            # 格式化返回
            result = f"""用户信息:
QQ号: {info.get('user_id')}
昵称: {info.get('nickname')}
性别: {info.get('sex', 'unknown')}
等级: {info.get('level')}
签名: {info.get('sign', '无')}"""

            return result

        except Exception as e:
            logger.error(f"获取用户信息失败: {e}", exc_info=True)
            return f"获取用户信息失败: {str(e)}"
