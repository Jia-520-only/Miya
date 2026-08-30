#!/usr/bin/env python3
"""
弥娅多端状态监控面板
实时显示各端服务状态和性能指标
"""

import asyncio
import os
import platform
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

import aiohttp


@dataclass
class ServiceStatus:
    """服务状态"""

    name: str
    type: str  # terminal, web, api, desktop, qq
    status: str  # running, stopped, starting, error
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: Optional[float] = None  # 运行时间（秒）
    cpu_usage: Optional[float] = None  # CPU使用率
    memory_usage: Optional[float] = None  # 内存使用率
    last_check: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    endpoint_url: Optional[str] = None


class MultiEndMonitor:
    """多端状态监控器"""

    def __init__(self):
        self.services: Dict[str, ServiceStatus] = {}
        self.running = True
        self.update_interval = 5  # 更新间隔（秒）

        # 初始化服务定义
        self._init_services()

    def _init_services(self):
        """初始化服务定义"""
        self.services = {
            "api": ServiceStatus(
                name="API服务器",
                type="api",
                status="unknown",
                port=8001,
                endpoint_url="http://localhost:8001/api/status",
            ),
            "web": ServiceStatus(
                name="Web服务", type="web", status="unknown", port=8000, endpoint_url="http://localhost:8000/status"
            ),
            "terminal": ServiceStatus(name="多终端系统", type="terminal", status="unknown", port=None),
            "desktop": ServiceStatus(name="桌面应用", type="desktop", status="unknown", port=8002),
        }

    async def check_port(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except:
            return False

    async def check_api_endpoint(self, url: str) -> Optional[Dict]:
        """检查API端点"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
        except:
            pass
        return None

    async def check_service(self, service_id: str, service: ServiceStatus):
        """检查单个服务状态"""
        old_status = service.status

        # 检查端口（如果有）
        if service.port:
            port_available = await self.check_port(service.port)
            if port_available:
                service.status = "running"

                # 检查API端点（如果有）
                if service.endpoint_url:
                    endpoint_data = await self.check_api_endpoint(service.endpoint_url)
                    if endpoint_data:
                        # 更新额外信息
                        if "uptime" in endpoint_data:
                            service.uptime = endpoint_data["uptime"]
                        if "version" in endpoint_data:
                            service.error_message = f"版本: {endpoint_data['version']}"
            else:
                service.status = "stopped"
                service.error_message = f"端口 {service.port} 不可用"
        else:
            # 对于无端口服务，通过进程检查
            service.status = "unknown"
            service.error_message = "无端口监控"

        # 更新最后检查时间
        service.last_check = time.time()

        # 状态变化通知
        if old_status != service.status:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {service.name}: {old_status} -> {service.status}")

    async def update_all_services(self):
        """更新所有服务状态"""
        tasks = []
        for service_id, service in self.services.items():
            tasks.append(self.check_service(service_id, service))

        await asyncio.gather(*tasks)

    def print_status_dashboard(self):
        """打印状态面板"""
        os.system("cls" if platform.system() == "Windows" else "clear")

        print("=" * 80)
        print("                    弥娅多端状态监控面板")
        print("=" * 80)
        print(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # 服务状态表
        print("服务状态:")
        print("-" * 80)
        print(f"{'服务名称':<15} {'类型':<10} {'状态':<12} {'端口':<8} {'运行时间':<12} {'备注'}")
        print("-" * 80)

        for _service_id, service in self.services.items():
            # 状态图标
            status_icon = {"running": "🟢", "stopped": "🔴", "starting": "🟡", "error": "🔴", "unknown": "⚪"}.get(
                service.status, "⚪"
            )

            # 端口显示
            port_display = str(service.port) if service.port else "N/A"

            # 运行时间显示
            if service.uptime:
                if service.uptime < 60:
                    uptime_display = f"{int(service.uptime)}秒"
                elif service.uptime < 3600:
                    uptime_display = f"{int(service.uptime / 60)}分钟"
                else:
                    uptime_display = f"{int(service.uptime / 3600)}小时"
            else:
                uptime_display = "N/A"

            # 备注信息
            remark = service.error_message or "-"

            print(
                f"{status_icon} {service.name:<13} {service.type:<10} {service.status:<12} {port_display:<8} {uptime_display:<12} {remark}"
            )

        print("-" * 80)

        # 系统信息
        print("\n系统信息:")
        print("-" * 80)
        print(f"操作系统: {platform.system()} {platform.release()}")
        print(f"Python版本: {platform.python_version()}")
        print(f"监控间隔: {self.update_interval}秒")
        print(f"运行时间: {int(time.time() - self.start_time)}秒")
        print("-" * 80)

        # 操作提示
        print("\n操作提示:")
        print("  Ctrl+C 退出监控")
        print("  r 手动刷新")
        print("  q 退出")
        print("=" * 80)

    async def run(self):
        """运行监控器"""
        self.start_time = time.time()

        # 初始检查
        await self.update_all_services()
        self.print_status_dashboard()

        # 启动键盘监听线程
        keyboard_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        keyboard_thread.start()

        # 主循环
        last_update = time.time()
        while self.running:
            current_time = time.time()

            # 定时更新
            if current_time - last_update >= self.update_interval:
                await self.update_all_services()
                self.print_status_dashboard()
                last_update = current_time

            # 短暂休眠，避免CPU占用过高
            await asyncio.sleep(0.5)

    def _keyboard_listener(self):
        """键盘监听"""
        # FIX: Windows 环境没有 tty/termios；需要按平台分支实现非阻塞按键读取。
        if platform.system() == "Windows":
            import msvcrt

            while self.running:
                try:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        try:
                            key_str = key.decode("utf-8", errors="ignore")
                        except Exception:
                            key_str = ""

                        if key_str in ("q", "Q"):
                            self.running = False
                            print("\n正在退出监控...")
                            break
                        elif key_str in ("r", "R"):
                            loop = asyncio.get_event_loop()
                            asyncio.run_coroutine_threadsafe(self.update_all_services(), loop)
                            asyncio.run_coroutine_threadsafe(self.print_status_dashboard(), loop)
                    time.sleep(0.1)
                except Exception:
                    time.sleep(0.1)
        else:
            import select
            import termios
            import tty

            # 保存原始终端设置
            old_settings = termios.tcgetattr(sys.stdin)

            try:
                tty.setcbreak(sys.stdin.fileno())

                while self.running:
                    # 非阻塞读取
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)

                        if key == "q" or key == "\x03":  # q 或 Ctrl+C
                            self.running = False
                            print("\n正在退出监控...")
                            break
                        elif key == "r":  # r 刷新
                            asyncio.run_coroutine_threadsafe(self.update_all_services(), asyncio.get_event_loop())
                            asyncio.run_coroutine_threadsafe(self.print_status_dashboard(), asyncio.get_event_loop())

            finally:
                # 恢复原始终端设置
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def stop(self):
        """停止监控器"""
        self.running = False


async def main():
    """主函数"""
    print("启动弥娅多端状态监控...")

    try:
        monitor = MultiEndMonitor()
        await monitor.run()
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"监控错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Windows兼容性处理
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
