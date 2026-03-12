"""
终端命令工具 - 让弥娅完全掌控命令行

功能：
1. 自然语言理解命令（类似 claude-code）
2. 执行系统命令
3. 集成情绪染色
4. 记录到记忆系统

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
import subprocess
import asyncio
import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from webnet.tools.base import BaseTool, ToolContext

# 延迟导入 TerminalTool（避免循环依赖）
_terminal_tool_instance = None


def get_terminal_tool() -> Optional[Any]:
    """获取 TerminalTool 单例"""
    global _terminal_tool_instance
    if _terminal_tool_instance is None:
        try:
            from tools.terminal import TerminalTool
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / 'config' / 'terminal_config.json'
            _terminal_tool_instance = TerminalTool(str(config_path))
        except Exception as e:
            logging.error(f"初始化 TerminalTool 失败: {e}")
    return _terminal_tool_instance


class TerminalCommandTool(BaseTool):
    """
    终端命令工具

    让弥娅拥有完全的命令行控制权，可以：
    - 查看文件和目录
    - 启动程序和脚本
    - 执行系统命令
    - 管理文件和权限
    """

    def __init__(self):
        super().__init__()
        self.name = "terminal_command"
        self.terminal_tool = get_terminal_tool()
        self.logger = logging.getLogger("Tool.TerminalCommand")

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        import sys

        # 获取平台信息
        platform_info = "Linux/BSD/Unix"
        shell_info = "Bash"
        if sys.platform == 'win32':
            platform_info = "Windows"
            shell_info = "PowerShell"
        elif sys.platform == 'darwin':
            platform_info = "macOS"
            shell_info = "Zsh"

        # 获取当前工作目录
        import os
        cwd = os.getcwd()

        return {
            "name": "terminal_command",
            "description": f"""执行单个系统命令。仅当用户要求执行明确的系统命令（如ls、cd、pwd、git、python等）或查看系统信息时调用。

当前环境：{platform_info}系统，{shell_info} shell，当前目录：{cwd}

重要：如果用户要求"创建终端"、"打开终端"或"新建窗口"，必须调用multi_terminal工具，而不是此工具！""",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令字符串。例如：'ls', 'firefox', 'python script.py', 'git status', 'npm install', 'pwd'"
                    }
                },
                "required": ["command"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行终端命令

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        command = args.get("command", "")

        if not command:
            return "❌ 缺少命令参数"

        self.logger.info(f"执行命令: {command}")

        try:
            # 使用 TerminalTool 执行命令
            if self.terminal_tool:
                # 传递情绪和记忆给 TerminalTool
                self.terminal_tool.emotion = context.emotion
                self.terminal_tool.memory_engine = context.memory_engine

                # 注意：这里使用 user_confirm=True，因为 AI 已经理解了用户意图
                # 不需要再次让用户确认
                result = self.terminal_tool.execute(command, user_confirm=True)
                formatted = self.terminal_tool.format_result(result)
                return formatted
            else:
                # TerminalTool 不可用，使用简化版本
                return await self._execute_direct(command, context)

        except Exception as e:
            self.logger.error(f"执行命令失败: {e}", exc_info=True)
            return f"❌ 命令执行失败: {str(e)}"

    async def _execute_direct(self, command: str, context: ToolContext) -> str:
        """
        直接执行命令（简化版本，不使用 TerminalTool）

        Args:
            command: 命令字符串
            context: 执行上下文

        Returns:
            执行结果
        """
        try:
            # 使用平台适配器进行命令翻译和路径展开
            from tools.terminal.platform_adapter import get_platform_adapter

            adapter = get_platform_adapter()

            # 展开路径（如果有 ~ 符号）
            if hasattr(adapter, '_expand_home_directory'):
                command = adapter._expand_home_directory(command)

            # 翻译命令（Windows -> PowerShell）
            translated_command = adapter.translate_command(command)

            self.logger.info(f"执行命令: {command} -> {translated_command}")

            # 执行命令
            process = await asyncio.create_subprocess_shell(
                translated_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )

            stdout, stderr = await process.communicate()

            # 解码输出
            stdout_text = stdout.decode('utf-8', errors='ignore')
            stderr_text = stderr.decode('utf-8', errors='ignore')

            # 组合结果
            if stderr_text and process.returncode != 0:
                # 命令执行失败
                result = f"❌ 命令执行失败 (退出码: {process.returncode})\n\n错误输出:\n{stderr_text}"
                if stdout_text:
                    result += f"\n\n标准输出:\n{stdout_text}"
            else:
                # 命令执行成功
                result = f"✅ 命令执行成功\n\n{stdout_text}"
                if stderr_text:
                    result += f"\n\n警告信息:\n{stderr_text}"

            return result

        except Exception as e:
            return f"❌ 执行命令时发生异常: {str(e)}"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        command = args.get("command", "")
        if not command:
            return False, "缺少必填参数: command"
        return True, None
