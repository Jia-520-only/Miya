"""
任务调度
管理和调度系统任务
"""

import asyncio
import contextlib
import heapq
import json
import logging
import sys
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from hub.task_store import TaskStore

logger = logging.getLogger(__name__)


class Task:
    """任务类"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        priority: int,
        data: Dict,
        execute_at: Optional[datetime] = None,
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.priority = priority
        self.data = data
        self.created_at = datetime.now()
        self.scheduled_at = None
        self.execute_at = execute_at or datetime.now()
        self.completed_at = None
        self.status = "pending"

    def __lt__(self, other):
        # 按执行时间排序，如果时间相同则按优先级
        if self.execute_at != other.execute_at:
            return self.execute_at < other.execute_at
        return self.priority < other.priority


class Scheduler:
    """任务调度器"""

    def __init__(
        self, tool_registry=None, onebot_client=None, task_store: Optional[TaskStore] = None, memory_manager=None
    ):
        self.task_queue = []
        self.running_tasks = {}
        self.completed_tasks = {}
        self.task_history = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self.tool_registry = tool_registry
        self.onebot_client = onebot_client
        self.terminal_callback: Optional[Callable[[str], Any]] = None
        self.task_store = task_store
        self.memory_manager = memory_manager
        self._online_users: set = set()
        self._last_condition_check = datetime.now()
        self.main_event_loop: Optional[asyncio.AbstractEventLoop] = None
        # 队列中任务 ID 集合（防重复入队）
        self._queued_task_ids: set = set()
        # 启动锁 + 启动标记（防止多线程/多平台并发触发多次启动）
        self._start_lock = threading.Lock()
        self._started = False
        # 跨平台主动消息分发器 (message, target_id, chat_type, platform, trigger_type, store_memory) -> bool
        self.cross_platform_sender: Optional[Callable] = None

    async def start(self):
        """启动调度器（自动恢复持久化任务）"""
        if self._running:
            logger.warning("调度器已经在运行")
            return

        self._running = True
        self._started = True

        if self.task_store:
            await self._restore_pending_tasks()

        self._task = asyncio.create_task(self._run_loop())
        logger.info("任务调度器已启动")

    def start_background(self):
        """在后台线程中启动调度器（幂等，多平台并发调用只会启动一次）"""
        with self._start_lock:
            if self._running or self._started:
                logger.warning("调度器已经在运行")
                return
            # 先占位，防止其它线程在 spawn 后、线程真正运行前重复启动
            self._started = True

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
                loop.run_forever()
            except Exception as e:
                logger.error(f"调度器线程错误: {e}")
            finally:
                loop.close()

        self._thread = threading.Thread(target=run_in_thread, daemon=True)
        self._thread.start()
        logger.info("任务调度器已在后台线程中启动")

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            try:
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task
            except RuntimeError:
                # 调度循环运行在后台线程的事件循环里，跨循环无法 await，仅取消即可
                pass
        logger.info("任务调度器已停止")

    async def _run_loop(self):
        """调度循环（含条件任务检查）"""
        while self._running:
            try:
                now = datetime.now()

                # ── 时间触发任务 ──
                if self.task_queue:
                    next_task = self.task_queue[0]
                    if next_task.execute_at <= now:
                        heapq.heappop(self.task_queue)
                        self._queued_task_ids.discard(next_task.task_id)
                        if next_task.task_id in self.running_tasks or next_task.task_id in self.completed_tasks:
                            logger.warning(f"跳过重复任务(已在执行/已完成): {next_task.task_id}")
                        else:
                            logger.info(f"执行定时任务: {next_task.task_id}, 类型: {next_task.task_type}")
                            await self._execute_task(next_task)

                # ── 条件触发任务（每 5 秒检查一次） ──
                if (now - self._last_condition_check).total_seconds() >= 5:
                    self._last_condition_check = now
                    await self._check_conditional_tasks()

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环错误: {e}", exc_info=True)

    def notify_user_online(self, user_id: str):
        """通知调度器：某用户上线了"""
        self._online_users.add(str(user_id))
        logger.debug(f"[Scheduler] 用户上线: {user_id}")

    def notify_user_offline(self, user_id: str):
        """通知调度器：某用户下线了"""
        self._online_users.discard(str(user_id))
        logger.debug(f"[Scheduler] 用户离线: {user_id}")

    async def _check_conditional_tasks(self):
        """检查条件触发任务"""
        if not self.task_store or not self._online_users:
            return
        try:
            for uid in list(self._online_users):
                tasks = self.task_store.find_by_condition("online", str(uid))
                for td in tasks:
                    task_id = td["task_id"]
                    if task_id in self.running_tasks or task_id in self.completed_tasks:
                        continue
                    if task_id in self._queued_task_ids:
                        continue

                    execute_at = datetime.fromisoformat(td["execute_at"])
                    from hub.scheduler import Task

                    task = Task(
                        task_id=task_id,
                        task_type=f"scheduled_{td['task_type']}",
                        priority=td.get("priority", 5),
                        data={
                            **td,
                            "task_type": td["task_type"],
                            "target_type": td.get("target_type"),
                            "target_id": td.get("target_id"),
                            "message": td.get("message", ""),
                            "repeat": td.get("repeat_type", "once"),
                            "repeat_config": td.get("repeat_config"),
                            "max_executions": td.get("max_executions"),
                            "execution_count": td.get("execution_count", 0),
                            "priority": td.get("priority", 5),
                            "platform": td.get("platform"),
                            "action_type": td.get("action_type"),
                            "action_times": td.get("action_times", 1),
                            "created_by": td.get("created_by", ""),
                            "scheduled_at": td.get("execute_at"),
                            "condition_type": td.get("condition_type", "time"),
                            "condition_data": td.get("condition_data"),
                            "follow_up_task": td.get("follow_up_task"),
                        },
                        execute_at=execute_at,
                    )
                    heapq.heappush(self.task_queue, task)
                    self._queued_task_ids.add(task_id)
                    self._online_users.discard(uid)
                    logger.info(f"[Condition] 条件触发任务已入队: {task_id} (用户 {uid} 上线)")
        except Exception as e:
            logger.error(f"[Condition] 条件检查失败: {e}", exc_info=True)

    async def _safe_onebot_call(self, coro_func, target_id, message, task):
        """跨事件循环安全地调用 onebot_client 方法"""
        send_success = False
        if self.onebot_client:
            try:
                if self.main_event_loop and self.main_event_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        coro_func(target_id, message),
                        self.main_event_loop,
                    )
                    send_success = await asyncio.wrap_future(future)
                else:
                    send_success = await coro_func(target_id, message)
            except Exception as e:
                logger.error(f"跨事件循环发送消息失败: {e}", exc_info=True)
        return send_success

    async def _send_scheduled_message(self, task: Task, data: Dict, message: str) -> bool:
        """按任务记录的 platform 发送定时消息（跨平台兼容）

        发送优先级:
        1. 跨平台分发器 (DecisionHub._dispatch_proactive_message) — 支持所有平台
        2. OneBot 直连回退（终端模式 / 分发器未注入）
        3. 终端回调打印
        """
        target_type = data.get("target_type", "private")
        target_id = data.get("target_id")
        platform = data.get("platform") or "aiocqhttp"

        # 1) 跨平台分发 — 由 DecisionHub 统一路由（含跨平台 ID 解析与在线检测）
        if self.cross_platform_sender is not None:
            try:
                sent = await self.cross_platform_sender(
                    message=message,
                    target_id=target_id,
                    chat_type=target_type,
                    platform=platform,
                    trigger_type="scheduled",
                    store_memory=False,
                )
                if sent:
                    logger.info(f"定时消息已分发: platform={platform}, 目标={target_type}_{target_id}")
                else:
                    logger.warning(f"定时消息分发失败: platform={platform}, 目标={target_type}_{target_id}")
                return bool(sent)
            except Exception as e:
                logger.error(f"跨平台分发定时消息失败: {e}", exc_info=True)

        # 2) OneBot 直连回退
        if self.onebot_client:
            if target_type == "group":
                sent = await self._safe_onebot_call(
                    self.onebot_client.send_group_message, target_id, message, task
                )
            else:
                sent = await self._safe_onebot_call(
                    self.onebot_client.send_private_message, target_id, message, task
                )
            return bool(sent)

        # 3) 终端模式：无任何平台通道，打印提醒
        logger.info(f"【定时提醒】{message}")
        if self.terminal_callback:
            try:
                await self.terminal_callback(message)
            except Exception as e:
                logger.error(f"终端回调失败: {e}")
        return False

    async def _execute_task(self, task: Task):
        """执行任务（含重复任务自动重新入队）"""
        task.status = "running"
        self.running_tasks[task.task_id] = task

        try:
            tool_context = {
                "onebot_client": self.onebot_client,
                "send_like_callback": getattr(self.onebot_client, "send_like", None) if self.onebot_client else None,
                "user_id": task.data.get("target_id"),
                "group_id": task.data.get("target_id") if task.data.get("target_type") == "group" else None,
                "message_type": task.data.get("target_type", "private"),
                "sender_name": "scheduled_task",
            }

            # 根据任务类型执行不同的操作
            if task.task_type == "scheduled_reminder":
                # 定时提醒任务 - 发送消息提醒（按任务 platform 跨平台分发）
                data = task.data
                target_type = data.get("target_type", "private")
                target_id = data.get("target_id")
                message = data.get("message", "")

                logger.info(f"执行提醒任务: 目标={target_type}_{target_id}, 消息={message}")

                send_success = await self._send_scheduled_message(task, data, message)
                if send_success:
                    logger.info(f"提醒消息已发送: {target_type}_{target_id}")
                    await self._store_scheduled_response(task, message)

            elif task.task_type == "scheduled_message":
                # 定时发送消息任务（按任务 platform 跨平台分发）
                data = task.data
                target_type = data.get("target_type", "private")
                target_id = data.get("target_id")
                message = data.get("message", "")

                logger.info(f"发送定时消息: 目标={target_type}_{target_id}, 消息={message}")

                send_success = await self._send_scheduled_message(task, data, message)
                if send_success:
                    logger.info(f"定时消息已发送: {target_type}_{target_id}")
                    await self._store_scheduled_response(task, message)

            elif task.task_type == "scheduled_action":
                # 定时执行动作（如点赞等）
                data = task.data
                action_type = data.get("action_type", "")
                target_id = data.get("target_id")
                message = data.get("message", "")

                logger.info(f"执行定时动作: 类型={action_type}, 目标={target_id}")

                # 根据动作类型调用相应工具
                if self.tool_registry and action_type:
                    from core.tool_adapter import ToolAdapter

                    adapter = ToolAdapter()
                    adapter.set_tool_registry(self.tool_registry)

                    if action_type == "qq_like":
                        args = {
                            "target_user_id": target_id,
                            "times": data.get("times", 1),
                        }
                        result = await adapter.execute_tool("qq_like", args, tool_context)
                        logger.info(f"点赞动作已执行: {result}")

                    elif action_type == "send_poke":
                        args = {
                            "target_user_id": target_id,
                            "group_id": target_id if task.data.get("target_type") == "group" else None,
                        }
                        result = await adapter.execute_tool("send_poke", args, tool_context)
                        logger.info(f"拍一拍动作已执行: {result}")

            # 标记任务完成
            self.complete_task(task.task_id, {"result": "success"})

            # 重复任务：计算下次执行时间并重新入队
            await self._reschedule_if_repeat(task)

            # 任务链：完成后自动创建 follow_up 任务
            await self._trigger_follow_up(task)

        except Exception as e:
            logger.error(f"任务执行失败 {task.task_id}: {e}", exc_info=True)
            self.fail_task(task.task_id, str(e))

    async def _reschedule_if_repeat(self, task: Task):
        """如果任务是重复类型，计算下次时间并重新入队"""
        task_data = task.data
        repeat_type = task_data.get("repeat_type") or task_data.get("repeat", "once")

        if repeat_type == "once":
            return

        next_time = TaskStore.calc_next_execute_time(
            current_execute_at=task.execute_at,
            repeat_type=repeat_type,
            repeat_config=task_data.get("repeat_config"),
        )

        if next_time is None:
            logger.info(f"[Repeat] 重复任务 {task.task_id} 已到期，不再重复")
            if self.task_store:
                self.task_store.update_status(task.task_id, "completed")
            return

        if "max_executions" in task_data and task_data.get("execution_count", 0) >= task_data["max_executions"]:
            logger.info(f"[Repeat] 重复任务 {task.task_id} 已达最大执行次数")
            if self.task_store:
                self.task_store.update_status(task.task_id, "completed")
            return

        task.execute_at = next_time
        task.scheduled_at = datetime.now()
        task.status = "pending"
        task.data["execution_count"] = task.data.get("execution_count", 0) + 1
        # 清除完成/运行标记，避免调度循环把重新入队的重复任务跳过
        self.completed_tasks.pop(task.task_id, None)
        self.running_tasks.pop(task.task_id, None)
        heapq.heappush(self.task_queue, task)
        self._queued_task_ids.add(task.task_id)
        logger.info(
            f"[Repeat] 重复任务 {task.task_id} 已重新入队, "
            f"下次: {next_time.isoformat()}, "
            f"类型: {repeat_type}, "
            f"已执行: {task.data['execution_count']} 次"
        )

        if self.task_store:
            self.task_store.save_task(
                {
                    **task.data,
                    "task_id": task.task_id,
                    "status": task.status,
                    "execute_at": next_time.isoformat(),
                    "execution_count": task.data["execution_count"],
                }
            )

    async def _trigger_follow_up(self, task: Task):
        """任务链：完成后自动创建 follow_up 任务"""
        follow_up = task.data.get("follow_up_task")
        if not follow_up:
            return
        if isinstance(follow_up, str):
            try:
                follow_up = json.loads(follow_up)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[Chain] follow_up 解析失败: {follow_up}")
                return
        if not isinstance(follow_up, dict):
            return

        try:
            import uuid

            from webnet.ToolNet.tools.scheduler.time_parser import (
                parse_smart_time,
            )

            follow_id = str(uuid.uuid4())
            ftask_type = follow_up.get("task_type", "reminder")
            ftarget_id = str(task.data.get("target_id", ""))
            ftarget_type = task.data.get("target_type", "private")
            fmessage = follow_up.get("message", "")
            frepeat = follow_up.get("repeat", "once")

            schedule_time = follow_up.get("schedule_time", "")
            scheduled_at = parse_smart_time(schedule_time) if schedule_time else datetime.now() + timedelta(minutes=30)

            if not scheduled_at:
                scheduled_at = datetime.now() + timedelta(minutes=30)

            ftask_data = {
                "task_id": follow_id,
                "task_type": ftask_type,
                "target_type": ftarget_type,
                "target_id": ftarget_id,
                "message": fmessage,
                "scheduled_at": scheduled_at.isoformat(),
                "repeat": frepeat,
                "priority": follow_up.get("priority", 5),
                "platform": task.data.get("platform"),
                "created_by": task.data.get("created_by", ""),
                "execution_count": 0,
            }

            parent_id = task.task_id

            ftask = Task(
                task_id=follow_id,
                task_type=f"scheduled_{ftask_type}",
                priority=follow_up.get("priority", 5),
                data=ftask_data,
                execute_at=scheduled_at,
            )
            self.schedule(ftask)
            logger.info(f"[Chain] 任务链触发: {parent_id} -> {follow_id} ({fmessage[:30]})")
        except Exception as e:
            logger.error(f"[Chain] follow_up 创建失败: {e}", exc_info=True)

    def _sync_queued_ids(self):
        """按当前 task_queue 重建队列 ID 集合。

        供直接重建 task_queue 的调用方（删除/更新任务工具、Web API）使用，
        避免 _queued_task_ids 与实际队列不一致导致误跳过重新入队。
        """
        self._queued_task_ids = {getattr(t, "task_id", "") for t in self.task_queue}

    def schedule(self, task: Task) -> None:
        """添加任务到调度队列（自动持久化，防重复入队）"""
        if task.task_id in self._queued_task_ids:
            logger.warning(f"任务已在队列中，跳过重复入队: {task.task_id}")
            return

        heapq.heappush(self.task_queue, task)
        self._queued_task_ids.add(task.task_id)
        task.scheduled_at = datetime.now()
        logger.info(f"任务已添加到调度队列: {task.task_id}, 执行时间: {task.execute_at}")

        if self.task_store:
            self.task_store.save_task(
                {
                    **task.data,
                    "task_id": task.task_id,
                    "status": task.status,
                    "execute_at": task.execute_at.isoformat(),
                    "created_at": task.created_at.isoformat(),
                }
            )

    async def _restore_pending_tasks(self):
        """从 TaskStore 恢复未完成的任务"""
        if not self.task_store:
            return
        try:
            pending = self.task_store.load_pending_tasks()
            restored = 0
            for td in pending:
                try:
                    if td["task_id"] in self._queued_task_ids:
                        # 创建时已通过 schedule() 入队的任务，恢复阶段跳过，避免重复执行
                        logger.info(f"[Restore] 任务已在队列中，跳过: {td['task_id']}")
                        continue
                    execute_at = datetime.fromisoformat(td["execute_at"])
                    task = Task(
                        task_id=td["task_id"],
                        task_type=f"scheduled_{td['task_type']}",
                        priority=td.get("priority", 5),
                        data={
                            "task_id": td["task_id"],
                            "task_type": td["task_type"],
                            "target_type": td.get("target_type"),
                            "target_id": td.get("target_id"),
                            "message": td.get("message", ""),
                            "repeat": td.get("repeat_type", "once"),
                            "repeat_config": td.get("repeat_config"),
                            "priority": td.get("priority", 5),
                            "platform": td.get("platform"),
                            "action_type": td.get("action_type"),
                            "action_times": td.get("action_times", 1),
                            "created_by": td.get("created_by", ""),
                            "execution_count": td.get("execution_count", 0),
                            "max_executions": td.get("max_executions"),
                            "scheduled_at": td.get("execute_at"),
                        },
                        execute_at=execute_at,
                    )
                    heapq.heappush(self.task_queue, task)
                    self._queued_task_ids.add(td["task_id"])
                    restored += 1
                except Exception as e:
                    logger.error(f"[Restore] 恢复任务 {td.get('task_id')} 失败: {e}")

            if restored > 0:
                logger.info(f"[Restore] 从数据库恢复了 {restored} 个待执行任务")
        except Exception as e:
            logger.error(f"[Restore] 恢复任务失败: {e}", exc_info=True)

    async def _store_scheduled_response(self, task: Task, message: str) -> None:
        """将定时任务产出存入记忆系统（对话历史 + 统一记忆）"""
        if not self.memory_manager:
            logger.warning("[Scheduler] memory_manager 未注入，定时任务产出无法存入记忆")
            return

        try:
            data = task.data
            target_id = str(data.get("target_id", ""))
            target_type = data.get("target_type", "private")
            group_id = target_id if target_type == "group" else ""
            platform = data.get("platform", "")
            if not platform:
                platform = "aiocqhttp"
            created_by = data.get("created_by", "")
            # Strip "user_" prefix if present
            raw_owner = created_by if created_by else target_id
            owner_id = raw_owner.replace("user_", "") if str(raw_owner).startswith("user_") else str(raw_owner)
            session_id = f"user_{owner_id}"

            perception = {
                "content": message,
                "user_id": owner_id,
                "group_id": group_id,
                "platform": platform,
                "sender_name": "弥娅",
                "message_type": target_type,
                "response": message,
                "_meta": {"scheduled": True},
            }

            await self.memory_manager.store_unified_memory(perception, role="assistant")

            # 验证：立即回读对话历史确认写入成功
            verify_count = 0
            try:
                if self.memory_manager.memory_net and self.memory_manager.memory_net.conversation_history:
                    history = await self.memory_manager.memory_net.conversation_history.get_history(session_id, limit=3)
                    verify_count = len(history) if history else 0
            except Exception:
                pass

            logger.info(
                f"[Scheduler] 定时任务产出已存入记忆: {message[:30]}... "
                f"(user={owner_id}, platform={platform}, session={session_id}, 会话消息数={verify_count})"
            )
        except Exception as e:
            logger.error(f"[Scheduler] 存储定时任务产出到记忆失败: {e}", exc_info=True)

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务"""
        if not self.task_queue:
            return None

        task = heapq.heappop(self.task_queue)
        self._queued_task_ids.discard(task.task_id)
        task.status = "running"
        self.running_tasks[task.task_id] = task
        return task

    def complete_task(self, task_id: str, result: Dict = None) -> None:
        """完成任务"""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = result
            self.completed_tasks[task_id] = task
            self.task_history.append(task)
            self._queued_task_ids.discard(task_id)

            # 只保留最近100条历史
            if len(self.task_history) > 100:
                self.task_history = self.task_history[-100:]

            if self.task_store:
                self.task_store.update_status(task_id, "completed")

    def fail_task(self, task_id: str, error: str) -> None:
        """任务失败"""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.status = "failed"
            task.error = error
            task.completed_at = datetime.now()
            self.task_history.append(task)
            self._queued_task_ids.discard(task_id)

            if self.task_store:
                self.task_store.update_status(task_id, "failed", error=error)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        # 检查运行中的任务
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                "status": task.status,
                "type": task.task_type,
                "created_at": task.created_at.isoformat(),
                "running_time": (datetime.now() - task.created_at).total_seconds(),
            }

        # 检查已完成的任务
        if task_id in self.completed_tasks:
            task = self.completed_tasks[task_id]
            return {
                "status": task.status,
                "type": task.task_type,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat(),
            }

        return None

    def get_queue_info(self) -> Dict:
        """获取队列信息"""
        return {
            "pending": len(self.task_queue),
            "running": len(self.running_tasks),
            "completed": len(self.completed_tasks),
            "total": len(self.task_history),
        }

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """清理旧任务"""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)

        to_remove = [tid for tid, task in self.completed_tasks.items() if task.completed_at < cutoff]

        for tid in to_remove:
            del self.completed_tasks[tid]

        return len(to_remove)


# ==================== 全局单例 ====================

_global_scheduler: Optional["Scheduler"] = None


def get_global_scheduler() -> "Scheduler":
    """获取全局调度器实例"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = Scheduler()
    return _global_scheduler


def set_global_scheduler(scheduler: "Scheduler"):
    """设置全局调度器实例"""
    global _global_scheduler
    _global_scheduler = scheduler
