"""
弥娅思考记录查询工具

用于查询弥娅的思考过程、情绪分析、内心独白等认知记忆
"""

import logging
from typing import Any, Callable, Dict, List

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

# 操作分发表
_ACTION_FORMATS: Dict[str, tuple[str, str, Callable]] = {}


def _fmt_recent(rec) -> List[str]:
    """格式化最近思考记录"""
    lines = []
    inner = (rec.inner_thought if hasattr(rec, "inner_thought") else rec.get("inner_thought", ""))[:40]
    thinking = (rec.thinking if hasattr(rec, "thinking") else rec.get("thinking", ""))[:60]
    emotions = rec.emotions if hasattr(rec, "emotions") else rec.get("emotions", {})
    emo_str = ", ".join([f"{k}({v})" for k, v in list(emotions.items())[:3]]) if emotions else "无"
    lines.append(f"  内心: {inner}")
    lines.append(f"  情绪: {emo_str}")
    if thinking:
        lines.append(f"  思考: {thinking}")
    return lines


def _fmt_inner(rec) -> List[str]:
    """格式化内心独白"""
    inner = rec.inner_thought if hasattr(rec, "inner_thought") else rec.get("inner_thought", "")
    return [f"  {inner}"] if inner else []


def _fmt_emotion(rec) -> List[str]:
    """格式化情绪"""
    emotions = rec.emotions if hasattr(rec, "emotions") else rec.get("emotions", {})
    if emotions:
        return [f"  {', '.join([f'{k}({v})' for k, v in emotions.items()])}"]
    return []


def _fmt_attribution(rec) -> List[str]:
    """格式化归因"""
    attr = rec.attribution if hasattr(rec, "attribution") else rec.get("attribution", "")
    return [f"  {attr}"] if attr else []


def _fmt_full(rec) -> List[str]:
    """格式化完整记录"""
    lines = []
    inner = rec.inner_thought if hasattr(rec, "inner_thought") else rec.get("inner_thought", "")
    attr = rec.attribution if hasattr(rec, "attribution") else rec.get("attribution", "")
    refl = rec.reflection if hasattr(rec, "reflection") else rec.get("reflection", "")
    emotions = rec.emotions if hasattr(rec, "emotions") else rec.get("emotions", {})
    thinking = rec.thinking if hasattr(rec, "thinking") else rec.get("thinking", "")

    if inner:
        lines.append(f"内心: {inner}")
    if emotions:
        lines.append(f"情绪: {', '.join([f'{k}({v})' for k, v in emotions.items()])}")
    if attr:
        lines.append(f"归因: {attr}")
    if refl:
        lines.append(f"反思: {refl}")
    if thinking:
        lines.append(f"思考: {thinking[:80]}")
    return lines


# 操作配置: (emoji, 标题, 格式化函数)
_ACTION_CONFIG: Dict[str, tuple[str, str, Callable, str]] = {
    "recent": ("🧠", "最近的思考记录", _fmt_recent, "暂无思考记录"),
    "inner": ("💭", "内心独白历史", _fmt_inner, "暂无内心独白记录"),
    "emotion": ("💗", "情绪历史", _fmt_emotion, "暂无情绪记录"),
    "attribution": ("🎯", "归因分析历史", _fmt_attribution, "暂无归因记录"),
    "full": ("📝", "完整认知记录", _fmt_full, "暂无认知记录"),
}


class ThinkingQueryTool(BaseTool):
    """思考记录查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "thinking_query",
            "description": """弥娅思考记录查询工具，用于查看弥娅的思考过程、情绪分析、内心独白等。

可查询内容：
1. 最近思考 - 查看最近的思考记录
2. 内心独白 - 查看内心独白历史
3. 情绪历史 - 查看情绪变化
4. 归因分析 - 查看归因历史
5. 完整记录 - 查看完整认知记录

使用方式：
- 思考最近 [数量]
- 思考内心 [数量]
- 思考情绪 [数量]
- 思考归因 [数量]
- 思考完整 [数量]""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型: recent/inner/emotion/attribution/full",
                        "enum": ["recent", "inner", "emotion", "attribution", "full"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制",
                        "default": 5,
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        """执行思考记录查询"""
        args = args or {}
        action = args.get("action", "recent")
        limit = args.get("limit", 5)

        user_id = str(context.user_id) if context.user_id else None
        if not user_id:
            return "无法确定用户身份"

        if action not in _ACTION_CONFIG:
            return "未知操作类型"

        try:
            emoji, title, fmt_func, empty_msg = _ACTION_CONFIG[action]
            return await self._query_cognition(user_id, limit, emoji, title, fmt_func, empty_msg)
        except Exception as e:
            logger.error("思考记录查询失败: %s", e)
            return f"查询失败: {str(e)[:100]}"

    async def _query_cognition(
        self,
        user_id: str,
        limit: int,
        emoji: str,
        title: str,
        fmt_func: Callable,
        empty_msg: str,
    ) -> str:
        """通用的认知记录查询方法 — 消除 5 个方法的重复代码"""
        from memory.cognition_cache import get_cognition_cache

        cache = get_cognition_cache()
        records = await cache.get_recent(user_id, limit)

        lines: List[str] = []

        if records:
            lines.append(f"{emoji} {title} ({len(records)}条)")
            lines.append("=" * 50)
            for i, rec in enumerate(records, 1):
                lines.append(f"\n{i}.")
                formatted = fmt_func(rec)
                if formatted:
                    lines.extend(formatted)
            return "\n".join(lines) if len(lines) > 2 else empty_msg

        # 缓存为空，直接从数据库查询
        from memory import retrieve_cognition

        results = await retrieve_cognition(user_id, limit)
        if not results:
            return empty_msg

        lines.append(f"{emoji} {title} ({len(results)}条)")
        lines.append("=" * 60 if len(results) < 10 else "=" * 50)
        for i, rec in enumerate(results, 1):
            if emoji == "📝":
                lines.append(f"\n--- 第{i}条 ---")
            else:
                lines.append(f"\n{i}.")
            formatted = fmt_func(rec)
            if formatted:
                lines.extend(formatted)

        return "\n".join(lines) if len(lines) > 2 else empty_msg


TOOL_CLASS = ThinkingQueryTool
