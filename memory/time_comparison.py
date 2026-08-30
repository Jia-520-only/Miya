"""
时间对照引擎 (TimeComparisonEngine)

对比本次交互与上次交互的时间差，生成自然语言时间感知描述。
从配置加载所有标签文本，支持热更新。

输出三类感知文本：
1. elapsed_label — "刚才/几小时前/昨天下午/3天前/一周没见"
2. time_period — "凌晨/早上/上午/中午/下午/傍晚/深夜"
3. platform_context — "之前在QQ上聊过，现在换终端了？"
4. session_duration — 本次在线时长
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_config() -> dict:
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("time_awareness", {})
    except Exception:
        pass
    return {}


_CONFIG: dict = {}


def _get_config() -> dict:
    global _CONFIG
    if not _CONFIG:
        _CONFIG = _load_config()
    return _CONFIG


def reload_config():
    global _CONFIG
    _CONFIG = _load_config()


@dataclass
class TimePerception:
    user_id: str
    platform: str  # current platform

    elapsed_seconds: float
    elapsed_label: str
    elapsed_short: str
    elapsed_category: str

    last_platform: str
    platform_switch: bool
    platform_context: str

    time_period: str
    time_period_simple: str
    current_hour: int

    session_duration_seconds: float
    session_duration_label: str

    is_new_day: bool
    is_new_session: bool
    daily_streak: int

    all_platforms_seen: List[str]

    full_context: str = ""


class TimeComparisonEngine:
    """时间对照引擎"""

    def __init__(self, time_tracker=None):
        self._tracker = time_tracker
        self._session_start_times: Dict[str, float] = {}

    def set_tracker(self, tracker):
        self._tracker = tracker

    def mark_session_start(self, user_id: str):
        uid = str(user_id)
        self._session_start_times[uid] = datetime.now().timestamp()

    def compare(
        self,
        user_id: str,
        current_platform: str,
        session_start_ts: Optional[float] = None,
    ) -> TimePerception:
        """生成完整时间感知

        Args:
            user_id: 用户ID
            current_platform: 当前所在平台
            session_start_ts: 本次会话启动时间戳（可选）
        """
        now = datetime.now()
        now_ts = now.timestamp()
        config = _get_config()

        profile = None
        last_ts = 0.0
        last_platform = "unknown"
        all_platforms = []
        daily_streak = 0

        if self._tracker:
            profile = self._tracker.get_profile(user_id)
            if profile:
                last_ts = profile.last_interaction_ts
                last_platform = profile.last_platform
                all_platforms = list(profile.all_platforms)
                daily_streak = profile.daily_streak

        elapsed = now_ts - last_ts if last_ts > 0 else float("inf")
        platform_switch = last_platform != current_platform and last_platform != "unknown"
        is_new_day = True
        if last_ts > 0:
            last_date = datetime.fromtimestamp(last_ts).date()
            is_new_day = last_date != now.date()

        session_duration = 0.0
        uid = str(user_id)
        if session_start_ts is not None:
            session_duration = now_ts - session_start_ts
        elif uid in self._session_start_times:
            session_duration = now_ts - self._session_start_times[uid]

        # 生成各类标签
        elapsed_label, elapsed_short, elapsed_category = self._classify_elapsed(elapsed, config)
        time_period, time_period_simple, current_hour = self._classify_time_period(now.hour, config)
        platform_context = self._build_platform_context(
            current_platform, last_platform, platform_switch, elapsed_label, all_platforms, config
        )
        session_label = self._format_duration(session_duration, config)

        perception = TimePerception(
            user_id=user_id,
            platform=current_platform,
            elapsed_seconds=elapsed,
            elapsed_label=elapsed_label,
            elapsed_short=elapsed_short,
            elapsed_category=elapsed_category,
            last_platform=last_platform,
            platform_switch=platform_switch,
            platform_context=platform_context,
            time_period=time_period,
            time_period_simple=time_period_simple,
            current_hour=current_hour,
            session_duration_seconds=session_duration,
            session_duration_label=session_label,
            is_new_day=is_new_day,
            is_new_session=elapsed > 300,
            daily_streak=daily_streak,
            all_platforms_seen=all_platforms,
        )

        perception.full_context = self.build_raw_context(perception)
        return perception

    def _classify_elapsed(self, elapsed_seconds: float, config: dict):
        """分类时间间隔"""
        thresholds = config.get(
            "elapsed_thresholds",
            {
                "just_now": 300,
                "this_session": 1800,
                "hours": 21600,
                "today": 43200,
                "yesterday": 172800,
                "this_week": 604800,
            },
        )
        labels = config.get(
            "elapsed_labels",
            {
                "just_now": "刚才还在聊",
                "this_session": "半小时内聊过",
                "hours": "{hours}小时前聊过",
                "today": "今天早些时候聊过",
                "yesterday": "昨天{period}聊过",
                "this_week": "上次是{weekday}",
                "older": "好久不见（{days}天前）",
            },
        )

        weekdays = config.get("weekdays", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

        if elapsed_seconds == float("inf") or elapsed_seconds < 0:
            return "初次见面", "初次", "first_time"

        now = datetime.now()
        last_dt = datetime.fromtimestamp(now.timestamp() - elapsed_seconds)
        period = self._classify_time_period(last_dt.hour, config)[0]

        if elapsed_seconds <= thresholds["just_now"]:
            return labels.get("just_now", "刚才还在聊"), "刚才", "just_now"
        elif elapsed_seconds <= thresholds["this_session"]:
            mins = int(elapsed_seconds / 60)
            label = labels.get("this_session", "半小时内聊过").format(minutes=mins)
            return label, f"{mins}分钟前", "this_session"
        elif elapsed_seconds <= thresholds["hours"]:
            hours = int(elapsed_seconds / 3600)
            label = labels.get("hours", "{hours}小时前聊过").format(hours=hours)
            return label, f"{hours}小时前", "hours"
        elif elapsed_seconds <= thresholds["today"]:
            label = labels.get("today", "今天早些时候聊过").format(period=period)
            return label, "今天", "today"
        elif elapsed_seconds <= thresholds["yesterday"]:
            label = labels.get("yesterday", "昨天{period}聊过").format(period=period)
            return label, "昨天", "yesterday"
        elif elapsed_seconds <= thresholds["this_week"]:
            wd = weekdays[last_dt.weekday()] if last_dt.weekday() < len(weekdays) else "那天"
            label = labels.get("this_week", "上次是{weekday}").format(weekday=wd)
            return label, wd, "this_week"
        else:
            days = int(elapsed_seconds / 86400)
            label = labels.get("older", "好久不见（{days}天前）").format(days=days)
            return label, f"{days}天前", "older"

    def _classify_time_period(self, hour: int, config: dict):
        """分类时段"""
        periods = config.get(
            "time_periods",
            {
                "late_night": {"range": [0, 6], "label": "深夜", "simple": "深夜"},
                "morning": {"range": [6, 9], "label": "清晨", "simple": "早上"},
                "forenoon": {"range": [9, 12], "label": "上午", "simple": "上午"},
                "noon": {"range": [12, 14], "label": "中午", "simple": "中午"},
                "afternoon": {"range": [14, 18], "label": "下午", "simple": "下午"},
                "evening": {"range": [18, 22], "label": "晚上", "simple": "晚上"},
                "night": {"range": [22, 24], "label": "深夜", "simple": "深夜"},
            },
        )

        for key, info in periods.items():
            r = info["range"]
            if r[0] <= hour < r[1]:
                return info["label"], info["simple"], hour

        return "晚上", "晚上", hour

    def _build_platform_context(
        self,
        current_platform: str,
        last_platform: str,
        switched: bool,
        elapsed_label: str,
        all_platforms: list,
        config: dict,
    ) -> str:
        platform_names = config.get(
            "platform_names",
            {
                "qq": "QQ",
                "aiocqhttp": "QQ",
                "qqofficial": "QQ",
                "terminal": "终端",
                "desktop": "桌面端",
                "mobile": "手机端",
                "lark": "飞书",
                "weixin_official_account": "微信公众号",
                "weixin_ilink": "微信",
                "generic": "通用平台",
            },
        )
        templates = config.get(
            "platform_templates",
            {
                "switch": "之前在{last}上聊{elapsed}，现在换{current}了？",
                "same_first": "在{current}上{elapsed}",
                "same_later": "还是在{current}上~",
                "multi_platform": "在{platforms}上都聊过",
            },
        )

        cur_name = platform_names.get(current_platform, current_platform)
        last_name = platform_names.get(last_platform, last_platform)

        if switched:
            return templates.get("switch", "之前在{last}上聊{elapsed}，现在换{current}了？").format(
                last=last_name, elapsed=elapsed_label, current=cur_name
            )

        return templates.get("same_later", "还是在{current}上~").format(current=cur_name)

    def _format_duration(self, seconds: float, config: dict) -> str:
        duration_labels = config.get(
            "duration_labels",
            {
                "just_started": "刚开始聊",
                "minutes": "{minutes}分钟了",
                "hours": "{hours}小时{remain_min}分钟了",
            },
        )

        if seconds < 60:
            return duration_labels.get("just_started", "刚开始聊")
        elif seconds < 3600:
            mins = int(seconds / 60)
            return duration_labels.get("minutes", "{minutes}分钟了").format(minutes=mins)
        else:
            hours = int(seconds / 3600)
            remain_min = int((seconds % 3600) / 60)
            return duration_labels.get("hours", "{hours}小时{remain_min}分钟了").format(
                hours=hours, remain_min=remain_min
            )

    def build_raw_context(self, p: TimePerception) -> str:
        """构建结构化时间事实（交给 AI 自行表达）

        不生成预格式化的问候语，只提供客观事实，
        让 AI 根据当前人格和语境自然决定如何、是否提及时间。
        """
        platform_names = _get_config().get("platform_names", {})
        last_name = platform_names.get(p.last_platform, p.last_platform) if p.last_platform != "unknown" else "未知"
        cur_name = platform_names.get(p.platform, p.platform)

        last_dt_str = ""
        if p.elapsed_seconds > 0 and p.elapsed_seconds != float("inf"):
            last_dt = datetime.fromtimestamp(datetime.now().timestamp() - p.elapsed_seconds)
            last_dt_str = last_dt.strftime("%m-%d %H:%M")

        facts = [
            f"当前时间: {datetime.now().strftime('%H:%M')} ({p.time_period_simple})",
        ]

        if last_dt_str:
            facts.append(f"上次交互: {last_dt_str} (在{last_name})")
        elif p.elapsed_seconds == float("inf"):
            facts.append("上次交互: 无记录 (初次对话)")

        if p.elapsed_seconds > 0 and p.elapsed_seconds != float("inf"):
            facts.append(f"距今间隔: {p.elapsed_short}")

        if p.platform_switch:
            facts.append(f"平台切换: {last_name} → {cur_name}")

        if p.is_new_day:
            facts.append("新的一天: 是")

        if p.session_duration_seconds > 60:
            facts.append(f"本次会话时长: {p.session_duration_label}")

        if p.daily_streak > 1:
            facts.append(f"连续活跃: {p.daily_streak}天")

        if p.current_hour >= 23 or p.current_hour < 6:
            facts.append("深夜时段: 是")

        if p.all_platforms_seen:
            named = [platform_names.get(pl, pl) for pl in p.all_platforms_seen]
            facts.append(f"使用过的平台: {', '.join(named)}")

        return "\n".join(f"- {f}" for f in facts)


# 全局单例
_engine: Optional[TimeComparisonEngine] = None


def get_time_comparison_engine() -> TimeComparisonEngine:
    global _engine
    if _engine is None:
        _engine = TimeComparisonEngine()
    return _engine
