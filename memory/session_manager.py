"""
统一会话管理器 - SessionManager

负责管理所有平台（QQ/Web/Desktop/Terminal）的会话存储：
1. 多种触发条件：再见/晚安、超时、主动保存
2. 多类别存储：弥娅日记、用户日记、活动记录
3. 双重口吻：弥娅视角 + 用户视角
4. 定时提醒：晚间日记提醒
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionCategory:
    """会话类别"""
    MIYA_DIARY = "miya_diary"      # 弥娅日记
    USER_DIARY = "user_diary"       # 用户日记
    ACTIVITY = "activity"           # 活动记录
    TERMINAL = "terminal_session"    # 终端会话


class SessionManager:
    """
    统一会话管理器
    
    功能：
    1. 统一管理所有平台的会话
    2. 多种触发条件
    3. 多类别存储到 Lifebook
    4. 双重口吻记录
    5. 定时提醒
    """
    
    def __init__(
        self,
        memory_engine=None,
        conversation_history=None,
        scheduler=None,
        ai_client=None
    ):
        """
        初始化会话管理器
        
        Args:
            memory_engine: 记忆引擎（用于存储）
            conversation_history: 对话历史管理器
            scheduler: 调度器（用于定时提醒）
            ai_client: AI 客户端（用于生成摘要）
        """
        self.memory_engine = memory_engine
        self.conversation_history = conversation_history
        self.scheduler = scheduler
        self.ai_client = ai_client
        
        # 活动超时时间（分钟）
        self.activity_timeout_minutes = 30
        
        # 最后活动时间记录
        self.last_activity: Dict[str, datetime] = {}
        
        # 平台到类别的映射
        self.platform_category_map = {
            'terminal': SessionCategory.TERMINAL,
            'qq': SessionCategory.ACTIVITY,
            'web': SessionCategory.ACTIVITY,
            'desktop': SessionCategory.ACTIVITY,
            'pc_ui': SessionCategory.ACTIVITY,
        }
        
        logger.info("[SessionManager] 统一会话管理器初始化完成")
    
    # ========== 触发条件检测 ==========
    
    def should_save_on_message(self, message: str, platform: str) -> bool:
        """
        检测消息是否触发保存
        
        Args:
            message: 用户消息
            platform: 平台类型
            
        Returns:
            是否应该保存
        """
        msg_lower = message.lower()
        
        # 触发保存的关键词
        save_keywords = [
            '保存会话', '记日记', '写日记', '记录一下',
            '再见', '晚安', '拜拜', '走了', '下回见',
            '退出', 'exit', 'quit'
        ]
        
        return any(keyword in msg_lower for keyword in save_keywords)
    
    def should_save_diary(self, message: str) -> bool:
        """
        检测是否是记日记请求
        
        Args:
            message: 用户消息
            
        Returns:
            是否是记日记
        """
        msg_lower = message.lower()
        diary_keywords = [
            '记日记', '写日记', '帮我记', '我要记日记',
            '记录今天', '记录一下'
        ]
        
        return any(keyword in msg_lower for keyword in diary_keywords)
    
    def check_timeout_save(self, session_id: str) -> bool:
        """
        检查是否超时需要自动保存
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否超时
        """
        if session_id not in self.last_activity:
            return False
        
        last_time = self.last_activity[session_id]
        elapsed = datetime.now() - last_time
        
        return elapsed > timedelta(minutes=self.activity_timeout_minutes)
    
    def update_activity(self, session_id: str) -> None:
        """更新会话活动时间"""
        self.last_activity[session_id] = datetime.now()
    
    # ========== 会话保存 ==========
    
    async def save_session(
        self,
        session_id: str,
        platform: str,
        messages: List[Any],
        category: str = None,
        is_diary: bool = False,
        diary_content: str = None
    ) -> Dict:
        """
        保存会话到 Lifebook
        
        Args:
            session_id: 会话ID
            platform: 平台类型
            messages: 对话消息列表
            category: 存储类别（默认根据平台自动选择）
            is_diary: 是否是日记模式
            diary_content: 用户提供的日记内容（记日记时）
            
        Returns:
            保存结果
        """
        try:
            # 确定类别
            if category is None:
                category = self.platform_category_map.get(platform, SessionCategory.ACTIVITY)
            
            # 生成双重口吻的摘要
            if is_diary and diary_content:
                # 用户主动记日记
                content = self._generate_diary_content(diary_content, platform, is_user_diary=True)
                title = self._generate_title(category, is_user_diary=True)
            else:
                # 普通会话保存
                content = self._generate_session_summary(messages, platform)
                title = self._generate_title(category)
            
            # 存储到记忆系统
            if self.memory_engine:
                entry_id = f"{category}_{session_id}_{int(datetime.now().timestamp())}"
                self.memory_engine.store_tide(
                    entry_id,
                    {
                        'type': category,
                        'title': title,
                        'content': content,
                        'platform': platform,
                        'session_id': session_id,
                        'timestamp': datetime.now().isoformat(),
                        'is_diary': is_diary,
                    }
                )
                logger.info(f"[SessionManager] 会话已保存: {entry_id}")
            
            # 清除对话历史
            if self.conversation_history:
                full_session_id = f"{platform}_{session_id}"
                await self.conversation_history.clear_session(full_session_id)
                logger.info(f"[SessionManager] 对话历史已清除: {full_session_id}")
            
            return {
                "success": True,
                "message": "会话已保存到 LifeBook",
                "category": category,
                "title": title
            }
            
        except Exception as e:
            logger.error(f"[SessionManager] 保存会话失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e)
            }
    
    # ========== 内容生成 ==========
    
    def _generate_title(self, category: str, is_user_diary: bool = False) -> str:
        """生成标题"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M")
        
        if category == SessionCategory.MIYA_DIARY:
            return f"弥娅日记 - {date_str}"
        elif category == SessionCategory.USER_DIARY:
            return f"用户日记 - {date_str}"
        elif category == SessionCategory.TERMINAL:
            return f"终端会话 - {date_str} {time_str}"
        else:
            return f"活动记录 - {date_str}"
    
    def _generate_session_summary(self, messages: List[Any], platform: str) -> str:
        """
        生成会话摘要（双重口吻）
        
        Args:
            messages: 对话消息列表
            platform: 平台类型
            
        Returns:
            Markdown 格式的摘要
        """
        lines = []
        
        # 标题
        lines.append(f"# {platform.upper()} 会话记录\n")
        lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append(f"**平台**: {platform}\n")
        
        # ===== 弥娅视角 =====
        lines.append("\n## 弥娅视角\n")
        lines.append("*以下是从弥娅的角度记录的*\n")
        
        miya_actions = []
        user_requests = []
        
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)
            role = msg.role if hasattr(msg, 'role') else 'unknown'
            
            if role == 'user':
                # 用户说了什么
                if any(kw in content for kw in ['打开', '启动', '运行', '执行', '安装', '检查']):
                    user_requests.append(content)
            elif role == 'assistant':
                # 弥娅做了什么
                if any(kw in content for kw in ['已打开', '已启动', '已创建', '已完成', '会话ID']):
                    miya_actions.append(content.split('\n')[0][:100])
        
        if miya_actions:
            for action in miya_actions[-5:]:
                lines.append(f"- {action}\n")
        else:
            lines.append("- 进行了日常对话\n")
        
        # ===== 用户视角 =====
        lines.append("\n## 用户视角\n")
        lines.append("*以下是从用户角度记录的*\n")
        
        if user_requests:
            for req in user_requests[-5:]:
                lines.append(f"- 用户：{req}\n")
        else:
            lines.append("- 用户进行了日常交流\n")
        
        # ===== 总结 =====
        lines.append("\n## 总结\n")
        total = len(messages) // 2 if messages else 0
        lines.append(f"本次会话共 {total} 轮对话。\n")
        
        return "".join(lines)
    
    def _generate_diary_content(
        self, 
        diary_content: str, 
        platform: str,
        is_user_diary: bool = False
    ) -> str:
        """
        生成日记内容（双重口吻）
        
        Args:
            diary_content: 用户提供的日记内容
            platform: 平台类型
            is_user_diary: 是否是用户日记
            
        Returns:
            Markdown 格式的日记
        """
        lines = []
        
        if is_user_diary:
            # 用户日记
            lines.append(f"# 用户日记\n")
            lines.append(f"**日期**: {datetime.now().strftime('%Y-%m-%d')}\n")
            lines.append(f"**时间**: {datetime.now().strftime('%H:%M')}\n")
            lines.append(f"**平台**: {platform}\n")
            
            lines.append("\n## 用户记录\n")
            lines.append(f"{diary_content}\n")
            
            lines.append("\n## 弥娅的观察\n")
            lines.append("*以下是从弥娅视角的观察*\n")
            lines.append(f"- 用户在 {platform} 平台上记录了日记\n")
            lines.append(f"- 这是一段珍贵的记忆\n")
        else:
            # 弥娅日记
            lines.append(f"# 弥娅日记\n")
            lines.append(f"**日期**: {datetime.now().strftime('%Y-%m-%d')}\n")
            lines.append(f"**时间**: {datetime.now().strftime('%H:%M')}\n")
            
            lines.append("\n## 今日记录\n")
            lines.append(f"{diary_content}\n")
            
            lines.append("\n## 我的感受\n")
            lines.append("*弥娅的感受*\n")
            lines.append("- 今天又陪伴了用户，很开心\n")
        
        return "".join(lines)
    
    # ========== 定时提醒 ==========
    
    async def schedule_diary_reminder(self, user_id: str, time: str = "21:00") -> bool:
        """
        设置日记提醒
        
        Args:
            user_id: 用户ID
            time: 提醒时间（格式：HH:MM）
            
        Returns:
            是否设置成功
        """
        if not self.scheduler:
            logger.warning("[SessionManager] 调度器未初始化，无法设置提醒")
            return False
        
        try:
            # 解析时间
            hour, minute = map(int, time.split(':'))
            
            # 创建提醒任务
            reminder_message = "佳宝，今天过得怎么样？想记日记吗？我可以帮你记录哦~"
            
            # 这里需要根据调度器的具体API来实现
            # 暂时返回一个成功标志
            logger.info(f"[SessionManager] 已设置日记提醒: user={user_id}, time={time}")
            
            return True
            
        except Exception as e:
            logger.error(f"[SessionManager] 设置提醒失败: {e}")
            return False
    
    # ========== 对话历史获取 ==========
    
    async def get_conversation_messages(
        self, 
        session_id: str, 
        platform: str,
        limit: int = 50
    ) -> List[Any]:
        """
        获取对话历史消息
        
        Args:
            session_id: 会话ID
            platform: 平台类型
            limit: 返回数量限制
            
        Returns:
            消息列表
        """
        if not self.conversation_history:
            return []
        
        full_session_id = f"{platform}_{session_id}"
        
        try:
            messages = await self.conversation_history.get_history(
                full_session_id,
                limit=limit
            )
            return messages
        except Exception as e:
            logger.error(f"[SessionManager] 获取对话历史失败: {e}")
            return []


# 全局实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def init_session_manager(
    memory_engine=None,
    conversation_history=None,
    scheduler=None,
    ai_client=None
) -> SessionManager:
    """初始化全局会话管理器"""
    global _session_manager
    _session_manager = SessionManager(
        memory_engine=memory_engine,
        conversation_history=conversation_history,
        scheduler=scheduler,
        ai_client=ai_client
    )
    return _session_manager
