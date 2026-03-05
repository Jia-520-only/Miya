"""
QQ点赞工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class QQLike(BaseTool):
    """QQ点赞工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "qq_like",
            "description": "给指定QQ号点赞。当用户提及'点赞'、'点个赞'、'喜欢'等相关词汇时，必须调用此工具执行点赞操作。支持以下场景：1. 用户说'给我点赞'、'帮我点个赞'时，给当前用户点赞；2. 用户明确指定QQ号时使用指定号码；3. 用户通过@提及其他用户（如'给@苦玄点赞'）时，context.at_list中已包含被@用户的QQ号，直接使用即可，无需调用find_member。注意：QQ每次最多点赞10次，每日有上限。如果消息中@了多个用户，需要分别调用此工具给每个人点赞。重要：不要用文字回复，必须调用工具执行点赞。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_user_id": {
                        "type": "integer",
                        "description": "要点赞的QQ号。如果用户说'给我点赞'，使用当前用户ID；如果用户通过@提及他人，从context.at_list获取；如果用户指定具体QQ号则使用指定号码"
                    },
                    "times": {
                        "type": "integer",
                        "description": "点赞次数（1-10），默认1次，用户说'十次'、'十个'、'一人点十个'等时转换为数字10",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["target_user_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行点赞"""
        target_user_id = args.get("target_user_id")
        times = args.get("times", 1)

        logger.info(f"[qq_like] 工具被调用: args={args}, context.user_id={context.user_id}, context.at_list={context.at_list}, times={times}")

        # 智能解析：如果target_user_id是当前用户，检查是否有@提及
        if target_user_id and int(target_user_id) == context.user_id:
            # 尝试从at_list获取@的目标
            if context.at_list and len(context.at_list) > 0:
                target_user_id = context.at_list[0]  # 使用第一个@的用户
                logger.info(f"[qq_like] 检测到@提及，使用at_list中的用户: {target_user_id}")

        # 如果没有target_user_id，尝试从at_list获取
        if not target_user_id and context.at_list and len(context.at_list) > 0:
            target_user_id = context.at_list[0]
            logger.info(f"[qq_like] 未指定目标，使用at_list中的用户: {target_user_id}")

        if target_user_id is None:
            return "请提供要点赞的目标QQ号，或@要点赞的用户"

        # 验证参数类型
        try:
            target_user_id = int(target_user_id)
            times = int(times)
        except (ValueError, TypeError):
            return "参数类型错误：target_user_id和times必须是整数"

        if times < 1:
            return "点赞次数必须大于0"
        if times > 10:
            return "单次点赞次数不能超过10次"

        send_like_callback = context.send_like_callback
        if not send_like_callback:
            return "点赞功能不可用（回调函数未设置）"

        try:
            # 调用点赞回调
            await send_like_callback(target_user_id, times)

            if times == 1:
                return f"✅ 已给 QQ{target_user_id} 点赞。"
            else:
                return f"✅ 已给 QQ{target_user_id} 点赞 {times} 次。"

        except Exception as e:
            logger.error(f"点赞失败: {e}", exc_info=True)
            error_msg = str(e)

            # 根据错误消息提供更友好的提示
            if "SVIP 上限" in error_msg:
                return "点赞失败：今日给同一好友的点赞数已达SVIP上限"
            elif "点赞失败" in error_msg:
                return f"点赞失败：{error_msg}"
            else:
                return f"点赞失败：{error_msg}"
