"""
后台终端日志流 — 捕获守护进程控制台输出，供前端「后台终端」页面实时展示。

捕获两个来源:
  1. root logger 的全部日志（[名称] 级别: 内容，含异常栈）
  2. sys.stdout / sys.stderr 的 print 输出（启动 banner、uvicorn、traceback 等）

数据进入线程安全环形缓冲（带自增 seq），由管理 API 的
GET /api/v1/logs        快照查询
GET /api/v1/logs/stream SSE 实时推送（支持 ?since=seq 断线续传）
"""

from __future__ import annotations

import itertools
import logging
import sys
import threading
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

BUFFER_SIZE = 2000

# 与 run/daemon.py 的 basicConfig 格式保持一致
_FMT = "[%(name)s] %(levelname)s: %(message)s"


class LogStreamBuffer:
    """线程安全日志环形缓冲"""

    def __init__(self, maxlen: int = BUFFER_SIZE):
        self._lock = threading.Lock()
        self._entries: Deque[Dict] = deque(maxlen=maxlen)
        self._seq = itertools.count(1)

    def add(self, level: str, name: str, text: str) -> Dict:
        entry = {
            "seq": next(self._seq),
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": level,
            "name": name,
            "text": text,
        }
        with self._lock:
            self._entries.append(entry)
        return entry

    def snapshot(self, limit: int = 500) -> Tuple[List[Dict], int]:
        """最近 limit 条 + 最新 seq"""
        with self._lock:
            entries = list(self._entries)
        latest = entries[-1]["seq"] if entries else 0
        return entries[-limit:], latest

    def since(self, seq: int) -> Dict:
        """取 seq 之后的新条目；请求位置已被环形缓冲淘汰时 overrun=True"""
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return {"entries": [], "latest_seq": 0, "overrun": False}
        oldest = entries[0]["seq"]
        latest = entries[-1]["seq"]
        if seq < oldest - 1:
            return {"entries": [], "latest_seq": latest, "overrun": True}
        return {
            "entries": [e for e in entries if e["seq"] > seq],
            "latest_seq": latest,
            "overrun": False,
        }


_buffer: Optional[LogStreamBuffer] = None


def get_log_buffer() -> LogStreamBuffer:
    global _buffer
    if _buffer is None:
        _buffer = LogStreamBuffer()
    return _buffer


class LogStreamHandler(logging.Handler):
    """把 root logger 日志写入环形缓冲（格式与控制台一致）"""

    def __init__(self, buffer: LogStreamBuffer):
        super().__init__(level=logging.INFO)
        self.buffer = buffer
        self.setFormatter(logging.Formatter(_FMT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
            self.buffer.add(record.levelname, record.name, text)
        except Exception:
            self.handleError(record)


class _StreamTee:
    """包装原输出流：透写的同时按行捕获到环形缓冲"""

    def __init__(self, original, buffer: LogStreamBuffer, label: str, level: str):
        self._original = original
        self._buffer = buffer
        self._label = label
        self._level = level
        self._pending = ""
        self._lock = threading.Lock()

    def _drain(self) -> None:
        line, self._pending = self._pending, ""
        if line:
            self._buffer.add(self._level, self._label, line)

    def write(self, data) -> None:
        try:
            self._original.write(data)
        except Exception:
            pass
        if not isinstance(data, str):
            return
        with self._lock:
            self._pending += data
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                if line:
                    self._buffer.add(self._level, self._label, line)

    def flush(self) -> None:
        try:
            self._original.flush()
        except Exception:
            pass
        with self._lock:
            self._drain()

    def __getattr__(self, item):
        return getattr(self._original, item)


_installed = False
_stdout_tee: Optional[_StreamTee] = None
_stderr_tee: Optional[_StreamTee] = None
_handler: Optional[LogStreamHandler] = None


def install_log_stream() -> None:
    """安装日志捕获（幂等）。

    必须在 logging.basicConfig 之后调用：root 的 StreamHandler 此刻已绑定真实
    stderr，随后的 stderr Tee 只捕获后来绑定的 handler（uvicorn 等）与运行期
    直接写 sys.stderr 的内容，日志本体由 LogStreamHandler 结构化捕获，不会重复。
    """
    global _installed, _stdout_tee, _stderr_tee, _handler
    if _installed:
        return
    buffer = get_log_buffer()
    _handler = LogStreamHandler(buffer)
    logging.getLogger().addHandler(_handler)
    _stdout_tee = _StreamTee(sys.stdout, buffer, "stdout", "OUT")
    _stderr_tee = _StreamTee(sys.stderr, buffer, "stderr", "ERR")
    sys.stdout = _stdout_tee
    sys.stderr = _stderr_tee
    _installed = True


def uninstall_log_stream() -> None:
    """卸载日志捕获，恢复原输出流（供测试使用）"""
    global _installed, _stdout_tee, _stderr_tee, _handler
    if not _installed:
        return
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
    if isinstance(sys.stdout, _StreamTee):
        sys.stdout = sys.stdout._original
    if isinstance(sys.stderr, _StreamTee):
        sys.stderr = sys.stderr._original
    _handler = None
    _stdout_tee = None
    _stderr_tee = None
    _installed = False
