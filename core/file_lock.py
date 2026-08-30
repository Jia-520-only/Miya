"""跨平台文件锁工具

借鉴 Undefined 的实现，支持 Windows (msvcrt) 和 Linux (flock)。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO

if os.name == "nt":
    import msvcrt

    def _ensure_lock_region(handle: IO[bytes]) -> None:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)

    def lock_exclusive(handle: IO[bytes]) -> None:
        _ensure_lock_region(handle)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def lock_shared(handle: IO[bytes]) -> None:
        lock_exclusive(handle)

    def unlock(handle: IO[bytes]) -> None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            return

else:
    import fcntl

    def lock_exclusive(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def lock_shared(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)

    def unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class FileLock:
    """跨平台文件锁上下文管理器

    用法:
        with FileLock(Path("data/lockfile.lock")):
            # 安全地写入文件
            pass
    """

    def __init__(self, path: Path, *, shared: bool = False) -> None:
        self._path = path
        self._shared = shared
        self._handle: IO[bytes] | None = None

    def __enter__(self) -> FileLock:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self._path, "a+b")
        if self._shared:
            lock_shared(self._handle)
        else:
            lock_exclusive(self._handle)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._handle is None:
            return
        try:
            unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
