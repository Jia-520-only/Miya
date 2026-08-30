"""
弥娅管理 API (REST + WebSocket)

提供平台热插拔的控制面和实时状态推送。

REST 端点:
  GET    /api/v1/health              - 系统健康检查
  GET    /api/v1/platforms            - 获取所有平台状态
  GET    /api/v1/platforms/{id}       - 获取单个平台状态
  POST   /api/v1/platforms/{id}/start    - 启动平台
  POST   /api/v1/platforms/{id}/stop     - 停止平台
  POST   /api/v1/platforms/{id}/restart  - 重启平台
  GET    /api/v1/daemon/status        - 守护进程状态
  GET    /api/v1/logs                 - 后台终端日志快照
  GET    /api/v1/logs/stream          - 后台终端日志实时流 (SSE)

WebSocket:
  WS /api/v1/ws                      - 实时事件流

Usage:
    from core.management_api import ManagementAPI
    api = ManagementAPI(daemon)
    await api.serve(port=9800)
"""

from __future__ import annotations

import asyncio
import contextlib
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Set

import uvicorn
from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

logger = logging.getLogger("Miya.ManagementAPI")

_global_management_api: Optional[ManagementAPI] = None


def set_management_api(api: ManagementAPI):
    global _global_management_api
    _global_management_api = api


def get_management_api() -> Optional[ManagementAPI]:
    return _global_management_api


class ManagementAPI:
    """弥娅管理 API 服务器"""

    def __init__(self, daemon, host: str = "0.0.0.0", port: int = 9800):
        self.daemon = daemon
        self.host = host
        self.port = port
        self.app = FastAPI(title="Miya Management API", version="4.1.11")
        self._ws_clients: Set[WebSocket] = set()
        self._ws_client_types: Dict[WebSocket, str] = {}
        self._ws_client_users: Dict[WebSocket, str] = {}
        self._server: Optional[uvicorn.Server] = None
        self._serve_task: Optional[asyncio.Task] = None

        self._setup_middleware()
        self._setup_routes()

    def register_webhook_platforms(self):
        """v7.0: 注册 webhook 平台的 FastAPI 路由"""
        for _pid, inst in self.daemon.registry._instances.items():
            if hasattr(inst, "get_webhook_routes"):
                try:
                    webhook_info = inst.get_webhook_routes()
                    if not webhook_info:
                        continue
                    prefix = webhook_info.get("prefix", "")
                    routes = webhook_info.get("routes", [])
                    if not routes:
                        continue

                    router = APIRouter(prefix=prefix)
                    for method, path, handler in routes:
                        handler.__name__ = f"{_pid}_webhook"
                        router.add_api_route(
                            path if path else "/",
                            endpoint=handler,
                            methods=[method],
                        )
                    self.app.include_router(router)
                    logger.info(f"[Webhook] 注册 {_pid} ({prefix})")
                except Exception as e:
                    logger.warning(f"[Webhook] {_pid} 注册失败: {e}")

    def _setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """注册所有路由"""
        app = self.app

        @app.get("/api/v1/health")
        async def health_check():
            daemon_status = self.daemon.get_daemon_status()
            return {
                "status": "ok" if daemon_status["started"] else "starting",
                "timestamp": datetime.now().isoformat(),
                **daemon_status,
            }

        @app.get("/api/soul/current")
        async def get_current_soul():
            """获取当前灵魂数据（供桌面端情绪面板）"""
            try:
                dh = getattr(getattr(self.daemon, "_miya", None), "decision_hub", None)
                if dh:
                    # 优先读取 _last_soul_data (灵魂发生器直接写入)
                    soul_data = getattr(dh, "_last_soul_data", None)
                    if soul_data and soul_data.get("emotions"):
                        return soul_data
                    soul = getattr(dh, "_last_soul_output", None)
                    if soul:
                        return soul
            except Exception:
                pass
            return {}

        @app.get("/api/v1/platforms")
        async def list_platforms():
            return {
                "platforms": self.daemon.get_platform_status(),
                "total": len(self.daemon.get_platform_status()),
                "online": self.daemon.get_daemon_status()["platforms"]["online"],
            }

        @app.get("/api/v1/platforms/{platform_id}")
        async def get_platform(platform_id: str):
            stats = self.daemon.get_platform_status()
            for p in stats:
                if p["platform_id"] == platform_id:
                    return p
            return {"error": "platform not found", "platform_id": platform_id}

        @app.post("/api/v1/platforms/{platform_id}/start")
        async def start_platform(platform_id: str):
            success = await self.daemon.start_platform(platform_id)
            return {
                "platform_id": platform_id,
                "action": "start",
                "success": success,
            }

        @app.post("/api/v1/platforms/{platform_id}/stop")
        async def stop_platform(platform_id: str):
            success = await self.daemon.stop_platform(platform_id)
            return {
                "platform_id": platform_id,
                "action": "stop",
                "success": success,
            }

        @app.post("/api/v1/platforms/{platform_id}/restart")
        async def restart_platform(platform_id: str):
            success = await self.daemon.restart_platform(platform_id)
            return {
                "platform_id": platform_id,
                "action": "restart",
                "success": success,
            }

        @app.get("/api/v1/daemon/status")
        async def daemon_status():
            return self.daemon.get_daemon_status()

        # ======== 跨平台统一消息 (v8.1) ========

        @app.get("/api/v1/messages")
        async def query_messages(
            platform_id: str = "",
            user_id: str = "",
            direction: str = "",
            sender_name: str = "",
            limit: int = 50,
            offset: int = 0,
        ):
            """查询跨平台消息"""
            from core.unified_message_store import get_unified_message_store

            store = get_unified_message_store()
            messages = await store.query_messages(
                platform_id=platform_id or None,
                user_id=user_id or None,
                direction=direction or None,
                sender_name=sender_name or None,
                limit=min(limit, 500),
                offset=offset,
            )
            count = await store.get_message_count(platform_id=platform_id or None)
            return {
                "messages": messages,
                "total": count,
                "limit": limit,
                "offset": offset,
            }

        @app.post("/api/v1/messages")
        async def record_message(request: Request):
            """记录一条消息到跨平台存储"""
            try:
                body = await request.json()
            except Exception:
                return {"error": "需要 JSON body"}

            from core.unified_message_store import get_unified_message_store

            store = get_unified_message_store()
            record_id = await store.record_message(
                platform_id=body.get("platform_id", "unknown"),
                user_id=body.get("user_id", "unknown"),
                sender_id=body.get("sender_id"),
                sender_name=body.get("sender_name"),
                content=body.get("content"),
                direction=body.get("direction", "in"),
                message_id=body.get("message_id"),
                reply_to_message_id=body.get("reply_to_message_id"),
                group_id=body.get("group_id"),
                text=body.get("text"),
            )
            return {"success": record_id is not None, "id": record_id}

        @app.post("/api/v1/messages/reply")
        async def record_miya_reply(request: Request):
            """记录弥娅发出的回复"""
            try:
                body = await request.json()
            except Exception:
                return {"error": "需要 JSON body"}

            from core.unified_message_store import get_unified_message_store

            store = get_unified_message_store()
            record_id = await store.record_miya_reply(
                platform_id=body.get("platform_id", "unknown"),
                user_id=body.get("user_id", "unknown"),
                content_text=body.get("text", ""),
                reply_to_message_id=body.get("reply_to_message_id"),
                sender_name=body.get("sender_name", "弥娅"),
                group_id=body.get("group_id"),
            )
            return {"success": record_id is not None, "id": record_id}

        @app.get("/api/v1/messages/search")
        async def search_messages(
            keyword: str = "",
            platform_id: str = "",
            direction: str = "",
            limit: int = 50,
            offset: int = 0,
        ):
            """跨平台消息全文搜索"""
            if not keyword:
                return {"messages": [], "total": 0}

            from core.unified_message_store import get_unified_message_store

            store = get_unified_message_store()
            messages = await store.search_messages(
                keyword=keyword,
                platform_id=platform_id or None,
                direction=direction or None,
                limit=min(limit, 200),
                offset=offset,
            )
            return {
                "messages": messages,
                "total": len(messages),
                "keyword": keyword,
            }

        # ======== 权限管理 (v7.0) ========

        @app.get("/api/v1/auth/status")
        async def auth_status():
            engine = self.daemon.permission_engine
            return engine.get_stats()

        @app.get("/api/v1/auth/roles")
        async def list_roles():
            engine = self.daemon.permission_engine
            return {"roles": engine.list_roles()}

        @app.get("/api/v1/auth/users")
        async def list_users():
            engine = self.daemon.permission_engine
            return {"users": engine.list_users()}

        @app.get("/api/v1/auth/users/{user_id}")
        async def get_user(user_id: str):
            engine = self.daemon.permission_engine
            groups = engine.get_user_groups(user_id)
            perms = engine.get_user_permissions_list(user_id)
            is_super = engine.is_superadmin(user_id)
            return {
                "user_id": user_id,
                "groups": groups,
                "permissions": perms,
                "is_superadmin": is_super,
                "role_level": engine.get_role_level(user_id),
            }

        @app.post("/api/v1/auth/users/{user_id}/grant")
        async def grant_role(user_id: str, request: Request):
            try:
                body = await request.json()
            except Exception:
                return {"error": "需要 JSON body: {platform, groups, username?}"}
            engine = self.daemon.permission_engine
            ok = engine.grant_role(
                user_id=user_id,
                platform=body.get("platform", ""),
                username=body.get("username", user_id),
                groups=body.get("groups", []),
            )
            return {"success": ok, "user_id": user_id}

        @app.post("/api/v1/auth/users/{user_id}/revoke")
        async def revoke_role(user_id: str, request: Request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            engine = self.daemon.permission_engine
            ok = engine.revoke_role(user_id=user_id, groups=body.get("groups"))
            return {"success": ok, "user_id": user_id}

        @app.get("/api/v1/auth/check/{user_id}")
        async def check_permission(user_id: str, permission: str = ""):
            engine = self.daemon.permission_engine
            if not permission:
                return {"error": "需要 ?permission=xxx 参数"}
            return {
                "user_id": user_id,
                "permission": permission,
                "allowed": engine.check(user_id, permission),
            }

        # ======== 后台终端日志流 ========

        @app.get("/api/v1/logs")
        async def get_logs(limit: int = 500, level: str = ""):
            """后台终端日志快照（环形缓冲最近 limit 条）"""
            from core.log_stream import get_log_buffer

            entries, latest = get_log_buffer().snapshot(min(max(limit, 1), 2000))
            if level:
                entries = [e for e in entries if e["level"] == level.upper()]
            return {"entries": entries, "latest_seq": latest}

        @app.get("/api/v1/logs/stream")
        async def logs_stream(since: int = 0):
            """后台终端日志实时流 (SSE)

            since<=0 时先补发缓冲尾部；之后每 0.25s 推增量。
            客户端断线重连时带 ?since=<latest_seq> 续传；缓冲溢出发 reset 事件。
            """
            from core.log_stream import get_log_buffer

            buf = get_log_buffer()

            def sse(payload: Dict) -> str:
                return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

            async def gen():
                last = since
                if since <= 0:
                    entries, latest = buf.snapshot(500)
                    last = latest
                    yield sse({"type": "init", "entries": entries, "latest_seq": latest})
                last_beat = time.time()
                while True:
                    result = buf.since(last)
                    if result["overrun"]:
                        entries, latest = buf.snapshot(500)
                        last = latest
                        yield sse({"type": "reset", "entries": entries, "latest_seq": latest})
                        last_beat = time.time()
                    elif result["entries"]:
                        last = result["latest_seq"]
                        yield sse({"type": "logs", "entries": result["entries"]})
                        last_beat = time.time()
                    elif time.time() - last_beat >= 15.0:
                        yield ": ping\n\n"
                        last_beat = time.time()
                    await asyncio.sleep(0.25)

            return StreamingResponse(
                gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        @app.websocket("/api/v1/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._ws_clients.add(ws)
            self._ws_client_types[ws] = ws.query_params.get("client_type", "unknown")
            self._ws_client_users[ws] = ws.query_params.get("user_id", "")
            logger.info(
                f"WS 客户端连接 type={self._ws_client_types.get(ws)}"
                f" user={self._ws_client_users.get(ws)}"
                f" (总数: {len(self._ws_clients)})"
            )

            await ws.send_json(
                {
                    "type": "initial_state",
                    "timestamp": datetime.now().isoformat(),
                    "platforms": self.daemon.get_platform_status(),
                    "daemon": self.daemon.get_daemon_status(),
                }
            )

            try:
                while True:
                    data = await ws.receive_text()
                    try:
                        msg = json.loads(data)
                        await self._handle_ws_message(ws, msg)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "message": "Invalid JSON"})
            except WebSocketDisconnect:
                pass
            finally:
                self._ws_clients.discard(ws)
                self._ws_client_types.pop(ws, None)
                self._ws_client_users.pop(ws, None)
                logger.info(f"WS 客户端断开 (剩余: {len(self._ws_clients)})")

    async def _handle_ws_message(self, ws: WebSocket, msg: Dict):
        """处理 WebSocket 客户端消息"""
        action = msg.get("action", "")
        platform_id = msg.get("platform_id", "")

        if action == "start_platform" and platform_id:
            success = await self.daemon.start_platform(platform_id)
            await ws.send_json({"type": "action_result", "action": action, "success": success})
        elif action == "stop_platform" and platform_id:
            success = await self.daemon.stop_platform(platform_id)
            await ws.send_json({"type": "action_result", "action": action, "success": success})
        elif action == "restart_platform" and platform_id:
            success = await self.daemon.restart_platform(platform_id)
            await ws.send_json({"type": "action_result", "action": action, "success": success})
        elif action == "get_status":
            await ws.send_json(
                {
                    "type": "status_update",
                    "platforms": self.daemon.get_platform_status(),
                    "daemon": self.daemon.get_daemon_status(),
                }
            )
        else:
            await ws.send_json({"type": "error", "message": f"Unknown action: {action}"})

    async def broadcast_event(self, event: Dict):
        """向所有 WebSocket 客户端广播平台事件"""
        payload = {
            "type": "platform_event",
            "timestamp": datetime.now().isoformat(),
            **event,
        }
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    async def broadcast_message(
        self,
        content: str,
        platform: str = "",
        platform_name: str = "",
        sender_name: str = "",
        sender_id: str = "",
        user_id: str = "",
        direction: str = "in",
        message_id: str = "",
        reply_to_message_id: str = "",
        timestamp: str = "",
        group_id: str = "",
    ):
        """向所有 WebSocket 客户端广播跨平台消息"""
        payload = {
            "type": "new_message",
            "timestamp": timestamp or datetime.now().isoformat(),
            "data": {
                "content": content,
                "platform": platform,
                "platform_name": platform_name,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "user_id": user_id,
                "direction": direction,
                "message_id": message_id,
                "reply_to_message_id": reply_to_message_id,
                "group_id": group_id,
                "timestamp": timestamp or datetime.now().isoformat(),
            },
        }
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    async def push_to_client_type(
        self,
        client_type: str,
        user_id: str = "",
        payload: dict = None,
    ):
        """向指定类型的 WebSocket 客户端推送消息 (v9.0)

        Args:
            client_type: 客户端类型 (mobile, desktop, web, unknown)
            user_id: 目标用户 ID (空则推送给所有该类型客户端)
            payload: 推送数据
        """
        if not payload:
            return
        dead = set()
        for ws in self._ws_clients:
            ws_type = self._ws_client_types.get(ws, "unknown")
            ws_user = self._ws_client_users.get(ws, "")
            if ws_type == client_type or client_type == "all":
                if not user_id or ws_user == user_id:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead.add(ws)
        self._ws_clients -= dead
        for ws in dead:
            self._ws_client_types.pop(ws, None)
            self._ws_client_users.pop(ws, None)

    async def push_mobile_pending(
        self,
        user_id: str,
        message_count: int = 0,
    ):
        """通知手机端有待发送消息 (v9.0)"""
        payload = {
            "type": "mobile_pending",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "user_id": user_id,
                "message_count": message_count,
                "action": "poll_pending",
            },
        }
        await self.push_to_client_type("mobile", user_id=user_id, payload=payload)

    async def push_proactive_message(
        self,
        user_id: str,
        message: str,
        platform: str = "",
        target_client: str = "desktop",
    ):
        """向桌面/Web 端推送主动消息 (v9.0: WS 直推)"""
        payload = {
            "type": "proactive_message",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "user_id": user_id,
                "message": message,
                "platform": platform,
            },
        }
        await self.push_to_client_type(target_client, user_id=user_id, payload=payload)

    def register_platform_awareness_callbacks(self):
        """注册平台感知 WS 推送回调 (v9.0)"""
        try:
            from core.platform_awareness import get_platform_awareness

            awareness = get_platform_awareness()

            async def _ws_push(event_type: str, **kwargs):
                if event_type == "mobile_pending":
                    await self.push_mobile_pending(
                        user_id=kwargs.get("user_id", ""),
                        message_count=kwargs.get("pending_count", 0),
                    )
                elif event_type == "proactive_desktop":
                    await self.push_proactive_message(
                        user_id=kwargs.get("user_id", ""),
                        message=kwargs.get("message", ""),
                        platform=kwargs.get("platform", ""),
                        target_client="desktop",
                    )

            awareness.set_ws_push_callback(_ws_push)
            logger.info("[ManagementAPI] 平台感知 WS 推送回调已注册")
        except Exception as e:
            logger.warning(f"[ManagementAPI] 平台感知回调注册失败: {e}")

    async def serve(self, block: bool = True):
        """启动 API 服务器"""
        self.register_platform_awareness_callbacks()
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)

        if block:
            await self._server.serve()
        else:
            self._serve_task = asyncio.create_task(self._server.serve())
            await asyncio.sleep(0.1)

    async def stop(self):
        """停止 API 服务器"""
        if self._server:
            self._server.should_exit = True
        if self._serve_task and not self._serve_task.done():
            self._serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._serve_task
