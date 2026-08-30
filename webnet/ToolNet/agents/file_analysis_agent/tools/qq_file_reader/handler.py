"""
QQ文件读取工具 handler
"""

from typing import Any, Dict

from webnet.ToolNet.tools.qq.qq_file_reader import QQFileReaderTool


async def execute(args: Dict[str, Any], context: Any) -> str:
    """读取QQ文件"""
    try:
        tool = QQFileReaderTool()
        result = await tool.execute(args, context)
        return result
    except Exception as e:
        return f"文件读取失败: {str(e)}"
