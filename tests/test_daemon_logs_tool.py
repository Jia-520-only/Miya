"""弥娅自检工具 daemon_logs 测试 — 级别过滤 / 关键词 / limit / 回退"""

import asyncio

import core.log_stream as log_stream_module
from core.log_stream import LogStreamBuffer
from webnet.ToolNet.tools.core.daemon_logs import DaemonLogsTool


def _fill_buffer(entries):
    buf = LogStreamBuffer(maxlen=100)
    for level, name, text in entries:
        buf.add(level, name, text)
    return buf


def _run_tool(buf, **args):
    prev = log_stream_module._buffer
    log_stream_module._buffer = buf
    try:
        return asyncio.run(DaemonLogsTool().execute(args, None))
    finally:
        log_stream_module._buffer = prev


SAMPLE = [
    ("INFO", "Miya.Daemon", "平台连接: 7/7 在线"),
    ("INFO", "core.mcp_manager", "注册服务: web_search"),
    ("WARNING", "memory.vector_index", "faiss 包未包含 AVX2 扩展"),
    ("INFO", "Miya.Daemon", "主动聊天后台轮询已启动"),
    ("ERROR", "Miya.Platform.Lark", "WebSocket 断开重连失败"),
    ("OUT", "stdout", "弥娅守护进程已就绪"),
]


def test_default_level_warning_only():
    out = _run_tool(_fill_buffer(SAMPLE))
    assert "ERROR" in out
    assert "WebSocket 断开重连失败" in out
    assert "faiss" in out
    # INFO/OUT 不应出现在正文
    assert "平台连接: 7/7 在线" not in out
    assert "主动聊天后台轮询已启动" not in out
    assert "守护进程已就绪" not in out
    assert "统计:" in out


def test_level_all_and_keyword():
    out = _run_tool(_fill_buffer(SAMPLE), level="all", keyword="lark")
    assert "WebSocket 断开重连失败" in out
    assert "平台连接" not in out


def test_limit_takes_most_recent():
    entries = [("INFO", "T", f"msg-{i}") for i in range(50)]
    entries.append(("ERROR", "T", "最新错误"))
    out = _run_tool(_fill_buffer(entries), level="error", limit=5)
    assert "最新错误" in out
    # error 级别匹配的只有 1 条
    assert "msg-49" not in out


def test_all_good_message():
    entries = [("INFO", "T", "正常"), ("OUT", "stdout", "banner")]
    out = _run_tool(_fill_buffer(entries))
    assert "一切正常" in out


def test_empty_buffer_fallback():
    out = _run_tool(LogStreamBuffer(maxlen=10))
    # 真实环境 logs/daemon.log 存在 → 文件回退；否则提示不在守护进程模式
    assert "守护进程日志" in out or "守护进程模式" in out


def test_registry_loads_tool():
    """_load_core_tools 能把 DaemonLogsTool 注册进注册表"""
    from webnet.ToolNet.registry import ToolRegistry

    reg = ToolRegistry()
    reg._load_core_tools()
    tool = reg.get_tool("daemon_logs")
    assert tool is not None
    assert tool.config["name"] == "daemon_logs"
    assert "自检" in tool.config["description"]


def test_line_clip_and_limit_cap():
    """超长日志行被截断、limit 上限 100"""
    from webnet.ToolNet.tools.core.daemon_logs import _MAX_LIMIT, _clip

    assert _MAX_LIMIT == 100
    long_line = "x" * 500
    clipped = _clip(long_line)
    assert len(clipped) == 201 and clipped.endswith("…")

    buf = _fill_buffer([("ERROR", "T", long_line)])
    out = _run_tool(buf, level="error", limit=500)
    assert "x" * 210 not in out                     # 500 字符长行不会原样进入输出
