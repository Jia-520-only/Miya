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
import contextlib
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# 尝试导入FastAPI
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, status
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("[Runtime API] FastAPI未安装，Runtime API功能将被禁用")

logger = logging.getLogger(__name__)


def is_port_available(port: int) -> bool:
    """检查端口是否可用"""
    try:
        # 尝试连接端口，如果能连接说明被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            result = s.connect_ex(("127.0.0.1", port))
            # result == 0 表示连接成功，说明端口被占用
            return result != 0
    except:
        return False


def find_available_port(start_port: int = 8001, max_attempts: int = 100) -> int:
    """查找可用端口"""
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(port):
            return port
    raise RuntimeError(f"无法找到可用端口，已尝试 {max_attempts} 次")


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

    # 全局缓存 - 避免每次请求重新初始化
    _global_model_client = None
    _global_prompt_manager = None
    _global_tool_subnet = None
    _global_memory_engine = None
    _global_initialized = False

    @classmethod
    async def ensure_global_initialized(cls) -> bool:
        """初始化全局组件 - 只执行一次"""
        if cls._global_initialized:
            return True

        logger.info("[Runtime API] 初始化全局组件...")
        try:
            # 初始化AI客户端 — 使用 ModelPoolManager 统一管理
            try:
                from core.model_pool_manager import get_model_pool

                pool = get_model_pool()
                cls._global_model_client = pool.create_ai_client(task_type="simple_chat")
                if cls._global_model_client:
                    logger.info("[Runtime API] AI客户端初始化成功 (ModelPoolManager)")
                else:
                    logger.warning("[Runtime API] 模型池未返回可用客户端")
            except Exception as e:
                logger.warning(f"AI客户端初始化失败: {e}")

            # 初始化提示词管理器
            try:
                from core.prompt_manager import PromptManager

                cls._global_prompt_manager = PromptManager()
                logger.info("[Runtime API] 提示词管理器初始化成功")
            except Exception as e:
                logger.warning(f"提示词管理器初始化失败: {e}")

            # 初始化记忆系统
            try:
                from core.memory_system_initializer import get_memory_system_initializer

                memory_initializer = await get_memory_system_initializer()
                cls._global_memory_engine = await memory_initializer.get_memory_engine()
                logger.info("[Runtime API] 记忆系统初始化成功")
            except Exception as e:
                logger.warning(f"记忆系统初始化失败: {e}")

            # 初始化工具系统
            try:
                from webnet.ToolNet.subnet import ToolSubnet

                cls._global_tool_subnet = ToolSubnet(
                    memory_engine=cls._global_memory_engine,
                    cognitive_memory=None,
                    onebot_client=None,
                    scheduler=None,
                )
                logger.info(
                    f"[Runtime API] 工具系统初始化成功，已加载 {len(cls._global_tool_subnet.registry.tools)} 个工具"
                )
            except Exception as e:
                logger.warning(f"工具系统初始化失败: {e}")

            cls._global_initialized = True
            logger.info("[Runtime API] 全局初始化完成")
            return True

        except Exception as e:
            logger.error(f"全局初始化失败: {e}")
            return False

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

        # 添加 CORS 中间件
        from fastapi.middleware.cors import CORSMiddleware

        # FIX: allow_origins=['*'] 与 allow_credentials=True 组合在浏览器侧会被拒绝（规范不允许）。
        # 这里提供可配置的允许来源列表；若未配置则默认关闭 credentials 并允许任意来源。
        cors_origins_raw = os.getenv("MIYA_CORS_ALLOW_ORIGINS", "").strip()
        allow_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()] if cors_origins_raw else ["*"]
        allow_credentials = allow_origins != ["*"]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],  # 允许所有 HTTP 方法
            allow_headers=["*"],  # 允许所有请求头
        )

        # 健康检查
        @app.get("/api/probe")
        async def probe():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}

        @app.get("/api/health")
        async def api_health():
            return {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "service": "miya-runtime",
            }

        @app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

        # WebSocket 支持
        from fastapi import WebSocket, WebSocketDisconnect

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket 聊天端点"""
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_text()
                    # 处理接收到的消息
                    await websocket.send_text(f"收到: {data}")
            except WebSocketDisconnect:
                logger.info("WebSocket 断开连接")
            except Exception as e:
                logger.error(f"WebSocket 错误: {e}")

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

        # ========== 弥娅核心管理 API ==========

        @app.get("/api/miya/status")
        async def get_miya_status():
            """获取弥娅核心系统状态"""
            try:
                from core.memory_system_initializer import get_memory_system_initializer
                from core.prompt_manager import PromptManager
                from webnet.ToolNet.subnet import ToolSubnet

                # 初始化记忆系统
                try:
                    memory_initializer = await get_memory_system_initializer()
                    memory_stats = await memory_initializer.get_statistics()
                except:
                    memory_stats = None

                # 初始化工具系统
                try:
                    tool_subnet = ToolSubnet()
                    tools_count = len(tool_subnet.registry.tools)
                except:
                    tools_count = 0

                # 获取人设
                try:
                    prompt_manager = PromptManager()
                    system_prompt = prompt_manager.get_system_prompt()
                    prompt_length = len(system_prompt)
                except:
                    prompt_length = 0

                return {
                    "status": "running",
                    "memory": memory_stats,
                    "tools": {"count": tools_count, "status": "active"},
                    "personality": {"prompt_length": prompt_length, "status": "loaded"},
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"获取弥娅状态失败: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

        @app.get("/api/miya/memory")
        async def get_miya_memory():
            """获取记忆系统统计"""
            try:
                from core.memory_system_initializer import get_memory_system_initializer

                memory_initializer = await get_memory_system_initializer()
                stats = await memory_initializer.get_statistics()

                return {
                    "status": "success",
                    "data": stats,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"获取记忆统计失败: {e}")
                return {"status": "error", "error": str(e)}

        @app.get("/api/miya/tools")
        async def get_miya_tools():
            """获取工具列表"""
            try:
                from webnet.ToolNet.subnet import ToolSubnet

                tool_subnet = ToolSubnet()
                tools = []

                for tool_name, tool in tool_subnet.registry.tools.items():
                    try:
                        tool_config = tool.config if hasattr(tool, "config") else {}
                        tools.append(
                            {
                                "name": tool_config.get("name", tool_name),
                                "description": tool_config.get("description", ""),
                                "type": tool_config.get("type", "unknown"),
                            }
                        )
                    except:
                        tools.append(
                            {
                                "name": tool_name,
                                "description": "无描述",
                                "type": "unknown",
                            }
                        )

                return {
                    "status": "success",
                    "tools": tools,
                    "count": len(tools),
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"获取工具列表失败: {e}")
                return {"status": "error", "error": str(e)}

        @app.get("/api/miya/personality")
        async def get_miya_personality():
            """获取人设和人格配置"""
            try:
                from core.prompt_manager import PromptManager

                prompt_manager = PromptManager()
                system_prompt = prompt_manager.get_system_prompt()

                return {
                    "status": "success",
                    "personality": {
                        "system_prompt": system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt,
                        "length": len(system_prompt),
                        "loaded": True,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"获取人设配置失败: {e}")
                return {"status": "error", "error": str(e)}

        @app.get("/api/miya/models")
        async def get_miya_models():
            """获取AI模型信息"""
            try:
                import json
                from pathlib import Path

                config_path = Path(__file__).parent.parent / "config" / "multi_model_config.json"

                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)

                    models = []
                    for model_id, model_config in config.get("models", {}).items():
                        models.append(
                            {
                                "id": model_id,
                                "name": model_config.get("name", model_id),
                                "provider": model_config.get("provider", "unknown"),
                                "type": "chat",
                                "description": model_config.get("description", ""),
                                "latency": model_config.get("latency", "unknown"),
                                "quality": model_config.get("quality", "unknown"),
                                "capabilities": model_config.get("capabilities", []),
                            }
                        )

                    # 添加路由策略信息
                    routing = config.get("routing_strategy", {})

                    return {
                        "status": "success",
                        "models": models,
                        "count": len(models),
                        "routing_strategy": routing,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "status": "error",
                        "error": "多模型配置文件不存在",
                        "models": [],
                        "count": 0,
                    }
            except Exception as e:
                logger.error(f"获取模型信息失败: {e}")
                return {"status": "error", "error": str(e), "models": [], "count": 0}

        @app.get("/api/miya/logs")
        async def get_miya_logs(limit: int = 100):
            """获取系统日志"""
            try:
                from pathlib import Path

                log_dir = Path(__file__).parent.parent / "logs"
                logs = []

                if log_dir.exists():
                    # 读取最新的日志文件
                    log_files = sorted(
                        log_dir.glob("*.log"),
                        key=lambda x: x.stat().st_mtime,
                        reverse=True,
                    )

                    for log_file in log_files[:3]:  # 读取最近3个日志文件
                        try:
                            with open(log_file, "r", encoding="utf-8") as f:
                                lines = f.readlines()
                                # 获取最后limit行
                                recent_lines = lines[-limit:]
                                logs.extend([line.strip() for line in recent_lines if line.strip()])
                                if len(logs) >= limit:
                                    break
                        except Exception as e:
                            logger.debug(f"读取日志文件失败: {e}")

                return {
                    "status": "success",
                    "logs": logs[-limit:],  # 确保不超过limit
                    "count": len(logs[-limit:]),
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"获取日志失败: {e}")
                return {"status": "error", "error": str(e), "logs": [], "count": 0}

        # 终端代理聊天接口 - 集成弥娅核心AI系统
        @app.post("/api/terminal/chat")
        async def terminal_chat(request: dict[str, str]):
            """处理终端代理的聊天请求 - 使用全局缓存优化"""
            from datetime import datetime

            try:
                message = request.get("message", "")
                session_id = request.get("session_id", "")
                from_terminal = request.get("from_terminal", session_id)

                logger.info(f"[终端聊天] 收到消息: {message} (会话: {session_id})")

                # 确保全局组件已初始化
                await RuntimeAPIServer.ensure_global_initialized()

                # 使用全局缓存的组件
                model_client = RuntimeAPIServer._global_model_client
                prompt_manager = RuntimeAPIServer._global_prompt_manager
                tool_subnet = RuntimeAPIServer._global_tool_subnet
                memory_engine = RuntimeAPIServer._global_memory_engine

                # 获取人设提示词
                system_prompt = ""
                try:
                    from core.config_loader import get_text_config_value

                    system_prompt = get_text_config_value(
                        "prompt_templates.runtime_api.fallback_system_prompt",
                        "你是弥娅，一个智能AI助手。你友善、专业、乐于助人。",
                    )
                except Exception:
                    system_prompt = "你是弥娅，一个智能AI助手。你友善、专业、乐于助人。"
                if prompt_manager:
                    try:
                        system_prompt = prompt_manager.get_system_prompt()
                    except Exception as e:
                        logger.debug(f"获取提示词失败: {e}")

                # 添加工具使用说明
                if tool_subnet:
                    tools_info = []
                    for tool_name, tool in list(tool_subnet.registry.tools.items())[:10]:
                        try:
                            tool_config = tool.config if hasattr(tool, "config") else {}
                            description = tool_config.get("description", "无描述")
                            tools_info.append(f"- {tool_name}: {description}")
                        except:
                            pass

                    if tools_info:
                        system_prompt += "\n\n可用工具:\n" + "\n".join(tools_info)
                        system_prompt += "\n\n工具使用说明: 当用户明确请求某个功能时，你应该使用相应的工具。"

                # 构建对话消息
                from core.ai_client import AIMessage

                messages = [AIMessage(role="system", content=system_prompt)]

                # 添加记忆上下文
                if memory_engine:
                    try:
                        memory_context = await memory_engine.get_context(session_id, limit=5)
                        if memory_context:
                            messages.append(
                                AIMessage(
                                    role="system",
                                    content=f"记忆上下文:\n{memory_context}",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"获取记忆上下文失败: {e}")

                messages.append(AIMessage(role="user", content=message))

                # 检测工具调用
                tool_call_result = None
                if tool_subnet:
                    try:
                        from webnet.ToolNet.base import ToolContext

                        for tool_name, tool in tool_subnet.registry.tools.items():
                            try:
                                tool_config = tool.config if hasattr(tool, "config") else {}
                                tool_display_name = tool_config.get("name", tool_name).lower()

                                if tool_display_name in message.lower() or tool_name.lower() in message.lower():
                                    logger.info(f"[终端聊天] 检测到工具调用: {tool_name}")

                                    context = ToolContext(
                                        memory_engine=memory_engine,
                                        unified_memory=memory_engine,
                                        user_id=int(session_id) if session_id.isdigit() else None,
                                        message_type="web",
                                    )

                                    result = await tool_subnet.execute_tool(
                                        tool_name=tool_name,
                                        args={},
                                        user_id=context.user_id,
                                        message_type="web",
                                    )
                                    tool_call_result = result
                                    break
                            except Exception as tool_error:
                                logger.debug(f"工具 {tool_name} 执行失败: {tool_error}")
                    except Exception as e:
                        logger.debug(f"工具检测失败: {e}")

                # 调用AI生成响应
                response_text = "抱歉，AI服务暂时不可用。"
                if model_client:
                    if tool_call_result:
                        messages.append(
                            AIMessage(
                                role="system",
                                content=f"工具执行结果:\n{tool_call_result}",
                            )
                        )

                    try:
                        response = await model_client.chat(messages)
                        if isinstance(response, str):
                            response_text = response
                        elif hasattr(response, "content"):
                            response_text = response.content
                        else:
                            response_text = str(response)
                    except Exception as e:
                        logger.error(f"AI调用失败: {e}")
                        response_text = tool_call_result or "抱歉，AI服务暂时不可用。"
                else:
                    response_text = tool_call_result or "抱歉，AI服务暂时不可用。"

                # 保存对话到记忆系统
                if memory_engine:
                    try:
                        await memory_engine.add_conversation(session_id, message, response_text)
                    except Exception as e:
                        logger.debug(f"保存对话记忆失败: {e}")

                response_data = {
                    "response": response_text,
                    "status": "success",
                    "session_id": session_id,
                    "from_terminal": from_terminal,
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(f"[终端聊天] 发送响应: {response_text[:100]}...")
                return response_data

            except Exception as e:
                logger.error(f"[终端聊天] 处理请求时出错: {e}", exc_info=True)
                # 返回错误响应而不是崩溃
                return {
                    "response": f"处理您的请求时遇到了问题: {str(e)[:100]}",
                    "status": "error",
                    "session_id": request.get("session_id", "unknown"),
                    "from_terminal": request.get("from_terminal", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)[:200],
                }

        return app

    async def start(self) -> None:
        """启动API服务器"""
        if not self.enable_api or not FASTAPI_AVAILABLE:
            logger.info("[Runtime API] 未启用或FastAPI不可用")
            return

        # 查找可用端口
        original_port = self.port
        actual_port = find_available_port(self.port)

        if actual_port != original_port:
            logger.warning(f"[Runtime API] 默认端口 {original_port} 被占用，自动切换到端口 {actual_port}")
            self.port = actual_port

        self.app = self._create_app()

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            log_config=None,
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
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
            logger.info("[Runtime API停止]")
