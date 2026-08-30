"""
命令执行器模块
支持同步和异步命令执行
"""
import asyncio
import subprocess
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from .platform_adapter import PlatformAdapter, get_platform_adapter
from .platform_detector import Platform

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """命令执行结果"""
    command: str                           # 执行的命令
    return_code: int                        # 返回码
    stdout: str                            # 标准输出
    stderr: str                            # 错误输出
    success: bool                          # 是否成功
    execution_time: float                   # 执行时间（秒）
    platform: str                          # 执行平台
    timestamp: datetime                    # 执行时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'command': self.command,
            'return_code': self.return_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'success': self.success,
            'execution_time': self.execution_time,
            'platform': self.platform,
            'timestamp': self.timestamp.isoformat()
        }


class CommandExecutor:
    """命令执行器 - 支持同步和异步执行"""

    def __init__(self, adapter: Optional[PlatformAdapter] = None):
        """
        初始化命令执行器

        Args:
            adapter: 平台适配器（None 表示自动检测）
        """
        self.adapter = adapter or get_platform_adapter()
        self.platform = self.adapter.platform
        self.execution_count = 0
        self.success_count = 0
        self.total_execution_time = 0.0

    def execute(self, command: str, timeout: int = 30, check_security: bool = True) -> ExecutionResult:
        """
        同步执行命令

        Args:
            command: 命令字符串
            timeout: 超时时间（秒）
            check_security: 是否进行安全检查（由 SecurityAuditor 处理）

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = datetime.now()
        logger.info(f"执行命令: {command}")

        # 执行命令
        return_code, stdout, stderr = self.adapter.execute_command(command, timeout)

        # 计算执行时间
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # 更新统计
        self.execution_count += 1
        if return_code == 0:
            self.success_count += 1
        self.total_execution_time += execution_time

        # 创建结果对象
        result = ExecutionResult(
            command=command,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            success=(return_code == 0),
            execution_time=execution_time,
            platform=self.platform.value,
            timestamp=start_time
        )

        # 记录结果
        if result.success:
            logger.info(f"命令执行成功，耗时 {execution_time:.2f}秒")
        else:
            logger.warning(f"命令执行失败: {stderr}")

        return result

    async def execute_async(self, command: str, timeout: int = 30) -> ExecutionResult:
        """
        异步执行命令

        Args:
            command: 命令字符串
            timeout: 超时时间（秒）

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = datetime.now()
        logger.info(f"异步执行命令: {command}")

        try:
            if self.platform == Platform.WINDOWS:
                # Windows PowerShell
                ps_command = self.adapter.translate_command(command)
                proc = await asyncio.create_subprocess_exec(
                    'powershell', '-Command', ps_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    text=False
                )
            else:
                # Linux/MacOS Bash
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    text=False
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )

                # 解码输出
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')
                return_code = proc.returncode

            except asyncio.TimeoutError:
                proc.kill()
                return_code, stdout, stderr = -1, "", f"命令执行超时（{timeout}秒）"

        except Exception as e:
            return_code, stdout, stderr = -1, "", f"命令执行失败: {str(e)}"

        # 计算执行时间
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # 更新统计
        self.execution_count += 1
        if return_code == 0:
            self.success_count += 1
        self.total_execution_time += execution_time

        # 创建结果对象
        result = ExecutionResult(
            command=command,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            success=(return_code == 0),
            execution_time=execution_time,
            platform=self.platform.value,
            timestamp=start_time
        )

        # 记录结果
        if result.success:
            logger.info(f"异步命令执行成功，耗时 {execution_time:.2f}秒")
        else:
            logger.warning(f"异步命令执行失败: {stderr}")

        return result

    def execute_with_progress(self, command: str, timeout: int = 30, progress_callback=None) -> ExecutionResult:
        """
        执行命令并支持进度回调

        Args:
            command: 命令字符串
            timeout: 超时时间（秒）
            progress_callback: 进度回调函数 callback(progress: float, message: str)

        Returns:
            ExecutionResult: 执行结果
        """
        if progress_callback:
            progress_callback(0.0, "开始执行命令...")

        result = self.execute(command, timeout)

        if progress_callback:
            if result.success:
                progress_callback(1.0, "命令执行成功")
            else:
                progress_callback(1.0, f"命令执行失败: {result.stderr}")

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取执行统计

        Returns:
            Dict[str, Any]: 统计信息
        """
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        avg_time = (self.total_execution_time / self.execution_count) if self.execution_count > 0 else 0

        return {
            'total_executions': self.execution_count,
            'successful_executions': self.success_count,
            'failed_executions': self.execution_count - self.success_count,
            'success_rate': f"{success_rate:.2f}%",
            'total_time': f"{self.total_execution_time:.2f}s",
            'average_time': f"{avg_time:.2f}s",
            'platform': self.platform.value
        }
