"""
配置缓存层 - LRU缓存 + 文件监听

设计目标:
1. 减少频繁的配置文件读取
2. 支持智能缓存失效策略
3. 与现有热重载系统集成
4. 提供多级缓存支持
"""

import contextlib
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .unified_cache import BaseCacheLayer, CacheConfig, get_cache

logger = logging.getLogger(__name__)


@dataclass
class ConfigCacheEntry:
    """配置缓存条目"""

    config_data: Dict[str, Any]
    config_hash: str  # 配置内容的哈希值
    load_time: float  # 加载时间戳
    file_mtime: float  # 文件修改时间
    access_count: int = 0  # 访问次数
    last_access: float = 0.0  # 最后访问时间

    def is_expired(self, max_age: Optional[float] = None) -> bool:
        """检查是否过期"""
        current_time = time.time()
        age = current_time - self.load_time

        # 基础过期检查
        return bool(max_age and age > max_age)

    def touch(self):
        """更新访问统计"""
        self.access_count += 1
        self.last_access = time.time()


class ConfigCacheLayer:
    """配置缓存层"""

    def __init__(
        self,
        max_size: int = 100,  # 最大缓存条目数
        default_ttl: float = 300.0,  # 默认缓存时间（秒）
        enable_lru: bool = True,
        enable_file_watch: bool = True,
        cache_name: str = "config_cache",
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_lru = enable_lru
        self.enable_file_watch = enable_file_watch
        self.cache_name = cache_name

        # LRU缓存
        self._cache: OrderedDict[str, ConfigCacheEntry] = OrderedDict()

        # 文件监听器
        self._file_watchers: Dict[str, Any] = {}

        # 统一缓存后端（可选）
        self._unified_cache: Optional[BaseCacheLayer] = None

        # 统计信息
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "invalidations": 0, "loads": 0}

        logger.info(f"[配置缓存] 初始化完成: max_size={max_size}, ttl={default_ttl}s")

    def initialize(self) -> bool:
        """初始化缓存层"""
        try:
            # 初始化统一缓存后端
            try:
                cache_config = CacheConfig(
                    max_size=self.max_size,
                    default_ttl=self.default_ttl,
                    max_memory_mb=10.0,  # 配置缓存不需要太多内存
                    enable_stats=True,
                    async_mode=True,
                )
                self._unified_cache = get_cache(self.cache_name, cache_config)
            except Exception as e:
                logger.warning(f"[配置缓存] 统一缓存初始化失败，使用内存缓存: {e}")
                self._unified_cache = None

            # 文件监听：依赖 mtime 哈希兜底（ConfigHotReload 为单文件监听，不适用于多文件缓存场景）
            return True

        except Exception as e:
            logger.error(f"[配置缓存] 初始化失败: {e}")
            return False

    def _generate_cache_key(self, file_path: Path) -> str:
        """生成缓存键"""
        return f"config:{file_path.absolute()}"

    def _calculate_config_hash(self, config_data: Dict[str, Any]) -> str:
        """计算配置哈希值"""
        # 序列化配置数据为JSON字符串
        config_str = json.dumps(config_data, sort_keys=True, ensure_ascii=False)
        # 计算SHA-256哈希
        return hashlib.sha256(config_str.encode()).hexdigest()

    def _get_file_mtime(self, file_path: Path) -> float:
        """获取文件修改时间"""
        try:
            return file_path.stat().st_mtime
        except Exception:
            return 0.0

    def _evict_lru(self) -> int:
        """LRU驱逐策略"""
        if not self.enable_lru or len(self._cache) <= self.max_size:
            return 0

        evicted = 0
        # 找到最久未访问的条目
        while len(self._cache) > self.max_size:
            # OrderedDict第一个元素是最旧的
            key, entry = next(iter(self._cache.items()))
            self._cache.pop(key, None)
            self.stats["evictions"] += 1
            evicted += 1
            logger.debug(f"[配置缓存] LRU驱逐: {key}")

        return evicted

    async def load_config(
        self, file_path: Path, force_reload: bool = False, callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """加载配置（带缓存）"""
        cache_key = self._generate_cache_key(file_path)

        # 检查缓存
        if not force_reload:
            cached_data = await self._get_cached_config(cache_key, file_path)
            if cached_data is not None:
                self.stats["hits"] += 1
                return cached_data

        self.stats["misses"] += 1

        # 从文件加载
        config_data = await self._load_config_from_file(file_path)

        # 缓存结果
        await self._cache_config(cache_key, config_data, file_path)

        # 设置文件监听（如果需要）
        if self.enable_file_watch and callback:
            await self._setup_file_watch(file_path, callback)

        return config_data

    async def _get_cached_config(self, cache_key: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """从缓存获取配置"""
        # 首先检查内存缓存
        if cache_key in self._cache:
            entry = self._cache[cache_key]

            # 检查文件是否已修改
            current_mtime = self._get_file_mtime(file_path)
            if current_mtime > entry.file_mtime:
                logger.debug(f"[配置缓存] 文件已修改，缓存失效: {file_path}")
                self._cache.pop(cache_key, None)
                self.stats["invalidations"] += 1
                return None

            # 检查是否过期
            if entry.is_expired(self.default_ttl):
                logger.debug(f"[配置缓存] 缓存已过期: {file_path}")
                self._cache.pop(cache_key, None)
                return None

            # 更新访问统计
            entry.touch()
            # 移动到末尾（标记为最近使用）
            self._cache.move_to_end(cache_key)

            return entry.config_data

        # 检查统一缓存
        if self._unified_cache:
            try:
                cached_value = await self._unified_cache.get(cache_key)
                if cached_value:
                    # 验证文件是否已修改
                    current_mtime = self._get_file_mtime(file_path)
                    cache_mtime = cached_value.get("file_mtime", 0)

                    if current_mtime <= cache_mtime:
                        config_hash = cached_value.get("config_hash", "")
                        current_hash = self._calculate_config_hash(cached_value.get("config_data", {}))

                        if config_hash == current_hash:
                            # 同步到内存缓存
                            entry = ConfigCacheEntry(
                                config_data=cached_value.get("config_data", {}),
                                config_hash=config_hash,
                                load_time=cached_value.get("load_time", time.time()),
                                file_mtime=cache_mtime,
                            )
                            self._cache[cache_key] = entry
                            self._cache.move_to_end(cache_key)

                            return entry.config_data
            except Exception as e:
                logger.debug(f"[配置缓存] 统一缓存获取失败: {e}")

        return None

    async def _load_config_from_file(self, file_path: Path) -> Dict[str, Any]:
        """从文件加载配置"""
        try:
            if not file_path.exists():
                logger.error(f"[配置缓存] 配置文件不存在: {file_path}")
                return {}

            # 根据文件类型选择加载方式
            if file_path.suffix == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            elif file_path.suffix == ".yaml" or file_path.suffix == ".yml":
                try:
                    import yaml

                    with open(file_path, "r", encoding="utf-8") as f:
                        config_data = yaml.safe_load(f)
                except ImportError:
                    logger.error("[配置缓存] PyYAML未安装，无法加载YAML文件")
                    return {}
            else:
                # 尝试作为JSON加载
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except:
                    # 作为文本文件处理
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        config_data = {"content": content}

            self.stats["loads"] += 1
            logger.debug(f"[配置缓存] 从文件加载配置: {file_path}")

            return config_data or {}

        except Exception as e:
            logger.error(f"[配置缓存] 加载配置文件失败: {file_path}, error: {e}")
            return {}

    async def _cache_config(self, cache_key: str, config_data: Dict[str, Any], file_path: Path):
        """缓存配置数据"""
        # 计算哈希和文件修改时间
        config_hash = self._calculate_config_hash(config_data)
        file_mtime = self._get_file_mtime(file_path)

        # 创建缓存条目
        entry = ConfigCacheEntry(
            config_data=config_data, config_hash=config_hash, load_time=time.time(), file_mtime=file_mtime
        )

        # 更新内存缓存
        self._cache[cache_key] = entry
        self._cache.move_to_end(cache_key)

        # 应用LRU驱逐
        self._evict_lru()

        # 更新统一缓存
        if self._unified_cache:
            try:
                cache_value = {
                    "config_data": config_data,
                    "config_hash": config_hash,
                    "load_time": entry.load_time,
                    "file_mtime": file_mtime,
                }
                await self._unified_cache.set(cache_key, cache_value, self.default_ttl)
            except Exception as e:
                logger.debug(f"[配置缓存] 统一缓存设置失败: {e}")

    async def _setup_file_watch(self, file_path: Path, callback: Callable):
        """设置文件监听"""
        if not self.enable_file_watch:
            return

        try:
            cache_key = self._generate_cache_key(file_path)

            async def invalidate_cache():
                """文件修改时的回调函数"""
                logger.info(f"[配置缓存] 配置文件已修改，缓存失效: {file_path}")

                # 移除缓存
                if cache_key in self._cache:
                    self._cache.pop(cache_key)
                    self.stats["invalidations"] += 1

                # 调用用户回调
                if callback:
                    try:
                        await callback()
                    except Exception as e:
                        logger.error(f"[配置缓存] 回调执行失败: {e}")

            self._file_watchers[str(file_path)] = True
            logger.debug(f"[配置缓存] 文件监听已设置: {file_path}")

        except Exception as e:
            logger.error(f"[配置缓存] 设置文件监听失败: {e}")

    async def invalidate_config(self, file_path: Path) -> bool:
        """使指定配置文件的缓存失效"""
        cache_key = self._generate_cache_key(file_path)

        # 从内存缓存移除
        if cache_key in self._cache:
            self._cache.pop(cache_key)

        # 从统一缓存移除
        if self._unified_cache:
            with contextlib.suppress(Exception):
                await self._unified_cache.delete(cache_key)

        self.stats["invalidations"] += 1
        logger.debug(f"[配置缓存] 手动使缓存失效: {file_path}")

        return True

    async def clear_all(self):
        """清空所有缓存"""
        self._cache.clear()

        if self._unified_cache:
            with contextlib.suppress(Exception):
                await self._unified_cache.clear()

        logger.info("[配置缓存] 所有缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_access = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_access if total_access > 0 else 0

        return {
            "cache_name": self.cache_name,
            "memory_entries": len(self._cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": f"{hit_rate:.2%}",
            "evictions": self.stats["evictions"],
            "invalidations": self.stats["invalidations"],
            "loads": self.stats["loads"],
            "unified_cache_enabled": self._unified_cache is not None,
            "file_watch_enabled": self.enable_file_watch,
        }


# 全局配置缓存实例
_global_config_cache: Optional[ConfigCacheLayer] = None


def get_config_cache(
    max_size: int = 100, default_ttl: float = 300.0, cache_name: str = "global_config_cache"
) -> ConfigCacheLayer:
    """获取全局配置缓存实例"""
    global _global_config_cache

    if _global_config_cache is None:
        _global_config_cache = ConfigCacheLayer(max_size=max_size, default_ttl=default_ttl, cache_name=cache_name)
        _global_config_cache.initialize()

    return _global_config_cache


async def load_config_cached(
    file_path: str | Path, force_reload: bool = False, callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """便捷函数：加载配置（带缓存）"""
    cache = get_config_cache()
    return await cache.load_config(Path(file_path), force_reload, callback)


async def invalidate_config_cache(file_path: str | Path) -> bool:
    """便捷函数：使配置缓存失效"""
    cache = get_config_cache()
    return await cache.invalidate_config(Path(file_path))


def get_cache_stats() -> Dict[str, Any]:
    """便捷函数：获取缓存统计"""
    cache = get_config_cache()
    return cache.get_stats()
