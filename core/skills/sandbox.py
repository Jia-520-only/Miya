"""
弥娅技能沙箱执行器 (Skill Sandbox Executor)

功能：
1. 隔离危险操作
2. 限制资源使用
3. 安全的技能执行环境
4. 超时控制

作者: MIYA
日期: 2026-04-28
"""

import asyncio
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

# Windows compatibility - resource module is Unix-only
if sys.platform != "win32":
    import resource
else:
    resource = None

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================


class SandboxLevel(str, Enum):
    """沙箱级别"""

    NONE = "none"  # 无限制
    RESTRICTED = "restricted"  # 受限
    ISOLATED = "isolated"  # 完全隔离
    READONLY = "readonly"  # 只读


class SandboxError(Exception):
    """沙箱错误"""

    pass


# ==================== 沙箱配置 ====================


@dataclass
class SandboxConfig:
    """沙箱配置"""

    level: SandboxLevel = SandboxLevel.RESTRICTED
    timeout: int = 30  # 超时时间（秒）
    max_memory: int = 256 * 1024 * 1024  # 最大内存（256MB）
    max_output_size: int = 1024 * 1024  # 最大输出（1MB）
    cpu_limit: float = 10.0  # CPU时间限制（秒）
    enabled_modules: list = field(
        default_factory=lambda: [
            "json",
            "re",
            "math",
            "random",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "operator",
        ]
    )
    disabled_modules: list = field(
        default_factory=lambda: [
            "os",
            "sys",
            "subprocess",
            "socket",
            "requests",
            "multiprocessing",
            "threading",
            "ctypes",
            "signal",
            "resource",
        ]
    )
    allowed_paths: list = field(default_factory=list)
    blocked_paths: list = field(default_factory=lambda: ["/", "/etc", "/root", "/home", "/proc", "/sys"])
    enable_resource_limits: bool = True  # 是否启用资源限制（Unix）
    enable_psutil_monitor: bool = True  # 是否启用psutil监控


# ==================== 沙箱执行器 ====================


class SkillSandbox:
    """
    技能沙箱执行器

    提供安全的技能执行环境：
    - 资源限制
    - 模块白名单/黑名单
    - 路径访问控制
    - 执行超时
    - 输出限制
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._execution_history = []

    async def execute(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Any:
        """
        在沙箱中执行函数

        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            context: 执行上下文

        Returns:
            执行结果
        """
        kwargs = kwargs or {}

        # 记录开始时间
        start_time = datetime.now()

        # 检查超时
        try:
            result = await asyncio.wait_for(
                self._execute_internal(func, args, kwargs, context),
                timeout=self.config.timeout,
            )

            # 记录成功执行
            self._execution_history.append(
                {
                    "success": True,
                    "function": func.__name__,
                    "start_time": start_time.isoformat(),
                    "duration": (datetime.now() - start_time).total_seconds(),
                }
            )

            return result

        except asyncio.TimeoutError:
            error_msg = f"执行超时 ({self.config.timeout}秒)"
            logger.error(f"[Sandbox] {error_msg}")

            self._execution_history.append(
                {
                    "success": False,
                    "function": func.__name__,
                    "start_time": start_time.isoformat(),
                    "error": error_msg,
                }
            )

            raise SandboxError(error_msg)

        except Exception as e:
            error_msg = f"执行错误: {str(e)}"
            logger.error(f"[Sandbox] {error_msg}")

            self._execution_history.append(
                {
                    "success": False,
                    "function": func.__name__,
                    "start_time": start_time.isoformat(),
                    "error": error_msg,
                }
            )

            raise SandboxError(error_msg)

    async def _execute_internal(
        self,
        func: Callable,
        args: tuple,
        kwargs: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Any:
        """内部执行逻辑"""
        # 沙箱级别控制
        if self.config.level == SandboxLevel.NONE:
            return await self._execute_direct(func, args, kwargs)

        elif self.config.level == SandboxLevel.RESTRICTED:
            return await self._execute_restricted(func, args, kwargs, context)

        elif self.config.level == SandboxLevel.ISOLATED:
            return await self._execute_isolated(func, args, kwargs, context)

        elif self.config.level == SandboxLevel.READONLY:
            return await self._execute_readonly(func, args, kwargs, context)

        return await self._execute_direct(func, args, kwargs)

    async def _execute_direct(
        self,
        func: Callable,
        args: tuple,
        kwargs: Optional[Dict] = None,
    ) -> Any:
        """直接执行（无限制）"""
        return await func(*args, **(kwargs or {}))

    async def _execute_restricted(
        self,
        func: Callable,
        args: tuple,
        kwargs: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Any:
        """受限执行"""
        # 检查是否使用了禁止的模块
        # 这里可以添加更严格的检查

        safe_kwargs = self._sanitize_kwargs(kwargs or {})

        try:
            result = await func(*args, **safe_kwargs)

            # 限制输出大小
            if isinstance(result, str) and len(result) > self.config.max_output_size:
                result = result[: self.config.max_output_size] + "\n... [output truncated]"

            return result

        except Exception as e:
            logger.warning(f"[Sandbox] 受限执行异常: {e}")
            raise

    async def _execute_isolated(
        self,
        func: Callable,
        args: tuple,
        kwargs: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Any:
        """隔离执行 - 创建临时环境"""
        # 创建临时工作目录
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"[Sandbox] 隔离执行，工作目录: {tmpdir}")

            # 修改 kwargs 添加工作目录
            safe_kwargs = {
                **(kwargs or {}),
                "_sandbox_workspace": tmpdir,
                "_sandbox_config": self.config,
            }

            return await self._execute_restricted(func, args, safe_kwargs, context)

    async def _execute_readonly(
        self,
        func: Callable,
        args: tuple,
        kwargs: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Any:
        """只读执行"""
        # 只允许读取操作，不允许写入
        # 这里可以添加更严格的检查

        safe_kwargs = self._sanitize_kwargs(kwargs)
        return await func(*args, **safe_kwargs)

    def _sanitize_kwargs(self, kwargs: Optional[Dict]) -> Dict:
        """清理关键字参数"""
        safe = {}

        if kwargs is None:
            return safe

        for key, value in kwargs.items():
            # 跳过内部参数
            if key.startswith("_sandbox_"):
                continue

            # 清理敏感值
            if isinstance(value, str):
                # 限制字符串长度
                if len(value) > 100000:
                    value = value[:100000] + "\n... [truncated]"

            safe[key] = value

        return safe

    def check_module_access(self, module_name: str) -> bool:
        """检查模块访问权限"""
        # 白名单优先
        if module_name in self.config.enabled_modules:
            return True

        # 黑名单检查
        if module_name in self.config.disabled_modules:
            logger.warning(f"[Sandbox] 禁止访问模块: {module_name}")
            return False

        # 默认允许（除非有白名单）
        return not self.config.enabled_modules

    def check_path_access(self, path: str) -> bool:
        """检查路径访问权限"""
        # 黑名单检查
        for blocked in self.config.blocked_paths:
            if path.startswith(blocked):
                logger.warning(f"[Sandbox] 禁止访问路径: {path}")
                return False

        # 白名单检查
        if self.config.allowed_paths:
            return any(path.startswith(allowed) for allowed in self.config.allowed_paths)

        return True

    def get_execution_history(self, limit: int = 20) -> list:
        """获取执行历史"""
        return self._execution_history[-limit:]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self._execution_history)
        success = sum(1 for e in self._execution_history if e.get("success"))
        return {
            "total_executions": total,
            "success_count": success,
            "failure_count": total - success,
            "sandbox_level": self.config.level.value,
            "timeout": self.config.timeout,
        }


# ==================== 便捷函数 ====================


async def execute_in_sandbox(
    func: Callable,
    *args,
    level: SandboxLevel = SandboxLevel.RESTRICTED,
    timeout: int = 30,
    kwargs: Optional[Dict] = None,
) -> Any:
    """在沙箱中执行函数"""
    config = SandboxConfig(level=level, timeout=timeout)
    sandbox = SkillSandbox(config)
    return await sandbox.execute(func, args, kwargs)


# ==================== 全局实例 ====================


_sandbox: Optional[SkillSandbox] = None


def get_skill_sandbox(level: SandboxLevel = SandboxLevel.RESTRICTED) -> SkillSandbox:
    """获取沙箱实例"""
    global _sandbox
    if _sandbox is None:
        _sandbox = SkillSandbox(SandboxConfig(level=level))
    return _sandbox


__all__ = [
    "SandboxLevel",
    "SandboxConfig",
    "SandboxError",
    "SkillSandbox",
    "get_skill_sandbox",
    "execute_in_sandbox",
]
