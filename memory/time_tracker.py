"""
时间追踪器 (TimeTracker)

记录弥娅与每个用户/平台的交互时间线。
为 TimeComparisonEngine 提供原始数据，
支持跨平台时间线统一视图和活跃模式学习。

存储: data/time_tracker.json（轻量 JSON，高频写入）
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InteractionRecord:
    user_id: str
    platform: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    timestamp_float: float = field(default_factory=time.time)
    role: str = "user"
    session_start: bool = False
    message_preview: str = ""


@dataclass
class UserTimeProfile:
    user_id: str
    first_interaction: str = ""
    last_interaction: str = ""
    last_interaction_ts: float = 0.0
    last_session_start: str = ""
    last_session_start_ts: float = 0.0
    last_platform: str = "unknown"
    all_platforms: List[str] = field(default_factory=list)
    interaction_count: int = 0
    daily_streak: int = 0
    last_active_date: str = ""
    # 跨平台时间线
    platform_timeline: Dict[str, Dict] = field(default_factory=dict)
    # 近 7 天每日交互计数（用于模式学习）
    daily_counts: Dict[str, int] = field(default_factory=dict)


class TimeTracker:
    """时间追踪器 — 记录每次交互的时间戳"""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or Path("data")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._data_dir / "time_tracker.json"
        self._lock_file = self._data_dir / "time_tracker.lock"

        self._profiles: Dict[str, UserTimeProfile] = {}
        self._dirty = False
        self._last_save = 0.0
        self._save_interval = 30.0

        self._load()
        logger.info("[TimeTracker] 初始化完成，已加载 %d 个用户档案", len(self._profiles))

    def _load(self):
        try:
            if self._file_path.exists():
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for uid, raw in data.get("profiles", {}).items():
                    profile = UserTimeProfile(
                        user_id=raw.get("user_id", uid),
                        first_interaction=raw.get("first_interaction", ""),
                        last_interaction=raw.get("last_interaction", ""),
                        last_interaction_ts=raw.get("last_interaction_ts", 0.0),
                        last_session_start=raw.get("last_session_start", ""),
                        last_session_start_ts=raw.get("last_session_start_ts", 0.0),
                        last_platform=raw.get("last_platform", "unknown"),
                        all_platforms=raw.get("all_platforms", []),
                        interaction_count=raw.get("interaction_count", 0),
                        daily_streak=raw.get("daily_streak", 0),
                        last_active_date=raw.get("last_active_date", ""),
                        platform_timeline=raw.get("platform_timeline", {}),
                        daily_counts=raw.get("daily_counts", {}),
                    )
                    self._profiles[uid] = profile
        except Exception as e:
            logger.warning("[TimeTracker] 加载失败: %s", e)
            self._profiles = {}

    def _save(self, force: bool = False):
        now = time.time()
        if not force and (now - self._last_save) < self._save_interval:
            return

        try:
            if self._lock_file.exists():
                return

            self._lock_file.touch()
            try:
                data = {
                    "updated_at": datetime.now().isoformat(),
                    "profile_count": len(self._profiles),
                    "profiles": {uid: asdict(p) for uid, p in self._profiles.items()},
                }
                tmp_path = self._file_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._file_path)
                self._last_save = now
                self._dirty = False
            finally:
                if self._lock_file.exists():
                    self._lock_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("[TimeTracker] 保存失败: %s", e)

    def _get_or_create(self, user_id: str) -> UserTimeProfile:
        uid = str(user_id)
        if uid not in self._profiles:
            self._profiles[uid] = UserTimeProfile(user_id=uid)
        return self._profiles[uid]

    def record_interaction(
        self,
        user_id: str,
        platform: str,
        role: str = "user",
        session_start: bool = False,
        message_preview: str = "",
    ):
        """记录一次交互"""
        uid = str(user_id)
        profile = self._get_or_create(uid)
        now = time.time()
        now_iso = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")

        if not profile.first_interaction:
            profile.first_interaction = now_iso

        profile.last_interaction = now_iso
        profile.last_interaction_ts = now
        profile.interaction_count += 1

        if session_start:
            profile.last_session_start = now_iso
            profile.last_session_start_ts = now

        if profile.last_platform != platform:
            profile.last_platform = platform
            if platform not in profile.all_platforms:
                profile.all_platforms.append(platform)

        # 更新平台时间线
        if platform not in profile.platform_timeline:
            profile.platform_timeline[platform] = {
                "first_seen": now_iso,
                "last_seen": now_iso,
                "last_seen_ts": now,
                "message_count": 0,
            }
        pt = profile.platform_timeline[platform]
        pt["last_seen"] = now_iso
        pt["last_seen_ts"] = now
        pt["message_count"] += 1

        # 每日计数
        profile.daily_counts[today] = profile.daily_counts.get(today, 0) + 1

        # 连续活跃天数
        if profile.last_active_date != today:
            if profile.last_active_date:
                last_date = datetime.strptime(profile.last_active_date, "%Y-%m-%d")
                delta = (datetime.now() - last_date).days
                if delta == 1:
                    profile.daily_streak += 1
                elif delta > 1:
                    profile.daily_streak = 1
            else:
                profile.daily_streak = 1
            profile.last_active_date = today

        self._dirty = True
        self._save()

    def get_profile(self, user_id: str) -> Optional[UserTimeProfile]:
        return self._profiles.get(str(user_id))

    def get_all_profiles(self) -> Dict[str, UserTimeProfile]:
        return dict(self._profiles)

    def get_last_interaction_time(self, user_id: str) -> float:
        profile = self._profiles.get(str(user_id))
        return profile.last_interaction_ts if profile else 0.0

    def get_last_interaction_platform(self, user_id: str) -> str:
        profile = self._profiles.get(str(user_id))
        return profile.last_platform if profile else "unknown"

    def get_platform_timeline(self, user_id: str) -> Dict[str, Dict]:
        profile = self._profiles.get(str(user_id))
        return dict(profile.platform_timeline) if profile else {}

    def flush(self):
        self._save(force=True)


# 全局单例
_tracker: Optional[TimeTracker] = None


def get_time_tracker() -> TimeTracker:
    global _tracker
    if _tracker is None:
        _tracker = TimeTracker()
    return _tracker


def reset_time_tracker():
    global _tracker
    _tracker = None
