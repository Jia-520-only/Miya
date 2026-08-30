"""
内存管理和资源清理系统
"""

import asyncio
import contextlib
import gc
import linecache
import logging
import sys
import threading
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """资源类型"""

    MEMORY = "memory"  # 内存
    FILE = "file"  # 文件
    NETWORK = "network"  # 网络连接
    DATABASE = "database"  # 数据库连接
    THREAD = "thread"  # 线程
    PROCESS = "process"  # 进程
    CACHE = "cache"  # 缓存
    SESSION = "session"  # 会话


class ResourceState(Enum):
    """资源状态"""

    ACTIVE = "active"  # 活跃
    IDLE = "idle"  # 空闲
    LEAKING = "leaking"  # 泄漏
    CLOSED = "closed"  # 已关闭


@dataclass
class ResourceInfo:
    """资源信息"""

    resource_id: str
    resource_type: ResourceType
    state: ResourceState
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    size_bytes: int = 0
    reference_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    cleanup_func: Optional[Callable[[], None]] = None


@dataclass
class MemorySnapshot:
    """内存快照"""

    timestamp: float = field(default_factory=time.time)
    total_memory: int = 0
    used_memory: int = 0
    free_memory: int = 0
    memory_percent: float = 0.0
    object_count: int = 0
    gc_collected: int = 0
    gc_uncollectable: int = 0
    top_objects: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LeakDetection:
    """泄漏检测"""

    resource_id: str
    resource_type: ResourceType
    leak_size: int
    duration: float
    suspected_cause: str
    traceback: List[str] = field(default_factory=list)


class ResourceManager:
    """资源管理器"""

    def __init__(self):
        self.resources: Dict[str, ResourceInfo] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 60.0  # 清理间隔（秒）
        self._leak_detection_interval = 300.0  # 泄漏检测间隔（秒）
        self._max_idle_time = 300.0  # 最大空闲时间（秒）
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._memory_snapshots: List[MemorySnapshot] = []
        self._max_snapshots = 50
        self._leaks_detected: List[LeakDetection] = []

        # 启用内存跟踪
        tracemalloc.start()

        # 设置弱引用回调
        self._finalizers: Dict[str, Callable] = {}

        logger.info("资源管理器初始化完成")

    def register_resource(
        self,
        resource_id: str,
        resource_type: ResourceType,
        size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        cleanup_func: Optional[Callable[[], None]] = None,
    ) -> str:
        """注册资源

        Args:
            resource_id: 资源ID
            resource_type: 资源类型
            size_bytes: 资源大小（字节）
            metadata: 元数据
            cleanup_func: 清理函数

        Returns:
            资源ID
        """
        with self._lock:
            if resource_id in self.resources:
                logger.warning(f"资源已存在: {resource_id}")
                return resource_id

            resource = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                state=ResourceState.ACTIVE,
                size_bytes=size_bytes,
                metadata=metadata or {},
                cleanup_func=cleanup_func,
            )

            self.resources[resource_id] = resource

            # 如果是对象，设置弱引用
            if resource_type == ResourceType.MEMORY:
                self._setup_weak_reference(resource_id)

            logger.debug(f"已注册资源: {resource_id} ({resource_type.value})")
            return resource_id

    def _setup_weak_reference(self, resource_id: str):
        """设置弱引用"""

        def finalize(ref):
            with self._lock:
                if resource_id in self.resources:
                    resource = self.resources[resource_id]
                    resource.state = ResourceState.CLOSED
                    resource.reference_count = 0
                    logger.debug(f"资源已被垃圾回收: {resource_id}")

        # 这里需要实际的对象引用，简化处理
        self._finalizers[resource_id] = finalize

    def update_resource_state(self, resource_id: str, state: ResourceState):
        """更新资源状态"""
        with self._lock:
            if resource_id in self.resources:
                resource = self.resources[resource_id]
                resource.state = state
                resource.last_used = time.time()
                logger.debug(f"更新资源状态: {resource_id} -> {state.value}")

    def update_resource_size(self, resource_id: str, size_bytes: int):
        """更新资源大小"""
        with self._lock:
            if resource_id in self.resources:
                resource = self.resources[resource_id]
                resource.size_bytes = size_bytes
                logger.debug(f"更新资源大小: {resource_id} -> {size_bytes} bytes")

    def unregister_resource(self, resource_id: str) -> bool:
        """注销资源

        Args:
            resource_id: 资源ID

        Returns:
            是否成功注销
        """
        with self._lock:
            if resource_id not in self.resources:
                logger.warning(f"资源不存在: {resource_id}")
                return False

            resource = self.resources[resource_id]

            # 执行清理函数
            if resource.cleanup_func:
                try:
                    resource.cleanup_func()
                except Exception as e:
                    logger.error(f"资源清理函数执行失败: {resource_id} - {e}")

            # 更新状态
            resource.state = ResourceState.CLOSED

            # 从弱引用中移除
            if resource_id in self._finalizers:
                del self._finalizers[resource_id]

            # 从资源列表中移除
            del self.resources[resource_id]

            logger.info(f"已注销资源: {resource_id}")
            return True

    async def cleanup_idle_resources(self):
        """清理空闲资源"""
        with self._lock:
            now = time.time()
            resources_to_cleanup = []

            for resource_id, resource in self.resources.items():
                if resource.state == ResourceState.IDLE:
                    idle_time = now - resource.last_used
                    if idle_time > self._max_idle_time:
                        resources_to_cleanup.append(resource_id)

            for resource_id in resources_to_cleanup:
                logger.info(f"清理空闲资源: {resource_id} (空闲 {now - self.resources[resource_id].last_used:.1f} 秒)")
                self.unregister_resource(resource_id)

    async def detect_memory_leaks(self) -> List[LeakDetection]:
        """检测内存泄漏"""
        leaks = []

        # 获取当前内存快照
        current_snapshot = await self._take_memory_snapshot()
        self._memory_snapshots.append(current_snapshot)

        if len(self._memory_snapshots) > self._max_snapshots:
            self._memory_snapshots.pop(0)

        # 如果有多个快照，比较它们
        if len(self._memory_snapshots) >= 2:
            prev_snapshot = self._memory_snapshots[-2]
            current_snapshot = self._memory_snapshots[-1]

            memory_growth = current_snapshot.used_memory - prev_snapshot.used_memory
            time_diff = current_snapshot.timestamp - prev_snapshot.timestamp

            if memory_growth > 10 * 1024 * 1024:  # 10MB增长
                leak = LeakDetection(
                    resource_id="memory_growth",
                    resource_type=ResourceType.MEMORY,
                    leak_size=memory_growth,
                    duration=time_diff,
                    suspected_cause="持续内存增长",
                    traceback=self._get_memory_traceback(),
                )
                leaks.append(leak)

                logger.warning(f"检测到内存泄漏: 增长 {memory_growth / 1024 / 1024:.1f}MB 在 {time_diff:.1f} 秒内")

        # 检查资源泄漏
        with self._lock:
            for resource_id, resource in self.resources.items():
                if resource.state == ResourceState.LEAKING:
                    leak = LeakDetection(
                        resource_id=resource_id,
                        resource_type=resource.resource_type,
                        leak_size=resource.size_bytes,
                        duration=time.time() - resource.created_at,
                        suspected_cause="资源状态标记为泄漏",
                        traceback=[],
                    )
                    leaks.append(leak)

        self._leaks_detected.extend(leaks)
        return leaks

    async def _take_memory_snapshot(self) -> MemorySnapshot:
        """获取内存快照"""
        # 获取系统内存信息
        memory = psutil.virtual_memory()

        # 获取Python内存信息
        gc.collect()
        gc_info = gc.get_stats()

        # 获取对象计数
        object_count = len(gc.get_objects())

        # 获取内存分配跟踪
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")[:10]

        top_objects = []
        for stat in top_stats:
            top_objects.append(
                {
                    "file": stat.traceback[0].filename if stat.traceback else "unknown",
                    "line": stat.traceback[0].lineno if stat.traceback else 0,
                    "size": stat.size,
                    "count": stat.count,
                }
            )

        return MemorySnapshot(
            total_memory=memory.total,
            used_memory=memory.used,
            free_memory=memory.free,
            memory_percent=memory.percent,
            object_count=object_count,
            gc_collected=sum(gc["collected"] for gc in gc_info),
            gc_uncollectable=sum(gc["uncollectable"] for gc in gc_info),
            top_objects=top_objects,
        )

    def _get_memory_traceback(self) -> List[str]:
        """获取内存分配跟踪"""
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("traceback")[:5]

        tracebacks = []
        for stat in top_stats:
            tb = []
            for frame in stat.traceback:
                tb.append(f"{frame.filename}:{frame.lineno}")
            tracebacks.append("\n".join(tb))

        return tracebacks

    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源统计"""
        with self._lock:
            stats_by_type = defaultdict(lambda: {"count": 0, "total_size": 0, "active": 0, "idle": 0, "leaking": 0})

            total_size = 0
            for resource in self.resources.values():
                type_stats = stats_by_type[resource.resource_type.value]
                type_stats["count"] += 1
                type_stats["total_size"] += resource.size_bytes
                type_stats[resource.state.value] += 1
                total_size += resource.size_bytes

            return {
                "total_resources": len(self.resources),
                "total_size_bytes": total_size,
                "by_type": dict(stats_by_type),
                "leaks_detected": len(self._leaks_detected),
            }

    async def force_garbage_collection(self):
        """强制垃圾回收"""
        logger.info("执行强制垃圾回收")

        # 记录回收前的对象数量
        before_count = len(gc.get_objects())

        # 执行垃圾回收
        collected = gc.collect()

        # 记录回收后的对象数量
        after_count = len(gc.get_objects())

        logger.info(f"垃圾回收完成: 回收 {collected} 个对象, 对象数量从 {before_count} 减少到 {after_count}")

    async def cleanup_unused_resources(self):
        """清理未使用的资源"""
        logger.info("清理未使用的资源")

        # 清理空闲资源
        await self.cleanup_idle_resources()

        # 强制垃圾回收
        await self.force_garbage_collection()

        # 清理导入的模块缓存
        self._cleanup_module_cache()

        # 清理行缓存
        linecache.clearcache()

    def _cleanup_module_cache(self):
        """清理模块缓存"""
        # 清理sys.modules中的一些临时模块
        modules_to_remove = []
        for name, _module in sys.modules.items():
            if name.startswith("_temp_") or name.startswith("tmp_"):
                modules_to_remove.append(name)

        for name in modules_to_remove:
            del sys.modules[name]

        if modules_to_remove:
            logger.debug(f"清理了 {len(modules_to_remove)} 个临时模块")

    async def monitor_resources(self):
        """监控资源"""
        while self._running:
            try:
                # 检测内存泄漏
                leaks = await self.detect_memory_leaks()
                if leaks:
                    for leak in leaks:
                        logger.warning(
                            f"资源泄漏: {leak.resource_id} ({leak.resource_type.value}) - {leak.leak_size} bytes"
                        )

                # 获取资源统计
                stats = self.get_resource_stats()
                if stats["total_size_bytes"] > 100 * 1024 * 1024:  # 100MB
                    logger.warning(f"资源使用过高: {stats['total_size_bytes'] / 1024 / 1024:.1f}MB")

                # 等待下一次监控
                await asyncio.sleep(self._leak_detection_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"资源监控错误: {e}")
                await asyncio.sleep(10.0)

    async def start(self):
        """启动资源管理器"""
        if self._running:
            logger.warning("资源管理器已在运行")
            return

        self._running = True

        async def cleanup_loop():
            while self._running:
                try:
                    await self.cleanup_unused_resources()
                    await asyncio.sleep(self._cleanup_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"资源清理循环错误: {e}")
                    await asyncio.sleep(10.0)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        self._monitor_task = asyncio.create_task(self.monitor_resources())

        logger.info("资源管理器已启动")

    async def stop(self):
        """停止资源管理器"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task

        # 清理所有资源
        with self._lock:
            resource_ids = list(self.resources.keys())
            for resource_id in resource_ids:
                self.unregister_resource(resource_id)

        # 停止内存跟踪
        tracemalloc.stop()

        logger.info("资源管理器已停止")

    def __enter__(self):
        """上下文管理器入口"""
        asyncio.create_task(self.start())
        return self

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        asyncio.run(self.stop())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()


# 装饰器
def managed_resource(resource_type: ResourceType):
    """资源管理装饰器"""

    def decorator(func):
        resource_manager = _global_resource_manager

        def sync_wrapper(*args, **kwargs):
            resource_id = f"{func.__module__}.{func.__name__}"

            # 注册资源
            resource_manager.register_resource(
                resource_id=resource_id, resource_type=resource_type, metadata={"function": func.__name__}
            )

            try:
                # 执行函数
                result = func(*args, **kwargs)

                # 更新资源状态
                resource_manager.update_resource_state(resource_id, ResourceState.IDLE)

                return result

            except Exception as e:
                # 标记资源为泄漏
                resource_manager.update_resource_state(resource_id, ResourceState.LEAKING)
                raise e

        async def async_wrapper(*args, **kwargs):
            resource_id = f"{func.__module__}.{func.__name__}"

            # 注册资源
            resource_manager.register_resource(
                resource_id=resource_id, resource_type=resource_type, metadata={"function": func.__name__}
            )

            try:
                # 执行函数
                result = await func(*args, **kwargs)

                # 更新资源状态
                resource_manager.update_resource_state(resource_id, ResourceState.IDLE)

                return result

            except Exception as e:
                # 标记资源为泄漏
                resource_manager.update_resource_state(resource_id, ResourceState.LEAKING)
                raise e

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def cleanup_resources(func):
    """清理资源装饰器"""

    def sync_wrapper(*args, **kwargs):
        resource_manager = _global_resource_manager

        try:
            result = func(*args, **kwargs)

            # 执行资源清理
            asyncio.create_task(resource_manager.cleanup_unused_resources())

            return result

        except Exception as e:
            raise e

    async def async_wrapper(*args, **kwargs):
        resource_manager = _global_resource_manager

        try:
            result = await func(*args, **kwargs)

            # 执行资源清理
            await resource_manager.cleanup_unused_resources()

            return result

        except Exception as e:
            raise e

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# 全局资源管理器实例
_global_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """获取全局资源管理器实例"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager


async def start_resource_management():
    """启动全局资源管理"""
    manager = get_resource_manager()
    await manager.start()


async def stop_resource_management():
    """停止全局资源管理"""
    manager = get_resource_manager()
    await manager.stop()


async def cleanup_all_resources():
    """清理所有资源"""
    manager = get_resource_manager()
    await manager.cleanup_unused_resources()


def get_memory_info() -> Dict[str, Any]:
    """获取内存信息"""
    import gc

    import psutil

    process = psutil.Process()
    memory_info = process.memory_info()

    gc.collect()
    gc_stats = gc.get_stats()

    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
        "gc_objects": len(gc.get_objects()),
        "gc_collected": sum(gc["collected"] for gc in gc_stats),
        "gc_uncollectable": sum(gc["uncollectable"] for gc in gc_stats),
        "gc_threshold": gc.get_threshold(),
    }


# FastAPI 集成端点
try:
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.responses import JSONResponse

    router = APIRouter(prefix="/resources", tags=["resources"])

    @router.get("/stats")
    async def get_resource_stats():
        """获取资源统计"""
        manager = get_resource_manager()
        stats = manager.get_resource_stats()

        # 添加内存信息
        memory_info = get_memory_info()
        stats["memory_info"] = memory_info

        return stats

    @router.post("/cleanup")
    async def cleanup_resources_endpoint(force_gc: bool = False):
        """清理资源"""
        manager = get_resource_manager()

        if force_gc:
            await manager.force_garbage_collection()

        await manager.cleanup_unused_resources()

        return {"message": "资源清理完成"}

    @router.get("/leaks")
    async def get_detected_leaks():
        """获取检测到的泄漏"""
        manager = get_resource_manager()
        leaks = manager._leaks_detected

        return {
            "leaks": [
                {
                    "resource_id": leak.resource_id,
                    "resource_type": leak.resource_type.value,
                    "leak_size": leak.leak_size,
                    "duration": leak.duration,
                    "suspected_cause": leak.suspected_cause,
                }
                for leak in leaks
            ],
            "total_leaks": len(leaks),
        }

    @router.get("/memory")
    async def get_memory_usage():
        """获取内存使用情况"""
        memory_info = get_memory_info()

        # 获取系统内存
        import psutil

        system_memory = psutil.virtual_memory()

        return {
            "process_memory": memory_info,
            "system_memory": {
                "total_mb": system_memory.total / 1024 / 1024,
                "available_mb": system_memory.available / 1024 / 1024,
                "percent": system_memory.percent,
                "used_mb": system_memory.used / 1024 / 1024,
                "free_mb": system_memory.free / 1024 / 1024,
            },
        }

except ImportError:
    logger.warning("FastAPI未安装，资源管理端点不可用")
    router = None
