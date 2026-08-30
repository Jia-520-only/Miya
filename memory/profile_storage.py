"""
弥娅认知记忆 — 用户/群聊 Markdown 侧写存储

存储格式: YAML frontmatter + Markdown 正文
文件路径: data/cognitive/profiles/users/{user_id}.md / groups/{group_id}.md
自动备份: data/cognitive/profiles/history/
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)

_DEFAULT_REVISION_KEEP = 5

_PROFILE_TEMPLATE = """---
entity_type: {entity_type}
entity_id: "{entity_id}"
name: {name}
tags: []
updated_at: "{updated_at}"
---

{entity_id} 的画像正在生成中。
"""


class ProfileStorage:
    def __init__(self, base_path: str | Path, revision_keep: int = _DEFAULT_REVISION_KEEP) -> None:
        base = Path(base_path)
        self._users_dir = base / "users"
        self._groups_dir = base / "groups"
        self._history_users_dir = base / "history" / "users"
        self._history_groups_dir = base / "history" / "groups"
        self._revision_keep = max(1, int(revision_keep))

        for d in (
            self._users_dir,
            self._groups_dir,
            self._history_users_dir,
            self._history_groups_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[侧写存储] 初始化完成: users=%s groups=%s revision_keep=%s",
            str(self._users_dir),
            str(self._groups_dir),
            self._revision_keep,
        )

    def _file_path(self, entity_type: str, entity_id: str) -> Path:
        if entity_type == "user":
            return self._users_dir / f"{entity_id}.md"
        elif entity_type == "group":
            return self._groups_dir / f"{entity_id}.md"
        else:
            raise ValueError(f"不支持的实体类型: {entity_type}")

    def _history_dir(self, entity_type: str, entity_id: str) -> Path:
        base = self._history_users_dir if entity_type == "user" else self._history_groups_dir
        d = base / str(entity_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def load(self, entity_type: str, entity_id: str) -> Optional[str]:
        file_path = self._file_path(entity_type, entity_id)
        if not file_path.exists():
            return None
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def save(self, entity_type: str, entity_id: str, content: str) -> None:
        file_path = self._file_path(entity_type, entity_id)

        if file_path.exists():
            history_dir = self._history_dir(entity_type, entity_id)
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            backup_path = history_dir / f"{timestamp}.md"
            try:
                os.replace(str(file_path), str(backup_path))
            except OSError:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    old_content = await f.read()
                async with aiofiles.open(backup_path, "w", encoding="utf-8") as f:
                    await f.write(old_content)

            revisions = sorted(history_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_rev in revisions[self._revision_keep :]:
                old_rev.unlink(missing_ok=True)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        logger.info("[侧写存储] 已保存: entity=%s:%s len=%s", entity_type, entity_id, len(content))

    async def ensure_exists(self, entity_type: str, entity_id: str, name: str = "") -> None:
        file_path = self._file_path(entity_type, entity_id)
        if file_path.exists():
            return

        now_iso = datetime.now(datetime.UTC).isoformat()
        content = _PROFILE_TEMPLATE.format(
            entity_type=entity_type,
            entity_id=entity_id,
            name=name or entity_id,
            updated_at=now_iso,
        )
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        logger.info("[侧写存储] 已创建初始画像: entity=%s:%s", entity_type, entity_id)

    async def list_revisions(self, entity_type: str, entity_id: str) -> list[str]:
        history_dir = self._history_dir(entity_type, entity_id)
        return sorted(
            [p.stem for p in history_dir.glob("*.md")],
            reverse=True,
        )

    async def restore_revision(self, entity_type: str, entity_id: str, timestamp: str) -> bool:
        history_dir = self._history_dir(entity_type, entity_id)
        backup_path = history_dir / f"{timestamp}.md"
        if not backup_path.exists():
            return False
        async with aiofiles.open(backup_path, "r", encoding="utf-8") as f:
            content = await f.read()
        await self.save(entity_type, entity_id, content)
        return True
