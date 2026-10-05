"""What Miya's camera is telling her, as one card for the conversation layer.

The camera loop, the presence tracker, the activity tracker and the impression
memory all worked, and none of it reached the model that answers Jia. Asked
"did you see me in the camera", she truthfully said the camera was not connected
to her - because, from where she was reading, it was not.

This module is that missing connection, and it is deliberately one function: a
single image-free card carrying her presence read, what Jia has been doing, her
most recent impression, and - just as important - what she currently cannot see.
Saying "the camera showed me nothing" must be possible, or she will invent a
plausible answer instead.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("screen_vision.context")

# Beyond this, an observation is history rather than something she is seeing now.
FRESH_SECONDS = 180.0
# How many of her recent impressions to carry. Two is enough for continuity
# ("still at the desk", "asleep a moment ago") without burying the current one.
RECENT_IMPRESSIONS = 2


def _human_age(seconds: float) -> str:
    """A plain phrase for how long ago something was, never "0 hours"."""
    if seconds < 90:
        return "刚刚"
    if seconds < 3600:
        return f"{max(1, int(round(seconds / 60)))} 分钟前"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} 小时前"
    return f"{max(1, int(round(seconds / 86400)))} 天前"


def vision_context_card(*, now: float | None = None) -> str:
    """One compact, image-free card describing Miya's camera perception.

    Empty string when she has no camera state at all, so a machine with no
    camera does not get a confusing "you cannot see" note in every prompt.
    """
    moment = time.time() if now is None else now
    lines: list[str] = []

    presence_text = ""
    try:
        from .presence import get_presence_tracker

        snapshot = get_presence_tracker().snapshot()
        if snapshot.updated_at:
            presence_text = snapshot.describe()
    except Exception:
        logger.debug("[VisionContext] 读取在场判断失败", exc_info=True)

    activity_text = ""
    recent_activity: list[str] = []
    try:
        from .activity import get_activity_tracker

        activity = get_activity_tracker().snapshot()
        if activity.kind:
            activity_text = activity.describe()
            recent_activity = list(activity.recent[:4])
    except Exception:
        logger.debug("[VisionContext] 读取活动判断失败", exc_info=True)

    latest: dict[str, Any] = {}
    try:
        from .vision_stream import get_vision_stream

        latest = get_vision_stream().latest() or {}
    except Exception:
        logger.debug("[VisionContext] 读取观察过程失败", exc_info=True)

    browser_card = ""
    try:
        from core.vision_context import get_vision_context

        browser_card = get_vision_context().build_card(source="camera", limit=4, max_age=FRESH_SECONDS, now=moment)
    except Exception:
        logger.debug("[VisionContext] 读取浏览器摄像头上下文失败", exc_info=True)

    interpreted = bool(latest.get("interpreted"))
    latest_at = float(latest.get("at") or 0)
    age = moment - latest_at if latest_at else float("inf")

    # Nothing observed at all: stay silent rather than assert a camera exists.
    if not presence_text and not activity_text and not latest_at and not browser_card:
        return ""

    lines.append("[弥娅的摄像头所见]")
    lines.append("- 事实边界：下面的解读是推测，观察意图和旧对话不是当前画面证据；"
                 "头歪、张嘴或静坐不能证明困倦。没有直接线索就不能确定杯子、水温、食物或喝水进度。")
    if browser_card:
        browser_lines = browser_card.splitlines()[1:]
        if browser_lines:
            lines.append("- 浏览器摄像头：" + "；".join(browser_lines[:3]))
    if presence_text:
        lines.append(f"- 在场：{presence_text}")
    if activity_text:
        lines.append(f"- 在做什么：{activity_text}")
    if recent_activity:
        lines.append("- 最近的迹象：" + " → ".join(reversed(recent_activity)))

    if latest_at and interpreted:
        lines.append(f"- 最近一次观察的解读（推测，{_human_age(age)}）：{latest.get('summary') or ''}")
        expression = str(latest.get("expression_text") or "").strip()
        if expression:
            lines.append(f"- 脸上的样子：{expression}")
    elif latest_at and latest.get("blank_frame"):
        # Blindness, not absence. These two must never be confusable: the first
        # means her camera failed, the second would mean Jia left.
        lines.append(f"- 最近一次观察（{_human_age(age)}）：摄像头那一路是全黑的，什么都没看到"
                     "——可能是设备息屏或没有程序在推流，不是佳不在了。")
    elif latest_at and not interpreted:
        reason = str(latest.get("degraded_reason") or "").strip()
        lines.append(f"- 最近一次观察没有成功解读（{_human_age(age)}）" + (f"：{reason}" if reason else ""))

    # Her own reasons for watching, so a question about the camera can be
    # answered in terms of what she is actually paying attention to. The event
    # carries the intents that applied at the time; fall back to the live list
    # only when there is no observation to read them from.
    intents = [str(text) for text in (latest.get("intent_texts") or [])][:3]
    if not intents:
        try:
            from .vision_agent import get_vision_agency

            intents = [item.text for item in get_vision_agency().intents(active_only=True)][:3]
        except Exception:
            logger.debug("[VisionContext] 读取观察意图失败", exc_info=True)
    if intents:
        lines.append("- 她自己在留意：" + "；".join(intents))

    # The honest part. Without this she said the camera was not connected while
    # holding a reading of Jia's face.
    if browser_card:
        lines.append("- 注意：上面的摄像头记录是近期观察，并非连续实时画面；不要猜测记录之后的变化。")
    elif not latest_at:
        lines.append("- 注意：摄像头还没有给出任何一次观察结果，现在看不到佳。")
    elif age > FRESH_SECONDS:
        lines.append(f"- 注意：上一次能看清是{_human_age(age)}，那之后没有新的观察——"
                     "这段时间她没在看他，不要当成现在的情形。")
    elif not interpreted:
        lines.append("- 注意：这一次只有本地线索，没有模型解读，判断要保守。")

    return "\n".join(lines)


def vision_context_summary(*, now: float | None = None) -> dict[str, Any]:
    """The same information as structured data, for diagnostics and the panel."""
    moment = time.time() if now is None else now
    out: dict[str, Any] = {"at": moment}
    try:
        from .presence import get_presence_tracker

        out["presence"] = get_presence_tracker().snapshot().to_dict()
    except Exception:
        out["presence"] = None
    try:
        from .activity import get_activity_tracker

        out["activity"] = get_activity_tracker().snapshot().to_dict()
    except Exception:
        out["activity"] = None
    try:
        from .vision_stream import get_vision_stream

        out["latest"] = get_vision_stream().latest()
    except Exception:
        out["latest"] = None
    out["card"] = vision_context_card(now=moment)
    return out
