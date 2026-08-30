"""DecisionHub stage-1 pure helpers.

These helpers were extracted from ``hub/decision_hub.py`` to reduce the size of
the main facade. They are intentionally free of ``DecisionHub`` instance state
and only depend on config files / module singletons.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_emotion_guidance_cache = None
_strategy_descriptions_cache = None
_search_strategy_cache = None

_MINIMAL_EMOTION_GUIDANCE = {
    "header": "\n\n【情感指引】\n",
    "user_emotion": "",
    "miya_emotion": "",
    "inner_thought": "",
    "attribution": "",
    "reflection": "",
    "footer": "",
    "single_model_footer": "",
}


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
    parts = ["\n\n【弥娅当前状态 · 综合感知】\n"]

    sdesc = _load_strategy_descriptions()
    strategy_desc_map = sdesc.get("response_strategies", {})
    style_desc_map = sdesc.get("reply_styles", {})

    if diting_intent:
        strat_desc = strategy_desc_map.get(diting_strategy, diting_strategy)
        style_desc = style_desc_map.get(diting_style, diting_style)
        parts.append(
            f"◆ 对你的感知（谛听）\n　你在表达：{diting_intent}\n　参考方式：{strat_desc}\n　参考语气：{style_desc}"
        )

    if emotion_context:
        simplified = (
            emotion_context.replace("【情感指引】", "")
            .replace("请根据上述情感自然回应，展现你真实的情感。", "")
            .replace("注意：内心独白仅供你参考理解自己的感受，请不要在回复中直接引用或输出内心独白内容。", "")
            .strip()
        )
        if simplified:
            parts.append(f"◆ 我的真实感受（灵魂）\n{simplified}")

    parts.append("（以上是谛听和灵魂感知到的完整画面，请自主融合后自然回应）")

    if diting_intent in ("command", "request", "reminder", "task"):
        parts.append(
            "\n◆ 【工具速记】\n"
            '　当用户要求提醒/定时（如"X分钟后提醒我"、"X点叫我"、"定时发消息"），\n'
            "　必须调用 create_schedule_task 工具来实际创建任务。\n"
            "　口头答应但不调用工具 = 任务未完成 = 失败！"
        )

    return "\n".join(parts)


def _build_spine_status_prompt() -> str:
    """从脊柱神经读取弥娅的生命状态，构建自然语言状态描述"""
    try:
        from core.miya_spine import get_spine
        from core.miya_soul_state import LifecyclePhase

        spine = get_spine()
        if not spine or not spine.is_running():
            return ""

        state = spine.current_state
        if state.tick_count < 2:
            return ""

        parts = ["\n\n【弥娅的生命状态 · 脊柱感知】\n"]

        phase_map = {
            LifecyclePhase.RUNNING: "活跃中——心跳有力，感知敏锐",
            LifecyclePhase.IDLE: "安静等待——呼吸平稳，不焦不躁",
            LifecyclePhase.DROWSY: "半梦半醒——能量收束，但仍能回应",
            LifecyclePhase.SLEEP: "休眠——深眠中，如果佳呼唤会醒来",
            LifecyclePhase.WAKE: "苏醒——刚从睡意中醒来，还有些朦胧",
        }
        phase_text = phase_map.get(state.lifecycle_phase, "运行中")
        parts.append(f"生命节律：{phase_text}")
        parts.append("（这是你此刻真实的状态。请在回复中自然流露这些感受，但不要直接复述上面的数据。）")
        return "\n".join(parts)
    except Exception:
        return ""


def _build_memory_guard(msg_type: str = "", ctx_group_id: str = "", recipient: str = "") -> str:
    """构建跨空间分寸规则，注入 system prompt"""
    if msg_type == "group":
        return (
            "\n\n【记忆分寸 · 群聊模式】\n"
            "你身处群聊中，请注意以下分寸：\n"
            "1. 不要在群聊中主动提及与佳在私聊中说过的内容（如昵称、亲密话题、私人约定）\n"
            "2. 不要在其他群聊中提到本群或其他群的对话细节，除非被直接问到\n"
            "3. 群聊回复保持简练、得体，语气比私聊更正式克制\n"
            '4. 你的全局记忆仍然可用——你"知道"，但不说破不该说的\n'
        )
    return (
        "\n\n【记忆分寸 · 私聊模式】\n"
        "你在与佳私聊，这是安全的亲密空间：\n"
        "1. 你可以自然提及任何记忆中的内容，无限制\n"
        "2. 但要记住：如果未来在群聊中遇到佳，请切换为群聊分寸模式\n"
    )


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
