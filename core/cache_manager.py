"""
缓存管理器（已废弃，请使用 core.unified_cache）

⚠️ DEPRECATED: 此模块已废弃，请使用新的统一缓存系统：
    from core.unified_cache import get_cache, unified_cache_get, unified_cache_set
    from core.cache_adapter import CacheManagerAdapter  # 适配器提供兼容接口

    # 使用统一缓存
    from core.unified_cache import cached
    @cached(cache_type='memory', ttl=60)
    async def my_function():
        ...

保留此文件仅作为兼容性参考，建议迁移到新的统一接口。
"""
import asyncio
import logging
import hashlib
import json
from typing import Any, Dict, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from functools import wraps


logger = logging.getLogger(__name__)


@dataclass
class CacheItem:
    """缓存项"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_access: Optional[datetime] = None


class CacheManager:
    """
    缓存管理器

    功能：
    - 基于时间的过期策略
    - LRU (Least Recently Used) 淘汰策略
    - 内存使用限制
    - 缓存命中率统计
    - 异步缓存操作
    """

    def __init__(
        self,
        default_ttl: float = 3600.0,  # 默认缓存时间（秒）
        max_size: int = 1000,  # 最大缓存条目数
        max_memory_mb: float = 100.0,  # 最大内存使用（MB）
        enable_stats: bool = True
    ):
        """
        初始化缓存管理器

        Args:
            default_ttl: 默认缓存时间（秒）
            max_size: 最大缓存条目数
            max_memory_mb: 最大内存使用（MB）
            enable_stats: 是否启用统计
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.enable_stats = enable_stats

        # 缓存存储
        self._cache: Dict[str, CacheItem] = {}
        self._cache_lock = asyncio.Lock()

        # 统计信息
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_memory_mb': 0.0
        }

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        # 组合函数名和参数
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }

        # 转换为JSON字符串
        key_str = json.dumps(key_data, sort_keys=True, default=str)

        # 生成hash
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def _estimate_size(self, value: Any) -> float:
        """估算值的内存占用（MB）"""
        try:
            size = len(json.dumps(value, default=str))
            return size / (1024 * 1024)  # 转换为MB
        except:
            return 0.0

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在或已过期返回 None
        """
        async with self._cache_lock:
            if key not in self._cache:
                if self.enable_stats:
                    self._stats['misses'] += 1
                return None

            item = self._cache[key]

            # 检查是否过期
            if item.expires_at and datetime.now() > item.expires_at:
                del self._cache[key]
                if self.enable_stats:
                    self._stats['misses'] += 1
                    self._stats['evictions'] += 1
                return None

            # 更新访问统计
            item.access_count += 1
            item.last_access = datetime.now()

            if self.enable_stats:
                self._stats['hits'] += 1

            logger.debug(f"[Cache] 命中缓存: {key}")
            return item.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 缓存时间（秒），None表示使用默认值

        Returns:
            是否设置成功
        """
        async with self._cache_lock:
            # 检查缓存大小
            if len(self._cache) >= self.max_size:
                await self._evict_lru()

            # 检查内存使用
            value_size = self._estimate_size(value)
            if self._stats['total_memory_mb'] + value_size > self.max_memory_mb:
                await self._evict_lru()

            # 计算过期时间
            expires_at = None
            if ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            elif self.default_ttl > 0:
                expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

            # 创建缓存项
            item = CacheItem(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                access_count=1,
                last_access=datetime.now()
            )

            # 设置缓存
            self._cache[key] = item

            # 更新内存统计
            self._stats['total_memory_mb'] += value_size

            logger.debug(f"[Cache] 设置缓存: {key}, TTL: {ttl or self.default_ttl}s")
            return True

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        async with self._cache_lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"[Cache] 删除缓存: {key}")
                return True
            return False

    async def clear(self) -> None:
        """清空所有缓存"""
        async with self._cache_lock:
            self._cache.clear()
            self._stats['total_memory_mb'] = 0.0
            logger.info("[Cache] 缓存已清空")

    async def _evict_lru(self) -> None:
        """淘汰最近最少使用的缓存"""
        if not self._cache:
            return

        # 找到最近最少使用的项
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k].access_count,
                self._cache[k].last_access or datetime.min
            )
        )

        # 删除
        del self._cache[lru_key]
        self._stats['evictions'] += 1

        logger.debug(f"[Cache] LRU淘汰: {lru_key}")

    async def _cleanup_expired(self) -> None:
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []

        async with self._cache_lock:
            for key, item in self._cache.items():
                if item.expires_at and now > item.expires_at:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]
                self._stats['evictions'] += 1

        if expired_keys:
            logger.debug(f"[Cache] 清理过期缓存: {len(expired_keys)} 条")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.enable_stats:
            return {}

        hit_rate = 0.0
        total_requests = self._stats['hits'] + self._stats['misses']
        if total_requests > 0:
            hit_rate = self._stats['hits'] / total_requests

        return {
            **self._stats,
            'cache_size': len(self._cache),
            'max_size': self.max_size,
            'max_memory_mb': self.max_memory_mb,
            'memory_usage_percent': (self._stats['total_memory_mb'] / self.max_memory_mb * 100) if self.max_memory_mb > 0 else 0,
            'hit_rate': hit_rate
        }

    async def start_cleanup_task(self, interval: float = 60.0) -> None:
        """
        启动定期清理任务

        Args:
            interval: 清理间隔（秒）
        """
        if self._running:
            return

        self._running = True

        async def cleanup_loop():
            while self._running:
                await asyncio.sleep(interval)
                await self._cleanup_expired()

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"[Cache] 清理任务已启动 (间隔: {interval}s)")

    async def stop_cleanup_task(self) -> None:
        """停止清理任务"""
        if not self._running:
            return

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("[Cache] 清理任务已停止")


# 全局缓存管理器实例
_global_cache: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache


def cached(ttl: Optional[float] = None, key_prefix: str = ""):
    """
    缓存装饰器

    Args:
        ttl: 缓存时间（秒），None表示使用默认值
        key_prefix: 键前缀

    Usage:
        @cached(ttl=60, key_prefix="user_info")
        async def get_user_info(user_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # 生成缓存键
            cache_key = cache._generate_key(
                f"{key_prefix}:{func.__name__}",
                args[1:],  # 跳过 self
                kwargs
            )

            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 调用原函数
            result = await func(*args, **kwargs)

            # 存入缓存
            await cache.set(cache_key, result, ttl=ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # 生成缓存键
            cache_key = cache._generate_key(
                f"{key_prefix}:{func.__name__}",
                args[1:],  # 跳过 self
                kwargs
            )

            # 尝试从缓存获取
            cached_value = asyncio.run(cache.get(cache_key))
            if cached_value is not None:
                return cached_value

            # 调用原函数
            result = func(*args, **kwargs)

            # 存入缓存
            asyncio.run(cache.set(cache_key, result, ttl=ttl))

            return result

        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
