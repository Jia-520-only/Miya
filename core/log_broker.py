"""
弥娅系统 - 日志代理
"""

import logging
from asyncio import Queue
from typing import Callable, Optional


class LogBroker:
    """日志代理 - 将日志分发到 WebUI"""

    def __init__(self):
        self.log_queue: Queue = Queue()
        self.handlers: list = []

    def add_handler(self, handler):
        """添加日志处理器"""
        self.handlers.append(handler)


class LogManager:
    """日志管理器"""

    _queue_handler: Optional[Callable] = None

    @classmethod
    def set_queue_handler(cls, log_broker: LogBroker):
        """设置队列处理器"""
        cls._queue_handler = log_broker

    @classmethod
    def configure_logger(cls, logger, config):
        """配置日志"""
        pass


# 全局日志代理
_log_broker: Optional[LogBroker] = None


def get_log_broker() -> LogBroker:
    """获取日志代理"""
    global _log_broker
    if _log_broker is None:
        _log_broker = LogBroker()
    return _log_broker


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger


__all__ = ["LogBroker", "LogManager", "get_log_broker", "get_logger"]
