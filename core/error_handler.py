"""
统一错误处理模块
为Miya项目提供统一的错误处理和日志记录功能
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar, cast

from .project_types import AppError, ErrorCode

logger = logging.getLogger(__name__)

# 类型变量用于泛型
T = TypeVar("T")
P = TypeVar("P")  # 参数类型
R = TypeVar("R")  # 返回类型


# ==================== 错误类定义 ====================
class AIError(AppError):
    """AI相关错误"""

    pass


class TerminalError(AppError):
    """终端相关错误"""

    pass


class ConfigError(AppError):
    """配置相关错误"""

    pass


class NetworkError(AppError):
    """网络相关错误"""

    pass


class ValidationError(AppError):
    """验证错误"""

    pass


# ==================== 错误处理装饰器 ====================
def error_handler(func: Callable[P, R]) -> Callable[P, R]:
    """
    错误处理装饰器

    自动捕获异常并转换为AppError，同时记录日志
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except AppError as e:
            # 已知的应用错误，记录警告并重新抛出
            logger.warning(f"应用错误 [{e.code.value}]: {e.message}", exc_info=True)
            raise
        except Exception as e:
            # 未知错误，转换为内部错误
            logger.error(f"未处理的错误: {e}", exc_info=True)
            raise AppError(code=ErrorCode.SYSTEM_ERROR, message="内部服务器错误", original_error=e)

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AppError as e:
            logger.warning(f"应用错误 [{e.code.value}]: {e.message}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"未处理的错误: {e}", exc_info=True)
            raise AppError(code=ErrorCode.SYSTEM_ERROR, message="内部服务器错误", original_error=e)

    return cast(Callable[P, R], async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: Optional[list[type[Exception]]] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    重试装饰器

    在发生指定错误时自动重试

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 退避因子（每次重试延迟时间乘以此因子）
        retry_on: 需要重试的异常类型列表，如果为None则重试所有异常
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"重试 {func.__name__} 第 {attempt} 次，等待 {current_delay:.1f} 秒")
                        await asyncio.sleep(current_delay)

                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # 检查是否需要重试
                    should_retry = retry_on is None or any(isinstance(e, exc_type) for exc_type in (retry_on or []))

                    if not should_retry or attempt == max_retries:
                        break

                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {e}")

                    # 更新延迟时间（指数退避）
                    current_delay *= backoff_factor

            # 所有重试都失败
            if last_exception:
                logger.error(f"{func.__name__} 重试 {max_retries} 次后失败", exc_info=True)
                raise last_exception

            # 理论上不会到达这里
            raise AppError(code=ErrorCode.SYSTEM_ERROR, message=f"{func.__name__} 执行失败")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"重试 {func.__name__} 第 {attempt} 次，等待 {current_delay:.1f} 秒")
                        time.sleep(current_delay)

                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # 检查是否需要重试
                    should_retry = retry_on is None or any(isinstance(e, exc_type) for exc_type in (retry_on or []))

                    if not should_retry or attempt == max_retries:
                        break

                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {e}")

                    # 更新延迟时间（指数退避）
                    current_delay *= backoff_factor

            # 所有重试都失败
            if last_exception:
                logger.error(f"{func.__name__} 重试 {max_retries} 次后失败", exc_info=True)
                raise last_exception

            # 理论上不会到达这里
            raise AppError(code=ErrorCode.SYSTEM_ERROR, message=f"{func.__name__} 执行失败")

        return cast(Callable[P, R], async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)

    return decorator


# ==================== 性能监控装饰器 ====================
def log_execution_time(func: Callable[P, R]) -> Callable[P, R]:
    """
    记录执行时间装饰器

    记录函数的执行时间，并在执行时间过长时发出警告
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time

            logger.info(f"函数 {func.__name__} 执行时间: {elapsed:.3f}s")

            if elapsed > 5.0:  # 超过5秒警告
                logger.warning(f"函数 {func.__name__} 执行时间过长: {elapsed:.3f}s")

            return result
        except Exception:
            elapsed = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败, 耗时: {elapsed:.3f}s", exc_info=True)
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            logger.info(f"函数 {func.__name__} 执行时间: {elapsed:.3f}s")

            if elapsed > 5.0:
                logger.warning(f"函数 {func.__name__} 执行时间过长: {elapsed:.3f}s")

            return result
        except Exception:
            elapsed = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败, 耗时: {elapsed:.3f}s", exc_info=True)
            raise

    return cast(Callable[P, R], async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)


# ==================== 验证装饰器 ====================
def validate_arguments(
    validators: dict[str, Callable[[Any], bool]] = None, error_message: str = "参数验证失败"
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    参数验证装饰器

    验证函数参数是否符合要求

    Args:
        validators: 验证器字典，键为参数名，值为验证函数
        error_message: 验证失败时的错误消息
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if validators:
                # 获取参数名
                import inspect

                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                # 验证参数
                for param_name, validator in validators.items():
                    if param_name in bound_args.arguments:
                        value = bound_args.arguments[param_name]
                        if not validator(value):
                            raise ValidationError(
                                code=ErrorCode.CONFIG_INVALID,
                                message=f"{error_message}: {param_name}={value}",
                                details={"parameter": param_name, "value": value},
                            )

            if asyncio.iscoroutinefunction(func):

                async def async_wrapper():
                    return await func(*args, **kwargs)

                return async_wrapper()
            else:
                return func(*args, **kwargs)

        return cast(Callable[P, R], wrapper)

    return decorator


# ==================== 性能监控器 ====================
@dataclass
class PerformanceMetrics:
    """性能指标"""

    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    success_count: int = 0
    error_count: int = 0
    last_called: Optional[float] = None

    @property
    def average_time(self) -> float:
        """平均执行时间"""
        return self.total_time / self.call_count if self.call_count > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 1.0


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics: dict[str, PerformanceMetrics] = {}
        self.enabled: bool = True

    def record(self, function_name: str, execution_time: float, success: bool = True) -> None:
        """记录性能指标"""
        if not self.enabled:
            return

        if function_name not in self.metrics:
            self.metrics[function_name] = PerformanceMetrics(function_name=function_name)

        metrics = self.metrics[function_name]
        metrics.call_count += 1
        metrics.total_time += execution_time
        metrics.last_called = time.time()

        if success:
            metrics.success_count += 1
        else:
            metrics.error_count += 1

    def get_metrics(self, function_name: str) -> Optional[PerformanceMetrics]:
        """获取指定函数的性能指标"""
        return self.metrics.get(function_name)

    def get_slow_functions(self, threshold: float = 1.0) -> list[PerformanceMetrics]:
        """获取执行时间超过阈值的函数"""
        return [metrics for metrics in self.metrics.values() if metrics.average_time > threshold]

    def get_frequently_called(self, min_calls: int = 10) -> list[PerformanceMetrics]:
        """获取调用频繁的函数"""
        return [metrics for metrics in self.metrics.values() if metrics.call_count >= min_calls]

    def reset(self) -> None:
        """重置所有指标"""
        self.metrics.clear()

    def generate_report(self) -> dict[str, Any]:
        """生成性能报告"""
        return {
            "total_functions": len(self.metrics),
            "total_calls": sum(m.call_count for m in self.metrics.values()),
            "slow_functions": [
                {"function": m.function_name, "avg_time": m.average_time, "calls": m.call_count}
                for m in self.get_slow_functions(0.5)
            ],
            "frequently_called": [
                {"function": m.function_name, "calls": m.call_count, "avg_time": m.average_time}
                for m in self.get_frequently_called(5)
            ],
        }


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


def monitor_performance(func: Callable[P, R]) -> Callable[P, R]:
    """
    性能监控装饰器

    记录函数的执行时间和成功率
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        success = True

        try:
            result = await func(*args, **kwargs)
            return result
        except Exception:
            success = False
            raise
        finally:
            execution_time = time.time() - start_time
            performance_monitor.record(func.__name__, execution_time, success)

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        success = True

        try:
            result = func(*args, **kwargs)
            return result
        except Exception:
            success = False
            raise
        finally:
            execution_time = time.time() - start_time
            performance_monitor.record(func.__name__, execution_time, success)

    return cast(Callable[P, R], async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)


# ==================== 工具函数 ====================
def ensure_error_response(error: Exception) -> dict[str, Any]:
    """
    确保错误响应格式统一

    Args:
        error: 异常对象

    Returns:
        统一的错误响应字典
    """
    if isinstance(error, AppError):
        return error.to_dict()
    else:
        return {
            "error": ErrorCode.SYSTEM_ERROR.value,
            "message": str(error),
            "type": error.__class__.__name__,
            "timestamp": time.time(),
        }


def log_and_raise(error_class: type[AppError], code: ErrorCode, message: str, **kwargs: Any) -> None:
    """
    记录日志并抛出错误

    Args:
        error_class: 错误类
        code: 错误代码
        message: 错误消息
        **kwargs: 传递给错误构造函数的额外参数
    """
    error = error_class(code=code, message=message, **kwargs)
    logger.error(f"{error_class.__name__} [{code.value}]: {message}", exc_info=True)
    raise error


# ==================== 上下文管理器 ====================
class ErrorContext:
    """
    错误上下文管理器

    在上下文中捕获和处理错误
    """

    def __init__(self, suppress: bool = False, default_value: Any = None):
        """
        Args:
            suppress: 是否抑制错误
            default_value: 出错时返回的默认值
        """
        self.suppress = suppress
        self.default_value = default_value
        self.error: Optional[Exception] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.error = exc_val
            if not self.suppress:
                return False  # 重新抛出异常
            else:
                logger.warning(f"错误被抑制: {exc_val}", exc_info=True)
                return True  # 抑制异常
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# ==================== 初始化函数 ====================
def setup_error_handling(log_level: str = "INFO") -> None:
    """
    设置错误处理

    Args:
        log_level: 日志级别
    """
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, log_level.upper()), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("错误处理系统已初始化")
