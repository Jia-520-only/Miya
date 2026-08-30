"""
获取认知侧写工具 — 从 config 读取所有消息
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.cognitive.profile_storage import get_profile_storage

logger = logging.getLogger(__name__)


class GetProfileTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_profile",
            "description": "获取指定用户或群聊的认知侧写信息。侧写包含用户偏好、身份、习惯、群氛围等信息。当需要了解某人的偏好、习惯、身份，或了解群聊氛围时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "实体类型：user（用户）或 group（群聊）",
                        "enum": ["user", "group"],
                    },
                    "entity_id": {"type": "string", "description": "实体ID：用户QQ号或群号"},
                },
                "required": ["entity_type", "entity_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        entity_type = args.get("entity_type", "user")
        entity_id = str(args.get("entity_id", ""))

        if not entity_id or entity_id == "0" or entity_id == "None":
            if entity_type == "user":
                entity_id = str(getattr(context, "user_id", ""))
            elif entity_type == "group":
                entity_id = str(getattr(context, "group_id", ""))
        if not entity_id or entity_id == "0" or entity_id == "None":
            type_label = "用户" if entity_type == "user" else "群聊"
            return get_text_message("cognitive_memory", "entity_unknown", type=type_label)

        storage = get_profile_storage()
        profile = await storage.read_profile(entity_type, entity_id)

        if not profile:
            observations = await storage.get_observations(entity_type, entity_id, limit=10)
            if observations:
                type_label = "用户" if entity_type == "user" else "群聊"
                obs_text = "\n".join(f"- {o['observation']}" for o in observations[-5:])
                header = get_text_message("cognitive_memory", "preliminary_header", type=type_label)
                footer = get_text_message("cognitive_memory", "preliminary_footer")
                return f"{header}\n{obs_text}\n\n{footer}"
            type_label = "用户" if entity_type == "user" else "群聊"
            return get_text_message(
                "cognitive_memory",
                "no_profile_user" if entity_type == "user" else "no_profile_group",
                entity_id=entity_id,
            )

        return profile
