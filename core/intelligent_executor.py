#!/usr/bin/env python3
"""
智能命令执行器
让弥娅具备完整的终端掌控能力
"""

import enum

try:
    from core.terminal.base.types import CommandCategory, ExecutionMode
    from core.terminal.safety import SafetyChecker
except ImportError:  # core.terminal 包在当前仓库不存在（历史遗留），提供最小回退定义

    class ExecutionMode(enum.Enum):
        DIRECT = "direct"
        SIMULATE = "simulate"
        SAFE = "safe"
        STEP_BY_STEP = "step_by_step"

    class CommandCategory(enum.Enum):
        FILE_SYSTEM = "file_system"
        PROCESS_MANAGEMENT = "process_management"
        NETWORK = "network"
        SYSTEM_INFO = "system_info"
        CUSTOM = "custom"

    class SafetyChecker:
        def check(self, parsed_command):
            command = (
                parsed_command.get("base_command", "") if isinstance(parsed_command, dict) else str(parsed_command)
            )
            dangerous = any(
                kw in command.lower() for kw in ("rm -rf", "mkfs", "dd if=", "shutdown", "reboot", "format")
            )
            return {"level": 3 if dangerous else 1, "requires_confirmation": dangerous}


"""
智能命令执行器
让弥娅具备完整的终端掌控能力
"""

import asyncio
import builtins
import contextlib
import logging
import os
import re
import shlex
import sys
import tempfile
import threading
import time

from pathlib import Path
from typing import Any, Dict, List

import psutil

logger = logging.getLogger(__name__)


class IntelligentExecutor:
    """智能命令执行器"""

    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"exec_{int(time.time())}"
        self.working_directory = os.getcwd()
        self.execution_mode = ExecutionMode.DIRECT
        self.safety_level = 5  # 1-10, 10为最安全
        self.command_history = []
        self.process_registry = {}  # 进程注册表

        # 初始化组件
        self.command_parser = CommandParser()
        self.safety_checker = SafetyChecker()
        self.context_manager = ContextManager()
        self.execution_monitor = ExecutionMonitor()

        logger.info(f"智能执行器初始化完成 - 会话ID: {self.session_id}")

    async def execute_intelligent(self, user_input: str) -> Dict[str, Any]:
        """智能执行命令"""
        logger.info(f"智能执行: {user_input}")

        # 1. 解析用户输入
        parsed_command = self.command_parser.parse(user_input)

        # 2. 检查安全性
        safety_report = self.safety_checker.check(parsed_command)

        # 3. 获取上下文信息
        context = self.context_manager.get_context(self.working_directory)

        # 4. 选择执行模式
        mode = self._select_execution_mode(parsed_command, safety_report)

        # 5. 执行命令
        if mode == ExecutionMode.SIMULATE:
            result = await self._simulate_execution(parsed_command, context)
        elif mode == ExecutionMode.SAFE:
            result = await self._safe_execution(parsed_command, context, safety_report)
        else:
            result = await self._direct_execution(parsed_command, context)

        # 6. 监控执行过程
        if result.get("process_id"):
            self.execution_monitor.monitor_process(result["process_id"], parsed_command, self.session_id)

        # 7. 更新上下文
        self.context_manager.update_context(result, parsed_command)

        # 8. 记录历史
        self._record_execution(user_input, parsed_command, result)

        return {
            "success": result.get("success", False),
            "output": result.get("output", ""),
            "error": result.get("error", ""),
            "execution_mode": mode.value,
            "safety_level": safety_report.get("level", 0),
            "process_id": result.get("process_id"),
            "execution_time": result.get("execution_time", 0),
            "suggestions": self._generate_suggestions(parsed_command, result),
        }

    def _select_execution_mode(self, parsed_command: Dict, safety_report: Dict) -> ExecutionMode:
        """选择执行模式"""
        if self.execution_mode == ExecutionMode.SIMULATE:
            return ExecutionMode.SIMULATE

        safety_report.get("level", 0)
        requires_confirmation = safety_report.get("requires_confirmation", False)

        if requires_confirmation and self.safety_level > 3:
            return ExecutionMode.SAFE

        if parsed_command.get("complexity", 0) > 7:
            return ExecutionMode.STEP_BY_STEP

        return ExecutionMode.DIRECT

    async def _direct_execution(self, parsed_command: Dict, context: Dict) -> Dict[str, Any]:
        """直接执行"""
        start_time = time.time()

        try:
            # 构建完整命令
            command = self._build_command(parsed_command, context)

            # 执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )

            # 注册进程
            process_id = process.pid
            self.process_registry[process_id] = {
                "command": command,
                "start_time": start_time,
                "session_id": self.session_id,
            }

            # 等待完成
            stdout, stderr = await process.communicate()
            execution_time = time.time() - start_time

            return {
                "success": process.returncode == 0,
                "output": stdout.decode("utf-8", errors="ignore"),
                "error": stderr.decode("utf-8", errors="ignore"),
                "exit_code": process.returncode,
                "process_id": process_id,
                "execution_time": execution_time,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"直接执行失败: {e}")

            return {"success": False, "output": "", "error": str(e), "exit_code": -1, "execution_time": execution_time}

    async def _safe_execution(self, parsed_command: Dict, context: Dict, safety_report: Dict) -> Dict[str, Any]:
        """安全执行（需要确认）"""
        # 这里可以实现确认逻辑
        # 暂时使用直接执行
        return await self._direct_execution(parsed_command, context)

    async def _simulate_execution(self, parsed_command: Dict, context: Dict) -> Dict[str, Any]:
        """模拟执行"""
        command = self._build_command(parsed_command, context)

        return {
            "success": True,
            "output": f"模拟执行: {command}\n此命令将被执行但不会实际运行",
            "error": "",
            "exit_code": 0,
            "execution_time": 0,
            "simulated": True,
        }

    def _build_command(self, parsed_command: Dict, context: Dict) -> str:
        """构建完整命令"""
        base_command = parsed_command.get("base_command", "")
        arguments = parsed_command.get("arguments", [])
        flags = parsed_command.get("flags", [])

        # 添加上下文相关参数
        if context.get("sudo_required", False) and "sudo" not in base_command:
            base_command = f"sudo {base_command}"

        # 构建命令
        parts = [base_command] + flags + arguments
        return " ".join(parts)

    def _generate_suggestions(self, parsed_command: Dict, result: Dict) -> List[str]:
        """生成后续建议"""
        suggestions = []

        if result.get("success"):
            # 成功执行的后续建议
            command_type = parsed_command.get("category", "")

            if command_type == CommandCategory.FILE_SYSTEM.value:
                suggestions.extend(
                    [
                        "使用 'ls -la' 查看详细文件信息",
                        "使用 'du -sh' 查看目录大小",
                        "使用 'find . -type f -name \"*.py\"' 查找Python文件",
                    ]
                )
            elif command_type == CommandCategory.PROCESS_MANAGEMENT.value:
                suggestions.extend(
                    [
                        "使用 'ps aux | grep python' 查看Python进程",
                        "使用 'top' 查看系统进程",
                        "使用 'kill -9 <PID>' 终止进程",
                    ]
                )
            elif command_type == CommandCategory.NETWORK.value:
                suggestions.extend(
                    [
                        "使用 'netstat -tulpn' 查看监听端口",
                        "使用 'curl -I <URL>' 查看HTTP头信息",
                        "使用 'traceroute <主机>' 跟踪路由",
                    ]
                )
        else:
            # 失败执行的修复建议
            error = result.get("error", "").lower()

            if "permission denied" in error:
                suggestions.append("尝试使用 'sudo' 或检查文件权限")
            elif "command not found" in error:
                suggestions.append("检查命令是否安装，或使用完整路径")
            elif "no such file or directory" in error:
                suggestions.append("检查文件路径是否正确")

        return suggestions[:3]

    def _record_execution(self, user_input: str, parsed_command: Dict, result: Dict):
        """记录执行历史"""
        entry = {
            "timestamp": time.time(),
            "user_input": user_input,
            "parsed_command": parsed_command,
            "result": {
                "success": result.get("success", False),
                "exit_code": result.get("exit_code", 0),
                "execution_time": result.get("execution_time", 0),
            },
            "working_directory": self.working_directory,
            "session_id": self.session_id,
        }

        self.command_history.append(entry)

        # 限制历史记录大小
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-50:]

    async def execute_script(self, script_content: str, script_type: str = "bash") -> Dict[str, Any]:
        """执行脚本"""
        logger.info(f"执行{script_type}脚本")

        # 创建临时脚本文件
        temp_fd, temp_file = tempfile.mkstemp(prefix="miya_script_", suffix=f".{script_type}")
        os.close(temp_fd)

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(script_content)

            # 设置执行权限
            os.chmod(temp_file, 0o700)

            # 执行脚本
            if script_type == "bash":
                command = f"bash {temp_file}"
            elif script_type == "python":
                command = f"python {temp_file}"
            elif script_type == "powershell":
                command = f"powershell -File {temp_file}"
            else:
                command = temp_file

            result = await self.execute_intelligent(command)

            # 清理临时文件
            with contextlib.suppress(builtins.BaseException):
                os.remove(temp_file)

            return result

        except Exception as e:
            logger.error(f"执行脚本失败: {e}")

            # 清理临时文件
            with contextlib.suppress(builtins.BaseException):
                os.remove(temp_file)

            return {"success": False, "output": "", "error": str(e), "execution_time": 0}

    def get_execution_history(self, limit: int = 10) -> List[Dict]:
        """获取执行历史"""
        return self.command_history[-limit:] if self.command_history else []

    def set_execution_mode(self, mode: ExecutionMode):
        """设置执行模式"""
        self.execution_mode = mode
        logger.info(f"执行模式设置为: {mode.value}")

    def set_safety_level(self, level: int):
        """设置安全级别"""
        if 1 <= level <= 10:
            self.safety_level = level
            logger.info(f"安全级别设置为: {level}")
        else:
            logger.warning(f"无效的安全级别: {level}，保持为: {self.safety_level}")


class CommandParser:
    """命令解析器"""

    def __init__(self):
        self.command_patterns = self._load_patterns()
        self.command_aliases = self._load_aliases()

    def _load_patterns(self) -> Dict[str, Dict]:
        """加载命令模式"""
        return {
            "file_operations": {
                "patterns": [r"^ls\b", r"^cd\b", r"^cp\b", r"^mv\b", r"^rm\b", r"^mkdir\b"],
                "category": CommandCategory.FILE_SYSTEM.value,
            },
            "process_operations": {
                "patterns": [r"^ps\b", r"^kill\b", r"^top\b", r"^htop\b"],
                "category": CommandCategory.PROCESS_MANAGEMENT.value,
            },
            "network_operations": {
                "patterns": [r"^ping\b", r"^curl\b", r"^wget\b", r"^ssh\b"],
                "category": CommandCategory.NETWORK.value,
            },
            "system_info": {
                "patterns": [r"^uname\b", r"^df\b", r"^free\b", r"^whoami\b"],
                "category": CommandCategory.SYSTEM_INFO.value,
            },
        }

    def _load_aliases(self) -> Dict[str, str]:
        """加载命令别名"""
        return {
            "列表": "ls",
            "目录": "ls",
            "移动": "mv",
            "复制": "cp",
            "删除": "rm",
            "创建目录": "mkdir",
            "查看进程": "ps",
            "终止进程": "kill",
            "网络测试": "ping",
            "下载": "curl",
            "系统信息": "uname -a",
        }

    def parse(self, user_input: str) -> Dict[str, Any]:
        """解析用户输入"""
        # 清理输入
        clean_input = user_input.strip()

        # 检查别名
        if clean_input in self.command_aliases:
            clean_input = self.command_aliases[clean_input]

        # 分词
        try:
            parts = shlex.split(clean_input)
        except:
            parts = clean_input.split()

        if not parts:
            return {"raw_input": clean_input, "valid": False}

        base_command = parts[0]
        arguments = parts[1:] if len(parts) > 1 else []

        # 分类命令
        category = self._categorize_command(base_command)

        # 分析参数
        flags = [arg for arg in arguments if arg.startswith("-")]
        non_flag_args = [arg for arg in arguments if not arg.startswith("-")]

        # 评估复杂度
        complexity = self._assess_complexity(clean_input)

        return {
            "raw_input": clean_input,
            "base_command": base_command,
            "arguments": non_flag_args,
            "flags": flags,
            "category": category,
            "complexity": complexity,
            "valid": True,
        }

    def _categorize_command(self, command: str) -> str:
        """分类命令"""
        for _category, info in self.command_patterns.items():
            for pattern in info["patterns"]:
                if re.match(pattern, command, re.IGNORECASE):
                    return info["category"]

        return CommandCategory.CUSTOM.value

    def _assess_complexity(self, command: str) -> int:
        """评估复杂度 (1-10)"""
        complexity = 1

        # 管道和重定向增加复杂度
        if any(char in command for char in ["|", ">", "<", "&&", "||"]):
            complexity += 3

        # 脚本执行增加复杂度
        if any(cmd in command for cmd in ["bash", "sh", "python", "perl"]):
            complexity += 2

        # 危险命令增加复杂度
        if any(cmd in command.lower() for cmd in ["rm -rf", "chmod 777", "dd if="]):
            complexity += 5

        return min(complexity, 10)


class ContextManager:
    """上下文管理器"""

    def get_context(self, working_directory: str) -> Dict[str, Any]:
        """获取当前上下文"""
        context = {
            "working_directory": working_directory,
            "user": os.getenv("USER") or os.getenv("USERNAME"),
            "home_directory": str(Path.home()),
            "sudo_required": False,
            "environment": {},
        }

        # 检查当前目录权限
        try:
            # 简单检查写权限
            test_file = os.path.join(working_directory, ".miya_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            context["writable"] = True
        except:
            context["writable"] = False
            context["sudo_required"] = True

        # 获取环境信息
        context["environment"].update(
            {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "path": os.getenv("PATH", "").split(os.pathsep)[:5],
            }
        )

        return context

    def update_context(self, result: Dict, parsed_command: Dict):
        """更新上下文"""
        # 这里可以根据执行结果更新上下文
        # 例如：命令执行后目录改变等
        pass


class ExecutionMonitor:
    """执行监控器"""

    def __init__(self):
        self.monitored_processes = {}

    def monitor_process(self, process_id: int, command: Dict, session_id: str):
        """监控进程"""
        self.monitored_processes[process_id] = {
            "command": command,
            "session_id": session_id,
            "start_time": time.time(),
            "status": "running",
        }

        # 启动监控线程
        thread = threading.Thread(target=self._monitor_process_thread, args=(process_id,), daemon=True)
        thread.start()

    def _monitor_process_thread(self, process_id: int):
        """监控进程线程"""
        try:
            # 等待进程结束
            while True:
                try:
                    process = psutil.Process(process_id)

                    # 检查进程状态
                    status = process.status()
                    cpu_percent = process.cpu_percent(interval=0.1)
                    memory_mb = process.memory_info().rss / 1024 / 1024

                    # 更新监控信息
                    if process_id in self.monitored_processes:
                        self.monitored_processes[process_id].update(
                            {
                                "status": status,
                                "cpu_percent": cpu_percent,
                                "memory_mb": memory_mb,
                                "update_time": time.time(),
                            }
                        )

                    # 检查是否结束
                    if status in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                        break

                    time.sleep(1)

                except psutil.NoSuchProcess:
                    # 进程已结束
                    break
                except Exception as e:
                    logger.error(f"监控进程{process_id}失败: {e}")
                    break

            # 清理监控记录
            if process_id in self.monitored_processes:
                self.monitored_processes[process_id]["status"] = "finished"

                # 保留一段时间后清理
                threading.Timer(
                    300,  # 5分钟后清理
                    lambda: self._cleanup_process(process_id),
                ).start()

        except Exception as e:
            logger.error(f"监控线程异常: {e}")

    def _cleanup_process(self, process_id: int):
        """清理进程监控记录"""
        if process_id in self.monitored_processes:
            del self.monitored_processes[process_id]
            logger.debug(f"清理进程监控记录: {process_id}")

    def get_monitored_processes(self) -> Dict[int, Dict]:
        """获取监控中的进程"""
        return self.monitored_processes.copy()


# 使用示例
async def example_usage():
    """使用示例"""
    executor = IntelligentExecutor(session_id="demo_session")

    # 设置执行模式
    executor.set_execution_mode(ExecutionMode.DIRECT)
    executor.set_safety_level(7)

    # 执行命令
    commands = ["ls -la", "查看系统信息", "ps aux | grep python", "创建一个测试目录"]

    for cmd in commands:
        print(f"\n执行命令: {cmd}")
        result = await executor.execute_intelligent(cmd)

        print(f"结果: {'成功' if result['success'] else '失败'}")
        print(f"模式: {result['execution_mode']}")
        print(f"安全等级: {result['safety_level']}")

        if result["output"]:
            print(f"输出: {result['output'][:200]}...")

        if result["error"]:
            print(f"错误: {result['error']}")

        if result["suggestions"]:
            print(f"建议: {result['suggestions']}")

    # 查看历史
    print("\n执行历史:")
    history = executor.get_execution_history(3)
    for i, entry in enumerate(history, 1):
        print(f"{i}. {entry['user_input']}")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 运行示例
    asyncio.run(example_usage())
