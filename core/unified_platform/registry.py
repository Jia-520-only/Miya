"""
平台注册表 - 动态平台管理核心

取代 if-elif 链式调度，使用注册表模式：
  - 注册/注销平台（运行时动态）
  - 启动/停止单个平台
  - 批量启停
  - 状态查询
  - 事件广播
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type

from .base import BasePlatform
from .status import PlatformEvent, PlatformStatus

logger = logging.getLogger("Miya.PlatformRegistry")


class PlatformRegistry:
    """
    平台注册表

    Usage:
        registry = PlatformRegistry()
        registry.register(QQPlatform)
        await registry.start("qq")
        await registry.stop("qq")
        stats = registry.get_all_stats()
    """

    def __init__(self):
        self._platform_classes: Dict[str, Type[BasePlatform]] = {}
        self._instances: Dict[str, BasePlatform] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._broadcast_listeners: List[Callable[[Dict], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    # ==================== 注册 / 注销 ====================

    def register(
        self,
        platform_cls: Type[BasePlatform],
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        注册一个平台类型

        Args:
            platform_cls: BasePlatform 子类
            config: 该平台的配置
        """
        pid = platform_cls.platform_id
        if not pid:
            raise ValueError("platform_cls must define platform_id")

        self._platform_classes[pid] = platform_cls
        self._configs[pid] = config or {}
        logger.info(f"[Registry] 注册平台类型: {pid} ({platform_cls.platform_name})")

    def unregister(self, platform_id: str):
        """注销一个平台类型"""
        self._platform_classes.pop(platform_id, None)
        self._configs.pop(platform_id, None)
        logger.info(f"[Registry] 注销平台类型: {platform_id}")

    # ==================== 实例管理 ====================

    async def start(self, platform_id: str, miya_core=None) -> bool:
        """
        启动（连接）一个平台

        如果平台未实例化则先实例化，然后调用 connect()
        """
        async with self._lock:
            inst = self._instances.get(platform_id)
            if inst and inst.is_online:
                logger.info(f"[Registry] {platform_id} 已在线")
                return True

            # v8.1: 实例已预创建但未连接 (如 desktop/mobile 用 GenericPlatform)
            if inst:
                if miya_core and hasattr(inst, "set_miya_core"):
                    inst.set_miya_core(miya_core)
                return await inst.connect()

            cls = self._platform_classes.get(platform_id)
            if not cls:
                logger.error(f"[Registry] 未知平台: {platform_id}")
                return False

            config = self._configs.get(platform_id, {})
            inst = cls(config=config)
            inst.on(PlatformEvent.CONNECTED, self._on_platform_event)
            inst.on(PlatformEvent.DISCONNECTED, self._on_platform_event)
            inst.on(PlatformEvent.ERROR, self._on_platform_event)
            inst.on(PlatformEvent.RECONNECTING, self._on_platform_event)
            inst.on(PlatformEvent.RECONNECTED, self._on_platform_event)
            inst.on(PlatformEvent.RECONNECT_FAILED, self._on_platform_event)
            inst.on(PlatformEvent.SHUTDOWN, self._on_platform_event)
            self._instances[platform_id] = inst

            # 注入 Miya 核心引用（连接前，避免消息到达时核心未就绪）
            if miya_core and hasattr(inst, "set_miya_core"):
                inst.set_miya_core(miya_core)

            return await inst.connect()

    async def stop(self, platform_id: str) -> bool:
        """停止（断开）一个平台"""
        inst = self._instances.get(platform_id)
        if not inst:
            logger.warning(f"[Registry] {platform_id} 未实例化")
            return False
        return await inst.disconnect()

    async def restart(self, platform_id: str) -> bool:
        """重启一个平台"""
        inst = self._instances.get(platform_id)
        if not inst:
            return False
        return await inst.restart()

    async def remove(self, platform_id: str):
        """移除（断开并注销）一个平台实例"""
        inst = self._instances.pop(platform_id, None)
        if inst:
            await inst.shutdown()
        logger.info(f"[Registry] 移除平台: {platform_id}")

    # ==================== 批量操作 ====================

    async def start_all(
        self,
        platform_ids: Optional[List[str]] = None,
        miya_core=None,
        timeout: float = 30.0,
    ) -> Dict[str, bool]:
        """启动所有（或指定）平台 (v8.1: 包含预创建实例)

        timeout: 单个平台的连接超时（秒）。某个平台的连接卡住（网络不可达、上游
        API 超时等）时不再阻塞整个守护进程启动——该平台实例仍保留在注册表中，
        可稍后通过自身的后台重连机制或再次调用 start() 恢复。
        """
        ids = platform_ids or list(set(self._platform_classes.keys()) | set(self._instances.keys()))
        results = {}
        for pid in ids:
            try:
                if timeout and timeout > 0:
                    results[pid] = await asyncio.wait_for(
                        self.start(pid, miya_core=miya_core), timeout=timeout
                    )
                else:
                    results[pid] = await self.start(pid, miya_core=miya_core)
            except asyncio.TimeoutError:
                logger.warning(f"[Registry] 平台 {pid} 连接超时({timeout:.0f}s)，已跳过（后台重连可自行恢复）")
                results[pid] = False
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[Registry] 平台 {pid} 启动异常: {e}")
                results[pid] = False
        return results

    async def stop_all(self) -> Dict[str, bool]:
        """停止所有平台"""
        results = {}
        for pid in list(self._instances.keys()):
            results[pid] = await self.stop(pid)
        return results

    async def restart_all(self) -> Dict[str, bool]:
        """重启所有平台"""
        results = {}
        for pid in list(self._instances.keys()):
            results[pid] = await self.restart(pid)
        return results

    async def shutdown(self):
        """关闭所有平台并清理"""
        await self.stop_all()
        for pid in list(self._instances.keys()):
            await self.remove(pid)
        self._platform_classes.clear()
        self._configs.clear()

    # ==================== 查询 ====================

    def get(self, platform_id: str) -> Optional[BasePlatform]:
        """获取平台实例"""
        return self._instances.get(platform_id)

    def get_online_platforms(self) -> Dict[str, BasePlatform]:
        """获取所有在线平台"""
        return {k: v for k, v in self._instances.items() if v.is_online}

    def get_all_stats(self) -> List[Dict[str, Any]]:
        """获取所有平台统计信息"""
        stats = []
        seen = set()

        for pid, cls in self._platform_classes.items():
            seen.add(pid)
            inst = self._instances.get(pid)
            if inst:
                stats.append(inst.get_stats())
            else:
                if any(isinstance(i, cls) for i in self._instances.values()):
                    continue
                stats.append(
                    {
                        "platform_id": pid,
                        "platform_name": cls.platform_name,
                        "status": PlatformStatus.DISABLED.value,
                        "last_online": None,
                        "last_offline": None,
                        "last_error": None,
                        "error_count": 0,
                        "reconnect_count": 0,
                        "max_reconnect_attempts": 0,
                        "latency_ms": 0.0,
                        "message_count": 0,
                        "uptime_seconds": 0.0,
                    }
                )

        # v8.1: 包含直接存储在 _instances 中的平台 (如 desktop/mobile)
        for pid, inst in self._instances.items():
            if pid not in seen:
                stats.append(inst.get_stats())

        return stats

    def list_registered(self) -> List[Dict[str, str]]:
        """列出已注册的平台类型"""
        return [{"id": pid, "name": cls.platform_name} for pid, cls in self._platform_classes.items()]

    def list_active(self) -> List[str]:
        """列出所有已实例化且在线的平台 ID 列表（v8.1: 新增，修复阻断 Bug）"""
        return [pid for pid, inst in self._instances.items() if inst.is_online]

    def list_online_ids(self) -> List[str]:
        """list_active() 的显式别名"""
        return self.list_active()

    def supports_proactive(self, platform_id: str) -> bool:
        """检查平台是否支持主动消息"""
        inst = self._instances.get(platform_id)
        if inst and inst.is_online:
            return getattr(inst, "support_proactive_message", False)
        return False

    def proactive_capable_platforms(self) -> List[str]:
        """返回所有支持主动消息的在线平台 ID"""
        return [
            pid
            for pid, inst in self._instances.items()
            if inst.is_online and getattr(inst, "support_proactive_message", False)
        ]

    # ==================== 事件广播 ====================

    def on_broadcast(self, callback: Callable[[Dict], Awaitable[None]]):
        """注册广播监听器（接收所有平台事件）"""
        self._broadcast_listeners.append(callback)

    async def _on_platform_event(self, event: Dict):
        """平台事件 -> 广播"""
        for listener in self._broadcast_listeners:
            try:
                await listener(event)
            except Exception as e:
                logger.error(f"[Registry] 广播监听器异常: {e}")


# ==================== 全局单例 ====================

_global_registry: Optional[PlatformRegistry] = None


def get_registry() -> PlatformRegistry:
    """获取全局注册表单例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = PlatformRegistry()
    return _global_registry


# ==================== 装饰器 ====================


def register_platform(
    platform_id: str,
    platform_name: str = "",
    **kwargs,
):
    """
    装饰器：将类自动注册到全局注册表

    Usage:
        @register_platform("qq", "QQ")
        class QQPlatform(BasePlatform):
            ...
    """

    def decorator(cls: Type[BasePlatform]):
        cls.platform_id = platform_id
        cls.platform_name = platform_name or cls.__name__
        for k, v in kwargs.items():
            setattr(cls, k, v)
        get_registry().register(cls)
        return cls

    return decorator
