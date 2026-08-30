"""
工具权限配置器
集中管理游戏工具的权限规则，实现解耦和可维护性
"""

from typing import Set, Dict, List, TYPE_CHECKING
from enum import Enum

# 避免循环导入：使用 TYPE_CHECKING
if TYPE_CHECKING:
    from .mode_state import GameState


class GameModeType(Enum):
    """游戏模式类型"""
    NONE = "none"           # 普通模式
    TRPG = "trpg"           # 跑团模式
    TAVERN = "tavern"       # 酒馆模式


class ToolPermissionConfig:
    """
    工具权限配置器

    职责：
    1. 定义各游戏模式在不同状态下的工具权限
    2. 提供权限查询接口
    3. 支持动态扩展权限规则
    """

    # 基础工具：所有状态下始终允许
    BASE_TOOLS: Set[str] = {
        'get_current_time',
        'get_user_info',
        'python_interpreter',
        'send_message',
        'get_recent_messages',
        'get_member_list',
        'get_member_info',
        'find_member',
        'filter_members',
        'rank_members',
    }

    # 退出工具：所有状态下始终允许
    EXIT_TOOLS: Set[str] = {'exit_game'}

    # 存档管理工具：在游戏中受限
    SAVE_TOOLS: Set[str] = {
        'load_game_save',
        'create_game_save',
        'list_game_saves',
    }

    # 各游戏模式的工具白名单
    MODE_TOOL_WHITELIST: Dict[GameModeType, List[str]] = {
        GameModeType.TRPG: [
            'roll_dice', 'roll_secret',
            'create_pc', 'show_pc', 'update_pc', 'delete_pc',
            'skill_check', 'kp_command', 'attack', 'combat_log',
            'rest', 'start_combat', 'add_initiative', 'next_turn',
            'show_initiative', 'end_combat',
            'search_trpg_characters', 'search_trpg_by_attribute',
            'search_trpg_by_skill',
            'list_game_saves', 'create_game_save', 'load_game_save',
            'search_game_memory',
            'start_trpg', 'exit_game',
        ],
        GameModeType.TAVERN: [
            'tavern_chat', 'generate_story', 'continue_story',
            'set_mood', 'create_tavern_character', 'list_tavern_characters',
            'start_multi_chat', 'multi_character_chat', 'set_character_focus',
            'create_story_branch', 'add_story_choice', 'show_story_tree',
            'select_story_branch',
            'search_tavern_stories', 'search_tavern_characters',
            'search_tavern_preferences',
            'list_game_saves', 'create_game_save', 'load_game_save',
            'search_game_memory',
            'start_tavern', 'exit_game',
        ],
        GameModeType.NONE: [],
    }

    @classmethod
    def is_tool_allowed(
        cls,
        tool_name: str,
        mode_type: GameModeType,
        game_state: "GameState",
        tool_whitelist: List[str]
    ) -> bool:
        """
        检查工具是否允许使用

        Args:
            tool_name: 工具名称
            mode_type: 游戏模式类型
            game_state: 游戏状态
            tool_whitelist: 工具白名单

        Returns:
            是否允许使用
        """
        # 退出工具始终允许
        if tool_name in cls.EXIT_TOOLS:
            return True

        # 基础工具始终允许
        if tool_name in cls.BASE_TOOLS:
            return True

        # 非游戏模式，只允许基础工具
        if mode_type == GameModeType.NONE:
            return False

        # 【核心】基于游戏状态的权限控制
        # LOADING 状态：禁止所有游戏工具
        if game_state.value == "loading":
            return False

        # IN_PROGRESS 状态：禁止存档工具（防止游戏中重复加载）
        if game_state.value == "in_progress" and tool_name in cls.SAVE_TOOLS:
            return False

        # 检查白名单
        return tool_name in tool_whitelist

    @classmethod
    def get_mode_whitelist(cls, mode_type: GameModeType) -> List[str]:
        """获取指定游戏模式的工具白名单"""
        return cls.MODE_TOOL_WHITELIST.get(mode_type, []).copy()

    @classmethod
    def get_forbidden_tools_in_state(cls, game_state: "GameState") -> Set[str]:
        """获取指定状态下禁止的工具"""
        state_value = game_state.value if hasattr(game_state, 'value') else str(game_state)
        if state_value == "loading":
            # 加载状态禁止所有工具（除了基础工具和退出工具）
            return set()
        elif state_value == "in_progress":
            # 游戏进行中禁止存档工具
            return cls.SAVE_TOOLS.copy()
        return set()

    @classmethod
    def register_custom_tool(
        cls,
        mode_type: GameModeType,
        tool_name: str,
        allowed_states: List[str] = None
    ):
        """
        注册自定义工具到指定模式

        Args:
            mode_type: 游戏模式类型
            tool_name: 工具名称
            allowed_states: 允许使用的状态列表（None 表示所有状态）
        """
        if mode_type not in cls.MODE_TOOL_WHITELIST:
            cls.MODE_TOOL_WHITELIST[mode_type] = []

        if tool_name not in cls.MODE_TOOL_WHITELIST[mode_type]:
            cls.MODE_TOOL_WHITELIST[mode_type].append(tool_name)
