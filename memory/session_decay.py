"""
会话时间衰减模块

职责：
- 统一管理会话冷却倒计时阈值
- 根据距上次活跃时间判断会话层级（hot/warm/cold/dormant）
- 提供分层恢复策略
- 规则摘要生成
"""

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionPhase(str, Enum):
    """会话阶段"""

    HOT = "hot"  # ≤30min：活跃，完整恢复
    WARM = "warm"  # 30min-6h：摘要恢复
    COLD = "cold"  # 6h-24h：标签恢复
    YESTERDAY = "yesterday"  # 24h-48h：昨天发生过，保留关键摘要
    DORMANT = "dormant"  # >48h：不恢复


_DEFAULT_CONFIG = {
    "enabled": True,
    "hot_window_minutes": 30,
    "warm_window_hours": 6,
    "cold_window_hours": 24,
    "yesterday_window_hours": 48,
    "ai_summary_min_messages": 10,
    "ai_summary_enabled": True,
    "phase_labels": {
        "hot": "活跃对话中",
        "warm": "之前的对话",
        "cold_today": "今日有过对话",
        "cold_yesterday": "昨日有过对话",
        "yesterday": "昨天的对话",
        "dormant": "新对话",
        "warm_with_elapsed": "之前聊过（已过{hours}小时）",
        "warm_with_elapsed_zero": "之前聊过",
        "cold_with_elapsed": "{day_label}有过对话（已过{hours}小时）",
        "yesterday_with_elapsed": "昨天聊过（已过{hours}小时）",
    },
}


def _load_decay_config() -> dict:
    """从 text_config.json 加载衰减配置"""
    try:
        import json

        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                full = json.load(f)
            return full.get("session_decay", _DEFAULT_CONFIG)
    except Exception as e:
        logger.warning(f"[衰减] 配置加载失败: {e}")
    return _DEFAULT_CONFIG


def get_decay_config() -> dict:
    return _load_decay_config()


def get_phase(elapsed_seconds: float) -> SessionPhase:
    """根据距上次活跃时间判断会话阶段"""
    config = _load_decay_config()
    if not config.get("enabled", True):
        return SessionPhase.HOT

    hot_seconds = config.get("hot_window_minutes", 30) * 60
    warm_seconds = config.get("warm_window_hours", 6) * 3600
    cold_seconds = config.get("cold_window_hours", 24) * 3600
    yesterday_seconds = config.get("yesterday_window_hours", 48) * 3600

    if elapsed_seconds <= hot_seconds:
        return SessionPhase.HOT
    elif elapsed_seconds <= warm_seconds:
        return SessionPhase.WARM
    elif elapsed_seconds <= cold_seconds:
        return SessionPhase.COLD
    elif elapsed_seconds <= yesterday_seconds:
        return SessionPhase.YESTERDAY
    else:
        return SessionPhase.DORMANT


def get_phase_description(
    phase: SessionPhase,
    elapsed_minutes: Optional[float] = None,
    last_active_time: Optional[float] = None,
) -> str:
    """获取会话阶段的中文描述（标签来自配置文件 session_decay.phase_labels）"""
    config = _load_decay_config()
    labels = config.get("phase_labels", _DEFAULT_CONFIG["phase_labels"])

    now = datetime.now()
    is_today = True
    if last_active_time is not None and last_active_time > 0:
        last_date = datetime.fromtimestamp(last_active_time)
        is_today = last_date.date() == now.date()

    default_desc = labels.get("dormant", "新对话")

    if elapsed_minutes is not None and phase != SessionPhase.HOT:
        if phase == SessionPhase.WARM:
            hours = int(elapsed_minutes / 60)
            if hours > 0:
                desc = labels.get("warm_with_elapsed", "之前聊过（已过{hours}小时）").format(hours=hours)
            else:
                desc = labels.get("warm_with_elapsed_zero", "之前聊过")
        elif phase == SessionPhase.COLD:
            hours = int(elapsed_minutes / 60)
            day_label = "今日" if is_today else "昨日"
            desc = labels.get("cold_with_elapsed", "{day_label}有过对话（已过{hours}小时）").format(
                day_label=day_label, hours=hours
            )
        elif phase == SessionPhase.YESTERDAY:
            hours = int(elapsed_minutes / 60)
            desc = labels.get("yesterday_with_elapsed", "昨天聊过（已过{hours}小时）").format(hours=hours)
        else:
            desc = default_desc
    else:
        if phase == SessionPhase.HOT:
            desc = labels.get("hot", "活跃对话中")
        elif phase == SessionPhase.WARM:
            desc = labels.get("warm", "之前的对话")
        elif phase == SessionPhase.COLD:
            key = "cold_today" if is_today else "cold_yesterday"
            desc = labels.get(key, "今日有过对话")
        elif phase == SessionPhase.YESTERDAY:
            desc = labels.get("yesterday", "昨天的对话")
        elif phase == SessionPhase.DORMANT:
            desc = labels.get("dormant", "新对话")
        else:
            desc = default_desc

    return desc


def generate_topic_summary(messages: list, max_preview: int = 2) -> str:
    """规则摘要：从消息列表提取首尾关键信息"""
    if not messages:
        return ""

    # 消息格式: "sender: content" 或 "sender[id]: content"
    def _extract_content(msg: str) -> str:
        if ":" in msg:
            return msg.split(":", 1)[1].strip()[:40]
        return msg.strip()[:40]

    def _extract_sender(msg: str) -> str:
        if ":" in msg:
            return msg.split(":", 1)[0].strip()
        return ""

    if len(messages) == 1:
        return f"最后一条: {_extract_sender(messages[0])}: {_extract_content(messages[0])}"

    first_content = _extract_content(messages[0])
    last_content = _extract_content(messages[-1])
    first_sender = _extract_sender(messages[0])

    if first_content == last_content:
        return f"{first_sender}: {first_content}"

    return f"{first_sender} 从「{first_content}」聊到「{last_content}」"


def generate_cold_summary(recent_messages: list, last_topics: Optional[list] = None) -> str:
    """冷层摘要：话题标签 + 最后 1-2 条原文"""

    parts = []

    if last_topics:
        unique_topics = list(dict.fromkeys(last_topics))[:5]
        parts.append(f"聊过: {'、'.join(unique_topics)}")

    if recent_messages:
        last_msgs = recent_messages[-2:]
        for msg in last_msgs:
            if ":" in msg:
                sender, content = msg.split(":", 1)
                parts.append(f"{sender.strip()} 说: {content.strip()[:50]}")
            else:
                parts.append(msg.strip()[:50])

    return " | ".join(parts) if parts else ""


def get_warm_summary(messages: list, topic_history: Optional[list] = None) -> str:
    """温层摘要：话题 + 规则摘要"""
    config = _load_decay_config()
    min_for_ai = config.get("ai_summary_min_messages", 10)

    topic_str = ""
    if topic_history:
        unique = list(dict.fromkeys(topic_history))[:3]
        topic_str = f"【{'、'.join(unique)}】"

    rule_summary = generate_topic_summary(messages)

    if len(messages) >= min_for_ai and config.get("ai_summary_enabled", True):
        return (
            f"[之前的对话] {topic_str}{rule_summary}\n"
            f"[提示] 以上为上次对话摘要，请自然接续（不要生硬地问'我们聊到哪了'）"
        )
    else:
        return f"[之前的对话] {topic_str}{rule_summary}\n[提示] 以上为上次对话摘要，请自然接续"


def format_elapsed_time(seconds: float) -> str:
    """格式化时间间隔为可读字符串"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds / 60)}分钟"
    else:
        hours = seconds / 3600
        if hours < 24:
            return f"{hours:.1f}小时"
        else:
            return f"{hours / 24:.1f}天"


__all__ = [
    "SessionPhase",
    "get_decay_config",
    "get_phase",
    "get_phase_description",
    "generate_topic_summary",
    "generate_cold_summary",
    "get_warm_summary",
    "format_elapsed_time",
]
