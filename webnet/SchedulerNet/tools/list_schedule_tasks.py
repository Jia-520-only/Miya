"""
列出所有定时任务
"""
from typing import Dict, Any
import logging
from datetime import datetime
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class ListScheduleTasks(BaseTool):
    """ListScheduleTasks"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "list_schedule_tasks",
            "description": "列出所有定时任务。当用户说'查看任务'、'列出任务'、'查看提醒'、'任务列表'等时必须调用此工具。重要：此工具执行实际查询操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "筛选状态：all(全部), pending(待执行), running(执行中), completed(已完成)",
                        "enum": ["all", "pending", "running", "completed"],
                        "default": "all"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数量，默认20",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        status_filter = args.get("status", "all")
        limit = args.get("limit", 20)

        try:
            tasks = []

            if context.memory_engine:
                # 从记忆中获取任务
                all_memories = {
                    **context.memory_engine.tide_memory,
                    **context.memory_engine.dream_memory
                }

                for memory_id, memory_data in all_memories.items():
                    if not memory_id.startswith("scheduled_task_"):
                        continue

                    if isinstance(memory_data, dict):
                        task_info = {
                            'id': memory_id.replace("scheduled_task_", ""),
                            'data': memory_data
                        }
                        tasks.append(task_info)

                # 如果有调度器，获取任务状态
                scheduler = getattr(context, 'scheduler', None)
                if scheduler:
                    # 添加调度器中的任务
                    task_queue = getattr(scheduler, 'task_queue', [])
                    running_tasks = getattr(scheduler, 'running_tasks', {})
                    completed_tasks = getattr(scheduler, 'completed_tasks', {})

                    for task in task_queue:
                        task_id = getattr(task, 'task_id', '')
                        if task_id and task_id not in [t['id'] for t in tasks]:
                            tasks.append({
                                'id': task_id,
                                'data': {
                                    'task_type': getattr(task, 'task_type', 'unknown'),
                                    'status': 'pending'
                                }
                            })

                    for task_id, task in running_tasks.items():
                        if task_id not in [t['id'] for t in tasks]:
                            tasks.append({
                                'id': task_id,
                                'data': {
                                    'task_type': getattr(task, 'task_type', 'unknown'),
                                    'status': 'running'
                                }
                            })
                        else:
                            # 更新状态
                            for t in tasks:
                                if t['id'] == task_id:
                                    t['data']['status'] = 'running'

                    for task_id, task in completed_tasks.items():
                        if task_id not in [t['id'] for t in tasks]:
                            tasks.append({
                                'id': task_id,
                                'data': {
                                    'task_type': getattr(task, 'task_type', 'unknown'),
                                    'status': 'completed'
                                }
                            })
                        else:
                            # 更新状态
                            for t in tasks:
                                if t['id'] == task_id:
                                    t['data']['status'] = 'completed'

            if not tasks:
                return "📭 暂无定时任务"

            # 状态筛选
            if status_filter != "all":
                tasks = [t for t in tasks if t['data'].get('status') == status_filter]

            # 限制结果
            tasks = tasks[:limit]

            # 格式化输出
            result = f"📅 定时任务列表\n"
            result += f"状态筛选: {status_filter}\n"
            result += f"共 {len(tasks)} 个任务\n\n"

            for i, task in enumerate(tasks, 1):
                task_id = task['id']
                data = task['data']

                task_type = data.get('task_type', 'unknown')
                task_status = data.get('status', 'unknown')

                # 状态图标
                status_icon = {
                    'pending': '⏳',
                    'running': '▶️',
                    'completed': '✅',
                    'failed': '❌'
                }.get(task_status, '❓')

                result += f"{i}. {status_icon} **{task_id}**\n"
                result += f"   类型: {task_type}\n"

                # 显示任务详细信息
                if 'target_type' in data:
                    target_type = data.get('target_type', '')
                    target_id = data.get('target_id', '')
                    result += f"   目标: {target_type}_{target_id}\n"

                if 'message' in data:
                    message = data['message'][:50] + "..." if len(data['message']) > 50 else data['message']
                    result += f"   消息: {message}\n"

                if 'scheduled_at' in data:
                    schedule_time = data['scheduled_at']
                    try:
                        dt = datetime.fromisoformat(schedule_time)
                        result += f"   执行时间: {dt.strftime('%Y-%m-%d %H:%M')}\n"
                    except:
                        result += f"   执行时间: {schedule_time}\n"

                if 'repeat' in data:
                    result += f"   重复: {data['repeat']}\n"

                result += "\n"

            return result

        except Exception as e:
            logger.error(f"列出定时任务失败: {e}", exc_info=True)
            return f"❌ 列出定时任务失败: {str(e)}"
