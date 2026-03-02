"""工具系统"""
from .base import ToolRegistry, BaseTool, ToolContext

__all__ = ['ToolRegistry', 'BaseTool', 'ToolContext']

def get_tool_registry() -> ToolRegistry:
    """获取工具注册表实例"""
    registry = ToolRegistry()
    registry.load_all_tools()
    return registry
