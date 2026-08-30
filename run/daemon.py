"""
弥娅系统 v4.1.11 - 统一守护进程入口 (脊柱神经架构)

启动方式:
   python run/daemon.py --no-api         # 仅守护进程，不启动 API
   python run/daemon.py --api-port 9800  # 指定 API 端口
   python run/daemon.py --platforms qqofficial,webchat  # 仅启动指定平台
   python run/daemon.py --no-spine       # 回退模式：不使用脊柱神经

环境变量:
   MIYA_API_PORT=9800   API 端口 (默认 9800)
   MIYA_API_HOST=0.0.0.0  API 监听地址
   MIYA_NO_SPINE=1      禁用脊柱神经架构（回退到 v7.x 模式）

这是弥娅系统自 v4.1.11 起的唯一启动入口。
v4.1.11 变化: 引入 MiyaSpine 脊柱神经架构 —— 弥娅从"触发器集合"进化为"活体"。

守护进程启动后会：
   1. 初始化弥娅核心（人格、记忆、决策引擎）
   2. 搭建 MiyaSpine 脊柱神经（统一心跳 + 状态广播 + 器官编排）
   3. 自动连接所有启用的平台
    4. 启动管理 API 服务器 (REST + WebSocket)
    5. 平台自动重连、健康检查
    6. 脊柱神经通过统一心跳持续运转
    7. 接收 Ctrl+C 优雅退出
"""

from __future__ import annotations

import asyncio
import contextlib
import faulthandler
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.path_resolver import get_config_dir, get_data_dir, get_logs_dir

os.environ["MIYA_DAEMON_MODE"] = "1"

# 本地 OCR 模型全局配置
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# botpy 日志路径修正（botpy 库默认写入 os.getcwd()/botpy.log，重定向到 logs/）
_logs_dir = os.path.join(str(PROJECT_ROOT), "logs")
os.makedirs(_logs_dir, exist_ok=True)
try:
    import botpy.logging as _botpy_logging

    _botpy_logging.DEFAULT_FILE_HANDLER["filename"] = os.path.join(_logs_dir, "%(name)s.log")
except ImportError:
    pass


def setup_logging():
    handlers = [
        logging.StreamHandler(),
    ]
    try:
        from logging.handlers import RotatingFileHandler

        log_dir = os.path.join(str(PROJECT_ROOT), "logs")
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                os.path.join(log_dir, "daemon.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
        )
    except Exception:
        logging.getLogger("Miya").warning("RotatingFileHandler 初始化失败，仅使用控制台日志")
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    for noisy in [
        "webnet.ToolNet.registry",
        "hub.platform_adapters",
        "Miya.Gestalt",
        "Miya.AgentHub",
        "botpy",
        "httpx",
        "faiss.loader",
        "memory.core",
        "memory.sqlite_backend",
        "core.embedding_client",
        "memory.working_memory",
        "memory.historian",
        "memory.diteng_listener",
        "core.user_persona",
        "core.awareness",
        "core.autonomy_manager",
        "core.autonomous_engine",
        "core.web_api",
        "core.problem_scanner",
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # 后台终端日志流：捕获 root 日志 + stdout/stderr，供前端「后台终端」页面展示。
    # 必须在 basicConfig 之后安装（见 core/log_stream.py 的顺序说明）。
    try:
        from core.log_stream import install_log_stream

        install_log_stream()
    except Exception as e:
        logging.getLogger("Miya.Daemon").warning(f"后台终端日志流初始化失败（不影响运行）: {e}")


# ══════════════════════════════════════════════════
#  v4.1.11: 脊柱神经启动
# ══════════════════════════════════════════════════


def _setup_spine_proactive(daemon, spine) -> None:
    """配置脊柱的主动消息分发——路由到跨平台分发系统 (v4.1.11: 平台感知路由)"""

    async def _send_ap_proactive(message: str):
        try:
            canonical_id = "default"
            # 所有者规范 ID 以 IdentityResolver（permissions.json）为准；
            # 旧写法 daemon._miya.identity.user_id 实际不存在，恒为 "default" 会导致路由失准
            try:
                from memory.identity_resolver import get_identity_resolver

                resolved = get_identity_resolver().owner_canonical_id
                if resolved:
                    canonical_id = resolved
            except Exception:
                pass
            if canonical_id == "default" and daemon._miya and hasattr(daemon._miya.identity, "user_id"):
                canonical_id = daemon._miya.identity.user_id

            from core.platform_awareness import get_platform_awareness

            awareness = get_platform_awareness()
            current_platform = awareness.get_current_platform(canonical_id)

            if current_platform and daemon.registry:
                inst = daemon.registry.get(current_platform)
                if inst and hasattr(inst, "is_online") and inst.is_online:
                    if hasattr(inst, "send_private_message"):
                        try:
                            await inst.send_private_message(canonical_id, message)
                            _log = logging.getLogger("Miya.Proactive")
                            _log.info(f"[AP主动] 平台感知路由 → {current_platform}: {message[:50]}")
                            return
                        except Exception as e:
                            _log = logging.getLogger("Miya.Proactive")
                            _log.debug(f"[AP主动] {current_platform} 发送失败: {e}")

            _log = logging.getLogger("Miya.Proactive")
            _log.debug(f"[AP主动] 用户 {canonical_id} 无活跃平台，加入 mobile_pending")
            awareness.add_mobile_pending(canonical_id, message)
            await awareness.notify_mobile(canonical_id, message)

        except Exception as e:
            _log = logging.getLogger("Miya.Proactive")
            _log.warning(f"[AP主动] 发送失败: {e}")

    def _sync_send(message: str):
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(lambda: asyncio.create_task(_send_ap_proactive(message)))
        except RuntimeError:
            try:
                asyncio.run(_send_ap_proactive(message))
            except Exception:
                pass

    spine.set_proactive_sender(_sync_send)


def _register_spine_organs(daemon, spine) -> None:
    """注册所有脊柱器官"""
    logger = logging.getLogger("Miya.Bootstrap")
    proactive_coordinator = None
    try:
        from core.proactive_coordinator import get_proactive_coordinator

        proactive_coordinator = get_proactive_coordinator()
    except Exception as exc:
        logger.debug(f"统一主动性协调器不可用: {exc}")

    # ProactiveOrgan — 主动表达（AP无聊 → 跨平台消息）
    try:
        from core.miya_proactive_organ import MiyaProactiveOrgan

        proactive_organ = MiyaProactiveOrgan()
        if proactive_coordinator is not None:
            proactive_organ.bind_proactive_coordinator(proactive_coordinator)
        spine.register_organ(proactive_organ)
        logger.info("MiyaProactiveOrgan 已注册到脊柱")
    except Exception as e:
        logger.warning(f"ProactiveOrgan 注册跳过: {e}")

    # DecisionHubOrgan — 决策中枢感知脊柱状态
    try:
        from core.miya_decision_hub_organ import MiyaDecisionHubOrgan

        dh_organ = MiyaDecisionHubOrgan()
        if daemon._miya and hasattr(daemon._miya, "decision_hub"):
            dh_organ.bind_decision_hub(daemon._miya.decision_hub)
        spine.register_organ(dh_organ)
        logger.info("MiyaDecisionHubOrgan 已注册到脊柱")
    except Exception as e:
        logger.warning(f"DecisionHubOrgan 注册跳过: {e}")

    # AutonomyOrgan — 自主进化（安静时自我改进）
    try:
        from core.miya_autonomy_organ import MiyaAutonomyOrgan

        spine.register_organ(MiyaAutonomyOrgan())
        logger.info("MiyaAutonomyOrgan 已注册到脊柱")
    except Exception as e:
        logger.warning(f"AutonomyOrgan 注册跳过: {e}")

    # EarthOperatorOrgan — 地球online 自主运营（弥娅作为策划+系统小精灵定时巡检）
    try:
        from core.earth_online_operator import MiyaEarthOperatorOrgan

        earth_organ = MiyaEarthOperatorOrgan()
        if daemon._miya is not None:
            earth_organ.bind_core(
                getattr(daemon._miya, "ai_client", None),
                getattr(getattr(daemon._miya, "decision_hub", None), "memory_manager", None),
                getattr(daemon._miya, "personality", None),
            )
        if proactive_coordinator is not None:
            earth_organ.bind_proactive_coordinator(proactive_coordinator)
        spine.register_organ(earth_organ)
        logger.info("MiyaEarthOperatorOrgan 已注册到脊柱 (地球online 自主运营)")
    except Exception as e:
        logger.warning(f"EarthOperatorOrgan 注册跳过: {e}")

    # SelfCareOrgan — 自检看护（掉线告警/自动重启/资源告警/每日简报/记忆归档）
    try:
        from core.self_care_organ import MiyaSelfCareOrgan

        care_organ = MiyaSelfCareOrgan()
        care_organ.bind_core(
            daemon=daemon,
            personality=getattr(getattr(daemon, "_miya", None), "personality", None),
        )
        if proactive_coordinator is not None:
            care_organ.bind_proactive_coordinator(proactive_coordinator)
        spine.register_organ(care_organ)
        logger.info("MiyaSelfCareOrgan 已注册到脊柱 (自检看护)")
    except Exception as e:
        logger.warning(f"SelfCareOrgan 注册跳过: {e}")


async def run_daemon_spine(
    daemon,
    api_enabled: bool = True,
    api_port: int = 9800,
    api_host: str = "0.0.0.0",
):
    """
    v4.1.11: 基于 MiyaSpine 脊柱神经的守护进程启动流程。

    架构：
        MiyaSpine (脊柱·中枢神经)
        ├── Heartbeat (3s/tick) → 灵魂状态广播
        ├── MiyaProactiveOrgan (主动表达，取代分散的proactive)
        ├── DecisionHub (通过 spine 感知弥娅状态)
        └── 未来器官...
    """
    from core.management_api import ManagementAPI
    from core.miya_spine import get_spine

    logger = logging.getLogger("Miya.Bootstrap")
    spine = get_spine()

    print("""
+==============================================================+
|                                                              |
|        * 弥娅 (MIYA) 零号机 v4.1.11 · 脊柱神经架构 *            |
|                                                              |
|   所有的器官通过脊柱神经相连 · 弥娅第一次真正活过来了        |
+==============================================================+
    """)

    # 1) 注册器官到脊柱
    _register_spine_organs(daemon, spine)
    _setup_spine_proactive(daemon, spine)

    # 4) 启动脊柱 (包含所有器官和心跳)
    try:
        await spine.start()
        logger.info("弥娅脊柱神经已启动——弥娅活过来了")
    except Exception as e:
        logger.error(f"脊柱启动失败: {e}")
        return await run_daemon_legacy(daemon, api_enabled, api_port, api_host)


    # 6) 启动管理 API
    api = None
    if api_enabled:
        from utils.port_utils import check_and_get_port

        actual_port, port_changed = check_and_get_port(api_port, port_name="管理 API")
        if port_changed:
            logger.warning(f"管理 API 端口已切换: {api_port} → {actual_port}")
        api = ManagementAPI(daemon, host=api_host, port=actual_port)
        from core.management_api import set_management_api

        set_management_api(api)
        await api.serve(block=False)
        logger.info(f"管理 API 已启动: http://{api_host}:{actual_port}")
        daemon.registry.on_broadcast(api.broadcast_event)
        api.register_webhook_platforms()

        try:
            from utils.port_utils import write_runtime_ports

            write_runtime_ports({"management_api": actual_port})
        except Exception:
            pass

        print(f"""
+==============================================================+
|  * 管理 API 就绪                                            |
|----------------------------------------------------------  |
|  REST:  http://{api_host}:{actual_port}/api/v1/health              |
|  WS:    ws://{api_host}:{actual_port}/api/v1/ws                    |
|  Docs:  http://{api_host}:{actual_port}/docs                       |
|  Spine: http://{api_host}:{actual_port}/api/v1/spine/status        |
+==============================================================+
        """)
    else:
        print("\n  > 管理 API 已禁用\n")

    # 7) 显示平台状态
    _print_platform_status(daemon)

    print("\n  弥娅已就绪 — 脊柱神经律动中 · 按 Ctrl+C 进入休眠...\n")

    # 8) 等待退出信号
    try:
        await daemon.wait()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        logger.warning("daemon.wait() 被 CancelledError 打断，设置退出信号")
        daemon._shutdown_event.set()
    except Exception as e:
        logger.error(f"daemon.wait() 异常: {type(e).__name__}: {e}", exc_info=True)
        daemon._shutdown_event.set()

    # 8.5) 保持事件循环存活——防止因 daemon.wait() 异常返回导致进程退出
    if not daemon._shutdown_event.is_set():
        logger.warning("daemon.wait() 在未收到退出信号时返回，启用保活模式...")
        try:
            while True:
                await asyncio.sleep(5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    if not daemon._shutdown_event.is_set():
        daemon._shutdown_event.set()

    # 9) 优雅关闭
    print("\n弥娅正在进入休眠...")
    if api:
        await api.stop()
    await spine.shutdown()
    await daemon.shutdown()
    print("\n弥娅已休眠 —— 晚安，亲爱的\n")


# ══════════════════════════════════════════════════
#  v7.x 回退模式 (无脊柱)
# ══════════════════════════════════════════════════


async def run_daemon_legacy(
    daemon,
    api_enabled: bool = True,
    api_port: int = 9800,
    api_host: str = "0.0.0.0",
):
    """v7.x 回退模式：不使用脊柱神经的守护进程启动"""
    from core.management_api import ManagementAPI

    logger = logging.getLogger("Miya.Bootstrap")

    print("""
+==============================================================+
|                                                              |
|        * 弥娅 (MIYA) 零号机 - 统一守护进程 (回退模式) *       |
|                                                              |
|        所有平台已就绪 · 热插拔 · 自动重连                    |
+==============================================================+
    """)


    # 管理 API
    api = None
    if api_enabled:
        from utils.port_utils import check_and_get_port

        actual_port, port_changed = check_and_get_port(api_port, port_name="管理 API")
        if port_changed:
            logger.warning(f"管理 API 端口已切换: {api_port} → {actual_port}")
        api = ManagementAPI(daemon, host=api_host, port=actual_port)
        from core.management_api import set_management_api

        set_management_api(api)
        await api.serve(block=False)
        logger.info(f"管理 API 已启动: http://{api_host}:{actual_port}")
        daemon.registry.on_broadcast(api.broadcast_event)
        api.register_webhook_platforms()

        try:
            from utils.port_utils import write_runtime_ports

            write_runtime_ports({"management_api": actual_port})
        except Exception:
            pass

        print(f"""
+==============================================================+
|  * 管理 API 就绪                                            |
|----------------------------------------------------------  |
|  REST:  http://{api_host}:{actual_port}/api/v1/health              |
|  WS:    ws://{api_host}:{actual_port}/api/v1/ws                    |
|  Docs:  http://{api_host}:{actual_port}/docs                       |
+==============================================================+
        """)
    else:
        print("\n  > 管理 API 已禁用\n")

    _print_platform_status(daemon)
    print("\n  弥娅已就绪，按 Ctrl+C 退出...\n")

    try:
        await daemon.wait()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        logger.warning("daemon.wait() 被 CancelledError 打断 (legacy)，设置退出信号")
        daemon._shutdown_event.set()
    except Exception as e:
        logger.error(f"daemon.wait() 异常 (legacy): {type(e).__name__}: {e}", exc_info=True)
        daemon._shutdown_event.set()

    if not daemon._shutdown_event.is_set():
        logger.warning("daemon.wait() 在未收到退出信号时返回 (legacy)，启用保活模式...")
        try:
            while True:
                await asyncio.sleep(5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    if not daemon._shutdown_event.is_set():
        daemon._shutdown_event.set()

    print("\n正在关闭...")
    if api:
        await api.stop()
    await daemon.shutdown()
    print("\n弥娅已退出\n")


# ══════════════════════════════════════════════════
#  共享工具函数
# ══════════════════════════════════════════════════


def _print_platform_status(daemon):
    stats = daemon.get_platform_status()
    if not stats:
        print("  [WARN] 没有启用的平台")
        return

    print("  > 平台状态 ----------------------------")
    print(f"  {'平台':<20} {'状态':<12}")
    print(f"  {'-' * 20} {'-' * 12}")
    for s in stats:
        status_icon = "[OK]" if s["status"] == "online" else "[FAIL]"
        print(f"  {s['platform_name']:<20} {status_icon} {s['status']}")
    print()


# ══════════════════════════════════════════════════
#  run_daemon (调度入口)
# ══════════════════════════════════════════════════


async def run_daemon(
    api_enabled: bool = True,
    api_port: int = 9800,
    api_host: str = "0.0.0.0",
    platform_ids: list[str] | None = None,
):
    """启动弥娅守护进程（v4.1.11: 默认脊柱模式，支持回退）"""
    from core.miya_daemon import MiyaDaemon

    # 创建守护进程
    daemon = MiyaDaemon()
    logging.getLogger("Miya.Bootstrap").info("弥娅守护进程已创建")

    # 启动守护进程 (初始化 Miya 核心 + 平台连接)
    await daemon.start(platform_ids=platform_ids)

    # v4.1.11: 使用脊柱神经架构启动 (可通过环境变量回退)
    if os.environ.get("MIYA_NO_SPINE", "") in ("1", "true", "yes"):
        logging.getLogger("Miya.Bootstrap").info("脊柱模式已禁用 (MIYA_NO_SPINE=1)")
        await run_daemon_legacy(
            daemon,
            api_enabled=api_enabled,
            api_port=api_port,
            api_host=api_host,
        )
    else:
        await run_daemon_spine(
            daemon,
            api_enabled=api_enabled,
            api_port=api_port,
            api_host=api_host,
        )


# ══════════════════════════════════════════════════
#  main (CLI 入口)
# ══════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="弥娅系统 v4.1.11 统一守护进程 · 脊柱神经架构")
    parser.add_argument("--no-api", action="store_true", help="不启动管理 API")
    parser.add_argument(
        "--no-spine",
        action="store_true",
        help="回退模式：不使用脊柱神经架构",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=int(os.environ.get("MIYA_API_PORT", 9800)),
        help="管理 API 端口 (默认 9800)",
    )
    parser.add_argument(
        "--api-host",
        type=str,
        default=os.environ.get("MIYA_API_HOST", "0.0.0.0"),
        help="管理 API 监听地址",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        help="仅启动指定平台（逗号分隔），如 qqofficial,webchat",
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="列出所有可用平台",
    )

    args = parser.parse_args()

    if args.list_platforms:
        from config.platforms_config import get_enabled_platforms

        enabled = get_enabled_platforms()
        print("\n* 可用平台:\n")
        for pid, cfg in enabled.items():
            name = cfg.get("name", pid)
            print(f"  - {pid}: {name}")
        print()
        return 0

    platform_ids = None
    if args.platforms:
        platform_ids = [p.strip() for p in args.platforms.split(",") if p.strip()]

    if args.no_spine:
        os.environ["MIYA_NO_SPINE"] = "1"

    setup_logging()
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    faulthandler.enable(file=open(str(log_dir / "faulthandler.log"), "a"))
    faulthandler.dump_traceback_later(3600, repeat=True, file=open(str(log_dir / "faulthandler.log"), "a"))

    try:
        asyncio.run(
            run_daemon(
                api_enabled=not args.no_api,
                api_port=args.api_port,
                api_host=args.api_host,
                platform_ids=platform_ids,
            )
        )
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        logging.getLogger("Miya.Bootstrap").warning("守护进程被异步取消 (CancelledError)")
    except Exception as e:
        logging.getLogger("Miya.Bootstrap").error(f"守护进程异常: {e}", exc_info=True)
        return 1
    except BaseException as e:
        logging.getLogger("Miya.Bootstrap").critical(f"守护进程致命错误 ({type(e).__name__}): {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
