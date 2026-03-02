"""
删除指定定时任务
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class DeleteScheduleTask(BaseTool):
    """DeleteScheduleTask"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "delete_schedule_task",
            "description": "删除指定的定时任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务ID（使用 list_schedule_tasks 查看）"
                    }
                },
                "required": ["task_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        task_id = args.get("task_id", "").strip()

        if not task_id:
            return "❌ 任务ID不能为空"

        try:
            deleted = False
            deleted_from = []

            if context.memory_engine:
                # 从潮汐记忆中删除
                memory_key = f"scheduled_task_{task_id}"
                if memory_key in context.memory_engine.tide_memory:
                    del context.memory_engine.tide_memory[memory_key]
                    deleted = True
                    deleted_from.append("短期记忆")

                # 从梦境记忆中删除
                if memory_key in context.memory_engine.dream_memory:
                    del context.memory_engine.dream_memory[memory_key]
                    deleted = True
                    deleted_from.append("长期记忆")

                # 从元数据中删除
                if memory_key in context.memory_engine.memory_metadata:
                    del context.memory_engine.memory_metadata[memory_key]

            # 从调度器中删除（如果有）
            scheduler = getattr(context, 'scheduler', None)
            if scheduler:
                # 从队列中删除
                task_queue = getattr(scheduler, 'task_queue', [])
                scheduler.task_queue = [t for t in task_queue if getattr(t, 'task_id', '') != task_id]

                # 从运行中的任务中删除
                running_tasks = getattr(scheduler, 'running_tasks', {})
                if task_id in running_tasks:
                    del running_tasks[task_id]
                    deleted = True
                    deleted_from.append("调度器")

                # 从已完成的任务中删除
                completed_tasks = getattr(scheduler, 'completed_tasks', {})
                if task_id in completed_tasks:
                    del completed_tasks[task_id]
                    deleted = True
                    deleted_from.append("调度器历史")

                if task_id in [t['task_id'] for t in getattr(scheduler, 'task_history', [])]:
                    scheduler.task_history = [t for t in scheduler.task_history if t.task_id != task_id]
                    deleted = True

            if deleted:
                from_str = ", ".join(deleted_from) if deleted_from else "未知位置"
                return f"✅ 已删除定时任务\n任务ID: {task_id}\n来源: {from_str}"
            else:
                # 尝试模糊搜索
                if context.memory_engine:
                    all_memories = {
                        **context.memory_engine.tide_memory,
                        **context.memory_engine.dream_memory
                    }
                    similar_ids = [
                        mid for mid in all_memories.keys()
                        if task_id.lower() in mid.lower() and "scheduled_task" in mid
                    ]
                    if similar_ids:
                        return f"❌ 未找到精确匹配的任务: {task_id}\n\n相似的任务ID:\n{', '.join(similar_ids[:5])}"

                return f"❌ 未找到任务: {task_id}\n\n提示: 使用 list_schedule_tasks 查看所有任务ID"

        except Exception as e:
            logger.error(f"删除定时任务失败: {e}", exc_info=True)
            return f"❌ 删除定时任务失败: {str(e)}"
