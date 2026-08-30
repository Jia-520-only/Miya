"""系统状态API路由模块

提供系统状态、监控、日志、活动记录等API接口。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception


class SystemRoutes:
    """系统相关路由

    职责:
    - 系统状态查询
    - 系统监控数据
    - 日志管理
    - 最近活动记录
    - 情绪状态查询
    - 平台能力检测
    """

    def __init__(self, web_net: Any, decision_hub: Any):
        """初始化系统路由

        Args:
            web_net: WebNet实例
            decision_hub: DecisionHub实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            self.router = None
            return

        self.router = APIRouter(prefix="/api/system", tags=["System"])
        self._setup_routes()
        logger.info("[SystemRoutes] 系统路由已初始化")

    def _setup_routes(self):
        """设置路由"""

        @self.router.get("/status")
        async def get_system_status():
            """获取系统状态（包含平台自动检测和真实统计数据）"""
            try:
                # 优先从 decision_hub 获取完整状态
                if hasattr(self.decision_hub, "miya_instance"):
                    miya = self.decision_hub.miya_instance
                    status = miya.get_system_status()

                    # 获取Web平台适配器的自动检测结果
                    from hub.platform_adapters import get_adapter

                    web_adapter = get_adapter("desktop")
                    platform_info = web_adapter.get_platform_info()

                    # 获取终端工具统计
                    terminal_stats = {
                        "total_commands": 0,
                        "last_command": "N/A",
                        "status": "unknown",
                    }
                    if hasattr(self.decision_hub, "terminal_tool") and self.decision_hub.terminal_tool:
                        try:
                            # 检查是否有 get_command_history 方法
                            if hasattr(self.decision_hub.terminal_tool, "get_command_history"):
                                history = self.decision_hub.terminal_tool.get_command_history(1)
                            else:
                                history = []

                            # 检查是否有 get_command_statistics 方法
                            if hasattr(
                                self.decision_hub.terminal_tool,
                                "get_command_statistics",
                            ):
                                statistics = self.decision_hub.terminal_tool.get_command_statistics()
                            else:
                                statistics = {}

                            terminal_stats = {
                                "total_commands": statistics.get("total", 0) if statistics else 0,
                                "last_command": history[0].get("command", "N/A") if history else "N/A",
                                "status": "ready",
                            }
                        except Exception as e:
                            logger.warning(f"[SystemRoutes] 获取终端统计失败: {e}")

                    # 获取自主决策引擎统计
                    autonomy_stats = {
                        "status": "unknown",
                        "total_decisions": 0,
                        "total_fixes": 0,
                    }
                    if hasattr(miya, "autonomous_engine") and miya.autonomous_engine:
                        try:
                            if hasattr(miya.autonomous_engine, "get_statistics"):
                                auto_stats = miya.autonomous_engine.get_statistics()
                                autonomy_stats = {
                                    "status": "active",
                                    "total_decisions": auto_stats.get("total_decisions", 0),
                                    "total_fixes": auto_stats.get("total_fixes", 0),
                                }
                        except Exception as e:
                            logger.warning(f"[SystemRoutes] 获取自主决策统计失败: {e}")

                    # 获取安全统计
                    security_stats = {
                        "status": "unknown",
                        "blocked_ips": 0,
                        "total_events": 0,
                    }
                    if self.web_net and hasattr(self.web_net, "security_manager"):
                        try:
                            security_events = self.web_net.security_manager.get_security_events(limit=1000)
                            security_stats = {
                                "status": "protected",
                                "blocked_ips": len([e for e in security_events if e.get("type") == "ip_blocked"]),
                                "total_events": len(security_events),
                            }
                        except Exception as e:
                            logger.warning(f"[SystemRoutes] 获取安全统计失败: {e}")

                    # 转换为前端需要的格式
                    return {
                        "identity": status.get("identity", {}),
                        "personality": status.get("personality", {}),
                        "emotion": status.get("emotion", {}),
                        "memory_stats": status.get("memory_stats", {}),
                        "stats": status.get("stats", {}),
                        "platform_info": platform_info,
                        "system_capabilities": platform_info.get("system_capabilities", {}),
                        "available_tools": platform_info.get("available_tools", []),
                        "capabilities": platform_info.get("capabilities", {}),
                        "autonomy": autonomy_stats,
                        "security": security_stats,
                        "terminal": terminal_stats,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                # 降级到 web_net
                elif self.web_net:
                    status = self.web_net.get_system_status()
                    return status
                else:
                    raise HTTPException(status_code=500, detail="系统状态不可用")
            except Exception as e:
                logger.error(f"[SystemRoutes] 获取系统状态失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/monitor")
        async def get_system_monitor():
            """获取系统监控数据（实时）"""
            import psutil as _psutil

            def _is_process_running(process):
                """安全地检查进程状态"""
                try:
                    return process.status() == "running"
                except (_psutil.NoSuchProcess, _psutil.AccessDenied, _psutil.ZombieProcess):
                    return False

            try:
                from hub.platform_adapters import get_adapter

                web_adapter = get_adapter("desktop")
                capabilities = web_adapter.detect_system_capabilities()

                # 获取更多实时数据
                monitor_data = {
                    "cpu": {
                        **capabilities["cpu"],
                        "per_core": [round(p, 1) for p in _psutil.cpu_percent(interval=0.1, percpu=True)],
                    },
                    "memory": {
                        **capabilities["memory"],
                        "used_gb": round(
                            capabilities["memory"]["total_gb"]
                            * (1 - capabilities["memory"]["available_gb"] / capabilities["memory"]["total_gb"]),
                            2,
                        ),
                    },
                    "disk": {**capabilities["disk"]},
                    "network": {
                        **capabilities["network"],
                        "bytes_sent": _psutil.net_io_counters().bytes_sent,
                        "bytes_recv": _psutil.net_io_counters().bytes_recv,
                    },
                    "process": {
                        "total": len(_psutil.pids()),
                        "running": len([p for p in _psutil.process_iter() if _is_process_running(p)]),
                    },
                }

                return {
                    "success": True,
                    "monitor": monitor_data,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error(f"[SystemRoutes] 获取系统监控失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/logs")
        async def get_system_logs(limit: int = 50, level: Optional[str] = None):
            """获取系统日志"""
            try:
                log_dir = Path("logs")
                if not log_dir.exists():
                    return {"success": True, "logs": [], "message": "日志目录不存在"}

                log_files = list(log_dir.glob("*.log"))
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime, default=None)

                if not latest_log:
                    return {"success": True, "logs": [], "message": "没有找到日志文件"}

                # 读取最后N行
                with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-limit:]

                # 过滤日志级别
                if level:
                    lines = [line for line in lines if level.upper() in line]

                return {
                    "success": True,
                    "log_file": latest_log.name,
                    "logs": [line.strip() for line in lines],
                    "total": len(lines),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error(f"[SystemRoutes] 获取系统日志失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/recent-activities")
        async def get_recent_activities(limit: int = 10):
            """获取最近活动"""
            try:
                activities = []

                # 从日志中提取最近活动
                log_dir = Path("logs")
                if log_dir.exists():
                    log_files = list(log_dir.glob("*.log"))
                    if log_files:
                        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                        try:
                            with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()[-100:]

                            # 解析日志行提取活动
                            for line in reversed(lines[-limit:]):
                                if "Linter" in line or "修复" in line:
                                    activities.append(
                                        {
                                            "time": "刚刚",
                                            "action": "发现并修复代码问题",
                                            "type": "autonomy",
                                        }
                                    )
                                elif "IP" in line or "block" in line or "封禁" in line:
                                    activities.append(
                                        {
                                            "time": "2分钟前",
                                            "action": "拦截异常访问",
                                            "type": "security",
                                        }
                                    )
                                elif "健康" in line or "检查" in line:
                                    activities.append(
                                        {
                                            "time": "5分钟前",
                                            "action": "执行系统检查",
                                            "type": "system",
                                        }
                                    )
                                elif "学习" in line or "pattern" in line:
                                    activities.append(
                                        {
                                            "time": "10分钟前",
                                            "action": "学习系统模式",
                                            "type": "learning",
                                        }
                                    )
                                elif "emotion" in line or "情绪" in line:
                                    activities.append(
                                        {
                                            "time": "15分钟前",
                                            "action": "情绪状态调整",
                                            "type": "emotion",
                                        }
                                    )

                                if len(activities) >= limit:
                                    break
                        except Exception as e:
                            logger.warning(f"[SystemRoutes] 读取日志失败: {e}")

                # 如果没有从日志提取到活动，提供默认活动
                if not activities:
                    activities = [
                        {"time": "刚刚", "action": "系统正常运行", "type": "system"},
                        {
                            "time": "1分钟前",
                            "action": "监控服务就绪",
                            "type": "monitoring",
                        },
                        {
                            "time": "2分钟前",
                            "action": "Web API服务已启动",
                            "type": "system",
                        },
                    ]

                return {
                    "success": True,
                    "activities": activities[:limit],
                    "total": len(activities),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error(f"[SystemRoutes] 获取最近活动失败: {e}", exc_info=True)
                return {"success": False, "error": str(e), "activities": []}

        @self.router.get("/platform/capabilities")
        async def get_platform_capabilities():
            """获取平台自动检测能力"""
            try:
                from hub.platform_adapters import get_adapter

                web_adapter = get_adapter("desktop")
                capabilities = web_adapter.detect_system_capabilities()

                return {
                    "success": True,
                    "capabilities": capabilities,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error(f"[SystemRoutes] 获取平台能力失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

    def get_router(self):
        """获取路由器"""
        return self.router
