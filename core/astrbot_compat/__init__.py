"""
AstrBot 兼容层 - 将 AstrBot API 映射到弥娅接口

这个模块提供 AstrBot 核心接口的兼容实现，使得 *_astrbot 模块
可以逐步从 `from astrbot.core import ...` 迁移到
`from core.astrbot_compat import ...`，最终完全移除 astrbot/ 目录。
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

# 版本信息
VERSION = "4.1.11"

# 日志系统 - 使用 loguru 作为后端
try:
    from loguru import logger as _loguru_logger

    # 创建一个适配器，使 loguru logger 兼容标准 logging 接口
    class LoguruAdapter:
        """将 loguru logger 适配为标准 logging.Logger 接口"""

        def __init__(self, loguru_logger):
            self._logger = loguru_logger

        def debug(self, msg, *args, **kwargs):
            self._logger.debug(msg, *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            self._logger.info(msg, *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            self._logger.warning(msg, *args, **kwargs)

        def warn(self, msg, *args, **kwargs):
            self._logger.warning(msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            self._logger.error(msg, *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            self._logger.critical(msg, *args, **kwargs)

        def exception(self, msg, *args, **kwargs):
            self._logger.exception(msg, *args, **kwargs)

        def bind(self, **kwargs):
            return self._logger.bind(**kwargs)

        def opt(self, **kwargs):
            return self._logger.opt(**kwargs)

    logger = LoguruAdapter(_loguru_logger)

except ImportError:
    # 如果没有 loguru，使用标准 logging
    logger = logging.getLogger("miya")
    logger.setLevel(logging.DEBUG)

    # 添加控制台处理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# 配置管理 - 使用弥娅的配置系统
class AstrBotConfigManager:
    """AstrBot 配置管理器的兼容实现"""

    def __init__(self):
        self._config = {}
        self._config_dir = Path("config")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self._config[key] = value

    def load_config(self, config_path: Optional[str] = None) -> dict:
        """加载配置文件"""
        # 这里可以集成弥娅的配置系统
        return self._config

    @property
    def confs(self) -> dict:
        """兼容 AstrBot 的 confs 属性"""
        return {"default": self._config}


# 全局配置实例
astrbot_config = AstrBotConfigManager()


# 服务提供者 - 简化实现
class ServiceProvider:
    """服务提供者的兼容实现"""

    def __init__(self):
        self._services = {}

    def get(self, service_name: str, default: Any = None) -> Any:
        """获取服务"""
        return self._services.get(service_name, default)

    def register(self, service_name: str, service: Any) -> None:
        """注册服务"""
        self._services[service_name] = service

    def __getattr__(self, name: str) -> Any:
        """属性访问"""
        if name.startswith("_"):
            raise AttributeError(f"ServiceProvider has no attribute '{name}'")
        return self._services.get(name)


# 全局服务提供者实例
sp = ServiceProvider()


# 演示模式标志
DEMO_MODE = False


# 数据库基类 - 简化实现
class BaseDatabase:
    """数据库基类的兼容实现"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

    async def initialize(self) -> None:
        """初始化数据库"""
        pass

    async def close(self) -> None:
        """关闭数据库连接"""
        pass

    async def execute(self, query: str, params: tuple = ()) -> Any:
        """执行 SQL 查询"""
        raise NotImplementedError

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """获取单行结果"""
        raise NotImplementedError

    async def fetchall(self, query: str, params: tuple = ()) -> list:
        """获取所有结果"""
        raise NotImplementedError


# 配置管理器类
class AstrBotConfigManager:
    """AstrBot 配置管理器类的兼容实现"""

    def __init__(self, config_path: str = None):
        self._config_path = config_path
        self._config = {}
        self.confs = {"default": self._config}

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value


# 导出所有兼容接口
__all__ = [
    "VERSION",
    "logger",
    "astrbot_config",
    "sp",
    "DEMO_MODE",
    "BaseDatabase",
    "AstrBotConfigManager",
    "ServiceProvider",
]
