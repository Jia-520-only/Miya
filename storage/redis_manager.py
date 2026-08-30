"""
Redis统一管理器

提供全局唯一的Redis客户端实例，支持单例模式和配置管理。
"""
import asyncio
import logging
from typing import Optional
from .redis_async_client import RedisAsyncClient, RedisConfig


logger = logging.getLogger(__name__)


class RedisManager:
    """Redis统一管理器（单例模式）"""

    _instance: Optional['RedisManager'] = None
    _lock = asyncio.Lock()
    _client: Optional[RedisAsyncClient] = None
    _config: Optional[RedisConfig] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self, config: Optional[RedisConfig] = None) -> bool:
        """初始化Redis连接

        Args:
            config: Redis配置，如果为None则使用默认配置

        Returns:
            是否连接成功
        """
        async with self._lock:
            if self._client and self._client.is_connected:
                logger.info("Redis已连接，跳过初始化")
                return True

            self._config = config or RedisConfig()
            self._client = RedisAsyncClient(self._config)
            success = await self._client.connect()

            if success:
                logger.info("Redis管理器初始化成功")
            else:
                logger.error("Redis管理器初始化失败")

            return success

    async def get_client(self) -> RedisAsyncClient:
        """获取Redis客户端实例

        Returns:
            Redis异步客户端

        Raises:
            RuntimeError: 如果Redis未初始化
        """
        if self._client is None:
            raise RuntimeError("Redis管理器未初始化，请先调用initialize()方法")

        if not self._client.is_connected:
            await self._client.connect()

        return self._client

    async def close(self) -> None:
        """关闭Redis连接"""
        async with self._lock:
            if self._client:
                await self._client.disconnect()
                self._client = None
                self._config = None
                logger.info("Redis管理器已关闭")

    def reset(self) -> None:
        """重置管理器（用于测试）"""
        self._client = None
        self._config = None
        logger.info("Redis管理器已重置")

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._client is not None

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._client is not None and self._client.is_connected


# 全局单例实例
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    """获取Redis管理器单例

    Returns:
        Redis管理器实例
    """
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


async def get_redis_client() -> RedisAsyncClient:
    """获取Redis客户端（便捷方法）

    Returns:
        Redis异步客户端

    Raises:
        RuntimeError: 如果Redis未初始化
    """
    manager = get_redis_manager()
    return await manager.get_client()


async def initialize_redis(config: Optional[RedisConfig] = None) -> bool:
    """初始化Redis（便捷方法）

    Args:
        config: Redis配置

    Returns:
        是否初始化成功
    """
    manager = get_redis_manager()
    return await manager.initialize(config)


async def close_redis() -> None:
    """关闭Redis连接（便捷方法）"""
    manager = get_redis_manager()
    await manager.close()


def reset_redis() -> None:
    """重置Redis管理器（便捷方法，用于测试）"""
    manager = get_redis_manager()
    manager.reset()
