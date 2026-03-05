"""
提示词缓存系统（已废弃，请使用 core.unified_cache）

⚠️ DEPRECATED: 此模块已废弃，请使用新的统一缓存系统：
    from core.unified_cache import get_cache, cached
    from core.cache_adapter import PromptCacheAdapter  # 适配器提供兼容接口

    # 使用统一缓存
    from core.unified_cache import cached
    @cached(cache_type='prompt', ttl=3600)
    def generate_prompt(context):
        ...

保留此文件仅作为兼容性参考，建议迁移到新的统一接口。
"""
import hashlib
import json
import logging
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from threading import Lock
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CachedPrompt:
    """缓存的提示词"""
    key: str
    prompt: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0

    def touch(self):
        """更新访问时间"""
        self.last_accessed = time.time()
        self.access_count += 1


class PromptCache:
    """提示词缓存管理器"""

    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        ttl_seconds: int = 3600
    ):
        """
        初始化提示词缓存

        Args:
            max_size: 最大缓存条目数
            max_memory_mb: 最大内存使用（MB）
            ttl_seconds: 生存时间（秒）
        """
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds

        self._cache: Dict[str, CachedPrompt] = {}
        self._lock = Lock()

        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _generate_key(self, context: Dict[str, Any]) -> str:
        """
        生成缓存键

        Args:
            context: 上下文字典

        Returns:
            缓存键（MD5哈希）
        """
        # 确保字典键的顺序一致
        ordered_context = json.dumps(context, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(ordered_context.encode('utf-8')).hexdigest()

    def get(self, context: Dict[str, Any]) -> Optional[str]:
        """
        从缓存获取提示词

        Args:
            context: 上下文字典

        Returns:
            缓存的提示词，如果不存在或过期则返回None
        """
        key = self._generate_key(context)

        with self._lock:
            cached = self._cache.get(key)

            if cached is None:
                self._misses += 1
                return None

            # 检查是否过期
            age = time.time() - cached.created_at
            if age > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                logger.debug(f"[PromptCache] 缓存过期: {key[:8]}")
                return None

            # 更新访问信息
            cached.touch()
            self._hits += 1
            logger.debug(f"[PromptCache] 缓存命中: {key[:8]} (访问次数: {cached.access_count})")

            return cached.prompt

    def set(self, context: Dict[str, Any], prompt: str) -> None:
        """
        将提示词存入缓存

        Args:
            context: 上下文字典
            prompt: 提示词内容
        """
        key = self._generate_key(context)
        prompt_size = len(prompt.encode('utf-8'))

        # 检查单个条目大小限制
        if prompt_size > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"[PromptCache] 提示词过大，跳过缓存: {prompt_size} bytes")
            return

        with self._lock:
            # 如果已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 检查是否需要清理空间
            self._ensure_space(prompt_size)

            # 添加新缓存
            cached = CachedPrompt(
                key=key,
                prompt=prompt,
                size_bytes=prompt_size
            )
            self._cache[key] = cached

            logger.debug(
                f"[PromptCache] 缓存添加: {key[:8]} "
                f"(大小: {prompt_size} bytes, 总数: {len(self._cache)})"
            )

    def _ensure_space(self, required_bytes: int) -> None:
        """
        确保有足够的空间存储新的缓存项

        Args:
            required_bytes: 需要的空间（字节）
        """
        # 计算当前内存使用
        current_memory = sum(c.size_bytes for c in self._cache.values())
        current_size = len(self._cache)

        # 检查条目数量限制
        if current_size >= self.max_size:
            self._evict_lru(count=current_size - self.max_size + 1)

        # 检查内存限制
        new_memory = current_memory + required_bytes
        if new_memory > self.max_memory_bytes:
            needed_to_free = new_memory - self.max_memory_bytes
            self._evict_by_memory(needed_to_free)

    def _evict_lru(self, count: int) -> None:
        """
        根据LRU策略驱逐缓存

        Args:
            count: 要驱逐的条目数
        """
        # 按最后访问时间排序
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )

        # 驱逐最旧的count个条目
        for key, _ in sorted_items[:count]:
            del self._cache[key]
            self._evictions += 1

        logger.debug(f"[PromptCache] LRU驱逐: {count} 个条目")

    def _evict_by_memory(self, bytes_to_free: int) -> None:
        """
        根据内存使用驱逐缓存

        Args:
            bytes_to_free: 需要释放的字节数
        """
        # 按最后访问时间排序
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )

        freed = 0
        for key, cached in sorted_items:
            if freed >= bytes_to_free:
                break

            del self._cache[key]
            freed += cached.size_bytes
            self._evictions += 1

        logger.debug(f"[PromptCache] 内存驱逐: 释放 {freed} bytes")

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            logger.info("[PromptCache] 缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            total_memory = sum(c.size_bytes for c in self._cache.values())

            return {
                "total_entries": len(self._cache),
                "max_entries": self.max_size,
                "memory_usage_mb": total_memory / (1024 * 1024),
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "total_hits": self._hits,
                "total_misses": self._misses,
                "hit_rate": hit_rate * 100,
                "total_evictions": self._evictions,
                "ttl_seconds": self.ttl_seconds
            }


class PromptCacheManager:
    """提示词缓存管理器（单例）"""

    _instance: Optional['PromptCacheManager'] = None
    _lock = Lock()

    def __init__(self):
        self.cache = PromptCache()

    @classmethod
    def get_instance(cls) -> 'PromptCacheManager':
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, context: Dict[str, Any]) -> Optional[str]:
        """获取缓存提示词"""
        return self.cache.get(context)

    def set(self, context: Dict[str, Any], prompt: str) -> None:
        """设置缓存提示词"""
        self.cache.set(context, prompt)

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.cache.get_stats()


def cached_prompt(
    cache_manager: Optional[PromptCacheManager] = None
) -> Callable:
    """
    提示词缓存装饰器

    Args:
        cache_manager: 缓存管理器实例，默认使用全局单例

    Returns:
        装饰器函数

    Usage:
        @cached_prompt()
        def generate_prompt(context: Dict[str, Any]) -> str:
            # 生成提示词的代码
            return prompt
    """
    if cache_manager is None:
        cache_manager = PromptCacheManager.get_instance()

    def decorator(func: Callable) -> Callable:
        def wrapper(context: Dict[str, Any], *args, **kwargs) -> str:
            # 尝试从缓存获取
            cached = cache_manager.get(context)
            if cached is not None:
                return cached

            # 执行原始函数
            prompt = func(context, *args, **kwargs)

            # 存入缓存
            cache_manager.set(context, prompt)

            return prompt

        return wrapper

    return decorator


# 全局缓存实例
_global_cache_manager = PromptCacheManager.get_instance()


def get_global_prompt_cache() -> PromptCacheManager:
    """获取全局提示词缓存管理器"""
    return _global_cache_manager
