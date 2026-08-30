"""
用户级跨平台活跃度追踪 (v8.1)

目的：追踪每个用户在各平台上的最后活跃时间，
    为主动消息平台路由提供精准的用户级数据。

与 user_activity_tracker.py 的区别：
  - user_activity_tracker: 单用户全局活跃 (不区分平台)
  - user_platform_activity: 用户 × 平台二维活跃度矩阵

数据文件: data/activity/user_platform_activity.json
结构: {user_id: {platform_id: {last_active: <unix_timestamp>, message_count: <int>}}}
"""

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/activity/user_platform_activity.json")
_LOCK = threading.Lock()
_CACHE: dict = {}
_CACHE_LOADED = False
_MAX_ENTRIES_PER_USER = 20


def _ensure_dir():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_cache() -> dict:
    global _CACHE, _CACHE_LOADED
    with _LOCK:
        if _CACHE_LOADED:
            return _CACHE
        _ensure_dir()
        if DATA_FILE.exists():
            try:
                raw = DATA_FILE.read_text(encoding="utf-8")
                _CACHE = json.loads(raw) if raw.strip() else {}
            except Exception as e:
                logger.warning(f"[跨平台活跃] 加载失败: {e}，使用空缓存")
                _CACHE = {}
        else:
            _CACHE = {}
        _CACHE_LOADED = True
        return _CACHE


def _save_cache():
    try:
        _ensure_dir()
        with _LOCK:
            tmp = DATA_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(DATA_FILE)
    except Exception as e:
        logger.debug(f"[跨平台活跃] 写入失败: {e}")


def record_platform_activity(user_id: str, platform_id: str, timestamp: float = None) -> None:
    """记录用户在某平台上的活跃时间"""
    if not user_id or not platform_id:
        return
    cache = _load_cache()
    uid = str(user_id)
    pid = str(platform_id)
    ts = timestamp or time.time()

    with _LOCK:
        user_data = cache.setdefault(uid, {})
        platform_data = user_data.setdefault(pid, {"last_active": 0.0, "message_count": 0})
        platform_data["last_active"] = ts
        platform_data["message_count"] = platform_data.get("message_count", 0) + 1

        active_platforms = sorted(
            user_data.keys(),
            key=lambda p: user_data[p].get("last_active", 0.0),
            reverse=True,
        )
        if len(active_platforms) > _MAX_ENTRIES_PER_USER:
            for p in active_platforms[_MAX_ENTRIES_PER_USER:]:
                del user_data[p]

    _save_cache()


def get_user_platform_activity(user_id: str) -> dict:
    """获取用户在所有平台上的活跃记录

    返回: {platform_id: {last_active: float, message_count: int}}
    """
    cache = _load_cache()
    return cache.get(str(user_id), {}).copy()


def get_platform_last_active(user_id: str, platform_id: str) -> float:
    """获取用户在某平台的最后活跃时间（秒级 Unix 时间戳）"""
    cache = _load_cache()
    platform_data = cache.get(str(user_id), {}).get(str(platform_id), {})
    return platform_data.get("last_active", 0.0)


def get_most_active_platform(user_id: str) -> str:
    """返回用户最近活跃的平台 ID，无记录时返回空字符串"""
    cache = _load_cache()
    user_data = cache.get(str(user_id), {})
    if not user_data:
        return ""

    best_platform = ""
    best_time = 0.0
    for pid, pdata in user_data.items():
        last = pdata.get("last_active", 0.0)
        if last > best_time:
            best_time = last
            best_platform = pid
    return best_platform


def get_user_active_seconds_ago(user_id: str, platform_id: str) -> float:
    """返回用户在某平台距上次活跃的秒数，无记录则返回 inf"""
    last = get_platform_last_active(user_id, platform_id)
    if last <= 0:
        return float("inf")
    return max(0.0, time.time() - last)


def get_all_user_platform_activity(user_id: str, now: float = None) -> dict:
    """获取用户跨平台活跃度摘要（用于 AI 路由 prompt）

    返回: {platform_id: {last_active: float, seconds_ago: float, message_count: int}}
    """
    if now is None:
        now = time.time()
    cache = _load_cache()
    result = {}
    for pid, pdata in cache.get(str(user_id), {}).items():
        last = pdata.get("last_active", 0.0)
        result[pid] = {
            "last_active": last,
            "seconds_ago": max(0.0, now - last) if last > 0 else float("inf"),
            "message_count": pdata.get("message_count", 0),
        }
    return result
