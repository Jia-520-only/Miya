"""
弥娅守护进程 (MiyaDaemon) - 统一后台核心

提供：
- 单一 Miya 核心实例（所有平台共享同一个人格、记忆、决策）
- 平台编排（动态注册、批量启停、健康监控）
- 优雅的生命周期管理
- 信号处理（SIGINT/SIGTERM 安全退出）
- 运行时 API 服务器（可选）

Usage:
    daemon = MiyaDaemon()
    daemon.register_platforms_from_config()
    await daemon.start()
    await daemon.wait()          # 阻塞直到停止信号
    await daemon.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime
from typing import Any, Dict, List, Optional
from .version import __version__

from .unified_platform import (
    BasePlatform,
    PlatformEvent,
    PlatformRegistry,
    get_registry,
)

logger = logging.getLogger("Miya.Daemon")


class MiyaDaemon:
    """
    弥娅统一守护进程

    架构：
        MiyaDaemon
         ├── Miya Core (单例人格/记忆/决策)
         ├── PlatformRegistry (平台编排器)
         │    ├── QQ Official
         │    ├── Telegram
         │    ├── Discord
         │    └── ... (18+ 平台)
         └── Management API (可选)
    """

    VERSION = __version__

    def __init__(self, auto_register: bool = True):
        self._started = False
        self._shutdown_event = asyncio.Event()
        self._miya = None
        self._registry = get_registry()
        self._management_server = None

        self.start_time: Optional[datetime] = None
        self._background_tasks: list[asyncio.Task] = []

        if auto_register:
            self.register_platforms_from_config()

    # ==================== 平台注册 ====================

    def register_platforms_from_config(self):
        """从配置文件注册所有启用的平台"""
        from config.platforms_config import get_enabled_platforms

        enabled = get_enabled_platforms()
        if not enabled:
            logger.warning("没有启用的平台")
            return

        for platform_id, platform_config in enabled.items():
            self._register_from_config(platform_id, platform_config)

    def _register_from_config(self, platform_id: str, config: Dict[str, Any]):
        """根据配置注册单个平台"""
        platform = self._create_platform(platform_id, config)
        if platform:
            # v8.1: 对于 GenericPlatform，类 platform_id ("generic") 与真实 platform_id
            # (如 "desktop"/"mobile") 不一致。直接存实例，不注册类，避免产生幽灵 "generic" 条目。
            if platform.__class__.platform_id != platform_id:
                self._registry._instances[platform_id] = platform
                self._registry._configs[platform_id] = config
            else:
                self._registry.register(platform.__class__, config)
            logger.info(f"注册平台: {platform_id} ({platform.platform_name})")

    def _create_platform(self, platform_id: str, config: Dict[str, Any]) -> Optional[BasePlatform]:
        """根据平台ID创建对应的平台实例"""
        from .unified_platform_impl import (
            DingTalkPlatform,
            DiscordPlatform,
            GenericPlatform,
            KOOKPlatform,
            LarkPlatform,
            LINEPlatform,
            OneBotPlatform,
            QQOfficialPlatform,
            SatoriPlatform,
            SlackPlatform,
            TelegramPlatform,
            WeChatOfficialPlatform,
            WeComPlatform,
        )
        from .unified_platform_impl.weixin_ilink_platform import WeixinIlinkPlatform

        platform_map: Dict[str, type] = {
            "qqofficial": QQOfficialPlatform,
            "telegram": TelegramPlatform,
            "discord": DiscordPlatform,
            "aiocqhttp": OneBotPlatform,
            "lark": LarkPlatform,
            "kook": KOOKPlatform,
            "slack": SlackPlatform,
            "line": LINEPlatform,
            "dingtalk": DingTalkPlatform,
            "satori": SatoriPlatform,
            "wecom": WeComPlatform,
            "weixin_official_account": WeChatOfficialPlatform,
            "weixin_ilink": WeixinIlinkPlatform,
        }

        cls = platform_map.get(platform_id)
        if cls:
            return cls(config=config)

        logger.info(f"平台 {platform_id} 使用通用适配器")
        generic = GenericPlatform(config=config)
        generic.platform_id = platform_id
        generic.platform_name = config.get("name", platform_id)
        return generic

    # ==================== 生命周期 ====================

    async def start(self, platform_ids: Optional[List[str]] = None):
        """启动守护进程"""
        logger.info("=" * 60)
        logger.info(f"✦ 弥娅守护进程 v{self.VERSION} 启动中... ✦")
        logger.info("=" * 60)

        self.start_time = datetime.now()

        # 1. 初始化 Miya 核心
        await self._init_miya_core()

        # 2. 启动平台 (内含 miya_core 注入)
        await self._init_platforms(platform_ids)

        # 3. 注册信号处理
        self._setup_signal_handlers()

        # 4. 记录就绪
        registered = self._registry.list_registered()
        logger.info(f"已注册 {len(registered)} 个平台: {[p['id'] for p in registered]}")

        self._started = True
        logger.info("=" * 60)
        logger.info("💫 弥娅守护进程已就绪")
        logger.info("=" * 60)

    async def _init_miya_core(self):
        """初始化 Miya 核心（懒加载）"""
        try:
            # MCP 提前初始化：让 ToolNet / MCPNet 在 Miya 核心构建前就能发现服务
            from core.mcp_manager import get_mcp_manager

            mcp_manager = get_mcp_manager(auto_register=False)
            await mcp_manager.initialize()
            logger.info(f"✅ MCP 服务提前初始化完成: {len(mcp_manager._services)} 个服务")
            from run.main import Miya

            self._miya = Miya()
            logger.info("✅ Miya 核心初始化完成")

            # Web API 已由 Miya.__init__() → _init_web_api() → _start_api_server() 启动
            # 不再重复启动，避免端口冲突

            if self._miya.memory_net:
                try:
                    await self._miya._initialize_memory_net_async()
                    logger.info("✅ MemoryNet 全局记忆系统初始化成功")
                except Exception as e:
                    logger.error(f"⚠️ MemoryNet 初始化失败: {e}")

            dh = getattr(self._miya, "decision_hub", None)
            if dh:
                dh._deferred_init_event.wait(timeout=5)
            if dh and getattr(dh, "proactive_chat", None) and dh.proactive_chat.is_enabled():
                await dh.start_proactive_background()
                logger.info("✅ 主动聊天后台轮询已启动")
        except Exception as e:
            logger.error(f"❌ Miya 核心初始化失败: {e}", exc_info=True)
            raise

    async def _init_platforms(self, platform_ids: Optional[List[str]] = None):
        """初始化并连接所有平台"""
        self._registry.on_broadcast(self._on_platform_broadcast)

        if platform_ids:
            results = {}
            for pid in platform_ids:
                results[pid] = await self._registry.start(pid, miya_core=self._miya)
        else:
            results = await self._registry.start_all(miya_core=self._miya)

        online = sum(1 for v in results.values() if v)
        total = len(results)
        logger.info(f"平台连接: {online}/{total} 在线")

    async def wait(self):
        """阻塞等待直到收到停止信号"""
        logger.debug("daemon.wait() 开始等待...")
        try:
            await self._shutdown_event.wait()
            logger.info("daemon.wait() 收到退出信号，开始关闭")
        except asyncio.CancelledError:
            logger.warning("daemon.wait() 被取消 (CancelledError)，主动设置退出信号")
            self._shutdown_event.set()
        except Exception as e:
            logger.error(f"daemon.wait() 异常退出: {type(e).__name__}: {e}", exc_info=True)
            self._shutdown_event.set()

    async def stop(self):
        """停止守护进程（收到信号时调用）"""
        logger.info("收到停止信号，正在安全退出...")
        self._shutdown_event.set()

    async def shutdown(self):
        """优雅关闭"""
        logger.info("=" * 60)
        logger.info("弥娅守护进程正在关闭...")

        if self._miya:
            await self._save_state()

        # 停止所有平台
        await self._registry.shutdown()

        # 取消后台任务
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        if self._miya:
            await self._close_miya_core()

        logger.info("💤 弥娅守护进程已关闭")
        logger.info("=" * 60)

    async def _save_state(self):
        """保存状态（关闭前持久化工作记忆、谛听、话题追踪）"""
        try:
            from memory.diteng_listener import get_diting
            from memory.working_memory import get_working_memory

            try:
                wm = get_working_memory()
                wm.save()
                logger.debug("[关闭] 工作记忆已保存")
            except Exception as e:
                logger.debug(f"[关闭] 工作记忆保存失败: {e}")

            try:
                diting = get_diting()
                diting.save()
                logger.debug("[关闭] 谛听状态已保存")
            except Exception as e:
                logger.debug(f"[关闭] 谛听保存失败: {e}")

        except Exception as e:
            logger.warning(f"状态保存失败: {e}")

    async def _close_miya_core(self):
        """关闭 Miya 核心"""
        try:
            if self._miya:
                conv_hist = getattr(self._miya, "conversation_history", None)
                if conv_hist and hasattr(conv_hist, "flush"):
                    await conv_hist.flush()
                if conv_hist and hasattr(conv_hist, "close"):
                    await conv_hist.close()
        except Exception as e:
            logger.warning(f"Miya 核心关闭异常: {e}")

    # ==================== 信号处理 ====================

    def _setup_signal_handlers(self):
        """注册系统信号处理器（线程安全）"""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_stop)
            except NotImplementedError:
                signal.signal(sig, self._signal_handler_sync)

    def _signal_stop(self):
        """信号回调（运行在事件循环线程中，安全）"""
        asyncio.create_task(self.stop())

    def _signal_handler_sync(self, sig_num, frame):
        """Windows 信号回调（运行在任意线程中，使用 call_soon_threadsafe）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.stop()))
            else:
                self._shutdown_event.set()
        except Exception:
            self._shutdown_event.set()

    # ==================== 事件处理 ====================

    async def _on_platform_broadcast(self, event: Dict):
        """处理平台广播事件"""
        event_type = event.get("event", "")
        pid = event.get("platform_id", "unknown")

        if PlatformEvent.DISCONNECTED.value in event_type:
            logger.info(f"[{pid}] 平台已断开")
        elif PlatformEvent.RECONNECTING.value in event_type:
            logger.info(f"[{pid}] 正在重连 (第 {event.get('data', {}).get('attempt', '?')} 次)")
        elif PlatformEvent.RECONNECT_FAILED.value in event_type:
            logger.error(f"[{pid}] 重连失败，已达最大尝试次数")

    # ==================== 管理接口 ====================

    async def start_platform(self, platform_id: str) -> bool:
        """热启动一个平台"""
        return await self._registry.start(platform_id, miya_core=self._miya)

    async def stop_platform(self, platform_id: str) -> bool:
        """热停止一个平台"""
        return await self._registry.stop(platform_id)

    async def restart_platform(self, platform_id: str) -> bool:
        """热重启一个平台"""
        return await self._registry.restart(platform_id)

    def get_platform_status(self) -> List[Dict[str, Any]]:
        """获取所有平台状态"""
        return self._registry.get_all_stats()

    def get_daemon_status(self) -> Dict[str, Any]:
        """获取守护进程状态"""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        return {
            "version": self.VERSION,
            "started": self._started,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": uptime,
            "platforms": {
                "total": len(self._registry._platform_classes),
                "online": len(self._registry.get_online_platforms()),
            },
        }

    @property
    def permission_engine(self):
        """获取统一权限引擎"""
        from .unified_permission import get_permission_engine

        return get_permission_engine()

    @property
    def miya(self):
        """获取 Miya 核心实例"""
        return self._miya

    def _start_web_api(self):
        """启动 Web API 服务器（后台线程，端口 8000）"""
        try:
            import threading

            web_api = getattr(self._miya, "web_api", None)
            if not web_api or not getattr(web_api, "router", None):
                logger.debug("Web API 未初始化，跳过")
                return

            import uvicorn
            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware

            app = FastAPI(title="Miya Web API")
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            app.include_router(web_api.router)

            # Load yinmei plugin if available
            try:
                from plugins.yinmei.integration import install_yinmei_plugin

                install_yinmei_plugin(app, enable_scheduler=False)
            except Exception:
                pass

            from utils.port_utils import check_and_get_port

            api_port, port_changed = check_and_get_port(8000, port_name="Web API")

            def _run():
                uvicorn.run(app, host="0.0.0.0", port=api_port, log_level="warning")

            threading.Thread(target=_run, daemon=True, name="Miya-WebAPI").start()
            logger.info(f"Web API 服务器已启动 (http://0.0.0.0:{api_port})")
        except Exception as e:
            logger.warning(f"Web API 启动失败: {e}")

    @property
    def registry(self) -> PlatformRegistry:
        """获取平台注册表"""
        return self._registry
