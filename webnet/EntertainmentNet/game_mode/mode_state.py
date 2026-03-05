"""
游戏模式状态数据类
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


# 注意：GameModeType 已移至 tool_permission_config.py
# 这里保留导入以兼容旧代码
from .tool_permission_config import GameModeType


class GameState(Enum):
    """游戏运行状态"""
    NOT_STARTED = "not_started"      # 游戏未启动
    LOADING = "loading"              # 加载存档中
    IN_PROGRESS = "in_progress"      # 游戏进行中
    PAUSED = "paused"                # 暂停中


@dataclass
class GameMode:
    """
    游戏模式状态

    Attributes:
        chat_id: 聊天ID（群号或用户号）
        mode_type: 模式类型
        game_state: 游戏运行状态
        started_at: 启动时间
        tool_whitelist: 允许的工具白名单
        prompt_key: 人设提示词key
        extra_config: 额外配置（规则系统、氛围等）
        game_id: 游戏实例ID（用于游戏记忆分区）
        memory_config: 记忆配置
    """
    chat_id: str
    mode_type: GameModeType
    game_state: GameState = GameState.NOT_STARTED
    started_at: datetime = field(default_factory=datetime.now)
    tool_whitelist: List[str] = field(default_factory=list)
    prompt_key: str = "default"
    extra_config: Dict = field(default_factory=dict)
    game_id: Optional[str] = None  # 游戏实例ID
    memory_config: Dict = field(default_factory=dict)  # 记忆配置

    def is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用（委托给 ToolPermissionConfig）"""
        from .tool_permission_config import ToolPermissionConfig

        return ToolPermissionConfig.is_tool_allowed(
            tool_name=tool_name,
            mode_type=self.mode_type,
            game_state=self.game_state,
            tool_whitelist=self.tool_whitelist
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'chat_id': self.chat_id,
            'mode_type': self.mode_type.value,
            'game_state': self.game_state.value,
            'started_at': self.started_at.isoformat(),
            'tool_whitelist': self.tool_whitelist,
            'prompt_key': self.prompt_key,
            'extra_config': self.extra_config,
            'game_id': self.game_id,
            'memory_config': self.memory_config
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GameMode':
        """从字典创建"""
        game_state = GameState.NOT_STARTED
        if 'game_state' in data:
            game_state = GameState(data['game_state'])
        elif data.get('mode_type') != 'none':
            # 兼容旧数据：有游戏模式但没有game_state，默认为IN_PROGRESS
            game_state = GameState.IN_PROGRESS

        return cls(
            chat_id=data['chat_id'],
            mode_type=GameModeType(data['mode_type']),
            game_state=game_state,
            started_at=datetime.fromisoformat(data['started_at']),
            tool_whitelist=data.get('tool_whitelist', []),
            prompt_key=data.get('prompt_key', 'default'),
            extra_config=data.get('extra_config', {}),
            game_id=data.get('game_id'),
            memory_config=data.get('memory_config', {})
        )
