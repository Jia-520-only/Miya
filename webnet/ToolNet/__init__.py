"""
ToolNet - 弥娅工具子网

> 符合弥娅蛛网式分布式架构的工具子网实现
>
> 架构特点：
> - 通过 M-Link 与其他子网通信
> - 支持工具注册和动态加载
> - 与弥娅核心松耦合
> - 兼容旧版 tools/ 系统

目录结构:
ToolNet/
├── __init__.py              # 子网入口
├── subnet.py                # 子网基类
├── handlers/                # 工具处理器
│   ├── basic.py            # 基础工具
│   ├── message.py          # 消息工具
│   ├── group.py            # 群工具
│   ├── memory.py           # 记忆工具（统一接口）
│   ├── knowledge.py        # 知识库工具
│   ├── cognitive.py        # 认知工具
│   ├── bilibili.py         # B站工具
│   └── scheduler.py        # 定时任务工具
├── adapters/               # M-Link 适配器
│   └── mlink_adapter.py   # M-Link 通信适配
└── registry.py             # 工具注册表（兼容层）
"""
import logging
from typing import Any, Dict, List, Optional
from .subnet import ToolSubnet
from .registry import ToolRegistry


logger = logging.getLogger(__name__)


__all__ = [
    'ToolSubnet',
    'ToolRegistry',
    'get_tool_subnet',
    'get_tool_registry',
]


# 全局子网实例
_tool_subnet = None


def get_tool_subnet(
    memory_engine: Any = None,
    cognitive_memory: Any = None,
    onebot_client: Any = None,
    scheduler: Any = None
) -> ToolSubnet:
    """获取 ToolNet 子网单例

    Args:
        memory_engine: 记忆引擎实例
        cognitive_memory: 认知记忆系统实例
        onebot_client: OneBot 客户端
        scheduler: 任务调度器

    Returns:
        ToolSubnet 实例
    """
    global _tool_subnet
    if _tool_subnet is None:
        _tool_subnet = ToolSubnet(
            memory_engine=memory_engine,
            cognitive_memory=cognitive_memory,
            onebot_client=onebot_client,
            scheduler=scheduler
        )
        logger.info("ToolNet 子网已初始化")
    return _tool_subnet


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例（兼容旧版）"""
    subnet = get_tool_subnet()
    return subnet.registry
