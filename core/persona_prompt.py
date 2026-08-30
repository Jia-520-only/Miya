"""Helpers for keeping background organs aligned with the active personality."""

from __future__ import annotations

from typing import Any


def compose_persona_system_prompt(
    module_prompt: str,
    *,
    personality: Any = None,
    ai_client: Any = None,
) -> str:
    """Combine the live persona prompt with a background-module prompt.

    Background organs do not have a normal user turn, so they cannot rely on
    the regular DecisionHub prompt assembly.  Prefer the Personality object
    directly (it always reflects the current form), and fall back to the AI
    client's prompt provider for embedded/test callers.
    """
    persona_prompt = ""
    if personality is not None:
        try:
            persona_prompt = str(personality.get_status_for_prompt() or "").strip()
        except Exception:
            persona_prompt = ""

    if not persona_prompt and ai_client is not None:
        try:
            getter = getattr(ai_client, "get_miya_system_prompt", None)
            if getter:
                persona_prompt = str(getter(use_full=True) or "").strip()
        except Exception:
            persona_prompt = ""

    if not persona_prompt:
        return module_prompt

    return (
        "【当前人格（必须继承）】\n"
        f"{persona_prompt}\n\n"
        "【本次后台模块职责】\n"
        f"{module_prompt}"
    )

