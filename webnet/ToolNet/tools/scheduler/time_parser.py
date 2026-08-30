"""
智能时间表达式解析器

支持自然语言时间表达：
- 相对时间: "1分钟后", "2小时后", "30秒后"
- 绝对时间: "15:30", "2026-06-01 14:00"
- 日期偏移: "明天 15:00", "后天 8:30", "大后天 14:00"
- 星期偏移: "下周一 10:00", "下周三 9:00"
- 月份偏移: "下个月5号", "下月15日"
- 中文数字: "三点半", "五分钟后"
- 时段: "下午3点", "晚上8点", "早上9点"
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
WEEKDAY_NAMES = {
    "周一": 0,
    "周二": 1,
    "周三": 2,
    "周四": 3,
    "周五": 4,
    "周六": 5,
    "周日": 6,
    "星期天": 6,
    "星期一": 0,
    "星期二": 1,
    "星期三": 2,
    "星期四": 3,
    "星期五": 4,
    "星期六": 5,
    "星期日": 6,
}
PERIOD_MAP = {
    "凌晨": 0,
    "早上": 8,
    "上午": 9,
    "中午": 12,
    "下午": 12,
    "傍晚": 17,
    "晚上": 20,
    "半夜": 0,
}


def _parse_chinese_number(text: str) -> Optional[int]:
    """解析中文数字如 '五' → 5, '十二' → 12"""
    if not text:
        return None
    if text in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[text]
    if text.endswith("十") and len(text) == 2:
        return CHINESE_NUMBERS.get(text[0], 0) * 10
    if "十" in text and len(text) == 3:
        parts = text.split("十")
        return CHINESE_NUMBERS.get(parts[0], 0) * 10 + CHINESE_NUMBERS.get(parts[1], 0)
    return None


def _parse_time_str(time_str: str) -> Tuple[int, int]:
    """解析时间字符串 → (hour, minute)
    支持: '15:30', '3:00', '下午3点半', '晚上8点', '早上9:00'
    """
    time_str = time_str.strip()
    hour = 0
    minute = 0

    # 处理时段前缀
    offset = 0
    for period, poffset in PERIOD_MAP.items():
        if period in time_str:
            time_str = time_str.replace(period, "").strip()
            offset = poffset
            break

    # 处理 "X点" 格式
    point_match = re.search(r"(\d+|[一二三四五六七八九十]+)\s*点", time_str)
    if point_match:
        num_str = point_match.group(1)
        hour = int(num_str) if num_str.isdigit() else _parse_chinese_number(num_str) or 0

    # 处理 "X:" 格式
    colon_match = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if colon_match:
        hour = int(colon_match.group(1))
        minute = int(colon_match.group(2))

    # 处理 "X点半" 格式
    half_match = re.search(r"(\d+|[一二三四五六七八九十]+)点\s*半", time_str)
    if half_match:
        minute = 30

    # 应用时段偏移
    if offset >= 12:
        if hour < 12:
            hour += 12
    elif offset == 0 and hour == 12:
        hour = 0

    # 纯数字 "15:30"
    raw_match = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if raw_match:
        hour = int(raw_match.group(1))
        minute = int(raw_match.group(2))

    return hour, minute


def parse_smart_time(
    expression: str,
    reference: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    智能解析时间表达式

    Args:
        expression: 时间表达式，如 "1分钟后", "明天 15:30", "下周三 10:00"
        reference: 参考时间，默认为当前时间

    Returns:
        解析后的 datetime，无法解析返回 None
    """
    if not expression or not expression.strip():
        return None

    now = reference or datetime.now()
    expr = expression.strip()

    # ── 纯相对时间 ──
    # "X分钟后"
    match = re.search(r"(\d+)\s*分钟后", expr)
    if match:
        return now + timedelta(minutes=int(match.group(1)))
    # "X分钟后" 中文数字
    match = re.search(r"([一二三四五六七八九十]+)\s*分钟后", expr)
    if match:
        num = _parse_chinese_number(match.group(1))
        if num:
            return now + timedelta(minutes=num)

    # "X小时后"
    match = re.search(r"(\d+)\s*小时后", expr)
    if match:
        return now + timedelta(hours=int(match.group(1)))
    match = re.search(r"([一二三四五六七八九十]+)\s*小时后", expr)
    if match:
        num = _parse_chinese_number(match.group(1))
        if num:
            return now + timedelta(hours=num)

    # "X秒后"
    match = re.search(r"(\d+)\s*秒后", expr)
    if match:
        return now + timedelta(seconds=int(match.group(1)))

    # ── 日期偏移 + 时间 ──
    date_delta = timedelta(0)
    time_part = expr

    # "明天" / "后天" / "大后天"
    day_offsets = [
        (r"大后天", 3),
        (r"后天", 2),
        (r"明天", 1),
        (r"今天", 0),
    ]
    for pattern, days in day_offsets:
        if pattern in expr:
            date_delta = timedelta(days=days)
            time_part = expr.replace(pattern, "").strip()
            break

    # "下周X" / "下周一" 等
    for wd_name, wd_num in WEEKDAY_NAMES.items():
        if wd_name in expr:
            today_weekday = now.weekday()
            days_until = (wd_num - today_weekday) % 7
            if days_until == 0:
                days_until = 7  # 下周同一天 → +7天
            if "下周" in expr:
                days_until = max(days_until, (7 + wd_num - today_weekday) % 7)
                if days_until == 0:
                    days_until = 7
            date_delta = timedelta(days=days_until)
            time_part = expr.replace(wd_name, "").replace("下周", "").strip()
            break

    # "下个月X号" / "下月X日"
    match = re.search(r"下个?月\s*(\d+|[一二三四五六七八九十]+)\s*[号日]", expr)
    if match:
        num_str = match.group(1)
        day = int(num_str) if num_str.isdigit() else _parse_chinese_number(num_str) or 1
        month = now.month + 1
        year = now.year
        if month > 12:
            month = 1
            year += 1
        try:
            target_date = datetime(year, month, day, 0, 0)
            date_delta = target_date - now
            time_part = re.sub(r"下个?月\s*\d+\s*[号日]", "", expr).strip()
        except ValueError:
            pass

    # "下个月" 无具体日期 → 30天后
    if "下个月" in expr and not date_delta:
        date_delta = timedelta(days=30)
        time_part = expr.replace("下个月", "").strip()

    # 解析时间部分
    hour, minute = 0, 0
    if time_part:
        hour, minute = _parse_time_str(time_part)

    target = now + date_delta
    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # ── 纯 HH:MM 格式（无日期偏移） ──
    if not date_delta and not time_part:
        match = re.match(r"(\d{1,2}):(\d{2})", expr)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)  # 如果时间已过，默认明天
            return target

    # ── YYYY-MM-DD HH:MM ──
    match = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", expr)
    if match:
        try:
            return datetime.strptime(expr, "%Y-%m-%d %H:%M")
        except ValueError:
            pass

    # ── YYYY-MM-DD（无时间，默认当天 9:00） ──
    match = re.match(r"(\d{4}-\d{2}-\d{2})", expr)
    if match:
        try:
            return datetime.strptime(expr, "%Y-%m-%d").replace(hour=9)
        except ValueError:
            pass

    # ── 纯 HH:MM（已在上面处理了 time_part 里的） ──
    if hour > 0 or minute > 0:
        if target <= now:
            target += timedelta(days=1)
        return target

    return None
