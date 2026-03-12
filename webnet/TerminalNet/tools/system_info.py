"""
系统信息检索工具 - 弥娅完全掌控系统信息

功能：
1. 进程管理
2. 端口监控
3. 系统日志
4. 系统服务管理
5. 性能监控
6. 网络连接监控

符合 MIYA 框架：
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统
"""
import logging
import subprocess
import platform
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from webnet.tools.base import BaseTool, ToolContext


class SystemInfoTool(BaseTool):
    """
    系统信息检索工具

    让弥娅拥有完整的系统信息检索能力，可以：
    - 查看和管理进程
    - 监控端口占用
    - 查看系统日志
    - 管理系统服务
    - 监控系统性能
    - 监控网络连接
    """

    def __init__(self):
        super().__init__()
        self.name = "system_info"
        self.logger = logging.getLogger("Tool.SystemInfo")

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        return {
            "name": "system_info",
            "description": """检索和管理系统信息。当用户要求查看进程、端口、日志、服务、性能或网络信息时调用。

操作类型：
- list_processes: 列出所有进程
- find_process: 查找指定名称的进程
- kill_process: 终止指定进程（需要process_id）
- list_ports: 列出所有端口占用
- find_port: 查找指定端口
- list_services: 列出系统服务
- service_status: 查看指定服务状态（需要service_name）
- start_service: 启动指定服务（需要service_name）
- stop_service: 停止指定服务（需要service_name）
- system_logs: 查看系统日志
- performance: 查看系统性能指标
- network_connections: 查看网络连接

参数说明：
- process_id: 进程ID（kill_process时必填）
- service_name: 服务名称（service_status、start_service、stop_service时必填）
- port: 端口号（find_port时可选）
- name: 进程名称（find_process时可选）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list_processes",
                            "find_process",
                            "kill_process",
                            "list_ports",
                            "find_port",
                            "list_services",
                            "service_status",
                            "start_service",
                            "stop_service",
                            "system_logs",
                            "performance",
                            "network_connections"
                        ],
                        "description": "要执行的操作类型"
                    },
                    "process_id": {
                        "type": "string",
                        "description": "进程ID（kill_process时必填）"
                    },
                    "name": {
                        "type": "string",
                        "description": "进程名称（find_process时可选）"
                    },
                    "port": {
                        "type": "string",
                        "description": "端口号（find_port时可选）"
                    },
                    "service_name": {
                        "type": "string",
                        "description": "服务名称（service_status、start_service、stop_service时必填）"
                    },
                    "lines": {
                        "type": "number",
                        "description": "显示的行数（system_logs时可选，默认50）"
                    }
                },
                "required": ["action"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行系统信息检索操作

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        action = args.get("action", "")

        if not action:
            return "❌ 缺少action参数"

        try:
            if action == "list_processes":
                return await self._list_processes()
            elif action == "find_process":
                return await self._find_process(args)
            elif action == "kill_process":
                return await self._kill_process(args, context)
            elif action == "list_ports":
                return await self._list_ports()
            elif action == "find_port":
                return await self._find_port(args)
            elif action == "list_services":
                return await self._list_services()
            elif action == "service_status":
                return await self._service_status(args)
            elif action == "start_service":
                return await self._start_service(args, context)
            elif action == "stop_service":
                return await self._stop_service(args, context)
            elif action == "system_logs":
                return await self._system_logs(args)
            elif action == "performance":
                return await self._performance()
            elif action == "network_connections":
                return await self._network_connections()
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            self.logger.error(f"执行操作失败: {e}", exc_info=True)
            return f"❌ 操作执行失败: {str(e)}"

    async def _list_processes(self) -> str:
        """列出所有进程"""
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["tasklist"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📋 进程列表（Windows）\n\n{result.stdout}"
                else:
                    return f"❌ 获取进程列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取进程列表时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                # 使用ps命令
                result = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📋 进程列表\n\n{result.stdout}"
                else:
                    return f"❌ 获取进程列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取进程列表时出错: {str(e)}"

    async def _find_process(self, args: Dict[str, Any]) -> str:
        """查找指定名称的进程"""
        name = args.get("name", "")

        if not name:
            return "❌ 缺少process_name参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {name}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🔍 查找进程: {name}\n\n{result.stdout}"
                else:
                    return f"❌ 查找进程失败: {result.stderr}"
            except Exception as e:
                return f"❌ 查找进程时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["ps", "aux", "|", "grep", name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🔍 查找进程: {name}\n\n{result.stdout}"
                else:
                    return f"❌ 查找进程失败: {result.stderr}"
            except Exception as e:
                return f"❌ 查找进程时出错: {str(e)}"

    async def _kill_process(self, args: Dict[str, Any], context: ToolContext) -> str:
        """终止指定进程"""
        process_id = args.get("process_id", "")

        if not process_id:
            return "❌ 缺少process_id参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["taskkill", "/PID", process_id, "/F"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return f"✅ 已终止进程 {process_id}\n\n{result.stdout}"
                else:
                    return f"❌ 终止进程失败: {result.stderr}"
            except Exception as e:
                return f"❌ 终止进程时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["kill", "-9", process_id],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return f"✅ 已终止进程 {process_id}"
                else:
                    return f"❌ 终止进程失败: {result.stderr}"
            except Exception as e:
                return f"❌ 终止进程时出错: {str(e)}"

    async def _list_ports(self) -> str:
        """列出所有端口占用"""
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🌐 端口占用列表（Windows）\n\n{result.stdout}"
                else:
                    return f"❌ 获取端口列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取端口列表时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["netstat", "-tuln"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🌐 端口占用列表\n\n{result.stdout}"
                else:
                    return f"❌ 获取端口列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取端口列表时出错: {str(e)}"

    async def _find_port(self, args: Dict[str, Any]) -> str:
        """查找指定端口"""
        port = args.get("port", "")

        if not port:
            return "❌ 缺少port参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["netstat", "-ano", "|", "findstr", f":{port}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🔍 查找端口: {port}\n\n{result.stdout}"
                else:
                    return f"❌ 查找端口失败: {result.stderr}"
            except Exception as e:
                return f"❌ 查找端口时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["netstat", "-tuln", "|", "grep", f":{port}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"🔍 查找端口: {port}\n\n{result.stdout}"
                else:
                    return f"❌ 查找端口失败: {result.stderr}"
            except Exception as e:
                return f"❌ 查找端口时出错: {str(e)}"

    async def _list_services(self) -> str:
        """列出系统服务"""
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["sc", "query", "type=", "service", "state=", "all"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return f"📋 系统服务列表（Windows）\n\n{result.stdout}"
                else:
                    return f"❌ 获取服务列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取服务列表时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--all"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return f"📋 系统服务列表\n\n{result.stdout}"
                else:
                    # 回退到 service 命令
                    result = subprocess.run(
                        ["service", "--status-all"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        return f"📋 系统服务列表\n\n{result.stdout}"
                    else:
                        return f"❌ 获取服务列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取服务列表时出错: {str(e)}"

    async def _service_status(self, args: Dict[str, Any]) -> str:
        """查看指定服务状态"""
        service_name = args.get("service_name", "")

        if not service_name:
            return "❌ 缺少service_name参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["sc", "query", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📋 服务状态: {service_name}\n\n{result.stdout}"
                else:
                    return f"❌ 获取服务状态失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取服务状态时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["systemctl", "status", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📋 服务状态: {service_name}\n\n{result.stdout}"
                else:
                    return f"❌ 获取服务状态失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取服务状态时出错: {str(e)}"

    async def _start_service(self, args: Dict[str, Any], context: ToolContext) -> str:
        """启动指定服务"""
        service_name = args.get("service_name", "")

        if not service_name:
            return "❌ 缺少service_name参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["sc", "start", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"✅ 已启动服务: {service_name}\n\n{result.stdout}"
                else:
                    return f"❌ 启动服务失败: {result.stderr}"
            except Exception as e:
                return f"❌ 启动服务时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["sudo", "systemctl", "start", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"✅ 已启动服务: {service_name}"
                else:
                    return f"❌ 启动服务失败: {result.stderr}"
            except Exception as e:
                return f"❌ 启动服务时出错: {str(e)}"

    async def _stop_service(self, args: Dict[str, Any], context: ToolContext) -> str:
        """停止指定服务"""
        service_name = args.get("service_name", "")

        if not service_name:
            return "❌ 缺少service_name参数"

        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["sc", "stop", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"✅ 已停止服务: {service_name}\n\n{result.stdout}"
                else:
                    return f"❌ 停止服务失败: {result.stderr}"
            except Exception as e:
                return f"❌ 停止服务时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["sudo", "systemctl", "stop", service_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"✅ 已停止服务: {service_name}"
                else:
                    return f"❌ 停止服务失败: {result.stderr}"
            except Exception as e:
                return f"❌ 停止服务时出错: {str(e)}"

    async def _system_logs(self, args: Dict[str, Any]) -> str:
        """查看系统日志"""
        lines = args.get("lines", 50)
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ["wevtutil", "qe", "System", "/c:10", "/rd:true", "/f:text"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📝 系统日志（Windows，最近10条）\n\n{result.stdout}"
                else:
                    return f"❌ 获取系统日志失败: {result.stderr}"
            except Exception as e:
                return f"❌ 获取系统日志时出错: {str(e)}"
        else:
            # Unix-like系统
            try:
                result = subprocess.run(
                    ["journalctl", "-n", str(lines), "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return f"📝 系统日志（最近{lines}条）\n\n{result.stdout}"
                else:
                    # 回退到 syslog 或 messages
                    try:
                        result = subprocess.run(
                            ["tail", f"-{lines}", "/var/log/syslog"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            return f"📝 系统日志（/var/log/syslog，最近{lines}条）\n\n{result.stdout}"
                        else:
                            return f"❌ 获取系统日志失败: {result.stderr}"
                    except:
                        return f"❌ 获取系统日志失败"
            except Exception as e:
                return f"❌ 获取系统日志时出错: {str(e)}"

    async def _performance(self) -> str:
        """查看系统性能指标"""
        result = "📊 系统性能指标\n\n"

        system = platform.system()

        # CPU使用率
        result += "CPU使用率:\n"
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            result += f"  当前使用率: {cpu_percent:.1f}%\n"

            # CPU核心使用率
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            result += "  各核心使用率: "
            result += ", ".join([f"{p:.1f}%" for p in cpu_per_core])
            result += "\n"

            # 负载平均值（Unix-like）
            if system != "Windows":
                load_avg = psutil.getloadavg()
                result += f"  负载平均值 (1m/5m/15m): {load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}\n"
        except:
            result += "  检测失败\n"

        # 内存使用
        result += "\n内存使用:\n"
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            used_gb = mem.used / (1024 ** 3)
            available_gb = mem.available / (1024 ** 3)
            result += f"  总内存: {total_gb:.2f} GB\n"
            result += f"  已用内存: {used_gb:.2f} GB ({mem.percent:.1f}%)\n"
            result += f"  可用内存: {available_gb:.2f} GB\n"
        except:
            result += "  检测失败\n"

        # 磁盘使用
        result += "\n磁盘使用:\n"
        try:
            import psutil
            disk = psutil.disk_usage('/')
            total_gb = disk.total / (1024 ** 3)
            used_gb = disk.used / (1024 ** 3)
            free_gb = disk.free / (1024 ** 3)
            result += f"  总空间: {total_gb:.2f} GB\n"
            result += f"  已用空间: {used_gb:.2f} GB ({disk.percent:.1f}%)\n"
            result += f"  可用空间: {free_gb:.2f} GB\n"

            # 磁盘IO
            disk_io = psutil.disk_io_counters()
            if disk_io:
                result += f"  读取: {disk_io.read_bytes / (1024**2):.2f} MB\n"
                result += f"  写入: {disk_io.write_bytes / (1024**2):.2f} MB\n"
        except:
            result += "  检测失败\n"

        # 网络IO
        result += "\n网络IO:\n"
        try:
            import psutil
            net_io = psutil.net_io_counters()
            if net_io:
                result += f"  发送: {net_io.bytes_sent / (1024**2):.2f} MB\n"
                result += f"  接收: {net_io.bytes_recv / (1024**2):.2f} MB\n"
        except:
            result += "  检测失败\n"

        # 进程数量
        result += "\n进程数量:\n"
        try:
            import psutil
            proc_count = len(psutil.pids())
            result += f"  总进程数: {proc_count}\n"
        except:
            result += "  检测失败\n"

        # 启动时间
        result += "\n系统启动时间:\n"
        try:
            import psutil
            boot_time = psutil.boot_time()
            boot_datetime = datetime.fromtimestamp(boot_time)
            result += f"  {boot_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n"
        except:
            result += "  检测失败\n"

        return result

    async def _network_connections(self) -> str:
        """查看网络连接"""
        system = platform.system()

        result = "🌐 网络连接\n\n"

        try:
            import psutil
            connections = psutil.net_connections()

            result += f"总连接数: {len(connections)}\n\n"

            # 按状态分组
            status_count = {}
            for conn in connections:
                status = conn.status
                status_count[status] = status_count.get(status, 0) + 1

            result += "连接状态统计:\n"
            for status, count in status_count.items():
                result += f"  {status}: {count}\n"

            result += "\n最近的连接:\n"
            # 显示最近的10个连接
            for i, conn in enumerate(connections[:10]):
                local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                result += f"  [{i+1}] {local_addr} -> {remote_addr} ({conn.status})\n"

        except Exception as e:
            result += f"检测失败: {str(e)}\n"

        return result

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        action = args.get("action")

        if not action:
            return False, "缺少必填参数: action"

        if action == "kill_process":
            if not args.get("process_id"):
                return False, "kill_process 需要 process_id 参数"

        if action in ["service_status", "start_service", "stop_service"]:
            if not args.get("service_name"):
                return False, f"{action} 需要 service_name 参数"

        return True, None
