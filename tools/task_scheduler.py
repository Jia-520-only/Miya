"""
任务调度工具
支持定时任务、延时任务、周期任务等调度功能
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    func: Callable
    trigger_type: str  # date, interval, cron
    trigger_args: Dict[str, Any] = field(default_factory=dict)
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    max_instances: int = 1
    misfire_grace_time: int = 300
    coalesce: bool = True
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskExecution:
    """任务执行记录"""
    task_id: str
    execution_id: str
    status: TaskStatus
    started_at: str
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None


class TaskScheduler:
    """任务调度器"""

    def __init__(self, async_mode: bool = False, jobstore_path: str = None):
        """
        初始化任务调度器

        Args:
            async_mode: 是否使用异步模式
            jobstore_path: 任务存储路径（SQLAlchemy）
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError("APScheduler未安装，请先安装: pip install APScheduler")

        self.async_mode = async_mode
        self.tasks: Dict[str, ScheduledTask] = {}
        self.executions: List[TaskExecution] = []

        # 配置调度器
        if jobstore_path:
            jobstores = {
                'default': SQLAlchemyJobStore(url=f'sqlite:///{jobstore_path}')
            }
        else:
            jobstores = {'default': 'memory'}

        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }

        job_defaults = {
            'coalesce': True,
            'max_instances': 3,
            'misfire_grace_time': 300
        }

        if async_mode:
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults
            )
        else:
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults
            )

    def start(self) -> None:
        """启动调度器"""
        self.scheduler.start()
        logger.info("任务调度器已启动")

    def shutdown(self, wait: bool = True) -> None:
        """
        关闭调度器

        Args:
            wait: 是否等待任务完成
        """
        self.scheduler.shutdown(wait=wait)
        logger.info("任务调度器已关闭")

    def add_task(self, task: ScheduledTask) -> str:
        """
        添加任务

        Args:
            task: 调度任务

        Returns:
            任务ID
        """
        # 创建触发器
        trigger = self._create_trigger(task.trigger_type, task.trigger_args)

        # 包装函数，记录执行状态
        def wrapper(*args, **kwargs):
            execution_id = f"{task.task_id}_{datetime.now().timestamp()}"

            # 记录开始
            execution = TaskExecution(
                task_id=task.task_id,
                execution_id=execution_id,
                status=TaskStatus.RUNNING,
                started_at=datetime.now().isoformat()
            )
            self.executions.append(execution)

            try:
                # 执行任务
                result = task.func(*task.args, **task.kwargs)

                # 记录完成
                execution.status = TaskStatus.COMPLETED
                execution.completed_at = datetime.now().isoformat()
                execution.result = str(result)

                logger.info(f"任务执行成功: {task.name} ({execution_id})")
                return result
            except Exception as e:
                # 记录失败
                execution.status = TaskStatus.FAILED
                execution.completed_at = datetime.now().isoformat()
                execution.error = str(e)

                logger.error(f"任务执行失败: {task.name} ({execution_id}), 错误: {e}")
                raise

        # 添加到调度器
        job = self.scheduler.add_job(
            wrapper,
            trigger=trigger,
            id=task.task_id,
            name=task.name,
            args=(),
            kwargs={},
            max_instances=task.max_instances,
            misfire_grace_time=task.misfire_grace_time,
            coalesce=task.coalesce,
            replace_existing=True
        )

        self.tasks[task.task_id] = task
        logger.info(f"添加任务: {task.name} ({task.task_id})")

        return task.task_id

    def remove_task(self, task_id: str) -> None:
        """
        移除任务

        Args:
            task_id: 任务ID
        """
        try:
            self.scheduler.remove_job(task_id)
            del self.tasks[task_id]
            logger.info(f"移除任务: {task_id}")
        except Exception as e:
            logger.error(f"移除任务失败: {task_id}, 错误: {e}")

    def pause_task(self, task_id: str) -> None:
        """
        暂停任务

        Args:
            task_id: 任务ID
        """
        try:
            self.scheduler.pause_job(task_id)
            logger.info(f"暂停任务: {task_id}")
        except Exception as e:
            logger.error(f"暂停任务失败: {task_id}, 错误: {e}")

    def resume_task(self, task_id: str) -> None:
        """
        恢复任务

        Args:
            task_id: 任务ID
        """
        try:
            self.scheduler.resume_job(task_id)
            logger.info(f"恢复任务: {task_id}")
        except Exception as e:
            logger.error(f"恢复任务失败: {task_id}, 错误: {e}")

    def run_task_now(self, task_id: str) -> None:
        """
        立即运行任务

        Args:
            task_id: 任务ID
        """
        try:
            self.scheduler.modify_job(task_id, next_run_time=datetime.now())
            logger.info(f"立即运行任务: {task_id}")
        except Exception as e:
            logger.error(f"立即运行任务失败: {task_id}, 错误: {e}")

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            调度任务
        """
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[ScheduledTask]:
        """列出所有任务"""
        return list(self.tasks.values())

    def get_job_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息

        Args:
            task_id: 任务ID

        Returns:
            任务信息
        """
        try:
            job = self.scheduler.get_job(task_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                }
        except Exception as e:
            logger.error(f"获取任务信息失败: {task_id}, 错误: {e}")
        return None

    def _create_trigger(self, trigger_type: str, args: Dict[str, Any]):
        """
        创建触发器

        Args:
            trigger_type: 触发器类型
            args: 触发器参数

        Returns:
            触发器对象
        """
        if trigger_type == 'date':
            return DateTrigger(**args)
        elif trigger_type == 'interval':
            return IntervalTrigger(**args)
        elif trigger_type == 'cron':
            return CronTrigger(**args)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger_type}")

    def get_executions(self, task_id: str = None) -> List[TaskExecution]:
        """
        获取执行记录

        Args:
            task_id: 任务ID（可选）

        Returns:
            执行记录列表
        """
        if task_id:
            return [e for e in self.executions if e.task_id == task_id]
        return self.executions

    def get_running_jobs(self) -> List[str]:
        """
        获取正在运行的任务ID列表

        Returns:
            任务ID列表
        """
        running = [e.task_id for e in self.executions if e.status == TaskStatus.RUNNING]
        return list(set(running))

    def clear_executions(self, task_id: str = None, keep_recent: int = 100) -> None:
        """
        清除执行记录

        Args:
            task_id: 任务ID（可选）
            keep_recent: 保留最近的记录数
        """
        if task_id:
            # 清除特定任务的记录
            task_executions = [e for e in self.executions if e.task_id == task_id]
            self.executions = [e for e in self.executions if e not in task_executions[:-keep_recent]]
        else:
            # 清除所有记录
            self.executions = self.executions[-keep_recent:] if self.executions else []

        logger.info("执行记录已清理")


class TaskBuilder:
    """任务构建器"""

    def __init__(self, scheduler: TaskScheduler):
        """
        初始化任务构建器

        Args:
            scheduler: 任务调度器
        """
        self.scheduler = scheduler
        self.task_id: Optional[str] = None
        self.name: str = ""
        self.func: Optional[Callable] = None
        self.trigger_type: str = 'interval'
        self.trigger_args: Dict[str, Any] = {}
        self.args: tuple = ()
        self.kwargs: Dict[str, Any] = {}
        self.max_instances: int = 1
        self.description: str = ""

    def set_id(self, task_id: str) -> 'TaskBuilder':
        """设置任务ID"""
        self.task_id = task_id
        return self

    def set_name(self, name: str) -> 'TaskBuilder':
        """设置任务名称"""
        self.name = name
        return self

    def set_function(self, func: Callable) -> 'TaskBuilder':
        """设置执行函数"""
        self.func = func
        return self

    def interval(self, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0) -> 'TaskBuilder':
        """设置间隔触发"""
        self.trigger_type = 'interval'
        self.trigger_args = {
            'seconds': seconds,
            'minutes': minutes,
            'hours': hours,
            'days': days
        }
        return self

    def cron(self, minute: str = '*', hour: str = '*', day: str = '*',
             month: str = '*', day_of_week: str = '*') -> 'TaskBuilder':
        """设置Cron触发"""
        self.trigger_type = 'cron'
        self.trigger_args = {
            'minute': minute,
            'hour': hour,
            'day': day,
            'month': month,
            'day_of_week': day_of_week
        }
        return self

    def once(self, run_date: datetime) -> 'TaskBuilder':
        """设置单次触发"""
        self.trigger_type = 'date'
        self.trigger_args = {
            'run_date': run_date
        }
        return self

    def set_args(self, *args) -> 'TaskBuilder':
        """设置位置参数"""
        self.args = args
        return self

    def set_kwargs(self, **kwargs) -> 'TaskBuilder':
        """设置关键字参数"""
        self.kwargs = kwargs
        return self

    def set_description(self, description: str) -> 'TaskBuilder':
        """设置描述"""
        self.description = description
        return self

    def build(self) -> ScheduledTask:
        """构建任务"""
        if not self.task_id:
            self.task_id = f"task_{datetime.now().timestamp()}"

        return ScheduledTask(
            task_id=self.task_id,
            name=self.name,
            func=self.func,
            trigger_type=self.trigger_type,
            trigger_args=self.trigger_args,
            args=self.args,
            kwargs=self.kwargs,
            max_instances=self.max_instances,
            description=self.description
        )


# 便捷函数
def schedule_once(scheduler: TaskScheduler, func: Callable, run_date: datetime,
                   name: str = None, **kwargs) -> str:
    """
    调度单次任务

    Args:
        scheduler: 调度器
        func: 执行函数
        run_date: 运行时间
        name: 任务名称
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_id = f"once_{datetime.now().timestamp()}"

    task = ScheduledTask(
        task_id=task_id,
        name=name or func.__name__,
        func=func,
        trigger_type='date',
        trigger_args={'run_date': run_date},
        kwargs=kwargs
    )

    return scheduler.add_task(task)


def schedule_interval(scheduler: TaskScheduler, func: Callable,
                      interval_seconds: int, name: str = None, **kwargs) -> str:
    """
    调度间隔任务

    Args:
        scheduler: 调度器
        func: 执行函数
        interval_seconds: 间隔秒数
        name: 任务名称
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_id = f"interval_{func.__name__}_{datetime.now().timestamp()}"

    task = ScheduledTask(
        task_id=task_id,
        name=name or func.__name__,
        func=func,
        trigger_type='interval',
        trigger_args={'seconds': interval_seconds},
        kwargs=kwargs
    )

    return scheduler.add_task(task)


def schedule_cron(scheduler: TaskScheduler, func: Callable,
                  cron_expression: str, name: str = None, **kwargs) -> str:
    """
    调度Cron任务

    Args:
        scheduler: 调度器
        func: 执行函数
        cron_expression: Cron表达式
        name: 任务名称
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_id = f"cron_{func.__name__}_{datetime.now().timestamp()}"

    # 解析Cron表达式
    parts = cron_expression.split()
    if len(parts) >= 5:
        minute, hour, day, month, day_of_week = parts[:5]
    else:
        raise ValueError("无效的Cron表达式")

    task = ScheduledTask(
        task_id=task_id,
        name=name or func.__name__,
        func=func,
        trigger_type='cron',
        trigger_args={
            'minute': minute,
            'hour': hour,
            'day': day,
            'month': month,
            'day_of_week': day_of_week
        },
        kwargs=kwargs
    )

    return scheduler.add_task(task)


if __name__ == "__main__":
    # 示例使用
    scheduler = TaskScheduler()

    # 示例任务函数
    def hello_task(name: str):
        """示例任务"""
        print(f"Hello, {name}! Time: {datetime.now()}")
        return f"Greeted {name}"

    # 添加间隔任务
    interval_task = ScheduledTask(
        task_id="hello_interval",
        name="每分钟问候",
        func=hello_task,
        trigger_type='interval',
        trigger_args={'seconds': 30},
        kwargs={'name': 'World'}
    )

    scheduler.add_task(interval_task)

    # 启动调度器
    scheduler.start()

    print("调度器已启动，按Ctrl+C停止")
    print("任务列表:")
    for task in scheduler.list_tasks():
        print(f"  - {task.name} ({task.task_id})")

    try:
        import time
        time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown()
