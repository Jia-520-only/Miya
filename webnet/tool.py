"""
[废弃] 工具执行节点

⚠️ 此文件已废弃，请使用 webnet/ToolNet/ 中的完整工具系统实现

原因：
- webnet/tool.py 是旧版简化的工具系统
- webnet/ToolNet/ 是符合弥娅子网架构的完整工具系统
- 新系统提供更好的 M-Link 集成、工具注册和执行能力

迁移指南：
- 替换导入：from webnet.tool import ToolNet -> from webnet.ToolNet import get_tool_subnet
- 参考：webnet/ToolNet/__init__.py 中的实现

此文件仅保留用于向后兼容，未来版本将删除
"""
import warnings

def __getattr__(name: str):
    """当尝试访问此模块时发出警告"""
    warnings.warn(
        f"webnet.tool 模块已废弃，请使用 webnet.ToolNet 代替。访问 '{name}' 将导致错误。",
        DeprecationWarning,
        stacklevel=2
    )
    raise AttributeError(f"'webnet.tool' module is deprecated. Use 'webnet.ToolNet' instead.")
