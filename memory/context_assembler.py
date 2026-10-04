from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from memory.context_identity import ContextIdentity, effective_group_id, platform_family

logger = logging.getLogger(__name__)


def timestamp_value(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return 0.0


@dataclass
class ContextMessage:
    role: str
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextSnapshot:
    identity: ContextIdentity
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    messages: list[ContextMessage] = field(default_factory=list)
    memory_context: str = ""
    screen_context: str = ""
    vision_context: str = ""
    working_context: str = ""
    pending_context: str = ""
    errors: list[str] = field(default_factory=list)

    def prompt_text(self, max_chars: int = 8000) -> str:
        parts = []
        if self.messages:
            lines = [f"- [{message.timestamp}] {message.role}: {message.content[:350]}" for message in self.messages[-12:]]
            parts.append("【近期对话】\n" + "\n".join(lines))
        parts.extend(part for part in (
            self.memory_context, self.working_context, self.pending_context,
            self.screen_context, self.vision_context,
        ) if part)
        return "\n\n".join(parts)[:max_chars]


class ContextAssembler:
    """A request-scoped view of dialogue, recall, senses and unfinished intent."""

    def __init__(self, memory_net: Any = None, history_manager: Any = None):
        self.history_manager = history_manager or getattr(memory_net, "conversation_history", None)

    async def load_dialogue(self, identity: ContextIdentity, limit: int = 50) -> list[ContextMessage]:
        if limit <= 0 or not (identity.user_id or identity.group_id):
            return []
        sources: list[tuple[str, Any]] = []
        if self.history_manager:
            for session_id in identity.session_ids:
                try:
                    messages = await self.history_manager.get_history(session_id, limit=limit)
                    sources.extend(("cache", message) for message in messages or [])
                except Exception as exc:
                    logger.warning("[ContextAssembler] 会话缓存读取失败 session=%s: %s", session_id, exc)
        try:
            from memory import get_dialogue_history
            from core.unified_platform.platform_type import MiyaPlatform

            platforms = sorted(MiyaPlatform.qq_family()) if platform_family(identity.platform) == "qq" else [identity.platform]
            if identity.group_id and not identity.explicit_session:
                history = await get_dialogue_history(group_id=identity.group_id, platforms=platforms, limit=limit)
            elif identity.explicit_session:
                history = await get_dialogue_history(session_id=identity.session_id, limit=limit)
            else:
                history = await get_dialogue_history(user_id=identity.user_id, private_only=True, limit=limit)
            sources.extend(("unified", message) for message in history or [])
        except Exception as exc:
            logger.warning("[ContextAssembler] 统一对话读取失败: %s", exc)

        result: list[tuple[str, ContextMessage]] = []
        seen_ids: set[tuple[str, str]] = set()
        for origin, message in sources:
            metadata = dict(getattr(message, "metadata", {}) or {})
            group = effective_group_id(message)
            if identity.group_id:
                # Cache records came from the exact group session IDs above, so
                # older entries without group metadata are still trusted there.
                # Unified-memory records must explicitly belong to this group;
                # otherwise a private record could leak into a group prompt.
                if origin != "cache" and group != identity.group_id:
                    continue
            elif group:
                # Private conversations must never inherit a group message.
                continue
            role = str(getattr(message, "role", "user"))
            content = str(getattr(message, "content", ""))
            stamp = str(getattr(message, "timestamp", "") or getattr(message, "created_at", ""))
            event_id = metadata.get("memory_event_id") or metadata.get("delivery_id")
            key = (str(event_id), role)
            if event_id and key in seen_ids:
                continue
            duplicate = next((previous for previous_origin, previous in result if (
                previous_origin != origin and previous.role == role and previous.content == content
                and metadata.get("platform_user_id", metadata.get("user_id", "")) == previous.metadata.get("platform_user_id", previous.metadata.get("user_id", ""))
                and stamp and previous.timestamp
                and abs(timestamp_value(stamp) - timestamp_value(previous.timestamp)) < 2
            )), None)
            if duplicate:
                continue
            if event_id:
                seen_ids.add(key)
            result.append((origin, ContextMessage(role, content, stamp, metadata)))
        messages = [message for _, message in result]
        messages.sort(key=lambda message: timestamp_value(message.timestamp))
        return messages[-limit:]

    @staticmethod
    def can_read_senses(identity: ContextIdentity) -> bool:
        from memory.identity_resolver import get_identity_resolver

        owner = get_identity_resolver().owner_canonical_id
        return bool(owner and identity.user_id == owner and not identity.group_id)

    @staticmethod
    def senses(identity: ContextIdentity) -> tuple[str, str]:
        if not ContextAssembler.can_read_senses(identity):
            return "", ""
        screen = ""
        camera = ""
        try:
            from miya_senses.sensors.screen_aware import get_screen_aware

            sensor = get_screen_aware()
            screen = sensor.build_timeline_card(max_entries=8) if sensor else ""
        except Exception as exc:
            logger.debug("[ContextAssembler] 屏幕上下文不可用: %s", exc)
        try:
            from mcpserver.screen_vision.vision_context import vision_context_card

            camera = vision_context_card()
        except Exception as exc:
            logger.debug("[ContextAssembler] 摄像头上下文不可用: %s", exc)
        return screen, camera

    async def build(
        self, identity: ContextIdentity, query: str = "", limit: int = 20,
        messages: list[Any] | None = None, recall: bool = True,
    ) -> ContextSnapshot:
        snapshot = ContextSnapshot(identity)
        snapshot.messages = messages if messages is not None else await self.load_dialogue(identity, limit)
        snapshot.screen_context, snapshot.vision_context = self.senses(identity)
        if recall and identity.user_id and query.strip():
            try:
                from memory.cognitive_engine import get_cognitive_engine

                history = [{"role": message.role, "content": message.content} for message in snapshot.messages]
                snapshot.memory_context = await asyncio.wait_for(get_cognitive_engine().build_context(
                    user_input=query, conversation_history=history, limit=5,
                    user_id=identity.user_id, group_id=identity.group_id or None, platform=identity.platform,
                ), timeout=6)
            except Exception as exc:
                snapshot.errors.append("recall")
                logger.warning("[ContextAssembler] 记忆召回失败 trace=%s: %s", snapshot.trace_id, exc)
        try:
            from memory.working_memory import get_working_memory

            working = get_working_memory()
            snapshot.working_context = working.get_folded_background(session_id=identity.session_id) or ""
            if identity.group_id:
                snapshot.working_context += "\n" + (working.build_prompt_context(identity.group_id) or "")
        except Exception as exc:
            logger.debug("[ContextAssembler] 工作记忆不可用: %s", exc)
        try:
            from core.proactive_chat import get_proactive_chat_system

            system = get_proactive_chat_system()
            target = identity.group_id or identity.platform_user_id
            key = int(target) if target.isdigit() else target
            intent = system._pending_intents.get(key)
            if intent:
                snapshot.pending_context = "【尚未完成的意图】\n" + str(intent.context_summary)[:500]
        except Exception as exc:
            logger.debug("[ContextAssembler] 主动意图不可用: %s", exc)
        return snapshot
