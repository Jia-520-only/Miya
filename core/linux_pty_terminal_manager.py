"""
Linux PTY 终端管理器 - 基于伪终端的完整终端控制

功能：
1. 使用 Linux pty 创建可控制的终端会话
2. 完整支持输入/输出控制
3. 支持读取终端输出
4. 支持发送命令到终端
5. 支持多终端并行管理

依赖：
- 标准库：pty, select, os, subprocess
"""

import asyncio
import subprocess
import threading
import queue
import time
import os
import sys
import logging
import pty
import select
import tty
import fcntl
import termios
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class PTYSession:
    """PTY 终端会话"""
    session_id: str
    name: str
    terminal_type: str
    master_fd: int  # PTY 主设备文件描述符
    process: Optional[subprocess.Popen]
    output_queue: queue.Queue
    running: bool = True
    current_dir: str = ""


class LinuxPTYTerminalManager:
    """
    Linux PTY 终端管理器
    
    使用 Linux pty 实现完整的终端控制
    """
    
    def __init__(self):
        self.sessions: Dict[str, PTYSession] = {}
        self.active_session_id: Optional[str] = None
        self.output_callbacks: Dict[str, List[Callable]] = {}
        
    def create_terminal(
        self,
        name: str,
        terminal_type: str = "bash",
        initial_dir: str = None
    ) -> str:
        """
        创建 PTY 终端
        
        Args:
            name: 终端名称
            terminal_type: 终端类型 (bash, zsh, sh)
            initial_dir: 初始目录
            
        Returns:
            session_id
        """
        session_id = str(uuid.uuid4())[:8]
        work_dir = initial_dir or os.getcwd()
        
        # 确定 shell
        if terminal_type == "zsh":
            shell = "zsh"
        elif terminal_type == "sh":
            shell = "sh"
        else:
            shell = "bash"
        
        try:
            # 创建 PTY
            master_fd, slave_fd = pty.openpty()
            
            # 设置环境变量
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            
            # 启动子进程
            process = subprocess.Popen(
                [shell],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=work_dir,
                env=env,
                preexec_fn=os.setsid  # 创建新的进程组
            )
            
            # 关闭 slave 端（不再需要）
            os.close(slave_fd)
            
            # 设置非阻塞模式
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # 创建会话
            output_queue = queue.Queue()
            
            session = PTYSession(
                session_id=session_id,
                name=name,
                terminal_type=terminal_type,
                master_fd=master_fd,
                process=process,
                output_queue=output_queue,
                running=True,
                current_dir=work_dir
            )
            
            self.sessions[session_id] = session
            
            # 启动输出读取线程
            thread = threading.Thread(
                target=self._read_output,
                args=(session_id,),
                daemon=True
            )
            thread.start()
            
            # 设为活动会话
            if not self.active_session_id:
                self.active_session_id = session_id
            
            logger.info(f"PTY终端创建成功: {name} ({session_id})")
            return session_id
            
        except Exception as e:
            logger.error(f"创建 PTY 终端失败: {e}")
            raise
    
    def _read_output(self, session_id: str):
        """读取终端输出（在线程中运行）"""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        try:
            while session.running and self._is_process_running(session):
                try:
                    # 使用 select 检查数据
                    ready, _, _ = select.select([session.master_fd], [], [], 0.1)
                    
                    if ready:
                        try:
                            data = os.read(session.master_fd, 4096)
                            if data:
                                # 解码并添加到队列
                                try:
                                    text = data.decode('utf-8', errors='replace')
                                except:
                                    text = data.decode('latin-1', errors='replace')
                                
                                session.output_queue.put(text)
                                
                                # 调用回调
                                if session_id in self.output_callbacks:
                                    for callback in self.output_callbacks[session_id]:
                                        try:
                                            callback(text)
                                        except:
                                            pass
                        except OSError:
                            break
                except Exception:
                    time.sleep(0.01)
                    continue
        except Exception as e:
            logger.error(f"读取输出失败: {e}")
        finally:
            session.running = False
    
    def _is_process_running(self, session: PTYSession) -> bool:
        """检查进程是否还在运行"""
        if session.process:
            return session.process.poll() is None
        return False
    
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
        if not session or not self._is_process_running(session):
            return False
        
        try:
            # 添加换行符
            if not command.endswith('\n'):
                command += '\n'
            
            os.write(session.master_fd, command.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    def send_input(self, session_id: str, char: str) -> bool:
        """发送单个字符到终端"""
        session = self.sessions.get(session_id)
        if not session or not self._is_process_running(session):
            return False
        
        try:
            os.write(session.master_fd, char.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"发送输入失败: {e}")
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
    
    def resize_terminal(self, session_id: str, rows: int = 24, cols: int = 80) -> bool:
        """调整终端大小"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        try:
            import struct
            import fcntl
            import termios
            # TIOCSWINSZ = 0x5414
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(session.master_fd, 0x5414, winsize)
            return True
        except Exception as e:
            logger.error(f"调整终端大小失败: {e}")
            return False
    
    def close_terminal(self, session_id: str) -> bool:
        """关闭终端"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        try:
            session.running = False
            
            # 关闭 PTY
            try:
                os.close(session.master_fd)
            except:
                pass
            
            # 终止进程
            if session.process:
                try:
                    # 发送 SIGHUP
                    os.killpg(os.getpgid(session.process.pid), 1)
                except:
                    pass
                
                try:
                    session.process.wait(timeout=2)
                except:
                    pass
                
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
                "status": "running" if self._is_process_running(session) else "stopped",
                "current_dir": session.current_dir,
                "pid": session.process.pid if session.process else None
            }
        return result
    
    def register_output_callback(self, session_id: str, callback: Callable):
        """注册输出回调"""
        if session_id not in self.output_callbacks:
            self.output_callbacks[session_id] = []
        self.output_callbacks[session_id].append(callback)
    
    def get_terminal_info(self, session_id: str) -> Dict:
        """获取终端信息"""
        session = self.sessions.get(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session_id,
            "name": session.name,
            "type": session.terminal_type,
            "status": "running" if self._is_process_running(session) else "stopped",
            "current_dir": session.current_dir,
            "pid": session.process.pid if session.process else None,
            "master_fd": session.master_fd
        }


# 全局单例
_pty_manager = None


def get_pty_manager() -> LinuxPTYTerminalManager:
    """获取 PTY 终端管理器单例"""
    global _pty_manager
    if _pty_manager is None:
        _pty_manager = LinuxPTYTerminalManager()
    return _pty_manager


# 平台检测
def is_linux() -> bool:
    """检测是否在 Linux 上运行"""
    return sys.platform.startswith('linux')


if __name__ == "__main__":
    # 测试代码
    if not is_linux():
        print("此测试仅适用于 Linux 系统")
        sys.exit(1)
    
    print("Linux PTY 终端管理器测试")
    print("=" * 40)
    
    manager = LinuxPTYTerminalManager()
    
    # 创建终端
    session_id = manager.create_terminal("测试终端", "bash")
    print(f"创建终端: {session_id}")
    
    # 发送命令
    time.sleep(0.5)
    manager.send_command(session_id, "echo Hello from PTY")
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
