"""后台终端日志流测试 — 环形缓冲 / 日志 Handler / stdout Tee / 并发安全"""

import io
import logging
import sys
import threading

from core.log_stream import (
    LogStreamBuffer,
    LogStreamHandler,
    _StreamTee,
    get_log_buffer,
    install_log_stream,
    uninstall_log_stream,
)


def test_buffer_add_and_snapshot():
    buf = LogStreamBuffer(maxlen=10)
    for i in range(5):
        buf.add("INFO", "Test", f"line-{i}")
    entries, latest = buf.snapshot(3)
    assert latest == 5
    assert [e["seq"] for e in entries] == [3, 4, 5]
    assert entries[-1]["text"] == "line-4"
    assert entries[-1]["level"] == "INFO"
    assert entries[-1]["name"] == "Test"
    assert "ts" in entries[-1]


def test_buffer_ring_eviction():
    buf = LogStreamBuffer(maxlen=3)
    for i in range(10):
        buf.add("INFO", "Test", f"line-{i}")
    entries, latest = buf.snapshot(100)
    assert len(entries) == 3
    assert latest == 10
    assert [e["seq"] for e in entries] == [8, 9, 10]


def test_buffer_since_and_overrun():
    buf = LogStreamBuffer(maxlen=3)
    for i in range(5):
        buf.add("INFO", "Test", f"line-{i}")

    # 正常续传：seq=2 之后应拿到 3,4,5
    r = buf.since(2)
    assert r["overrun"] is False
    assert [e["seq"] for e in r["entries"]] == [3, 4, 5]
    assert r["latest_seq"] == 5

    # 已到最新：无新条目
    r = buf.since(5)
    assert r["entries"] == []
    assert r["overrun"] is False

    # 请求位置已被淘汰（oldest=3，seq<2 即溢出）
    r = buf.since(1)
    assert r["overrun"] is True


def _with_handler(logger_name: str, fn):
    """临时给指定 logger 挂 handler（隔离 propagate），执行 fn 后恢复"""
    buf = LogStreamBuffer()
    handler = LogStreamHandler(buf)
    logger = logging.getLogger(logger_name)
    old_handlers = list(logger.handlers)
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        fn(logger)
    finally:
        logger.handlers = old_handlers
        logger.propagate = old_propagate
    return buf


def test_log_handler_capture():
    buf = _with_handler("Test.LogStream", lambda lg: (lg.info("你好弥娅"), lg.warning("小心警告")))
    entries, _ = buf.snapshot(10)
    texts = [e["text"] for e in entries]
    assert "[Test.LogStream] INFO: 你好弥娅" in texts
    assert "[Test.LogStream] WARNING: 小心警告" in texts
    info_entry = next(e for e in entries if e["level"] == "INFO")
    assert info_entry["name"] == "Test.LogStream"


def test_log_handler_with_exception():
    def run(logger):
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("出错了")

    buf = _with_handler("Test.LogStreamExc", run)
    entries, _ = buf.snapshot(10)
    entry = entries[-1]
    assert entry["level"] == "ERROR"
    assert "Traceback" in entry["text"]
    assert "ValueError: boom" in entry["text"]


def test_stream_tee_capture():
    buf = LogStreamBuffer()
    original = io.StringIO()
    tee = _StreamTee(original, buf, "stdout", "OUT")

    tee.write("hello ")
    tee.write("world\n")
    tee.write("第二行\n")
    tee.flush()

    # 透写原流不受影响
    assert original.getvalue() == "hello world\n第二行\n"

    entries, _ = buf.snapshot(10)
    texts = [e["text"] for e in entries]
    assert texts == ["hello world", "第二行"]
    assert entries[0]["level"] == "OUT"
    assert entries[0]["name"] == "stdout"


def test_install_uninstall_roundtrip():
    uninstall_log_stream()

    prev_stdout, prev_stderr = sys.stdout, sys.stderr
    prev_root_handlers = list(logging.getLogger().handlers)
    fake_stdout, fake_stderr = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = fake_stdout, fake_stderr
    try:
        install_log_stream()
        assert isinstance(sys.stdout, _StreamTee)
        assert isinstance(sys.stderr, _StreamTee)

        print("banner 输出")
        test_logger = logging.getLogger("Test.Install")
        test_logger.setLevel(logging.INFO)
        test_logger.info("日志输出")

        buf = get_log_buffer()
        entries, _ = buf.snapshot(50)
        texts = [e["text"] for e in entries]
        assert "banner 输出" in texts
        assert any("日志输出" in t for t in texts)
        # 透写不被吞
        assert "banner 输出" in fake_stdout.getvalue()

        # 幂等：重复安装不会二次包装
        install_log_stream()
        assert isinstance(sys.stdout, _StreamTee)
        assert not isinstance(sys.stdout._original, _StreamTee)
    finally:
        uninstall_log_stream()
        assert sys.stdout is fake_stdout
        assert sys.stderr is fake_stderr
        assert logging.getLogger().handlers == prev_root_handlers
        sys.stdout, sys.stderr = prev_stdout, prev_stderr


def test_concurrent_add_seq_unique():
    buf = LogStreamBuffer(maxlen=100000)

    def worker(tn):
        for i in range(200):
            buf.add("INFO", f"T{tn}", f"msg-{tn}-{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    entries, latest = buf.snapshot(100000)
    seqs = [e["seq"] for e in entries]
    assert len(seqs) == 1600
    assert len(set(seqs)) == 1600
    assert latest == 1600
    assert seqs == sorted(seqs)
