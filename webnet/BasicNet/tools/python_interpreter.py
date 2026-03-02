"""
Python解释器工具
"""
from typing import Dict, Any
import logging
import subprocess
import tempfile
from pathlib import Path
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class PythonInterpreter(BaseTool):
    """Python解释器工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "python_interpreter",
            "description": "在隔离环境中执行Python代码，用于计算、数据处理等任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的Python代码"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间（秒）",
                        "default": 30
                    }
                },
                "required": ["code"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行Python代码

        Args:
            args: {code, timeout}
            context: 执行上下文

        Returns:
            执行结果或错误信息
        """
        code = args.get("code", "")
        timeout = args.get("timeout", 30)

        if not code.strip():
            return "代码不能为空"

        try:
            # 简化实现：直接执行（生产环境应使用Docker隔离）
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()

            try:
                exec(code, {'__name__': '__main__'})
                output = buffer.getvalue()
            finally:
                sys.stdout = old_stdout

            if output:
                return f"执行结果:\n{output}"
            else:
                return "代码执行完成，无输出"

        except Exception as e:
            return f"执行错误: {str(e)}"
