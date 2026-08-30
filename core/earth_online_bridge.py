"""地球online ↔ 弥娅本体 桥接层。

把游戏内事件 (服务券使用/商城兑换/关怀委托...) 送进弥娅的两个统一系统:

1. 统一主动协调器 (ProactiveCoordinator)
   - 用弥娅**当前人格**把事件重新表达成一条消息 (candidate_message 只是参考基调)
   - 经活跃消息平台发送给佳 (与自检/主动聊天/巡检共用统一限频、静默时段保护)

2. 统一记忆 (MemoryManager.store_unified_memory)
   - 以 assistant 角色写入对话总线 + MemoryNet
   - 记忆系统会自动分析其中的承诺/互动，必要时升级为长期自记忆
   - 下次运营周期的 [与佳的最近对话记忆] 也会读到它们 → 弥娅真的记得

所有函数都吞异常返回布尔——桥接失败绝不影响游戏主流程。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("Miya.EarthBridge")


async def deliver_via_proactive(
    event: Dict[str, Any],
    *,
    key: str,
    trigger_type: str = "earth_event",
    decision_hub: Any = None,
) -> bool:
    """把事件交给统一主动协调器：人格化重表达 → 平台发送 → 限频/静默保护。"""
    try:
        from core.proactive_coordinator import get_proactive_coordinator

        coordinator = get_proactive_coordinator()
        sent = await coordinator.submit_event(event, key=key, trigger_type=trigger_type)
        return bool(sent)
    except Exception as exc:
        logger.debug(f"[EarthBridge] 主动投递失败 (key={key}): {exc}")
        return False


def _resolve_memory_manager(memory_manager: Any = None, decision_hub: Any = None) -> Optional[Any]:
    if memory_manager is not None:
        return memory_manager
    if decision_hub is not None:
        manager = getattr(decision_hub, "memory_manager", None)
        if manager is not None:
            return manager
    return None


async def remember(
    content: str,
    *,
    memory_manager: Any = None,
    decision_hub: Any = None,
    source: str = "earth_online",
) -> bool:
    """把一句话写进弥娅的统一记忆 (assistant 角色，触发长期自记忆分析)。"""
    manager = _resolve_memory_manager(memory_manager, decision_hub)
    if manager is None or not str(content).strip():
        return False
    try:
        await manager.store_unified_memory(
            {
                "platform": "earth_online",
                "user_id": "default",
                "group_id": "",
                "message_type": "private",
                "_meta": {"source": source},
                "response": content,
            },
            role="assistant",
        )
        return True
    except Exception as exc:
        logger.debug(f"[EarthBridge] 记忆写入失败: {exc}")
        return False
