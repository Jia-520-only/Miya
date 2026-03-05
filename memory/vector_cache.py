"""
弥娅 - 向量化缓存系统
从VCPToolBox浪潮RAG V3整合
实现多级缓存策略：文本向量缓存、查询结果缓存、AI记忆缓存
"""

import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod
from core.constants import Encoding, CacheTTL
from core.unified_cache import BaseCacheLayer, CacheConfig

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    timestamp: float
    ttl: float  # Time To Live (seconds)

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class BaseCache(ABC):
    """缓存基类（兼容接口）"""

    def __init__(
        self,
        name: str,
        max_size: int = 100,
        ttl: float = 3600,
        persist_file: Optional[Path] = None
    ):
        self.name = name
        self.max_size = max_size
        self.default_ttl = ttl
        self.persist_file = persist_file
        
        # 使用统一缓存配置
        config = CacheConfig(
            max_size=max_size,
            default_ttl=ttl,
            enable_stats=True,
            enable_persist=(persist_file is not None),
            persist_dir=str(persist_file.parent) if persist_file else None,
            async_mode=False
        )
        
        self._unified_cache = BaseCacheLayer(name, config)
        self.cache: Dict[str, CacheEntry] = {}
        self.stats = CacheStats()

        logger.info(
            f"[Cache] {name} 初始化 - "
            f"max_size={max_size}, ttl={ttl}s"
        )

    def _make_key(self, key: str) -> str:
        """生成缓存键"""
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存（兼容接口，内部使用统一缓存）"""
        cache_key = self._make_key(key)
        
        # 先尝试从统一缓存获取
        try:
            import asyncio
            value = asyncio.run(self._unified_cache.get(key))
            if value is not None:
                self.stats.hits += 1
                return value
        except:
            pass
        
        # 回退到旧实现

        if cache_key not in self.cache:
            self.stats.misses += 1
            return None

        entry = self.cache[cache_key]

        if entry.is_expired():
            # 过期删除
            del self.cache[cache_key]
            self.stats.evictions += 1
            self.stats.misses += 1
            logger.debug(f"[Cache] {self.name} 缓存过期: {key[:30]}...")
            return None

        self.stats.hits += 1
        logger.debug(f"[Cache] {self.name} 缓存命中: {key[:30]}...")
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存"""
        if len(self.cache) >= self.max_size:
            # LRU淘汰
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].timestamp
            )
            del self.cache[oldest_key]
            self.stats.evictions += 1
            logger.debug(f"[Cache] {self.name} LRU淘汰")

        ttl = ttl or self.default_ttl
        cache_key = self._make_key(key)

        self.cache[cache_key] = CacheEntry(
            value=value,
            timestamp=time.time(),
            ttl=ttl
        )

        self.stats.size = len(self.cache)

    def delete(self, key: str):
        """删除缓存"""
        cache_key = self._make_key(key)
        if cache_key in self.cache:
            del self.cache[cache_key]
            self.stats.size = len(self.cache)

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.stats.size = 0
        logger.info(f"[Cache] {self.name} 缓存已清空")

    async def persist(self):
        """持久化缓存到文件"""
        if not self.persist_file:
            return

        try:
            # 只持久化未过期的缓存
            valid_cache = {
                k: {
                    'value': v.value,
                    'timestamp': v.timestamp,
                    'ttl': v.ttl
                }
                for k, v in self.cache.items()
                if not v.is_expired()
            }

            self.persist_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_file, 'w', encoding=Encoding.UTF8) as f:
                json.dump(valid_cache, f, ensure_ascii=False, indent=2)

            logger.info(f"[Cache] {self.name} 持久化完成: {len(valid_cache)} 条")

        except Exception as e:
            logger.error(f"[Cache] {self.name} 持久化失败: {e}")

    async def load(self):
        """从文件加载缓存"""
        if not self.persist_file or not self.persist_file.exists():
            return

        try:
            with open(self.persist_file, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            for k, v in data.items():
                entry = CacheEntry(
                    value=v['value'],
                    timestamp=v['timestamp'],
                    ttl=v['ttl']
                )
                if not entry.is_expired():
                    self.cache[k] = entry

            self.stats.size = len(self.cache)
            logger.info(f"[Cache] {self.name} 加载完成: {len(self.cache)} 条")

        except Exception as e:
            logger.error(f"[Cache] {self.name} 加载失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'name': self.name,
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'evictions': self.stats.evictions,
            'size': self.stats.size,
            'hit_rate': self.stats.hit_rate
        }


class EmbeddingCache(BaseCache):
    """文本向量化缓存"""

    def __init__(
        self,
        max_size: int = 500,
        ttl: float = 7200,  # 2小时
        persist_file: Optional[Path] = None
    ):
        super().__init__(
            name='EmbeddingCache',
            max_size=max_size,
            ttl=ttl,
            persist_file=persist_file or Path(__file__).parent / 'embedding_cache.json'
        )


class QueryResultCache(BaseCache):
    """查询结果缓存"""

    def __init__(
        self,
        max_size: int = 200,
        ttl: float = 3600,  # 1小时
        persist_file: Optional[Path] = None
    ):
        super().__init__(
            name='QueryResultCache',
            max_size=max_size,
            ttl=ttl,
            persist_file=persist_file or Path(__file__).parent / 'query_cache.json'
        )


class AIMemoCache(BaseCache):
    """AI记忆缓存"""

    def __init__(
        self,
        max_size: int = 50,
        ttl: float = 1800,  # 30分钟
        persist_file: Optional[Path] = None
    ):
        super().__init__(
            name='AIMemoCache',
            max_size=max_size,
            ttl=ttl,
            persist_file=persist_file or Path(__file__).parent / 'ai_memo_cache.json'
        )


class VectorCacheManager:
    """
    向量缓存管理器

    统一管理多级缓存：
    - EmbeddingCache: 文本向量缓存
    - QueryResultCache: 查询结果缓存
    - AIMemoCache: AI记忆缓存
    """

    def __init__(
        self,
        config: Optional[Dict] = None
    ):
        self.config = config or {}

        # 初始化各级缓存
        self.embedding_cache = EmbeddingCache(
            max_size=self.config.get('embedding_max_size', 500),
            ttl=self.config.get('embedding_ttl', 7200)
        )

        self.query_cache = QueryResultCache(
            max_size=self.config.get('query_max_size', 200),
            ttl=self.config.get('query_ttl', 3600)
        )

        self.ai_memo_cache = AIMemoCache(
            max_size=self.config.get('ai_memo_max_size', 50),
            ttl=self.config.get('ai_memo_ttl', 1800)
        )

        logger.info("[VectorCacheManager] 初始化完成")

    async def initialize(self):
        """初始化，加载持久化缓存"""
        await self.embedding_cache.load()
        await self.query_cache.load()
        await self.ai_memo_cache.load()

        logger.info("[VectorCacheManager] 持久化缓存加载完成")

    async def save(self):
        """保存所有缓存"""
        await self.embedding_cache.persist()
        await self.query_cache.persist()
        await self.ai_memo_cache.persist()

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """获取缓存的向量"""
        return self.embedding_cache.get(text)

    def set_embedding(self, text: str, vector: List[float]):
        """缓存向量"""
        self.embedding_cache.set(text, vector)

    def get_query_result(self, query: str, params: Dict) -> Optional[Any]:
        """
        获取查询结果缓存

        Args:
            query: 查询文本
            params: 查询参数

        Returns:
            缓存的结果
        """
        cache_key = self._make_query_cache_key(query, params)
        return self.query_cache.get(cache_key)

    def set_query_result(self, query: str, params: Dict, result: Any):
        """缓存查询结果"""
        cache_key = self._make_query_cache_key(query, params)
        self.query_cache.set(cache_key, result)

    def get_ai_memo(self, key: str) -> Optional[Any]:
        """获取AI记忆缓存"""
        return self.ai_memo_cache.get(key)

    def set_ai_memo(self, key: str, memo: Any):
        """缓存AI记忆"""
        self.ai_memo_cache.set(key, memo)

    def _make_query_cache_key(self, query: str, params: Dict) -> str:
        """
        生成查询缓存键

        Args:
            query: 查询文本
            params: 查询参数

        Returns:
            缓存键
        """
        import json
        params_json = json.dumps(params, sort_keys=True)
        return f"{query}||{params_json}"

    def clear_all(self):
        """清空所有缓存"""
        self.embedding_cache.clear()
        self.query_cache.clear()
        self.ai_memo_cache.clear()
        logger.info("[VectorCacheManager] 所有缓存已清空")

    def get_stats(self) -> Dict:
        """获取所有缓存统计"""
        return {
            'embedding_cache': self.embedding_cache.get_stats(),
            'query_cache': self.query_cache.get_stats(),
            'ai_memo_cache': self.ai_memo_cache.get_stats(),
            'total_size': (
                self.embedding_cache.stats.size +
                self.query_cache.stats.size +
                self.ai_memo_cache.stats.size
            )
        }


# 全局缓存管理器实例
_manager_instance = None


def get_vector_cache_manager(
    config: Optional[Dict] = None
) -> VectorCacheManager:
    """获取向量缓存管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = VectorCacheManager(config)
    return _manager_instance
