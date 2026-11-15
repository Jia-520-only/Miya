"""
权限检查工具
"""

import json
import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool

logger = logging.getLogger(__name__)


class CheckPermissionTool(BaseTool):
    """检查权限工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "check_permission",
            "description": "检查用户是否有指定权限。用于在执行敏感操作前验证用户权限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID（格式: platform_id，如: qq_123, web_user456）",
                    },
                    "platform": {
                        "type": "string",
                        "description": "原始 user_id 所属平台；user_id 已是 platform_id 格式时可省略",
                    },
                    "permission": {
                        "type": "string",
                        "description": "权限节点（如: tool.web_search, agent.task.execute）",
                    },
                    "list_mode": {
                        "type": "boolean",
                        "description": "是否返回所有权限列表（默认为False，只检查是否有权限）",
                        "default": False,
                    },
                },
                "required": ["user_id", "permission"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行权限检查"""
        try:
            from core.unified_permission import get_permission_engine
            from webnet.AuthNet.user_mapper import UserMapper

            requested_id = str(args.get("user_id") or "").strip()
            permission = str(args.get("permission") or "").strip()
            platform = args.get("platform") or getattr(context, "platform", None)
            if isinstance(context, dict):
                platform = args.get("platform") or context.get("platform")
            if not requested_id or not permission:
                return json.dumps({
                    "success": False, "allowed": False, "error": "user_id 和 permission 均为必填项",
                }, ensure_ascii=False)

            caller_id = context.get("user_id") if isinstance(context, dict) else getattr(context, "user_id", None)
            caller_platform = context.get("platform") if isinstance(context, dict) else getattr(context, "platform", None)
            mapper = UserMapper()

            def normalize(user_id: str, user_platform: str | None) -> str:
                if "_" in user_id or not user_platform:
                    return user_id
                return mapper.generate_user_id(user_platform, user_id)

            target_id = normalize(requested_id, platform)
            if not caller_id:
                return json.dumps({
                    "success": False, "allowed": False, "error": "缺少调用者身份，无法查询权限",
                }, ensure_ascii=False)
            normalized_caller = normalize(str(caller_id), caller_platform)

            engine = get_permission_engine()
            if target_id != normalized_caller:
                can_inspect_others = any(
                    engine.check(normalized_caller, permission_name, context={"platform": caller_platform})
                    for permission_name in ("system.permissions.read", "system.permissions.manage")
                )
                if not can_inspect_others:
                    return json.dumps({
                        "success": False, "allowed": False, "error": "无权查询其他用户的权限",
                    }, ensure_ascii=False)

            if args.get("list_mode", False):
                permissions = engine.get_user_permissions_list(target_id, context={"platform": platform})
                payload = {"success": True, "user_id": target_id, "permissions": permissions}
            else:
                group_id = context.get("group_id") if isinstance(context, dict) else getattr(context, "group_id", None)
                allowed = engine.check(target_id, permission, context={
                    "platform": platform,
                    "group_id": group_id,
                })
                payload = {
                    "success": True,
                    "user_id": target_id,
                    "permission": permission,
                    "allowed": allowed,
                }

            return json.dumps(payload, ensure_ascii=False)

        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return json.dumps({"success": False, "allowed": False, "error": str(e)}, ensure_ascii=False)
