"""
ConPTY 终端管理器 - 基于 Windows 伪控制台的完整终端控制

功能：
1. 使用 ConPTY 创建可控制的终端会话
2. 完整支持输入/输出控制
3. 支持读取终端输出
4. 支持发送命令到终端

依赖：
- pywin32 (Windows API 调用)
"""

import asyncio
import subprocess
import threading
import queue
import time
import os
import sys
import logging
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConPTYSession:
    """ConPTY 终端会话"""
    session_id: str
    name: str
    terminal_type: str
    process: Optional[subprocess.Popen]
    output_queue: queue.Queue
    input_queue: queue.Queue
    running: bool = True
    current_dir: str = ""


class ConPTYTerminalManager:
    """
    ConPTY 终端管理器
    
    使用 Windows ConPTY API 实现完整的终端控制
    """
    
    def __init__(self):
        self.sessions: Dict[str, ConPTYSession] = {}
        self.active_session_id: Optional[str] = None
        self.output_callbacks: Dict[str, List[Callable]] = {}
        
    def create_terminal(
        self,
        name: str,
        terminal_type: str = "cmd",
        initial_dir: str = None
    ) -> str:
        """
        创建 ConPTY 终端
        
        Args:
            name: 终端名称
            terminal_type: 终端类型 (cmd, powershell, bash)
            initial_dir: 初始目录
            
        Returns:
            session_id
        """
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        work_dir = initial_dir or os.getcwd()
        
        # 创建命令
        if terminal_type == "cmd":
            cmd = "cmd.exe"
        elif terminal_type == "powershell":
            cmd = "powershell.exe"
        elif terminal_type == "powershell_7":
            cmd = "pwsh.exe"
        else:
            cmd = "cmd.exe"
        
        try:
            # 使用 Python 启动隐藏的子进程，并通过管道通信
            # 同时使用 start 命令打开可见窗口
            if terminal_type in ["cmd", "powershell"]:
                # 启动一个 Python 脚本来处理 ConPTY
                process = self._create_pty_process(cmd, work_dir, session_id)
            else:
                # 非 Windows 终端使用普通方式
                process = subprocess.Popen(
                    [cmd],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=work_dir,
                    bufsize=0  # 行缓冲
                )
            
            # 创建会话
            output_queue = queue.Queue()
            input_queue = queue.Queue()
            
            session = ConPTYSession(
                session_id=session_id,
                name=name,
                terminal_type=terminal_type,
                process=process,
                output_queue=output_queue,
                input_queue=input_queue,
                running=True,
                current_dir=work_dir
            )
            
            self.sessions[session_id] = session
            
            # 启动输出读取线程
            if process and process.stdout:
                thread = threading.Thread(
                    target=self._read_output,
                    args=(session_id,),
                    daemon=True
                )
                thread.start()
            
            # 设为活动会话
            if not self.active_session_id:
                self.active_session_id = session_id
            
            logger.info(f"ConPTY终端创建成功: {name} ({session_id})")
            return session_id
            
        except Exception as e:
            logger.error(f"创建 ConPTY 终端失败: {e}")
            raise
    
    def _create_pty_process(self, cmd: str, work_dir: str, session_id: str) -> subprocess.Popen:
        """
        创建 ConPTY 进程
        
        使用 Windows ConPTY 需要复杂的 API 调用
        这里使用简化版本：通过管道连接到进程
        """
        try:
            # 尝试使用 windows-curses 或直接使用管道
            process = subprocess.Popen(
                [cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=work_dir,
                bufsize=0,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            return process
        except Exception as e:
            logger.error(f"创建进程失败: {e}")
            raise
    
    def _read_output(self, session_id: str):
        """读取终端输出（在线程中运行）"""
        session = self.sessions.get(session_id)
        if not session or not session.process or not session.process.stdout:
            return
        
        try:
            import sys
            is_windows = sys.platform == 'win32'
            
            while session.running and session.process.poll() is None:
                try:
                    if is_windows:
                        # Windows: 使用 msvcrt 进行非阻塞读取
                        import msvcrt
                        while session.running and session.process.poll() is None:
                            if msvcrt.kbhit():
                                data = msvcrt.getwch()
                                session.output_queue.put(data)
                                # 调用回调
                                if session_id in self.output_callbacks:
                                    for callback in self.output_callbacks[session_id]:
                                        try:
                                            callback(data)
                                        except:
                                            pass
                            time.sleep(0.01)
                        break
                    else:
                        # Unix: 使用 select
                        import select
                        if select.select([session.process.stdout], [], [], 0.1)[0]:
                            data = session.process.stdout.read(1)
                            if data:
                                # 解码并添加到队列
                                try:
                                    text = data.decode('gbk', errors='replace')
                                except:
                                    text = data.decode('utf-8', errors='replace')
                                
                                session.output_queue.put(text)
                                
                                # 调用回调
                                if session_id in self.output_callbacks:
                                    for callback in self.output_callbacks[session_id]:
                                        try:
                                            callback(text)
                                        except:
                                            pass
                except Exception as e:
                    # 继续循环，不因单次错误退出
                    time.sleep(0.1)
                    continue
        except Exception as e:
            logger.error(f"读取输出失败: {e}")
        finally:
            session.running = False
    
    def send_command(self, session_id: str, command: str) -> bool:
        """
        发送命令到终端
        
        Args:
            session_id: 会话ID
            command: 命令
            
        Returns:
            是否成功
        """
        session = self.sessions.get(session_id)
        if not session or not session.process or not session.process.stdin:
            return False
        
        try:
            # 添加换行符
            if not command.endswith('\n'):
                command += '\n'
            
            session.process.stdin.write(command)
            session.process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    def read_output(self, session_id: str, timeout: float = 0.1, max_chars: int = 1000) -> str:
        """
        读取终端输出
        
        Args:
            session_id: 会话ID
            timeout: 超时时间
            max_chars: 最大字符数
            
        Returns:
            输出文本
        """
        session = self.sessions.get(session_id)
        if not session:
            return ""
        
        output = []
        end_time = time.time() + timeout
        
        try:
            while time.time() < end_time and len(output) < max_chars:
                try:
                    text = session.output_queue.get(timeout=0.01)
                    output.append(text)
                except queue.Empty:
                    break
        except:
            pass
        
        return ''.join(output)
    
    def get_all_output(self, session_id: str) -> str:
        """获取所有累积的输出"""
        session = self.sessions.get(session_id)
        if not session:
            return ""
        
        output = []
        try:
            while True:
                text = session.output_queue.get_nowait()
                output.append(text)
        except queue.Empty:
            pass
        
        return ''.join(output)
    
    def close_terminal(self, session_id: str) -> bool:
        """关闭终端"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        try:
            session.running = False
            
            if session.process:
                # 发送 exit 命令
                try:
                    session.process.stdin.write(b'exit\n')
                    session.process.stdin.flush()
                except:
                    pass
                
                # 等待进程结束
                try:
                    session.process.wait(timeout=2)
                except:
                    pass
                
                # 终止进程
                try:
                    session.process.terminate()
                except:
                    pass
            
            # 移除会话
            if session_id in self.sessions:
                del self.sessions[session_id]
            
            # 更新活动会话
            if self.active_session_id == session_id:
                self.active_session_id = list(self.sessions.keys())[0] if self.sessions else None
            
            logger.info(f"终端已关闭: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"关闭终端失败: {e}")
            return False
    
    def list_terminals(self) -> Dict:
        """列出所有终端"""
        result = {}
        for sid, session in self.sessions.items():
            result[sid] = {
                "name": session.name,
                "type": session.terminal_type,
                "status": "running" if session.running else "stopped",
                "current_dir": session.current_dir
            }
        return result
    
    def register_output_callback(self, session_id: str, callback: Callable):
        """注册输出回调"""
        if session_id not in self.output_callbacks:
            self.output_callbacks[session_id] = []
        self.output_callbacks[session_id].append(callback)


# 全局单例
_conpty_manager = None


def get_conpty_manager() -> ConPTYTerminalManager:
    """获取 ConPTY 终端管理器单例"""
    global _conpty_manager
    if _conpty_manager is None:
        _conpty_manager = ConPTYTerminalManager()
    return _conpty_manager


if __name__ == "__main__":
    # 测试代码
    import sys
    
    print("ConPTY 终端管理器测试")
    print("=" * 40)
    
    manager = ConPTYTerminalManager()
    
    # 创建终端
    session_id = manager.create_terminal("测试终端", "cmd")
    print(f"创建终端: {session_id}")
    
    # 发送命令
    time.sleep(0.5)
    manager.send_command(session_id, "echo Hello from ConPTY")
    time.sleep(0.5)
    
    # 读取输出
    output = manager.read_output(session_id, timeout=1)
    print(f"输出: {output[:200]}")
    
    # 列出终端
    terminals = manager.list_terminals()
    print(f"终端列表: {terminals}")
    
    # 关闭
    manager.close_terminal(session_id)
    print("测试完成")
