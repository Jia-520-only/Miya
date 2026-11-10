"""Miya writes a quiet, persistent observatory note in her current persona."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from datetime import datetime
from uuid import uuid4

from core.miya_organ import MiyaOrgan
from core.observatory import get_observatory, utc_now, valid_count

logger = logging.getLogger(__name__)
NOTE_PROMPT = """你正在弥娅观测台给佳留下一张专属短笺。继承当前人格，用你自己的口吻表达此刻想留给他的话。
下方状态快照是唯一事实来源；未知值不是零。可以诗意、安静、亲密，但不要编造刚发生的对话、回忆、任务或身体感知，也不要把系统数据当作人类生理测量。
不要复述数字、写运行报告或解释实现。不要沿用上一张的措辞。不需要写时只输出 SKIP。
否则只输出 JSON：{"title":"两行以内的短标题，4至24字","body":"一段给佳的话，10至100字"}。不使用 Markdown 或 HTML。"""


def parse_note(response: str) -> dict | None:
    text = response.strip()
    if text.upper() == "SKIP":
        return None
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected note object")
    title, body = value.get("title"), value.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("Expected note text")
    title, body = title.strip(), body.strip()
    if not 4 <= len(title) <= 24 or not 10 <= len(body) <= 100 or len(title.splitlines()) > 2:
        raise ValueError("Invalid note length")
    if any(character in title + body for character in "<>"):
        raise ValueError("Note must be plain text")
    return {"title": title, "body": body}


class MiyaObservatoryOrgan(MiyaOrgan):
    def __init__(self, service=None, client_factory=None):
        super().__init__(name="observatory_organ", priority=65)
        self.service = service or get_observatory()
        self.client_factory = client_factory
        self._future = None
        self._last_check = 0.0
        self._generation_lock = asyncio.Lock()

    def _config(self) -> dict:
        from config.config_utils import get_qq_config

        value = get_qq_config("observatory", default={})
        return value if isinstance(value, dict) else {}

    def on_soul_state(self, state) -> None:
        if not self.started or self._future is not None or time.monotonic() - self._last_check < 30:
            return
        self._last_check = time.monotonic()
        if self.spine and self.spine._loop:
            self._future = asyncio.run_coroutine_threadsafe(self.generate_if_due(), self.spine._loop)
            self._future.add_done_callback(lambda _: setattr(self, "_future", None))

    async def on_shutdown(self) -> None:
        if self._future is not None:
            self._future.cancel()
        await super().on_shutdown()

    async def generate_if_due(self) -> dict:
        async with self._generation_lock:
            config = self._config()
            if not config.get("enabled", True):
                return {"status": "disabled"}
            if datetime.now().hour in config.get("quiet_hours", [0, 1, 2, 3, 4, 5, 6]):
                return {"status": "quiet"}
            state = self.service.store.read("state")
            now = time.time()
            interval = max(15, valid_count(config.get("interval_minutes")) or 120) * 60
            if (
                now - (valid_count(state.get("last_generated")) or 0) < interval
                or now - (valid_count(state.get("last_attempt")) or 0) < 900
            ):
                return {"status": "throttled"}
            client = None
            try:
                # Persist attempts too: failures and SKIP must not create a hot loop.
                state["last_attempt"] = now
                self.service.store.write(state, "state")
                snapshot = await self.service.snapshot()
                if not snapshot["availability"].get("persona"):
                    return {"status": "unavailable"}
                if self.client_factory:
                    client = self.client_factory()
                else:
                    from core.model_pool_manager import get_model_pool

                    # A dedicated client leaves the conversation's tools untouched.
                    client = get_model_pool().create_ai_client(
                        task_type="creative_writing", endpoint="desktop", reuse=False
                    )
                if client is None:
                    return {"status": "unavailable"}
                from core.ai_client import AIMessage
                from core.persona_prompt import compose_persona_system_prompt

                personality = getattr(self.service.hub, "personality", None)
                persona_id = snapshot["persona"].get("id")
                system = compose_persona_system_prompt(NOTE_PROMPT, personality=personality, ai_client=client)
                # Provider adapters have different chat signatures. Explicitly
                # disable tools where supported, without breaking Anthropic's
                # messages-only adapter or replacing the composed persona.
                parameters = inspect.signature(client.chat).parameters
                accepts_kwargs = any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
                )
                options = {
                    key: value
                    for key, value in {
                        "use_miya_prompt": False,
                        "tools": [],
                        "max_iterations": 1,
                        "max_tokens": 2048,
                    }.items()
                    if accepts_kwargs or key in parameters
                }
                response = await asyncio.wait_for(
                    client.chat(
                        messages=[
                            AIMessage(role="system", content=system),
                            AIMessage(role="user", content=json.dumps(snapshot, ensure_ascii=False)),
                        ],
                        **options,
                    ),
                    timeout=90,
                )
                note = parse_note(str(response or ""))
                if note is None:
                    return {"status": "silent"}
                if getattr(personality, "current_form", None) != persona_id:
                    return {"status": "persona_changed"}
                note.update(
                    {
                        "id": uuid4().hex,
                        "created_at": utc_now(),
                        "persona_id": persona_id,
                        "persona_name": snapshot["persona"].get("name"),
                    }
                )
                self.service.store.write(note)
                state["last_generated"] = time.time()
                self.service.store.write(state, "state")
                self.service._cached = None
                return {"status": "written"}
            except Exception as exc:
                logger.warning("Observatory note retained after generation failure: %s", exc)
                return {"status": "failed"}
            finally:
                if self.client_factory is None and client is not None:
                    close = getattr(getattr(client, "client", None), "close", None)
                    if close:
                        try:
                            result = close()
                            if inspect.isawaitable(result):
                                await result
                        except Exception as exc:
                            logger.debug("Observatory client cleanup failed: %s", exc)
