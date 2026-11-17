"""Unified knowledge with audience-aware expression, shared with the soul.

Private memories remain available to cognition and reply generation. Privacy is
enforced on speech, without reducing the soul to a fixed set of feeling labels.
"""

from __future__ import annotations

import asyncio
import logging
import re
from enum import Enum
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class PrivacyLevel(str, Enum):
    PUBLIC = "public"
    REVIEW = "review"
    PRIVATE = "private"


_SENSITIVE_RE = re.compile(
    r"私密|隐私|秘密|保密|别.{0,4}告诉|不要.{0,4}告诉|不能.{0,4}告诉|只属于我们|"
    r"亲密|暧昧|亲亲|亲吻|接吻|贴贴|抱抱|搂.{0,4}怀里|钻.{0,4}怀里|"
    r"涩涩|色情|性爱|性行为|裸|自慰|做爱|上床|床上|阴部|生殖|"
    r"病情|疾病|手术|诊断|心脏病|心理咨询|创伤|家暴|欠债|存款|工资|"
    r"密码|验证码|身份证|银行卡|住址|家庭地址|手机号|电话号码|QQ号|定位|"
    r"(?<!\d)1[3-9]\d{9}(?!\d)|"
    r"\b(?:secret|confidential|password|passcode|sexual|intimate|nude|diagnosis|medical)\b",
    re.IGNORECASE,
)
_SENSITIVE_LABELS = {
    "private", "secret", "confidential", "intimate", "sexual", "sensitive",
    "私密", "隐私", "秘密", "保密", "亲密", "涩涩", "色情", "性", "健康", "疾病", "病情", "密码",
}


def classify_content(content: str, metadata: dict[str, Any] | None = None) -> PrivacyLevel:
    """Suggest a privacy label; this never excludes a memory from cognition."""
    metadata = metadata or {}
    labels = {
        str(metadata.get(key) or "").lower()
        for key in ("privacy_level", "privacy", "source_privacy", "sensitivity")
    }
    for key in ("tags", "privacy_categories"):
        values = metadata.get(key) or []
        if isinstance(values, str):
            values = [values]
        labels.update(str(value).strip().lower() for value in values)
    if (
        labels & _SENSITIVE_LABELS
        or metadata.get("visibility") == "owner"
        or metadata.get("do_not_share") is True
        or _SENSITIVE_RE.search(str(content or ""))
    ):
        return PrivacyLevel.PRIVATE
    return PrivacyLevel.REVIEW if metadata.get("conversation_scope") == "private" else PrivacyLevel.PUBLIC


def privacy_metadata(content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(metadata or {})
    if classify_content(content, metadata) == PrivacyLevel.PRIVATE:
        metadata["privacy_level"] = "private"
        metadata["source_privacy"] = "private"
    return metadata


def soul_privacy_context(*, is_group: bool, content: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "scene": "group" if is_group else "private",
        "level": classify_content(content).value,
        "knowledge_rule": "记忆是统一的，无论身处哪里都可以理解相关经历，知道不等于应当说出。",
        "private_material_rule": (
            "这里有旁人在场。亲密互动、涩涩内容和敏感私事留在心里，不复述、暗示或用玩笑透露；"
            "可以据此理解关系、保持体贴，不能解释私密原因，也不主动宣告自己知道秘密。"
            if is_group else "当前是与这位用户独处，可以自然谈及彼此的私密经历，仍尊重他人的隐私。"
        ),
        "ordinary_private_rule": "普通日常结合当前听众、话题和氛围自主决定是否提起；拿不准时不说细节。",
    }


ReplyReviewer = Callable[[str, dict[str, Any]], Awaitable[bool]]
_reply_reviewer: ReplyReviewer | None = None
speech_context: ContextVar[dict[str, Any] | None] = ContextVar("miya_speech_context", default=None)


def set_reply_reviewer(reviewer: ReplyReviewer | None) -> None:
    global _reply_reviewer
    _reply_reviewer = reviewer


async def check_public_reply(response: str, *, group_id: Any, context: dict[str, Any]) -> str:
    """Check completed speech before sending; keep unapproved drafts internal.

    This is a model-based additional check, not a mathematical confidentiality
    guarantee. Timeouts/invalid responses suppress the draft instead of sending
    private details during a degraded request.
    """
    from memory.context_identity import normalize_group_id

    if not response or not normalize_group_id(group_id):
        return response
    if _reply_reviewer:
        try:
            approved = await asyncio.wait_for(_reply_reviewer(response, context), timeout=10.0)
            if approved is True:
                return response
        except Exception as exc:
            logger.warning("[场合判断] 发言暂留内部: %s", type(exc).__name__)
    logger.info("[场合判断] 群聊草稿未通过公开表达检查")
    return ""
