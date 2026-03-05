"""
状态转换验证器
规范游戏状态的转换流程，防止非法状态转换
"""

from typing import Set, Dict, Tuple, Optional, Callable
from enum import Enum
from .mode_state import GameState


class StateTransitionError(Exception):
    """状态转换异常"""
    pass


class StateTransitionValidator:
    """
    状态转换验证器

    职责：
    1. 定义合法的状态转换路径
    2. 验证状态转换是否合法
    3. 提供状态转换日志和追踪
    4. 支持自定义转换规则
    """

    # 合法的状态转换：from_state -> [to_states]
    VALID_TRANSITIONS: Dict[GameState, Set[GameState]] = {
        GameState.NOT_STARTED: {
            GameState.LOADING,   # 加载存档
            GameState.IN_PROGRESS,  # 直接开始游戏
        },
        GameState.LOADING: {
            GameState.IN_PROGRESS,  # 加载成功
            GameState.NOT_STARTED,  # 加载失败
            GameState.PAUSED,      # 加载完成但暂停
        },
        GameState.IN_PROGRESS: {
            GameState.PAUSED,      # 暂停游戏
            GameState.NOT_STARTED, # 结束游戏
        },
        GameState.PAUSED: {
            GameState.IN_PROGRESS, # 恢复游戏
            GameState.LOADING,    # 加载新存档
            GameState.NOT_STARTED, # 结束游戏
        },
    }

    # 转换原因说明
    TRANSITION_REASONS: Dict[Tuple[GameState, GameState], str] = {
        (GameState.NOT_STARTED, GameState.LOADING): "正在加载存档",
        (GameState.NOT_STARTED, GameState.IN_PROGRESS): "游戏开始",
        (GameState.LOADING, GameState.IN_PROGRESS): "存档加载完成",
        (GameState.LOADING, GameState.NOT_STARTED): "存档加载失败",
        (GameState.LOADING, GameState.PAUSED): "存档加载完成，等待开始",
        (GameState.IN_PROGRESS, GameState.PAUSED): "游戏暂停",
        (GameState.IN_PROGRESS, GameState.NOT_STARTED): "游戏结束",
        (GameState.PAUSED, GameState.IN_PROGRESS): "游戏恢复",
        (GameState.PAUSED, GameState.LOADING): "加载新存档",
        (GameState.PAUSED, GameState.NOT_STARTED): "游戏结束",
    }

    # 转换前的钩子函数类型
    TransitionHook = Callable[[GameState, GameState, dict], Optional[dict]]

    # 注册的钩子函数
    _hooks: Dict[Tuple[GameState, GameState], TransitionHook] = {}

    @classmethod
    def validate(
        cls,
        from_state: GameState,
        to_state: GameState,
        context: Optional[dict] = None,
        raise_on_error: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        验证状态转换是否合法

        Args:
            from_state: 当前状态
            to_state: 目标状态
            context: 转换上下文信息
            raise_on_error: 验证失败时是否抛出异常

        Returns:
            (是否合法, 错误信息)
        """
        if from_state == to_state:
            return True, None

        valid_targets = cls.VALID_TRANSITIONS.get(from_state, set())
        if to_state not in valid_targets:
            error_msg = (
                f"非法的状态转换: {from_state.value} -> {to_state.value}. "
                f"允许的转换: {[s.value for s in valid_targets]}"
            )
            if raise_on_error:
                raise StateTransitionError(error_msg)
            return False, error_msg

        return True, None

    @classmethod
    def get_transition_reason(cls, from_state: GameState, to_state: GameState) -> str:
        """获取状态转换的原因说明"""
        return cls.TRANSITION_REASONS.get(
            (from_state, to_state),
            f"状态转换: {from_state.value} -> {to_state.value}"
        )

    @classmethod
    def register_hook(
        cls,
        from_state: GameState,
        to_state: GameState,
        hook: TransitionHook
    ):
        """
        注册状态转换钩子函数

        Args:
            from_state: 当前状态
            to_state: 目标状态
            hook: 钩子函数，接收 (from_state, to_state, context)，返回可选的上下文
        """
        key = (from_state, to_state)
        cls._hooks[key] = hook

    @classmethod
    def execute_hooks(
        cls,
        from_state: GameState,
        to_state: GameState,
        context: Optional[dict] = None
    ) -> dict:
        """
        执行状态转换钩子

        Args:
            from_state: 当前状态
            to_state: 目标状态
            context: 转换上下文

        Returns:
            更新后的上下文
        """
        if context is None:
            context = {}

        key = (from_state, to_state)
        if key in cls._hooks:
            hook = cls._hooks[key]
            try:
                result = hook(from_state, to_state, context)
                if result is not None:
                    context.update(result)
            except Exception as e:
                # 钩子执行失败不应阻止状态转换
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"[StateTransitionValidator] 钩子执行失败: "
                    f"{from_state.value} -> {to_state.value}, error: {e}"
                )

        return context

    @classmethod
    def can_save(cls, game_state: GameState) -> bool:
        """检查当前状态是否可以创建存档"""
        return game_state in {GameState.IN_PROGRESS, GameState.PAUSED}

    @classmethod
    def can_load(cls, game_state: GameState) -> bool:
        """检查当前状态是否可以加载存档"""
        return game_state in {GameState.NOT_STARTED, GameState.PAUSED}

    @classmethod
    def can_exit(cls, game_state: GameState) -> bool:
        """检查当前状态是否可以退出游戏"""
        # 所有状态都可以退出
        return True

    @classmethod
    def reset_to_safe_state(cls, current_state: GameState) -> GameState:
        """
        将状态重置到安全状态（错误恢复）

        Args:
            current_state: 当前状态

        Returns:
            安全状态
        """
        if current_state == GameState.LOADING:
            # 加载失败时，回到未启动状态
            return GameState.NOT_STARTED
        return current_state
