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
import os
import platform
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from core.constants import HTTPStatus

try:
    import aiohttp
    from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
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
        decision_hub: Optional[Any] = None,
    ):
        """初始化Runtime API服务器

        Args:
            host: 监听地址
            port: 监听端口
            auth_key: 认证密钥
            decision_hub: 决策中心实例（用于聊天功能）
        """
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("[Runtime API] aiohttp未安装")

        self.host = host
        self.port = port
        self.auth_key = auth_key

        # 交互端管理
        self.endpoints: Dict[str, EndpointStatus] = {}
        self.endpoints_lock = asyncio.Lock()
        self.endpoint_processes: Dict[str, Any] = {}  # 存储端点进程引用

        # 依赖的服务
        self.cognitive_memory = None
        self.skills_registry = None
        self.decision_hub = decision_hub  # 新增：决策中心

        # 配置管理
        self._config: Dict[str, Any] = {}

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

    def set_decision_hub(self, decision_hub):
        """设置决策中心"""
        self.decision_hub = decision_hub

    async def start(self):
        """启动API服务器"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"[Runtime API] 服务器已启动: http://{self.host}:{self.port}")

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
        return await self._json_response(
            {
                "status": "ok",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def handle_status(self, request: web.Request):
        """系统状态"""
        status = {
            "status": "running",
            "uptime": time.time() - self.start_time,
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "endpoints": {
                "total": len(self.endpoints),
                "running": sum(1 for ep in self.endpoints.values() if ep.status == "running"),
                "stopped": sum(1 for ep in self.endpoints.values() if ep.status == "stopped"),
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

        return await self._json_response(
            {
                "id": endpoint.id,
                "name": endpoint.name,
                "type": endpoint.type,
                "status": endpoint.status,
                "config": endpoint.config,
                "stats": endpoint.stats,
                "started_at": endpoint.started_at,
                "last_error": endpoint.last_error,
            }
        )

    async def handle_start_endpoint(self, request: web.Request):
        """启动交互端"""
        endpoint_id = request.match_info["id"]

        async with self.endpoints_lock:
            endpoint = self.endpoints.get(endpoint_id)

        if not endpoint:
            return await self._error_response("交互端不存在", HTTPStatus.NOT_FOUND)

        if endpoint.status == "running":
            return await self._error_response("交互端已在运行", HTTPStatus.BAD_REQUEST)

        try:
            # 根据端点类型执行启动逻辑
            if endpoint.type == "web":
                success = await self._start_web_endpoint(endpoint)
            elif endpoint.type == "terminal":
                success = await self._start_terminal_endpoint(endpoint)
            elif endpoint.type == "web":
                success = await self._start_desktop_endpoint(endpoint)
            else:
                return await self._error_response(f"不支持的端点类型: {endpoint.type}", HTTPStatus.BAD_REQUEST)

            if success:
                endpoint.status = "running"
                endpoint.started_at = time.time()
                endpoint.last_error = None
                logger.info(f"[Runtime API] 启动交互端成功: {endpoint_id}")
                return await self._json_response({"status": "started"})
            else:
                return await self._error_response("启动失败", HTTPStatus.INTERNAL_ERROR)

        except Exception as e:
            logger.error(f"[Runtime API] 启动交互端失败 {endpoint_id}: {e}", exc_info=True)
            endpoint.last_error = str(e)
            return await self._error_response(f"启动失败: {str(e)}", HTTPStatus.INTERNAL_ERROR)

    async def handle_stop_endpoint(self, request: web.Request):
        """停止交互端"""
        endpoint_id = request.match_info["id"]

        async with self.endpoints_lock:
            endpoint = self.endpoints.get(endpoint_id)

        if not endpoint:
            return await self._error_response("交互端不存在", HTTPStatus.NOT_FOUND)

        if endpoint.status != "running":
            return await self._error_response("交互端未在运行", HTTPStatus.BAD_REQUEST)

        try:
            # 根据端点类型执行停止逻辑
            if endpoint.type == "web":
                success = await self._stop_web_endpoint(endpoint)
            elif endpoint.type == "terminal":
                success = await self._stop_terminal_endpoint(endpoint)
            elif endpoint.type == "web":
                success = await self._stop_desktop_endpoint(endpoint)
            else:
                success = await self._stop_generic_endpoint(endpoint)

            if success:
                endpoint.status = "stopped"
                endpoint.started_at = None
                logger.info(f"[Runtime API] 停止交互端成功: {endpoint_id}")
                return await self._json_response({"status": "stopped"})
            else:
                return await self._error_response("停止失败", HTTPStatus.INTERNAL_ERROR)

        except Exception as e:
            logger.error(f"[Runtime API] 停止交互端失败 {endpoint_id}: {e}", exc_info=True)
            endpoint.last_error = str(e)
            return await self._error_response(f"停止失败: {str(e)}", HTTPStatus.INTERNAL_ERROR)

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

        return await self._json_response(
            {
                "events": [
                    {
                        "content": event.content,
                        "user_id": event.user_id,
                        "group_id": event.group_id,
                        "timestamp_utc": event.timestamp_utc,
                    }
                    for event in events
                ]
            }
        )

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

        return await self._json_response(
            {
                "agents": [
                    {
                        "name": name,
                        "description": item.get_description(),
                        "stats": self.skills_registry.get_stats(name).to_dict(),
                    }
                    for name, item in agents.items()
                ]
            }
        )

    async def handle_agent_stats(self, request: web.Request):
        """获取Agent统计"""
        if not self.skills_registry:
            return await self._error_response("Skills注册表未初始化", HTTPStatus.INTERNAL_ERROR)

        stats = self.skills_registry.get_stats()

        return await self._json_response({"agents": {name: stat.to_dict() for name, stat in stats.items()}})

    # ========== 配置管理 ==========

    async def handle_get_config(self, request: web.Request):
        """获取配置"""
        # 过滤敏感配置
        safe_config = self._get_safe_config()
        return await self._json_response({"config": safe_config})

    async def handle_update_config(self, request: web.Request):
        """更新配置"""
        try:
            data = await request.json()
            new_config = data.get("config", {})

            # 验证配置
            if not isinstance(new_config, dict):
                return await self._error_response("配置格式错误", HTTPStatus.BAD_REQUEST)

            # 检测变更
            changes = self._detect_config_changes(new_config)

            # 应用配置
            self._config.update(new_config)

            logger.info(f"[Runtime API] 配置已更新，变更: {list(changes.keys())}")

            return await self._json_response({"status": "updated", "changes": changes})

        except json.JSONDecodeError:
            return await self._error_response("无效的JSON格式", HTTPStatus.BAD_REQUEST)
        except Exception as e:
            logger.error(f"[Runtime API] 更新配置失败: {e}", exc_info=True)
            return await self._error_response(f"更新失败: {str(e)}", HTTPStatus.INTERNAL_ERROR)

    # ========== 统计数据 ==========

    async def handle_stats(self, request: web.Request):
        """获取统计数据"""
        stats = {
            "uptime": time.time() - self.start_time,
            "endpoints": len(self.endpoints),
            "memory": self._get_memory_stats(),
            "performance": self._get_performance_stats(),
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
            platform = data.get("platform", "web")

            if not message:
                return await self._json_response({"response": "❌ 缺少消息内容"}, status=400)

            # 如果有决策中心，使用决策中心处理
            if self.decision_hub:
                response = await self._process_with_decision_hub(message, session_id, platform, from_terminal)
            else:
                # 回退到简单响应
                response = self._process_without_decision_hub(message, session_id, from_terminal)

            return await self._json_response({"response": response, "session_id": session_id})

        except Exception as e:
            logger.error(f"处理聊天请求失败: {e}", exc_info=True)
            return await self._json_response({"response": f"❌ 处理失败: {str(e)}"}, status=500)

    # ========== 健康检查 ==========

    async def handle_health(self, request: web.Request):
        """健康检查"""
        return web.Response(text="OK", status=HTTPStatus.OK)

    # ========== 辅助方法 ==========

    async def _start_web_endpoint(self, endpoint: EndpointStatus) -> bool:
        """启动Web端点"""
        try:
            logger.info(f"[Runtime API] 启动Web端点: {endpoint.id}")

            # 获取端点配置
            config = endpoint.config
            host = config.get("host", "127.0.0.1")
            port = config.get("port", 8080)
            static_path = config.get("static_path", None)

            # 创建新的aiohttp应用实例
            web_app = web.Application()

            # 设置路由
            web_app.router.add_get("/", self._handle_web_root)
            web_app.router.add_get("/health", self._handle_health)

            # 添加静态文件支持（如果配置了静态路径）
            if static_path:
                from pathlib import Path

                static_dir = Path(static_path)
                if static_dir.exists() and static_dir.is_dir():
                    web_app.router.add_static("/static", static_path, name="static")
                    logger.info(f"[Runtime API] 静态文件路径: {static_path}")

            # 添加WebSocket支持（如果需要）
            if config.get("websocket_enabled", False):
                web_app.router.add_get("/ws", self._handle_websocket)

            # 创建runner和site
            runner = web.AppRunner(web_app)
            await runner.setup()

            site = web.TCPSite(runner, host=host, port=port)
            await site.start()

            # 保存引用以便停止
            self.endpoint_processes[endpoint.id] = runner

            # 更新端点状态
            endpoint.status = "running"
            endpoint.started_at = time.time()
            endpoint.stats = {
                "host": host,
                "port": port,
                "url": f"http://{host}:{port}",
                "started_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"[Runtime API] Web端点启动成功: {endpoint.id} -> http://{host}:{port}")
            return True

        except Exception as e:
            error_msg = f"Web端点启动失败: {e}"
            logger.error(f"[Runtime API] {error_msg}", exc_info=True)
            endpoint.status = "error"
            endpoint.last_error = error_msg
            return False

    async def _start_terminal_endpoint(self, endpoint: EndpointStatus) -> bool:
        """启动终端端点"""
        try:
            logger.info(f"[Runtime API] 启动终端端点: {endpoint.id}")

            config = endpoint.config
            shell = config.get("shell", None)  # None表示使用系统默认shell
            timeout = config.get("timeout", 30)
            env_vars = config.get("env_vars", {})

            # 确定系统默认shell
            if shell is None:
                if platform.system() == "Windows":
                    shell = "cmd.exe"
                elif platform.system() == "Darwin":  # macOS
                    shell = "/bin/zsh"
                else:  # Linux
                    shell = "/bin/bash"

            logger.info(f"[Runtime API] 终端Shell: {shell}")

            # 创建终端进程
            process = await asyncio.create_subprocess_exec(
                shell,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(os.environ), **env_vars} if env_vars else None,
            )

            # 保存进程引用
            self.endpoint_processes[endpoint.id] = {
                "process": process,
                "shell": shell,
                "timeout": timeout,
                "type": "terminal",
            }

            # 更新端点状态
            endpoint.status = "running"
            endpoint.started_at = time.time()
            endpoint.stats = {
                "shell": shell,
                "timeout": timeout,
                "started_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"[Runtime API] 终端端点启动成功: {endpoint.id} -> PID {process.pid}")
            return True

        except Exception as e:
            error_msg = f"终端端点启动失败: {e}"
            logger.error(f"[Runtime API] {error_msg}", exc_info=True)
            endpoint.status = "error"
            endpoint.last_error = error_msg
            return False

    async def _start_desktop_endpoint(self, endpoint: EndpointStatus) -> bool:
        """启动桌面端点"""
        try:
            logger.info(f"[Runtime API] 启动桌面端点: {endpoint.id}")

            config = endpoint.config
            app_path = config.get("app_path")
            app_args = config.get("args", [])
            working_dir = config.get("working_dir", None)

            if not app_path:
                error_msg = "桌面应用路径未配置"
                logger.error(f"[Runtime API] {error_msg}")
                endpoint.status = "error"
                endpoint.last_error = error_msg
                return False

            # 验证应用路径
            from pathlib import Path

            app_file = Path(app_path)
            if not app_file.exists():
                error_msg = f"桌面应用不存在: {app_path}"
                logger.error(f"[Runtime API] {error_msg}")
                endpoint.status = "error"
                endpoint.last_error = error_msg
                return False

            # 构建启动命令
            if platform.system() == "Windows":
                # Windows系统
                cmd = ["start", str(app_file)] + app_args
                # Windows下start需要在shell中执行
                process = await asyncio.create_subprocess_shell(" ".join(cmd), cwd=working_dir)
            elif platform.system() == "Darwin":  # macOS
                # macOS系统
                cmd = ["open", str(app_file)] + app_args
                process = await asyncio.create_subprocess_exec(*cmd, cwd=working_dir)
            else:  # Linux
                # Linux系统
                cmd = [str(app_file)] + app_args
                # 给文件添加执行权限
                import stat

                app_file.chmod(app_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                process = await asyncio.create_subprocess_exec(*cmd, cwd=working_dir)

            # 保存进程引用
            self.endpoint_processes[endpoint.id] = {
                "process": process,
                "app_path": app_path,
                "type": "desktop",
            }

            # 更新端点状态
            endpoint.status = "running"
            endpoint.started_at = time.time()
            endpoint.stats = {
                "app_path": app_path,
                "args": app_args,
                "working_dir": working_dir,
                "started_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"[Runtime API] 桌面端点启动成功: {endpoint.id} -> {app_path}")
            return True

        except Exception as e:
            error_msg = f"桌面端点启动失败: {e}"
            logger.error(f"[Runtime API] {error_msg}", exc_info=True)
            endpoint.status = "error"
            endpoint.last_error = error_msg
            return False

    async def _stop_web_endpoint(self, endpoint: EndpointStatus) -> bool:
        """停止Web端点"""
        logger.info(f"[Runtime API] 停止Web端点: {endpoint.id}")
        return True

    async def _stop_terminal_endpoint(self, endpoint: EndpointStatus) -> bool:
        """停止终端端点"""
        logger.info(f"[Runtime API] 停止终端端点: {endpoint.id}")
        return True

    async def _stop_desktop_endpoint(self, endpoint: EndpointStatus) -> bool:
        """停止桌面端点"""
        logger.info(f"[Runtime API] 停止桌面端点: {endpoint.id}")
        return True

    async def _stop_generic_endpoint(self, endpoint: EndpointStatus) -> bool:
        """停止通用端点"""
        logger.info(f"[Runtime API] 停止通用端点: {endpoint.id}")
        return True

    def _get_safe_config(self) -> Dict[str, Any]:
        """获取安全配置（过滤敏感信息）"""
        safe_config = {}

        # 定义敏感配置键
        sensitive_keys = {
            "api_key",
            "password",
            "secret",
            "token",
            "private_key",
            "auth_key",
            "credential",
        }

        for key, value in self._config.items():
            # 检查是否是敏感配置
            is_sensitive = any(sensitive_key in key.lower() for sensitive_key in sensitive_keys)

            if is_sensitive:
                # 部分隐藏敏感值
                if isinstance(value, str) and len(value) > 8:
                    safe_config[key] = value[:4] + "****" + value[-4:]
                else:
                    safe_config[key] = "****"
            else:
                safe_config[key] = value

        return safe_config

    def _detect_config_changes(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """检测配置变更"""
        changes = {}

        for key in set(list(self._config.keys()) + list(new_config.keys())):
            old_val = self._config.get(key)
            new_val = new_config.get(key)

            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes

    def _get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计"""
        try:
            import psutil

            process = psutil.Process()

            return {
                "rss_mb": process.memory_info().rss / 1024 / 1024,  # 物理内存
                "vms_mb": process.memory_info().vms / 1024 / 1024,  # 虚拟内存
                "percent": process.memory_percent(),  # 内存使用百分比
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,  # 可用内存
            }
        except Exception:
            return {"error": "无法获取内存统计"}

    def _get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        try:
            import psutil

            process = psutil.Process()

            return {
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
            }
        except Exception:
            return {"error": "无法获取性能统计"}

    async def _process_with_decision_hub(
        self, message: str, session_id: str, platform: str, from_terminal: Optional[str]
    ) -> str:
        """使用决策中心处理消息"""
        try:
            from mlink.message import Message

            perception = {
                "platform": platform,
                "content": message,
                "user_id": session_id,
                "sender_name": f"{platform}用户-{session_id[:8]}",
            }

            msg = Message(
                msg_type="data",
                content=perception,
                source="runtime_api",
                destination="decision_hub",
            )

            response = await self.decision_hub.process_perception_cross_platform(msg)

            if not response:
                response = "抱歉，我无法处理您的请求。"

            return response

        except Exception as e:
            logger.error(f"[Runtime API] 决策中心处理失败: {e}", exc_info=True)
            return f"处理失败: {str(e)}"

    def _process_without_decision_hub(self, message: str, session_id: str, from_terminal: Optional[str]) -> str:
        """无决策中心时的处理"""
        if from_terminal:
            return f"✅ 终端[{from_terminal}]已连接。弥娅主系统正在处理请求..."

        # 使用文本加载器
        from core.text_loader import get_greeting, is_greeting

        # 简单响应
        if is_greeting(message):
            return get_greeting("弥娅")
        elif "帮助" in message or "help" in message.lower():
            return "我可以帮你处理各种任务，包括代码编辑、文件管理、系统操作等。有什么需要帮助的吗？"
        else:
            return f"收到消息: {message}"


# 全局单例
_runtime_api: Optional[RuntimeAPIServer] = None


def get_runtime_api(
    host: str = "127.0.0.1",
    port: int = 8080,
    auth_key: Optional[str] = None,
    decision_hub: Optional[Any] = None,
) -> RuntimeAPIServer:
    """获取Runtime API服务器单例

    Args:
        host: 监听地址
        port: 监听端口
        auth_key: 认证密钥
        decision_hub: 决策中心实例

    Returns:
        RuntimeAPIServer实例
    """
    global _runtime_api
    if _runtime_api is None:
        _runtime_api = RuntimeAPIServer(host, port, auth_key, decision_hub)
    return _runtime_api
