"""
弥娅终端代理 - 运行在新打开的终端窗口中

这个脚本运行在新创建的终端中，与主弥娅系统建立通信，
让用户可以在独立终端窗口中与弥娅交互。

用法:
    python terminal_agent.py --session-id <会话ID> --mode interactive
"""
import asyncio
import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _detect_windows_host_ip() -> str:
    """
    检测Windows主机IP地址（用于WSL环境）
    
    在WSL中，localhost指向WSL自己，需要通过特殊方式获取Windows主机IP
    """
    # 检测是否在WSL中
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version", "r") as f:
                if "Microsoft" in f.read() or "WSL" in f.read():
                    # 在WSL中，尝试获取Windows主机IP
                    # 方法1: 使用 /etc/resolv.conf 中的nameserver（通常是Windows DNS）
                    if os.path.exists("/etc/resolv.conf"):
                        with open("/etc/resolv.conf", "r") as f:
                            for line in f:
                                if line.startswith("nameserver"):
                                    ip = line.split()[1]
                                    # 验证是否是有效的IP（10.x.x.x 或 172.x.x.x 或 192.168.x.x）
                                    if ip.startswith(("10.", "172.", "192.168.")):
                                        print(f"[终端代理] 检测到WSL环境，使用Windows主机IP: {ip}")
                                        return ip
                    
                    # 方法2: 使用host.docker.internal（如果可用）
                    try:
                        result = subprocess.run(
                            ["cmd.exe", "/c", "echo", "%USERDOMAIN%"],
                            capture_output=True, text=True, timeout=5
                        )
                        # 如果cmd可用，说明在WSL中，可以尝试其他方法
                    except:
                        pass
        except:
            pass
    
    # 非WSL环境，返回localhost
    return "localhost"


class MiyaTerminalAgent:
    """弥娅终端代理 - 在子终端中运行"""
    
    def __init__(self, session_id: str, host: str = None, port: int = 8000):
        self.session_id = session_id
        # 如果没有指定host，自动检测（检测WSL环境）
        if host is None:
            self.host = _detect_windows_host_ip()
        else:
            self.host = host
        self.port = port
        self.running = True
        self._session = None  # 复用 HTTP session
        
    async def connect_to_miya(self) -> bool:
        """连接到弥娅主系统"""
        # 尝试多个端口，优先尝试8000（Web API）
        ports_to_try = [8000, 8080, 8001, 8888]

        print(f"正在尝试连接到弥娅主系统...")

        for port in ports_to_try:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # Web API的状态端点是 /api/status
                    url = f"http://{self.host}:{port}/api/status"
                    print(f"  - 尝试连接 {url}")
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            self.port = port
                            print(f"✅ 已连接到弥娅主系统 (端口: {port})")
                            return True
            except Exception as e:
                print(f"  - 端口 {port} 连接失败")
                continue

        print(f"⚠️ 无法连接到弥娅主系统")
        print(f"   尝试的端口: {', '.join(map(str, ports_to_try))}")
        print(f"   请确保弥娅主程序正在运行")
        print("   请确保弥娅主程序正在运行")
        return False
    
    def _should_stream_output(self, text: str) -> bool:
        """
        判断是否应该使用流式输出（逐字显示）
        
        规则：
        - 聊天/文本内容 → 流式输出
        - 系统目录/状态/命令结果 → 一次性输出
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # 系统类内容模式（不需要流式输出）
        system_patterns = [
            # 目录列表
            text.startswith('/') or '目录' in text or '文件夹' in text,
            text.startswith('d:') or text.startswith('c:') or text.startswith('e:') or text.startswith('f:'),
            'total ' in text_lower and 'drwxr-xr-x' in text_lower,  # Linux目录
            # 命令提示符
            'root@' in text or '@' in text and ':~' in text,
            # 状态信息
            'status:' in text_lower or '状态:' in text,
            # 错误信息
            text.startswith('error') or text.startswith('error:') or text.startswith('错误'),
            # JSON/XML结构
            (text.strip().startswith('{') and text.strip().endswith('}')),
            (text.strip().startswith('[') and text.strip().endswith(']')),
            # 纯数字/符号
            text.isdigit(),
            # 命令执行结果（通常较短但有特定格式）
            ('=' * 20 in text or '-' * 20 in text),
        ]
        
        # 如果匹配任何系统模式，不使用流式输出
        if any(system_patterns):
            return False
        
        # 检查是否像正常的对话文本
        # 包含中文或常见对话词汇
        chat_indicators = [
            '你好', '您好', '我知道了', '明白了', '好的', '可以', '没问题',
            '请问', '有什么', '帮助', '是的', '不是', '但是', '因为', '所以',
            '我建议', '你可以', '让我', '我来', '推荐', '今天', '天气',
            # 标点符号比例（正常文本有更多标点）
        ]
        
        # 统计中文字符和标点
        chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        punctuation_count = sum(1 for c in text if c in '，。！？；：""''（）')
        
        # 如果有足够的中文字符或对话关键词，认为是聊天内容
        if chinese_count > 10 or any(indicator in text for indicator in chat_indicators):
            return True
        
        # 如果标点比例较高，也认为是文本
        if len(text) > 20 and punctuation_count / len(text) > 0.05:
            return True
        
        # 默认返回True（流式输出），除非明确是系统内容
        return True
    
    def _stream_print(self, text: str, prefix: str = "", delay: float = 0.02):
        """流式输出（逐字显示）
        
        Args:
            text: 要输出的文本
            prefix: 前缀（如 "【弥娅】"）
            delay: 每个字符的延迟（秒），默认0.02秒
        """
        if not text:
            print()
            return
        
        import sys
        import time
        
        # 先输出前缀
        if prefix:
            sys.stdout.write(prefix)
            sys.stdout.flush()
        
        # 逐字输出
        for i, char in enumerate(text):
            sys.stdout.write(char)
            sys.stdout.flush()
            # 最后一个字符或遇到句末标点时停顿稍长
            if i < len(text) - 1:
                if char in '。！？；：\n':
                    time.sleep(delay * 3)
                else:
                    time.sleep(delay)
        
        print()  # 最后换行
    
    async def send_message(self, message: str) -> str:
        """发送消息到弥娅并获取回复"""
        try:
            import aiohttp
            # 复用 session，避免每次请求都创建新连接
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
            
            url = f"http://{self.host}:{self.port}/api/terminal/chat"
            payload = {
                "message": message,
                "session_id": self.session_id,
                "from_terminal": self.session_id
            }
            async with self._session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "❌ 无响应")
                else:
                    return f"❌ 请求失败: {resp.status}"
        except Exception as e:
            import traceback
            error_details = f"{type(e).__name__}: {e}"
            print(f"[终端代理] 通信错误: {error_details}")
            traceback.print_exc()
            return f"❌ 通信错误: {error_details}"
    
    async def notify_session_end(self) -> bool:
        """通知主系统会话结束，触发对话历史存储到 LifeBook"""
        try:
            import aiohttp
            # 复用 session
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
            
            url = f"http://{self.host}:{self.port}/api/terminal/session_end"
            payload = {
                "session_id": self.session_id
            }
            async with self._session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    print("[终端代理] 对话历史已保存到 LifeBook")
                    return True
                else:
                    print(f"[终端代理] 保存对话历史失败: {resp.status}")
                    return False
        except Exception as e:
            print(f"[终端代理] 保存对话历史出错: {e}")
            return False
    
    async def run_interactive(self):
        """交互式运行"""
        print("\n" + "=" * 50)
        print("       弥娅终端代理 - 交互模式")
        print("=" * 50)
        print(f"会话ID: {self.session_id}")
        print("输入内容与弥娅对话，输入 'exit' 或 '退出' 结束")
        print("=" * 50 + "\n")
        
        # 尝试连接主系统
        connected = await self.connect_to_miya()
        
        if not connected:
            print("⚠️ 警告: 无法连接到弥娅主系统")
            print("   请确保弥娅主程序正在运行")
            print("   交互功能受限\n")
        
        # 等待用户输入
        while self.running:
            try:
                # 显示提示符
                user_input = input(f"[{self.session_id}] ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', '退出', 'quit', 'q']:
                    print("👋 再见！")
                    # 通知主系统会话结束，保存对话历史
                    await self.notify_session_end()
                    # 关闭 HTTP session
                    if self._session and not self._session.closed:
                        await self._session.close()
                    self.running = False
                    break
                
                # 发送消息
                print("\n[正在思考...]\n")
                response = await self.send_message(user_input)
                
                # 根据内容类型决定输出方式
                if self._should_stream_output(response):
                    # 流式输出（聊天/文本内容）
                    self._stream_print(response, "\n【弥娅】")
                    print()
                else:
                    # 一次性输出（系统/目录/命令结果）
                    print(f"\n【弥娅】{response}\n")
                
            except KeyboardInterrupt:
                print("\n👋 再见！（对话即将结束）")
                # 通知主系统会话结束，保存对话历史
                await self.notify_session_end()
                # 关闭 HTTP session
                if self._session and not self._session.closed:
                    await self._session.close()
                self.running = False
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}\n")
    
    async def run_command_mode(self, command: str):
        """命令模式 - 执行单个命令"""
        response = await self.send_message(command)
        # 命令模式通常返回系统结果，直接一次性输出
        print(response)


async def main():
    parser = argparse.ArgumentParser(description="弥娅终端代理")
    parser.add_argument("--session-id", type=str, help="会话ID")
    parser.add_argument("--mode", type=str, default="interactive", choices=["interactive", "command"])
    parser.add_argument("--command", type=str, help="命令模式下的命令")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    
    args = parser.parse_args()
    
    session_id = args.session_id or f"term_{os.getpid()}"
    
    agent = MiyaTerminalAgent(session_id, args.host, args.port)
    
    if args.mode == "interactive":
        await agent.run_interactive()
    else:
        await agent.run_command_mode(args.command)


if __name__ == "__main__":
    asyncio.run(main())
