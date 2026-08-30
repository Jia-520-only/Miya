"""
弥娅记忆总线 (MemoryBus) — 系统唯一记忆入口
===========================================

此文件现已重定向到 memory.api.bus (V4.0 重构)。
所有对 `from memory.bus import MemoryBus` 的导入将自动使用新版 bus。

设计原则:
1. 单点接入 — 所有模块只能通过 MemoryBus 操作记忆
2. 智能路由 — 自动选择最优存储/检索策略
3. 管线组装 — 统一 Prompt 上下文化注入
4. 异步非阻塞 — 不阻塞主响应路径
"""

# 重定向到新版 MemoryBus
from memory.api.bus import (
    MemoryBus,
    RecallRequest,
    RecallResult,
    get_memory_bus,
    reset_memory_bus,
)

__all__ = [
    "MemoryBus",
    "RecallRequest",
    "RecallResult",
    "get_memory_bus",
    "reset_memory_bus",
]
