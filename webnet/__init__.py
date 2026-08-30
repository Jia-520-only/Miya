"""
弹性分支子网集群

CrossNetEngine + NetManager 在启动时立即加载，
其余子网（ToolNet, HealthNet 等）按需懒加载，
减少启动时的模块导入开销。
"""

from .cross_net_engine import CrossNetEngine
from .net_manager import NetManager

_LAZY = {
    "HealthNet": ("webnet.health", "HealthNet"),
    "IoTNet": ("webnet.iot", "IoTNet"),
    "LifeNet": ("webnet.life", "LifeNet"),
    "ToolSubnet": ("webnet.ToolNet", "ToolSubnet"),
    "get_tool_registry": ("webnet.ToolNet", "get_tool_registry"),
    "get_tool_subnet": ("webnet.ToolNet", "get_tool_subnet"),
}


def __getattr__(name):
    if name in _LAZY:
        mod_path, attr_name = _LAZY[name]
        import importlib

        module = importlib.import_module(mod_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "NetManager",
    "CrossNetEngine",
    "LifeNet",
    "HealthNet",
    "IoTNet",
    "ToolSubnet",
    "get_tool_subnet",
    "get_tool_registry",
]
