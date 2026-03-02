"""
工具适配器 - 连接 AI 客户端和工具系统
"""
import logging
from typing import Dict, Any, Optional
from webnet.tools.base import ToolContext


logger = logging.getLogger(__name__)


class ToolAdapter:
    """工具适配器 - 执行工具调用"""

    def __init__(self):
        self.tool_registry: Optional[Any] = None

    def set_tool_registry(self, registry: Any):
        """设置工具注册表"""
        self.tool_registry = registry

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 上下文信息

        Returns:
            执行结果
        """
        if not self.tool_registry:
            logger.warning(f"工具注册表未设置，无法执行工具: {tool_name}")
            return f"错误：工具系统未初始化"

        try:
            # 从注册表获取工具
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                logger.warning(f"未找到工具: {tool_name}")
                return f"错误：未找到工具 '{tool_name}'"

            # 创建工具上下文
            tool_context = ToolContext(**context)

            # 执行工具
            logger.info(f"执行工具: {tool_name}, 参数: {args}")
            result = await tool.execute(args, tool_context)
            logger.info(f"工具执行完成: {tool_name}")
            return result

        except Exception as e:
            logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return f"错误：工具执行失败 - {str(e)}"


# 全局适配器实例
_adapter = None


def get_tool_adapter() -> ToolAdapter:
    """获取全局工具适配器实例"""
    global _adapter
    if _adapter is None:
        _adapter = ToolAdapter()
    return _adapter


def set_tool_adapter(adapter: ToolAdapter):
    """设置全局工具适配器"""
    global _adapter
    _adapter = adapter
