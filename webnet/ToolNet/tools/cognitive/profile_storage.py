"""
认知侧写存储系统 — 所有配置从 config 读取
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.config_utils import get_cognitive_config

logger = logging.getLogger(__name__)


def _get_cognitive_dir() -> Path:
    cfg_dir = get_cognitive_config("storage", default={}).get("data_dir", "")
    if cfg_dir:
        return Path(cfg_dir)
    return (
        Path(os.getenv("MIYA_DATA_DIR", Path(__file__).resolve().parent.parent.parent.parent.parent / "data"))
        / "cognitive"
    )


class CognitiveProfileStorage:
    _instance: Optional[CognitiveProfileStorage] = None

    def __init__(self):
        self._base = _get_cognitive_dir()
        self._revision_keep = get_cognitive_config("storage", default={}).get("revision_keep", 5)
        self._max_observations = get_cognitive_config("storage", default={}).get("max_observations", 100)
        self._locks: dict[str, asyncio.Lock] = {}

    @classmethod
    def get_instance(cls) -> CognitiveProfileStorage:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_lock(self, entity_type: str, entity_id: str) -> asyncio.Lock:
        key = f"{entity_type}:{entity_id}"
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _profile_path(self, entity_type: str, entity_id: str) -> Path:
        return self._base / f"{entity_type}s" / f"{entity_id}.md"

    def _history_dir(self, entity_type: str, entity_id: str) -> Path:
        return self._base / "history" / entity_type / str(entity_id)

    def _observations_path(self) -> Path:
        return self._base / "observations.json"

    async def read_profile(self, entity_type: str, entity_id: str) -> Optional[str]:
        p = self._profile_path(entity_type, entity_id)

        def _read():
            if not p.exists():
                return None
            return p.read_text(encoding="utf-8")

        try:
            return await asyncio.to_thread(_read)
        except Exception as e:
            logger.warning(f"[侧写] 读取失败: {e}")
            return None

    async def write_profile(self, entity_type: str, entity_id: str, content: str) -> None:
        async with self._get_lock(entity_type, entity_id):
            p = self._profile_path(entity_type, entity_id)
            hist_dir = self._history_dir(entity_type, entity_id)

            def _write():
                p.parent.mkdir(parents=True, exist_ok=True)
                hist_dir.mkdir(parents=True, exist_ok=True)
                if p.exists():
                    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
                    (hist_dir / f"{ts}.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(content)
                    os.replace(tmp, p)
                except Exception:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    raise
                snapshots = sorted(hist_dir.glob("*.md"))
                for old in snapshots[: max(0, len(snapshots) - self._revision_keep)]:
                    try:
                        old.unlink()
                    except OSError:
                        pass

            await asyncio.to_thread(_write)

    async def list_revisions(self, entity_type: str, entity_id: str) -> list[str]:
        hist_dir = self._history_dir(entity_type, entity_id)

        def _list():
            if not hist_dir.exists():
                return []
            return sorted(f.name for f in hist_dir.glob("*.md"))

        return await asyncio.to_thread(_list)

    async def add_observation(self, entity_type: str, entity_id: str, observation: str, source: str = "") -> None:
        obs_path = self._observations_path()

        def _add():
            obs_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if obs_path.exists():
                try:
                    data = json.loads(obs_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    data = {}
            key = f"{entity_type}:{entity_id}"
            if key not in data:
                data[key] = []
            data[key].append(
                {
                    "observation": observation,
                    "source": source,
                    "timestamp": datetime.now(datetime.UTC).isoformat(),
                }
            )
            data[key] = data[key][-self._max_observations :]
            tmp = obs_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, obs_path)

        await asyncio.to_thread(_add)

    async def get_observations(self, entity_type: str, entity_id: str, limit: int = 20) -> list[dict]:
        obs_path = self._observations_path()

        def _get():
            if not obs_path.exists():
                return []
            try:
                data = json.loads(obs_path.read_text(encoding="utf-8"))
                key = f"{entity_type}:{entity_id}"
                return data.get(key, [])[-limit:]
            except Exception:
                return []

        return await asyncio.to_thread(_get)

    async def search_profiles(self, query: str, entity_type: str = "", top_k: int = 8) -> list[dict]:
        results = []
        search_dirs = []
        if entity_type:
            search_dirs = [self._base / f"{entity_type}s"]
        else:
            search_dirs = [d for d in self._base.iterdir() if d.is_dir() and d.name.endswith("s")]

        query_lower = query.lower()
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            etype = search_dir.name[:-1]
            for profile_file in sorted(search_dir.glob("*.md")):
                try:
                    content = profile_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    score = 0
                    if query_lower in content_lower:
                        score += 5
                    for word in query_lower.split():
                        if word in content_lower:
                            score += 1
                    if score > 0:
                        results.append(
                            {
                                "entity_type": etype,
                                "entity_id": profile_file.stem,
                                "content": content[:500],
                                "score": score,
                            }
                        )
                except Exception:
                    continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def get_stats(self) -> dict:
        user_count = 0
        group_count = 0
        users_dir = self._base / "users"
        groups_dir = self._base / "groups"
        if users_dir.exists():
            user_count = len(list(users_dir.glob("*.md")))
        if groups_dir.exists():
            group_count = len(list(groups_dir.glob("*.md")))
        return {"user_profiles": user_count, "group_profiles": group_count}


def get_profile_storage() -> CognitiveProfileStorage:
    return CognitiveProfileStorage.get_instance()
