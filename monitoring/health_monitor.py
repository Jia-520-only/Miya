"""
系统健康监控

监控Redis、缓存、记忆系统的健康状态
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """健康检查"""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    details: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    last_error: Optional[Exception] = None


class HealthMonitor:
    """健康监控器"""
    
    def __init__(self, check_interval: float = 60.0):
        """初始化监控器
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self.check_interval = check_interval
        self.checks: Dict[str, Callable] = {}
        self.current_status: Dict[str, HealthCheck] = {}
        self.history: List[Dict] = []
        self.max_history = 100
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False
        self._callbacks: List[Callable] = []
    
    def register_check(self, name: str, check_func: Callable):
        """注册健康检查
        
        Args:
            name: 检查名称
            check_func: 检查函数，返回 (status: HealthStatus, message: str, details: Dict)
        """
        self.checks[name] = check_func
        logger.info(f"注册健康检查: {name}")
    
    def add_status_callback(self, callback: Callable):
        """添加状态变化回调
        
        Args:
            callback: 回调函数，接收 (name: str, status: HealthCheck)
        """
        self._callbacks.append(callback)
    
    async def run_check(self, name: str) -> HealthCheck:
        """运行单个健康检查
        
        Args:
            name: 检查名称
        
        Returns:
            健康检查结果
        """
        if name not in self.checks:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"未注册的检查: {name}"
            )
        
        start_time = time.time()
        health_check = HealthCheck(name=name)
        
        try:
            status, message, details = await self.checks[name]()
            health_check.status = status
            health_check.message = message
            health_check.details = details
            
            # 触发回调
            for callback in self._callbacks:
                try:
                    await callback(name, health_check)
                except Exception as e:
                    logger.error(f"状态回调失败: {e}")
        
        except Exception as e:
            health_check.status = HealthStatus.UNHEALTHY
            health_check.message = f"检查失败: {str(e)}"
            health_check.last_error = e
            logger.error(f"健康检查失败 {name}: {e}")
        
        health_check.duration_ms = (time.time() - start_time) * 1000
        return health_check
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """运行所有健康检查
        
        Returns:
            所有检查结果
        """
        results = {}
        
        for name in self.checks.keys():
            result = await self.run_check(name)
            results[name] = result
            self.current_status[name] = result
        
        # 记录历史
        self._record_history()
        
        return results
    
    def _record_history(self):
        """记录历史状态"""
        snapshot = {
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "duration_ms": check.duration_ms
                }
                for name, check in self.current_status.items()
            }
        }
        
        self.history.append(snapshot)
        
        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_overall_status(self) -> HealthStatus:
        """获取整体状态"""
        if not self.current_status:
            return HealthStatus.UNKNOWN
        
        statuses = [check.status for check in self.current_status.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.HEALTHY
    
    def get_summary(self) -> Dict:
        """获取状态摘要"""
        return {
            "overall_status": self.get_overall_status().value,
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "duration_ms": check.duration_ms,
                    "details": check.details
                }
                for name, check in self.current_status.items()
            },
            "history_count": len(self.history)
        }
    
    async def start_monitoring(self):
        """启动持续监控"""
        if self._monitoring:
            logger.warning("监控已在运行")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("健康监控已启动")
    
    async def stop_monitoring(self):
        """停止持续监控"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("健康监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                await self.run_all_checks()
                
                # 等待下一次检查
                await asyncio.sleep(self.check_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(5)


# 全局健康监控实例
_global_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """获取全局健康监控器"""
    global _global_health_monitor
    if _global_health_monitor is None:
        _global_health_monitor = HealthMonitor()
        _register_default_checks(_global_health_monitor)
    return _global_health_monitor


def _register_default_checks(monitor: HealthMonitor):
    """注册默认健康检查"""
    
    async def check_redis():
        """检查Redis"""
        try:
            from storage import get_redis_manager
            manager = get_redis_manager()
            
            if not manager.is_initialized:
                return HealthStatus.UNHEALTHY, "Redis未初始化", {}
            
            client = await manager.get_client()
            if client.is_mock:
                return HealthStatus.DEGRADED, "Redis运行在模拟模式", {"is_mock": True}
            
            stats = await client.get_stats()
            return HealthStatus.HEALTHY, "Redis运行正常", stats
        
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Redis检查失败: {str(e)}", {}
    
    async def check_cache():
        """检查缓存"""
        try:
            from core.unified_cache import get_cache
            cache = get_cache("health_check")
            
            # 测试缓存操作
            await cache.set("health_test", "test_value", ttl=10)
            value = await cache.get("health_test")
            
            if value != "test_value":
                return HealthStatus.UNHEALTHY, "缓存读写测试失败", {}
            
            stats = cache.get_stats()
            
            return HealthStatus.HEALTHY, "缓存运行正常", stats
        
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"缓存检查失败: {str(e)}", {}
    
    async def check_memory():
        """检查记忆系统"""
        try:
            from memory import get_memory_manager
            manager = get_memory_manager()
            
            # 测试记忆统计
            stats = await manager.get_memory_stats()
            
            return HealthStatus.HEALTHY, "记忆系统运行正常", stats
        
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"记忆系统检查失败: {str(e)}", {}
    
    # 注册检查
    monitor.register_check("redis", check_redis)
    monitor.register_check("cache", check_cache)
    monitor.register_check("memory", check_memory)


__all__ = [
    'HealthStatus',
    'HealthCheck',
    'HealthMonitor',
    'get_health_monitor',
]
