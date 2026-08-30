"""弥娅Runtime API服务器

整合Undefined的Runtime API能力：
- WebUI支持
- OpenAPI文档
- 探针接口
- 记忆查询API
- 配置管理
- 交互端管理
"""

import asyncio
import json
import logging
import platform
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.constants import HTTPStatus

try:
    from aiohttp import web, ClientSession, ClientTimeout
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logging.warning("[Runtime API] aiohttp未安装，Runtime API将不可用")

logger = logging.getLogger(__name__)


@dataclass
class EndpointStatus:
    """交互端状态"""
    id: str
    name: str
    type: str
    status: str  # running, stopped, error
    config: Dict[str, Any]
    stats: Dict[str, Any]
    started_at: Optional[float] = None
    last_error: Optional[str] = None


class RuntimeAPIServer:
    """
    运行时API服务器
    
    提供：
    - RESTful API
    - WebUI支持
    - 系统监控
    - 交互端管理
    - 记忆查询
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        auth_key: Optional[str] = None,
    ):
        """初始化Runtime API服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            auth_key: 认证密钥
        """
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("[Runtime API] aiohttp未安装")
        
        self.host = host
        self.port = port
        self.auth_key = auth_key
        
        # 交互端管理
        self.endpoints: Dict[str, EndpointStatus] = {}
        self.endpoints_lock = asyncio.Lock()
        
        # 依赖的服务
        self.cognitive_memory = None
        self.skills_registry = None
        
        # 启动时间
        self.start_time = time.time()
        
        # aiohttp应用
        self.app = web.Application()
        self._setup_routes()
        
        # Web服务器
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
    
    def _setup_routes(self):
        """设置路由"""
        # 系统状态
        self.app.router.add_get("/api/probe", self.handle_probe)
        self.app.router.add_get("/api/status", self.handle_status)
        
        # 交互端管理
        self.app.router.add_get("/api/endpoints", self.handle_list_endpoints)
        self.app.router.add_post("/api/endpoints/{id}/start", self.handle_start_endpoint)
        self.app.router.add_post("/api/endpoints/{id}/stop", self.handle_stop_endpoint)
        self.app.router.add_get("/api/endpoints/{id}", self.handle_get_endpoint)
        
        # 认知记忆
        self.app.router.add_get("/api/cognitive/events", self.handle_cognitive_events)
        self.app.router.add_get("/api/cognitive/profiles", self.handle_cognitive_profiles)
        
        # Agent管理
        self.app.router.add_get("/api/agents", self.handle_list_agents)
        self.app.router.add_get("/api/agents/stats", self.handle_agent_stats)
        
        # 配置管理
        self.app.router.add_get("/api/config", self.handle_get_config)
        self.app.router.add_post("/api/config", self.handle_update_config)
        
        # 统计数据
        self.app.router.add_get("/api/stats", self.handle_stats)
        
        # WebUI支持
        self.app.router.add_get("/api/chat", self.handle_chat)
        
        # 健康检查
        self.app.router.add_get("/health", self.handle_health)
        
        # 静态文件（WebUI）
        self.app.router.add_static("/static", "pc_ui", name="static")
    
    def set_cognitive_memory(self, cognitive_memory):
        """设置认知记忆系统"""
        self.cognitive_memory = cognitive_memory
    
    def set_skills_registry(self, skills_registry):
        """设置Skills注册表"""
        self.skills_registry = skills_registry
    
    async def start(self):
        """启动API服务器"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        logger.info(
            f"[Runtime API] 服务器已启动: http://{self.host}:{self.port}"
        )
    
    async def stop(self):
        """停止API服务器"""
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("[Runtime API] 服务器已停止")
    
    def _check_auth(self, request: web.Request) -> bool:
        """检查认证"""
        if not self.auth_key:
            return True
        
        auth_header = request.headers.get("X-Miya-API-Key", "")
        return auth_header == self.auth_key
    
    async def _json_response(self, data: Any, status: int = HTTPStatus.OK):
        """返回JSON响应"""
        return web.json_response(data, status=status)

    async def _error_response(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        """返回错误响应"""
        return web.json_response({"error": message}, status=status)
    
    # ========== 系统状态 ==========
    
    async def handle_probe(self, request: web.Request):
        """探针接口"""
        return await self._json_response({
            "status": "ok",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
        })
    
    async def handle_status(self, request: web.Request):
        """系统状态"""
        status = {
            "status": "running",
            "uptime": time.time() - self.start_time,
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "endpoints": {
                "total": len(self.endpoints),
                "running": sum(
                    1 for ep in self.endpoints.values()
                    if ep.status == "running"
                ),
                "stopped": sum(
                    1 for ep in self.endpoints.values()
                    if ep.status == "stopped"
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }
        
        return await self._json_response(status)
    
    # ========== 交互端管理 ==========
    
    async def handle_list_endpoints(self, request: web.Request):
        """获取所有交互端"""
        async with self.endpoints_lock:
            endpoints = [
                {
                    "id": ep.id,
                    "name": ep.name,
                    "type": ep.type,
                    "status": ep.status,
                    "config": ep.config,
                    "stats": ep.stats,
                    "started_at": ep.started_at,
                    "last_error": ep.last_error,
                }
                for ep in self.endpoints.values()
            ]
        
        return await self._json_response({"endpoints": endpoints})
    
    async def handle_get_endpoint(self, request: web.Request):
        """获取单个交互端"""
        endpoint_id = request.match_info["id"]

        async with self.endpoints_lock:
            endpoint = self.endpoints.get(endpoint_id)

        if not endpoint:
            return await self._error_response("交互端不存在", HTTPStatus.NOT_FOUND)

        return await self._json_response({
            "id": endpoint.id,
            "name": endpoint.name,
            "type": endpoint.type,
            "status": endpoint.status,
            "config": endpoint.config,
            "stats": endpoint.stats,
            "started_at": endpoint.started_at,
            "last_error": endpoint.last_error,
        })

    async def handle_start_endpoint(self, request: web.Request):
        """启动交互端"""
        endpoint_id = request.match_info["id"]

        async with self.endpoints_lock:
            endpoint = self.endpoints.get(endpoint_id)

        if not endpoint:
            return await self._error_response("交互端不存在", HTTPStatus.NOT_FOUND)

        if endpoint.status == "running":
            return await self._error_response("交互端已在运行", HTTPStatus.BAD_REQUEST)

        # TODO: 实际启动逻辑
        endpoint.status = "running"
        endpoint.started_at = time.time()
        endpoint.last_error = None

        logger.info(f"[Runtime API] 启动交互端: {endpoint_id}")

        return await self._json_response({"status": "started"})

    async def handle_stop_endpoint(self, request: web.Request):
        """停止交互端"""
        endpoint_id = request.match_info["id"]

        async with self.endpoints_lock:
            endpoint = self.endpoints.get(endpoint_id)

        if not endpoint:
            return await self._error_response("交互端不存在", HTTPStatus.NOT_FOUND)

        if endpoint.status != "running":
            return await self._error_response("交互端未在运行", HTTPStatus.BAD_REQUEST)

        # TODO: 实际停止逻辑
        endpoint.status = "stopped"
        endpoint.started_at = None

        logger.info(f"[Runtime API] 停止交互端: {endpoint_id}")

        return await self._json_response({"status": "stopped"})
    
    # ========== 认知记忆 ==========

    async def handle_cognitive_events(self, request: web.Request):
        """搜索认知事件"""
        query = request.query.get("query", "")
        user_id = request.query.get("user_id", "")
        group_id = request.query.get("group_id", "")
        top_k = int(request.query.get("top_k", 10))

        if not self.cognitive_memory:
            return await self._error_response("认知记忆系统未初始化", HTTPStatus.INTERNAL_ERROR)

        events = await self.cognitive_memory.search_cognitive_events(
            query=query,
            user_id=user_id,
            group_id=group_id,
            top_k=top_k,
        )

        return await self._json_response({
            "events": [
                {
                    "content": event.content,
                    "user_id": event.user_id,
                    "group_id": event.group_id,
                    "timestamp_utc": event.timestamp_utc,
                }
                for event in events
            ]
        })
    
    async def handle_cognitive_profiles(self, request: web.Request):
        """获取侧写"""
        user_id = request.query.get("user_id", "")
        group_id = request.query.get("group_id", "")

        if not self.cognitive_memory:
            return await self._error_response("认知记忆系统未初始化", HTTPStatus.INTERNAL_ERROR)

        result = {}

        if user_id:
            profile = self.cognitive_memory.get_user_profile(user_id)
            if profile:
                result["user"] = {"id": user_id, "profile": profile}

        if group_id:
            profile = self.cognitive_memory.get_group_profile(group_id)
            if profile:
                result["group"] = {"id": group_id, "profile": profile}

        return await self._json_response(result)
    
    # ========== Agent管理 ==========

    async def handle_list_agents(self, request: web.Request):
        """获取所有Agent"""
        if not self.skills_registry:
            return await self._error_response("Skills注册表未初始化", HTTPStatus.INTERNAL_ERROR)

        agents = self.skills_registry.get_items()

        return await self._json_response({
            "agents": [
                {
                    "name": name,
                    "description": item.get_description(),
                    "stats": self.skills_registry.get_stats(name).to_dict(),
                }
                for name, item in agents.items()
            ]
        })

    async def handle_agent_stats(self, request: web.Request):
        """获取Agent统计"""
        if not self.skills_registry:
            return await self._error_response("Skills注册表未初始化", HTTPStatus.INTERNAL_ERROR)

        stats = self.skills_registry.get_stats()
        
        return await self._json_response({
            "agents": {
                name: stat.to_dict()
                for name, stat in stats.items()
            }
        })
    
    # ========== 配置管理 ==========
    
    async def handle_get_config(self, request: web.Request):
        """获取配置"""
        # TODO: 实现配置获取
        return await self._json_response({"config": {}})
    
    async def handle_update_config(self, request: web.Request):
        """更新配置"""
        # TODO: 实现配置更新
        return await self._json_response({"status": "updated"})
    
    # ========== 统计数据 ==========
    
    async def handle_stats(self, request: web.Request):
        """获取统计数据"""
        stats = {
            "uptime": time.time() - self.start_time,
            "endpoints": len(self.endpoints),
            "memory": {},  # TODO: 添加内存统计
            "performance": {},  # TODO: 添加性能统计
        }
        
        return await self._json_response(stats)
    
    # ========== WebUI Chat ==========
    
    async def handle_chat(self, request: web.Request):
        """聊天接口（支持终端代理）"""
        try:
            # 获取请求数据
            data = await request.json()
            message = data.get("message", "")
            session_id = data.get("session_id", "default")
            from_terminal = data.get("from_terminal")

            if not message:
                return await self._json_response({
                    "response": "❌ 缺少消息内容"
                }, status=400)

            # TODO: 实现实际的聊天逻辑
            # 这里需要集成到弥娅的认知引擎或对话系统
            # 暂时返回一个占位响应
            response = f"收到消息: {message}"

            if from_terminal:
                response = f"✅ 终端[{from_terminal}]已连接。弥娅主系统正在处理请求..."

            return await self._json_response({
                "response": response,
                "session_id": session_id
            })

        except Exception as e:
            logger.error(f"处理聊天请求失败: {e}", exc_info=True)
            return await self._json_response({
                "response": f"❌ 处理失败: {str(e)}"
            }, status=500)
    
    # ========== 健康检查 ==========

    async def handle_health(self, request: web.Request):
        """健康检查"""
        return web.Response(text="OK", status=HTTPStatus.OK)


# 全局单例
_runtime_api: Optional[RuntimeAPIServer] = None


def get_runtime_api(
    host: str = "127.0.0.1",
    port: int = 8080,
    auth_key: Optional[str] = None,
) -> RuntimeAPIServer:
    """获取Runtime API服务器单例
    
    Args:
        host: 监听地址
        port: 监听端口
        auth_key: 认证密钥
    
    Returns:
        RuntimeAPIServer实例
    """
    global _runtime_api
    if _runtime_api is None:
        _runtime_api = RuntimeAPIServer(host, port, auth_key)
    return _runtime_api
