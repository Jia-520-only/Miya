"""
游戏模式管理器
管理所有聊天窗口的游戏模式状态
"""

import logging
from typing import Dict, Optional, List
from pathlib import Path
import json
from datetime import datetime

from .mode_state import GameMode, GameState
from .tool_permission_config import GameModeType, ToolPermissionConfig
from .game_instance_manager import get_instance_manager
from .game_memory_manager import get_game_memory_manager
from core.constants import Encoding


logger = logging.getLogger(__name__)


class GameModeManager:
    """
    游戏模式管理器

    职责：
    1. 管理所有聊天窗口的游戏模式状态
    2. 提供模式切换功能
    3. 提供工具过滤功能
    4. 持久化模式状态
    """

    # 预定义工具白名单（从 ToolPermissionConfig 获取）
    TRPG_TOOLS = None  # 将在 __init__ 中从 ToolPermissionConfig 获取

    TAVERN_TOOLS = None  # 将在 __init__ 中从 ToolPermissionConfig 获取

    MODE_NAMES = {
        GameModeType.TRPG: "跑团",
        GameModeType.TAVERN: "酒馆",
        GameModeType.NONE: "普通"
    }

    def __init__(self, data_path: str = "data/game_modes.json"):
        self.data_path = Path(data_path)
        self.modes: Dict[str, GameMode] = {}  # chat_id -> GameMode
        self.game_memory_manager = get_game_memory_manager()  # 游戏记忆管理器
        self.instance_manager = get_instance_manager()  # 游戏实例管理器

        # 从 ToolPermissionConfig 获取工具白名单
        self.TRPG_TOOLS = ToolPermissionConfig.get_mode_whitelist(GameModeType.TRPG)
        self.TAVERN_TOOLS = ToolPermissionConfig.get_mode_whitelist(GameModeType.TAVERN)

        self.load()

    def load(self):
        """加载模式状态并恢复实例"""
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r', encoding=Encoding.UTF8) as f:
                    data = json.load(f)
                    for mode_data in data:
                        mode = GameMode.from_dict(mode_data)
                        self.modes[mode.chat_id] = mode

                        # 恢复游戏实例
                        self.instance_manager.create_instance(
                            chat_id=mode.chat_id,
                            mode_type=mode.mode_type,
                            game_mode=mode,
                            on_state_change=self._on_state_change
                        )

                    logger.info(f"[GameModeManager] 加载了 {len(self.modes)} 个游戏模式")
            except Exception as e:
                logger.error(f"[GameModeManager] 加载失败: {e}")

    def save(self):
        """保存模式状态"""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            data = [mode.to_dict() for mode in self.modes.values()]
            with open(self.data_path, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[GameModeManager] 已保存 {len(self.modes)} 个游戏模式")
        except Exception as e:
            logger.error(f"[GameModeManager] 保存失败: {e}")

    def set_mode(
        self,
        chat_id: str,
        mode_type: GameModeType,
        tool_whitelist: Optional[List[str]] = None,
        prompt_key: str = "default",
        extra_config: Optional[Dict] = None,
        create_game_memory: bool = True,
        game_name: Optional[str] = None,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        preserve_game_id: Optional[str] = None
    ) -> GameMode:
        """
        设置游戏模式

        Args:
            chat_id: 聊天ID（群号或用户号）
            mode_type: 模式类型
            tool_whitelist: 工具白名单（可选，使用预定义）
            prompt_key: 人设提示词key
            extra_config: 额外配置
            create_game_memory: 是否创建游戏记忆
            game_name: 游戏名称
            group_id: 群号
            user_id: 用户号
            preserve_game_id: 保留现有的 game_id (用于重启游戏时保留对话历史)

        Returns:
            GameMode 实例
        """
        # 使用预定义白名单
        if tool_whitelist is None:
            if mode_type == GameModeType.TRPG:
                tool_whitelist = self.TRPG_TOOLS.copy()
            elif mode_type == GameModeType.TAVERN:
                tool_whitelist = self.TAVERN_TOOLS.copy()
            else:
                tool_whitelist = []

        # 创建游戏记忆
        game_id = preserve_game_id  # 如果指定了保留的 game_id,则使用它
        memory_config = {}
        if create_game_memory and mode_type != GameModeType.NONE and not game_id:
            rule_system = extra_config.get('rule_system', 'trpg') if extra_config else 'trpg'
            game_id = self.game_memory_manager.create_game(
                game_name=game_name or f"{mode_type.value}_game_{chat_id}",
                rule_system=rule_system,
                mode_type=mode_type.value,
                group_id=group_id,
                user_id=user_id,
                auto_save_enabled=True
            )
            memory_config = {
                'enabled': True,
                'auto_save': True,
                'memory_context_limit': 10
            }
        elif game_id:
            # 保留现有 game_id,加载现有记忆配置
            memory_config = {
                'enabled': True,
                'auto_save': True,
                'memory_context_limit': 10
            }
            logger.info(f"[GameModeManager] {chat_id} 保留现有 game_id: {game_id}")

        mode = GameMode(
            chat_id=chat_id,
            mode_type=mode_type,
            tool_whitelist=tool_whitelist,
            prompt_key=prompt_key,
            extra_config=extra_config or {},
            game_id=game_id,
            memory_config=memory_config
        )

        self.modes[chat_id] = mode

        # 创建游戏实例
        self.instance_manager.create_instance(
            chat_id=chat_id,
            mode_type=mode_type,
            game_mode=mode,
            on_state_change=self._on_state_change
        )

        self.save()

        mode_name = self.MODE_NAMES.get(mode_type, "未知")
        logger.info(f"[GameModeManager] {chat_id} 已切换到 {mode_name} 模式")

        return mode

    def _on_state_change(self, chat_id: str, old_state: GameState, new_state: GameState, context: dict):
        """状态变更回调"""
        logger.info(f"[GameModeManager] {chat_id} 状态变更回调: {old_state.value} -> {new_state.value}")

    def get_mode(self, chat_id: str) -> Optional[GameMode]:
        """获取当前模式"""
        return self.modes.get(chat_id)

    def exit_mode(self, chat_id: str, auto_save: bool = True) -> Optional[GameModeType]:
        """
        退出游戏模式

        Args:
            chat_id: 聊天ID
            auto_save: 是否自动保存

        Returns:
            退出的模式类型
        """
        if chat_id in self.modes:
            mode = self.modes[chat_id]
            mode_type = mode.mode_type

            # 自动保存游戏记忆
            if auto_save and mode.game_id and mode.memory_config.get('auto_save', True):
                try:
                    self.game_memory_manager.save_game(mode.game_id)
                    logger.info(f"[GameModeManager] {chat_id} 游戏已自动保存")
                except Exception as e:
                    logger.error(f"[GameModeManager] 自动保存失败: {e}")

            # 移除实例（独立于 GameMode）
            self.instance_manager.remove_instance(chat_id)

            del self.modes[chat_id]
            self.save()

            mode_name = self.MODE_NAMES.get(mode_type, "未知")
            logger.info(f"[GameModeManager] {chat_id} 已退出 {mode_name} 模式")
            return mode_type
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
        mode = self.get_mode(chat_id)

        # 如果没有游戏模式，返回所有工具
        if mode is None or mode.mode_type == GameModeType.NONE:
            return all_tools

        # 过滤工具
        filtered_tools = {}
        for tool_name, tool_obj in all_tools.items():
            if mode.is_tool_allowed(tool_name):
                filtered_tools[tool_name] = tool_obj

        logger.debug(f"[GameModeManager] {chat_id} 工具过滤: {len(all_tools)} -> {len(filtered_tools)}")
        return filtered_tools

    def list_active_modes(self) -> List[GameMode]:
        """列出所有活跃的游戏模式"""
        return list(self.modes.values())

    def is_in_game_mode(self, chat_id: str) -> bool:
        """检查是否在游戏模式中"""
        mode = self.get_mode(chat_id)
        return mode is not None and mode.mode_type != GameModeType.NONE

    def set_game_state(self, chat_id: str, state: GameState, context: Optional[dict] = None) -> bool:
        """
        设置游戏状态（使用实例管理器）

        Args:
            chat_id: 聊天ID
            state: 游戏状态
            context: 转换上下文

        Returns:
            是否设置成功
        """
        try:
            # 使用实例管理器转换状态
            success = self.instance_manager.transition_state(chat_id, state, context)
            if success:
                self.save()
            return success
        except Exception as e:
            logger.error(f"[GameModeManager] 设置游戏状态失败: {e}")
            return False

    def get_game_state(self, chat_id: str) -> GameState:
        """获取游戏状态"""
        mode = self.get_mode(chat_id)
        return mode.game_state if mode else GameState.NOT_STARTED

    def get_game_memory_manager(self):
        """获取游戏记忆管理器"""
        return self.game_memory_manager

    def save_current_game(self, chat_id: str, save_name: Optional[str] = None) -> Optional[str]:
        """
        手动保存当前游戏

        Args:
            chat_id: 聊天ID
            save_name: 存档名称

        Returns:
            save_id 或 None
        """
        mode = self.get_mode(chat_id)
        if mode and mode.game_id:
            return self.game_memory_manager.save_game(mode.game_id, save_name)
        return None

    def load_game_memory(self, chat_id: str) -> Optional[Dict]:
        """
        加载游戏记忆

        Args:
            chat_id: 聊天ID

        Returns:
            游戏记忆数据 或 None
        """
        mode = self.get_mode(chat_id)
        if mode and mode.game_id:
            save_data = self.game_memory_manager.load_game(mode.game_id)
            if save_data:
                return {
                    'game_id': mode.game_id,
                    'story_progress': save_data.story_progress,
                    'characters': save_data.characters,
                    'game_state': save_data.game_state,
                    'save_id': save_data.save_id,
                    'save_name': save_data.save_name
                }
        return None

    def get_game_characters(self, chat_id: str, player_id: int, is_admin: bool = False) -> List:
        """
        获取游戏角色卡(带权限控制)

        Args:
            chat_id: 聊天ID
            player_id: 玩家ID
            is_admin: 是否管理员

        Returns:
            角色卡列表
        """
        mode = self.get_mode(chat_id)
        if mode and mode.game_id:
            return self.game_memory_manager.get_visible_characters(
                mode.game_id,
                player_id,
                is_admin
            )
        return []


# 全局单例
_game_mode_manager = None


def get_game_mode_manager() -> GameModeManager:
    """获取游戏模式管理器单例"""
    global _game_mode_manager
    if _game_mode_manager is None:
        _game_mode_manager = GameModeManager()
    return _game_mode_manager
