"""
QQ工具模块 - 向后兼容层

这个文件是为了解决导入错误而创建的。
实际的QQ工具位于 webnet/ToolNet/tools/qq/ 目录中。
"""

# 从实际的QQ工具模块导入
from webnet.ToolNet.tools.qq import (
    QQEmojiTool,
    QQFileReaderTool,
    QQImageAnalyzerTool,
)

# 导出相同的接口
__all__ = [
    "QQEmojiTool",
    "QQFileReaderTool",
    "QQImageAnalyzerTool",
]
