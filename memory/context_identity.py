from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def normalize_group_id(value: Any) -> str:
    group_id = str(value or "").strip()
    return "" if group_id in {"0", "None", "null"} else group_id


def platform_family(platform: str) -> str:
    from core.unified_platform.platform_type import MiyaPlatform

    return "qq" if platform in MiyaPlatform.qq_family() else str(platform or "unknown")


def effective_group_id(memory: Any) -> str:
    metadata = getattr(memory, "metadata", {}) or {}
    return normalize_group_id(getattr(memory, "group_id", "")) or normalize_group_id(metadata.get("group_id"))


@dataclass(frozen=True)
class ContextIdentity:
    user_id: str
    platform_user_id: str
    group_id: str
    platform: str
    session_id: str
    aliases: tuple[str, ...]
    explicit_session: bool = False

    @classmethod
    def resolve(
        cls, user_id: Any = "", group_id: Any = "", platform: str = "unknown", session_id: str = ""
    ) -> ContextIdentity:
        from memory.identity_resolver import get_identity_resolver

        resolver = get_identity_resolver()
        original = str(user_id or "").strip()
        canonical = resolver.canonicalize(original) if original else ""
        aliases = tuple(dict.fromkeys([canonical, original, *resolver.expand(canonical)]))
        aliases = tuple(alias for alias in aliases if alias)
        group = normalize_group_id(group_id)
        generated = f"group_{group}_{canonical}" if group else f"user_{canonical}"
        return cls(canonical, original, group, platform, str(session_id or generated), aliases, bool(session_id))

    @classmethod
    def from_perception(cls, perception: dict) -> ContextIdentity:
        return cls.resolve(
            perception.get("user_id", perception.get("sender_id", "")),
            perception.get("group_id", ""),
            perception.get("platform", perception.get("source", "unknown")),
            perception.get("session_id", ""),
        )

    @property
    def session_ids(self) -> tuple[str, ...]:
        if self.explicit_session:
            return (self.session_id,)
        if self.group_id:
            return tuple(dict.fromkeys([
                self.session_id,
                *(f"group_{self.group_id}_{alias}" for alias in self.aliases),
            ]))
        return tuple(dict.fromkeys([self.session_id, *(f"user_{alias}" for alias in self.aliases)]))

    def metadata(self) -> dict[str, Any]:
        return {
            "canonical_user_id": self.user_id,
            "platform_user_id": self.platform_user_id,
            "conversation_scope": "group" if self.group_id else "private",
            "group_id": self.group_id,
            "visibility": "group" if self.group_id else "private",
        }


def matches_context_scope(memory: Any, query: Any) -> bool:
    if not query.scope_user_ids and not query.scope_group_id:
        return True
    metadata = getattr(memory, "metadata", {}) or {}
    visibility = metadata.get("visibility", "")
    group_id = effective_group_id(memory)
    if visibility in {"public", "global"}:
        return True
    if memory.user_id == "global" and not group_id and visibility not in {"private", "owner", "group"}:
        return True
    if query.scope_group_id:
        return bool(
            group_id == query.scope_group_id
            and visibility not in {"private", "owner"}
            and (not query.scope_platforms or memory.platform in query.scope_platforms)
        )
    return memory.user_id in (query.scope_user_ids or [])
