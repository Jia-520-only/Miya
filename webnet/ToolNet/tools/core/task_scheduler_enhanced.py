"""
增强版任务调度器

提供更可靠的任务执行、失败重试、持久化存储等功能
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EnhancedTaskScheduler:
    """增强版任务调度器"""

    def __init__(self, db_path: str = "./data/tasks.db"):
        self.db_path = db_path
        self.running_tasks = {}
        self.task_callbacks = {}
        self.is_running = False

        # 初始化数据库
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    task_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 3,
                    scheduled_at TIMESTAMP,
                    execute_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建任务历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks (scheduled_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_execute ON tasks (execute_at)")

            conn.commit()
            conn.close()

            logger.info(f"任务数据库初始化完成: {self.db_path}")

        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")

    async def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已经在运行")
            return

        self.is_running = True
        logger.info("任务调度器启动")

        # 启动任务检查循环
        asyncio.create_task(self._task_check_loop())

        # 恢复待执行任务
        await self._recover_pending_tasks()

    async def stop(self):
        """停止调度器"""
        self.is_running = False

        # 等待运行中的任务完成
        running_tasks = list(self.running_tasks.values())
        if running_tasks:
            logger.info(f"等待 {len(running_tasks)} 个运行中的任务完成...")
            await asyncio.gather(*running_tasks, return_exceptions=True)

        logger.info("任务调度器已停止")

    async def create_task(self, task_data: Dict[str, Any]) -> str:
        """创建新任务"""
        try:
            task_id = str(uuid.uuid4())

            # 验证任务数据
            if not self._validate_task_data(task_data):
                raise ValueError("无效的任务数据")

            # 解析执行时间
            execute_at = self._parse_execute_time(task_data)

            # 构建完整任务
            task = {
                "task_id": task_id,
                "task_type": task_data.get("type", "unknown"),
                "task_data": json.dumps(task_data, ensure_ascii=False),
                "status": "pending",
                "priority": task_data.get("priority", 3),
                "scheduled_at": datetime.now().isoformat(),
                "execute_at": execute_at.isoformat() if execute_at else None,
                "retry_count": 0,
                "max_retries": task_data.get("max_retries", 3),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # 保存到数据库
            self._save_task_to_db(task)

            # 记录历史
            self._record_task_history(task_id, "create", "success", "任务创建成功")

            logger.info(f"任务创建成功: {task_id} ({task['task_type']})")
            return task_id

        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            raise

    async def execute_task(self, task_id: str) -> bool:
        """执行任务"""
        try:
            # 获取任务
            task = self._get_task_from_db(task_id)
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False

            # 检查任务状态
            if task["status"] not in ["pending", "retrying"]:
                logger.warning(f"任务状态不正确: {task_id} ({task['status']})")
                return False

            # 标记为执行中
            self._update_task_status(task_id, "running")
            self._record_task_history(task_id, "execute", "started", "开始执行任务")

            # 执行任务
            task_data = json.loads(task["task_data"])
            success = await self._execute_task_internal(task_id, task_data)

            # 更新任务状态
            if success:
                self._update_task_status(task_id, "completed")
                self._record_task_history(task_id, "execute", "success", "任务执行成功")
                logger.info(f"任务执行成功: {task_id}")
            else:
                # 检查是否需要重试
                retry_count = task["retry_count"] + 1
                max_retries = task["max_retries"]

                if retry_count < max_retries:
                    # 安排重试
                    retry_delay = self._calculate_retry_delay(retry_count)
                    next_execute = datetime.now() + timedelta(seconds=retry_delay)

                    self._update_task_status(task_id, "retrying", retry_count=retry_count, execute_at=next_execute)

                    retry_msg = f"任务执行失败，{retry_delay}秒后重试 ({retry_count}/{max_retries})"
                    self._record_task_history(task_id, "retry", "scheduled", retry_msg)
                    logger.warning(f"任务执行失败，安排重试: {task_id} ({retry_count}/{max_retries})")
                else:
                    # 重试次数用尽
                    self._update_task_status(task_id, "failed")
                    self._record_task_history(task_id, "execute", "failed", "任务执行失败，重试次数用尽")
                    logger.error(f"任务执行失败，重试次数用尽: {task_id}")

            return success

        except Exception as e:
            logger.error(f"执行任务异常: {task_id}, 错误: {e}")
            self._record_task_history(task_id, "execute", "error", f"执行异常: {str(e)}")

            # 标记为失败
            self._update_task_status(task_id, "failed", error_message=str(e))
            return False

    async def _execute_task_internal(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """实际执行任务"""
        task_type = task_data.get("type", "unknown")

        try:
            if task_type == "qq_message":
                return await self._execute_qq_message_task(task_data)
            elif task_type == "qq_action":
                return await self._execute_qq_action_task(task_data)
            elif task_type == "system_command":
                return await self._execute_system_command_task(task_data)
            elif task_type == "custom_callback" and "callback" in task_data:
                # 自定义回调
                callback = task_data["callback"]
                if callable(callback):
                    result = await callback(task_data)
                    return bool(result)
                else:
                    logger.error(f"自定义回调不可调用: {task_id}")
                    return False
            else:
                logger.error(f"未知任务类型: {task_type}")
                return False

        except Exception as e:
            logger.error(f"任务执行内部错误: {task_id}, 错误: {e}")
            return False

    async def _execute_qq_message_task(self, task_data: Dict[str, Any]) -> bool:
        """执行QQ消息任务"""
        # 这里需要集成QQ客户端
        # 由于QQ客户端的实际实现未知，这里返回模拟成功

        target_type = task_data.get("target_type", "group")
        target_id = task_data.get("target_id", 0)
        message = task_data.get("message", "")

        logger.info(f"[模拟] 发送QQ消息: {target_type} {target_id} - {message[:50]}...")

        # 模拟延迟
        await asyncio.sleep(0.5)

        return True

    async def _execute_qq_action_task(self, task_data: Dict[str, Any]) -> bool:
        """执行QQ动作任务（点赞、拍一拍等）"""
        logger.info("[模拟] 执行QQ动作任务")
        await asyncio.sleep(0.5)
        return True

    async def _execute_system_command_task(self, task_data: Dict[str, Any]) -> bool:
        """执行系统命令任务"""
        logger.info("[模拟] 执行系统命令任务")
        await asyncio.sleep(0.5)
        return True

    async def _task_check_loop(self):
        """任务检查循环"""
        logger.info("任务检查循环启动")

        while self.is_running:
            try:
                # 检查待执行任务
                pending_tasks = self._get_pending_tasks()

                for task in pending_tasks:
                    task_id = task["task_id"]
                    execute_at = datetime.fromisoformat(task["execute_at"]) if task["execute_at"] else None

                    # 检查是否到达执行时间
                    if execute_at and execute_at <= datetime.now():
                        # 检查是否已经在运行
                        if task_id not in self.running_tasks:
                            # 执行任务
                            self.running_tasks[task_id] = asyncio.create_task(self.execute_task(task_id))

                            # 设置完成回调
                            self.running_tasks[task_id].add_done_callback(
                                lambda f, tid=task_id: self._task_done_callback(f, tid)
                            )

                # 清理已完成的任务
                self._cleanup_completed_tasks()

            except Exception as e:
                logger.error(f"任务检查循环异常: {e}")

            # 等待一段时间再检查
            await asyncio.sleep(5)  # 5秒检查一次

    def _task_done_callback(self, future: asyncio.Future, task_id: str):
        """任务完成回调"""
        try:
            # 从运行中任务移除
            self.running_tasks.pop(task_id, None)

            # 检查执行结果
            if future.exception():
                logger.error(f"任务执行异常: {task_id}, 异常: {future.exception()}")
            else:
                result = future.result()
                if not result:
                    logger.warning(f"任务执行失败: {task_id}")

        except Exception as e:
            logger.error(f"任务完成回调异常: {e}")

    async def _recover_pending_tasks(self):
        """恢复待执行任务"""
        try:
            pending_tasks = self._get_tasks_by_status(["pending", "retrying"])

            logger.info(f"恢复 {len(pending_tasks)} 个待执行任务")

            for task in pending_tasks:
                task_id = task["task_id"]
                self._record_task_history(task_id, "recover", "success", "任务恢复")

        except Exception as e:
            logger.error(f"恢复任务失败: {e}")

    def _validate_task_data(self, task_data: Dict[str, Any]) -> bool:
        """验证任务数据"""
        if not task_data:
            return False

        # 检查必填字段
        task_type = task_data.get("type")
        if not task_type:
            return False

        # 根据任务类型验证字段
        return not (task_type == "qq_message" and not task_data.get("message"))

    def _parse_execute_time(self, task_data: Dict[str, Any]) -> Optional[datetime]:
        """解析执行时间"""
        try:
            execute_time = task_data.get("execute_at")
            if not execute_time:
                # 默认立即执行
                return datetime.now()

            # 尝试解析各种时间格式
            if isinstance(execute_time, str):
                # ISO格式
                if "T" in execute_time:
                    return datetime.fromisoformat(execute_time.replace("Z", "+00:00"))
                # 简单日期时间格式
                elif " " in execute_time:
                    try:
                        return datetime.strptime(execute_time, "%Y-%m-%d %H:%M:%S")
                    except:
                        try:
                            return datetime.strptime(execute_time, "%Y-%m-%d %H:%M")
                        except:
                            pass
                # 相对时间（如"+1h", "+30m"）
                elif execute_time.startswith("+"):
                    import re

                    match = re.match(r"\+(\d+)([mhdw])", execute_time.lower())
                    if match:
                        amount = int(match.group(1))
                        unit = match.group(2)

                        if unit == "m":  # 分钟
                            return datetime.now() + timedelta(minutes=amount)
                        elif unit == "h":  # 小时
                            return datetime.now() + timedelta(hours=amount)
                        elif unit == "d":  # 天
                            return datetime.now() + timedelta(days=amount)
                        elif unit == "w":  # 周
                            return datetime.now() + timedelta(weeks=amount)

            # 时间戳
            try:
                timestamp = float(execute_time)
                return datetime.fromtimestamp(timestamp)
            except:
                pass

            return datetime.now()

        except Exception as e:
            logger.error(f"解析执行时间失败: {e}")
            return datetime.now()

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """计算重试延迟（指数退避）"""
        base_delay = 60  # 60秒基础延迟
        max_delay = 3600  # 最大1小时

        delay = min(base_delay * (2**retry_count), max_delay)
        return delay

    # 数据库操作

    def _save_task_to_db(self, task: Dict[str, Any]):
        """保存任务到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO tasks (
                    task_id, task_type, task_data, status, priority,
                    scheduled_at, execute_at, retry_count, max_retries,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task["task_id"],
                    task["task_type"],
                    task["task_data"],
                    task["status"],
                    task["priority"],
                    task["scheduled_at"],
                    task["execute_at"],
                    task["retry_count"],
                    task.get("max_retries", 3),
                    task["created_at"],
                    task["updated_at"],
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"保存任务到数据库失败: {e}")

    def _get_task_from_db(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()

            conn.close()

            if row:
                return dict(row)
            else:
                return None

        except Exception as e:
            logger.error(f"从数据库获取任务失败: {e}")
            return None

    def _update_task_status(self, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = ["status = ?", "updated_at = ?"]
            update_values = [status, datetime.now().isoformat()]

            if "retry_count" in kwargs:
                update_fields.append("retry_count = ?")
                update_values.append(kwargs["retry_count"])

            if "execute_at" in kwargs:
                execute_at = kwargs["execute_at"]
                if isinstance(execute_at, datetime):
                    execute_at = execute_at.isoformat()
                update_fields.append("execute_at = ?")
                update_values.append(execute_at)

            if "error_message" in kwargs:
                update_fields.append("error_message = ?")
                update_values.append(kwargs["error_message"])

            if status == "completed":
                update_fields.append("completed_at = ?")
                update_values.append(datetime.now().isoformat())

            update_values.append(task_id)  # WHERE条件

            query = f"""
                UPDATE tasks
                SET {", ".join(update_fields)}
                WHERE task_id = ?
            """

            cursor.execute(query, update_values)
            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")

    def _get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待执行任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'retrying')
                AND (execute_at IS NULL OR execute_at <= ?)
                ORDER BY priority DESC, execute_at ASC
            """,
                (datetime.now().isoformat(),),
            )

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"获取待执行任务失败: {e}")
            return []

    def _get_tasks_by_status(self, status_list: List[str]) -> List[Dict[str, Any]]:
        """根据状态获取任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            placeholders = ",".join(["?"] * len(status_list))
            query = f"""
                SELECT * FROM tasks
                WHERE status IN ({placeholders})
                ORDER BY created_at DESC
            """

            cursor.execute(query, status_list)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"根据状态获取任务失败: {e}")
            return []

    def _record_task_history(self, task_id: str, action: str, status: str, message: str = ""):
        """记录任务历史"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO task_history (task_id, action, status, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                (task_id, action, status, message, datetime.now().isoformat()),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"记录任务历史失败: {e}")

    def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 删除30天前已完成的任务
            cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()

            cursor.execute(
                """
                DELETE FROM tasks
                WHERE status = 'completed'
                AND completed_at < ?
            """,
                (cutoff_date,),
            )

            # 删除对应的历史记录
            cursor.execute(
                """
                DELETE FROM task_history
                WHERE task_id IN (
                    SELECT task_id FROM tasks WHERE status = 'completed' AND completed_at < ?
                )
            """,
                (cutoff_date,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 个已完成的任务")

        except Exception as e:
            logger.error(f"清理已完成任务失败: {e}")

    # 公共API

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self._get_task_from_db(task_id)

    def list_tasks(self, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """列出任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"列出任务失败: {e}")
            return []

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            task = self._get_task_from_db(task_id)
            if not task:
                return False

            # 检查是否可以取消
            if task["status"] not in ["pending", "retrying"]:
                return False

            # 更新状态
            self._update_task_status(task_id, "cancelled")
            self._record_task_history(task_id, "cancel", "success", "任务已取消")

            logger.info(f"任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False

    def get_task_history(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取任务历史"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM task_history
                WHERE task_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (task_id, limit),
            )

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"获取任务历史失败: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 任务状态统计
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """)
            status_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # 今日任务统计
            today = datetime.now().date().isoformat()
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM tasks
                WHERE DATE(created_at) = ?
            """,
                (today,),
            )
            today_count = cursor.fetchone()[0]

            # 成功率统计
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM tasks
            """)
            total, success, failed = cursor.fetchone()
            success_rate = success / total * 100 if total > 0 else 0

            conn.close()

            return {
                "status_stats": status_stats,
                "today_count": today_count,
                "total_tasks": total,
                "success_count": success,
                "failed_count": failed,
                "success_rate": round(success_rate, 2),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


# 单例实例
_global_scheduler = None


def get_global_scheduler() -> EnhancedTaskScheduler:
    """获取全局调度器实例"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = EnhancedTaskScheduler()
    return _global_scheduler
