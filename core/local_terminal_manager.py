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
    
    def __init__(self, use_conpty: bool = True):
        self.sessions: Dict[str, TerminalSession] = {}
        self.active_session_id: Optional[str] = None
        
        # 输出监听器
        self.output_listeners: Dict[str, List[Callable]] = {}
        
        # 全局命令历史
        self.global_history: List[Dict] = []
        
        # PTY 管理器（用于完整的终端控制）
        self._pty_manager = None
        self._use_pty = False
        
        # 根据平台选择合适的 PTY 管理器
        if platform.system() == "Windows":
            # Windows: 使用 ConPTY
            if use_conpty:
                try:
                    from .conpty_terminal_manager import get_conpty_manager
                    self._pty_manager = get_conpty_manager()
                    self._use_pty = True
                    logger.info("Windows ConPTY 终端控制已启用")
                except Exception as e:
                    logger.warning(f"ConPTY 初始化失败，使用兼容模式: {e}")
        else:
            # Linux/macOS: 使用 PTY
            if use_conpty:
                try:
                    from .linux_pty_terminal_manager import get_pty_manager
                    self._pty_manager = get_pty_manager()
                    self._use_pty = True
                    logger.info("Linux PTY 终端控制已启用")
                except Exception as e:
                    logger.warning(f"PTY 初始化失败，使用兼容模式: {e}")
    
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
        
        # 确定终端类型字符串
        terminal_type_str = terminal_type.value if hasattr(terminal_type, 'value') else str(terminal_type)
        
        # ===== 关键修改：必须打开可见的终端窗口 =====
        # 使用 start 命令打开真正的可见窗口，同时启动终端代理
        try:
            self._open_visible_window(terminal_type, work_dir, session_id)
        except Exception as e:
            logger.error(f"打开可见窗口失败: {e}", exc_info=True)
        
        # 同时也可以使用 PTY 来控制（可选，用于读取输出）
        pty_session_id = None
        process = None
        
        if self._use_pty and self._pty_manager:
            try:
                pty_session_id = self._pty_manager.create_terminal(
                    name=name,
                    terminal_type=terminal_type_str,
                    initial_dir=work_dir
                )
                logger.info(f"使用 PTY 创建终端: {pty_session_id}")
            except Exception as e:
                logger.warning(f"PTY 创建失败，回退到普通方式: {e}")
        
        # 如果 PTY 失败，使用普通方式
        if not pty_session_id:
            process = self._create_process(terminal_type, work_dir)
        
        # 创建会话
        session = TerminalSession(
            id=session_id,
            name=name,
            terminal_type=terminal_type,
            process=process,
            current_dir=work_dir
        )
        
        # 保存 PTY 会话 ID
        if pty_session_id:
            session.pty_session_id = pty_session_id
        
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
            output = ""
            
            # 如果有 PTY 会话 ID，优先使用 PTY
            pty_id = getattr(session, 'pty_session_id', None)
            if pty_id and self._pty_manager:
                # 使用 PTY 发送命令
                self._pty_manager.send_command(pty_id, command)
                
                # 等待输出
                if wait_for_completion:
                    time.sleep(0.5)  # 等待命令执行
                    output = self._pty_manager.read_output(pty_id, timeout=timeout)
            elif session.process and session.process.stdin:
                # 使用普通管道发送命令
                session.process.stdin.write(command + "\n")
                session.process.stdin.flush()
                
                if wait_for_completion:
                    # 简单等待
                    await asyncio.sleep(0.5)
                    output = f"[执行命令] {command}"
            
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
            import platform
            if platform.system() != "Windows":
                # 非Windows系统使用普通方式
                if terminal_type == TerminalType.CMD:
                    return subprocess.Popen(
                        ["bash"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=work_dir,
                        text=True,
                        bufsize=1
                    )
            
            # Windows: 使用 start 命令打开新窗口
            if terminal_type == TerminalType.CMD:
                # Windows CMD - 使用 start cmd 打开新窗口
                # /k 表示执行命令后保持窗口打开
                subprocess.Popen(
                    f'start cmd /k "cd /d {work_dir}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                # 返回一个虚拟的进程对象
                return None
            
            elif terminal_type == TerminalType.POWERSHELL:
                # PowerShell - 使用 start powershell 打开新窗口
                subprocess.Popen(
                    f'start powershell -NoExit -Command "cd \'{work_dir}\'"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return None
            
            elif terminal_type == TerminalType.WSL:
                # WSL - 使用 wt.exe 打开 Windows Terminal 或直接用 wsl
                try:
                    subprocess.Popen(
                        f'start wsl -d Ubuntu',
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except:
                    # 回退到普通方式
                    return subprocess.Popen(
                        ["wsl", "bash"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=work_dir,
                        text=True,
                        bufsize=1
                    )
                return None
            
            elif terminal_type == TerminalType.BASH:
                # Linux/Mac Bash - 在 Windows 上使用 Git Bash
                try:
                    subprocess.Popen(
                        f'start "C:\\Program Files\\Git\\git-bash.exe" --cd="{work_dir}"',
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return None
                except:
                    # 回退到普通方式
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
    
    def _open_visible_window(self, terminal_type: TerminalType, work_dir: str, session_id: str = None):
        """打开可见的终端窗口（独立新窗口）
        
        这是让用户真正看到新终端窗口的关键方法！
        使用 Windows start 命令打开独立窗口。
        同时在新窗口中启动弥娅终端代理，实现与弥娅的交互。
        
        Args:
            terminal_type: 终端类型
            work_dir: 工作目录
            session_id: 会话ID（用于终端代理）
        """
        import platform
        import sys
        from pathlib import Path
        
        # 获取项目根目录
        project_root = Path(__file__).parent.parent
        agent_script = str(project_root / "core" / "terminal_agent.py")
        venv_python = str(project_root / "venv" / "Scripts" / "python.exe")
        
        # 检查 venv Python 是否存在
        if not Path(venv_python).exists():
            venv_python = sys.executable  # 回退到系统 Python
        
        # 如果没有 session_id，生成一个
        if not session_id:
            session_id = self._generate_session_id()
        
        if platform.system() != "Windows":
            # Linux/macOS: 使用 xdg-open 或 open
            if platform.system() == "Linux":
                # 使用 Python 脚本启动终端代理
                subprocess.Popen(
                    ["x-terminal-emulator", "-e", f"cd {work_dir} && {venv_python} {agent_script} --session-id {session_id}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif platform.system() == "Darwin":
                subprocess.Popen(
                    ["open", "-a", "Terminal", "-n", "--args", f"-c 'cd {work_dir} && {venv_python} {agent_script} --session-id {session_id}'"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            logger.info(f"已打开终端窗口并启动弥娅代理: {session_id}")
            return
        
        # Windows: 使用 start 命令打开真正可见的独立窗口
        # 同时启动 terminal_agent.py 连接回弥娅主系统
        try:
            if terminal_type == TerminalType.CMD:
                # 打开 CMD 窗口并运行终端代理
                cmd = f'cd /d "{work_dir}" && "{venv_python}" "{agent_script}" --session-id {session_id}'
                subprocess.Popen(
                    f'start cmd /k "{cmd}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"已打开 CMD 窗口并启动弥娅代理: {session_id}")
                
            elif terminal_type == TerminalType.POWERSHELL:
                # 打开 PowerShell 窗口并运行终端代理
                cmd = f'cd "{work_dir}"; "{venv_python}" "{agent_script}" --session-id {session_id}'
                subprocess.Popen(
                    f'start powershell -NoExit -Command "{cmd}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"已打开 PowerShell 窗口并启动弥娅代理: {session_id}")
                
            elif terminal_type == TerminalType.WSL:
                # 打开 WSL 窗口并启动终端代理
                # 使用 start wsl 命令打开可见的WSL窗口
                # Windows路径需要转换为WSL路径格式 (/mnt/c/...)
                wsl_work_dir = work_dir.replace("\\", "/")
                if len(wsl_work_dir) >= 2 and wsl_work_dir[1] == ":":
                    # 转换 D:/path 或 d:/path 为 /mnt/d/path 格式
                    drive_letter = wsl_work_dir[0].lower()
                    wsl_work_dir = f"/mnt/{drive_letter}{wsl_work_dir[2:]}"
                
                # 方案1: 使用 Windows Terminal 的 wt.exe 打开新的WSL标签页
                try:
                    wsl_cmd = f'wt.exe -w 0 new-tab --profile "Ubuntu" -- wsl.exe -- bash -c "cd {wsl_work_dir} && echo 正在启动弥娅终端代理... && python3 {agent_script} --session-id {session_id} && exec bash"'
                    subprocess.Popen(
                        wsl_cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logger.info(f"已使用 Windows Terminal 打开 WSL 窗口并启动弥娅代理: {session_id}")
                except FileNotFoundError:
                    # 方案2: 如果没有 Windows Terminal，使用 start wsl
                    logger.warning("Windows Terminal 未找到，使用 start wsl 命令")
                    wsl_cmd = f'start wsl bash -c "cd {wsl_work_dir} && echo 正在启动弥娅终端代理... && python3 {agent_script} --session-id {session_id} && exec bash"'
                    subprocess.Popen(
                        wsl_cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logger.info(f"已使用 start wsl 打开 WSL 窗口并启动弥娅代理: {session_id}")
                
            elif terminal_type == TerminalType.BASH:
                # 打开 Git Bash 窗口并运行终端代理
                git_bash_path = r"C:\Program Files\Git\git-bash.exe"
                cmd = f'cd "{work_dir}" && {venv_python} {agent_script} --session-id {session_id}'
                subprocess.Popen(
                    f'start "" "{git_bash_path}" -c "{cmd}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"已打开 Git Bash 窗口并启动弥娅代理: {session_id}")
                
            else:
                # 默认打开 PowerShell
                cmd = f'cd "{work_dir}"; "{venv_python}" "{agent_script}" --session-id {session_id}'
                subprocess.Popen(
                    f'start powershell -NoExit -Command "{cmd}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"已打开终端窗口并启动弥娅代理: {session_id}")
                
        except Exception as e:
            logger.error(f"打开可见窗口失败: {e}")
    
    def _generate_session_id(self) -> str:
        """生成会话ID
        
        Returns:
            8字符UUID
        """
        return str(uuid.uuid4())[:8]
