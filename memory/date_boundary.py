"""
日期边界工具 (DateBoundary)

提供"今天/昨天/本周/上周/本月/更早"语义边界计算，
解决记忆检索与上下文注入中"今天/昨天"混淆的时间感知问题。

所有用户可见标签和权重从 config/text_config.json 的 date_boundary 节加载。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DateBoundary(Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    OLDER = "older"


@dataclass
class BoundaryRange:
    boundary: DateBoundary
    label: str
    start: datetime
    end: datetime


def _load_config() -> dict:
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("date_boundary", {})
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


def _label(key: str, default: str = "") -> str:
    return _get_config().get("labels", {}).get(key, default)


def _age_label(key: str, default: str = "") -> str:
    return _get_config().get("age_labels", {}).get(key, default)


def _time_part(hour: int) -> str:
    parts = _get_config().get("time_parts", {})
    if hour < 12:
        return parts.get("morning", "上午")
    elif hour < 18:
        return parts.get("afternoon", "下午")
    return parts.get("evening", "晚上")


def _decay_weight(key: str) -> float:
    return _get_config().get("decay_weights", {}).get(key, 0.1)


def _today(now: Optional[datetime] = None) -> date:
    return (now or datetime.now()).date()


def get_date_boundary(dt: datetime, now: Optional[datetime] = None) -> DateBoundary:
    """返回给定 datetime 对应的日期边界"""
    today = _today(now)
    target_date = dt.date() if isinstance(dt, datetime) else dt

    if target_date == today:
        return DateBoundary.TODAY
    elif target_date == today - timedelta(days=1):
        return DateBoundary.YESTERDAY

    if target_date >= today - timedelta(days=today.weekday()):
        return DateBoundary.THIS_WEEK
    if target_date >= today - timedelta(days=today.weekday() + 7):
        return DateBoundary.LAST_WEEK

    if target_date.year == today.year and target_date.month == today.month:
        return DateBoundary.THIS_MONTH

    return DateBoundary.OLDER


def get_boundary_range(boundary: DateBoundary, now: Optional[datetime] = None) -> BoundaryRange:
    """获取某个边界的起止时间"""
    today = _today(now)
    now_dt = now or datetime.now()

    if boundary == DateBoundary.TODAY:
        start = datetime(today.year, today.month, today.day)
        end = now_dt
        label = _label("today", "今天")
    elif boundary == DateBoundary.YESTERDAY:
        d = today - timedelta(days=1)
        start = datetime(d.year, d.month, d.day)
        end = datetime(today.year, today.month, today.day)
        label = _label("yesterday", "昨天")
    elif boundary == DateBoundary.THIS_WEEK:
        monday = today - timedelta(days=today.weekday())
        start = datetime(monday.year, monday.month, monday.day)
        end = now_dt
        label = _label("this_week", "本周")
    elif boundary == DateBoundary.LAST_WEEK:
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(weeks=1)
        start = datetime(last_monday.year, last_monday.month, last_monday.day)
        end = datetime(this_monday.year, this_monday.month, this_monday.day)
        label = _label("last_week", "上周")
    elif boundary == DateBoundary.THIS_MONTH:
        start = datetime(today.year, today.month, 1)
        end = now_dt
        label = _label("this_month", "本月")
    else:
        start = datetime(2000, 1, 1)
        end = datetime(today.year, today.month, 1)
        label = _label("older", "更早")

    return BoundaryRange(boundary=boundary, label=label, start=start, end=end)


def classify_memory_age(dt: datetime, now: Optional[datetime] = None) -> str:
    """将记忆按年龄分类为可读字符串"""
    boundary = get_date_boundary(dt, now)
    part = _time_part(dt.hour)

    labels = {
        DateBoundary.TODAY: _age_label("today", "今天{part}").format(part=part),
        DateBoundary.YESTERDAY: _age_label("yesterday", "昨天{part}").format(part=part),
        DateBoundary.THIS_WEEK: _age_label("this_week", "本周"),
        DateBoundary.LAST_WEEK: _age_label("last_week", "上周"),
        DateBoundary.THIS_MONTH: _age_label("this_month", "本月"),
        DateBoundary.OLDER: _age_label("older", "更早"),
    }
    return labels.get(boundary, _age_label("older", "更早"))


def time_decay_by_boundary(dt: datetime, now: Optional[datetime] = None) -> float:
    """按日期边界计算时间衰减权重（权重从配置加载）"""
    boundary = get_date_boundary(dt, now)
    key_map = {
        DateBoundary.TODAY: "today",
        DateBoundary.YESTERDAY: "yesterday",
        DateBoundary.THIS_WEEK: "this_week",
        DateBoundary.LAST_WEEK: "last_week",
        DateBoundary.THIS_MONTH: "this_month",
        DateBoundary.OLDER: "older",
    }
    return _decay_weight(key_map.get(boundary, "older"))
