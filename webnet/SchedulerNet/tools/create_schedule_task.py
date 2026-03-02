"""
创建定时任务
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
import re
import uuid
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class CreateScheduleTask(BaseTool):
    """CreateScheduleTask"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_schedule_task",
            "description": "创建定时任务或提醒。当用户说'X分钟后提醒我'、'定时发送消息'、'X点叫我'、'一分钟后给我点个赞'等时间相关的请求时，必须调用此工具。支持定时发送消息、设置提醒、定时检查、定时执行动作等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": "任务类型：message(发送消息), reminder(提醒用户), action(执行动作如点赞、拍一拍), check(检查系统)。用户说'提醒'时用reminder，说'发送消息'时用message，说'给我点赞'、'拍一拍'等动作时用action",
                        "enum": ["message", "reminder", "action", "check"]
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标类型：group(群), private(私聊)。默认为用户当前会话类型",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标ID（群号或用户QQ号），默认为当前用户ID"
                    },
                    "message": {
                        "type": "string",
                        "description": "要发送的消息内容或提醒内容"
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "执行时间，格式：HH:MM 或 YYYY-MM-DD HH:MM。也可以是相对时间如'1分钟后'、'5分钟后'，系统会自动计算"
                    },
                    "repeat": {
                        "type": "string",
                        "description": "重复频率：once(一次性), daily(每天), weekly(每周)。默认为一次性",
                        "enum": ["once", "daily", "weekly"],
                        "default": "once"
                    },
                    "priority": {
                        "type": "integer",
                        "description": "优先级 (1-10)，越高越优先",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    },
                    "action_type": {
                        "type": "string",
                        "description": "当task_type为action时，指定要执行的动作类型：qq_like(点赞), send_poke(拍一拍)",
                        "enum": ["qq_like", "send_poke"]
                    },
                    "times": {
                        "type": "integer",
                        "description": "动作执行的次数（仅对qq_like有效，1-10）",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 1
                    }
                },
                "required": ["task_type"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        task_type = args.get("task_type")
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id")
        message = args.get("message", "")
        schedule_time = args.get("schedule_time", "")
        repeat = args.get("repeat", "once")
        priority = args.get("priority", 5)
        action_type = args.get("action_type", "")
        times = args.get("times", 1)

        if not task_type:
            return "❌ 任务类型不能为空"

        if not target_id:
            return "❌ 目标ID不能为空"

        if task_type == "message" and not message:
            return "❌ 消息任务需要提供消息内容"

        if task_type == "action" and not action_type:
            return "❌ 动作任务需要指定action_type（qq_like或send_poke）"

        try:
            # 生成任务ID
            task_id = str(uuid.uuid4())[:8]

            # 解析时间
            scheduled_at = None
            if schedule_time:
                try:
                    # 检测相对时间（如"1分钟后"、"5分钟后"）
                    if "分钟后" in schedule_time or "minute" in schedule_time.lower():
                        match = re.search(r'(\d+)\s*分钟', schedule_time)
                        if match:
                            minutes = int(match.group(1))
                            scheduled_at = datetime.now() + timedelta(minutes=minutes)
                            logger.info(f"检测到相对时间: {minutes}分钟后，执行时间: {scheduled_at}")
                    elif "小时后" in schedule_time or "hour" in schedule_time.lower():
                        match = re.search(r'(\d+)\s*小时', schedule_time)
                        if match:
                            hours = int(match.group(1))
                            scheduled_at = datetime.now() + timedelta(hours=hours)
                            logger.info(f"检测到相对时间: {hours}小时后，执行时间: {scheduled_at}")
                    # 绝对时间
                    elif ":" in schedule_time:
                        if len(schedule_time) == 5:
                            # 只有时间，使用今天的日期
                            today = datetime.now().date()
                            scheduled_at = datetime.strptime(f"{today} {schedule_time}", "%Y-%m-%d %H:%M")
                        else:
                            # 完整日期时间
                            scheduled_at = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
                except ValueError as e:
                    return f"❌ 时间格式错误: {e}。请使用 HH:MM、YYYY-MM-DD HH:MM 或相对时间（如'1分钟后'）"

            # 如果没有指定时间，默认立即执行（5分钟后）
            if not scheduled_at:
                scheduled_at = datetime.now() + timedelta(minutes=5)

            # 构建任务数据
            task_data = {
                "task_id": task_id,
                "task_type": task_type,
                "target_type": target_type,
                "target_id": target_id,
                "message": message,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "repeat": repeat,
                "priority": priority,
                "created_by": f"user_{context.user_id}" if context.user_id else 'unknown'
            }

            # 如果是action类型，添加action相关参数
            if task_type == "action":
                task_data["action_type"] = action_type
                if action_type == "qq_like":
                    task_data["times"] = times

            # 使用调度器
            if context.memory_engine:
                # 尝试获取调度器
                scheduler = getattr(context, 'scheduler', None)
                if scheduler:
                    from hub.scheduler import Task
                    task = Task(
                        task_id=task_id,
                        task_type=f"scheduled_{task_type}",
                        priority=priority,
                        data=task_data,
                        execute_at=scheduled_at
                    )
                    scheduler.schedule(task)

                # 同时存储在记忆中
                context.memory_engine.store_tide(
                    memory_id=f"scheduled_task_{task_id}",
                    content=task_data,
                    priority=priority / 10,
                    ttl=86400 * 30  # 30天
                )

                # 格式化输出
                result = f"✅ 定时任务已创建\n"
                result += f"任务ID: {task_id}\n"
                result += f"类型: {task_type}\n"
                result += f"目标: {target_type}_{target_id}\n"

                # 根据任务类型显示不同的信息
                if task_type == "action":
                    if action_type == "qq_like":
                        result += f"动作: 给用户点赞 {times} 次\n"
                    elif action_type == "send_poke":
                        result += f"动作: 拍一拍用户\n"
                elif message:
                    result += f"消息: {message}\n"

                if scheduled_at:
                    result += f"执行时间: {scheduled_at.strftime('%Y-%m-%d %H:%M')}\n"
                result += f"重复: {repeat}\n"
                result += f"优先级: {priority}"

                return result
            else:
                logger.warning("memory_engine 不可用，无法创建定时任务")
                return f"⚠️ 记忆引擎未初始化，任务已创建但无法持久化\n\n任务ID: {task_id}\n类型: {task_type}"

        except Exception as e:
            logger.error(f"创建定时任务失败: {e}", exc_info=True)
            return f"❌ 创建定时任务失败: {str(e)}"
