"""
弥娅 Web API 路由器 - 重构版
为 Web 端提供 HTTP 接口，支持模块化架构
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

from starlette.responses import StreamingResponse


def _is_process_running(process):
    """安全地检查进程状态"""
    try:
        import psutil

        return process.status() == "running"
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


try:
    from fastapi import APIRouter, HTTPException, UploadFile, Request

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception
    UploadFile = object

logger = logging.getLogger(__name__)

from datetime import datetime

# 导入模型（向后兼容）
from .models import (
    BlogPostCreate,
    BlogPostUpdate,
    ChatRequest,
    GitHubConfig,
    TerminalChatRequest,
    ToolExecuteRequest,
    UserLogin,
    UserRegister,
)


class WebAPI:
    """Web API 路由器（重构版）

    职责：
    - 提供 HTTP RESTful 接口
    - 认证和授权
    - 调用 WebNet 和 DecisionHub
    - 安全检查
    """

    def __init__(self, web_net: Any, decision_hub: Any, github_store: Any = None):
        """初始化 API 路由器

        Args:
            web_net: WebNet 实例
            decision_hub: DecisionHub 实例
            github_store: GitHubStore 实例 (可选)
        """
        self.web_net = web_net
        self.decision_hub = decision_hub
        self.github_store = github_store

        # 初始化多Agent协作系统
        try:
            from core.multi_agent_orchestrator import MultiAgentOrchestrator

            self.multi_agent_orchestrator = MultiAgentOrchestrator()
        except:
            self.multi_agent_orchestrator = None

        if not FASTAPI_AVAILABLE:
            logger.warning("[WebAPI] FastAPI 不可用，API 功能将被禁用")
            self.router = None
            return

        self.router = APIRouter(prefix="", tags=["Web"])

        # 初始化子路由
        self._init_subroutes()

        # 添加 MiyaAPI 路由（真实数据，必须在前）
        self._include_miya_api()

        # 添加健康/资源/管理路由
        self._include_extra_routers()

        # 设置路由（mock/兼容层，在真实路由之后）
        self._setup_routes()

    def _include_miya_api(self):
        """添加 MiyaAPI 完整路由（168 路，必须优先）"""
        try:
            from .miya_api import MiyaAPI

            miya_api = MiyaAPI(self.web_net, self.decision_hub)
            if miya_api and miya_api.router:
                self.router.include_router(miya_api.router)
                logger.info("[WebAPI] MiyaAPI 路由已添加")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加 MiyaAPI 路由失败: {e}")

    def _include_extra_routers(self):
        """添加健康监控 / 资源管理 / MiyaWebUI 管理路由"""
        try:
            from core.health_monitor import router as health_router

            self.router.include_router(health_router)
            logger.info("[WebAPI] 健康监控路由已添加 (/health/)")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加健康监控路由失败: {e}")
        try:
            # v9.0 模型池路由（/api/models/list|status|routing，前端 ConfigView 断链修复）
            from core.web_api.routes.models_routes import router as models_router

            self.router.include_router(models_router)
            logger.info("[WebAPI] 模型池路由已添加 (/api/models/)")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加模型池路由失败: {e}")
        try:
            # 前端断链端点桥接（/api/config/get|set、/api/system/prompt、/api/document/*、/api/audio/transcribe）
            from .frontend_bridge import FrontendBridgeRoutes

            bridge = FrontendBridgeRoutes(self.web_net, self.decision_hub)
            if bridge and bridge.get_router():
                self.router.include_router(bridge.get_router())
                logger.info("[WebAPI] 前端桥接路由已添加")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加前端桥接路由失败: {e}")
        try:
            from core.resource_manager import router as resource_router

            self.router.include_router(resource_router)
            logger.info("[WebAPI] 资源管理路由已添加 (/resources/)")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加资源管理路由失败: {e}")
        try:
            from pathlib import Path

            from webnet.miya_webui import (
                create_management_routes,
                create_runtime_routes,
                get_global_webui,
            )

            webui = get_global_webui(Path("config"), Path("data"))
            create_management_routes(self.router, webui)
            create_runtime_routes(self.router, webui)
            logger.info("[WebAPI] MiyaWebUI 管理路由已添加")
        except Exception as e:
            logger.warning(f"[WebAPI] 添加 MiyaWebUI 管理路由失败: {e}")

    def _init_subroutes(self):
        """初始化子路由模块"""
        try:
            from .auth import AuthRoutes
            from .blogs import BlogRoutes
            from .chat import ChatRoutes
            from .config_routes import ConfigPanelRoutes
            from .desktop import DesktopRoutes
            from .art import ArtRoutes
            from .system import SystemRoutes
            from .tools import ToolRoutes
            from .earth_online import EarthOnlineRoutes
            # 跨终端路由已迁移至 Open-ClaudeCode

            # 初始化路由模块
            self.auth_routes = AuthRoutes(self.web_net, self.decision_hub)
            self.blogs_routes = BlogRoutes(self.web_net, self.decision_hub)
            self.chat_routes = ChatRoutes(self.web_net, self.decision_hub)
            # 终端/跨终端路由已迁移至 Open-ClaudeCode
            self.terminal_routes = None
            self.cross_terminal_routes = None
            self.system_routes = SystemRoutes(self.web_net, self.decision_hub)
            self.desktop_routes = DesktopRoutes(self.web_net, self.decision_hub)
            self.config_panel_routes = ConfigPanelRoutes(self.web_net, self.decision_hub)
            self.tools_routes = ToolRoutes(self.web_net, self.decision_hub)
            self.art_routes = ArtRoutes(self.web_net, self.decision_hub)
            self.earth_routes = EarthOnlineRoutes(self.web_net, self.decision_hub)

            # TTS 语音合成路由
            from .tts_routes import TTSRoutes

            self.tts_routes = TTSRoutes()

            logger.info("[WebAPI] 所有子路由初始化成功")

        except Exception as e:
            logger.error(f"[WebAPI] 子路由初始化失败: {e}", exc_info=True)
            self.auth_routes = None
            self.blogs_routes = None
            self.chat_routes = None
            self.terminal_routes = None
            self.system_routes = None
            self.desktop_routes = None
            self.tools_routes = None
            self.cross_terminal_routes = None
            self.tts_routes = None
            self.art_routes = None
            self.earth_routes = None
            self.config_panel_routes = None

    def _setup_routes(self):
        """设置 API 路由"""

        # 注册子路由到主路由器
        if self.auth_routes and self.auth_routes.get_router():
            self.router.include_router(self.auth_routes.get_router())

        if self.blogs_routes and self.blogs_routes.get_router():
            self.router.include_router(self.blogs_routes.get_router())

        if self.chat_routes and self.chat_routes.get_router():
            self.router.include_router(self.chat_routes.get_router())

        if self.terminal_routes and self.terminal_routes.get_router():
            self.router.include_router(self.terminal_routes.get_router())

        if self.system_routes and self.system_routes.get_router():
            self.router.include_router(self.system_routes.get_router())

        if self.desktop_routes and self.desktop_routes.get_router():
            self.router.include_router(self.desktop_routes.get_router())

        if getattr(self, "config_panel_routes", None) and self.config_panel_routes.get_router():
            self.router.include_router(self.config_panel_routes.get_router())
            logger.info("[WebAPI] 配置面板路由已添加 (/api/config/panel/)")

        if self.tools_routes and self.tools_routes.get_router():
            self.router.include_router(self.tools_routes.get_router())

        if self.art_routes and self.art_routes.get_router():
            self.router.include_router(self.art_routes.get_router())

        if getattr(self, "earth_routes", None) and self.earth_routes.get_router():
            self.router.include_router(self.earth_routes.get_router())
            logger.info("[WebAPI] 地球online 路由已添加 (/api/earth/)")

        if self.cross_terminal_routes and self.cross_terminal_routes.get_router():
            self.router.include_router(self.cross_terminal_routes.get_router())

        if hasattr(self, "tts_routes") and self.tts_routes and self.tts_routes.get_router():
            self.router.include_router(self.tts_routes.get_router())

        # ========== 兼容旧API路径 ==========

        @self.router.get("/api/system/info")
        async def get_system_info():
            """获取系统信息（psutil 实时数据）"""
            import platform

            import psutil

            try:
                dp = "C:\\" if platform.system() == "Windows" else "/"
                d = psutil.disk_usage(dp)
                m = psutil.virtual_memory()
                return {
                    "cpu_usage": psutil.cpu_percent(interval=0.1),
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_total_gb": round(m.total / (1024**3), 1),
                    "memory_used_gb": round(m.used / (1024**3), 1),
                    "memory_usage_percent": m.percent,
                    "disk_usage_percent": d.percent,
                    "disk_used_gb": round(d.used / (1024**3), 1),
                    "disk_total_gb": round(d.total / (1024**3), 1),
                    "uptime_seconds": int(time.time() - getattr(psutil, "boot_time", lambda: time.time() - 1)())
                    if hasattr(psutil, "boot_time")
                    else 0,
                    "process_count": len(psutil.pids()),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                return {"error": str(e)}

        @self.router.get("/api/emotion")
        async def get_emotion_state():
            """获取当前情绪状态"""
            try:
                if self.decision_hub and hasattr(self.decision_hub, "emotion") and self.decision_hub.emotion:
                    s = self.decision_hub.emotion.get_emotion_state()
                    if s:
                        return {
                            "dominant_emotion": s.get("dominant", "平静"),
                            "intensity": s.get("intensity", 50),
                            "emotions": s.get("emotions", {}),
                        }
            except Exception:
                pass
            return {"dominant_emotion": "平静", "intensity": 50, "emotions": {}}

        @self.router.get("/api/miya/logs")
        async def get_miya_logs(limit: int = 100):
            """获取系统日志"""
            try:
                import glob

                lfs = sorted(glob.glob("logs/*.log"), key=os.path.getmtime, reverse=True)
                lines = []
                for lf in lfs[:3]:
                    try:
                        with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                            lines.extend(f.readlines()[-limit:])
                    except:
                        pass
                return {
                    "status": "success",
                    "logs": lines[-limit:],
                    "count": len(lines),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                return {"status": "error", "error": str(e), "logs": [], "count": 0}

        @self.router.get("/api/queue/stats")
        async def get_queue_stats():
            """获取消息队列统计"""
            return {
                "size": 0,
                "processing": False,
                "model": "default",
                "interval": 5,
                "last_process_time_ms": 0,
            }

        @self.router.get("/api/config/file")
        async def get_config_file(path: str = ""):
            """读取配置文件内容"""
            try:
                fp = os.path.join(os.getcwd(), path)
                fp = os.path.normpath(fp)
                if not fp.startswith(os.path.normpath(os.getcwd())) or not os.path.isfile(fp):
                    return {"error": "文件不存在"}
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    return {"path": path, "content": f.read()}
            except Exception as e:
                return {"error": str(e)}

        @self.router.get("/api/status")
        async def get_legacy_system_status():
            """获取系统状态（兼容旧API路径，重定向到新路径）"""
            try:
                if hasattr(self.decision_hub, "miya_instance"):
                    miya = self.decision_hub.miya_instance
                    status = miya.get_system_status()

                    from hub.platform_adapters import get_adapter

                    web_adapter = get_adapter("web")
                    platform_info = web_adapter.get_platform_info()

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
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                return {"error": "System not initialized"}
            except Exception as e:
                logger.error(f"[WebAPI] 获取系统状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # ========== Web 端对话路由 (兼容旧API) ==========

        @self.router.get("/api/soul/current")
        async def get_current_soul():
            """获取当前消息的灵魂数据"""
            # 优先读取 _last_soul_data (灵魂发生器直接写入)
            soul_data = getattr(self.decision_hub, "_last_soul_data", None)
            if soul_data and soul_data.get("emotions"):
                return soul_data
            # 回退到 _last_soul_output (协作引擎写入)
            soul = getattr(self.decision_hub, "_last_soul_output", None)
            return soul or {}

        @self.router.post("/api/chat")
        async def web_chat(request: ChatRequest, req: Request):
            """Web 端对话接口（兼容旧API）"""
            try:
                from mlink.message import Message

                platform = request.platform or "desktop"

                # 用户身份链接处理
                # 优先使用 usg_id 字段（桌面端专用），其次用 session_id
                lookup_id = request.usg_id or request.user_id or request.session_id
                usg_id = lookup_id
                sendg_name = f"{platform}用户-{lookup_id[:8]}"

                # 从 permissions.json 检查用户链接配置（兼容 usg_id / user_id 两种字段名）
                try:
                    import json
                    from pathlib import Path

                    perms_file = Path("config/permissions.json")
                    if perms_file.exists():
                        perms_data = json.loads(perms_file.read_text(encoding="utf-8"))
                        users = perms_data.get("users", [])
                        for u in users:
                            uid_match = u.get("usg_id") or u.get("user_id")
                            if uid_match and str(uid_match) == str(lookup_id or ""):
                                linked_to = u.get("linked_to")
                                if linked_to:
                                    usg_id = linked_to
                                    sendg_name = u.get("username", sendg_name)
                                break
                except Exception:
                    pass

                perception = {
                    "platform": platform,
                    "content": request.message,
                    "usg_id": usg_id,
                    "sendg_name": sendg_name,
                    "user_id": usg_id,
                }

                # 处理图片/文件分析 (base64 → 视觉模型 → 注入上下文)
                if request.image_data:
                    try:
                        from core.game_play.engine import get_game_play_engine
                        from core.text_loader import get_text

                        engine = get_game_play_engine()
                        await engine.initialize()
                        analysis = await engine._call_vision(
                            get_text("screen_vision.describe_prompt", "用中文描述当前屏幕上的内容。"),
                            request.image_data,
                            request.message or get_text("screen_vision.describe_default_query", "描述当前画面"),
                        )
                        if analysis:
                            perception["_image_analysis"] = {
                                "success": True,
                                "description": analysis,
                                "labels": [],
                                "model": "vision",
                            }
                            perception["image_analysis"] = perception["_image_analysis"]
                            logger.info(f"[WebChat] 图片分析: {analysis[:80]}...")
                    except Exception as e:
                        logger.warning(f"[WebChat] 图片分析失败: {e}")

                # 检查是否为超级管理员，注入 is_owner 标记
                try:
                    from core.unified_permission import get_permission_engine

                    engine = get_permission_engine()
                    if engine and engine.is_superadmin(str(usg_id), platform=platform):
                        perception["is_owner"] = True
                        perception["canonical_user_id"] = usg_id
                except Exception:
                    pass

                message = Message(
                    msg_type="data",
                    content=perception,
                    source="web_api",
                    destination="decision_hub",
                )

                (self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None)
                (self.decision_hub.personality.get_profile() if self.decision_hub.personality else None)

                response = await self.decision_hub.process_perception_cross_platform(message)

                if not response:
                    response = "抱歉，我无法处理您的请求。"

                emotion_after = self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None
                personality_after = (
                    self.decision_hub.personality.get_profile() if self.decision_hub.personality else None
                )

                emotion_result = None
                if emotion_after:
                    emotion_result = {
                        "dominant": emotion_after.get("dominant", "平静"),
                        "intensity": emotion_after.get("intensity", 0.5),
                    }

                personality_result = None
                if personality_after:
                    personality_result = {
                        "state": personality_after.get("dominant", "empathy"),
                        "vectors": personality_after.get(
                            "vectors",
                            {
                                "warmth": 0.5,
                                "logic": 0.5,
                                "creativity": 0.5,
                                "empathy": 0.5,
                                "resilience": 0.5,
                            },
                        ),
                    }

                # 获取文件数据（桌面/移动端 — 含 base64 用于前端渲染文件卡片）
                files = None
                try:
                    from core.platform_context import get_current_platform_adapter

                    adapter = get_current_platform_adapter()
                    if adapter and hasattr(adapter, "last_file_info") and adapter.last_file_info:
                        fi = adapter.last_file_info
                        files = [
                            {
                                "name": fi["name"],
                                "size": fi["size"],
                                "mime_type": fi["mime_type"],
                                "url": fi["url"],
                                "base64": fi["base64"],
                            }
                        ]
                        url = fi["url"]
                        response += f"\n\n📄 [{fi['name']}]({url})"
                        adapter.last_file_info = None
                except Exception:
                    pass

                return {
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat(),
                    "emotion": emotion_result,
                    "personality": personality_result,
                    "files": files,
                    "tools_used": getattr(self.decision_hub, "_last_tools_used", []),
                    "memory_retrieved": getattr(self.decision_hub, "_last_memory_retrieved", False),
                }
            except Exception as e:
                logger.error(f"[WebAPI] Web聊天处理失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # ========== SSE 流式对话（弥娅灵魂模式） ==========
        @self.router.post("/api/chat/send")
        async def web_chat_sse(request: ChatRequest):
            """SSE流式对话 - 复用QQ端灵魂处理逻辑

            与QQ端/Napcat完全一致的处理流程：
            1. 创建 M-Link Message
            2. DecisionHub.process_perception_cross_platform
            3. 灵魂发生器 + AI Client + 工具编排
            4. SSE 流式输出
            """
            import asyncio
            import json

            # 吟美虚拟主播命令拦截
            if request.message in ("/主播 on", "/主播 off"):
                try:
                    from plugins.yinmei.core.live_stream_hub import LiveStreamHub

                    hub = LiveStreamHub()
                    if request.message == "/主播 on":
                        hub.enable()
                        msg = "虚拟主播已开启"
                    else:
                        hub.disable()
                        msg = "虚拟主播已关闭"
                except Exception:
                    msg = "虚拟主播命令执行失败"

                async def toggle_sse():
                    yield f"data: {json.dumps({'content': msg, 'done': True})}\n\n"

                return StreamingResponse(toggle_sse(), media_type="text/event-stream")

            session_id = request.session_id or "default"
            platform = request.platform or "web"

            async def sse_generator():
                try:
                    from mlink.message import Message

                    lookup_id = request.usg_id or request.user_id or session_id
                    sendg_name = f"{platform}用户-{lookup_id[:8]}"

                    try:
                        import json as _json
                        from pathlib import Path

                        perms_file = Path("config/permissions.json")
                        if perms_file.exists():
                            perms_data = _json.loads(perms_file.read_text(encoding="utf-8"))
                            for u in perms_data.get("users", []):
                                uid_match = u.get("usg_id") or u.get("user_id")
                                if uid_match and str(uid_match) == str(lookup_id or ""):
                                    linked_to = u.get("linked_to")
                                    if linked_to:
                                        lookup_id = linked_to
                                        sendg_name = u.get("username", sendg_name)
                                    break
                    except Exception:
                        pass

                    perception = {
                        "platform": platform,
                        "content": request.message,
                        "usg_id": lookup_id,
                        "user_id": lookup_id,
                        "sendg_name": sendg_name,
                        "message_type": "private",
                    }

                    # 处理悬浮球截图：base64 → 视觉模型分析 → 注入上下文
                    if request.image_data:
                        try:
                            from core.game_play.engine import get_game_play_engine
                            from core.text_loader import get_text

                            engine = get_game_play_engine()
                            await engine.initialize()
                            analysis = await engine._call_vision(
                                get_text(
                                    "screen_vision.describe_prompt",
                                    "用中文描述当前屏幕上的内容。",
                                ),
                                request.image_data,
                                request.message or get_text("screen_vision.describe_default_query", "描述当前画面"),
                            )
                            if analysis:
                                perception["_image_analysis"] = {
                                    "success": True,
                                    "description": analysis,
                                    "labels": [],
                                    "model": "vision",
                                }
                                perception["image_analysis"] = perception["_image_analysis"]
                                logger.info(f"[WebChat] 悬浮球截图分析: {analysis[:80]}...")
                        except Exception as e:
                            logger.warning(f"[WebChat] 截图分析失败: {e}")

                    # 注入 is_owner 标记（桌面端超管权限）
                    try:
                        from core.unified_permission import get_permission_engine

                        engine = get_permission_engine()
                        if engine and engine.is_superadmin(str(lookup_id), platform=platform):
                            perception["is_owner"] = True
                            perception["canonical_user_id"] = str(lookup_id)
                    except Exception:
                        pass
                    message = Message(
                        msg_type="data",
                        content=perception,
                        source="web_api",
                        destination="decision_hub",
                    )

                    yield f"data: {json.dumps({'type': 'session_id', 'data': None, 'session_id': session_id}, ensure_ascii=False)}\n\n"
                    logger.debug(f"[SSE Chat] 已发送 session_id 事件: session_id={session_id}")

                    try:
                        response = await self.decision_hub.process_perception_cross_platform(message)

                        if not response:
                            response = "抱歉，弥娅无法处理这个请求呢。"

                        # TTS 本地播放 (fire-and-forget, 桌面/Web 端)
                        try:
                            import json as _json

                            with open("config/tts_config.json", "r", encoding="utf-8") as _f:
                                _cfg = _json.load(_f)
                            if _cfg.get("local_playback_enabled") and response:
                                asyncio.ensure_future(self._do_tts_local(response))
                        except Exception:
                            pass

                        response_data = {
                            "type": "plain",
                            "data": response,
                            "chain_type": "final",
                            "streaming": False,
                        }
                        yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"
                        logger.debug(
                            f"[SSE Chat] 已发送 plain 事件: response_len={len(response) if response else 0}, preview={response[:30] if response else 'None'}"
                        )

                        # 读取灵魂数据 (从 decision_hub._last_soul_output)
                        soul_ = getattr(self.decision_hub, "_last_soul_output", None)
                        if soul_:
                            yield f"data: {json.dumps({'type': 'soul', 'data': soul_}, ensure_ascii=False)}\n\n"

                        personality_ = (
                            self.decision_hub.personality.get_profile()
                            if self.decision_hub
                            and hasattr(self.decision_hub, "personality")
                            and self.decision_hub.personality
                            else None
                        )
                        if personality_:
                            yield f"data: {json.dumps({'type': 'personality', 'data': personality_}, ensure_ascii=False)}\n\n"

                        final_result = {
                            "response": response,
                            "timestamp": datetime.utcnow().isoformat(),
                            "personality": personality_,
                        }
                        yield f"data: {json.dumps({'type': 'done', 'data': final_result}, ensure_ascii=False)}\n\n"
                        logger.debug(f"[SSE Chat] 已发送 done 事件")

                    except asyncio.TimeoutError:
                        logger.error("[SSE Chat] 处理超时")
                        yield f"data: {json.dumps({'type': 'error', 'message': '处理超时，请稍后重试'}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error(f"[SSE Chat] 处理错误: {e}", exc_info=True)
                        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

                except Exception as gen_e:
                    logger.error(f"[SSE Generator] 错误: {gen_e}", exc_info=True)

            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.router.get("/api/platform/stats")
        async def get_platform_stats():
            """获取平台统计信息"""
            try:
                from config.platforms_config import (
                    get_enabled_platforms,
                    list_all_platforms,
                )

                platforms = list_all_platforms()
                enabled = get_enabled_platforms()
                return {
                    "online": len([p for p in platforms if p.get("id") in enabled]),
                    "total": len(platforms),
                    "platforms": [
                        {
                            "id": p.get("id"),
                            "name": p.get("name", p.get("id")),
                            "enable": p.get("id") in enabled,
                            "status": "running" if p.get("id") in enabled else "stopped",
                            "error_count": 0,
                        }
                        for p in platforms
                    ],
                }
            except Exception as e:
                logger.error(f"[Platform API] 获取平台统计失败: {e}")
                return {"online": 0, "total": 0, "platforms": [], "error": str(e)}

        @self.router.get("/api/config/platform/list")
        async def get_config_platform_list():
            """获取配置文件中的平台列表"""
            try:
                from config.platforms_config import (
                    get_enabled_platforms,
                    list_all_platforms,
                )

                all_ = list_all_platforms()
                enabled = get_enabled_platforms()
                return {
                    "success": True,
                    "platform": [
                        {
                            "id": p.get("id"),
                            "name": p.get("name", p.get("id")),
                            "enable": p.get("id") in enabled,
                            "type": p.get("id"),
                        }
                        for p in all_
                    ],
                }
            except Exception as e:
                return {"success": False, "platform": [], "error": str(e)}

        @self.router.post("/api/config/platform/new")
        async def add_new_platform(request: Dict = None):
            """添加新平台"""
            if request is None:
                request = {}
            try:
                platform_id = request.get("id")
                if not platform_id:
                    return {"success": False, "message": "缺少平台ID"}
                return {
                    "success": True,
                    "message": f"平台 {platform_id} 添加成功（需重启生效）",
                }
            except Exception as e:
                return {"success": False, "message": str(e)}

        @self.router.post("/api/config/platform/update")
        async def update_platform(request: Dict = None):
            """更新平台配置"""
            if request is None:
                request = {}
            try:
                platform_id = request.get("id")
                if not platform_id:
                    return {"success": False, "message": "缺少平台ID"}
                from config.platforms_config import get_enabled_platforms

                enabled = get_enabled_platforms()
                if request.get("enable"):
                    if platform_id not in enabled:
                        enabled.append(platform_id)
                else:
                    if platform_id in enabled:
                        enabled.remove(platform_id)
                return {"success": True, "message": f"平台 {platform_id} 更新成功"}
            except Exception as e:
                return {"success": False, "message": str(e)}

        @self.router.post("/api/config/platform/delete")
        async def delete_platform(request: Dict = None):
            """删除平台"""
            if request is None:
                request = {}
            try:
                platform_id = request.get("id")
                if not platform_id:
                    return {"success": False, "message": "缺少平台ID"}
                return {"success": True, "message": f"平台 {platform_id} 删除成功"}
            except Exception as e:
                return {"success": False, "message": str(e)}

        @self.router.get("/api/platform/template")
        async def get_platform_templates():
            """获取平台模板列表"""
            try:
                from config.platforms_config import PLATFORM_GUIDE

                templates = {}
                for k, v in PLATFORM_GUIDE.items():
                    templates[k] = {
                        "type": k,
                        "name": v.get("name", k),
                        "url": v.get("url", ""),
                        "credentials": v.get("credentials", []),
                    }
                return {"success": True, "templates": templates}
            except Exception as e:
                return {"success": False, "templates": {}, "error": str(e)}

        @self.router.get("/api/platform/capabilities")
        async def get_platform_capabilities():
            """获取平台能力信息"""
            return {
                "success": True,
                "capabilities": {
                    "qqofficial": {
                        "supports_group_chat": True,
                        "supports_private_chat": True,
                        "supports_image": True,
                    },
                    "telegram": {
                        "supports_group_chat": True,
                        "supports_private_chat": True,
                        "supports_image": True,
                        "supports_voice": True,
                    },
                    "discord": {
                        "supports_group_chat": True,
                        "supports_private_chat": True,
                        "supports_image": True,
                        "supports_voice": True,
                    },
                },
            }

        # ==================== Knowledge Base API ====================

        @self.router.get("/api/kb/list")
        async def list_knowledge_bases():
            return {"success": True, "data": {"items": []}}

        @self.router.post("/api/kb/create")
        async def create_knowledge_base(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "created"}

        @self.router.post("/api/kb/update")
        async def update_knowledge_base(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "updated"}

        @self.router.post("/api/kb/delete")
        async def delete_knowledge_base(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "deleted"}

        @self.router.get("/api/kb/get")
        async def get_knowledge_base(kb_id: str = ""):
            return {"success": True, "data": {"kb_id": kb_id}}

        @self.router.post("/api/kb/retrieve")
        async def retrieve_from_knowledge_base(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "data": {"items": []}}

        @self.router.get("/api/kb/document/list")
        async def list_kb_documents(kb_id: str = ""):
            return {"success": True, "data": {"items": []}}

        @self.router.get("/api/kb/document/get")
        async def get_kb_document(doc_id: str = ""):
            return {"success": True, "data": {"doc_id": doc_id}}

        @self.router.post("/api/kb/document/upload")
        async def upload_kb_document(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "uploaded"}

        @self.router.post("/api/kb/document/delete")
        async def delete_kb_document(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "deleted"}

        @self.router.get("/api/kb/chunk/list")
        async def list_kb_chunks(kb_id: str = "", doc_id: str = ""):
            return {"success": True, "data": {"items": []}}

        @self.router.post("/api/kb/chunk/delete")
        async def delete_kb_chunk(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "deleted"}

        # ==================== Memory API ====================

        @self.router.get("/api/memory/list")
        async def list_memories(level: str = "", limit: int = 20, offset: int = 0):
            return {"success": True, "data": {"items": []}}

        @self.router.post("/api/memory/add")
        async def add_memory(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "added"}

        @self.router.post("/api/memory/delete")
        async def delete_memory(request: Dict = None):
            if request is None:
                request = {}
            return {"success": True, "message": "deleted"}

        @self.router.get("/api/memory/search")
        async def search_memories(query: str = "", level: str = "", limit: int = 20):
            return {"success": True, "data": {"items": []}}

        @self.router.get("/api/memory/stats")
        async def get_memory_stats():
            return {"success": True, "data": {}}

        # ========== OpenAI 兼容 /v1/chat/completions（供 DSH 等调用） ==========
        @self.router.post("/v1/chat/completions")
        async def openai_chat_completions(request: dict):
            """OpenAI 兼容对话接口 - 内部代理到弥娅模型池

            透传 tools / tool_choice 参数，支持 stream 和非 stream 模式。
            返回标准 OpenAI chat.completion 响应（含 tool_calls）。
            由调用方（DSH 等）自行执行工具。
            """
            import json
            import time
            import uuid

            from starlette.responses import StreamingResponse

            model_name = request.get("model", "")
            messages = request.get("messages", [])
            temperature = request.get("temperature", 0.7)
            max_tokens = request.get("max_tokens", 2000)
            tools = request.get("tools")
            tool_choice = request.get("tool_choice")
            stream = request.get("stream", False)
            stream_options = request.get("stream_options")

            if not messages:
                raise HTTPException(status_code=400, detail="messages is required")

            try:
                from core.ai_client import AIMessage
                from core.model_pool_manager import ModelPoolManager

                pool = ModelPoolManager()
                client_wrapper = pool.create_ai_client(model_id=model_name)

                if not client_wrapper:
                    client_wrapper = pool.create_ai_client(task_type="simple_chat")

                if not client_wrapper:
                    raise HTTPException(status_code=503, detail="No available model client")

                if not client_wrapper.client:
                    raise HTTPException(
                        status_code=503,
                        detail="Model client not initialized",
                    )

                def _normalize_content(content) -> str:
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    parts.append(block.get("text", ""))
                                elif block.get("type") == "image_url":
                                    img = block.get("image_url", {})
                                    parts.append(img.get("url", "") if isinstance(img, dict) else str(img))
                                else:
                                    parts.append(str(block))
                            else:
                                parts.append(str(block))
                        return "\n".join(parts)
                    return str(content)

                ai_messages = [
                    AIMessage(
                        role=m.get("role", "user"),
                        content=_normalize_content(m.get("content", "")),
                        tool_calls=m.get("tool_calls"),
                        tool_call_id=m.get("tool_call_id"),
                    )
                    for m in messages
                ]

                openai_messages = client_wrapper._convert_messages_to_openai_format(ai_messages)

                request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

                request_params = {
                    "model": client_wrapper.model,
                    "messages": openai_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }

                if stream and stream_options:
                    request_params["stream_options"] = stream_options

                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = client_wrapper._normalize_tool_choice(tool_choice or "auto")
                elif tool_choice:
                    request_params["tool_choice"] = tool_choice

                if stream:

                    async def generate_sse():
                        created = int(time.time())
                        try:
                            response_stream = await client_wrapper.client.chat.completions.create(**request_params)
                            async for chunk in response_stream:
                                chunk_dict = chunk.model_dump()
                                chunk_dict.setdefault("id", request_id)
                                chunk_dict.setdefault("object", "chat.completion.chunk")
                                chunk_dict.setdefault("created", created)
                                chunk_dict.setdefault("model", client_wrapper.model)
                                data = json.dumps(chunk_dict, ensure_ascii=False)
                                yield f"data: {data}\n\n"
                            yield "data: [DONE]\n\n"
                        except Exception as e:
                            logger.error(f"[OpenAI兼容] SSE 流失败: {e}", exc_info=True)
                            error_chunk = json.dumps(
                                {
                                    "id": request_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": client_wrapper.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "content": None,
                                            },
                                            "finish_reason": "error",
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                            yield f"data: {error_chunk}\n\n"
                            yield "data: [DONE]\n\n"

                    return StreamingResponse(
                        generate_sse(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                        },
                    )

                # 非 stream 模式（原逻辑）
                response = await client_wrapper.client.chat.completions.create(**request_params)

                choice = response.choices[0]
                msg = choice.message

                message_dict = {"role": "assistant", "content": msg.content or ""}

                if msg.tool_calls:
                    message_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]

                return {
                    "id": request_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": client_wrapper.model,
                    "choices": [
                        {
                            "index": 0,
                            "message": message_dict,
                            "finish_reason": "tool_calls" if msg.tool_calls else (choice.finish_reason or "stop"),
                        }
                    ],
                    "usage": {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                        "total_tokens": getattr(response.usage, "total_tokens", 0),
                    },
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[OpenAI兼容] chat/completions 失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def health_check():
            """健康检查"""
            from datetime import datetime

            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "miya-web-api",
            }

        @self.router.get("/api/health")
        async def api_health_check():
            """API健康检查"""
            from datetime import datetime

            return {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "miya-web-api",
            }

        # ── Emoji / 表情包 API ──

        @self.router.get("/api/emoji/list")
        async def list_emoji():
            """获取表情包列表（分类 + 文件 URL）"""
            try:
                import json
                from pathlib import Path

                emoji_dir = Path("data/emoji")
                if not emoji_dir.exists():
                    return {"categories": []}

                categories = []
                for cat_dir in sorted(emoji_dir.iterdir()):
                    if not cat_dir.is_dir():
                        continue
                    files = []
                    for f in sorted(cat_dir.iterdir()):
                        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                            files.append(
                                {
                                    "name": f.name,
                                    "url": f"/api/emoji/file/{cat_dir.name}/{f.name}",
                                }
                            )
                    if files:
                        categories.append({"name": cat_dir.name, "files": files})

                # Also check stickers directory
                sticker_dir = Path("data/stickers")
                if sticker_dir.exists():
                    for cat_dir in sorted(sticker_dir.iterdir()):
                        if not cat_dir.is_dir():
                            continue
                        files = []
                        for f in sorted(cat_dir.iterdir()):
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                                files.append(
                                    {
                                        "name": f.name,
                                        "url": f"/api/emoji/file/stickers/{cat_dir.name}/{f.name}",
                                    }
                                )
                        if files:
                            categories.append({"name": f"贴纸-{cat_dir.name}", "files": files})

                return {"categories": categories}
            except Exception as e:
                logger.error(f"[EmojiAPI] 列表获取失败: {e}")
                return {"categories": [], "error": str(e)}

        @self.router.get("/api/emoji/file/{category}/{filename:path}")
        async def serve_emoji_file(category: str, filename: str):
            """提供表情包图片文件"""
            from pathlib import Path

            import aiofiles
            from fastapi.responses import FileResponse

            possible_paths = [
                Path("data/emoji") / category / filename,
                Path("data/stickers") / category / filename,
            ]
            for file_path in possible_paths:
                if file_path.exists() and file_path.is_file():
                    media_type_map = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                    }
                    media_type = media_type_map.get(file_path.suffix.lower(), "application/octet-stream")
                    return FileResponse(str(file_path), media_type=media_type)

            raise HTTPException(status_code=404, detail="Emoji file not found")

        @self.router.get("/api/chat/pending/{user_id}")
        async def get_pending_messages(user_id: str):
            """获取并清除移动端的待发送主动消息 (v9.0: 合并 default 队列)"""
            try:
                pending = getattr(self.decision_hub, "_mobile_pending", {})
                msgs = pending.pop(str(user_id), [])
                # v9.0: 如果用户队列为空，也提供 default 兜底队列
                if not msgs and user_id != "default":
                    msgs = pending.pop("default", [])
                return {"messages": msgs}
            except Exception:
                return {"messages": []}

        @self.router.post("/api/chat/upload")
        async def upload_file(file: UploadFile):
            """文件上传 — 保存到 data/downloads/ 并返回分析"""
            import os
            from pathlib import Path

            try:
                upload_dir = Path("data/downloads")
                upload_dir.mkdir(parents=True, exist_ok=True)

                safe_name = file.filename or "unknown_file"
                file_path = upload_dir / safe_name

                content = await file.read()
                file_path.write_bytes(content)

                result: dict = {"success": True, "path": str(file_path), "name": safe_name, "size": len(content)}

                is_text = (file.content_type or "").startswith("text/") or safe_name.endswith(
                    (".txt", ".md", ".json", ".xml", ".yaml", ".yml", ".py", ".js", ".html", ".css", ".log")
                )
                if is_text:
                    try:
                        text = content.decode("utf-8")[:5000]
                        result["preview"] = text
                    except Exception:
                        result["preview"] = "[无法解码]"
                else:
                    result["preview"] = f"[二进制文件: {file.content_type}, {len(content)} bytes]"

                logger.info(f"[Upload] 收到文件: {safe_name} ({len(content)} bytes)")
                return result
            except Exception as e:
                logger.error(f"[Upload] 失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _do_tts_local(self, text: str):
        """TTS 本地播放 (fire-and-forget)"""
        try:
            from core.tts.engine_router import synthesize

            audio_path = await synthesize(text)
            if not audio_path:
                return

            from core.audio_player import play_audio_isolated

            play_audio_isolated(audio_path)
        except ImportError:
            pass
        except Exception:
            pass

    def get_router(self):
        """获取 API 路由器"""
        return self.router


# 公开接口列表
__all__ = [
    "WebAPI",
    "create_web_api",
    # 模型
    "BlogPostCreate",
    "BlogPostUpdate",
    "UserRegister",
    "UserLogin",
    "ChatRequest",
    "TerminalChatRequest",
    "GitHubConfig",
    "ToolExecuteRequest",
]


# 向后兼容：创建函数式接口
def create_web_api(web_net: Any, decision_hub: Any, github_store: Any = None) -> Optional[WebAPI]:
    """创建 Web API 实例（向后兼容）

    Args:
        web_net: WebNet 实例
        decision_hub: DecisionHub 实例
        github_store: GitHubStore 实例 (可选)

    Returns:
        WebAPI 实例，如果 FastAPI 不可用则返回 None
    """
    try:
        return WebAPI(web_net, decision_hub, github_store)
    except Exception as e:
        logger.error(f"[WebAPI] 创建失败: {e}")
        return None
