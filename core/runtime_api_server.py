"""弥娅Runtime API服务器 - 整合Undefined的Runtime API能力

该模块提供弥娅的运行时管理API，支持：
- 交互端管理（启动/停止/状态查询）
- 认知记忆查询
- Agent管理
- 系统监控
- PC端统一管理面板后端

设计理念：符合弥娅的蛛网式分布式架构，作为M-Link的API层扩展
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

# 尝试导入FastAPI
try:
    from fastapi import FastAPI, HTTPException, status
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("[Runtime API] FastAPI未安装，Runtime API功能将被禁用")

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    """交互端信息"""
    id: str
    name: str
    type: str  # qq, pc, web
    status: str  # running, stopped, error
    pid: Optional[int] = None
    last_heartbeat: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Agent信息"""
    id: str
    name: str
    type: str
    description: str
    status: str
    stats: Dict[str, Any] = field(default_factory=dict)


class RuntimeAPIServer:
    """运行时API服务器
    
    职责：
    - 提供RESTful API接口
    - 管理交互端生命周期
    - 查询认知记忆和Agent状态
    - PC端统一管理面板后端
    
    架构定位：属于M-Link传输层的API扩展，不改变核心架构
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        enable_api: bool = True,
    ):
        self.host = host
        self.port = port
        self.enable_api = enable_api and FASTAPI_AVAILABLE
        
        # 交互端管理
        self._endpoints: Dict[str, EndpointInfo] = {}
        self._endpoint_lock = asyncio.Lock()
        
        # Agent管理
        self._agents: Dict[str, AgentInfo] = {}
        
        # 认知记忆服务（注入）
        self._cognitive_service: Optional[Any] = None
        self._agent_manager: Optional[Any] = None
        self._queue_manager: Optional[Any] = None
        
        # API服务器
        self.app: Optional[Any] = None
        self._server_task: Optional[asyncio.Task[None]] = None
        
        if not FASTAPI_AVAILABLE:
            logger.warning("[Runtime API] FastAPI不可用，请安装: pip install fastapi uvicorn")

    def set_cognitive_service(self, service: Any) -> None:
        """设置认知记忆服务"""
        self._cognitive_service = service

    def set_agent_manager(self, manager: Any) -> None:
        """设置Agent管理器"""
        self._agent_manager = manager

    def set_queue_manager(self, manager: Any) -> None:
        """设置队列管理器"""
        self._queue_manager = manager

    async def register_endpoint(
        self,
        endpoint_id: str,
        name: str,
        endpoint_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """注册交互端"""
        async with self._endpoint_lock:
            if endpoint_id in self._endpoints:
                logger.warning(
                    "[交互端注册] 已存在 endpoint=%s，更新信息",
                    endpoint_id,
                )
            
            self._endpoints[endpoint_id] = EndpointInfo(
                id=endpoint_id,
                name=name,
                type=endpoint_type,
                status="running",
                last_heartbeat=time.time(),
                metadata=metadata or {},
            )
            
            logger.info(
                "[交互端注册] id=%s name=%s type=%s",
                endpoint_id,
                name,
                endpoint_type,
            )
            return True

    async def update_endpoint_status(
        self,
        endpoint_id: str,
        status: str,
        pid: Optional[int] = None,
    ) -> bool:
        """更新交互端状态"""
        async with self._endpoint_lock:
            if endpoint_id not in self._endpoints:
                return False
            
            endpoint = self._endpoints[endpoint_id]
            endpoint.status = status
            endpoint.last_heartbeat = time.time()
            
            if pid is not None:
                endpoint.pid = pid
            
            logger.debug(
                "[交互端状态更新] id=%s status=%s",
                endpoint_id,
                status,
            )
            return True

    async def unregister_endpoint(self, endpoint_id: str) -> bool:
        """注销交互端"""
        async with self._endpoint_lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
                logger.info("[交互端注销] id=%s", endpoint_id)
                return True
            return False

    def get_endpoints(self) -> List[Dict[str, Any]]:
        """获取所有交互端"""
        return [
            {
                "id": ep.id,
                "name": ep.name,
                "type": ep.type,
                "status": ep.status,
                "pid": ep.pid,
                "last_heartbeat": ep.last_heartbeat,
                "metadata": ep.metadata,
            }
            for ep in self._endpoints.values()
        ]

    def get_endpoint(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """获取指定交互端"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None
        
        return {
            "id": endpoint.id,
            "name": endpoint.name,
            "type": endpoint.type,
            "status": endpoint.status,
            "pid": endpoint.pid,
            "last_heartbeat": endpoint.last_heartbeat,
            "metadata": endpoint.metadata,
        }

    async def start_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """启动交互端"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="交互端不存在")
        
        # 这里应该调用实际的启动逻辑
        # 由于弥娅架构，启动逻辑由各端点自己管理
        logger.info("[启动交互端] id=%s", endpoint_id)
        
        await self.update_endpoint_status(endpoint_id, "running")
        return {"status": "ok", "endpoint_id": endpoint_id}

    async def stop_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """停止交互端"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="交互端不存在")
        
        logger.info("[停止交互端] id=%s", endpoint_id)
        
        await self.update_endpoint_status(endpoint_id, "stopped")
        return {"status": "ok", "endpoint_id": endpoint_id}

    def _create_app(self) -> Any:
        """创建FastAPI应用"""
        if not FASTAPI_AVAILABLE:
            return None
        
        app = FastAPI(
            title="弥娅 Runtime API",
            description="弥娅AI Agent运行时管理API",
            version="1.0.0",
        )

        # 健康检查
        @app.get("/api/probe")
        async def probe():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}

        @app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

        # 系统状态
        @app.get("/api/status")
        async def get_status():
            return {
                "status": "running",
                "endpoints_count": len(self._endpoints),
                "agents_count": len(self._agents),
                "timestamp": datetime.now().isoformat(),
            }

        # 交互端管理
        @app.get("/api/endpoints")
        async def get_endpoints():
            return {"endpoints": self.get_endpoints()}

        @app.get("/api/endpoints/{endpoint_id}")
        async def get_endpoint(endpoint_id: str):
            endpoint = self.get_endpoint(endpoint_id)
            if not endpoint:
                raise HTTPException(status_code=404, detail="交互端不存在")
            return endpoint

        @app.post("/api/endpoints/{endpoint_id}/start")
        async def start_endpoint(endpoint_id: str):
            return await self.start_endpoint(endpoint_id)

        @app.post("/api/endpoints/{endpoint_id}/stop")
        async def stop_endpoint(endpoint_id: str):
            return await self.stop_endpoint(endpoint_id)

        # 认知记忆查询
        @app.get("/api/cognitive/events")
        async def search_events(
            query: str,
            limit: int = 10,
            user_id: Optional[str] = None,
        ):
            if not self._cognitive_service:
                return {"events": []}
            
            # 调用认知记忆服务
            try:
                events = await self._cognitive_service.search_events(
                    query=query,
                    limit=limit,
                    user_id=user_id,
                )
                return {"events": events}
            except Exception as e:
                logger.error("[认知记忆查询] error=%s", e, exc_info=True)
                return {"events": []}

        @app.get("/api/cognitive/profiles")
        async def get_profiles(user_id: Optional[str] = None):
            if not self._cognitive_service:
                return {"profiles": []}
            
            try:
                profiles = await self._cognitive_service.get_profiles(user_id=user_id)
                return {"profiles": profiles}
            except Exception as e:
                logger.error("[侧写查询] error=%s", e, exc_info=True)
                return {"profiles": []}

        # Agent管理
        @app.get("/api/agents")
        async def get_agents():
            return {"agents": list(self._agents.values())}

        @app.get("/api/agents/stats")
        async def get_agents_stats():
            if self._agent_manager:
                try:
                    stats = await self._agent_manager.get_all_stats()
                    return {"stats": stats}
                except Exception as e:
                    logger.error("[Agent统计] error=%s", e, exc_info=True)
            return {"stats": {}}

        # 队列统计
        @app.get("/api/queue/stats")
        async def get_queue_stats():
            if self._queue_manager:
                return {"stats": self._queue_manager.get_all_stats()}
            return {"stats": {}}

        return app

    async def start(self) -> None:
        """启动API服务器"""
        if not self.enable_api or not FASTAPI_AVAILABLE:
            logger.info("[Runtime API] 未启用或FastAPI不可用")
            return
        
        self.app = self._create_app()
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        
        self._server_task = asyncio.create_task(server.serve())
        
        logger.info(
            "[Runtime API启动] host=%s port=%s",
            self.host,
            self.port,
        )

    async def stop(self) -> None:
        """停止API服务器"""
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
            logger.info("[Runtime API停止]")
