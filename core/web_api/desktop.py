"""桌面操控API路由模块

提供终端命令执行、文件管理、系统信息、进程管理等API接口。
"""

import builtins
import contextlib
import logging
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from core.text_loader import get_permission
from core.dsh_routing import execute_dsh

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

        project_root = Path(__file__).parent.parent.parent.resolve()

        def checked_path(raw_path: str, *, must_exist: bool = False) -> Path:
            """Keep Web file operations inside the Miya project boundary."""
            candidate = Path(raw_path).expanduser().resolve(strict=False)
            try:
                candidate.relative_to(project_root)
            except ValueError as exc:
                raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围") from exc
            if must_exist and not candidate.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            return candidate

        @self.router.post("/terminal/execute")
        async def execute_terminal_command(command: str, timeout: int = 30):
            """执行终端命令（电脑操控核心功能）"""
            try:
                dangerous_commands = ("rm -rf /", "format", "del /f /s /q", "shutdown", "reboot")
                if any(dcmd in command.lower() for dcmd in dangerous_commands):
                    raise HTTPException(status_code=403, detail="危险命令已被拦截")
                result = await execute_dsh(
                    getattr(self.decision_hub, "tool_subnet", None),
                    f"执行以下终端命令，并保留 stdout、stderr 和退出码：\n{command}",
                    timeout=timeout,
                    user_id=1,
                    platform="web",
                    sender_name="desktop",
                )
                return {
                    "success": bool(result.get("success")),
                    "command": command,
                    "exit_code": result.get("exit_code"),
                    "stdout": result.get("stdout", result.get("output", "")),
                    "stderr": result.get("stderr", result.get("error", "")),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[DesktopRoutes] 终端命令执行失败: {e}", exc_info=True)
                return {"success": False, "error": str(e), "command": command}

        @self.router.get("/files/list")
        async def list_files_api(path: str = ".", recursive: bool = False):
            """列出文件（电脑操控）"""
            try:
                checked_path(path)
                result = await execute_dsh(
                    getattr(self.decision_hub, "tool_subnet", None),
                    f"列出目录 {path} 的文件，recursive={recursive}。请优先返回 JSON 数组，每项包含 name、path、is_dir、size、modified。",
                    timeout=60,
                    user_id=1,
                    platform="web",
                    sender_name="desktop",
                )
                structured = result.get("structured_output")
                if isinstance(structured, list):
                    file_list = structured
                elif isinstance(structured, dict) and isinstance(structured.get("files"), list):
                    file_list = structured["files"]
                else:
                    file_list = []
                return {
                    "success": bool(result.get("success")),
                    "path": path,
                    "files": file_list,
                    "count": len(file_list),
                    "result": result.get("output", "") if not file_list else None,
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
                file_path = checked_path(path, must_exist=True)
                if not file_path.is_file():
                    raise HTTPException(status_code=404, detail="文件不存在")
                if file_path.stat().st_size > 10 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="文件过大")
                result = await execute_dsh(
                    getattr(self.decision_hub, "tool_subnet", None),
                    f"读取文件 {path} 的内容，返回第 {offset} 行起最多 {limit} 行。",
                    timeout=60,
                    user_id=1,
                    platform="web",
                    sender_name="desktop",
                )
                structured = result.get("structured_output")
                content = (
                    str(structured.get("content", ""))
                    if isinstance(structured, dict) and "content" in structured
                    else str(result.get("output", ""))
                )
                lines = content.splitlines(keepends=True)
                return {
                    "success": bool(result.get("success")),
                    "path": path,
                    "content": content,
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
                checked_path(path)
                result = await execute_dsh(
                    getattr(self.decision_hub, "tool_subnet", None),
                    f"将以下内容写入文件 {path}，覆盖原内容：\n{content}",
                    timeout=60,
                    user_id=1,
                    platform="web",
                    sender_name="desktop",
                )
                return {
                    "success": bool(result.get("success")),
                    "path": path,
                    "message": "文件写入成功",
                    "result": result.get("output", ""),
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
                checked_path(path, must_exist=True)
                result = await execute_dsh(
                    getattr(self.decision_hub, "tool_subnet", None),
                    f"删除文件或目录 {path}。仅执行这一个删除操作并返回结果。",
                    timeout=60,
                    user_id=1,
                    platform="web",
                    sender_name="desktop",
                )
                return {
                    "success": bool(result.get("success")),
                    "path": path,
                    "message": "删除成功" if result.get("success") else result.get("error", "删除失败"),
                    "result": result.get("output", ""),
                }
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
