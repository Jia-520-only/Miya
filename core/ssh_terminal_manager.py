"""
SSH远程终端管理 - 弥娅V4.0

支持远程服务器的SSH连接和管理
"""

import asyncio
from typing import Dict, Optional, List
from .terminal_types import TerminalType, TerminalStatus, CommandResult, TerminalSession

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None

class SSHConnection:
    """SSH连接配置"""

    def __init__(self, host: str, port: int = 22, username: str = None, password: str = None, key_path: str = None):
        if not PARAMIKO_AVAILABLE:
            raise ImportError("paramiko 模块未安装。SSH 功能需要安装 paramiko: pip install paramiko")

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.client = None
    
    def connect(self):
        """建立SSH连接"""
        self.client = paramiko.SSHClient()
        
        if self.key_path:
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                key_filename=self.key_path
            )
        else:
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            self.client = None

class SSHTerminalManager:
    """SSH远程终端管理器"""

    def __init__(self):
        if not PARAMIKO_AVAILABLE:
            print("[警告] paramiko 未安装，SSH 功能将不可用。运行: pip install paramiko")

        self.ssh_connections: Dict[str, SSHConnection] = {}
        self.ssh_sessions: Dict[str, TerminalSession] = {}
        self.active_ssh_id: Optional[str] = None
    
    async def create_ssh_session(
        self,
        name: str,
        host: str,
        port: int = 22,
        username: str = None,
        password: str = None,
        key_path: str = None
    ) -> str:
        """创建SSH会话
        
        Args:
            name: 会话名称
            host: 主机地址
            port: SSH端口
            username: 用户名
            password: 密码
            key_path: 密钥路径
            
        Returns:
            会话ID
        """
        
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        # 创建SSH连接
        connection = SSHConnection(host, port, username, password, key_path)
        
        try:
            connection.connect()
        except Exception as e:
            raise Exception(f"SSH连接失败: {e}")
        
        self.ssh_connections[session_id] = connection
        
        # 创建会话
        session = TerminalSession(
            id=session_id,
            name=name,
            terminal_type=TerminalType.BASH,
            status=TerminalStatus.IDLE,
            current_dir=f"ssh://{host}"
        )
        
        self.ssh_sessions[session_id] = session
        
        if not self.active_ssh_id:
            self.active_ssh_id = session_id
        
        return session_id
    
    async def execute_ssh_command(
        self,
        session_id: str,
        command: str
    ) -> CommandResult:
        """在SSH会话中执行命令
        
        Args:
            session_id: 会话ID
            command: 要执行的命令
            
        Returns:
            执行结果
        """
        
        if session_id not in self.ssh_sessions:
            return CommandResult(
                success=False,
                output="",
                error=f"SSH会话不存在: {session_id}"
            )
        
        if session_id not in self.ssh_connections:
            return CommandResult(
                success=False,
                output="",
                error="SSH连接不存在"
            )
        
        connection = self.ssh_connections[session_id]
        session = self.ssh_sessions[session_id]
        
        session.add_command(command)
        session.status = TerminalStatus.EXECUTING
        
        import time
        start_time = time.time()
        
        try:
            # 执行命令
            stdin, stdout, stderr = connection.client.exec_command(command)
            
            # 读取输出
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            execution_time = time.time() - start_time
            
            session.status = TerminalStatus.IDLE
            
            return CommandResult(
                success=(exit_code == 0),
                output=output,
                error=error,
                exit_code=exit_code,
                execution_time=execution_time,
                session_id=session_id
            )
        
        except Exception as e:
            session.status = TerminalStatus.ERROR
            return CommandResult(
                success=False,
                output="",
                error=str(e),
                session_id=session_id
            )
    
    async def execute_parallel_ssh(
        self,
        commands: Dict[str, str]
    ) -> Dict[str, CommandResult]:
        """在多个SSH会话并行执行命令
        
        Args:
            commands: {session_id: command}
            
        Returns:
            {session_id: result}
        """
        
        tasks = []
        for session_id, command in commands.items():
            task = self.execute_ssh_command(session_id, command)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
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
    
    async def close_ssh_session(self, session_id: str):
        """关闭SSH会话
        
        Args:
            session_id: 会话ID
        """
        
        if session_id in self.ssh_sessions:
            del self.ssh_sessions[session_id]
        
        if session_id in self.ssh_connections:
            self.ssh_connections[session_id].close()
            del self.ssh_connections[session_id]
        
        if self.active_ssh_id == session_id:
            self.active_ssh_id = next(iter(self.ssh_sessions.keys()), None)
    
    def get_ssh_status(self, session_id: str) -> Optional[Dict]:
        """获取SSH会话状态"""
        
        if session_id not in self.ssh_sessions:
            return None
        
        session = self.ssh_sessions[session_id]
        connection = self.ssh_connections.get(session_id)
        
        return {
            "id": session.id,
            "name": session.name,
            "host": connection.host if connection else "unknown",
            "port": connection.port if connection else 22,
            "status": session.status.value,
            "is_active": session_id == self.active_ssh_id
        }
    
    def get_all_ssh_status(self) -> Dict[str, Dict]:
        """获取所有SSH会话状态"""
        
        status = {}
        for session_id in self.ssh_sessions:
            status[session_id] = self.get_ssh_status(session_id)
        
        return status
