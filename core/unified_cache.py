"""
统一缓存管理系统

弥娅系统的统一缓存层，支持内存缓存、向量缓存、查询缓存、去重缓存。
提供TTL过期、LRU驱逐、持久化、异步/同步双模式支持。
"""
import asyncio
import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.constants import CacheTTL, Encoding


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    ttl: Optional[float] = None
    access_count: int = 0
    last_access: float = 0.0
    size: int = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)

    def touch(self):
        """更新访问时间和计数"""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 1000
    default_ttl: float = CacheTTL.MEDIUM
    max_memory_mb: float = 100.0
    enable_stats: bool = True
    enable_persist: bool = False
    persist_dir: str = "data/cache"
    async_mode: bool = True
    cleanup_interval: float = 60.0


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    sets: int = 0
    deletes: int = 0
    total_memory: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def reset(self):
        """重置统计"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.sets = 0
        self.deletes = 0
        self.total_memory = 0


class BaseCacheLayer(ABC):
    """基础缓存层（抽象类）"""

    def __init__(self, name: str, config: Optional[CacheConfig] = None):
        self.name = name
        self.config = config or CacheConfig()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()

        # 并发控制
        if self.config.async_mode:
            self._lock = asyncio.Lock()
        else:
            self._lock = threading.Lock()

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"缓存层初始化: {name}")

    def _generate_key(self, key: str) -> str:
        """生成缓存键"""
        return f"{self.name}:{key}"

    def _estimate_size(self, value: Any) -> int:
        """估算值的大小"""
        try:
            return len(json.dumps(value, ensure_ascii=False))
        except:
            return len(str(value))

    def _check_ttl(self, entry: CacheEntry) -> bool:
        """检查TTL是否过期"""
        if entry.is_expired():
            return False
        return True

    def _evict_lru(self, count: int = 1) -> int:
        """LRU驱逐"""
        evicted = 0
        keys_to_remove = []

        # 找出最少使用的条目
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_access
        )

        for key, entry in sorted_entries[:count]:
            if not entry.is_expired():
                keys_to_remove.append(key)

        # 移除条目
        for key in keys_to_remove:
            entry = self._cache.pop(key, None)
            if entry:
                self._stats.total_memory -= entry.size
                self._stats.evictions += 1
                evicted += 1

        if evicted > 0:
            logger.debug(f"LRU驱逐了 {evicted} 个缓存条目")

        return evicted

    def _evict_expired(self) -> int:
        """驱逐过期条目"""
        evicted = 0
        keys_to_remove = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]

        for key in keys_to_remove:
            entry = self._cache.pop(key, None)
            if entry:
                self._stats.total_memory -= entry.size
                self._stats.evictions += 1
                evicted += 1

        if evicted > 0:
            logger.debug(f"驱逐了 {evicted} 个过期缓存条目")

        return evicted

    def _check_memory_limit(self) -> None:
        """检查内存限制"""
        max_bytes = self.config.max_memory_mb * 1024 * 1024
        while self._stats.total_memory > max_bytes:
            self._evict_lru()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值（异步/自适应）"""
        cache_key = self._generate_key(key)

        if self.config.async_mode:
            async with self._lock:
                # 同步操作，但在async上下文中执行
                return self._get_sync(cache_key)
        else:
            return self._get_sync(cache_key)

    def _get_sync(self, cache_key: str) -> Optional[Any]:
        """同步获取"""
        entry = self._cache.get(cache_key)
        if entry is None:
            self._stats.misses += 1
            return None

        # 检查TTL
        if not self._check_ttl(entry):
            self._cache.pop(cache_key, None)
            self._stats.misses += 1
            return None

        # 更新访问
        entry.touch()
        self._stats.hits += 1

        # 移动到末尾（标记为最近使用）
        self._cache.move_to_end(cache_key)

        return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """设置缓存值（异步/自适应）"""
        cache_key = self._generate_key(key)

        if self.config.async_mode:
            async with self._lock:
                # 同步操作，但在async上下文中执行
                return self._set_sync(cache_key, value, ttl)
        else:
            return self._set_sync(cache_key, value, ttl)

    def _set_sync(self, cache_key: str, value: Any, ttl: Optional[float]) -> bool:
        """同步设置"""
        # 计算大小
        size = self._estimate_size(value)

        # 检查内存限制
        if self._stats.total_memory + size > self.config.max_memory_mb * 1024 * 1024:
            self._evict_lru()

        # 检查数量限制
        while len(self._cache) >= self.config.max_size:
            self._evict_lru()

        # 设置TTL
        if ttl is None:
            ttl = self.config.default_ttl

        # 创建条目
        entry = CacheEntry(
            key=cache_key,
            value=value,
            created_at=time.time(),
            ttl=ttl,
            size=size
        )

        # 如果已存在，移除旧值的大小
        old_entry = self._cache.get(cache_key)
        if old_entry:
            self._stats.total_memory -= old_entry.size

        # 添加新条目
        self._cache[cache_key] = entry
        self._cache.move_to_end(cache_key)
        self._stats.total_memory += size
        self._stats.sets += 1

        return True

    async def delete(self, key: str) -> bool:
        """删除缓存值（异步/自适应）"""
        cache_key = self._generate_key(key)

        if self.config.async_mode:
            async with self._lock:
                # 同步操作，但在async上下文中执行
                return self._delete_sync(cache_key)
        else:
            return self._delete_sync(cache_key)

    def _delete_sync(self, cache_key: str) -> bool:
        """同步删除"""
        entry = self._cache.pop(cache_key, None)
        if entry:
            self._stats.total_memory -= entry.size
            self._stats.deletes += 1
            return True
        return False

    async def clear(self) -> None:
        """清空缓存（异步/自适应）"""
        if self.config.async_mode:
            async with self._lock:
                self._cache.clear()
        else:
            self._cache.clear()

        self._stats.total_memory = 0
        logger.info(f"缓存已清空: {self.name}")

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有键（异步/自适应）"""
        import fnmatch

        if self.config.async_mode:
            async with self._lock:
                return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
        else:
            return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "size": len(self._cache),
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": self._stats.hit_rate,
            "evictions": self._stats.evictions,
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "total_memory": self._stats.total_memory,
            "max_size": self.config.max_size,
            "max_memory_mb": self.config.max_memory_mb,
        }

    async def cleanup(self) -> int:
        """清理过期条目"""
        if self.config.async_mode:
            async with self._lock:
                return self._evict_expired()
        else:
            return self._evict_expired()

    async def start_cleanup_task(self) -> None:
        """启动定期清理任务"""
        if self._cleanup_task and not self._cleanup_task.done():
            return

        async def _cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval)
                    await self.cleanup()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"缓存清理任务失败: {e}")

        self._cleanup_task = asyncio.create_task(_cleanup_loop())
        logger.info(f"缓存清理任务已启动: {self.name}")

    async def stop_cleanup_task(self) -> None:
        """停止清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info(f"缓存清理任务已停止: {self.name}")

    async def persist(self) -> bool:
        """持久化缓存（可选）"""
        if not self.config.enable_persist:
            return False

        try:
            persist_dir = Path(self.config.persist_dir)
            persist_dir.mkdir(parents=True, exist_ok=True)

            persist_file = persist_dir / f"{self.name}.json"

            data = {
                "cache": {
                    key: {
                        "value": entry.value,
                        "created_at": entry.created_at,
                        "ttl": entry.ttl,
                        "size": entry.size,
                    }
                    for key, entry in self._cache.items()
                },
                "stats": {
                    "hits": self._stats.hits,
                    "misses": self._stats.misses,
                    "evictions": self._stats.evictions,
                    "sets": self._stats.sets,
                    "deletes": self._stats.deletes,
                }
            }

            with open(persist_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"缓存已持久化: {persist_file}")
            return True

        except Exception as e:
            logger.error(f"缓存持久化失败: {e}")
            return False

    async def load(self) -> bool:
        """从持久化加载缓存（可选）"""
        if not self.config.enable_persist:
            return False

        try:
            persist_dir = Path(self.config.persist_dir)
            persist_file = persist_dir / f"{self.name}.json"

            if not persist_file.exists():
                return False

            with open(persist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 加载缓存
            for key, entry_data in data["cache"].items():
                entry = CacheEntry(
                    key=key,
                    value=entry_data["value"],
                    created_at=entry_data["created_at"],
                    ttl=entry_data["ttl"],
                    size=entry_data["size"],
                )
                self._cache[key] = entry

            # 加载统计
            stats = data["stats"]
            self._stats.hits = stats.get("hits", 0)
            self._stats.misses = stats.get("misses", 0)
            self._stats.evictions = stats.get("evictions", 0)
            self._stats.sets = stats.get("sets", 0)
            self._stats.deletes = stats.get("deletes", 0)

            # 计算总内存
            self._stats.total_memory = sum(e.size for e in self._cache.values())

            logger.info(f"缓存已加载: {persist_file}")
            return True

        except Exception as e:
            logger.error(f"缓存加载失败: {e}")
            return False


def cached(cache_type: str = "memory", ttl: Optional[float] = None, key_prefix: str = ""):
    """统一缓存装饰器

    Args:
        cache_type: 缓存类型
        ttl: 过期时间（秒）
        key_prefix: 键前缀

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = _generate_cache_key(func.__name__, args, kwargs, key_prefix)

            # 尝试从缓存获取
            cached_value = await unified_cache_get(cache_type, cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            await unified_cache_set(cache_type, cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本（简化处理）
            return func(*args, **kwargs)

        # 返回适当版本
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _generate_cache_key(func_name: str, args: Tuple, kwargs: Dict, prefix: str) -> str:
    """生成缓存键"""
    # 创建键字符串
    key_parts = [prefix, func_name]

    # 添加参数
    if args:
        key_parts.extend(str(arg) for arg in args)

    if kwargs:
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

    key_str = ":".join(key_parts)

    # 生成哈希
    return hashlib.md5(key_str.encode()).hexdigest()


# 全局缓存实例
_caches: Dict[str, BaseCacheLayer] = {}
_caches_lock = threading.Lock()


def get_cache(name: str, config: Optional[CacheConfig] = None) -> BaseCacheLayer:
    """获取或创建缓存实例"""
    with _caches_lock:
        if name not in _caches:
            _caches[name] = BaseCacheLayer(name, config)
        return _caches[name]


async def unified_cache_get(cache_type: str, key: str) -> Optional[Any]:
    """统一缓存获取"""
    cache = get_cache(cache_type)
    return await cache.get(key)


async def unified_cache_set(cache_type: str, key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """统一缓存设置"""
    cache = get_cache(cache_type)
    return await cache.set(key, value, ttl)


async def unified_cache_delete(cache_type: str, key: str) -> bool:
    """统一缓存删除"""
    cache = get_cache(cache_type)
    return await cache.delete(key)


async def unified_cache_clear(cache_type: str) -> None:
    """统一缓存清空"""
    cache = get_cache(cache_type)
    await cache.clear()


async def cleanup_all_caches() -> None:
    """清理所有缓存的过期条目"""
    with _caches_lock:
        for cache in _caches.values():
            await cache.cleanup()
