"""
权限缓存 - 使用 Redis 缓存权限检查结果

功能：
- 缓存用户权限检查结果
- 减少数据库查询次数
- 支持缓存失效和手动刷新
"""

import json
import logging
from typing import Dict, Any, Optional, Set
from datetime import timedelta

logger = logging.getLogger(__name__)


class PermissionCache:
    """
    权限缓存管理器

    使用内存缓存（可扩展为Redis）存储权限检查结果
    缓存策略：TTL + 手动失效
    """

    def __init__(
        self,
        enable_cache: bool = True,
        ttl_seconds: int = 300,  # 5分钟缓存
        redis_url: Optional[str] = None
    ):
        """
        初始化权限缓存

        Args:
            enable_cache: 是否启用缓存
            ttl_seconds: 缓存TTL（秒）
            redis_url: Redis连接URL（可选）
        """
        self.enable_cache = enable_cache
        self.ttl_seconds = ttl_seconds

        # 内存缓存
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Redis连接（可选）
        self._redis = None
        self._redis_url = redis_url

        if enable_cache and redis_url:
            self._init_redis()

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            import redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            logger.info("[PermissionCache] Redis缓存已启用")
        except ImportError:
            logger.warning("[PermissionCache] redis库未安装，使用内存缓存")
            self._redis = None
        except Exception as e:
            logger.warning(f"[PermissionCache] Redis连接失败: {e}，使用内存缓存")
            self._redis = None

    def _make_key(self, user_id: str, permission: str) -> str:
        """生成缓存键"""
        return f"perm:{user_id}:{permission}"

    def get(self, user_id: str, permission: str) -> Optional[bool]:
        """
        获取缓存的权限检查结果

        Args:
            user_id: 用户ID
            permission: 权限节点

        Returns:
            缓存的权限结果，如果未缓存则返回None
        """
        if not self.enable_cache:
            return None

        key = self._make_key(user_id, permission)

        # 尝试从Redis获取
        if self._redis:
            try:
                cached = self._redis.get(key)
                if cached is not None:
                    return json.loads(cached)
            except Exception as e:
                logger.debug(f"[PermissionCache] Redis获取失败: {e}")

        # 从内存缓存获取
        if key in self._cache:
            entry = self._cache[key]
            # 检查是否过期
            import time
            if time.time() - entry['timestamp'] < self.ttl_seconds:
                return entry['result']
            else:
                # 过期，删除
                del self._cache[key]

        return None

    def set(self, user_id: str, permission: str, result: bool) -> None:
        """
        设置权限检查结果缓存

        Args:
            user_id: 用户ID
            permission: 权限节点
            result: 权限检查结果
        """
        if not self.enable_cache:
            return

        key = self._make_key(user_id, permission)

        # 存储到Redis
        if self._redis:
            try:
                self._redis.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(result)
                )
            except Exception as e:
                logger.debug(f"[PermissionCache] Redis存储失败: {e}")

        # 存储到内存缓存
        import time
        self._cache[key] = {
            'result': result,
            'timestamp': time.time()
        }

    def invalidate_user(self, user_id: str) -> None:
        """
        失效用户所有缓存

        Args:
            user_id: 用户ID
        """
        # 从Redis删除
        if self._redis:
            try:
                pattern = f"perm:{user_id}:*"
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.debug(f"[PermissionCache] Redis删除失败: {e}")

        # 从内存缓存删除
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"perm:{user_id}:")]
        for key in keys_to_delete:
            del self._cache[key]

    def invalidate_permission(self, user_id: str, permission: str) -> None:
        """
        失效指定权限缓存

        Args:
            user_id: 用户ID
            permission: 权限节点
        """
        key = self._make_key(user_id, permission)

        if self._redis:
            try:
                self._redis.delete(key)
            except Exception as e:
                logger.debug(f"[PermissionCache] Redis删除失败: {e}")

        if key in self._cache:
            del self._cache[key]

    def clear_all(self) -> None:
        """清空所有缓存"""
        if self._redis:
            try:
                pattern = "perm:*"
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.debug(f"[PermissionCache] Redis清空失败: {e}")

        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = {
            "enabled": self.enable_cache,
            "backend": "redis" if self._redis else "memory",
            "memory_size": len(self._cache),
            "ttl_seconds": self.ttl_seconds
        }

        if self._redis:
            try:
                stats["redis_keys"] = len(self._redis.keys("perm:*"))
            except:
                pass

        return stats


# 全局缓存实例
_permission_cache = None


def get_permission_cache() -> PermissionCache:
    """获取全局权限缓存实例"""
    global _permission_cache
    if _permission_cache is None:
        # 尝试从环境变量读取Redis配置
        import os
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        enable_cache = os.getenv('PERMISSION_CACHE_ENABLED', 'true').lower() == 'true'
        ttl = int(os.getenv('PERMISSION_CACHE_TTL', '300'))

        _permission_cache = PermissionCache(
            enable_cache=enable_cache,
            ttl_seconds=ttl,
            redis_url=redis_url
        )
    return _permission_cache
