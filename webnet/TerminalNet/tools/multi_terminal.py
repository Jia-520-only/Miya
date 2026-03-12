"""
多终端管理工具 - 弥娅完全掌控多终端能力

功能：
1. 创建、切换、关闭多个终端
2. 并行执行命令
3. 自动任务编排和分配
4. 集成情绪染色
5. 记录到记忆系统

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from webnet.tools.base import BaseTool, ToolContext

# 延迟导入 LocalTerminalManager（避免循环依赖）
_terminal_manager_instance = None


def get_terminal_manager() -> Optional[Any]:
    """获取 LocalTerminalManager 单例"""
    global _terminal_manager_instance
    if _terminal_manager_instance is None:
        try:
            from core.local_terminal_manager import LocalTerminalManager
            _terminal_manager_instance = LocalTerminalManager()
        except Exception as e:
            logging.error(f"初始化 LocalTerminalManager 失败: {e}")
    return _terminal_manager_instance


class MultiTerminalTool(BaseTool):
    """
    多终端管理工具

    让弥娅拥有完全的多终端控制权，可以：
    - 创建不同类型的终端（CMD、PowerShell、Bash、Zsh等）
    - 在多个终端间切换
    - 并行执行命令
    - 自动关闭不需要的终端
    - 集成情绪系统和记忆系统
    """

    def __init__(self):
        super().__init__()
        self.name = "multi_terminal"
        self.manager = get_terminal_manager()
        self.logger = logging.getLogger("Tool.MultiTerminal")

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
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
            "name": "multi_terminal",
            "description": f"""管理多个终端窗口的创建、切换和关闭。仅当用户明确要求"创建终端"、"打开终端"、"新建窗口"、"切换终端"、"关闭终端"时调用。

当前环境：{platform_info}系统，{shell_info} shell，当前目录：{cwd}

⚡ 【重要】创建终端时，AI 必须根据当前操作系统自动选择合适的终端类型：
- Windows系统：自动使用 powershell
- Linux/BSD系统：自动使用 bash
- macOS系统：自动使用 zsh
不要询问用户选择终端类型，直接根据系统自动推断！

操作类型：
- create_terminal: 创建新终端（需要参数：name, terminal_type）
- list_terminals: 列出所有终端
- switch_terminal: 切换到指定终端（需要参数：session_id）
- close_terminal: 关闭指定终端（需要参数：session_id）
- execute_parallel: 在多个终端并行执行命令（需要参数：commands）
- execute_sequence: 在指定终端顺序执行命令（需要参数：session_id, sequence_commands）

终端类型：cmd(仅Windows), powershell(Windows/Linux), bash(Linux/macOS/Windows), zsh(macOS), sh(Unix)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "create_terminal",
                            "list_terminals",
                            "switch_terminal",
                            "close_terminal",
                            "execute_parallel",
                            "execute_sequence"
                        ],
                        "description": "要执行的操作类型"
                    },
                    "name": {
                        "type": "string",
                        "description": "终端名称（create_terminal时必填，其他操作可选）"
                    },
                    "terminal_type": {
                        "type": "string",
                        "enum": ["cmd", "powershell", "bash", "zsh", "sh"],
                        "description": "终端类型（create_terminal时必填）"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "会话ID（switch_terminal、close_terminal、execute_sequence时使用）"
                    },
                    "commands": {
                        "type": "object",
                        "description": "并行执行的命令映射（execute_parallel时使用，格式：{{\"session_id1\": \"command1\", \"session_id2\": \"command2\"}}）"
                    },
                    "sequence_commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "顺序执行的命令列表（execute_sequence时使用）"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "工作目录（可选，默认为当前目录）"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行多终端管理操作

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        action = args.get("action", "")

        if not action:
            return "❌ 缺少action参数"

        if not self.manager:
            return "❌ 终端管理器不可用"

        try:
            if action == "create_terminal":
                return await self._create_terminal(args, context)
            elif action == "list_terminals":
                return await self._list_terminals()
            elif action == "switch_terminal":
                return await self._switch_terminal(args, context)
            elif action == "close_terminal":
                return await self._close_terminal(args, context)
            elif action == "execute_parallel":
                return await self._execute_parallel(args, context)
            elif action == "execute_sequence":
                return await self._execute_sequence(args, context)
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            self.logger.error(f"执行操作失败: {e}", exc_info=True)
            return f"❌ 操作执行失败: {str(e)}"

    async def _create_terminal(self, args: Dict[str, Any], context: ToolContext) -> str:
        """创建新终端"""
        from core.terminal_types import TerminalType

        # 检查 manager 是否可用
        if not self.manager:
            self.logger.error("Terminal manager 未初始化，尝试重新获取...")
            self.manager = get_terminal_manager()
            if not self.manager:
                return "❌ 终端管理器不可用，请重启弥娅"

        name = args.get("name", "未命名终端")
        terminal_type_str = args.get("terminal_type", "cmd")
        working_dir = args.get("working_dir")

        self.logger.info(f"创建终端: name={name}, type={terminal_type_str}, dir={working_dir}")

        # 转换终端类型
        try:
            terminal_type = TerminalType.from_string(terminal_type_str)
        except ValueError:
            return f"❌ 不支持的终端类型: {terminal_type_str}"

        # 创建终端
        try:
            self.logger.info(f"调用 manager.create_terminal...")
            session_id = await self.manager.create_terminal(
                name=name,
                terminal_type=terminal_type,
                initial_dir=working_dir
            )

            result = f"✅ 终端创建成功\n"
            result += f"名称: {name}\n"
            result += f"类型: {terminal_type_str}\n"
            result += f"会话ID: {session_id}"

            # 记录到记忆
            if context.memory_engine:
                try:
                    from datetime import datetime
                    context.memory_engine.store_tide(
                        memory_id=f"create_terminal_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                        content={
                            'type': 'create_terminal',
                            'name': name,
                            'type': terminal_type_str,
                            'session_id': session_id
                        },
                        priority=0.4,
                        ttl=3600
                    )
                except Exception as e:
                    self.logger.warning(f"记录到记忆失败: {e}")

            return result

        except Exception as e:
            return f"❌ 创建终端失败: {str(e)}"

    async def _list_terminals(self) -> str:
        """列出所有终端"""
        try:
            all_status = self.manager.get_all_status()

            if not all_status:
                return "📭 当前没有活动终端"

            result = f"📋 终端列表（共 {len(all_status)} 个）\n\n"

            for session_id, status in all_status.items():
                active_marker = "🟢" if session_id == self.manager.active_session_id else "⚪"
                result += f"{active_marker} [{session_id}] {status.get('name', '未命名')}\n"
                result += f"   类型: {status.get('type', 'unknown')}\n"
                result += f"   状态: {status.get('status', 'unknown')}\n"
                result += f"   工作目录: {status.get('work_dir', 'unknown')}\n\n"

            return result

        except Exception as e:
            return f"❌ 获取终端列表失败: {str(e)}"

    async def _switch_terminal(self, args: Dict[str, Any], context: ToolContext) -> str:
        """切换终端"""
        session_id = args.get("session_id")

        if not session_id:
            return "❌ 缺少session_id参数"

        # 获取终端信息
        all_status = self.manager.get_all_status()
        if session_id not in all_status:
            return f"❌ 终端不存在: {session_id}"

        try:
            await self.manager.switch_session(session_id)
            terminal_info = all_status[session_id]

            result = f"✅ 已切换到终端\n"
            result += f"名称: {terminal_info.get('name', '未命名')}\n"
            result += f"类型: {terminal_info.get('type', 'unknown')}\n"
            result += f"会话ID: {session_id}"

            return result

        except Exception as e:
            return f"❌ 切换终端失败: {str(e)}"

    async def _close_terminal(self, args: Dict[str, Any], context: ToolContext) -> str:
        """关闭终端"""
        session_id = args.get("session_id")

        if not session_id:
            return "❌ 缺少session_id参数"

        # 获取终端信息
        all_status = self.manager.get_all_status()
        terminal_info = all_status.get(session_id)

        try:
            await self.manager.close_session(session_id)

            if terminal_info:
                result = f"✅ 已关闭终端\n"
                result += f"名称: {terminal_info.get('name', '未命名')}\n"
                result += f"类型: {terminal_info.get('type', 'unknown')}"
            else:
                result = f"✅ 已关闭终端: {session_id}"

            return result

        except Exception as e:
            return f"❌ 关闭终端失败: {str(e)}"

    async def _execute_parallel(self, args: Dict[str, Any], context: ToolContext) -> str:
        """并行执行命令"""
        commands = args.get("commands", {})

        if not commands:
            return "❌ 缺少commands参数"

        try:
            results = await self.manager.execute_parallel(commands)

            result = f"🚀 并行执行完成（共 {len(results)} 个任务）\n\n"

            for session_id, cmd_result in results.items():
                status = "✅" if cmd_result.success else "❌"
                result += f"{status} [{session_id}]\n"
                result += f"   命令: {cmd_result.command}\n"
                result += f"   输出: {cmd_result.stdout[:200] if cmd_result.stdout else ''}\n"
                if cmd_result.stderr:
                    result += f"   错误: {cmd_result.stderr[:200]}\n\n"
                else:
                    result += "\n"

            return result

        except Exception as e:
            return f"❌ 并行执行失败: {str(e)}"

    async def _execute_sequence(self, args: Dict[str, Any], context: ToolContext) -> str:
        """顺序执行命令"""
        session_id = args.get("session_id")
        sequence_commands = args.get("sequence_commands", [])

        if not session_id:
            return "❌ 缺少session_id参数"

        if not sequence_commands:
            return "❌ 缺少sequence_commands参数"

        try:
            results = await self.manager.execute_sequence(session_id, sequence_commands)

            result = f"📝 顺序执行完成（共 {len(results)} 个命令）\n\n"

            for i, cmd_result in enumerate(results, 1):
                status = "✅" if cmd_result.success else "❌"
                result += f"{status} [{i}/{len(results)}] {cmd_result.command}\n"
                result += f"   输出: {cmd_result.stdout[:200] if cmd_result.stdout else ''}\n"
                if cmd_result.stderr:
                    result += f"   错误: {cmd_result.stderr[:200]}\n"
                result += "\n"

            return result

        except Exception as e:
            return f"❌ 顺序执行失败: {str(e)}"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        action = args.get("action")

        if not action:
            return False, "缺少必填参数: action"

        if action == "create_terminal":
            if not args.get("terminal_type"):
                return False, "create_terminal 需要 terminal_type 参数"

        if action in ["switch_terminal", "close_terminal", "execute_sequence"]:
            if not args.get("session_id"):
                return False, f"{action} 需要 session_id 参数"

        if action == "execute_parallel":
            if not args.get("commands"):
                return False, "execute_parallel 需要 commands 参数"

        if action == "execute_sequence":
            if not args.get("sequence_commands"):
                return False, "execute_sequence 需要 sequence_commands 参数"

        return True, None
