"""
搜索结果缓存 - 弥娅资源猎手核心

TTL 内存缓存：
- 主动搜索 / 工具重复查询时避免反复打引擎（节省 API 配额、降低延迟）
- 线程安全（搜索多在 run_in_executor 线程中执行）

参数从 qq_config.yaml 的 web_search.result_cache 读取。
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from config.config_utils import get_qq_config

logger = logging.getLogger(__name__)


class SearchCache:
    """线程安全的 TTL 内存缓存"""

    def __init__(self):
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._reload_config()

    def _reload_config(self) -> None:
        cfg = get_qq_config("web_search", "result_cache", default={}) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        self.enabled = bool(cfg.get("enabled", True))
        self.ttl = max(int(cfg.get("ttl_seconds", 1800) or 1800), 60)
        self.max_entries = max(int(cfg.get("max_entries", 256) or 256), 16)

    @staticmethod
    def make_key(prefix: str, query: str, engines: Any = None, resource_type: str = "") -> str:
        """构造缓存键。engines 可为列表/元组/None。"""
        eng = ""
        if engines:
            eng = ",".join(str(e) for e in engines) if isinstance(engines, (list, tuple)) else str(engines)
        return f"{prefix}|{resource_type}|{eng}|{query.strip().lower()}"

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        if not self.enabled or value is None:
            return
        with self._lock:
            # 逐出最早插入的条目，防止无限膨胀
            if len(self._data) >= self.max_entries and key not in self._data:
                oldest = next(iter(self._data), None)
                if oldest is not None:
                    self._data.pop(oldest, None)
            self._data[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"entries": len(self._data), "enabled": self.enabled, "ttl": self.ttl}


_search_cache: Optional[SearchCache] = None
_cache_lock = threading.Lock()


def get_search_cache() -> SearchCache:
    """获取全局缓存单例"""
    global _search_cache
    if _search_cache is None:
        with _cache_lock:
            if _search_cache is None:
                _search_cache = SearchCache()
    return _search_cache
