"""
时间表达式解析器 (TemporalParser)

把自然语言时间表达式转换为精确的 datetime 范围。
时间范围从 text_config.json 加载，可随时调整无需改代码。

用于记忆检索时自动设置时间过滤范围。
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class TemporalRange:
    """时间范围"""

    def __init__(self, start: datetime, end: datetime, label: str):
        self.start = start
        self.end = end
        self.label = label

    def __repr__(self):
        return f"TemporalRange({self.label}: {self.start.isoformat()} ~ {self.end.isoformat()})"


def _load_config() -> dict:
    """从 text_config.json 加载时间解析配置"""
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("temporal_parser", {})
    except Exception:
        pass
    return {}


_CONFIG = _load_config()


def _build_patterns() -> dict:
    """从配置动态构建时间表达式 → 计算函数映射"""
    patterns = {}

    # 天级表达式 (date_expressions)
    date_expr = _CONFIG.get("date_expressions", {})
    for label, offset in date_expr.items():
        if isinstance(offset, int):
            patterns[label] = _make_day_fn(offset)
        else:
            patterns[label] = None  # 动态处理

    # 周级表达式
    week_expr = _CONFIG.get("week_expressions", {})
    for label, offset in week_expr.items():
        patterns[label] = _make_week_fn(offset)

    # 月级表达式
    month_expr = _CONFIG.get("month_expressions", {})
    for label, offset in month_expr.items():
        patterns[label] = _make_month_fn(offset)

    # 模糊天级
    fuzzy_days = _CONFIG.get("fuzzy_days", {})
    for label, days in fuzzy_days.items():
        patterns[label] = _make_fuzzy_day_fn(days)

    # 模糊分钟级
    fuzzy_mins = _CONFIG.get("fuzzy_minutes", {})
    for label, mins in fuzzy_mins.items():
        patterns[label] = _make_fuzzy_min_fn(mins)

    # 动态正则（数值+单位）
    dyn = _CONFIG.get("dynamic_patterns", {})
    for _ptag, regex_str in dyn.items():
        if regex_str:
            patterns[regex_str] = None  # _parse_dynamic 处理

    return patterns


def _make_day_fn(offset: int):
    def fn(now: datetime):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if offset < 0 or offset > 0:
            start += timedelta(days=offset)
        end = start + timedelta(days=1)
        return start, end

    return fn


def _make_week_fn(offset: int):
    def fn(now: datetime):
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start = monday + timedelta(weeks=offset)
        end = start + timedelta(weeks=1)
        if offset == 0:
            end = now
        return start, end

    return fn


def _make_month_fn(offset: int):
    def fn(now: datetime):
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if offset < 0:
            start = (first_day - timedelta(days=1)).replace(day=1)
        elif offset > 0:
            if now.month == 12:
                start = now.replace(
                    year=now.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                start = now.replace(
                    month=now.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
        else:
            start = first_day
        if offset == 0:
            end = now
        else:
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1)
            else:
                end = start.replace(month=start.month + 1, day=1)
        return start, end

    return fn


def _make_fuzzy_day_fn(days: int):
    def fn(now: datetime):
        return now - timedelta(days=days), now

    return fn


def _make_fuzzy_min_fn(mins: int):
    def fn(now: datetime):
        return now - timedelta(minutes=mins), now

    return fn


# 在模块加载时构建模式表（配置可热更新）
_PATTERNS = _build_patterns()


def _parse_dynamic(text: str, now: datetime) -> Optional[TemporalRange]:
    """解析数值型动态时间表达式"""
    dyn = _CONFIG.get("dynamic_patterns", {})

    # "最近N天" / "过去N天" / "这几天"
    regex_str = dyn.get("recent_days", r"(最近|过去|这几天)\s*(\d+)?\s*天")
    m = re.search(regex_str, text)
    if m:
        raw_days = m.group(2) or "1"
        days = int(raw_days) if raw_days.isdigit() else 1
        if not raw_days.isdigit() and m.group(1) in _CONFIG.get("fuzzy_days", {}):
            days = _CONFIG["fuzzy_days"][m.group(1)]
        return TemporalRange(
            now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days),
            now,
            f"最近{days}天",
        )

    # "N天前"
    regex_str = dyn.get("days_ago", r"(\d+)\s*天前")
    m = re.search(regex_str, text)
    if m:
        days = int(m.group(1))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
        return TemporalRange(start, start + timedelta(days=1), f"{days}天前")

    # "N小时前"
    regex_str = dyn.get("hours_ago", r"(\d+)\s*小时前")
    m = re.search(regex_str, text)
    if m:
        hours = int(m.group(1))
        return TemporalRange(now - timedelta(hours=hours), now, f"{hours}小时前")

    # "N分钟前"
    regex_str = dyn.get("minutes_ago", r"(\d+)\s*分钟前")
    m = re.search(regex_str, text)
    if m:
        mins = int(m.group(1))
        return TemporalRange(now - timedelta(minutes=mins), now, f"{mins}分钟前")

    return None


def reload_config():
    """热更新配置"""
    global _CONFIG, _PATTERNS
    _CONFIG = _load_config()
    _PATTERNS = _build_patterns()


def parse_temporal(text: str, now: Optional[datetime] = None) -> Optional[TemporalRange]:
    """解析文本中的时间表达式

    Args:
        text: 用户输入文本
        now: 当前时间（默认 datetime.now()）

    Returns:
        TemporalRange 或 None
    """
    if now is None:
        now = datetime.now()

    # 先解析数值型动态表达式（更精确）
    dyn_result = _parse_dynamic(text, now)
    if dyn_result:
        return dyn_result

    # 按长度降序匹配固定表达式（优先匹配更具体的）
    sorted_keys = sorted(
        [k for k in _PATTERNS if isinstance(k, str)],
        key=len,
        reverse=True,
    )
    for pattern_str in sorted_keys:
        if pattern_str in text:
            fn = _PATTERNS[pattern_str]
            if fn is not None:
                start, end = fn(now)
                return TemporalRange(start, end, pattern_str)

    # 无匹配 → 如果文本包含"天""晚""前""最近"等模糊词，用默认回退
    fuzzy_indicators = ["天", "晚", "前", "最近", "之前", "前一天"]
    if any(ind in text for ind in fuzzy_indicators):
        fallback_days = _CONFIG.get("default_fallback_days", 3)
        return TemporalRange(
            now - timedelta(days=fallback_days),
            now,
            f"模糊时间(~{fallback_days}天)",
        )

    return None


def extract_temporal_keywords(text: str) -> list[str]:
    """从文本中提取所有匹配的时间关键词"""
    keywords = []

    for pattern_str in _PATTERNS:
        if isinstance(pattern_str, str) and pattern_str in text:
            keywords.append(pattern_str)

    # 也检查数值模式
    dyn = _CONFIG.get("dynamic_patterns", {})
    regex_str = dyn.get("recent_days", r"(最近|过去|这几天)\s*(\d+)?\s*天")
    m = re.search(regex_str, text)
    if m:
        raw_days = m.group(2) or ""
        keywords.append(f"最近{raw_days}天" if raw_days else "最近")

    regex_str = dyn.get("days_ago", r"(\d+)\s*天前")
    m = re.search(regex_str, text)
    if m:
        keywords.append(f"{m.group(1)}天前")

    return keywords
