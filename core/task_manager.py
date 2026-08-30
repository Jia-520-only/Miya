"""
弥娅任务管理器 - 后台任务队列+Worker线程

从 NagaAgent 引入的任务管理系统，用于异步处理：
- 五元组知识图谱提取
- 记忆持久化
- 工具执行等耗时操作

特点：
- 异步任务队列
- 可配置 Worker 数量
- 自动重试机制
- 任务状态追踪
- 自动清理过期任务
"""

import asyncio
import hashlib
import logging
import time
import traceback
import weakref
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MiyaTask:
    """弥娅任务定义"""

    task_id: str
    task_type: str  # "quintuple_extract", "memory_save", "tool_execute", etc.
    payload: Dict[str, Any]  # 任务数据
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    future: Optional[asyncio.Future] = None


class MiyaTaskManager:
    """弥娅任务管理器 - 后台任务处理系统"""

    _instance = None
    _weak_ref = None

    @classmethod
    def get_instance(cls, max_workers: int = 3, max_queue_size: int = 100) -> "MiyaTaskManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(max_workers, max_queue_size)
            cls._weak_ref = weakref.ref(cls._instance)
        return cls._instance

    def __init__(self, max_workers: int = 3, max_queue_size: int = 100):
        """初始化任务管理器"""
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        # 任务存储
        self.tasks: Dict[str, MiyaTask] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)

        # Worker 管理
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
        self._lock = asyncio.Lock()

        # 统计信息
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = 0

        # 回调函数
        self.on_task_completed: Optional[Callable] = None
        self.on_task_failed: Optional[Callable] = None

        # 自动清理任务
        self.cleanup_task: Optional[asyncio.Task] = None
        self.auto_cleanup_hours = 24  # 24小时自动清理

        # 任务处理器映射
        self._task_handlers: Dict[str, Callable] = {}

        logger.info(f"[TaskManager] 初始化完成: workers={max_workers}, queue_size={max_queue_size}")

    def register_handler(self, task_type: str, handler: Callable) -> None:
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        logger.info(f"[TaskManager] 注册任务处理器: {task_type}")

    async def start(self) -> None:
        """启动任务管理器"""
        if self.is_running:
            logger.info("[TaskManager] 已在运行")
            return

        logger.info("[TaskManager] 正在启动...")
        self.is_running = True

        # 启动 Worker
        loop = asyncio.get_running_loop()
        for i in range(self.max_workers):
            task = loop.create_task(self._worker(i))
            self.worker_tasks.append(task)

        # 启动自动清理
        self.cleanup_task = loop.create_task(self._auto_cleanup())

        logger.info(f"[TaskManager] 启动完成: {self.max_workers} workers")

    async def stop(self) -> None:
        """停止任务管理器"""
        if not self.is_running:
            return

        logger.info("[TaskManager] 正在停止...")
        self.is_running = False

        # 取消所有 worker
        for task in self.worker_tasks:
            task.cancel()

        # 等待所有 worker 完成
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        # 取消清理任务
        if self.cleanup_task:
            self.cleanup_task.cancel()

        self.worker_tasks.clear()
        logger.info("[TaskManager] 已停止")

    async def add_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """添加任务到队列"""
        # 生成任务ID
        if not task_id:
            task_id = self._generate_task_id(task_type, payload)

        # 检查是否已存在（避免重复）
        if task_id in self.tasks and self.tasks[task_id].status == TaskStatus.RUNNING:
            logger.warning(f"[TaskManager] 任务 {task_id} 已在运行中")
            return task_id

        # 创建任务
        task = MiyaTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            max_retries=max_retries,
        )

        self.tasks[task_id] = task
        self.total_tasks += 1

        # 加入队列
        try:
            self.task_queue.put_nowait(task)
            logger.info(f"[TaskManager] 添加任务: {task_id} ({task_type})")
        except asyncio.QueueFull:
            logger.error("[TaskManager] 任务队列已满")
            task.status = TaskStatus.FAILED
            task.error = "任务队列已满"

        return task_id

    async def _worker(self, worker_id: int) -> None:
        """Worker 协程 - 处理队列中的任务"""
        logger.info(f"[TaskManager] Worker {worker_id} 启动")

        while self.is_running:
            try:
                # 从队列获取任务（带超时以便检查is_running）
                try:
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # 执行任务
                await self._execute_task(task, worker_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskManager] Worker {worker_id} 异常: {e}")

        logger.info(f"[TaskManager] Worker {worker_id} 停止")

    async def _execute_task(self, task: MiyaTask, worker_id: int) -> None:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        logger.info(f"[TaskManager] Worker {worker_id} 执行任务: {task.task_id}")

        try:
            # 获取处理器
            handler = self._task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"未注册的任务处理器: {task.task_type}")

            # 执行处理
            result = await handler(task.payload)

            # 成功
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            self.completed_tasks += 1

            # 触发回调
            if self.on_task_completed:
                try:
                    self.on_task_completed(task.task_id, result)
                except Exception as e:
                    logger.error(f"[TaskManager] 任务完成回调失败: {e}")

            logger.info(f"[TaskManager] 任务完成: {task.task_id}")

        except Exception as e:
            logger.error(f"[TaskManager] 任务执行失败: {e}\n{traceback.format_exc()}")

            task.error = str(e)

            # 重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.info(f"[TaskManager] 任务重试 ({task.retry_count}/{task.max_retries}): {task.task_id}")
                self.task_queue.put_nowait(task)
            else:
                task.status = TaskStatus.FAILED
                self.failed_tasks += 1

                # 触发失败回调
                if self.on_task_failed:
                    try:
                        self.on_task_failed(task.task_id, e)
                    except Exception as cb_error:
                        logger.error(f"[TaskManager] 任务失败回调失败: {cb_error}")

    async def _auto_cleanup(self) -> None:
        """自动清理过期任务"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次

                now = time.time()
                to_remove = []

                for task_id, task in self.tasks.items():
                    # 清理已完成超过24小时的任务
                    if task.completed_at and (now - task.completed_at) > 86400:
                        to_remove.append(task_id)

                for task_id in to_remove:
                    del self.tasks[task_id]

                if to_remove:
                    logger.info(f"[TaskManager] 自动清理 {len(to_remove)} 个过期任务")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskManager] 自动清理异常: {e}")

    def _generate_task_id(self, task_type: str, payload: Dict[str, Any]) -> str:
        """生成唯一任务ID"""
        content = f"{task_type}:{str(payload)}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "retry_count": task.retry_count,
            "error": task.error,
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        running = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING)
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)

        return {
            "total_tasks": self.total_tasks,
            "completed": self.completed_tasks,
            "failed": self.failed_tasks,
            "running": running,
            "pending": pending,
            "queue_size": self.task_queue.qsize(),
            "workers": self.max_workers,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            logger.info(f"[TaskManager] 任务已取消: {task_id}")
            return True

        return False


# 全局单例
_task_manager_instance: Optional[MiyaTaskManager] = None


def get_task_manager() -> MiyaTaskManager:
    """获取任务管理器全局实例"""
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = MiyaTaskManager.get_instance()
    return _task_manager_instance


async def start_task_manager() -> None:
    """启动任务管理器（便捷函数）"""
    manager = get_task_manager()
    await manager.start()


async def stop_task_manager() -> None:
    """停止任务管理器（便捷函数）"""
    global _task_manager_instance
    if _task_manager_instance:
        await _task_manager_instance.stop()
        _task_manager_instance = None


# 使用示例
if __name__ == "__main__":

    async def main():
        # 获取管理器
        manager = get_task_manager()

        # 注册处理器
        async def handle_quintuple_extract(payload: Dict) -> List:
            # 模拟处理
            await asyncio.sleep(2)
            return ["五元组1", "五元组2"]

        manager.register_handler("quintuple_extract", handle_quintuple_extract)

        # 启动
        await manager.start()

        # 添加任务
        await manager.add_task(
            task_type="quintuple_extract",
            payload={"text": "用户说今天天气很好"},
            max_retries=3,
        )

        # 等待完成
        await asyncio.sleep(5)

        # 获取统计
        print(manager.get_stats())

        # 停止
        await manager.stop()

    asyncio.run(main())
