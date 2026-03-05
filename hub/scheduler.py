"""
任务调度
管理和调度系统任务
"""
from typing import Dict, List, Optional
import heapq
import asyncio
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class Task:
    """任务类"""

    def __init__(self, task_id: str, task_type: str, priority: int, data: Dict, execute_at: Optional[datetime] = None):
        self.task_id = task_id
        self.task_type = task_type
        self.priority = priority
        self.data = data
        self.created_at = datetime.now()
        self.scheduled_at = None
        self.execute_at = execute_at or datetime.now()
        self.completed_at = None
        self.status = 'pending'

    def __lt__(self, other):
        # 按执行时间排序，如果时间相同则按优先级
        if self.execute_at != other.execute_at:
            return self.execute_at < other.execute_at
        return self.priority < other.priority

    def __lt__(self, other):
        return self.priority < other.priority


class Scheduler:
    """任务调度器"""

    def __init__(self, tool_registry=None, onebot_client=None):
        self.task_queue = []
        self.running_tasks = {}
        self.completed_tasks = {}
        self.task_history = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.tool_registry = tool_registry
        self.onebot_client = onebot_client

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已经在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("任务调度器已启动")

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("任务调度器已停止")

    async def _run_loop(self):
        """调度循环"""
        while self._running:
            try:
                # 检查是否有待执行的任务
                if self.task_queue:
                    now = datetime.now()
                    # 查看队首任务（不弹出）
                    next_task = self.task_queue[0]
                    if next_task.execute_at <= now:
                        # 任务时间到了，执行
                        heapq.heappop(self.task_queue)
                        logger.info(f"执行定时任务: {next_task.task_id}, 类型: {next_task.task_type}")
                        await self._execute_task(next_task)

                # 等待一段时间再检查
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环错误: {e}", exc_info=True)

    async def _execute_task(self, task: Task):
        """执行任务"""
        task.status = 'running'
        self.running_tasks[task.task_id] = task

        try:
            # 构建工具上下文
            tool_context = {
                'onebot_client': self.onebot_client,
                'send_like_callback': getattr(self.onebot_client, 'send_like', None) if self.onebot_client else None,
                'user_id': task.data.get('target_id'),
                'group_id': task.data.get('target_id') if task.data.get('target_type') == 'group' else None,
                'message_type': task.data.get('target_type', 'private'),
                'sender_name': 'scheduled_task'
            }

            # 根据任务类型执行不同的操作
            if task.task_type == 'scheduled_reminder':
                # 定时提醒任务 - 发送消息提醒
                data = task.data
                target_type = data.get('target_type', 'private')
                target_id = data.get('target_id')
                message = data.get('message', '')

                logger.info(f"执行提醒任务: 目标={target_type}_{target_id}, 消息={message}")

                # 直接使用 onebot_client 发送消息（避免 tool_context 的 qq_net 依赖）
                if self.onebot_client:
                    try:
                        if target_type == 'group':
                            await self.onebot_client.send_group_message(target_id, message)
                            logger.info(f"提醒消息已发送到群 {target_id}")
                        else:
                            await self.onebot_client.send_private_message(target_id, message)
                            logger.info(f"提醒消息已发送到用户 {target_id}")
                    except Exception as e:
                        logger.error(f"发送提醒消息失败: {e}", exc_info=True)

            elif task.task_type == 'scheduled_message':
                # 定时发送消息任务
                data = task.data
                target_type = data.get('target_type', 'private')
                target_id = data.get('target_id')
                message = data.get('message', '')

                logger.info(f"发送定时消息: 目标={target_type}_{target_id}, 消息={message}")

                # 直接使用 onebot_client 发送消息
                if self.onebot_client:
                    try:
                        if target_type == 'group':
                            await self.onebot_client.send_group_message(target_id, message)
                            logger.info(f"定时消息已发送到群 {target_id}")
                        else:
                            await self.onebot_client.send_private_message(target_id, message)
                            logger.info(f"定时消息已发送到用户 {target_id}")
                    except Exception as e:
                        logger.error(f"发送定时消息失败: {e}", exc_info=True)

            elif task.task_type == 'scheduled_action':
                # 定时执行动作（如点赞等）
                data = task.data
                action_type = data.get('action_type', '')
                target_id = data.get('target_id')
                message = data.get('message', '')

                logger.info(f"执行定时动作: 类型={action_type}, 目标={target_id}")

                # 根据动作类型调用相应工具
                if self.tool_registry and action_type:
                    from core.tool_adapter import ToolAdapter
                    adapter = ToolAdapter()
                    adapter.set_tool_registry(self.tool_registry)

                    if action_type == 'qq_like':
                        args = {
                            'target_user_id': target_id,
                            'times': data.get('times', 1)
                        }
                        result = await adapter.execute_tool('qq_like', args, tool_context)
                        logger.info(f"点赞动作已执行: {result}")

                    elif action_type == 'send_poke':
                        args = {
                            'target_user_id': target_id,
                            'group_id': target_id if task.data.get('target_type') == 'group' else None
                        }
                        result = await adapter.execute_tool('send_poke', args, tool_context)
                        logger.info(f"拍一拍动作已执行: {result}")

            # 标记任务完成
            self.complete_task(task.task_id, {'result': 'success'})

        except Exception as e:
            logger.error(f"任务执行失败 {task.task_id}: {e}", exc_info=True)
            self.fail_task(task.task_id, str(e))

    def schedule(self, task: Task) -> None:
        """添加任务到调度队列"""
        heapq.heappush(self.task_queue, task)
        task.scheduled_at = datetime.now()
        logger.info(f"任务已添加到调度队列: {task.task_id}, 执行时间: {task.execute_at}")

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务"""
        if not self.task_queue:
            return None

        task = heapq.heappop(self.task_queue)
        task.status = 'running'
        self.running_tasks[task.task_id] = task
        return task

    def complete_task(self, task_id: str, result: Dict = None) -> None:
        """完成任务"""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.status = 'completed'
            task.completed_at = datetime.now()
            task.result = result
            self.completed_tasks[task_id] = task
            self.task_history.append(task)

            # 只保留最近100条历史
            if len(self.task_history) > 100:
                self.task_history = self.task_history[-100:]

    def fail_task(self, task_id: str, error: str) -> None:
        """任务失败"""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.status = 'failed'
            task.error = error
            task.completed_at = datetime.now()
            self.task_history.append(task)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        # 检查运行中的任务
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                'status': task.status,
                'type': task.task_type,
                'created_at': task.created_at.isoformat(),
                'running_time': (datetime.now() - task.created_at).total_seconds()
            }

        # 检查已完成的任务
        if task_id in self.completed_tasks:
            task = self.completed_tasks[task_id]
            return {
                'status': task.status,
                'type': task.task_type,
                'created_at': task.created_at.isoformat(),
                'completed_at': task.completed_at.isoformat()
            }

        return None

    def get_queue_info(self) -> Dict:
        """获取队列信息"""
        return {
            'pending': len(self.task_queue),
            'running': len(self.running_tasks),
            'completed': len(self.completed_tasks),
            'total': len(self.task_history)
        }

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """清理旧任务"""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)

        to_remove = [
            tid for tid, task in self.completed_tasks.items()
            if task.completed_at < cutoff
        ]

        for tid in to_remove:
            del self.completed_tasks[tid]

        return len(to_remove)
