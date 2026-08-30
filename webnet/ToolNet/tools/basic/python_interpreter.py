"""
Python解释器工具

统一复用 mcpserver.code_executor 的子进程执行器（真正隔离 + 可终止超时），
避免进程内 exec() 的超时后线程仍继续运行的问题。
"""

import json
import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class PythonInterpreter(BaseTool):
    """Python解释器工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "python_interpreter",
            "description": "在隔离环境中执行Python代码，用于计算、数据处理等任务。当用户明确要求执行Python代码、计算、数据分析等时必须调用此工具。重要：此工具执行实际代码执行操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的Python代码"},
                    "timeout": {"type": "integer", "description": "超时时间（秒）", "default": 30},
                },
                "required": ["code"],
            },
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
            from mcpserver.code_executor.service import CodeExecutorService

            svc = CodeExecutorService()
            result_json = await svc._execute_code({"code": code, "language": "python", "timeout": timeout})
            result = json.loads(result_json)

            if "error" in result:
                return f"执行错误: {result['error']}"

            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            if stderr:
                return f"执行结果:\n{stdout}\n\n[stderr]\n{stderr}"
            if stdout:
                return f"执行结果:\n{stdout}"
            return "代码执行完成，无输出"

        except Exception as e:
            return f"执行错误: {str(e)}"
