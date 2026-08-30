"""
健康检查和监控端点系统
"""

import asyncio
import contextlib
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""

    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级
    UNHEALTHY = "unhealthy"  # 不健康
    UNKNOWN = "unknown"  # 未知


class CheckType(Enum):
    """检查类型"""

    LIVENESS = "liveness"  # 存活检查
    READINESS = "readiness"  # 就绪检查
    STARTUP = "startup"  # 启动检查
    CUSTOM = "custom"  # 自定义检查


@dataclass
class HealthCheck:
    """健康检查"""

    name: str
    check_type: CheckType
    check_func: Callable[[], Union[bool, Dict[str, Any]]]
    timeout: float = 5.0
    interval: float = 30.0
    critical: bool = True
    tags: List[str] = field(default_factory=list)

    # 运行时状态
    last_check: Optional[float] = None
    last_result: Optional[bool] = None
    last_duration: float = 0.0
    failure_count: int = 0
    total_checks: int = 0


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    name: str
    status: bool
    message: str = ""
    duration: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemMetrics:
    """系统指标"""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    disk_usage_percent: float = 0.0
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    open_files: int = 0
    uptime: float = 0.0


@dataclass
class HealthReport:
    """健康报告"""

    status: HealthStatus
    timestamp: datetime = field(default_factory=datetime.now)
    checks: Dict[str, HealthCheckResult] = field(default_factory=dict)
    metrics: SystemMetrics = field(default_factory=SystemMetrics)
    version: str = "1.0.0"
    service: str = "miya-ai"
    environment: str = "production"

    @property
    def healthy(self) -> bool:
        """是否健康"""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "healthy": self.healthy,
            "checks": {
                name: {
                    "status": "healthy" if result.status else "unhealthy",
                    "message": result.message,
                    "duration": result.duration,
                    "timestamp": datetime.fromtimestamp(result.timestamp).isoformat(),
                    "data": result.data,
                }
                for name, result in self.checks.items()
            },
            "metrics": {
                "cpu_percent": self.metrics.cpu_percent,
                "memory_percent": self.metrics.memory_percent,
                "memory_used_mb": self.metrics.memory_used_mb,
                "memory_total_mb": self.metrics.memory_total_mb,
                "disk_usage_percent": self.metrics.disk_usage_percent,
                "disk_free_gb": self.metrics.disk_free_gb,
                "disk_total_gb": self.metrics.disk_total_gb,
                "network_sent_mb": self.metrics.network_sent_mb,
                "network_recv_mb": self.metrics.network_recv_mb,
                "process_count": self.metrics.process_count,
                "thread_count": self.metrics.thread_count,
                "open_files": self.metrics.open_files,
                "uptime": self.metrics.uptime,
            },
            "version": self.version,
            "service": self.service,
            "environment": self.environment,
        }


class HealthMonitor:
    """健康监视器"""

    def __init__(self, service_name: str = "miya-ai", environment: str = "production"):
        self.service_name = service_name
        self.environment = environment
        self.checks: Dict[str, HealthCheck] = {}
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = 100
        self._lock = threading.RLock()
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._start_time = time.time()

        # 注册默认检查
        self._register_default_checks()

        logger.info(f"健康监视器初始化完成: {service_name}")

    def _register_default_checks(self):
        """注册默认检查"""
        # 内存检查
        self.register_check(
            name="memory_usage",
            check_type=CheckType.LIVENESS,
            check_func=self._check_memory_usage,
            interval=10.0,
            critical=True,
        )

        # 磁盘空间检查
        self.register_check(
            name="disk_space",
            check_type=CheckType.LIVENESS,
            check_func=self._check_disk_space,
            interval=60.0,
            critical=True,
        )

        # 进程检查
        self.register_check(
            name="process_alive",
            check_type=CheckType.LIVENESS,
            check_func=self._check_process_alive,
            interval=5.0,
            critical=True,
        )

        # 网络连接检查
        self.register_check(
            name="network_connectivity",
            check_type=CheckType.READINESS,
            check_func=self._check_network_connectivity,
            interval=15.0,
            critical=False,
        )

    def register_check(
        self,
        name: str,
        check_type: CheckType,
        check_func: Callable[[], Union[bool, Dict[str, Any]]],
        timeout: float = 5.0,
        interval: float = 30.0,
        critical: bool = True,
        tags: Optional[List[str]] = None,
    ):
        """注册健康检查

        Args:
            name: 检查名称
            check_type: 检查类型
            check_func: 检查函数
            timeout: 超时时间
            interval: 检查间隔
            critical: 是否关键
            tags: 标签列表
        """
        with self._lock:
            if name in self.checks:
                logger.warning(f"健康检查已存在: {name}")
                return

            check = HealthCheck(
                name=name,
                check_type=check_type,
                check_func=check_func,
                timeout=timeout,
                interval=interval,
                critical=critical,
                tags=tags or [],
            )

            self.checks[name] = check
            logger.info(f"已注册健康检查: {name} ({check_type.value})")

    def unregister_check(self, name: str):
        """取消注册健康检查"""
        with self._lock:
            if name in self.checks:
                del self.checks[name]
                logger.info(f"已取消注册健康检查: {name}")

    async def run_check(self, name: str) -> HealthCheckResult:
        """运行单个检查

        Args:
            name: 检查名称

        Returns:
            检查结果
        """
        with self._lock:
            check = self.checks.get(name)
            if not check:
                return HealthCheckResult(name=name, status=False, message=f"检查未找到: {name}", duration=0.0)

        start_time = time.time()

        try:
            # 运行检查函数（带超时）
            result = await asyncio.wait_for(asyncio.to_thread(check.check_func), timeout=check.timeout)

            duration = time.time() - start_time

            if isinstance(result, dict):
                # 检查函数返回了详细结果
                status = result.get("status", False)
                message = result.get("message", "检查通过")
                data = result.get("data", {})
            else:
                # 检查函数返回了布尔值
                status = bool(result)
                message = "检查通过" if status else "检查失败"
                data = {}

            # 更新检查状态
            with self._lock:
                check.last_check = time.time()
                check.last_result = status
                check.last_duration = duration
                check.total_checks += 1

                if not status:
                    check.failure_count += 1
                else:
                    check.failure_count = 0

            return HealthCheckResult(
                name=name, status=status, message=message, duration=duration, data=data, timestamp=time.time()
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time

            with self._lock:
                check.last_check = time.time()
                check.last_result = False
                check.last_duration = duration
                check.total_checks += 1
                check.failure_count += 1

            return HealthCheckResult(
                name=name,
                status=False,
                message=f"检查超时 ({check.timeout} 秒)",
                duration=duration,
                timestamp=time.time(),
            )

        except Exception as e:
            duration = time.time() - start_time

            with self._lock:
                check.last_check = time.time()
                check.last_result = False
                check.last_duration = duration
                check.total_checks += 1
                check.failure_count += 1

            logger.error(f"健康检查执行失败: {name} - {e}")

            return HealthCheckResult(
                name=name, status=False, message=f"检查异常: {str(e)}", duration=duration, timestamp=time.time()
            )

    async def run_checks(
        self, check_type: Optional[CheckType] = None, tags: Optional[List[str]] = None
    ) -> HealthReport:
        """运行所有检查

        Args:
            check_type: 检查类型筛选
            tags: 标签筛选

        Returns:
            健康报告
        """
        with self._lock:
            # 筛选检查
            checks_to_run = []
            for check in self.checks.values():
                if check_type and check.check_type != check_type:
                    continue

                if tags and not any(tag in check.tags for tag in tags):
                    continue

                # 检查是否需要运行（基于间隔）
                if check.last_check and (time.time() - check.last_check) < check.interval:
                    continue

                checks_to_run.append(check.name)

        # 并发运行检查
        tasks = [self.run_check(name) for name in checks_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        check_results = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = checks_to_run[i]
                check_results[name] = HealthCheckResult(
                    name=name, status=False, message=f"检查异常: {str(result)}", duration=0.0, timestamp=time.time()
                )
            else:
                check_results[result.name] = result

        # 收集系统指标
        metrics = await self._collect_system_metrics()

        # 确定整体状态
        status = self._determine_overall_status(check_results)

        return HealthReport(
            status=status,
            checks=check_results,
            metrics=metrics,
            version=self._get_version(),
            service=self.service_name,
            environment=self.environment,
        )

    def _determine_overall_status(self, check_results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """确定整体状态"""
        if not check_results:
            return HealthStatus.UNKNOWN

        critical_failures = []
        non_critical_failures = []

        for name, result in check_results.items():
            with self._lock:
                check = self.checks.get(name)
                if not check:
                    continue

                if not result.status:
                    if check.critical:
                        critical_failures.append(name)
                    else:
                        non_critical_failures.append(name)

        if critical_failures:
            return HealthStatus.UNHEALTHY
        elif non_critical_failures:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / 1024 / 1024
            memory_total_mb = memory.total / 1024 / 1024

            # 磁盘使用率
            disk = psutil.disk_usage("/")
            disk_usage_percent = disk.percent
            disk_free_gb = disk.free / 1024 / 1024 / 1024
            disk_total_gb = disk.total / 1024 / 1024 / 1024

            # 网络使用率
            net_io = psutil.net_io_counters()
            network_sent_mb = net_io.bytes_sent / 1024 / 1024
            network_recv_mb = net_io.bytes_recv / 1024 / 1024

            # 进程信息
            process = psutil.Process()
            process_count = len(psutil.pids())
            thread_count = process.num_threads()

            # 打开文件数
            try:
                open_files = len(process.open_files())
            except (psutil.AccessDenied, psutil.ZombieProcess):
                open_files = 0

            # 运行时间
            uptime = time.time() - self._start_time

            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_total_mb=memory_total_mb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                disk_total_gb=disk_total_gb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                process_count=process_count,
                thread_count=thread_count,
                open_files=open_files,
                uptime=uptime,
            )

        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
            return SystemMetrics()

    def _get_version(self) -> str:
        """获取版本号"""
        try:
            # 尝试从pyproject.toml获取版本
            import tomli

            with open("pyproject.toml", "rb") as f:
                config = tomli.load(f)
                return config.get("project", {}).get("version", "1.0.0")
        except Exception:
            return "1.0.0"

    # 默认检查函数
    def _check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用率"""
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        status = memory_percent < 90  # 小于90%为健康

        return {
            "status": status,
            "message": f"内存使用率: {memory_percent:.1f}%",
            "data": {
                "memory_percent": memory_percent,
                "memory_used_mb": memory.used / 1024 / 1024,
                "memory_total_mb": memory.total / 1024 / 1024,
                "threshold": 90.0,
            },
        }

    def _check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间"""
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent

        status = disk_percent < 85  # 小于85%为健康

        return {
            "status": status,
            "message": f"磁盘使用率: {disk_percent:.1f}%",
            "data": {
                "disk_percent": disk_percent,
                "disk_free_gb": disk.free / 1024 / 1024 / 1024,
                "disk_total_gb": disk.total / 1024 / 1024 / 1024,
                "threshold": 85.0,
            },
        }

    def _check_process_alive(self) -> Dict[str, Any]:
        """检查进程是否存活"""
        try:
            process = psutil.Process()
            status = process.is_running()

            return {
                "status": status,
                "message": "进程正常运行" if status else "进程已终止",
                "data": {"pid": process.pid, "name": process.name(), "status": process.status()},
            }
        except psutil.NoSuchProcess:
            return {"status": False, "message": "进程不存在", "data": {}}

    def _check_network_connectivity(self) -> Dict[str, Any]:
        """检查网络连接性"""
        try:
            # 测试连接性
            socket.create_connection(("8.8.8.8", 53), timeout=3)

            return {"status": True, "message": "网络连接正常", "data": {"test_host": "8.8.8.8", "test_port": 53}}
        except Exception as e:
            return {
                "status": False,
                "message": f"网络连接失败: {str(e)}",
                "data": {"test_host": "8.8.8.8", "test_port": 53, "error": str(e)},
            }

    async def start(self):
        """启动健康监视器"""
        if self._running:
            logger.warning("健康监视器已在运行")
            return

        self._running = True

        async def check_loop():
            while self._running:
                try:
                    # 运行所有检查
                    report = await self.run_checks()

                    # 记录指标历史
                    with self._lock:
                        self.metrics_history.append(report.metrics)
                        if len(self.metrics_history) > self.max_history_size:
                            self.metrics_history.pop(0)

                    # 如果有不健康的检查，记录警告
                    if not report.healthy:
                        unhealthy_checks = [name for name, result in report.checks.items() if not result.status]
                        logger.warning(f"健康检查失败: {', '.join(unhealthy_checks)}")

                    # 等待下一次检查
                    await asyncio.sleep(10.0)  # 每10秒检查一次

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"健康检查循环错误: {e}")
                    await asyncio.sleep(5.0)

        async def metrics_loop():
            while self._running:
                try:
                    # 收集系统指标
                    metrics = await self._collect_system_metrics()

                    # 记录指标历史
                    with self._lock:
                        self.metrics_history.append(metrics)
                        if len(self.metrics_history) > self.max_history_size:
                            self.metrics_history.pop(0)

                    # 检查系统资源
                    if metrics.memory_percent > 90:
                        logger.warning(f"内存使用率过高: {metrics.memory_percent:.1f}%")

                    if metrics.disk_usage_percent > 85:
                        logger.warning(f"磁盘使用率过高: {metrics.disk_usage_percent:.1f}%")

                    # 等待下一次收集
                    await asyncio.sleep(30.0)  # 每30秒收集一次

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"指标收集循环错误: {e}")
                    await asyncio.sleep(10.0)

        self._check_task = asyncio.create_task(check_loop())
        self._metrics_task = asyncio.create_task(metrics_loop())

        logger.info("健康监视器已启动")

    async def stop(self):
        """停止健康监视器"""
        self._running = False

        if self._check_task:
            self._check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._check_task

        if self._metrics_task:
            self._metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._metrics_task

        logger.info("健康监视器已停止")

    def get_metrics_history(self) -> List[SystemMetrics]:
        """获取指标历史"""
        with self._lock:
            return self.metrics_history.copy()

    def get_check_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取检查状态"""
        with self._lock:
            check = self.checks.get(name)
            if not check:
                return None

            return {
                "name": check.name,
                "type": check.check_type.value,
                "last_check": check.last_check,
                "last_result": check.last_result,
                "last_duration": check.last_duration,
                "total_checks": check.total_checks,
                "failure_count": check.failure_count,
                "critical": check.critical,
                "tags": check.tags,
            }


# 全局健康监视器实例
_global_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """获取全局健康监视器实例"""
    global _global_health_monitor
    if _global_health_monitor is None:
        _global_health_monitor = HealthMonitor()
    return _global_health_monitor


async def start_health_monitoring():
    """启动全局健康监控"""
    monitor = get_health_monitor()
    await monitor.start()


async def stop_health_monitoring():
    """停止全局健康监控"""
    monitor = get_health_monitor()
    await monitor.stop()


# FastAPI 集成端点
try:
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.responses import JSONResponse

    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/")
    async def health_check():
        """健康检查端点"""
        monitor = get_health_monitor()
        report = await monitor.run_checks()

        status_code = 200 if report.healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)

    @router.get("/liveness")
    async def liveness_check():
        """存活检查端点"""
        monitor = get_health_monitor()
        report = await monitor.run_checks(check_type=CheckType.LIVENESS)

        status_code = 200 if report.healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)

    @router.get("/readiness")
    async def readiness_check():
        """就绪检查端点"""
        monitor = get_health_monitor()
        report = await monitor.run_checks(check_type=CheckType.READINESS)

        status_code = 200 if report.healthy else 503
        return JSONResponse(content=report.to_dict(), status_code=status_code)

    @router.get("/metrics")
    async def get_metrics():
        """获取系统指标"""
        monitor = get_health_monitor()
        metrics = await monitor._collect_system_metrics()

        return {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "memory_used_mb": metrics.memory_used_mb,
            "memory_total_mb": metrics.memory_total_mb,
            "disk_usage_percent": metrics.disk_usage_percent,
            "disk_free_gb": metrics.disk_free_gb,
            "disk_total_gb": metrics.disk_total_gb,
            "network_sent_mb": metrics.network_sent_mb,
            "network_recv_mb": metrics.network_recv_mb,
            "process_count": metrics.process_count,
            "thread_count": metrics.thread_count,
            "open_files": metrics.open_files,
            "uptime": metrics.uptime,
        }

    @router.get("/checks")
    async def list_checks():
        """列出所有检查"""
        monitor = get_health_monitor()

        checks = []
        for check in monitor.checks.values():
            checks.append(
                {
                    "name": check.name,
                    "type": check.check_type.value,
                    "critical": check.critical,
                    "tags": check.tags,
                    "interval": check.interval,
                    "timeout": check.timeout,
                }
            )

        return {"checks": checks}

    @router.get("/checks/{check_name}")
    async def get_check_status(check_name: str):
        """获取检查状态"""
        monitor = get_health_monitor()
        status = monitor.get_check_status(check_name)

        if not status:
            raise HTTPException(status_code=404, detail="检查未找到")

        return status

    @router.get("/history")
    async def get_metrics_history(limit: int = 10):
        """获取指标历史"""
        monitor = get_health_monitor()
        history = monitor.get_metrics_history()

        if limit > 0:
            history = history[-limit:]

        return {
            "history": [
                {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "disk_usage_percent": metrics.disk_usage_percent,
                    "timestamp": datetime.now().isoformat(),
                }
                for metrics in history
            ]
        }

except ImportError:
    logger.warning("FastAPI未安装，健康检查端点不可用")
    router = None
