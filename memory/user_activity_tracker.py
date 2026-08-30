"""
用户活跃追踪器（轻量级、同步写盘）

目的：绕过 conversation history 异步写的不确定性，
    提供可靠的用户最后活跃时间查询。

每个用户一个文件：data/activity/user_<user_id>.json
内容：{"last_active": <timestamp>, "last_topic": "<topic>"}
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/activity")


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_user_file(user_id: str) -> Path:
    _ensure_dir()
    return DATA_DIR / f"user_{user_id}.json"


def record_activity(user_id: str, last_topic: str = "") -> None:
    """记录用户活跃（同步写盘）"""
    try:
        file_path = _get_user_file(str(user_id))
        data = {
            "last_active": time.time(),
            "last_topic": last_topic[:100] if last_topic else "",
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"[活动追踪] 写入失败 ({user_id}): {e}")


def get_last_active(user_id: str) -> float:
    """获取用户最后活跃时间（秒级 Unix 时间戳）"""
    try:
        file_path = _get_user_file(str(user_id))
        if not file_path.exists():
            return 0.0
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_active", 0.0)
    except Exception:
        return 0.0


def get_last_topic(user_id: str) -> str:
    """获取用户最后话题"""
    try:
        file_path = _get_user_file(str(user_id))
        if not file_path.exists():
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_topic", "")
    except Exception:
        return ""


def get_elapsed(user_id: str) -> float:
    """获取用户距上次活跃的秒数"""
    last = get_last_active(user_id)
    if last <= 0:
        return float("inf")
    return max(0, time.time() - last)
