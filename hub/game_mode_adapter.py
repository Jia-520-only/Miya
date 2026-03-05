"""
游戏模式适配器 - 架构修复: 封装WebNet层的游戏模式访问

目的: 解决Hub层直接依赖WebNet层的问题
      通过适配器模式隔离层级边界,符合蜘蛛网分布式架构设计
"""

import logging
from typing import Dict, Optional, List
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class IGameModeAdapter(ABC):
    """游戏模式适配器接口"""

    @abstractmethod
    def get_mode(self, chat_id: str) -> Optional[Dict]:
        """获取当前模式"""

    @abstractmethod
    def get_game_memory(self, game_id: str) -> Optional[Dict]:
        """获取游戏记忆"""

    @abstractmethod
    def get_conversation_history(self, game_id: str, max_tokens: int = 80000) -> List[Dict]:
        """获取对话历史"""

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """估算token数"""

    @abstractmethod
    async def compress_conversation(self, game_id: str) -> bool:
        """压缩对话"""


class GameModeAdapter(IGameModeAdapter):
    """
    游戏模式适配器实现

    职责:
    1. 封装WebNet层的GameModeManager访问
    2. 提供统一的接口给Hub层使用
    3. 隔离层级边界,防止Hub层直接依赖WebNet层
    """

    def __init__(self, webnet_game_mode_manager=None):
        """
        初始化适配器

        Args:
            webnet_game_mode_manager: WebNet层的GameModeManager实例
                                   (通过M-Link或依赖注入获取)
        """
        self._game_mode_manager = webnet_game_mode_manager
        self._game_memory_manager = None

        if self._game_mode_manager:
            self._game_memory_manager = self._game_mode_manager.game_memory_manager
            logger.info("[GameModeAdapter] 适配器初始化成功,已连接到WebNet层")
        else:
            logger.warning("[GameModeAdapter] 未提供WebNet层的GameModeManager,适配器将处于未连接状态")

    def set_game_mode_manager(self, game_mode_manager):
        """
        设置游戏模式管理器(延迟注入)

        Args:
            game_mode_manager: WebNet层的GameModeManager实例
        """
        self._game_mode_manager = game_mode_manager
        self._game_memory_manager = game_mode_manager.game_memory_manager
        logger.info("[GameModeAdapter] GameModeManager已设置")

    def get_mode(self, chat_id: str) -> Optional[Dict]:
        """
        获取当前游戏模式

        Args:
            chat_id: 聊天ID

        Returns:
            模式信息字典 或 None
        """
        if not self._game_mode_manager:
            logger.debug("[GameModeAdapter] GameModeManager未连接")
            return None

        try:
            mode = self._game_mode_manager.get_mode(chat_id)
            if mode:
                return {
                    'mode_type': mode.mode_type.value,
                    'game_id': mode.game_id,
                    'prompt_key': mode.prompt_key,
                    'tool_whitelist': mode.tool_whitelist,
                    'extra_config': mode.extra_config
                }
            return None
        except Exception as e:
            logger.error(f"[GameModeAdapter] 获取模式失败: {e}")
            return None

    def get_game_memory(self, game_id: str) -> Optional[Dict]:
        """
        获取游戏记忆

        Args:
            game_id: 游戏ID

        Returns:
            游戏记忆数据 或 None
        """
        if not self._game_memory_manager:
            logger.debug("[GameModeAdapter] GameMemoryManager未连接")
            return None

        try:
            save_data = self._game_memory_manager.load_game(game_id)
            if save_data:
                return {
                    'game_id': save_data.game_id,
                    'save_id': save_data.save_id,
                    'save_name': save_data.save_name,
                    'story_progress': save_data.story_progress,
                    'game_state': save_data.game_state,
                    'characters': save_data.characters
                }
            return None
        except Exception as e:
            logger.error(f"[GameModeAdapter] 获取游戏记忆失败: {e}")
            return None

    def get_conversation_history(self, game_id: str, max_tokens: int = 80000) -> List[Dict]:
        """
        获取游戏对话历史

        Args:
            game_id: 游戏ID
            max_tokens: 最大token数

        Returns:
            对话列表
        """
        if not self._game_memory_manager:
            logger.debug("[GameModeAdapter] GameMemoryManager未连接")
            return []

        try:
            history = self._game_memory_manager.get_conversation_history(game_id, max_tokens)
            return history
        except Exception as e:
            logger.error(f"[GameModeAdapter] 获取对话历史失败: {e}")
            return []

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量

        Args:
            text: 输入文本

        Returns:
            token数量
        """
        if not self._game_memory_manager:
            # 降级估算: 中文1字符≈1.5token, 英文1单词≈1.5token
            return len(text) // 2 + len(text.split())

        try:
            return self._game_memory_manager.estimate_tokens(text)
        except Exception as e:
            logger.warning(f"[GameModeAdapter] Token估算失败,使用降级方案: {e}")
            return len(text) // 2 + len(text.split())

    def estimate_conversation_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算对话列表的总token数

        Args:
            messages: 消息列表

        Returns:
            总token数
        """
        if not self._game_memory_manager:
            total = 0
            for msg in messages:
                total += 10  # 角色标记约10个token
                total += self.estimate_tokens(msg.get('content', ''))
            return total

        try:
            return self._game_memory_manager.estimate_conversation_history_tokens(messages)
        except Exception as e:
            logger.warning(f"[GameModeAdapter] 对话token估算失败: {e}")
            return self.estimate_tokens(' '.join([m.get('content', '') for m in messages]))

    async def compress_conversation(self, game_id: str) -> bool:
        """
        压缩游戏对话

        Args:
            game_id: 游戏ID

        Returns:
            是否成功
        """
        if not self._game_memory_manager:
            logger.warning("[GameModeAdapter] GameMemoryManager未连接,无法压缩对话")
            return False

        try:
            return await self._game_memory_manager.compress_old_messages(game_id)
        except Exception as e:
            logger.error(f"[GameModeAdapter] 压缩对话失败: {e}")
            return False

    def add_conversation_message(
        self,
        game_id: str,
        role: str,
        content: str,
        player_id: Optional[int] = None,
        player_name: Optional[str] = None
    ) -> bool:
        """
        添加游戏对话消息

        Args:
            game_id: 游戏ID
            role: 角色 ('user' or 'assistant')
            content: 消息内容
            player_id: 玩家ID
            player_name: 玩家名称

        Returns:
            是否成功
        """
        if not self._game_memory_manager:
            logger.warning("[GameModeAdapter] GameMemoryManager未连接,无法添加消息")
            return False

        try:
            return self._game_memory_manager.add_conversation_message(
                game_id, role, content, player_id, player_name
            )
        except Exception as e:
            logger.error(f"[GameModeAdapter] 添加对话消息失败: {e}")
            return False

    def get_game_characters(
        self,
        game_id: str,
        player_id: int,
        is_admin: bool = False
    ) -> List[Dict]:
        """
        获取游戏角色卡

        Args:
            game_id: 游戏ID
            player_id: 请求的玩家ID
            is_admin: 是否是管理员

        Returns:
            角色卡列表
        """
        if not self._game_memory_manager:
            return []

        try:
            characters = self._game_memory_manager.get_visible_characters(
                game_id, player_id, is_admin
            )
            return [char.to_dict() for char in characters]
        except Exception as e:
            logger.error(f"[GameModeAdapter] 获取角色卡失败: {e}")
            return []

    def is_connected(self) -> bool:
        """
        检查适配器是否已连接到WebNet层

        Returns:
            是否已连接
        """
        return self._game_mode_manager is not None and self._game_memory_manager is not None

    def find_user_game(self, user_id: int) -> Optional[Dict]:
        """
        查找用户所在的游戏

        Args:
            user_id: 用户QQ号

        Returns:
            游戏模式信息 或 None
        """
        if not self._game_mode_manager or not self._game_memory_manager:
            return None

        try:
            # 遍历所有游戏模式，查找该用户是否在游戏中
            for chat_id, mode in self._game_mode_manager.modes.items():
                if mode.game_id:
                    # 检查该游戏是否有这个用户的角色
                    characters = self._game_memory_manager.get_visible_characters(
                        mode.game_id,
                        user_id,
                        is_admin=False
                    )
                    if characters:
                        return {
                            'mode_type': mode.mode_type.value,
                            'game_id': mode.game_id,
                            'prompt_key': mode.prompt_key,
                            'tool_whitelist': mode.tool_whitelist,
                            'extra_config': mode.extra_config
                        }
            return None
        except Exception as e:
            logger.error(f"[GameModeAdapter] 查找用户游戏失败: {e}")
            return None

    def filter_tools(self, all_tools: Dict[str, object], chat_id: str) -> Dict[str, object]:
        """
        根据当前模式过滤工具列表

        Args:
            all_tools: 所有工具字典
            chat_id: 聊天ID

        Returns:
            过滤后的工具字典
        """
        if not self._game_mode_manager:
            # 未连接时返回所有工具
            return all_tools

        try:
            return self._game_mode_manager.filter_tools(all_tools, chat_id)
        except Exception as e:
            logger.error(f"[GameModeAdapter] 过滤工具失败: {e}")
            return all_tools
