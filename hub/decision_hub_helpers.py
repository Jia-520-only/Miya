"""DecisionHub stage-1 pure helpers.

These helpers were extracted from ``hub/decision_hub.py`` to reduce the size of
the main facade. They are intentionally free of ``DecisionHub`` instance state
and only depend on config files / module singletons.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.text_loader import get_text

logger = logging.getLogger(__name__)

_emotion_guidance_cache = None
_strategy_descriptions_cache = None
_search_strategy_cache = None

_MINIMAL_EMOTION_GUIDANCE = {
    "header": "",
    "user_emotion": "",
    "miya_emotion": "",
    "inner_thought": "",
    "attribution": "",
    "reflection": "",
    "footer": "",
    "single_model_footer": "",
}


def _format_reply_context(reply_info) -> str:
    """Format a quoted message without touching the active message fields."""
    if not reply_info:
        return ""

    guidance = _get_emotion_guidance()
    sender_default = guidance.get("unknown_sender", "")

    if hasattr(reply_info, "get"):
        sender_name = reply_info.get("sender_name", sender_default)
        content = reply_info.get("content", "") or ""
        image_url = reply_info.get("image_url")
    elif hasattr(reply_info, "sender_name"):
        sender_name = getattr(reply_info, "sender_name", sender_default)
        content = getattr(reply_info, "content", "") or ""
        image_url = getattr(reply_info, "image_url", None)
    else:
        sender_name, content, image_url = sender_default, "", None

    content = str(content)[:100]
    template = guidance.get("reply_context_template", "")
    result = template.format(sender_name=sender_name, content=content) if template else ""
    if image_url:
        image_template = guidance.get("reply_context_image", "")
        if image_template:
            result += image_template.format(image_url=image_url)
    return result


def _load_strategy_descriptions() -> dict:
    """加载策略描述映射（带缓存）"""
    global _strategy_descriptions_cache
    if _strategy_descriptions_cache is not None:
        return _strategy_descriptions_cache
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        _strategy_descriptions_cache = cfg.get("strategy_descriptions", {})
    except Exception:
        _strategy_descriptions_cache = {}
    return _strategy_descriptions_cache


def _get_emotion_guidance() -> dict:
    """加载情感引导配置（带缓存）"""
    global _emotion_guidance_cache
    if _emotion_guidance_cache is not None:
        return _emotion_guidance_cache
    try:
        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        eg = cfg.get("emotion_guidance")
        if eg and eg.get("header"):
            _emotion_guidance_cache = eg
        else:
            logger.warning("[情感指引] text_config.json 缺少 emotion_guidance 配置段，使用最小兜底")
            _emotion_guidance_cache = _MINIMAL_EMOTION_GUIDANCE
    except Exception as e:
        logger.error(f"[情感指引] 加载 text_config.json 失败: {e}，使用最小兜底")
        _emotion_guidance_cache = _MINIMAL_EMOTION_GUIDANCE
    return _emotion_guidance_cache


def _build_integrated_status(
    strategy_guidance: str,
    emotion_context: str,
    diting_strategy: str,
    diting_style: str,
    diting_intent: str,
) -> str:
    """融合谛听策略与灵魂情绪为一幅完整的弥娅状态画像"""
    guidance = _get_emotion_guidance()
    parts = [guidance.get("integrated_status_header", "")]

    sdesc = _load_strategy_descriptions()
    strategy_desc_map = sdesc.get("response_strategies", {})
    style_desc_map = sdesc.get("reply_styles", {})

    if diting_intent:
        strat_desc = strategy_desc_map.get(diting_strategy, diting_strategy)
        style_desc = style_desc_map.get(diting_style, diting_style)
        parts.append(
            guidance.get("strategy_template", "").format(
                intent=diting_intent, strategy=strat_desc, style=style_desc
            )
        )

    if emotion_context:
        simplified = emotion_context
        for marker in guidance.get("integrated_strip_texts", []):
            simplified = simplified.replace(marker, "")
        simplified = simplified.strip()
        if simplified:
            parts.append(guidance.get("soul_template", "{context}").format(context=simplified))

    integrated_footer = guidance.get("integrated_footer", "")
    if integrated_footer:
        parts.append(integrated_footer)

    if diting_strategy == "question_back":
        question_guidance = guidance.get("question_back_guidance", "")
        if question_guidance:
            parts.append(question_guidance)

    if diting_intent in ("command", "request", "reminder", "task"):
        tool_guidance = guidance.get("tool_guidance", "")
        if tool_guidance:
            parts.append(tool_guidance)

    return "\n".join(parts)


def _build_spine_status_prompt() -> str:
    """从脊柱神经读取弥娅的生命状态，构建自然语言状态描述"""
    try:
        from core.miya_spine import get_spine

        spine = get_spine()
        if not spine or not spine.is_running():
            return ""

        state = spine.current_state
        if state.tick_count < 2:
            return ""

        guidance = get_text("context_guidance", {})
        parts = [guidance.get("spine_header", "")]
        phase_map = guidance.get("spine_phases", {})
        phase_key = getattr(state.lifecycle_phase, "value", state.lifecycle_phase)
        phase_text = phase_map.get(phase_key, guidance.get("spine_default_phase", ""))
        parts.append(guidance.get("spine_phase_template", "").format(phase=phase_text))
        parts.append(guidance.get("spine_footer", ""))
        return "\n".join(parts)
    except Exception:
        return ""


def _build_memory_guard(msg_type: str = "", ctx_group_id: str = "", recipient: str = "") -> str:
    """构建跨空间分寸规则，注入 system prompt"""
    if msg_type == "group" or str(ctx_group_id or "") not in {"", "0", "None", "null"}:
        return get_text("context_guidance.memory_guard_group")
    return get_text("context_guidance.memory_guard_private")


def _is_reminder_request(user_content: str) -> bool:
    """检测用户消息是否包含提醒/定时请求"""
    if not user_content:
        return False
    import re

    return bool(
        re.search(
            r"提醒我|提醒|叫我|喊我|定时|分钟后|小时后|几点|秒后|分钟",
            user_content,
        )
    )


__all__ = [
    "_build_integrated_status",
    "_build_memory_guard",
    "_build_spine_status_prompt",
    "_get_emotion_guidance",
    "_is_reminder_request",
    "_load_strategy_descriptions",
    "_MINIMAL_EMOTION_GUIDANCE",
]
