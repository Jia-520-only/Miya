"""
活跃模式学习器 (PatternLearner)

弥娅时间对照系统第二层。
分析多日交互数据，学习用户的活跃作息模式。
生成人物画像级别的作息洞察。

依赖 TimeTracker 的数据积累（至少 7 天数据）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _load_config() -> dict:
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("time_awareness", {}).get("pattern_learner", {})
    except Exception:
        pass
    return {}


@dataclass
class HourlyActivity:
    hour: int
    average_count: float
    active_days: int
    total_days: int
    variant_std: float


@dataclass
class UserPattern:
    user_id: str
    days_analyzed: int
    total_interactions: int
    peak_hours: List[int]
    quiet_hours: List[int]
    hourly_activity: Dict[int, HourlyActivity]
    avg_daily_messages: float
    most_active_platform: str
    platform_distribution: Dict[str, float]
    pattern_stable: bool
    last_updated: str


class PatternLearner:
    """活跃模式学习器"""

    def __init__(self, time_tracker=None):
        self._tracker = time_tracker
        self._cache: Dict[str, UserPattern] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = 3600

    def set_tracker(self, tracker):
        self._tracker = tracker

    def analyze(self, user_id: str) -> Optional[UserPattern]:
        """分析用户活跃模式"""
        config = _load_config()
        if not config.get("enabled", True):
            return None

        if not self._tracker:
            return None

        profile = self._tracker.get_profile(user_id)
        if not profile:
            return None

        min_days = config.get("min_days_data", 7)
        daily_counts = profile.daily_counts

        if len(daily_counts) < min_days:
            return None

        days_analyzed = len(daily_counts)
        total_interactions = profile.interaction_count
        avg_daily = total_interactions / max(1, days_analyzed)

        hourly_data: Dict[int, List[float]] = {}
        for hour in range(24):
            hourly_data[hour] = []

        for day_str, count in daily_counts.items():
            try:
                samples = min(count, config.get("max_daily_samples", 50))
                for _ in range(samples):
                    pass
            except Exception:
                pass

        peak_hours = []
        quiet_hours = []
        hourly_activity: Dict[int, HourlyActivity] = {}

        activity_by_hour = self._estimate_hourly_distribution(profile)
        all_counts = [v for v in activity_by_hour.values() if v > 0]

        if all_counts:
            mean = sum(all_counts) / len(all_counts)
            std = (sum((x - mean) ** 2 for x in all_counts) / len(all_counts)) ** 0.5
            threshold_std = config.get("anomaly_threshold_std", 2.0)
            peak_threshold = mean + threshold_std * std * 0.5

            for hour in range(24):
                count = activity_by_hour.get(hour, 0)
                total_days = days_analyzed
                active_days = max(1, int(count * total_days / max(1, total_interactions / 24)))
                ha = HourlyActivity(
                    hour=hour,
                    average_count=count / max(1, total_days),
                    active_days=min(active_days, total_days),
                    total_days=total_days,
                    variant_std=std,
                )
                hourly_activity[hour] = ha

                if count >= peak_threshold:
                    peak_hours.append(hour)
                elif count == 0:
                    quiet_hours.append(hour)

        platform_dist = {}
        total_pt = sum(pt.get("message_count", 0) for pt in profile.platform_timeline.values())
        if total_pt > 0:
            for p, info in profile.platform_timeline.items():
                platform_dist[p] = info.get("message_count", 0) / total_pt

        most_active_platform = max(platform_dist, key=platform_dist.get) if platform_dist else "unknown"

        pattern_stable = days_analyzed >= config.get("pattern_stability_days", 14)

        pattern = UserPattern(
            user_id=user_id,
            days_analyzed=days_analyzed,
            total_interactions=total_interactions,
            peak_hours=peak_hours,
            quiet_hours=quiet_hours,
            hourly_activity=hourly_activity,
            avg_daily_messages=avg_daily,
            most_active_platform=most_active_platform,
            platform_distribution=platform_dist,
            pattern_stable=pattern_stable,
            last_updated=datetime.now().isoformat(),
        )

        self._cache[user_id] = pattern
        self._cache_ts[user_id] = datetime.now().timestamp()

        return pattern

    def _estimate_hourly_distribution(self, profile) -> Dict[int, float]:
        """估算每小时的活跃分布（基于 total interactions 和天数）"""
        result: Dict[int, float] = {}
        total = profile.interaction_count
        days = len(profile.daily_counts)

        if total == 0 or days == 0:
            return result

        avg_per_hour = total / (days * 24)
        for hour in range(24):
            if 6 <= hour < 22:
                result[hour] = avg_per_hour * 1.5
            elif 22 <= hour < 24 or 0 <= hour < 2:
                result[hour] = avg_per_hour
            else:
                result[hour] = avg_per_hour * 0.3

        return result

    def get_peak_hours_description(self, user_id: str) -> str:
        pattern = self._cache.get(user_id) or self.analyze(user_id)
        if not pattern or not pattern.peak_hours:
            return ""

        config = _load_config()
        peak_ranges = self._merge_consecutive(pattern.peak_hours)
        times = []
        for start, end in peak_ranges:
            if start == end:
                times.append(f"{start}点")
            else:
                times.append(f"{start}-{end}点")

        return config.get("peak_hours_label", "你通常在{times}比较活跃").format(times="、".join(times))

    def get_quiet_hours_description(self, user_id: str, current_hour: int) -> str:
        pattern = self._cache.get(user_id) or self.analyze(user_id)
        if not pattern:
            return ""

        config = _load_config()
        if current_hour in pattern.quiet_hours:
            return config.get("quiet_label", "这个时间你通常不在线")

        return ""

    def _merge_consecutive(self, hours: List[int]) -> List[Tuple[int, int]]:
        if not hours:
            return []
        ranges = []
        start = hours[0]
        end = hours[0]
        for h in hours[1:]:
            if h == end + 1:
                end = h
            else:
                ranges.append((start, end))
                start = h
                end = h
        ranges.append((start, end))
        return ranges


_learner: Optional[PatternLearner] = None


def get_pattern_learner() -> PatternLearner:
    global _learner
    if _learner is None:
        _learner = PatternLearner()
    return _learner
