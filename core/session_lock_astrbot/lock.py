"""Session Lock"""

import asyncio
import contextlib
from typing import Dict, Optional


class SessionLock:
    """会话锁 - 防止并发处理同一会话"""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}

    async def acquire(self, session_id: str, timeout: float = 30.0) -> bool:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()

        try:
            await asyncio.wait_for(self._locks[session_id].acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self, session_id: str):
        if session_id in self._locks:
            with contextlib.suppress(RuntimeError):
                self._locks[session_id].release()

    def is_locked(self, session_id: str) -> bool:
        if session_id in self._locks:
            return self._locks[session_id].locked()
        return False


_session_lock: Optional[SessionLock] = None


def get_session_lock() -> SessionLock:
    global _session_lock
    if _session_lock is None:
        _session_lock = SessionLock()
    return _session_lock
