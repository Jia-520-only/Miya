"""桌面操控API路由模块

提供终端命令执行、文件管理、系统信息、进程管理等API接口。
"""

import builtins
import contextlib
import logging
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.text_loader import get_permission

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception


class DesktopRoutes:
    """桌面操控路由

    职责:
    - 终端命令执行
    - 文件系统操作（列表、读取、写入、删除）
    - 系统信息获取
    - 进程管理（列表、终止）
    - 可用工具列表
    """

    def __init__(self, web_net: Any, decision_hub: Any):
        """初始化桌面路由

        Args:
            web_net: WebNet实例
            decision_hub: DecisionHub实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            self.router = None
            return

        self.router = APIRouter(prefix="/api/desktop", tags=["Desktop"])
        self._setup_routes()
        logger.info("[DesktopRoutes] 桌面路由已初始化")

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/terminal/execute")
        async def execute_terminal_command(command: str, timeout: int = 30):
            """执行终端命令（电脑操控核心功能）"""
            try:
                # 安全检查：禁止危险命令
                dangerous_commands = [
                    "rm -rf /",
                    "format",
                    "del /f /s /q",
                    "shutdown",
                    "reboot",
                ]
                if any(dcmd in command for dcmd in dangerous_commands):
                    raise HTTPException(status_code=403, detail="危险命令已被拦截")

                # 执行命令
                result = subprocess.run(
                    command,
                    shell=True,  # nosec B602
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="ignore",
                )

                return {
                    "success": True,
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "命令执行超时", "command": command}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 终端命令执行失败: {e}", exc_info=True)
                return {"success": False, "error": str(e), "command": command}

        @self.router.get("/files/list")
        async def list_files_api(path: str = ".", recursive: bool = False):
            """列出文件（电脑操控）"""
            try:
                base_path = Path(path).resolve()
                # 安全检查：限制在项目目录内
                project_path = Path(__file__).parent.parent.parent.resolve()
                try:
                    base_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                files = list(base_path.rglob("*")) if recursive else list(base_path.iterdir())

                file_list = []
                for f in files:
                    with contextlib.suppress(builtins.BaseException):
                        file_list.append(
                            {
                                "name": f.name,
                                "path": str(f),
                                "is_dir": f.is_dir(),
                                "size": f.stat().st_size if f.is_file() else 0,
                                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                            }
                        )

                return {
                    "success": True,
                    "path": path,
                    "files": file_list,
                    "count": len(file_list),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 列出文件失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/files/read")
        async def read_file_api(path: str, offset: int = 0, limit: int = 1000):
            """读取文件内容"""
            try:
                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                if not file_path.is_file():
                    raise HTTPException(status_code=404, detail="文件不存在")

                # 限制文件大小
                if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                    raise HTTPException(status_code=400, detail="文件过大")

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[offset : offset + limit]

                return {
                    "success": True,
                    "path": path,
                    "content": "".join(lines),
                    "lines": lines,
                    "total_lines_read": len(lines),
                    "offset": offset,
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 读取文件失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/files/write")
        async def write_file_api(request: dict = None):
            """写入文件内容（JSON body: {path, content}）"""
            request = request or {}
            path = str(request.get("path", ""))
            content = str(request.get("content", ""))
            if not path:
                raise HTTPException(status_code=400, detail="缺少 path 参数")
            try:
                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                # 创建父目录
                file_path.parent.mkdir(parents=True, exist_ok=True)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                return {
                    "success": True,
                    "path": path,
                    "message": "文件写入成功",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 写入文件失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.delete("/files/delete")
        async def delete_file_api(path: str):
            """删除文件"""
            try:
                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if file_path.is_dir():
                    import shutil

                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

                return {"success": True, "path": path, "message": "删除成功"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 删除文件失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/system/info")
        async def get_system_info():
            """获取系统信息"""
            import psutil as _psutil

            try:
                return {
                    "success": True,
                    "system": {
                        "os": platform.system(),
                        "os_version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                        "python_version": platform.python_version(),
                    },
                    "cpu": {
                        "count": _psutil.cpu_count(),
                        "percent": _psutil.cpu_percent(interval=1),
                    },
                    "memory": {
                        "total": _psutil.virtual_memory().total,
                        "available": _psutil.virtual_memory().available,
                        "percent": _psutil.virtual_memory().percent,
                    },
                    "disk": {
                        "total": _psutil.disk_usage("/").total
                        if platform.system() != "Windows"
                        else _psutil.disk_usage("C:\\").total,
                        "used": _psutil.disk_usage("/").used
                        if platform.system() != "Windows"
                        else _psutil.disk_usage("C:\\").used,
                        "free": _psutil.disk_usage("/").free
                        if platform.system() != "Windows"
                        else _psutil.disk_usage("C:\\").free,
                    },
                }
            except Exception as e:
                logger.error(f"[DesktopRoutes] 获取系统信息失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/processes")
        async def list_processes():
            """列出运行中的进程"""
            import psutil as _psutil

            try:
                processes = []
                for proc in _psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
                    with contextlib.suppress(builtins.BaseException):
                        processes.append(
                            {
                                "pid": proc.info["pid"],
                                "name": proc.info["name"],
                                "username": proc.info["username"],
                                "cpu_percent": proc.info["cpu_percent"],
                                "memory_percent": proc.info["memory_percent"],
                            }
                        )

                # 按CPU使用率排序
                processes.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)

                return {
                    "success": True,
                    "processes": processes[:50],  # 限制返回50个进程
                }
            except Exception as e:
                logger.error(f"[DesktopRoutes] 列出进程失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/processes/kill")
        async def kill_process(pid: int):
            """终止进程"""
            import psutil as _psutil

            try:
                proc = _psutil.Process(pid)
                proc.terminate()

                return {"success": True, "pid": pid, "message": f"进程 {pid} 已终止"}
            except _psutil.NoSuchProcess:
                raise HTTPException(status_code=404, detail="进程不存在")
            except _psutil.AccessDenied:
                raise HTTPException(
                    status_code=403,
                    detail=get_permission("tool_permissions.process_kill_denied", "权限不足"),
                )
            except Exception as e:
                logger.error(f"[DesktopRoutes] 终止进程失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/tools/available")
        async def get_available_tools():
            """获取可用工具列表（MCP/Skill）"""
            try:
                if hasattr(self.decision_hub, "tool_subnet") and self.decision_hub.tool_subnet:
                    # 使用 get_tools_schema 获取工具信息
                    tools_schema = self.decision_hub.tool_subnet.get_tools_schema()

                    tool_list = []
                    for tool_schema in tools_schema:
                        tool_list.append(
                            {
                                "name": tool_schema.get("function", {}).get("name", ""),
                                "description": tool_schema.get("function", {}).get("description", ""),
                                "category": tool_schema.get("category", "general"),
                                "parameters": tool_schema.get("function", {}).get("parameters", {}),
                            }
                        )

                    return {
                        "success": True,
                        "tools": tool_list,
                        "count": len(tool_list),
                    }
                else:
                    return {"success": False, "message": "工具子网未初始化"}
            except Exception as e:
                logger.error(f"[DesktopRoutes] 获取工具列表失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

    def get_router(self):
        """获取路由器"""
        return self.router
