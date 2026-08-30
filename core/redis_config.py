"""
Redis 配置和客户端管理（已废弃，请使用 storage/redis_manager）

⚠️ DEPRECATED: 此模块已废弃，请使用新的统一Redis管理器：
    from storage import RedisManager, get_redis_client, initialize_redis

    # 初始化
    await initialize_redis(config)

    # 获取客户端
    client = await get_redis_client()
    await client.set("key", "value")
    value = await client.get("key")

保留此文件仅作为兼容性参考，建议迁移到新的统一接口。
"""
import logging
import redis.asyncio as redis
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redis 配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    encoding: str = "utf-8"
    decode_responses: bool = True


class MockRedisClient:
    """模拟 Redis 客户端（用于回退）"""

    def __init__(self):
        self._data = {}

    async def set(self, key: str, value: dict, ex: Optional[int] = None):
        """设置键值"""
        self._data[key] = value
        if ex:
            # 简化处理，忽略 TTL
            pass

    async def get(self, key: str) -> Optional[dict]:
        """获取键值"""
        return self._data.get(key)

    async def keys(self, pattern: str) -> list:
        """获取键列表"""
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    async def delete(self, key: str):
        """删除键"""
        self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self._data

    async def close(self):
        """关闭连接"""
        self._data.clear()

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return True


class RedisClient:
    """Redis 客户端包装器

    特点：
    - 支持自动回退到模拟模式
    - 连接池管理
    - 异步操作
    """

    def __init__(self, config: Optional[RedisConfig] = None, use_mock: bool = False):
        self.config = config or RedisConfig()
        self.use_mock = use_mock
        self._client = None

    async def connect(self) -> bool:
        """连接 Redis"""
        if self.use_mock:
            logger.info("使用模拟 Redis 客户端")
            self._client = MockRedisClient()
            return True

        try:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                encoding=self.config.encoding,
                decode_responses=self.config.decode_responses
            )

            # 测试连接
            await self._client.ping()
            logger.info(f"✅ Redis 连接成功: {self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            logger.warning(f"Redis 连接失败: {e}，使用模拟模式")
            self._client = MockRedisClient()
            return False

    async def disconnect(self):
        """断开连接"""
        if self._client:
            await self._client.close()
            self._client = None

    def __getattr__(self, name):
        """代理所有属性到内部客户端"""
        if self._client is None:
            raise RuntimeError("Redis 客户端未连接")
        return getattr(self._client, name)

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return self._client is None or isinstance(self._client, MockRedisClient)


# 全局单例
_global_redis_client: Optional[RedisClient] = None


async def get_redis_client(
    config: Optional[RedisConfig] = None,
    use_mock: bool = False
) -> RedisClient:
    """获取全局 Redis 客户端（单例）"""
    global _global_redis_client

    if _global_redis_client is None:
        _global_redis_client = RedisClient(config, use_mock)
        await _global_redis_client.connect()

    return _global_redis_client


def reset_redis_client():
    """重置 Redis 客户端（主要用于测试）"""
    global _global_redis_client
    _global_redis_client = None
