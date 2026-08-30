"""
缓存系统适配器

提供旧缓存管理器到统一缓存系统的适配层
保持向后兼容性，逐步迁移
"""
import asyncio
import logging
from typing import Any, Dict, Optional, Callable
from functools import wraps

from core.unified_cache import (
    get_cache, unified_cache_get, unified_cache_set,
    unified_cache_delete, unified_cache_clear, cached
)
from core.constants import CacheTTL


logger = logging.getLogger(__name__)


class CacheManagerAdapter:
    """
    缓存管理器适配器
    
    将旧的CacheManager接口适配到统一缓存系统
    """
    
    def __init__(
        self,
        default_ttl: float = 3600.0,
        max_size: int = 1000,
        max_memory_mb: float = 100.0,
        enable_stats: bool = True
    ):
        """初始化适配器"""
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.enable_stats = enable_stats
        
        # 创建统一缓存实例
        self._cache = get_cache(
            "adapter_cache",
            config={
                "max_size": max_size,
                "default_ttl": default_ttl,
                "max_memory_mb": max_memory_mb,
                "enable_stats": enable_stats,
                "async_mode": False  # 使用同步模式以保持兼容性
            }
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值，不存在或已过期返回 None
        """
        return await unified_cache_get("adapter_cache", key)
    
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
        ttl = ttl or self.default_ttl
        return await unified_cache_set("adapter_cache", key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await unified_cache_delete("adapter_cache", key)
    
    async def clear(self) -> None:
        """清空所有缓存"""
        await unified_cache_clear("adapter_cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._cache.get_stats()
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键（兼容旧接口）"""
        import hashlib
        import json
        
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }
        
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()


class PromptCacheAdapter:
    """
    提示词缓存适配器
    
    将旧的PromptCache接口适配到统一缓存系统
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        ttl_seconds: int = 3600
    ):
        """初始化适配器"""
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds
        
        # 创建统一缓存实例
        self._cache = get_cache(
            "prompt_cache",
            config={
                "max_size": max_size,
                "default_ttl": float(ttl_seconds),
                "max_memory_mb": float(max_memory_mb),
                "enable_stats": True,
                "async_mode": False
            }
        )
    
    def get(self, context: Dict[str, Any]) -> Optional[str]:
        """
        从缓存获取提示词
        
        Args:
            context: 上下文字典
        
        Returns:
            缓存的提示词，如果不存在或过期则返回None
        """
        import hashlib
        import json
        
        # 生成缓存键
        ordered_context = json.dumps(context, sort_keys=True, ensure_ascii=False)
        key = hashlib.md5(ordered_context.encode('utf-8')).hexdigest()
        
        # 从统一缓存获取
        try:
            value = asyncio.run(unified_cache_get("prompt_cache", key))
            return value
        except:
            return None
    
    def set(self, context: Dict[str, Any], prompt: str) -> None:
        """
        将提示词存入缓存
        
        Args:
            context: 上下文字典
            prompt: 提示词内容
        """
        import hashlib
        import json
        
        # 生成缓存键
        ordered_context = json.dumps(context, sort_keys=True, ensure_ascii=False)
        key = hashlib.md5(ordered_context.encode('utf-8')).hexdigest()
        
        # 存入统一缓存
        try:
            asyncio.run(unified_cache_set("prompt_cache", key, prompt, self.ttl_seconds))
        except Exception as e:
            logger.error(f"提示词缓存设置失败: {e}")
    
    def clear(self) -> None:
        """清空缓存"""
        try:
            asyncio.run(unified_cache_clear("prompt_cache"))
        except Exception as e:
            logger.error(f"提示词缓存清空失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._cache.get_stats()


# 兼容函数
def get_cache_manager() -> CacheManagerAdapter:
    """获取缓存管理器（兼容旧接口）"""
    return CacheManagerAdapter()


def get_global_prompt_cache() -> PromptCacheAdapter:
    """获取全局提示词缓存（兼容旧接口）"""
    return PromptCacheAdapter()


def cached_decorator(ttl: Optional[float] = None, key_prefix: str = ""):
    """
    缓存装饰器（兼容旧接口）
    
    Args:
        ttl: 缓存时间（秒），None表示使用默认值
        key_prefix: 键前缀
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 使用新的统一缓存装饰器
            wrapper = cached(cache_type="adapter_cache", ttl=ttl, key_prefix=key_prefix)
            return await wrapper(func)(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本
            cache = get_cache_manager()
            
            # 生成缓存键
            cache_key = cache._generate_key(
                f"{key_prefix}:{func.__name__}",
                args[1:] if args and hasattr(args[0], '__class__') else args,
                kwargs
            )
            
            # 尝试从缓存获取
            try:
                cached_value = asyncio.run(cache.get(cache_key))
                if cached_value is not None:
                    return cached_value
            except:
                pass
            
            # 调用原函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            try:
                asyncio.run(cache.set(cache_key, result, ttl))
            except:
                pass
            
            return result
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 导出兼容接口
__all__ = [
    'CacheManagerAdapter',
    'PromptCacheAdapter',
    'get_cache_manager',
    'get_global_prompt_cache',
    'cached_decorator',
]
