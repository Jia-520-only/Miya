"""
Redis客户端 - 内存/涨潮记忆
管理短期高访问数据
支持真实Redis连接和模拟回退模式
"""
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta
import logging
from core.constants import NetworkTimeout

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端 - 支持真实连接和模拟回退"""

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 db: int = 0, password: str = None, use_mock: bool = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._redis = None
        self._use_mock = use_mock

        # 模拟内存存储（回退模式）
        self._memory = {}
        self._expires = {}

        # 尝试连接真实Redis
        if not self._use_mock:
            self._connect_real()

    def _connect_real(self) -> bool:
        """尝试连接真实Redis"""
        try:
            import redis
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT,
                socket_timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT
            )
            # 测试连接
            self._redis.ping()
            logger.info(f"✅ 已连接到真实Redis: {self.host}:{self.port}")
            self._use_mock = False
            return True
        except ImportError:
            logger.warning("⚠️ redis包未安装，使用模拟模式")
            self._use_mock = True
            return False
        except Exception as e:
            logger.warning(f"⚠️ Redis连接失败: {e}，使用模拟模式")
            self._use_mock = True
            return False

    def is_mock_mode(self) -> bool:
        """是否为模拟模式"""
        return self._use_mock

    def connect(self) -> bool:
        """连接Redis"""
        if self._use_mock:
            return True
        if self._redis:
            try:
                self._redis.ping()
                return True
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                return False
        return self._connect_real()

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        设置键值

        Args:
            key: 键
            value: 值
            ttl: 过期时间（秒）
        """
        if self._use_mock:
            return self._set_mock(key, value, ttl)

        try:
            # 序列化值
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value, ensure_ascii=False)

            if ttl:
                return self._redis.setex(key, ttl, value)
            else:
                return self._redis.set(key, value)
        except Exception as e:
            logger.error(f"Redis set失败: {e}")
            return self._set_mock(key, value, ttl)

    def _set_mock(self, key: str, value: Any, ttl: int = None) -> bool:
        """模拟设置键值"""
        # 序列化值
        if not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value, ensure_ascii=False)

        self._memory[key] = value

        # 设置过期时间
        if ttl:
            self._expires[key] = datetime.now() + timedelta(seconds=ttl)

        return True

    def get(self, key: str) -> Optional[Any]:
        """获取值"""
        if self._use_mock:
            return self._get_mock(key)

        try:
            value = self._redis.get(key)
            if value is None:
                return None

            # 尝试反序列化
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis get失败: {e}")
            return self._get_mock(key)

    def _get_mock(self, key: str) -> Optional[Any]:
        """模拟获取值"""
        # 检查是否过期
        if key in self._expires and datetime.now() > self._expires[key]:
            del self._memory[key]
            del self._expires[key]
            return None

        value = self._memory.get(key)

        # 尝试反序列化
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return value

        return value

    def delete(self, key: str) -> bool:
        """删除键"""
        if self._use_mock:
            return self._delete_mock(key)

        try:
            return bool(self._redis.delete(key))
        except Exception as e:
            logger.error(f"Redis delete失败: {e}")
            return self._delete_mock(key)

    def _delete_mock(self, key: str) -> bool:
        """模拟删除键"""
        if key in self._memory:
            del self._memory[key]
        if key in self._expires:
            del self._expires[key]
        return True

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if self._use_mock:
            return self._exists_mock(key)

        try:
            return bool(self._redis.exists(key))
        except Exception as e:
            logger.error(f"Redis exists失败: {e}")
            return self._exists_mock(key)

    def _exists_mock(self, key: str) -> bool:
        """模拟检查键是否存在"""
        # 检查是否过期
        if key in self._expires and datetime.now() > self._expires[key]:
            del self._memory[key]
            del self._expires[key]
            return False

        return key in self._memory

    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        if self._use_mock:
            return self._expire_mock(key, ttl)

        try:
            return bool(self._redis.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis expire失败: {e}")
            return self._expire_mock(key, ttl)

    def _expire_mock(self, key: str, ttl: int) -> bool:
        """模拟设置过期时间"""
        if key not in self._memory:
            return False

        self._expires[key] = datetime.now() + timedelta(seconds=ttl)
        return True

    def hset(self, name: str, key: str, value: Any) -> bool:
        """哈希表设置"""
        if self._use_mock:
            return self._hset_mock(name, key, value)

        try:
            # 序列化复杂类型
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value, ensure_ascii=False)
            return bool(self._redis.hset(name, key, value))
        except Exception as e:
            logger.error(f"Redis hset失败: {e}")
            return self._hset_mock(name, key, value)

    def _hset_mock(self, name: str, key: str, value: Any) -> bool:
        """模拟哈希表设置"""
        if name not in self._memory:
            self._memory[name] = {}

        if not isinstance(self._memory[name], dict):
            self._memory[name] = {}

        self._memory[name][key] = value
        return True

    def hget(self, name: str, key: str) -> Optional[Any]:
        """哈希表获取"""
        if self._use_mock:
            return self._hget_mock(name, key)

        try:
            value = self._redis.hget(name, key)
            if value is None:
                return None

            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis hget失败: {e}")
            return self._hget_mock(name, key)

    def _hget_mock(self, name: str, key: str) -> Optional[Any]:
        """模拟哈希表获取"""
        if name not in self._memory or not isinstance(self._memory[name], dict):
            return None

        return self._memory[name].get(key)

    def hgetall(self, name: str) -> Dict:
        """获取整个哈希表"""
        if self._use_mock:
            return self._hgetall_mock(name)

        try:
            data = self._redis.hgetall(name)
            # 尝试反序列化所有值
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except:
                    result[k] = v
            return result
        except Exception as e:
            logger.error(f"Redis hgetall失败: {e}")
            return self._hgetall_mock(name)

    def _hgetall_mock(self, name: str) -> Dict:
        """模拟获取整个哈希表"""
        if name not in self._memory or not isinstance(self._memory[name], dict):
            return {}

        return self._memory[name].copy()

    def lpush(self, name: str, *values: Any) -> int:
        """列表左侧插入"""
        if self._use_mock:
            return self._lpush_mock(name, *values)

        try:
            # 序列化复杂类型
            serialized_values = []
            for v in values:
                if not isinstance(v, (str, int, float, bool)):
                    serialized_values.append(json.dumps(v, ensure_ascii=False))
                else:
                    serialized_values.append(v)
            return self._redis.lpush(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis lpush失败: {e}")
            return self._lpush_mock(name, *values)

    def _lpush_mock(self, name: str, *values: Any) -> int:
        """模拟列表左侧插入"""
        if name not in self._memory:
            self._memory[name] = []

        if not isinstance(self._memory[name], list):
            self._memory[name] = []

        for value in reversed(values):
            self._memory[name].insert(0, value)

        return len(self._memory[name])

    def lpop(self, name: str) -> Optional[Any]:
        """列表左侧弹出"""
        if self._use_mock:
            return self._lpop_mock(name)

        try:
            value = self._redis.lpop(name)
            if value is None:
                return None

            try:
                return json.loads(value)
            except:
                return value
        except Exception as e:
            logger.error(f"Redis lpop失败: {e}")
            return self._lpop_mock(name)

    def _lpop_mock(self, name: str) -> Optional[Any]:
        """模拟列表左侧弹出"""
        if name not in self._memory or not isinstance(self._memory[name], list):
            return None

        if not self._memory[name]:
            return None

        return self._memory[name].pop(0)

    def lrange(self, name: str, start: int, end: int) -> List[Any]:
        """列表范围获取"""
        if self._use_mock:
            return self._lrange_mock(name, start, end)

        try:
            values = self._redis.lrange(name, start, end)
            # 反序列化
            result = []
            for v in values:
                try:
                    result.append(json.loads(v))
                except:
                    result.append(v)
            return result
        except Exception as e:
            logger.error(f"Redis lrange失败: {e}")
            return self._lrange_mock(name, start, end)

    def _lrange_mock(self, name: str, start: int, end: int) -> List[Any]:
        """模拟列表范围获取"""
        if name not in self._memory or not isinstance(self._memory[name], list):
            return []

        lst = self._memory[name]
        return lst[start:end+1] if end >= 0 else lst[start:]

    def keys(self, pattern: str = '*') -> List[str]:
        """获取匹配的键"""
        if self._use_mock:
            return self._keys_mock(pattern)

        try:
            return list(self._redis.keys(pattern))
        except Exception as e:
            logger.error(f"Redis keys失败: {e}")
            return self._keys_mock(pattern)

    def _keys_mock(self, pattern: str = '*') -> List[str]:
        """模拟获取匹配的键"""
        import fnmatch

        all_keys = list(self._memory.keys())
        if pattern == '*':
            return all_keys

        return [key for key in all_keys if fnmatch.fnmatch(key, pattern)]

    def flushdb(self) -> bool:
        """清空数据库"""
        if self._use_mock:
            return self._flushdb_mock()

        try:
            self._redis.flushdb()
            return True
        except Exception as e:
            logger.error(f"Redis flushdb失败: {e}")
            return self._flushdb_mock()

    def _flushdb_mock(self) -> bool:
        """模拟清空数据库"""
        self._memory.clear()
        self._expires.clear()
        return True

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if self._use_mock:
            return self._get_stats_mock()

        try:
            info = self._redis.info()
            return {
                'mode': 'real',
                'keys_count': info.get('db0', {}).get('keys', 0),
                'memory_usage': info.get('used_memory_human', '0B'),
                'connected_clients': info.get('connected_clients', 0)
            }
        except Exception as e:
            logger.error(f"Redis get_stats失败: {e}")
            return self._get_stats_mock()

    def _get_stats_mock(self) -> Dict:
        """获取模拟统计信息"""
        # 清理过期键
        self._cleanup_expired()

        return {
            'mode': 'mock',
            'keys_count': len(self._memory),
            'expires_count': len(self._expires),
            'memory_usage': len(str(self._memory))  # 简化
        }

    def _cleanup_expired(self) -> None:
        """清理过期键"""
        now = datetime.now()
        expired_keys = [
            key for key, expiry in self._expires.items()
            if expiry < now
        ]

        for key in expired_keys:
            if key in self._memory:
                del self._memory[key]
            del self._expires[key]

    def close(self) -> None:
        """关闭连接"""
        if self._redis:
            try:
                self._redis.close()
                logger.info("Redis连接已关闭")
            except Exception as e:
                logger.error(f"关闭Redis连接失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
