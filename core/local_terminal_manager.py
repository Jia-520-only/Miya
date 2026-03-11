"""
单机多终端管理器 - 弥娅V4.0核心模块

支持在同一操作系统上同时创建和管理多个终端窗口
"""

import asyncio
import subprocess
import threading
import queue
import time
import uuid
import os
import platform
from typing import Dict, List, Optional, Callable
from .terminal_types import (
    TerminalType, TerminalStatus, CommandResult,
    OutputData, TerminalSession
)
import logging

logger = logging.getLogger(__name__)


class LocalTerminalManager:
    """单机多终端管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}
        self.active_session_id: Optional[str] = None
        
        # 输出监听器
        self.output_listeners: Dict[str, List[Callable]] = {}
        
        # 全局命令历史
        self.global_history: List[Dict] = []
    
    async def create_terminal(
        self,
        name: str,
        terminal_type: TerminalType = TerminalType.CMD,
        initial_dir: str = None
    ) -> str:
        """创建新终端
        
        Args:
            name: 终端名称
            terminal_type: 终端类型
            initial_dir: 初始工作目录
            
        Returns:
            会话ID
        """
        
        session_id = self._generate_session_id()
        
        # 确定初始目录
        work_dir = initial_dir or os.getcwd()
        
        # 创建进程
        process = self._create_process(terminal_type, work_dir)
        
        # 创建会话
        session = TerminalSession(
            id=session_id,
            name=name,
            terminal_type=terminal_type,
            process=process,
            current_dir=work_dir
        )
        
        self.sessions[session_id] = session
        
        # 如果是第一个终端，设为活动
        if not self.active_session_id:
            self.active_session_id = session_id
        
        # 注册输出监听器
        self.output_listeners[session_id] = []
        
        logger.info(f"创建终端: {name} ({terminal_type.value}) - {session_id}")
        
        return session_id
    
    async def execute_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: int = 30
    ) -> CommandResult:
        """在指定终端执行命令
        
        Args:
            session_id: 会话ID
            command: 要执行的命令
            wait_for_completion: 是否等待完成
            timeout: 超时时间
            
        Returns:
            执行结果
        """
        
        if session_id not in self.sessions:
            return CommandResult(
                success=False,
                output="",
                error=f"终端会话不存在: {session_id}",
                session_id=session_id
            )
        
        session = self.sessions[session_id]
        
        # 记录命令
        session.add_command(command)
        
        # 更新状态
        session.status = TerminalStatus.EXECUTING
        start_time = time.time()
        
        try:
            # 发送命令
            if session.process and session.process.stdin:
                session.process.stdin.write(command + "\n")
                session.process.stdin.flush()
            
            if wait_for_completion:
                # 简单等待
                await asyncio.sleep(0.5)
                
                # 模拟执行（实际应该监听输出）
                output = f"[执行命令] {command}"
                
                # 记录输出
                output_data = OutputData(
                    type="output",
                    content=output,
                    timestamp=time.time()
                )
                session.add_output(output_data)
                
                # 更新全局历史
                self.global_history.append({
                    "session_id": session_id,
                    "session_name": session.name,
                    "timestamp": time.time(),
                    "command": command
                })
                
                execution_time = time.time() - start_time
                session.status = TerminalStatus.IDLE
                
                return CommandResult(
                    success=True,
                    output=output,
                    execution_time=execution_time,
                    session_id=session_id
                )
            else:
                session.status = TerminalStatus.IDLE
                return CommandResult(
                    success=True,
                    output="",
                    session_id=session_id
                )
        
        except Exception as e:
            session.status = TerminalStatus.ERROR
            logger.error(f"执行命令错误: {e}")
            return CommandResult(
                success=False,
                output="",
                error=str(e),
                session_id=session_id
            )
    
    async def execute_parallel(
        self,
        commands: Dict[str, str],
        timeout: int = 60
    ) -> Dict[str, CommandResult]:
        """在多个终端并行执行命令
        
        Args:
            commands: {session_id: command} 映射
            timeout: 超时时间
            
        Returns:
            {session_id: result} 映射
        """
        
        # 创建任务
        tasks = []
        for session_id, command in commands.items():
            task = self.execute_command(
                session_id, command, timeout=timeout
            )
            tasks.append(task)
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        final_results = {}
        session_ids = list(commands.keys())
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results[session_ids[i]] = CommandResult(
                    success=False,
                    output="",
                    error=str(result),
                    session_id=session_ids[i]
                )
            else:
                final_results[session_ids[i]] = result
        
        return final_results
    
    async def execute_sequence(
        self,
        session_id: str,
        commands: List[str],
        stop_on_error: bool = True
    ) -> List[CommandResult]:
        """在指定终端顺序执行命令
        
        Args:
            session_id: 会话ID
            commands: 命令列表
            stop_on_error: 遇错是否停止
            
        Returns:
            结果列表
        """
        
        results = []
        
        for command in commands:
            result = await self.execute_command(
                session_id, command
            )
            results.append(result)
            
            if not result.success and stop_on_error:
                break
        
        return results
    
    async def switch_session(self, session_id: str):
        """切换活动终端
        
        Args:
            session_id: 会话ID
        """
        
        if session_id not in self.sessions:
            raise ValueError(f"终端不存在: {session_id}")
        
        self.active_session_id = session_id
        
        # 显示切换信息
        session = self.sessions[session_id]
        print(f"\n{'='*60}")
        print(f"[切换到终端] {session.name} ({session.terminal_type.value})")
        print(f"[会话ID] {session_id}")
        print(f"[当前目录] {session.current_dir}")
        print(f"[状态] {session.status.value}")
        print(f"[命令历史] {len(session.command_history)}条")
        print(f"{'='*60}\n")
    
    async def close_session(self, session_id: str):
        """关闭终端会话
        
        Args:
            session_id: 会话ID
        """
        
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        session.status = TerminalStatus.CLOSED
        
        # 关闭进程
        if session.process:
            try:
                session.process.terminate()
                try:
                    session.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    session.process.kill()
            except Exception as e:
                logger.error(f"关闭进程错误: {e}")
        
        # 移除会话
        del self.sessions[session_id]
        if session_id in self.output_listeners:
            del self.output_listeners[session_id]
        
        # 如果关闭的是活动终端，切换到另一个
        if self.active_session_id == session_id:
            self.active_session_id = next(iter(self.sessions.keys()), None)
        
        logger.info(f"关闭终端: {session.name} ({session_id})")
    
    async def close_all_sessions(self):
        """关闭所有终端"""
        
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
    
    def get_session_status(
        self,
        session_id: str
    ) -> Optional[Dict]:
        """获取终端状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            状态字典或None
        """
        
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        return {
            "id": session.id,
            "name": session.name,
            "type": session.terminal_type.value,
            "status": session.status.value,
            "directory": session.current_dir,
            "command_count": len(session.command_history),
            "output_count": len(session.output_history),
            "is_active": session_id == self.active_session_id
        }
    
    def get_all_status(self) -> Dict[str, Dict]:
        """获取所有终端状态
        
        Returns:
            {session_id: status} 映射
        """
        
        status = {}
        for session_id in self.sessions:
            status[session_id] = self.get_session_status(session_id)
        
        return status
    
    def register_output_listener(
        self,
        session_id: str,
        callback: Callable
    ):
        """注册输出监听器
        
        Args:
            session_id: 会话ID
            callback: 回调函数
        """
        
        if session_id not in self.output_listeners:
            self.output_listeners[session_id] = []
        
        self.output_listeners[session_id].append(callback)
    
    def _create_process(
        self,
        terminal_type: TerminalType,
        work_dir: str
    ) -> Optional[subprocess.Popen]:
        """创建终端进程
        
        Args:
            terminal_type: 终端类型
            work_dir: 工作目录
            
        Returns:
            进程对象
        """
        
        try:
            if terminal_type == TerminalType.CMD:
                # Windows CMD
                return subprocess.Popen(
                    ["cmd"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    bufsize=1
                )
            
            elif terminal_type == TerminalType.POWERSHELL:
                # PowerShell
                return subprocess.Popen(
                    ["powershell", "-NoExit"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    bufsize=1
                )
            
            elif terminal_type == TerminalType.WSL:
                # WSL Bash
                return subprocess.Popen(
                    ["wsl", "bash"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    bufsize=1
                )
            
            elif terminal_type == TerminalType.BASH:
                # Linux/Mac Bash
                return subprocess.Popen(
                    ["bash"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    bufsize=1
                )
            
            elif terminal_type == TerminalType.ZSH:
                # Zsh
                return subprocess.Popen(
                    ["zsh"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    bufsize=1
                )
            
            else:
                logger.warning(f"不支持的终端类型: {terminal_type}")
                return None
        
        except Exception as e:
            logger.error(f"创建进程失败: {e}")
            return None
    
    def _generate_session_id(self) -> str:
        """生成会话ID
        
        Returns:
            8字符UUID
        """
        return str(uuid.uuid4())[:8]
