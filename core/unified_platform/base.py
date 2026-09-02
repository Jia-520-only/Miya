"""
统一平台基类

所有平台接入的抽象基类。定义完整的生命周期：
  register → connect → run → health_check → disconnect → unregister

平台实现者只需继承此类并实现核心方法即可自动获得：
  - 状态管理
  - 健康检查
  - 自动重连
  - 事件通知
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

from .reconnect import ExponentialBackoffPolicy, ReconnectPolicy, run_reconnect_loop
from .status import PlatformEvent, PlatformHealth, PlatformStatus

logger = logging.getLogger("Miya.UnifiedPlatform")


class BasePlatform(ABC):
    """
    统一平台基类

    子类需要实现：
    - platform_id: str      平台唯一标识
    - platform_name: str    平台显示名称
    - _do_connect()         执行实际连接
    - _do_disconnect()      执行实际断开
    - _do_health_check()    执行健康检查

    可选覆写：
    - _on_message()         处理接收到的消息
    - _do_start()           平台启动后的初始化
    - _do_stop()            平台停止前的清理
    """

    # ---- 子类必须定义 ----
    platform_id: str = ""
    platform_name: str = ""

    # ---- 可选覆写 ----
    reconnect_policy: Optional[ReconnectPolicy] = None
    health_check_interval: float = 30.0
    auto_reconnect: bool = True
    support_proactive_message: bool = True  # v8.1: 默认支持主动消息（有 send_private_message 即视为支持）

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._health = PlatformHealth()
        self._health.status = PlatformStatus.DISABLED
        self._health.max_reconnect_attempts = self.reconnect_policy.max_attempts if self.reconnect_policy else 10

        self._event_listeners: Dict[PlatformEvent, list[Callable]] = {e: [] for e in PlatformEvent}
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()

        if self.reconnect_policy is None and self.auto_reconnect:
            self.reconnect_policy = ExponentialBackoffPolicy()

        if not self.platform_id:
            self.platform_id = self.__class__.__name__.lower()

        if not self.platform_name:
            self.platform_name = self.platform_id

    # ==================== 生命周期 ====================

    async def connect(self) -> bool:
        """连接到平台（外部调用入口）"""
        async with self._lock:
            if self._health.status == PlatformStatus.ONLINE:
                logger.info(f"[{self.platform_id}] 已在线，跳过连接")
                return True

            self._set_status(PlatformStatus.CONNECTING)
            await self._emit(PlatformEvent.CONNECTING, {})

            try:
                success = await self._do_connect()
                if success:
                    self._health.status = PlatformStatus.ONLINE
                    self._health.last_online = datetime.now()
                    self._health.reconnect_count = 0
                    self._health.error_count = 0
                    self._health.last_error = None
                    self._set_status(PlatformStatus.ONLINE)
                    await self._emit(PlatformEvent.CONNECTED, {})
                    await self._do_start()

                    if self.health_check_interval > 0:
                        self._tasks.append(asyncio.create_task(self._health_check_loop()))
                    return True
                else:
                    self._set_status(PlatformStatus.ERROR)
                    self._health.last_error = "_do_connect 返回 False"
                    await self._emit(PlatformEvent.ERROR, {"error": "connect returned False"})
                    return False

            except Exception as e:
                self._set_status(PlatformStatus.ERROR)
                self._health.last_error = str(e)
                self._health.error_count += 1
                await self._emit(PlatformEvent.ERROR, {"error": str(e)})
                logger.error(f"[{self.platform_id}] 连接异常: {e}")

                if self.auto_reconnect and self.reconnect_policy:
                    return await self._reconnect()
                return False

    async def disconnect(self) -> bool:
        """断开平台连接"""
        async with self._lock:
            if self._health.status in (PlatformStatus.OFFLINE, PlatformStatus.DISABLED):
                return True

            self._set_status(PlatformStatus.OFFLINE)
            await self._cancel_tasks()
            await self._do_stop()

            try:
                await self._do_disconnect()
            except Exception as e:
                logger.warning(f"[{self.platform_id}] 断开异常: {e}")

            self._health.last_offline = datetime.now()
            await self._emit(PlatformEvent.DISCONNECTED, {})
            return True

    async def restart(self) -> bool:
        """重启平台连接"""
        await self.disconnect()
        await asyncio.sleep(1)
        return await self.connect()

    async def shutdown(self):
        """关闭平台 (注销前调用)"""
        await self.disconnect()
        self._set_status(PlatformStatus.DISABLED)
        await self._emit(PlatformEvent.SHUTDOWN, {})

    # ==================== 内部连接流程 ====================

    async def _reconnect(self) -> bool:
        """执行自动重连"""
        if not self.reconnect_policy:
            return False

        self._set_status(PlatformStatus.RECONNECTING)
        self._health.reconnect_count += 1

        async def try_connect() -> bool:
            try:
                return await self._do_connect()
            except Exception:
                return False

        success = await run_reconnect_loop(
            policy=self.reconnect_policy,
            connect_fn=try_connect,
            on_reconnecting=lambda a, d: self._emit(PlatformEvent.RECONNECTING, {"attempt": a, "delay": d}),
            on_reconnected=lambda a: self._emit(PlatformEvent.RECONNECTED, {"attempt": a}),
            on_give_up=lambda a: self._on_reconnect_failed(a),
            on_error=lambda a, e: logger.warning(f"[{self.platform_id}] 重连 {a} 失败: {e}"),
        )

        if success:
            self._health.status = PlatformStatus.ONLINE
            self._health.last_online = datetime.now()
            self._health.reconnect_count = 0
            self._health.error_count = 0
            self._health.last_error = None
            self._set_status(PlatformStatus.ONLINE)
            await self._do_start()
            if self.health_check_interval > 0:
                self._tasks.append(asyncio.create_task(self._health_check_loop()))
            return True
        return False

    async def _on_reconnect_failed(self, attempt: int):
        """重连最终失败"""
        self._set_status(PlatformStatus.OFFLINE)
        self._health.last_offline = datetime.now()
        await self._emit(
            PlatformEvent.RECONNECT_FAILED,
            {
                "attempt": attempt,
                "max_attempts": self.reconnect_policy.max_attempts if self.reconnect_policy else 0,
            },
        )

    async def _ping(self) -> bool:
        """
        执行心跳检测，测量延迟

        默认委托给 _do_health_check() 但会测量耗时。
        子类可覆写以提供更轻量的 ping 实现。
        """
        start = asyncio.get_event_loop().time()
        try:
            ok = await asyncio.wait_for(self._do_health_check(), timeout=10.0)
            elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000
            if ok:
                self._health.latency_ms = round(elapsed_ms, 1)
                self._health.last_heartbeat = datetime.now()
            return ok
        except asyncio.TimeoutError:
            self._health.latency_ms = -1.0
            return False
        except Exception:
            self._health.latency_ms = -1.0
            return False

    async def _health_check_loop(self):
        """后台健康检查循环"""
        await asyncio.sleep(self.health_check_interval)
        self._health.heartbeat_interval = self.health_check_interval
        while self._health.status in (PlatformStatus.ONLINE, PlatformStatus.DEGRADED):
            try:
                if self._health.last_online:
                    self._health.uptime_seconds = (datetime.now() - self._health.last_online).total_seconds()

                ok = await self._ping()
                if not ok:
                    self._health.status = PlatformStatus.DEGRADED
                    self._health.consecutive_health_failures += 1
                    cf = self._health.consecutive_health_failures
                    if cf == 1 or cf % 10 == 0:
                        logger.warning(
                            f"[{self.platform_id}] 心跳检测失败 (第{cf}次, 延迟={self._health.latency_ms}ms)"
                        )
                    await self._emit(
                        PlatformEvent.HEALTH_CHECK_FAILED,
                        {"consecutive_failures": cf, "latency_ms": self._health.latency_ms},
                    )

                    max_passive_delay = self.config.get("passive_health_timeout", 0)
                    if max_passive_delay > 0 and self._health.last_message_received:
                        since_last_msg = (datetime.now() - self._health.last_message_received).total_seconds()
                        if since_last_msg < max_passive_delay:
                            self._health.consecutive_health_failures = 0
                            self._health.status = PlatformStatus.DEGRADED
                            logger.debug(
                                f"[{self.platform_id}] 主动检查失败但最近 {since_last_msg:.0f}s 有消息，维持降级"
                            )
                            await asyncio.sleep(self.health_check_interval)
                            continue

                    if self.auto_reconnect:
                        await self._reconnect()
                        self._health.consecutive_health_failures = 0
                        return
                    else:
                        try:
                            await self._do_connect()
                        except Exception:
                            pass
                else:
                    if self._health.status == PlatformStatus.DEGRADED:
                        self._health.status = PlatformStatus.ONLINE
                        await self._emit(
                            PlatformEvent.HEALTH_CHECK_RECOVERED,
                            {"latency_ms": self._health.latency_ms},
                        )
                    self._health.consecutive_health_failures = 0
            except Exception as e:
                logger.debug(f"[{self.platform_id}] 心跳检测异常: {e}")

            await asyncio.sleep(self.health_check_interval)

    async def _cancel_tasks(self):
        """取消所有后台任务"""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # ==================== 子类需要实现的方法 ====================

    @abstractmethod
    async def _do_connect(self) -> bool:
        """执行实际连接逻辑。返回 True 表示成功"""
        ...

    @abstractmethod
    async def _do_disconnect(self):
        """执行实际断开逻辑"""
        ...

    @abstractmethod
    async def _do_health_check(self) -> bool:
        """执行健康检查。返回 True 表示健康"""
        ...

    async def _do_start(self):
        """平台连接成功后的初始化（可选覆写）"""
        pass

    async def _do_stop(self):
        """平台断开前的清理（可选覆写）"""
        pass

    # ==================== 消息处理 ====================

    async def handle_message(self, raw_message: Any) -> Optional[Dict]:
        """
        处理平台原始消息，转换为 M-Link 格式

        子类应覆写此方法将平台特有消息格式转换为统一格式
        """
        pass

    async def send_message(self, target: str, content: str, **kwargs) -> bool:
        """发送消息到平台（子类覆写）"""
        logger.warning(f"[{self.platform_id}] send_message 未实现")
        return False

    async def download_attachment(self, url: str, file_name: str = "") -> Optional[str]:
        """
        下载附件到本地 data/downloads/ 目录，返回本地文件路径

        子类可覆写以使用平台特定的下载方式（如 QQ Official API）。
        默认使用 aiohttp 直接下载。
        """
        import os
        import tempfile
        from urllib.parse import unquote, urlsplit

        try:
            import aiohttp

            from core.file_context import get_downloads_dir

            download_dir = get_downloads_dir()
            os.makedirs(download_dir, exist_ok=True)

            parsed = urlsplit(str(url).strip())
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                logger.warning(f"[{self.platform_id}] 拒绝非 HTTP(S) 附件 URL: {url}")
                return None

            # 仅保留文件名，避免 file_name/URL 路径穿越到 downloads 目录之外。
            local_name = os.path.basename(unquote(file_name or os.path.basename(parsed.path)))
            local_name = local_name.strip() or f"download_{id(url)}.bin"
            local_path = os.path.join(download_dir, local_name)
            if os.path.exists(local_path):
                stem, ext = os.path.splitext(local_name)
                counter = 1
                while os.path.exists(local_path):
                    local_name = f"{stem}_{counter}{ext}"
                    local_path = os.path.join(download_dir, local_name)
                    counter += 1

            temp_path = None

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    str(url).strip(),
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status < 200 or resp.status >= 300:
                        logger.warning(f"[{self.platform_id}] 下载失败 HTTP {resp.status}: {url}")
                        return None
                    data = await resp.read()

            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, dir=download_dir, prefix=".miya_download_", suffix=".part"
            ) as f:
                f.write(data)
                temp_path = f.name
            os.replace(temp_path, local_path)

            logger.debug(f"[{self.platform_id}] 文件已下载: {local_path} ({len(data)} bytes)")
            return local_path
        except ImportError:
            logger.warning(f"[{self.platform_id}] aiohttp 不可用，请安装")
            return None
        except Exception as e:
            logger.warning(f"[{self.platform_id}] 下载附件异常: {e}")
            return None
        finally:
            if "temp_path" in locals() and temp_path:
                with contextlib.suppress(OSError):
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

    async def send_file(
        self,
        target: str,
        file_path: str = "",
        file_name: str = "",
        file_data: Optional[bytes] = None,
        mime_type: str = "",
        caption: str = "",
        **kwargs,
    ) -> bool:
        """发送文件到平台

        Args:
            target: 接收方标识 (私聊: user_id, 群聊: group_id)
            file_path: 本地文件路径
            file_name: 文件显示名称（不指定则取路径 basename）
            file_data: 文件二进制数据（与 file_path 二选一，优先 file_path）
            mime_type: MIME 类型
            caption: 附带文本说明

        Returns:
            True 表示发送成功

        子类应覆写此方法实现平台特定的文件发送逻辑。
        基类默认实现：尝试从 file_path 读取并委托给 _do_send_file()。
        """
        if not await self._ensure_online():
            return False

        try:
            from core.file_context import OutboundFile

            if file_path:
                obf = OutboundFile.from_local(file_path, file_name=file_name, caption=caption)
            elif file_data:
                obf = OutboundFile.from_bytes(
                    file_data, filename=file_name or "file.bin", mime_type=mime_type, caption=caption
                )
            else:
                logger.warning(f"[{self.platform_id}] send_file: 未提供 file_path 或 file_data")
                return False

            if not obf.validate():
                logger.warning(f"[{self.platform_id}] send_file: 文件验证失败")
                return False

            return await self._do_send_file(target, obf, **kwargs)
        except Exception as e:
            logger.error(f"[{self.platform_id}] send_file 异常: {e}")
            return False

    async def send_image(
        self,
        target: str,
        image_path: str = "",
        file_data: Optional[bytes] = None,
        file_name: str = "",
        caption: str = "",
        **kwargs,
    ) -> bool:
        """发送图片到平台

        默认委托给 send_file()，子类可覆写以使用平台专属的图片发送 API。
        """
        return await self.send_file(
            target=target,
            file_path=image_path,
            file_name=file_name,
            file_data=file_data,
            caption=caption,
            **kwargs,
        )

    async def send_file_from_url(self, target: str, url: str, file_name: str = "", caption: str = "", **kwargs) -> bool:
        """下载远程文件后发送到平台

        组合 download_attachment() + send_file() 的快捷方法。
        """
        try:
            local_path = await self.download_attachment(url, file_name)
            if not local_path:
                logger.warning(f"[{self.platform_id}] send_file_from_url: 下载失败: {url}")
                return False
            return await self.send_file(
                target=target, file_path=local_path, file_name=file_name, caption=caption, **kwargs
            )
        except Exception as e:
            logger.error(f"[{self.platform_id}] send_file_from_url 异常: {e}")
            return False

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """平台特定的文件发送实现（子类覆写）"""
        logger.warning(f"[{self.platform_id}] _do_send_file 未实现")
        return False

    @property
    def supports_file_send(self) -> bool:
        """是否真正支持发送文件（子类覆写 _do_send_file 即视为支持）"""
        return type(self)._do_send_file is not BasePlatform._do_send_file

    async def _ensure_online(self) -> bool:
        if not self.is_online:
            logger.warning(f"[{self.platform_id}] 平台未在线，无法发送文件")
            return False
        return True

    def _record_message_in(self):
        """记录一条入站消息"""
        self._health.message_count += 1
        self._health.message_in_count += 1
        self._health.last_message_received = datetime.now()

    def _record_message_out(self):
        """记录一条出站消息"""
        self._health.message_count += 1
        self._health.message_out_count += 1

    # ==================== 可选社交能力（平台按能力覆写） ====================

    # 能力声明：子类覆写为 True 表示支持对应能力，供工具层做跨平台判断
    supports_like: bool = False
    supports_poke: bool = False
    supports_emoji_reaction: bool = False
    supports_group_members: bool = False

    async def send_like(self, user_id: Any, times: int = 1) -> bool:
        """点赞（默认不支持，平台覆写）"""
        return False

    async def send_poke(self, user_id: Any, group_id: Any = 0) -> bool:
        """拍一拍（默认不支持，平台覆写）"""
        return False

    async def set_msg_emoji_like(self, message_id: Any, emoji_id: Any) -> bool:
        """表情表态（默认不支持，平台覆写）"""
        return False

    async def get_group_member_list(self, group_id: Any) -> Optional[list]:
        """获取群成员列表（默认不支持，返回 None）"""
        return None

    # ==================== 事件系统 ====================

    def on(self, event: PlatformEvent, callback: Callable[[Dict], Awaitable[None]]):
        """注册事件监听器"""
        self._event_listeners[event].append(callback)

    def off(self, event: PlatformEvent, callback: Callable):
        """移除事件监听器"""
        with contextlib.suppress(ValueError):
            self._event_listeners[event].remove(callback)

    async def _emit(self, event: PlatformEvent, data: Dict):
        """触发事件"""
        payload = {
            "event": event.value,
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "timestamp": datetime.now().isoformat(),
            "status": self._health.status.value,
            "health": self._health.to_dict(),
            "data": data,
        }
        for listener in self._event_listeners.get(event, []):
            try:
                await listener(payload)
            except Exception as e:
                logger.error(f"[{self.platform_id}] 事件监听器异常: {e}")

    # ==================== 状态方法 ====================

    def _set_status(self, status: PlatformStatus):
        self._health.status = status

    @property
    def status(self) -> PlatformStatus:
        return self._health.status

    @property
    def is_online(self) -> bool:
        return self._health.status == PlatformStatus.ONLINE

    @property
    def health(self) -> PlatformHealth:
        return self._health

    def get_stats(self) -> Dict[str, Any]:
        """获取平台统计信息"""
        return {
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            **self._health.to_dict(),
        }
