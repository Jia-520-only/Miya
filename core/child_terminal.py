"""
子终端管理 - 弥娅V4.0多终端协作架构

子终端是纯粹的执行环境，负责：
- 接收并执行命令（从主终端分配）
- 返回执行结果
- 状态监控（运行中/完成/失败）
- 可被弥娅接管（弥娅直接输入命令）
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
from .local_terminal_manager import LocalTerminalManager
from .ssh_terminal_manager import SSHTerminalManager
from .terminal_types import TerminalType, TerminalStatus, CommandResult
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChildTerminalConfig:
    """子终端配置"""
    name: str
    terminal_type: str  # local, ssh
    working_dir: str = "."
    ssh_host: str = None
    ssh_port: int = 22
    ssh_username: str = None
    ssh_password: str = None
    ssh_key_path: str = None


class ChildTerminal:
    """子终端 - 执行环境
    
    子终端专注于具体任务的执行：
    - 接收并执行命令
    - 返回执行结果
    - 状态监控
    - 支持弥娅接管
    """

    def __init__(
        self,
        terminal_id: str,
        config: ChildTerminalConfig,
        local_manager: LocalTerminalManager,
        ssh_manager: SSHTerminalManager = None
    ):
        self.id = terminal_id
        self.config = config
        self.local_manager = local_manager
        self.ssh_manager = ssh_manager
        
        # 状态
        self.status = "idle"  # idle, running, completed, failed
        self.current_task = None
        self.miya_takeover = False  # 弥娅是否接管
        self.task_history: List[Dict] = []
        
        # 执行统计
        self.total_commands = 0
        self.successful_commands = 0
        self.failed_commands = 0
        
        logger.info(f"[子终端 {self.id}] 初始化完成: {config.name} ({config.terminal_type})")

    async def execute(self, commands: List[str]) -> List[CommandResult]:
        """执行命令列表
        
        Args:
            commands: 命令列表
            
        Returns:
            执行结果列表
        """
        self.status = "running"
        self.total_commands += len(commands)
        
        results = []
        
        try:
            if self.config.terminal_type == "local":
                # 本地终端执行
                results = await self._execute_local(commands)
            elif self.config.terminal_type == "ssh":
                # SSH终端执行
                results = await self._execute_ssh(commands)
            else:
                logger.error(f"[子终端 {self.id}] 不支持的终端类型: {self.config.terminal_type}")
                self.status = "failed"
                return []
            
            # 更新统计
            for result in results:
                if result.success:
                    self.successful_commands += 1
                else:
                    self.failed_commands += 1
            
            self.status = "completed"
            
        except Exception as e:
            logger.error(f"[子终端 {self.id}] 执行错误: {e}")
            self.status = "failed"
            self.failed_commands += len(commands)
        
        return results

    async def _execute_local(self, commands: List[str]) -> List[CommandResult]:
        """在本地终端执行命令
        
        Args:
            commands: 命令列表
            
        Returns:
            执行结果列表
        """
        results = []
        
        for command in commands:
            result = await self.local_manager.execute_command(
                self.id, command
            )
            results.append(result)
        
        return results

    async def _execute_ssh(self, commands: List[str]) -> List[CommandResult]:
        """在SSH终端执行命令
        
        Args:
            commands: 命令列表
            
        Returns:
            执行结果列表
        """
        if not self.ssh_manager:
            logger.error(f"[子终端 {self.id}] SSH管理器未初始化")
            return []
        
        results = []
        
        for command in commands:
            result = await self.ssh_manager.execute_ssh_command(
                self.id, command
            )
            results.append(result)
        
        return results

    async def execute_from_miya(self, command: str) -> CommandResult:
        """弥娅接管执行
        
        当弥娅在子终端中直接输入命令时调用
        
        Args:
            command: 要执行的命令
            
        Returns:
            执行结果
        """
        if not self.miya_takeover:
            logger.warning(f"[子终端 {self.id}] 弥娅接管模式未启用")
            return CommandResult(
                success=False,
                output="",
                error="弥娅接管模式未启用"
            )
        
        logger.info(f"[子终端 {self.id}] 弥娅执行命令: {command}")
        
        results = await self.execute([command])
        return results[0] if results else CommandResult(
            success=False,
            output="",
            error="执行失败"
        )

    def is_running(self) -> bool:
        """检查是否在运行"""
        return self.status == "running"

    def is_idle(self) -> bool:
        """检查是否空闲"""
        return self.status == "idle"

    def get_recent_output(self, lines: int = 20) -> str:
        """获取最近输出
        
        Args:
            lines: 行数
            
        Returns:
            输出内容
        """
        if self.config.terminal_type == "local":
            session_status = self.local_manager.get_session_status(self.id)
            if session_status:
                # 简化实现：返回状态信息
                return f"终端 {self.config.name}: {session_status['status']}"
        
        return f"终端 {self.config.name}: {self.status}"

    def get_result(self) -> Dict:
        """获取执行结果汇总"""
        return {
            "terminal_id": self.id,
            "terminal_name": self.config.name,
            "terminal_type": self.config.terminal_type,
            "status": self.status,
            "total_commands": self.total_commands,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "success_rate": (
                self.successful_commands / self.total_commands * 100
                if self.total_commands > 0 else 0
            )
        }

    def enable_miya_takeover(self):
        """启用弥娅接管模式"""
        self.miya_takeover = True
        logger.info(f"[子终端 {self.id}] 弥娅接管模式已启用")

    def disable_miya_takeover(self):
        """禁用弥娅接管模式"""
        self.miya_takeover = False
        logger.info(f"[子终端 {self.id}] 弥娅接管模式已禁用")

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.config.name,
            "type": self.config.terminal_type,
            "status": self.status,
            "working_dir": self.config.working_dir,
            "miya_takeover": self.miya_takeover,
            "total_commands": self.total_commands,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands
        }


class ChildTerminalManager:
    """子终端管理器
    
    管理所有子终端的创建、执行、监控
    """

    def __init__(
        self,
        local_manager: LocalTerminalManager,
        ssh_manager: SSHTerminalManager = None
    ):
        self.local_manager = local_manager
        self.ssh_manager = ssh_manager
        
        # 子终端池
        self.child_terminals: Dict[str, ChildTerminal] = {}
        
        logger.info("[子终端管理器] 初始化完成")

    async def create_child_terminal(
        self,
        config: ChildTerminalConfig
    ) -> str:
        """创建子终端
        
        Args:
            config: 子终端配置
            
        Returns:
            终端ID
        """
        import uuid
        terminal_id = str(uuid.uuid4())[:8]
        
        # 根据类型创建实际终端
        if config.terminal_type == "local":
            # 创建本地终端
            session_id = await self.local_manager.create_terminal(
                name=config.name,
                terminal_type=TerminalType.CMD,
                initial_dir=config.working_dir
            )
        elif config.terminal_type == "ssh":
            # 创建SSH终端
            if not self.ssh_manager:
                raise Exception("SSH管理器未初始化")
            
            session_id = await self.ssh_manager.create_ssh_session(
                name=config.name,
                host=config.ssh_host,
                port=config.ssh_port,
                username=config.ssh_username,
                password=config.ssh_password,
                key_path=config.ssh_key_path
            )
        else:
            raise Exception(f"不支持的终端类型: {config.terminal_type}")
        
        # 创建子终端包装
        child_terminal = ChildTerminal(
            terminal_id=session_id,
            config=config,
            local_manager=self.local_manager,
            ssh_manager=self.ssh_manager
        )
        
        self.child_terminals[session_id] = child_terminal
        
        logger.info(f"[子终端管理器] 创建子终端: {config.name} ({session_id})")
        
        return session_id

    def get_child_terminal(self, terminal_id: str) -> Optional[ChildTerminal]:
        """获取子终端
        
        Args:
            terminal_id: 终端ID
            
        Returns:
            子终端对象或None
        """
        return self.child_terminals.get(terminal_id)

    def get_all_child_terminals(self) -> List[Dict]:
        """获取所有子终端信息"""
        return [
            child.to_dict()
            for child in self.child_terminals.values()
        ]

    async def close_child_terminal(self, terminal_id: str):
        """关闭子终端
        
        Args:
            terminal_id: 终端ID
        """
        if terminal_id not in self.child_terminals:
            return
        
        child = self.child_terminals[terminal_id]
        
        # 关闭底层终端
        if child.config.terminal_type == "local":
            await self.local_manager.close_session(terminal_id)
        elif child.config.terminal_type == "ssh":
            await self.ssh_manager.close_ssh_session(terminal_id)
        
        # 移除子终端
        del self.child_terminals[terminal_id]
        
        logger.info(f"[子终端管理器] 关闭子终端: {terminal_id}")

    async def close_all(self):
        """关闭所有子终端"""
        terminal_ids = list(self.child_terminals.keys())
        
        for terminal_id in terminal_ids:
            await self.close_child_terminal(terminal_id)
        
        logger.info("[子终端管理器] 所有子终端已关闭")
