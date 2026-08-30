"""
编辑定时任务
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class UpdateScheduleTaskTool(BaseTool):
    """UpdateScheduleTaskTool"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "update_schedule_task",
            "description": "修改已存在的定时任务。可修改执行时间、消息内容、重复频率等。重要：此工具执行实际操作，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要修改的任务ID（使用 list_schedule_tasks 查看）",
                    },
                    "message": {
                        "type": "string",
                        "description": "新的消息内容（留空则不修改）",
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "新的执行时间，支持自然语言（如'明天 15:00'）。留空则不修改",
                    },
                    "repeat": {
                        "type": "string",
                        "description": "新的重复频率：once/daily/weekly/monthly",
                        "enum": ["once", "daily", "weekly", "monthly"],
                    },
                    "max_executions": {
                        "type": "integer",
                        "description": "新的最大执行次数",
                        "minimum": 1,
                    },
                    "priority": {
                        "type": "integer",
                        "description": "新的优先级 (1-10)",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["task_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        task_id = args.get("task_id", "").strip()
        if not task_id:
            return "❌ 任务ID不能为空"

        try:
            scheduler = getattr(context, "scheduler", None)
            if not scheduler or not hasattr(scheduler, "task_store") or not scheduler.task_store:
                return "❌ 调度器未初始化或数据库不可用"

            existing = scheduler.task_store.get_task(task_id)
            if not existing:
                return f"❌ 未找到任务: {task_id}"

            if existing["status"] not in ("pending",):
                return f"❌ 只能修改待执行的任务，当前状态: {existing['status']}"

            updated_fields = []

            if "message" in args and args["message"]:
                existing["message"] = args["message"]
                updated_fields.append("消息内容")

            if "repeat" in args and args["repeat"]:
                existing["repeat_type"] = args["repeat"]
                updated_fields.append("重复频率")

            if "max_executions" in args:
                existing["max_executions"] = args["max_executions"]
                updated_fields.append("最大执行次数")

            if "priority" in args:
                existing["priority"] = args["priority"]
                updated_fields.append("优先级")

            if "schedule_time" in args and args["schedule_time"]:
                try:
                    from webnet.ToolNet.tools.scheduler.time_parser import (
                        parse_smart_time,
                    )

                    new_time = parse_smart_time(args["schedule_time"])
                    if new_time:
                        existing["execute_at"] = new_time.isoformat()
                        updated_fields.append(f"执行时间 -> {new_time.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        return f"❌ 无法解析时间表达式: {args['schedule_time']}"
                except Exception as e:
                    return f"❌ 时间解析失败: {e}"

            if not updated_fields:
                return "⚠️ 未修改任何字段"

            scheduler.task_store.save_task(existing)

            # 从队列中移除旧任务并重新调度
            queue = getattr(scheduler, "task_queue", [])
            scheduler.task_queue = [t for t in queue if getattr(t, "task_id", "") != task_id]
            if hasattr(scheduler, "_sync_queued_ids"):
                scheduler._sync_queued_ids()

            from hub.scheduler import Task

            execute_at = datetime.fromisoformat(existing["execute_at"])
            new_task = Task(
                task_id=task_id,
                task_type=f"scheduled_{existing['task_type']}",
                priority=existing.get("priority", 5),
                data={
                    "task_id": task_id,
                    "task_type": existing["task_type"],
                    "target_type": existing.get("target_type"),
                    "target_id": existing.get("target_id"),
                    "message": existing.get("message", ""),
                    "repeat": existing.get("repeat_type", "once"),
                    "repeat_config": existing.get("repeat_config"),
                    "max_executions": existing.get("max_executions"),
                    "execution_count": existing.get("execution_count", 0),
                    "priority": existing.get("priority", 5),
                    "platform": existing.get("platform"),
                    "action_type": existing.get("action_type"),
                    "action_times": existing.get("action_times", 1),
                    "created_by": existing.get("created_by", ""),
                    "scheduled_at": existing["execute_at"],
                },
                execute_at=execute_at,
            )
            scheduler.schedule(new_task)

            return f"✅ 任务已更新\n任务ID: {task_id}\n修改项: {', '.join(updated_fields)}"

        except Exception as e:
            logger.error(f"更新定时任务失败: {e}", exc_info=True)
            return f"❌ 更新定时任务失败: {str(e)}"
