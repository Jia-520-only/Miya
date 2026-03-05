"""
TavernNet 子网基类
酒馆子网的核心实现
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from mlink.mlink_core import MLinkCore
from .memory import TavernMemory
from .character import CharacterManager


class TavernNet:
    """弥娅酒馆子网"""

    def __init__(
        self,
        mlink: Optional[MLinkCore] = None,
        ai_client=None,
        personality=None
    ):
        self.mlink = mlink
        self.ai_client = ai_client
        self.personality = personality

        # 初始化核心组件
        self.memory = TavernMemory()
        self.character_manager = CharacterManager()

        # 当前会话状态
        self.active_sessions: Dict[str, Dict] = {}

    async def initialize(self):
        """初始化酒馆子网"""
        # TODO: 加载保存的角色和记忆
        pass

    async def shutdown(self):
        """关闭酒馆子网"""
        # TODO: 保存状态
        pass

    def get_session_state(self, chat_id: str) -> Dict:
        """获取会话状态"""
        return self.active_sessions.get(chat_id, {})

    def set_session_state(self, chat_id: str, state: Dict):
        """设置会话状态"""
        self.active_sessions[chat_id] = state

    def clear_session_state(self, chat_id: str):
        """清除会话状态"""
        if chat_id in self.active_sessions:
            del self.active_sessions[chat_id]
