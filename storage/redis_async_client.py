"""
统一异步Redis客户端

弥娅系统的统一Redis异步接口，支持String、Hash、List、Set、Pub/Sub等操作。
提供自动回退到模拟模式的能力，并支持统计和监控。
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncIterator, Union
from datetime import datetime

from core.constants import NetworkTimeout, DatabaseConfig


logger = logging.getLogger(__name__)


@dataclass
class RedisStats:
    """Redis统计信息"""
    total_operations: int = 0
    success_operations: int = 0
    failed_operations: int = 0
    hits: int = 0
    misses: int = 0
    last_operation_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_operations == 0:
            return 0.0
        return self.success_operations / self.total_operations

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total_lookups = self.hits + self.misses
        if total_lookups == 0:
            return 0.0
        return self.hits / total_lookups


@dataclass
class RedisConfig:
    """Redis配置"""
    host: str = "localhost"
    port: int = DatabaseConfig.REDIS_DEFAULT_PORT
    db: int = DatabaseConfig.REDIS_DEFAULT_DB
    password: Optional[str] = None
    use_mock: bool = False
    socket_connect_timeout: int = NetworkTimeout.REDIS_CONNECT_TIMEOUT
    socket_timeout: int = NetworkTimeout.REDIS_CONNECT_TIMEOUT
    max_connections: int = 10


class MockRedisAsyncClient:
    """模拟Redis异步客户端（回退模式）"""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}
        self._stats = RedisStats()

    @property
    def is_mock(self) -> bool:
        return True

    @property
    def stats(self) -> RedisStats:
        return self._stats

    async def connect(self) -> bool:
        logger.info("MockRedis连接成功（模拟模式）")
        return True

    async def disconnect(self) -> None:
        self._data.clear()
        self._expires.clear()

    def _check_expire(self, key: str) -> bool:
        """检查是否过期"""
        if key in self._expires:
            if datetime.now().timestamp() > self._expires[key]:
                del self._data[key]
                del self._expires[key]
                return False
        return True

    async def get(self, key: str) -> Optional[Any]:
        """获取值"""
        self._stats.total_operations += 1
        self._stats.last_operation_time = datetime.now()
        if not self._check_expire(key):
            self._stats.misses += 1
            return None
        if key in self._data:
            self._stats.hits += 1
            self._stats.success_operations += 1
            return self._data[key]
        self._stats.misses += 1
        self._stats.success_operations += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置值"""
        self._stats.total_operations += 1
        self._stats.last_operation_time = datetime.now()
        try:
            self._data[key] = value
            if ttl:
                self._expires[key] = datetime.now().timestamp() + ttl
            self._stats.success_operations += 1
            return True
        except Exception as e:
            logger.error(f"MockRedis设置失败: {e}")
            self._stats.failed_operations += 1
            return False

    async def delete(self, key: str) -> bool:
        """删除键"""
        self._stats.total_operations += 1
        self._stats.last_operation_time = datetime.now()
        try:
            if key in self._data:
                del self._data[key]
            if key in self._expires:
                del self._expires[key]
            self._stats.success_operations += 1
            return True
        except Exception as e:
            logger.error(f"MockRedis删除失败: {e}")
            self._stats.failed_operations += 1
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        self._stats.total_operations += 1
        return self._check_expire(key) and key in self._data

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        if not self._check_expire(key) or key not in self._data:
            return False
        self._expires[key] = datetime.now().timestamp() + ttl
        return True

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有匹配的键"""
        import fnmatch
        return [k for k in self._data.keys() if self._check_expire(k) and fnmatch.fnmatch(k, pattern)]

    async def flushdb(self) -> bool:
        """清空数据库"""
        self._data.clear()
        self._expires.clear()
        return True

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_operations": self._stats.total_operations,
            "success_operations": self._stats.success_operations,
            "failed_operations": self._stats.failed_operations,
            "success_rate": self._stats.success_rate,
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": self._stats.hit_rate,
            "last_operation_time": self._stats.last_operation_time,
            "is_mock": True
        }

    # Hash操作
    async def hset(self, name: str, key: str, value: Any) -> bool:
        """设置hash字段"""
        self._stats.total_operations += 1
        try:
            hash_key = f"hash:{name}"
            if hash_key not in self._data:
                self._data[hash_key] = {}
            self._data[hash_key][key] = value
            self._stats.success_operations += 1
            return True
        except Exception as e:
            logger.error(f"MockRedis hset失败: {e}")
            self._stats.failed_operations += 1
            return False

    async def hget(self, name: str, key: str) -> Optional[Any]:
        """获取hash字段"""
        self._stats.total_operations += 1
        hash_key = f"hash:{name}"
        if hash_key in self._data and key in self._data[hash_key]:
            self._stats.hits += 1
            self._stats.success_operations += 1
            return self._data[hash_key][key]
        self._stats.misses += 1
        self._stats.success_operations += 1
        return None

    async def hgetall(self, name: str) -> Dict[str, Any]:
        """获取所有hash字段"""
        self._stats.total_operations += 1
        hash_key = f"hash:{name}"
        if hash_key in self._data:
            self._stats.success_operations += 1
            return self._data[hash_key].copy()
        self._stats.success_operations += 1
        return {}

    # List操作
    async def lpush(self, name: str, *values: Any) -> int:
        """从左侧推入列表"""
        self._stats.total_operations += 1
        try:
            list_key = f"list:{name}"
            if list_key not in self._data:
                self._data[list_key] = []
            self._data[list_key] = list(values) + self._data[list_key]
            self._stats.success_operations += 1
            return len(self._data[list_key])
        except Exception as e:
            logger.error(f"MockRedis lpush失败: {e}")
            self._stats.failed_operations += 1
            return 0

    async def lpop(self, name: str) -> Optional[Any]:
        """从左侧弹出列表"""
        self._stats.total_operations += 1
        try:
            list_key = f"list:{name}"
            if list_key in self._data and self._data[list_key]:
                value = self._data[list_key].pop(0)
                self._stats.success_operations += 1
                return value
            self._stats.success_operations += 1
            return None
        except Exception as e:
            logger.error(f"MockRedis lpop失败: {e}")
            self._stats.failed_operations += 1
            return None

    async def lrange(self, name: str, start: int, end: int) -> List[Any]:
        """获取列表范围"""
        self._stats.total_operations += 1
        try:
            list_key = f"list:{name}"
            if list_key in self._data:
                self._stats.success_operations += 1
                return self._data[list_key][start:end + 1]
            self._stats.success_operations += 1
            return []
        except Exception as e:
            logger.error(f"MockRedis lrange失败: {e}")
            self._stats.failed_operations += 1
            return []

    # Pub/Sub操作
    async def publish(self, channel: str, message: Any) -> int:
        """发布消息"""
        logger.info(f"[MockPub] 发布到频道 {channel}: {message}")
        self._stats.total_operations += 1
        self._stats.success_operations += 1
        return 0

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        """订阅频道"""
        logger.info(f"[MockPub] 订阅频道 {channel}")
        yield None


class RedisAsyncClient:
    """统一异步Redis客户端"""

    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or RedisConfig()
        self._client: Optional[Any] = None
        self._mock_client: Optional[MockRedisAsyncClient] = None
        self._connected: bool = False
        self._lock = asyncio.Lock()

    @property
    def is_mock(self) -> bool:
        """是否为模拟模式"""
        return self._mock_client is not None

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    async def connect(self) -> bool:
        """连接Redis"""
        async with self._lock:
            if self._connected:
                return True

            if self.config.use_mock:
                self._mock_client = MockRedisAsyncClient()
                success = await self._mock_client.connect()
                self._connected = success
                return success

            try:
                import redis.asyncio as redis
                self._client = await redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    socket_timeout=self.config.socket_timeout,
                    decode_responses=True
                )
                await self._client.ping()
                self._connected = True
                logger.info(f"Redis连接成功: {self.config.host}:{self.config.port}/{self.config.db}")
                return True
            except Exception as e:
                logger.warning(f"Redis连接失败，切换到模拟模式: {e}")
                self._mock_client = MockRedisAsyncClient()
                success = await self._mock_client.connect()
                self._connected = success
                return success

    async def disconnect(self) -> None:
        """断开连接"""
        async with self._lock:
            if not self._connected:
                return

            if self._client:
                await self._client.aclose()
                self._client = None

            if self._mock_client:
                await self._mock_client.disconnect()
                self._mock_client = None

            self._connected = False
            logger.info("Redis已断开连接")

    # String操作
    async def get(self, key: str) -> Optional[Any]:
        """获取值"""
        if self.is_mock:
            return await self._mock_client.get(key)

        try:
            value = await self._client.get(key)
            if value:
                # 尝试解析JSON
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis get失败: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置值"""
        if self.is_mock:
            return await self._mock_client.set(key, value, ttl)

        try:
            # 序列化复杂类型
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)

            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis set失败: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除键"""
        if self.is_mock:
            return await self._mock_client.delete(key)

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete失败: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if self.is_mock:
            return await self._mock_client.exists(key)

        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists失败: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        if self.is_mock:
            return await self._mock_client.expire(key, ttl)

        try:
            await self._client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Redis expire失败: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有匹配的键"""
        if self.is_mock:
            return await self._mock_client.keys(pattern)

        try:
            return await self._client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys失败: {e}")
            return []

    async def flushdb(self) -> bool:
        """清空数据库"""
        if self.is_mock:
            return await self._mock_client.flushdb()

        try:
            await self._client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Redis flushdb失败: {e}")
            return False

    # Hash操作
    async def hset(self, name: str, key: str, value: Any) -> bool:
        """设置hash字段"""
        if self.is_mock:
            return await self._mock_client.hset(name, key, value)

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            await self._client.hset(name, key, value)
            return True
        except Exception as e:
            logger.error(f"Redis hset失败: {e}")
            return False

    async def hget(self, name: str, key: str) -> Optional[Any]:
        """获取hash字段"""
        if self.is_mock:
            return await self._mock_client.hget(name, key)

        try:
            value = await self._client.hget(name, key)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis hget失败: {e}")
            return None

    async def hgetall(self, name: str) -> Dict[str, Any]:
        """获取所有hash字段"""
        if self.is_mock:
            return await self._mock_client.hgetall(name)

        try:
            data = await self._client.hgetall(name)
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except:
                    result[k] = v
            return result
        except Exception as e:
            logger.error(f"Redis hgetall失败: {e}")
            return {}

    # List操作
    async def lpush(self, name: str, *values: Any) -> int:
        """从左侧推入列表"""
        if self.is_mock:
            return await self._mock_client.lpush(name, *values)

        try:
            serialized_values = []
            for v in values:
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                serialized_values.append(v)
            return await self._client.lpush(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis lpush失败: {e}")
            return 0

    async def lpop(self, name: str) -> Optional[Any]:
        """从左侧弹出列表"""
        if self.is_mock:
            return await self._mock_client.lpop(name)

        try:
            value = await self._client.lpop(name)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis lpop失败: {e}")
            return None

    async def lrange(self, name: str, start: int, end: int) -> List[Any]:
        """获取列表范围"""
        if self.is_mock:
            return await self._mock_client.lrange(name, start, end)

        try:
            values = await self._client.lrange(name, start, end)
            result = []
            for v in values:
                try:
                    result.append(json.loads(v))
                except:
                    result.append(v)
            return result
        except Exception as e:
            logger.error(f"Redis lrange失败: {e}")
            return []

    # Pub/Sub操作
    async def publish(self, channel: str, message: Any) -> int:
        """发布消息"""
        if self.is_mock:
            return await self._mock_client.publish(channel, message)

        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, ensure_ascii=False)
            return await self._client.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis publish失败: {e}")
            return 0

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        """订阅频道"""
        if self.is_mock:
            async for msg in self._mock_client.subscribe(channel):
                yield msg
            return

        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)
            async for msg in pubsub.listen():
                if msg['type'] == 'message':
                    try:
                        data = json.loads(msg['data'])
                    except:
                        data = msg['data']
                    yield data
        except Exception as e:
            logger.error(f"Redis subscribe失败: {e}")
            yield None

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self.is_mock:
            return await self._mock_client.get_stats()

        return {
            "is_mock": False,
            "is_connected": self._connected,
            "host": self.config.host,
            "port": self.config.port,
            "db": self.config.db
        }
