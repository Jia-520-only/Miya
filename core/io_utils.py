"""异步安全的 IO 工具模块

借鉴 Undefined 的实现，提供：
- 原子写入（临时文件 + os.replace）
- 文件锁保护（排他锁/共享锁）
- 异步到同步桥接（asyncio.to_thread）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from core.file_lock import FileLock

logger = logging.getLogger(__name__)

DEFAULT_LOCK_SUFFIX = ".lock"


async def write_json(file_path: Path | str, data: Any, use_lock: bool = True) -> None:
    """异步安全地写入 JSON 文件"""
    p = Path(file_path)
    start_time = time.perf_counter()
    data_size = len(str(data))
    logger.debug(
        "[IO] 写入JSON: path=%s, use_lock=%s, size_estimate=%s chars",
        p,
        use_lock,
        data_size,
    )

    def _lock_path_for(target: Path) -> Path:
        return target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")

    def sync_write() -> None:
        p.parent.mkdir(parents=True, exist_ok=True)

        def atomic_write() -> None:
            tmp_path: Path | None = None
            try:
                fd, tmp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
                tmp_path = Path(tmp_name)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, p)
            finally:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()

        if use_lock:
            lock_path = _lock_path_for(p)
            with FileLock(lock_path, shared=False):
                atomic_write()
        else:
            atomic_write()

    try:
        await asyncio.to_thread(sync_write)
        elapsed = time.perf_counter() - start_time
        logger.info("[IO] 写入成功: path=%s, elapsed=%.3fs", p, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error("[IO] 写入失败: path=%s, elapsed=%.3fs, error=%s", p, elapsed, e)
        raise


async def read_json(file_path: Path | str, use_lock: bool = False) -> Any | None:
    """异步安全地读取 JSON 文件"""
    p = Path(file_path)
    start_time = time.perf_counter()
    logger.debug("[IO] 读取JSON: path=%s, use_lock=%s", p, use_lock)

    def _lock_path_for(target: Path) -> Path:
        return target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")

    def sync_read() -> Any | None:
        if not p.exists():
            return None
        if use_lock:
            lock_path = _lock_path_for(p)
            with FileLock(lock_path, shared=True), open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    try:
        result = await asyncio.to_thread(sync_read)
        elapsed = time.perf_counter() - start_time
        logger.info("[IO] 读取成功: path=%s, elapsed=%.3fs", p, elapsed)
        return result
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error("[IO] 读取失败: path=%s, elapsed=%.3fs, error=%s", p, elapsed, e)
        raise


async def write_text(file_path: Path | str, content: str, use_lock: bool = True) -> None:
    """原子写入文本文件"""
    target = Path(file_path)

    def sync_write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)

        def atomic_write() -> None:
            tmp_path: Path | None = None
            try:
                fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
                tmp_path = Path(tmp_name)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, target)
            finally:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()

        if use_lock:
            lock_path = target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")
            with FileLock(lock_path, shared=False):
                atomic_write()
        else:
            atomic_write()

    await asyncio.to_thread(sync_write)


async def read_text(file_path: Path | str, use_lock: bool = False) -> str | None:
    """异步读取文本文件"""
    target = Path(file_path)

    def sync_read() -> str | None:
        if not target.exists():
            return None
        if use_lock:
            lock_path = target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")
            with FileLock(lock_path, shared=True):
                return target.read_text(encoding="utf-8")
        return target.read_text(encoding="utf-8")

    return await asyncio.to_thread(sync_read)


async def read_bytes(file_path: Path | str, use_lock: bool = False) -> bytes:
    """异步读取二进制文件"""
    target = Path(file_path)

    def sync_read() -> bytes:
        if use_lock:
            lock_path = target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")
            with FileLock(lock_path, shared=True):
                return target.read_bytes()
        return target.read_bytes()

    return await asyncio.to_thread(sync_read)


async def append_line(
    file_path: Path | str,
    line: str,
    use_lock: bool = True,
    lock_file_path: Path | str | None = None,
) -> None:
    """异步安全地追加一行文本"""
    p = Path(file_path)
    start_time = time.perf_counter()

    if not line.endswith("\n"):
        line += "\n"

    def _lock_path_for(target: Path) -> Path:
        return target.with_name(f"{target.name}{DEFAULT_LOCK_SUFFIX}")

    def sync_append() -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(lock_file_path) if lock_file_path else _lock_path_for(p)
        if use_lock:
            with FileLock(lock_path, shared=False), open(p, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            return
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    try:
        await asyncio.to_thread(sync_append)
        elapsed = time.perf_counter() - start_time
        logger.info("[IO] 追加成功: path=%s, elapsed=%.3fs", p, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error("[IO] 追加失败: path=%s, elapsed=%.3fs, error=%s", p, elapsed, e)
        raise


async def exists(file_path: Path | str) -> bool:
    """异步检查文件或目录是否存在"""
    return await asyncio.to_thread(Path(file_path).exists)


async def delete_file(file_path: Path | str) -> bool:
    """异步删除文件"""
    p = Path(file_path)

    def sync_delete() -> bool:
        if p.exists():
            p.unlink()
            return True
        return False

    return await asyncio.to_thread(sync_delete)
