"""
游戏模式模块
提供稳定、独立、可维护的游戏模式管理
"""

from .mode_state import GameMode, GameState
from .tool_permission_config import GameModeType, ToolPermissionConfig
from .state_transition_validator import StateTransitionValidator, StateTransitionError
from .game_instance_manager import GameInstance, GameInstanceManager, get_instance_manager
from .error_handler import (
    ErrorHandler,
    GameModeError,
    StateTransitionError as StateTransitionErrorAlias,
    GameInstanceError,
    ToolPermissionError,
    error_handler,
    FallbackStrategy,
    with_error_handling
)
from .mode_manager import GameModeManager, get_game_mode_manager

# 导出接口
__all__ = [
    # 核心类
    'GameMode',
    'GameState',
    'GameModeType',
    'GameModeManager',

    # 权限控制
    'ToolPermissionConfig',

    # 状态管理
    'StateTransitionValidator',
    'StateTransitionError',

    # 实例管理
    'GameInstance',
    'GameInstanceManager',

    # 错误处理
    'ErrorHandler',
    'GameModeError',
    'GameInstanceError',
    'ToolPermissionError',
    'FallbackStrategy',
    'with_error_handling',

    # 单例获取
    'get_game_mode_manager',
    'get_instance_manager',
]

# 模块文档
"""
游戏模式架构优化报告
======================

核心改进
--------

1. 解耦与模块化
   - 工具权限逻辑移至 ToolPermissionConfig
   - 状态转换规则移至 StateTransitionValidator
   - 实例管理独立为 GameInstanceManager
   - 错误处理统一为 ErrorHandler

2. 稳定性增强
   - 状态机驱动，禁止非法状态转换
   - 错误隔离，单个游戏失败不影响其他
   - 自动降级，频繁失败的工具自动禁用
   - 健康检查，监控实例状态

3. 独立性提升
   - 每个游戏实例独立管理
   - 实例级别错误计数
   - 实例级别的状态转换钩子
   - 自动清理不活跃实例

4. 可维护性改善
   - 集中配置，修改权限规则只需改一处
   - 统一接口，所有工具使用相同的验证器
   - 装饰器支持，方便添加错误处理
   - 详细日志，便于问题排查

架构层次
---------

┌─────────────────────────────────────────┐
│         GameModeManager                 │
│   管理所有游戏模式（兼容层）            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     GameInstanceManager                 │
│   管理每个游戏实例（独立层）              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   StateTransitionValidator               │
│   验证状态转换（规则层）                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   ToolPermissionConfig                  │
│   配置工具权限（配置层）                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   ErrorHandler                          │
│   统一错误处理（安全层）                  │
└─────────────────────────────────────────┘

使用示例
--------

# 1. 启动游戏模式
from webnet.EntertainmentNet.game_mode import get_game_mode_manager
manager = get_game_mode_manager()
mode = manager.set_mode(
    chat_id="123456",
    mode_type=GameModeType.TRPG,
    game_name="我的跑团"
)

# 2. 转换游戏状态
manager.set_game_state("123456", GameState.IN_PROGRESS)

# 3. 检查工具权限
mode.is_tool_allowed("load_game_save")  # 返回 False (游戏中禁止加载)

# 4. 错误处理
from webnet.EntertainmentNet.game_mode import with_error_handling

@with_error_handling(chat_id_param="chat_id")
async def my_game_function(chat_id: str):
    # 可能失败的代码
    pass

# 5. 获取错误统计
from webnet.EntertainmentNet.game_mode import ErrorHandler
stats = ErrorHandler.get_error_stats("123456")

兼容性
------

完全兼容旧代码：
- GameMode 类保留原有接口
- GameModeManager 保留所有方法
- 旧数据自动迁移到新架构
"""
