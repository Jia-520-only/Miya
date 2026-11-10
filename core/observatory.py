"""Read-only, shared observatory snapshots. Unknown readings stay unknown."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from weakref import WeakKeyDictionary

logger = logging.getLogger(__name__)
LAYERS = ("dialogue", "short_term", "long_term", "semantic", "knowledge", "pinned")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "observatory"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def valid_count(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return round(value)
    return None


class ObservatoryNoteStore:
    def __init__(self, directory: Path = DATA_DIR):
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def read(self, name: str = "note") -> dict:
        with self._lock:
            try:
                value = json.loads((self.directory / f"{name}.json").read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                return {}

    def write(self, value: dict, name: str = "note") -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / f"{name}.json"
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, target)


class ObservatoryService:
    def __init__(self, hub=None, *, spine=None, store=None):
        self.hub = hub
        self.spine = spine
        self.store = store or ObservatoryNoteStore()
        # The daemon and threaded Web API have separate asyncio event loops.
        self._locks = WeakKeyDictionary()
        self._locks_guard = threading.Lock()
        self._cached: dict | None = None
        self._cached_at = 0.0

    def _lifecycle(self) -> dict:
        spine = self.spine
        if spine is None:
            # Do not create a fresh spine merely because somebody opened the UI.
            from core import miya_spine

            spine = miya_spine._spine_instance
        if spine is None or not spine.is_running():
            return {"phase": None, "observed_at": None, "message_count": None}
        state = spine.current_state
        phase = spine.phase.value
        max_age = 95 if phase == "SLEEP" else 35 if phase == "DROWSY" else 15
        age = time.time() - state.timestamp
        if age < -5 or age > max_age or not state.tick_index:
            return {"phase": None, "observed_at": None, "message_count": None}
        return {
            "phase": phase,
            "observed_at": datetime.fromtimestamp(state.timestamp, UTC).isoformat(),
            "message_count": valid_count(state.message_count),
        }

    def _persona(self) -> dict:
        personality = getattr(self.hub, "personality", None)
        current = getattr(personality, "current_form", None)
        if not current:
            return {"id": None, "name": None}
        info = personality.get_form_config(current)
        return {"id": current, "name": info.get("name") or current}

    def _emotion(self) -> dict:
        engine = getattr(self.hub, "emotion", None)
        if engine is None:
            return {"name": None, "intensity": None, "emotions": []}
        state = engine.get_emotion_state()
        # Hub Emotion uses 0..1. The compatibility endpoint's 50/60 defaults
        # are deliberately never consulted here.
        value = state.get("intensity")
        intensity = (
            round(value * 100)
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 1
            else None
        )
        emotions = [
            {"name": name, "intensity": round(value * 100)}
            for name, value in (state.get("current") or {}).items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 1
        ]
        return {"name": state.get("dominant"), "intensity": intensity, "emotions": emotions}

    async def _memory(self) -> dict:
        manager = getattr(self.hub, "memory_manager", None)
        bus = getattr(manager, "_bus", None)
        if bus is None:
            from memory.api.bus import MemoryBus

            bus = MemoryBus._instance
        if bus is None or bus.core is None:
            return {"total": None, "layers": {key: None for key in LAYERS}}
        return await bus.observatory_stats()

    def _platforms(self) -> dict:
        from core.management_api import get_management_api

        api = get_management_api()
        if api is None:
            return {"online_count": None, "enabled_count": None}
        platforms = api.daemon.get_platform_status()
        if not isinstance(platforms, list):
            return {"online_count": None, "enabled_count": None}
        return {
            "online_count": sum(p.get("status") in {"online", "degraded"} for p in platforms),
            "enabled_count": sum(p.get("status") != "disabled" for p in platforms),
        }

    async def snapshot(self) -> dict:
        with self._locks_guard:
            lock = self._locks.setdefault(asyncio.get_running_loop(), asyncio.Lock())
        async with lock:
            if self._cached is not None and time.monotonic() - self._cached_at < 2.5:
                return self._cached
            values = {}
            availability = {}
            for name, reader in (
                ("persona", self._persona),
                ("emotion", self._emotion),
                ("lifecycle", self._lifecycle),
                ("platforms", self._platforms),
            ):
                try:
                    values[name] = reader()
                    availability[name] = any(value is not None and value != [] for value in values[name].values())
                except Exception as exc:
                    logger.debug("Observatory %s unavailable: %s", name, exc)
                    values[name] = {}
                    availability[name] = False
            try:
                values["memory"] = await asyncio.wait_for(self._memory(), timeout=3)
            except Exception as exc:
                logger.debug("Observatory memory unavailable: %s", exc)
                values["memory"] = {"total": None, "layers": {key: None for key in LAYERS}}
            availability["memory"] = values["memory"].get("total") is not None
            note = self.store.read()
            self._cached = {
                "success": True,
                "sampled_at": utc_now(),
                **values,
                "availability": availability,
                "note": note if note.get("title") and note.get("body") else None,
            }
            self._cached_at = time.monotonic()
            return self._cached


_service: ObservatoryService | None = None


def get_observatory(hub=None) -> ObservatoryService:
    global _service
    if _service is None:
        _service = ObservatoryService(hub)
    elif hub is not None and _service.hub is not hub:
        _service.hub = hub
        _service._cached = None
    return _service
