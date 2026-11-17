"""Shared event-time conversion for memory storage and prompt rendering.

Memory's legacy date filters use local, naive datetimes. Convert timezone-aware
platform timestamps to that same clock before persisting or comparing them.
"""

from datetime import datetime
from typing import Any


def local_datetime(value: Any) -> datetime | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, datetime):
            result = value
        elif isinstance(value, (int, float)) or str(value).strip().replace(".", "", 1).isdigit():
            stamp = float(value)
            # Some adapters supply milliseconds, OneBot supplies seconds.
            result = datetime.fromtimestamp(stamp / 1000 if stamp > 100_000_000_000 else stamp)
        else:
            result = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return result.astimezone().replace(tzinfo=None) if result.tzinfo else result
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def event_timestamp(perception: dict) -> str:
    for key in ("timestamp", "time", "created_at"):
        parsed = local_datetime(perception.get(key))
        if parsed is not None:
            return parsed.isoformat()
    return datetime.now().isoformat()


def time_label(value: Any) -> str:
    parsed = local_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "时间未知"


def clock_context() -> str:
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}"
    return f"当前时间: {now:%Y-%m-%d %H:%M:%S}（UTC{offset}）；今天/昨天按此日期区分，历史消息时间表示当时。"
