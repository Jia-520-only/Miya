"""
弥娅记忆系统 — 公共 API 层
==========================
这是整个记忆系统的唯一对外入口。所有外部模块只能通过此层访问记忆功能。

用法:
    from memory import MemoryBus

    bus = await MemoryBus.instance()

    # 存储对话
    await bus.store_dialogue("你好", role="user", user_id="123")

    # 检索记忆
    result = await bus.recall("颜色偏好", user_id="123")

    # Prompt 注入
    ctx = await bus.inject(user_id="123", user_input="我喜欢蓝色")

    # 认知操作
    await bus.cognitive.store(thinking="...", emotions={"joy": 7})
"""

from memory.api.bus import MemoryBus, RecallRequest, RecallResult, get_memory_bus, reset_memory_bus

__all__ = [
    "MemoryBus",
    "RecallRequest",
    "RecallResult",
    "get_memory_bus",
    "reset_memory_bus",
]
