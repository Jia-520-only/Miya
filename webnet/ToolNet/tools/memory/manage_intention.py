"""让明确约定可被保存、核实、暂停和收尾。"""

import asyncio
import json

from webnet.ToolNet.base import BaseTool, ToolContext


class ManageIntention(BaseTool):
    @property
    def config(self) -> dict:
        return {
            "name": "manage_intention",
            "description": (
                "当你答应持续跟进一件事时，必须先用 remember 保存具体事项与完成条件；"
                "执行关联工具前指定 action_name；后续回合继续之前用 resume 关联当前请求。"
                "失败不会自动完成，超时必须核实。用户确认完成用 confirm，"
                "确认未完成且要求重试用 retry，两者 evidence 必须引用当前用户原话。"
                "用户要求暂缓或不再继续时用 pause/abandon。list 查询当前会话事项。"
                "只有用户希望主动跟进时才设置 follow_up=true；该跟进只询问或报告进度，不自动重放工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": [
                        "remember", "list", "resume", "pause", "abandon", "confirm", "retry",
                    ]},
                    "intention_id": {"type": "string", "description": "已有事项的 ID"},
                    "title": {"type": "string", "description": "明确约定的事项"},
                    "expected_outcome": {"type": "string", "description": "可核实的完成条件"},
                    "action_name": {"type": "string", "description": "用于完成事项的确切工具名，可留空"},
                    "completion_mode": {"type": "string", "enum": ["user_confirmation", "action_success"],
                                        "description": "默认等待用户确认；仅工具成功足以满足完成条件时用 action_success"},
                    "follow_up": {"type": "boolean", "description": "是否希望主动跟进，默认 false"},
                    "evidence": {"type": "string", "description": "当前用户确认完成或要求重试的原话"},
                },
                "required": ["operation"],
                "additionalProperties": False,
            },
        }

    async def execute(self, args: dict, context: ToolContext) -> str:
        from core.miya_spine import get_existing_spine

        spine = get_existing_spine()
        if spine is None:
            return json.dumps({"success": False, "error": "生命事件总线尚未启用，无法保存持续事项"}, ensure_ascii=False)
        scope = {key: getattr(context, key, None) for key in (
            "user_id", "platform", "group_id", "session_id", "request_id", "message_id", "current_input",
        )}
        operation = args.get("operation")
        try:
            if operation == "list":
                result = await asyncio.to_thread(spine.list_intentions, scope, include_closed=True)
                return json.dumps({"success": True, "intentions": result}, ensure_ascii=False)
            if operation not in {"remember", "resume", "pause", "abandon", "confirm", "retry"}:
                raise ValueError("不支持的事项操作")
            values = {key: value for key, value in args.items() if key != "operation"}
            if operation == "remember" and values.get("action_name") == "manage_intention":
                raise ValueError("事项管理工具不能充当事项的完成行动")
            result = await asyncio.to_thread(spine.manage_intention, operation, scope, **values)
            return json.dumps({"success": True, "intention": result}, ensure_ascii=False)
        except (ValueError, TypeError) as exc:
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
