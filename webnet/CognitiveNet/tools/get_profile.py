"""
获取用户/群聊侧写
"""
from typing import Dict, Any
import logging
import json
from datetime import datetime
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetProfile(BaseTool):
    """GetProfile"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_profile",
            "description": "获取用户或群聊的侧写信息（基于历史交互构建的画像）",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_type": {
                        "type": "string",
                        "description": "目标类型",
                        "enum": ["user", "group"],
                        "default": "user"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标ID（用户QQ号或群号）。不指定则使用当前会话"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        target_type = args.get("target_type", "user")
        target_id = args.get("target_id")

        try:
            # 确定目标ID
            if target_id is None:
                if target_type == "group":
                    target_id = context.group_id
                else:
                    target_id = context.user_id

            if target_id is None:
                return "❌ 无法确定目标ID，请手动指定 target_id"

            # 尝试从记忆引擎获取侧写
            profile_key = f"profile_{target_type}_{target_id}"
            profile_data = None

            if context.memory_engine:
                # 检查梦境记忆
                if profile_key in context.memory_engine.dream_memory:
                    profile_data = context.memory_engine.dream_memory[profile_key]

                # 检查潮汐记忆
                if not profile_data and profile_key in context.memory_engine.tide_memory:
                    profile_data = context.memory_engine.tide_memory[profile_key]

            if profile_data and isinstance(profile_data, dict):
                # 返回已保存的侧写
                result = f"📊 {target_type.capitalize()} 侧写\nID: {target_id}\n\n"

                for key, value in profile_data.items():
                    if key == "last_updated":
                        continue
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                    elif isinstance(value, dict):
                        value_str = json.dumps(value, ensure_ascii=False)
                    else:
                        value_str = str(value)
                    result += f"**{key}**: {value_str}\n"

                last_updated = profile_data.get("last_updated", "未知")
                result += f"\n最后更新: {last_updated}"
                return result
            else:
                # 侧写不存在，创建基础侧写
                base_profile = {
                    "type": target_type,
                    "id": target_id,
                    "created_at": datetime.now().isoformat(),
                    "interactions": 0,
                    "topics": [],
                    "traits": []
                }

                # 如果是群，添加群信息
                if target_type == "group":
                    base_profile.update({
                        "member_count": "未知",
                        "description": "暂无描述"
                    })
                # 如果是用户，添加用户信息
                elif target_type == "user":
                    base_profile.update({
                        "nickname": context.sender_name or "未知",
                        "groups": [],
                        "interests": []
                    })

                result = f"📊 {target_type.capitalize()} 侧写（新）\nID: {target_id}\n\n"
                result += f"⚠️ 尚无历史侧写数据\n\n"
                result += "基础信息:\n"
                for key, value in base_profile.items():
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                    else:
                        value_str = str(value)
                    result += f"  {key}: {value_str}\n"

                return result

        except Exception as e:
            logger.error(f"获取侧写失败: {e}", exc_info=True)
            return f"❌ 获取侧写失败: {str(e)}"
