"""
弥娅认知记忆 — 文件持久化任务队列

三态流转: pending → processing → complete / failed
"""

from __future__ import annotations

import asyncio
import json as json_lib
import logging
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, base_path: str | Path) -> None:
        base = Path(base_path)
        self._pending_dir = base / "pending"
        self._processing_dir = base / "processing"
        self._failed_dir = base / "failed"
        for d in (self._pending_dir, self._processing_dir, self._failed_dir):
            d.mkdir(parents=True, exist_ok=True)

        stale_lock_count = 0
        for d in (self._pending_dir, self._processing_dir, self._failed_dir):
            for lock_file in d.glob("*.lock"):
                lock_file.unlink(missing_ok=True)
                stale_lock_count += 1
        if stale_lock_count:
            logger.info("[认知队列] 清理遗留 lock 文件: count=%s", stale_lock_count)

        logger.info(
            "[认知队列] 初始化完成: base=%s pending=%s processing=%s failed=%s",
            str(base),
            str(self._pending_dir),
            str(self._processing_dir),
            str(self._failed_dir),
        )

    async def enqueue(self, job: dict[str, Any]) -> str:
        request_id = str(job.get("request_id") or str(uuid4()))
        user_id = job.get("user_id", "")
        end_seq = job.get("end_seq", 0)
        job_id = f"{request_id}_{end_seq}_{int(time.time() * 1000)}"
        file_path = self._pending_dir / f"{job_id}.json"

        async with asyncio.Lock():
            with open(file_path, "w", encoding="utf-8") as f:
                json_lib.dump(job, f, ensure_ascii=False, default=str)

        logger.info(
            "[认知队列] 入队成功: job_id=%s request_id=%s user=%s group=%s",
            job_id,
            request_id,
            user_id,
            job.get("group_id", ""),
        )
        return job_id

    async def dequeue(self) -> tuple[str, dict[str, Any]] | None:
        def _pick() -> tuple[str, dict[str, Any]] | None:
            files = sorted(self._pending_dir.glob("*.json"))
            for f in files:
                dst = self._processing_dir / f.name
                try:
                    os.replace(f, dst)
                    with open(dst, "r", encoding="utf-8") as fh:
                        data = json_lib.load(fh)
                    lock_file = f.with_name(f"{f.name}.lock")
                    lock_file.unlink(missing_ok=True)
                    return f.stem, data
                except (OSError, Exception) as exc:
                    logger.warning("[认知队列] 出队失败，跳过文件: file=%s err=%s", str(f), exc)
                    continue
            return None

        result = await asyncio.to_thread(_pick)
        if result:
            job_id, job = result
            logger.info("[认知队列] 出队成功: job_id=%s", job_id)
        return result

    async def complete(self, job_id: str) -> None:
        proc_file = self._processing_dir / f"{job_id}.json"
        proc_file.unlink(missing_ok=True)
        logger.info("[认知队列] 任务完成: job_id=%s", job_id)

    async def requeue(self, job_id: str) -> bool:
        proc_file = self._processing_dir / f"{job_id}.json"
        if not proc_file.exists():
            return False
        dst = self._pending_dir / proc_file.name
        try:
            os.replace(proc_file, dst)
            logger.info("[认知队列] 重新入队: job_id=%s", job_id)
            return True
        except OSError as exc:
            logger.warning("[认知队列] 重新入队失败: job_id=%s err=%s", job_id, exc)
            return False

    async def fail(self, job_id: str, error: str = "") -> None:
        proc_file = self._processing_dir / f"{job_id}.json"
        if not proc_file.exists():
            return
        try:
            with open(proc_file, "r", encoding="utf-8") as f:
                data = json_lib.load(f)
            data["error"] = error
            data["failed_at"] = time.time()
            dst = self._failed_dir / proc_file.name
            with open(dst, "w", encoding="utf-8") as f:
                json_lib.dump(data, f, ensure_ascii=False, default=str)
            proc_file.unlink(missing_ok=True)
            logger.info("[认知队列] 任务标记失败: job_id=%s error=%s", job_id, error[:200])
        except Exception as exc:
            logger.warning("[认知队列] 标记失败异常: job_id=%s err=%s", job_id, exc)

    async def recover_stale(self, stale_timeout_seconds: float = 300.0) -> int:
        count = 0
        for f in sorted(self._processing_dir.glob("*.json")):
            try:
                mtime = f.stat().st_mtime
                age = time.time() - mtime
                if age > stale_timeout_seconds:
                    dst = self._pending_dir / f.name
                    os.replace(f, dst)
                    count += 1
            except OSError:
                continue
        if count:
            logger.info("[认知队列] 恢复 stale 任务: count=%s", count)
        return count

    @property
    def pending_count(self) -> int:
        return len(list(self._pending_dir.glob("*.json")))

    @property
    def processing_count(self) -> int:
        return len(list(self._processing_dir.glob("*.json")))

    @property
    def failed_count(self) -> int:
        return len(list(self._failed_dir.glob("*.json")))

    async def status(self) -> dict[str, int]:
        def _count() -> dict[str, int]:
            return {
                "pending": len(list(self._pending_dir.glob("*.json"))),
                "processing": len(list(self._processing_dir.glob("*.json"))),
                "failed": len(list(self._failed_dir.glob("*.json"))),
            }

        return await asyncio.to_thread(_count)

    async def cleanup_failed(self, max_age_days: int = 30, max_files: int = 500) -> int:
        now = time.time()
        max_age_seconds = max_age_days * 86400.0
        removed = 0
        files = sorted(self._failed_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)

        for f in files:
            age = now - f.stat().st_mtime
            if age > max_age_seconds:
                f.unlink(missing_ok=True)
                removed += 1

        remaining = len(list(self._failed_dir.glob("*.json")))
        if remaining > max_files:
            excess_files = sorted(
                self._failed_dir.glob("*.json"),
                key=lambda f: f.stat().st_mtime,
            )[: remaining - max_files]
            for f in excess_files:
                f.unlink(missing_ok=True)
                removed += 1

        if removed:
            logger.info("[认知队列] 清理 failed 文件: removed=%s", removed)
        return removed
