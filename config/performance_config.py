"""
性能优化配置

提供系统性能优化参数配置
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

from core.constants import CacheTTL, NetworkTimeout


@dataclass
class RedisPerformanceConfig:
    """Redis性能配置"""
    
    # 连接池配置
    max_connections: int = 20
    socket_connect_timeout: int = NetworkTimeout.REDIS_CONNECT_TIMEOUT
    socket_timeout: int = NetworkTimeout.REDIS_CONNECT_TIMEOUT
    socket_keepalive: bool = True
    socket_keepalive_options: Optional[Dict] = None
    
    # 重试配置
    max_retries: int = 3
    retry_on_timeout: bool = True
    
    # 批量操作配置
    pipeline_max_size: int = 100
    pipeline_timeout: float = 1.0
    
    # 压缩配置
    enable_compression: bool = False
    compression_threshold: int = 1024  # 字节
    
    # 性能监控
    enable_stats: bool = True
    stats_interval: float = 60.0  # 秒


@dataclass
class CachePerformanceConfig:
    """缓存性能配置"""
    
    # 通用配置
    max_size: int = 10000
    default_ttl: float = CacheTTL.MEDIUM
    max_memory_mb: float = 500.0
    
    # LRU配置
    lru_enabled: bool = True
    lru_eviction_batch: int = 10
    
    # TTL配置
    ttl_check_interval: float = 60.0
    auto_cleanup: bool = True
    
    # 持久化配置
    enable_persist: bool = False
    persist_interval: float = 300.0  # 5分钟
    persist_dir: str = "data/cache"
    
    # 预热配置
    enable_warmup: bool = False
    warmup_keys: list = None
    
    # 性能监控
    enable_stats: bool = True
    stats_report_interval: float = 300.0  # 5分钟


@dataclass
class MemoryPerformanceConfig:
    """记忆系统性能配置"""
    
    # 搜索配置
    default_top_k: int = 10
    max_top_k: int = 100
    search_timeout: float = 5.0
    
    # 批量操作配置
    batch_size: int = 100
    batch_timeout: float = 10.0
    
    # 向量检索配置
    vector_search_top_k: int = 20
    vector_similarity_threshold: float = 0.7
    
    # 缓存配置
    enable_cache: bool = True
    cache_ttl: float = CacheTTL.LONG
    cache_max_size: int = 1000
    
    # 并发配置
    max_concurrent_searches: int = 10
    
    # 性能监控
    enable_stats: bool = True
    stats_report_interval: float = 300.0


@dataclass
class SystemPerformanceConfig:
    """系统整体性能配置"""
    
    redis: RedisPerformanceConfig = None
    cache: CachePerformanceConfig = None
    memory: MemoryPerformanceConfig = None
    
    def __post_init__(self):
        if self.redis is None:
            self.redis = RedisPerformanceConfig()
        if self.cache is None:
            self.cache = CachePerformanceConfig()
        if self.memory is None:
            self.memory = MemoryPerformanceConfig()
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置字典"""
        return {
            "max_connections": self.redis.max_connections,
            "socket_connect_timeout": self.redis.socket_connect_timeout,
            "socket_timeout": self.redis.socket_timeout,
            "enable_stats": self.redis.enable_stats,
        }
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置字典"""
        return {
            "max_size": self.cache.max_size,
            "default_ttl": self.cache.default_ttl,
            "max_memory_mb": self.cache.max_memory_mb,
            "enable_stats": self.cache.enable_stats,
            "enable_persist": self.cache.enable_persist,
        }
    
    def get_memory_config(self) -> Dict[str, Any]:
        """获取记忆配置字典"""
        return {
            "default_top_k": self.memory.default_top_k,
            "enable_cache": self.memory.enable_cache,
            "enable_stats": self.memory.enable_stats,
        }


# 预定义配置模板

class PerformancePresets:
    """性能预设配置"""
    
    @staticmethod
    def development() -> SystemPerformanceConfig:
        """开发环境配置（注重调试）"""
        return SystemPerformanceConfig(
            redis=RedisPerformanceConfig(
                enable_stats=True,
                max_connections=5,
            ),
            cache=CachePerformanceConfig(
                max_size=1000,
                max_memory_mb=100.0,
                enable_stats=True,
                auto_cleanup=False,
            ),
            memory=MemoryPerformanceConfig(
                enable_cache=True,
                enable_stats=True,
                batch_size=10,
            )
        )
    
    @staticmethod
    def testing() -> SystemPerformanceConfig:
        """测试环境配置（注重速度）"""
        return SystemPerformanceConfig(
            redis=RedisPerformanceConfig(
                enable_stats=False,
                max_connections=10,
            ),
            cache=CachePerformanceConfig(
                max_size=5000,
                max_memory_mb=200.0,
                enable_stats=False,
                auto_cleanup=False,
            ),
            memory=MemoryPerformanceConfig(
                enable_cache=True,
                enable_stats=False,
                batch_size=50,
            )
        )
    
    @staticmethod
    def production() -> SystemPerformanceConfig:
        """生产环境配置（注重性能和稳定性）"""
        return SystemPerformanceConfig(
            redis=RedisPerformanceConfig(
                enable_stats=True,
                max_connections=50,
                max_retries=3,
                enable_compression=True,
            ),
            cache=CachePerformanceConfig(
                max_size=50000,
                max_memory_mb=1000.0,
                enable_stats=True,
                auto_cleanup=True,
                enable_persist=True,
                enable_warmup=True,
            ),
            memory=MemoryPerformanceConfig(
                enable_cache=True,
                enable_stats=True,
                batch_size=100,
                max_concurrent_searches=20,
            )
        )
    
    @staticmethod
    def high_performance() -> SystemPerformanceConfig:
        """高性能配置（注重吞吐量）"""
        return SystemPerformanceConfig(
            redis=RedisPerformanceConfig(
                enable_stats=False,
                max_connections=100,
                max_retries=1,
                enable_compression=True,
            ),
            cache=CachePerformanceConfig(
                max_size=100000,
                max_memory_mb=2000.0,
                enable_stats=False,
                auto_cleanup=True,
                enable_warmup=True,
            ),
            memory=MemoryPerformanceConfig(
                enable_cache=True,
                enable_stats=False,
                batch_size=200,
                max_concurrent_searches=50,
            )
        )
    
    @staticmethod
    def memory_optimized() -> SystemPerformanceConfig:
        """内存优化配置（注重低内存使用）"""
        return SystemPerformanceConfig(
            redis=RedisPerformanceConfig(
                enable_stats=False,
                max_connections=10,
            ),
            cache=CachePerformanceConfig(
                max_size=1000,
                max_memory_mb=50.0,
                enable_stats=False,
                auto_cleanup=True,
                default_ttl=CacheTTL.SHORT,
            ),
            memory=MemoryPerformanceConfig(
                enable_cache=False,
                enable_stats=False,
                batch_size=10,
            )
        )


# 获取配置的便捷函数

def get_performance_config(preset: str = "production") -> SystemPerformanceConfig:
    """获取性能配置
    
    Args:
        preset: 预设名称 (development, testing, production, high_performance, memory_optimized)
    
    Returns:
        性能配置对象
    """
    presets = {
        "development": PerformancePresets.development,
        "testing": PerformancePresets.testing,
        "production": PerformancePresets.production,
        "high_performance": PerformancePresets.high_performance,
        "memory_optimized": PerformancePresets.memory_optimized,
    }
    
    getter = presets.get(preset.lower(), PerformancePresets.production)
    return getter()


__all__ = [
    'RedisPerformanceConfig',
    'CachePerformanceConfig',
    'MemoryPerformanceConfig',
    'SystemPerformanceConfig',
    'PerformancePresets',
    'get_performance_config',
]
