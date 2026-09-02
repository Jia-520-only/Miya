"""Python 工具执行结果的回归测试。"""

import json

import pytest

from webnet.ToolNet.base import ToolContext
from webnet.ToolNet.tools.basic.python_interpreter import PythonInterpreter


@pytest.mark.anyio
async def test_python_interpreter_surfaces_fpdf_page_error(monkeypatch):
    from mcpserver.code_executor.service import CodeExecutorService

    async def fake_execute(self, _args):
        return json.dumps(
            {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "fpdf.errors.FPDFException: No page open, you need to call add_page() first",
            }
        )

    monkeypatch.setattr(CodeExecutorService, "_execute_code", fake_execute)

    result = await PythonInterpreter().execute({"code": "from fpdf import FPDF"}, ToolContext())

    assert result.startswith("执行错误 (退出码 1)")
    assert "pdf.add_page()" in result
