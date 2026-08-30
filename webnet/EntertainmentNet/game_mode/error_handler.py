"""
游戏模式错误处理器
提供统一的错误隔离、日志记录和降级机制
"""

import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime

from .mode_state import GameState
from .game_instance_manager import get_instance_manager


logger = logging.getLogger(__name__)


class GameModeError(Exception):
    """游戏模式基础异常"""
    pass


class StateTransitionError(GameModeError):
    """状态转换异常"""
    pass


class GameInstanceError(GameModeError):
    """游戏实例异常"""
    pass


class ToolPermissionError(GameModeError):
    """工具权限异常"""
    pass


class ErrorHandler:
    """
    游戏模式错误处理器

    职责：
    1. 统一错误捕获和日志记录
    2. 提供错误隔离机制
    3. 支持自动降级和恢复
    4. 提供错误统计和监控
    """

    # 错误统计
    error_stats: Dict[str, int] = {}

    @classmethod
    def handle_tool_error(
        cls,
        chat_id: str,
        tool_name: str,
        error: Exception,
        fallback_message: Optional[str] = None
    ) -> str:
        """
        处理工具执行错误

        Args:
            chat_id: 聊天ID
            tool_name: 工具名称
            error: 异常对象
            fallback_message: 降级消息

        Returns:
            错误消息或降级消息
        """
        error_key = f"{chat_id}:{tool_name}"
        cls.error_stats[error_key] = cls.error_stats.get(error_key, 0) + 1

        logger.error(
            f"[ErrorHandler] 工具执行错误: {chat_id}.{tool_name}, "
            f"错误: {type(error).__name__}: {error}"
        )

        # 记录实例错误
        instance_manager = get_instance_manager()
        instance = instance_manager.get_instance(chat_id)
        if instance:
            instance.record_error()

        # 检查是否需要禁用工具
        if cls.error_stats[error_key] >= 3:
            logger.warning(f"[ErrorHandler] 工具 {tool_name} 在 {chat_id} 中多次失败，建议禁用")

        return fallback_message or f"⚠️ 工具 {tool_name} 执行失败: {error}"

    @classmethod
    def safe_execute(
        cls,
        chat_id: str,
        func: Callable,
        fallback_value: Any = None,
        fallback_message: Optional[str] = None
    ) -> Any:
        """
        安全执行函数，捕获异常并提供降级

        Args:
            chat_id: 聊天ID
            func: 要执行的函数
            fallback_value: 降级返回值
            fallback_message: 降级消息

        Returns:
            函数执行结果或降级值
        """
        try:
            return func()
        except Exception as e:
            logger.error(f"[ErrorHandler] 安全执行失败: {e}", exc_info=True)
            return fallback_value

    @classmethod
    def get_error_stats(cls, chat_id: Optional[str] = None) -> Dict[str, int]:
        """
        获取错误统计

        Args:
            chat_id: 聊天ID（None 表示全部）

        Returns:
            错误统计字典
        """
        if chat_id:
            return {
                key: count
                for key, count in cls.error_stats.items()
                if key.startswith(f"{chat_id}:")
            }
        return cls.error_stats.copy()

    @classmethod
    def clear_error_stats(cls, chat_id: Optional[str] = None):
        """
        清除错误统计

        Args:
            chat_id: 聊天ID（None 表示全部）
        """
        if chat_id:
            keys_to_remove = [
                key for key in cls.error_stats.keys()
                if key.startswith(f"{chat_id}:")
            ]
            for key in keys_to_remove:
                del cls.error_stats[key]
        else:
            cls.error_stats.clear()


def with_error_handling(
    chat_id_param: str = "chat_id",
    fallback_message: Optional[str] = None,
    log_exception: bool = True
):
    """
    装饰器：为函数添加错误处理

    Args:
        chat_id_param: 聊天ID参数名
        fallback_message: 降级消息
        log_exception: 是否记录异常
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_exception:
                    logger.error(
                        f"[with_error_handling] 函数 {func.__name__} 执行失败: {e}",
                        exc_info=True
                    )

                # 获取 chat_id
                chat_id = kwargs.get(chat_id_param)
                if not chat_id and args:
                    # 尝试从位置参数获取
                    # 这里简化处理，实际需要根据函数签名定位
                    pass

                # 记录错误
                error_handler = ErrorHandler()
                if chat_id:
                    instance_manager = get_instance_manager()
                    instance = instance_manager.get_instance(str(chat_id))
                    if instance:
                        instance.record_error()

                # 返回降级消息
                return fallback_message or f"⚠️ 操作失败: {e}"

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_exception:
                    logger.error(
                        f"[with_error_handling] 函数 {func.__name__} 执行失败: {e}",
                        exc_info=True
                    )

                # 获取 chat_id
                chat_id = kwargs.get(chat_id_param)
                if not chat_id and args:
                    pass

                # 记录错误
                error_handler = ErrorHandler()
                if chat_id:
                    instance_manager = get_instance_manager()
                    instance = instance_manager.get_instance(str(chat_id))
                    if instance:
                        instance.record_error()

                # 返回降级消息
                return fallback_message or f"⚠️ 操作失败: {e}"

        # 根据函数类型返回合适的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class FallbackStrategy:
    """
    降级策略

    职责：
    1. 定义各种降级策略
    2. 根据错误类型选择合适的降级方案
    3. 提供降级执行接口
    """

    @staticmethod
    def get_safe_response(chat_id: str) -> str:
        """获取安全回复（降级方案）"""
        instance_manager = get_instance_manager()
        instance = instance_manager.get_instance(chat_id)

        if instance and not instance.is_healthy():
            # 实例不健康，建议重启
            return "⚠️ 游戏系统繁忙，请稍后重试或使用 exit_game 退出游戏模式"

        return "⚠️ 操作暂时不可用，请稍后重试"

    @staticmethod
    def should_disable_tool(chat_id: str, tool_name: str) -> bool:
        """判断是否应该禁用某个工具"""
        error_stats = ErrorHandler.get_error_stats(chat_id)
        error_key = f"{chat_id}:{tool_name}"
        return error_stats.get(error_key, 0) >= 3

    @staticmethod
    def get_available_tools(chat_id: str, all_tools: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取可用的工具列表（过滤掉频繁失败的工具）

        Args:
            chat_id: 聊天ID
            all_tools: 所有工具

        Returns:
            可用工具字典
        """
        available_tools = {}
        for tool_name, tool_obj in all_tools.items():
            if not FallbackStrategy.should_disable_tool(chat_id, tool_name):
                available_tools[tool_name] = tool_obj

        if len(available_tools) < len(all_tools):
            logger.warning(
                f"[FallbackStrategy] {chat_id} 已禁用 {len(all_tools) - len(available_tools)} 个频繁失败的工具"
            )

        return available_tools


# 全局错误处理器实例
error_handler = ErrorHandler()
