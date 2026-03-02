"""
高级日志系统
提供完善的日志记录、分析和追踪功能
"""
import logging
import sys
import traceback
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from dataclasses import dataclass, asdict
import threading


@dataclass
class LogContext:
    """日志上下文"""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    extra: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式器"""

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 基础信息
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        # 添加上下文
        if self.include_context and hasattr(record, 'context'):
            context = record.context
            if isinstance(context, LogContext):
                log_data['context'] = context.to_dict()
            elif isinstance(context, dict):
                log_data['context'] = context

        # 添加额外字段
        if hasattr(record, 'extra_fields'):
            log_data['extra'] = record.extra_fields

        return json.dumps(log_data, ensure_ascii=False, default=str)


class AdvancedLogger:
    """
    高级日志器

    功能：
    - 结构化日志输出
    - 多级别日志处理
    - 上下文追踪
    - 异步日志写入
    - 日志轮转和归档
    - 日志分析和查询
    """

    def __init__(
        self,
        name: str = "Miya",
        log_dir: Path = Path("logs"),
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_structured: bool = True,
        enable_console: bool = True
    ):
        """
        初始化日志器

        Args:
            name: 日志器名称
            log_dir: 日志目录
            max_bytes: 单个日志文件最大字节数
            backup_count: 备份文件数量
            enable_structured: 是否启用结构化日志
            enable_console: 是否输出到控制台
        """
        self.name = name
        self.log_dir = log_dir
        self.enable_structured = enable_structured
        self.enable_console = enable_console

        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 日志器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # 线程本地存储（用于上下文）
        self._context = threading.local()

        # 添加处理器
        self._add_handlers(max_bytes, backup_count)

    def _add_handlers(self, max_bytes: int, backup_count: int) -> None:
        """添加日志处理器"""
        # 控制台处理器
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # 文件处理器 - 调试日志
        debug_handler = RotatingFileHandler(
            self.log_dir / f"{self.name}_debug.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        debug_handler.setFormatter(debug_formatter)
        self.logger.addHandler(debug_handler)

        # 文件处理器 - 错误日志
        error_handler = RotatingFileHandler(
            self.log_dir / f"{self.name}_error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(debug_formatter)
        self.logger.addHandler(error_handler)

        # 文件处理器 - 结构化日志
        if self.enable_structured:
            structured_handler = RotatingFileHandler(
                self.log_dir / f"{self.name}_structured.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            structured_handler.setLevel(logging.DEBUG)
            structured_formatter = StructuredFormatter(include_context=True)
            structured_handler.setFormatter(structured_formatter)
            self.logger.addHandler(structured_handler)

    def set_context(self, **kwargs) -> None:
        """设置日志上下文"""
        if not hasattr(self._context, 'data'):
            self._context.data = LogContext()

        for key, value in kwargs.items():
            if hasattr(self._context.data, key):
                setattr(self._context.data, key, value)
            else:
                if self._context.data.extra is None:
                    self._context.data.extra = {}
                self._context.data.extra[key] = value

    def clear_context(self) -> None:
        """清除日志上下文"""
        self._context.data = LogContext()

    def _add_context_to_record(self, record: logging.LogRecord) -> None:
        """将上下文添加到日志记录"""
        if hasattr(self._context, 'data'):
            record.context = self._context.data

    def debug(self, message: str, **kwargs) -> None:
        """记录调试日志"""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """记录信息日志"""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """记录警告日志"""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """记录错误日志"""
        self._log_with_context(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """记录严重错误日志"""
        self._log_with_context(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def _log_with_context(
        self,
        level: int,
        message: str,
        exc_info: bool = False,
        **kwargs
    ) -> None:
        """带上下文的日志记录"""
        record = self.logger.makeRecord(
            self.name,
            level,
            fn='',  # 由调用栈自动获取
            lno=0,  # 由调用栈自动获取
            msg=message,
            args=(),
            exc_info=None
        )

        # 添加上下文
        self._add_context_to_record(record)

        # 添加额外字段
        if kwargs:
            record.extra_fields = kwargs

        # 记录日志
        self.logger.handle(record)

    def log_exception(self, exception: Exception, context: Optional[Dict] = None) -> None:
        """记录异常"""
        error_data = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'exception_module': exception.__class__.__module__
        }

        if context:
            error_data['context'] = context

        self.error(
            f"异常: {type(exception).__name__}: {exception}",
            exc_info=True,
            **error_data
        )

    def get_logger(self) -> logging.Logger:
        """获取底层日志器"""
        return self.logger


class LoggerManager:
    """日志管理器（单例）"""

    _instance: Optional['LoggerManager'] = None
    _loggers: Dict[str, AdvancedLogger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_logger(
        self,
        name: str = "Miya",
        **kwargs
    ) -> AdvancedLogger:
        """
        获取或创建日志器

        Args:
            name: 日志器名称
            **kwargs: 其他配置参数

        Returns:
            AdvancedLogger 实例
        """
        if name not in self._loggers:
            self._loggers[name] = AdvancedLogger(name=name, **kwargs)
        return self._loggers[name]

    def get_all_loggers(self) -> Dict[str, AdvancedLogger]:
        """获取所有日志器"""
        return self._loggers.copy()


def get_logger(name: str = "Miya", **kwargs) -> AdvancedLogger:
    """获取日志器的便捷函数"""
    manager = LoggerManager()
    return manager.get_logger(name, **kwargs)


def log_function_call(func):
    """
    函数调用日志装饰器

    Args:
        func: 被装饰的函数

    Usage:
        @log_function_call
        async def my_function(arg1, arg2):
            ...
    """
    def sync_wrapper(*args, **kwargs):
        logger = get_logger()
        func_name = f"{func.__module__}.{func.__name__}"
        logger.debug(f"调用函数: {func_name}, 参数: args={args}, kwargs={kwargs}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"函数返回: {func_name}, 结果: {result}")
            return result
        except Exception as e:
            logger.log_exception(e, context={'function': func_name})
            raise

    async def async_wrapper(*args, **kwargs):
        logger = get_logger()
        func_name = f"{func.__module__}.{func.__name__}"
        logger.debug(f"调用异步函数: {func_name}, 参数: args={args}, kwargs={kwargs}")

        try:
            result = await func(*args, **kwargs)
            logger.debug(f"异步函数返回: {func_name}, 结果: {result}")
            return result
        except Exception as e:
            logger.log_exception(e, context={'function': func_name})
            raise

    # 根据函数类型返回对应的包装器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# 导出
__all__ = [
    'AdvancedLogger',
    'LoggerManager',
    'get_logger',
    'LogContext',
    'StructuredFormatter',
    'log_function_call'
]
