"""
定时任务统计
"""

import logging
from datetime import datetime
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class GetScheduleStatsTool(BaseTool):
    """GetScheduleStatsTool"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_schedule_stats",
            "description": "获取定时任务统计信息。查看任务总数、各状态分布、最活跃的任务类型等。用于任务诊断和优化建议。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        try:
            scheduler = getattr(context, "scheduler", None)
            if not scheduler or not hasattr(scheduler, "task_store") or not scheduler.task_store:
                return "❌ 调度器未初始化或数据库不可用"

            stats = scheduler.task_store.get_stats()
            queue_size = len(getattr(scheduler, "task_queue", []))
            running_count = len(getattr(scheduler, "running_tasks", {}))

            total = sum(stats.values())
            if total == 0:
                return "📊 暂无定时任务记录"

            pending = stats.get("pending", 0)
            completed = stats.get("completed", 0)
            failed = stats.get("failed", 0)
            cancelled = stats.get("cancelled", 0)

            recent_tasks = scheduler.task_store.list_tasks(limit=10)

            result = "📊 定时任务统计\n"
            result += f"────────────────────────────\n"
            result += f"总任务数: {total}\n"
            result += f"  待执行: {pending} (队列中: {queue_size}, 运行中: {running_count})\n"
            result += f"  已完成: {completed}\n"
            result += f"  已取消: {cancelled}\n"
            result += f"  失败:   {failed}\n"
            result += f"────────────────────────────\n"

            if recent_tasks:
                result += f"\n📋 最近任务:\n"
                for i, t in enumerate(recent_tasks[:5], 1):
                    status_icon = {"pending": "⏳", "completed": "✅", "failed": "❌", "cancelled": "🚫"}.get(
                        t.get("status", ""), "❓"
                    )
                    msg = (t.get("message", "") or "")[:30]
                    result += f"  {i}. {status_icon} [{t.get('task_type', '?')}] {msg}\n"

            return result

        except Exception as e:
            logger.error(f"获取任务统计失败: {e}", exc_info=True)
            return f"❌ 获取任务统计失败: {str(e)}"
