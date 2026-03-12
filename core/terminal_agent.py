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
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MiyaTerminalAgent:
    """弥娅终端代理 - 在子终端中运行"""
    
    def __init__(self, session_id: str, host: str = "localhost", port: int = 8000):
        self.session_id = session_id
        self.host = host
        self.port = port
        self.running = True
        
    async def connect_to_miya(self) -> bool:
        """连接到弥娅主系统"""
        # 尝试多个端口
        ports_to_try = [8080, 8000, 8001, 8888]

        print(f"正在尝试连接到弥娅主系统...")

        for port in ports_to_try:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # 尝试连接状态 API
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
    
    async def send_message(self, message: str) -> str:
        """发送消息到弥娅并获取回复"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # 使用 terminal/chat 端点
                url = f"http://{self.host}:{self.port}/api/terminal/chat"
                payload = {
                    "message": message,
                    "session_id": self.session_id,
                    "from_terminal": self.session_id
                }
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "❌ 无响应")
                    else:
                        return f"❌ 请求失败: {resp.status}"
        except Exception as e:
            return f"❌ 通信错误: {e}"
    
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
                    self.running = False
                    break
                
                # 发送消息
                print("\n[正在思考...]\n")
                response = await self.send_message(user_input)
                print(f"\n【弥娅】{response}\n")
                
            except KeyboardInterrupt:
                print("\n👋 再见！")
                self.running = False
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}\n")
    
    async def run_command_mode(self, command: str):
        """命令模式 - 执行单个命令"""
        response = await self.send_message(command)
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
