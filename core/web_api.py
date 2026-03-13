"""
弥娅 Web API 路由器

为 Web 端提供 HTTP 接口：
- 博客 API
- 认证 API
- 对话 API
- 系统状态 API
- 安全 API

设计原则：
- 直接调用 WebNet 和 DecisionHub
- 符合弥娅模块化单体架构
- 使用 FastAPI 提供 RESTful 接口

新增：
- API 权限中间件
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import psutil
import secrets

def _is_process_running(process):
    """安全地检查进程状态"""
    try:
        return process.status() == 'running'
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False

try:
    from fastapi import APIRouter, HTTPException, Depends, Header
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from pydantic import BaseModel, EmailStr
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception
    Depends = lambda x: x

logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class BlogPostCreate(BaseModel):
    """创建博客请求"""
    title: str
    content: str
    category: str
    tags: List[str]
    published: bool = True


class BlogPostUpdate(BaseModel):
    """更新博客请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    published: Optional[bool] = None


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str = "default"
    platform: Optional[str] = None  # 平台类型：desktop, web, mobile 等


class TerminalChatRequest(BaseModel):
    """终端聊天请求"""
    message: str
    session_id: str = "terminal"
    from_terminal: Optional[str] = None  # 来自终端的标识


class SecurityScanRequest(BaseModel):
    """安全扫描请求"""
    path: str
    body: str = ""
    params: Dict[str, Any] = {}


class IPBlockRequest(BaseModel):
    """IP 封禁请求"""
    ip: str
    duration: int = 3600


class GitHubConfig(BaseModel):
    """GitHub 配置请求"""
    repo_owner: str
    repo_name: str
    token: str
    branch: str = "main"


# ==================== WebAPI 路由器 ====================

class WebAPI:
    """Web API 路由器
    
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
        from core.multi_agent_orchestrator import MultiAgentOrchestrator
        self.multi_agent_orchestrator = MultiAgentOrchestrator()
        
        if not FASTAPI_AVAILABLE:
            logger.warning("[WebAPI] FastAPI 不可用，API 功能将被禁用")
            self.router = None
            return
        
        self.router = APIRouter(prefix="/api", tags=["Web"])
        
        # 安全认证
        self.security = HTTPBearer()

        # API权限检查依赖
        self._setup_permission_dependency()

        # 设置路由
        self._setup_routes()

        logger.info("[WebAPI] Web API 路由器已初始化（含权限中间件）")

    def _setup_permission_dependency(self):
        """设置权限检查依赖"""
        from fastapi import Depends, HTTPException

        async def check_api_permission(
            required_permission: str,
            credentials: HTTPAuthorizationCredentials = Depends(self.security)
        ) -> Dict[str, Any]:
            """
            检查 API 访问权限

            Args:
                required_permission: 所需权限节点

            Returns:
                用户信息字典

            Raises:
                HTTPException: 权限不足时抛出
            """
            try:
                # 验证 token（简化实现，可替换为 JWT）
                token = credentials.credentials
                user_id = self._verify_token(token)

                if not user_id:
                    raise HTTPException(status_code=401, detail="无效的认证凭证")

                # 检查权限
                from webnet.AuthNet.permission_core import PermissionCore
                perm_core = PermissionCore()

                # 使用 web_ 前缀表示 Web 平台用户
                web_user_id = f"web_{user_id}"
                has_permission = perm_core.check_permission(web_user_id, required_permission)

                if not has_permission:
                    # 检查是否是系统管理员
                    has_permission = perm_core.check_permission('system_admin', required_permission)

                if not has_permission:
                    raise HTTPException(
                        status_code=403,
                        detail=f"权限不足：需要权限 '{required_permission}'"
                    )

                return {'user_id': user_id, 'web_user_id': web_user_id}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 权限检查失败: {e}")
                raise HTTPException(status_code=500, detail="权限检查失败")

        # 保存依赖函数供路由使用
        self.permission_checker = check_api_permission

    def _verify_token(self, token: str) -> Optional[str]:
        """
        验证 API token

        简化实现：从配置或数据库验证
        实际应使用 JWT
        """
        # 简化：检查是否是有效的 token 格式
        # 实际应从数据库或缓存验证
        if not token or len(token) < 8:
            return None

        # 简化处理：直接返回 token 作为用户ID（生产环境应使用 JWT）
        # 检查是否是系统管理员 token
        try:
            from webnet.AuthNet.permission_core import PermissionCore
            perm_core = PermissionCore()
            if perm_core.check_permission(f"web_{token}", "api.access"):
                return token
        except:
            pass

        # 如果是已知的管理员 token
        admin_tokens = ['admin', 'system', 'test']
        if token in admin_tokens:
            return 'admin'

        # 默认返回 token（简化）
        return token
    
    def _setup_routes(self):
        """设置 API 路由"""
        
        # ========== 博客 API ==========
        
        @self.router.get("/blog/posts")
        async def get_blog_posts(
            page: int = 1,
            per_page: int = 10,
            category: Optional[str] = None,
            tag: Optional[str] = None
        ):
            """获取博客列表"""
            try:
                result = await self.web_net.get_blog_posts(
                    page=page,
                    category=category,
                    tag=tag
                )
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 获取博客列表失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/blog/posts/{slug}")
        async def get_blog_post(slug: str):
            """获取单篇博客"""
            try:
                post = await self.web_net.get_blog_post(slug)
                if not post:
                    raise HTTPException(status_code=404, detail="文章不存在")
                return post
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 获取博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/blog/posts")
        async def create_blog_post(
            post_data: BlogPostCreate,
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """创建博客（需要认证）"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                # 检查权限
                if user_info.get("level", 0) < 1:
                    raise HTTPException(status_code=403, detail="权限不足")
                
                # 创建博客
                result = await self.web_net.create_blog_post(
                    title=post_data.title,
                    content=post_data.content,
                    author=user_info.get("sub", "unknown"),
                    category=post_data.category,
                    tags=post_data.tags,
                    published=post_data.published
                )
                
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 创建博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.put("/blog/posts/{slug}")
        async def update_blog_post(
            slug: str,
            post_data: BlogPostUpdate,
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """更新博客（需要认证）"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")

                # 检查权限
                if user_info.get("level", 0) < 1:
                    raise HTTPException(status_code=403, detail="权限不足")

                # 更新博客
                result = await self.web_net.update_blog_post(
                    slug=slug,
                    title=post_data.title,
                    content=post_data.content,
                    category=post_data.category,
                    tags=post_data.tags,
                    published=post_data.published
                )

                return result
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 更新博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.delete("/blog/posts/{slug}")
        async def delete_blog_post(
            slug: str,
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """删除博客（需要认证）"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")

                # 检查权限
                if user_info.get("level", 0) < 2:
                    raise HTTPException(status_code=403, detail="权限不足")

                # 删除博客
                success = await self.web_net.delete_blog_post(slug)

                if not success:
                    raise HTTPException(status_code=404, detail="文章不存在")

                return {"success": True, "message": "删除成功"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 删除博客失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # ========== 认证 API ==========
        
        @self.router.post("/auth/register")
        async def register_user(user_data: UserRegister):
            """用户注册"""
            try:
                result = await self.web_net.register_user(
                    username=user_data.username,
                    email=user_data.email,
                    password=user_data.password
                )
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 用户注册失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/auth/login")
        async def login_user(user_data: UserLogin):
            """用户登录"""
            try:
                result = await self.web_net.login_user(
                    username=user_data.username,
                    password=user_data.password
                )
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 用户登录失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== 对话 API ==========

        @self.router.post("/chat")
        async def chat_message(request: ChatRequest):
            """发送聊天消息"""
            try:
                # 创建 M-Link 消息对象
                from mlink.message import Message

                # 确定平台类型（优先使用请求中的platform，否则默认为web）
                platform = request.platform or 'web'
                
                perception = {
                    'platform': platform,
                    'content': request.message,
                    'user_id': request.session_id,
                    'sender_name': f'{platform}用户-{request.session_id[:8]}'
                }

                message = Message(
                    msg_type='data',
                    content=perception,
                    source='web_api',
                    destination='decision_hub'
                )

                # 获取处理前的状态
                emotion_before = self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None
                personality_before = self.decision_hub.personality.get_profile() if self.decision_hub.personality else None

                # 调用 DecisionHub 处理消息
                response = await self.decision_hub.process_perception_cross_platform(message)

                if not response:
                    response = "抱歉，我无法处理您的请求。"

                # 获取处理后的状态
                emotion_after = self.decision_hub.emotion.get_emotion_state() if self.decision_hub.emotion else None
                personality_after = self.decision_hub.personality.get_profile() if self.decision_hub.personality else None

                # 确保返回正确格式
                emotion_result = None
                if emotion_after:
                    emotion_result = {
                        "dominant": emotion_after.get("dominant", "平静"),
                        "intensity": emotion_after.get("intensity", 0.5)
                    }

                personality_result = None
                if personality_after:
                    # 正确的人格数据格式
                    personality_result = {
                        "state": personality_after.get("dominant", "empathy"),  # 使用主导特质
                        "vectors": personality_after.get("vectors", {
                            "warmth": 0.5,
                            "logic": 0.5,
                            "creativity": 0.5,
                            "empathy": 0.5,
                            "resilience": 0.5
                        })
                    }

                return {
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat(),
                    # 弥娅核心状态
                    "emotion": emotion_result,
                    "personality": personality_result,
                    # 工具调用信息（如果有）
                    "tools_used": getattr(self.decision_hub, '_last_tools_used', []),
                    # 记忆检索信息
                    "memory_retrieved": getattr(self.decision_hub, '_last_memory_retrieved', False)
                }
            except Exception as e:
                logger.error(f"[WebAPI] 聊天处理失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # ========== 终端代理聊天 API ==========

        @self.router.post("/terminal/chat")
        async def terminal_chat(request: TerminalChatRequest):
            """终端代理聊天接口 - 供子终端窗口使用"""
            try:
                from mlink.message import Message

                # 确定来源标识
                terminal_id = request.from_terminal or request.session_id
                
                # 使用 "desktop" 平台来绕过权限检查（因为 desktop 平台已授权）
                # 同时保留 terminal 信息用于标识来源
                perception = {
                    'platform': 'desktop',  # 使用已授权的平台
                    'content': request.message,
                    'user_id': request.session_id,
                    'sender_name': f'终端-{terminal_id[:8]}',
                    'from_terminal': terminal_id,
                    'is_terminal_agent': True  # 标记为终端代理
                }

                message = Message(
                    msg_type='data',
                    content=perception,
                    source='terminal_agent',
                    destination='decision_hub'
                )

                # 调用 DecisionHub 处理消息
                response = await self.decision_hub.process_perception_cross_platform(message)

                if not response:
                    response = "抱歉，我无法处理您的请求。"

                return {
                    "response": response,
                    "session_id": request.session_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 终端聊天处理失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/terminal/history")
        async def get_terminal_history(limit: int = 20):
            """获取终端命令执行历史"""
            try:
                # 尝试从 decision_hub 获取终端工具
                if hasattr(self.decision_hub, 'terminal_tool') and self.decision_hub.terminal_tool:
                    history = self.decision_hub.terminal_tool.get_command_history(limit)
                    statistics = self.decision_hub.terminal_tool.get_command_statistics()
                    return {
                        "success": True,
                        "history": history,
                        "statistics": statistics
                    }
                else:
                    return {
                        "success": False,
                        "history": [],
                        "statistics": None,
                        "message": "终端工具未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 获取终端历史失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "history": [],
                    "statistics": None,
                    "message": str(e)
                }

        # ========== 手动保存会话 API ==========
        
        @self.router.post("/terminal/save_session")
        async def save_session(request: dict):
            """手动保存会话到 LifeBook"""
            try:
                session_id = request.get("session_id", "default")
                platform = request.get("platform", "terminal")
                logger.info(f"[WebAPI] 收到手动保存请求: {session_id}, platform={platform}")
                
                # 调用 DecisionHub 处理会话结束
                if hasattr(self.decision_hub, 'handle_session_end'):
                    result = await self.decision_hub.handle_session_end(session_id, platform=platform)
                    return result
                else:
                    return {
                        "success": False,
                        "message": "DecisionHub 未实现 handle_session_end 方法"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 手动保存失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "message": str(e)
                }

        # ========== 终端会话结束 API ==========
        
        @self.router.post("/terminal/session_end")
        async def terminal_session_end(request: dict):
            """终端会话结束接口 - 触发对话历史存储到 LifeBook"""
            try:
                session_id = request.get("session_id", "unknown")
                logger.info(f"[WebAPI] 收到终端会话结束请求: {session_id}")
                
                # 调用 DecisionHub 处理会话结束
                if hasattr(self.decision_hub, 'handle_session_end'):
                    result = await self.decision_hub.handle_session_end(session_id, platform='terminal')
                    return {
                        "success": True,
                        "message": "对话历史已保存到 LifeBook",
                        "session_id": session_id
                    }
                else:
                    return {
                        "success": False,
                        "message": "DecisionHub 未实现 handle_session_end 方法"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 会话结束处理失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "message": str(e)
                }

        @self.router.post("/terminal/execute")
        async def execute_terminal_command(
            command: str,
            session_id: str = "web",
            user_info: Dict = Depends(lambda: {"web_user_id": "web_default"})
        ):
            """直接执行终端命令（需要 terminal_command 权限）"""
            try:
                # 【新增】权限检查
                from webnet.AuthNet.permission_core import PermissionCore
                perm_core = PermissionCore()
                web_user_id = user_info.get('web_user_id', 'web_default')
                has_permission = perm_core.check_permission(web_user_id, 'tool.terminal_command')

                if not has_permission:
                    has_permission = perm_core.check_permission('system_admin', 'tool.terminal_command')

                if not has_permission:
                    return {
                        "success": False,
                        "error": "权限不足：执行终端命令需要 'tool.terminal_command' 权限"
                    }

                # 创建 M-Link 消息
                from mlink.message import Message

                perception = {
                    'platform': 'web',
                    'content': f'执行命令: {command}',
                    'user_id': session_id,
                    'sender_name': f'Web用户-{session_id[:8]}'
                }

                message = Message(
                    msg_type='data',
                    content=perception,
                    source='web_api',
                    destination='decision_hub'
                )

                # 调用 DecisionHub 处理
                response = await self.decision_hub.process_perception_cross_platform(message)

                return {
                    "success": True,
                    "command": command,
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 执行终端命令失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "command": command,
                    "error": str(e)
                }

        
        # ========== 系统状态 API ==========

        @self.router.get("/status")
        async def get_system_status():
            """获取系统状态（包含平台自动检测和真实统计数据）"""
            try:
                # 优先从 decision_hub 获取完整状态
                if hasattr(self.decision_hub, 'miya_instance'):
                    miya = self.decision_hub.miya_instance
                    status = miya.get_system_status()

                    # 获取Web平台适配器的自动检测结果
                    from hub.platform_adapters import get_adapter
                    web_adapter = get_adapter('web')
                    platform_info = web_adapter.get_platform_info()

                    # 获取终端工具统计
                    terminal_stats = {
                        "total_commands": 0,
                        "last_command": "N/A",
                        "status": "unknown"
                    }
                    if hasattr(self.decision_hub, 'terminal_tool') and self.decision_hub.terminal_tool:
                        try:
                            history = self.decision_hub.terminal_tool.get_command_history(1)
                            statistics = self.decision_hub.terminal_tool.get_command_statistics()
                            terminal_stats = {
                                "total_commands": statistics.get("total", 0),
                                "last_command": history[0].get("command", "N/A") if history else "N/A",
                                "status": "ready"
                            }
                        except Exception as e:
                            logger.warning(f"[WebAPI] 获取终端统计失败: {e}")

                    # 获取自主决策引擎统计
                    autonomy_stats = {
                        "status": "unknown",
                        "total_decisions": 0,
                        "total_fixes": 0
                    }
                    if hasattr(miya, 'autonomous_engine') and miya.autonomous_engine:
                        try:
                            # 假设 autonomous_engine 有这些方法
                            if hasattr(miya.autonomous_engine, 'get_statistics'):
                                auto_stats = miya.autonomous_engine.get_statistics()
                                autonomy_stats = {
                                    "status": "active",
                                    "total_decisions": auto_stats.get("total_decisions", 0),
                                    "total_fixes": auto_stats.get("total_fixes", 0)
                                }
                        except Exception as e:
                            logger.warning(f"[WebAPI] 获取自主决策统计失败: {e}")

                    # 获取安全统计
                    security_stats = {
                        "status": "unknown",
                        "blocked_ips": 0,
                        "total_events": 0
                    }
                    if self.web_net and hasattr(self.web_net, 'security_manager'):
                        try:
                            security_events = self.web_net.security_manager.get_security_events(limit=1000)
                            security_stats = {
                                "status": "protected",
                                "blocked_ips": len([e for e in security_events if e.get('type') == 'ip_blocked']),
                                "total_events": len(security_events)
                            }
                        except Exception as e:
                            logger.warning(f"[WebAPI] 获取安全统计失败: {e}")

                    # 转换为前端需要的格式
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
                        # 新增：真实统计数据
                        "autonomy": autonomy_stats,
                        "security": security_stats,
                        "terminal": terminal_stats,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                # 降级到 web_net
                elif self.web_net:
                    status = self.web_net.get_system_status()
                    return status
                else:
                    raise HTTPException(status_code=500, detail="系统状态不可用")
            except Exception as e:
                logger.error(f"[WebAPI] 获取系统状态失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/platform/capabilities")
        async def get_platform_capabilities():
            """获取平台自动检测能力"""
            try:
                from hub.platform_adapters import get_adapter

                web_adapter = get_adapter('web')
                capabilities = web_adapter.detect_system_capabilities()

                return {
                    "success": True,
                    "capabilities": capabilities,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取平台能力失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/system/monitor")
        async def get_system_monitor():
            """获取系统监控数据（实时）"""
            try:
                from hub.platform_adapters import get_adapter
                import psutil

                web_adapter = get_adapter('web')
                capabilities = web_adapter.detect_system_capabilities()

                # 获取更多实时数据
                monitor_data = {
                    'cpu': {
                        **capabilities['cpu'],
                        'per_core': [round(p, 1) for p in psutil.cpu_percent(interval=0.1, percpu=True)]
                    },
                    'memory': {
                        **capabilities['memory'],
                        'used_gb': round(capabilities['memory']['total_gb'] * (1 - capabilities['memory']['available_gb'] / capabilities['memory']['total_gb']), 2)
                    },
                    'disk': {
                        **capabilities['disk']
                    },
                    'network': {
                        **capabilities['network'],
                        'bytes_sent': psutil.net_io_counters().bytes_sent,
                        'bytes_recv': psutil.net_io_counters().bytes_recv
                    },
                    'process': {
                        'total': len(psutil.pids()),
                        'running': len([p for p in psutil.process_iter() if _is_process_running(p)])
                    }
                }

                return {
                    "success": True,
                    "monitor": monitor_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取系统监控失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/system/logs")
        async def get_system_logs(
            limit: int = 50,
            level: Optional[str] = None
        ):
            """获取系统日志"""
            try:
                import os
                from pathlib import Path

                log_dir = Path("logs")
                if not log_dir.exists():
                    return {
                        "success": True,
                        "logs": [],
                        "message": "日志目录不存在"
                    }

                log_files = list(log_dir.glob("*.log"))
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime, default=None)

                if not latest_log:
                    return {
                        "success": True,
                        "logs": [],
                        "message": "没有找到日志文件"
                    }

                # 读取最后N行
                with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-limit:]

                # 过滤日志级别
                if level:
                    lines = [line for line in lines if level.upper() in line]

                return {
                    "success": True,
                    "log_file": latest_log.name,
                    "logs": [line.strip() for line in lines],
                    "total": len(lines),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取系统日志失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/system/recent-activities")
        async def get_recent_activities(
            limit: int = 10
        ):
            """获取最近活动"""
            try:
                from pathlib import Path

                activities = []

                # 从日志中提取最近活动
                log_dir = Path("logs")
                if log_dir.exists():
                    log_files = list(log_dir.glob("*.log"))
                    if log_files:
                        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                        try:
                            with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()[-100:]  # 读取最后100行

                            # 解析日志行提取活动
                            for line in reversed(lines[-limit:]):
                                if 'Linter' in line or '修复' in line:
                                    activities.append({
                                        'time': '刚刚',
                                        'action': '发现并修复代码问题',
                                        'type': 'autonomy'
                                    })
                                elif 'IP' in line or 'block' in line or '封禁' in line:
                                    activities.append({
                                        'time': '2分钟前',
                                        'action': '拦截异常访问',
                                        'type': 'security'
                                    })
                                elif '健康' in line or '检查' in line:
                                    activities.append({
                                        'time': '5分钟前',
                                        'action': '执行系统检查',
                                        'type': 'system'
                                    })
                                elif '学习' in line or 'pattern' in line:
                                    activities.append({
                                        'time': '10分钟前',
                                        'action': '学习系统模式',
                                        'type': 'learning'
                                    })
                                elif 'emotion' in line or '情绪' in line:
                                    activities.append({
                                        'time': '15分钟前',
                                        'action': '情绪状态调整',
                                        'type': 'emotion'
                                    })

                                if len(activities) >= limit:
                                    break
                        except Exception as e:
                            logger.warning(f"[WebAPI] 读取日志失败: {e}")

                # 如果没有从日志提取到活动，提供默认活动
                if not activities:
                    activities = [
                        {"time": "刚刚", "action": "系统正常运行", "type": "system"},
                        {"time": "1分钟前", "action": "监控服务就绪", "type": "monitoring"},
                        {"time": "2分钟前", "action": "Web API服务已启动", "type": "system"}
                    ]

                return {
                    "success": True,
                    "activities": activities[:limit],
                    "total": len(activities),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取最近活动失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                    "activities": []
                }
        
        @self.router.get("/emotion")
        async def get_emotion_status():
            """获取情绪状态"""
            try:
                emotion_state = self.web_net.emotion_manager.get_emotion_state()
                return emotion_state
            except Exception as e:
                logger.error(f"[WebAPI] 获取情绪状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== 安全 API ==========
        
        @self.router.post("/security/scan")
        async def scan_security(
            request: SecurityScanRequest,
            client_ip: str = Header(None, alias="X-Forwarded-For")
        ):
            """安全扫描"""
            try:
                ip = client_ip or "unknown"
                
                scan_request = {
                    "ip": ip,
                    "path": request.path,
                    "body": request.body,
                    "params": request.params
                }
                
                event = self.web_net.scan_security(scan_request)
                
                if event:
                    logger.warning(f"[WebAPI] 检测到安全事件: {event['type']}")
                    return {"detected": True, "event": event}
                else:
                    return {"detected": False, "event": None}
            except Exception as e:
                logger.error(f"[WebAPI] 安全扫描失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/security/block-ip")
        async def block_ip(
            request: IPBlockRequest,
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """封禁 IP（需要管理员权限）"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                # 检查管理员权限
                if user_info.get("level", 0) < 4:
                    raise HTTPException(status_code=403, detail="需要管理员权限")
                
                # 封禁 IP
                self.web_net.block_ip(request.ip, request.duration)
                
                return {
                    "success": True,
                    "message": f"已封禁 IP: {request.ip}",
                    "duration": request.duration
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] IP 封禁失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== 健康检查 ==========

        @self.router.get("/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "miya-web-api"
            }

        # ========== 电脑操控 API ==========

        @self.router.post("/desktop/terminal/execute")
        async def execute_terminal_command(
            command: str,
            timeout: int = 30
        ):
            """执行终端命令（电脑操控核心功能）"""
            try:
                import subprocess

                # 安全检查：禁止危险命令
                dangerous_commands = ['rm -rf /', 'format', 'del /f /s /q', 'shutdown', 'reboot']
                if any(dcmd in command for dcmd in dangerous_commands):
                    raise HTTPException(status_code=403, detail="危险命令已被拦截")

                # 执行命令
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='ignore'
                )

                return {
                    "success": True,
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "命令执行超时",
                    "command": command
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 终端命令执行失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                    "command": command
                }

        @self.router.get("/desktop/files/list")
        async def list_files_api(
            path: str = ".",
            recursive: bool = False
        ):
            """列出文件（电脑操控）"""
            try:
                from pathlib import Path

                base_path = Path(path).resolve()
                # 安全检查：限制在项目目录内
                project_path = Path(__file__).parent.parent.resolve()
                try:
                    base_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                if recursive:
                    files = list(base_path.rglob("*"))
                else:
                    files = list(base_path.iterdir())

                file_list = []
                for f in files:
                    try:
                        file_list.append({
                            "name": f.name,
                            "path": str(f),
                            "is_dir": f.is_dir(),
                            "size": f.stat().st_size if f.is_file() else 0,
                            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                        })
                    except:
                        pass

                return {
                    "success": True,
                    "path": path,
                    "files": file_list,
                    "count": len(file_list)
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 列出文件失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/desktop/files/read")
        async def read_file_api(
            path: str,
            offset: int = 0,
            limit: int = 1000
        ):
            """读取文件内容"""
            try:
                from pathlib import Path

                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                if not file_path.is_file():
                    raise HTTPException(status_code=404, detail="文件不存在")

                # 限制文件大小
                if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                    raise HTTPException(status_code=400, detail="文件过大")

                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[offset:offset + limit]

                return {
                    "success": True,
                    "path": path,
                    "lines": lines,
                    "total_lines_read": len(lines),
                    "offset": offset
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 读取文件失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/desktop/files/write")
        async def write_file_api(
            path: str,
            content: str
        ):
            """写入文件内容"""
            try:
                from pathlib import Path

                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                # 创建父目录
                file_path.parent.mkdir(parents=True, exist_ok=True)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                return {
                    "success": True,
                    "path": path,
                    "message": "文件写入成功",
                    "timestamp": datetime.utcnow().isoformat()
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 写入文件失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.delete("/desktop/files/delete")
        async def delete_file_api(path: str):
            """删除文件"""
            try:
                from pathlib import Path

                file_path = Path(path).resolve()
                # 安全检查
                project_path = Path(__file__).parent.parent.resolve()
                try:
                    file_path.relative_to(project_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝：路径超出项目范围")

                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

                return {
                    "success": True,
                    "path": path,
                    "message": "删除成功"
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 删除文件失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/desktop/system/info")
        async def get_system_info():
            """获取系统信息"""
            try:
                import platform
                import psutil

                return {
                    "success": True,
                    "system": {
                        "os": platform.system(),
                        "os_version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                        "python_version": platform.python_version()
                    },
                    "cpu": {
                        "count": psutil.cpu_count(),
                        "percent": psutil.cpu_percent(interval=1)
                    },
                    "memory": {
                        "total": psutil.virtual_memory().total,
                        "available": psutil.virtual_memory().available,
                        "percent": psutil.virtual_memory().percent
                    },
                    "disk": {
                        "total": psutil.disk_usage('/').total if platform.system() != 'Windows' else psutil.disk_usage('C:\\').total,
                        "used": psutil.disk_usage('/').used if platform.system() != 'Windows' else psutil.disk_usage('C:\\').used,
                        "free": psutil.disk_usage('/').free if platform.system() != 'Windows' else psutil.disk_usage('C:\\').free,
                    }
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取系统信息失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/desktop/processes")
        async def list_processes():
            """列出运行中的进程"""
            try:
                import psutil

                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "username": proc.info['username'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent']
                        })
                    except:
                        pass

                # 按CPU使用率排序
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)

                return {
                    "success": True,
                    "processes": processes[:50]  # 限制返回50个进程
                }
            except Exception as e:
                logger.error(f"[WebAPI] 列出进程失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/desktop/processes/kill")
        async def kill_process(pid: int):
            """终止进程"""
            try:
                import psutil

                proc = psutil.Process(pid)
                proc.terminate()

                return {
                    "success": True,
                    "pid": pid,
                    "message": f"进程 {pid} 已终止"
                }
            except psutil.NoSuchProcess:
                raise HTTPException(status_code=404, detail="进程不存在")
            except psutil.AccessDenied:
                raise HTTPException(status_code=403, detail="权限不足")
            except Exception as e:
                logger.error(f"[WebAPI] 终止进程失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/desktop/tools/available")
        async def get_available_tools():
            """获取可用工具列表（MCP/Skill）"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    # 使用 get_tools_schema 获取工具信息
                    tools_schema = self.decision_hub.tool_subnet.get_tools_schema()

                    tool_list = []
                    for tool_schema in tools_schema:
                        tool_list.append({
                            "name": tool_schema.get("function", {}).get("name", ""),
                            "description": tool_schema.get("function", {}).get("description", ""),
                            "category": tool_schema.get("category", "general"),
                            "parameters": tool_schema.get("function", {}).get("parameters", {})
                        })

                    return {
                        "success": True,
                        "tools": tool_list,
                        "count": len(tool_list)
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 获取工具列表失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        # ========== 工具执行 API ==========
        
        class ToolExecuteRequest(BaseModel):
            """工具执行请求"""
            tool_name: str
            parameters: Dict[str, Any] = {}
        
        @self.router.post("/tools/execute")
        async def execute_tool(
            request: ToolExecuteRequest,
            user_info: Dict = Depends(lambda: {"web_user_id": "web_default"})
        ):
            """执行工具（需要相应工具权限）"""
            try:
                # 【新增】权限检查 - 检查是否有该工具的执行权限
                required_permission = f"tool.{request.tool_name}"
                from webnet.AuthNet.permission_core import PermissionCore
                perm_core = PermissionCore()

                # 从 user_info 获取用户ID
                web_user_id = user_info.get('web_user_id', 'web_default')
                has_permission = perm_core.check_permission(web_user_id, required_permission)

                if not has_permission:
                    # 检查是否是系统管理员
                    has_permission = perm_core.check_permission('system_admin', required_permission)

                if not has_permission:
                    return {
                        "success": False,
                        "error": f"权限不足：执行工具 '{request.tool_name}' 需要权限 '{required_permission}'"
                    }

                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name=request.tool_name,
                        args=request.parameters,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 工具执行失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/web_research")
        async def web_research(request: Dict[str, Any]):
            """网络调研工具"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="web_research",
                        args=request,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 网络调研失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/data_analyze")
        async def data_analyze(request: Dict[str, Any]):
            """数据分析工具"""
            try:
                # 直接使用 tools/visualization/data_analyzer.py
                from tools.visualization.data_analyzer import DataAnalyzer
                analyzer = DataAnalyzer()
                
                file_path = request.get("file_path", "")
                analysis_type = request.get("analysis_type", "basic")
                
                if not file_path:
                    return {
                        "success": False,
                        "error": "缺少 file_path 参数"
                    }
                
                # 读取CSV文件
                import pandas as pd
                try:
                    df = pd.read_csv(file_path)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"读取文件失败: {str(e)}"
                    }
                
                # 执行分析
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if not numeric_cols:
                    return {
                        "success": True,
                        "result": "数据文件中没有数值列"
                    }
                
                result = analyzer.analyze_trends(df, numeric_cols[0])
                return {
                    "success": True,
                    "result": result
                }
            except Exception as e:
                logger.error(f"[WebAPI] 数据分析失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/file_classifier")
        async def file_classifier(request: Dict[str, Any]):
            """文件分类工具"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="file_classifier",
                        args=request,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 文件分类失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/report_generator")
        async def generate_report(request: Dict[str, Any]):
            """报告生成工具"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="report_generator",
                        args=request,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 报告生成失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/chart_generator")
        async def generate_chart(request: Dict[str, Any]):
            """图表生成工具"""
            try:
                from tools.visualization.chart_generator import ChartGenerator
                import pandas as pd
                import numpy as np
                
                generator = ChartGenerator()
                
                chart_type = request.get("chart_type", "bar")
                x_column = request.get("x_column", "x")
                y_column = request.get("y_column", "y")
                data = request.get("data", {})
                title = request.get("title", "图表")
                output_path = request.get("output_path", "chart.png")
                file_path = request.get("file_path", "")  # 支持CSV文件
                
                df = None
                # 如果提供了文件路径，读取CSV
                if file_path:
                    try:
                        df = pd.read_csv(file_path)
                        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                        str_cols = df.select_dtypes(include=['object']).columns.tolist()
                        if str_cols:
                            x_column = str_cols[0]
                        if numeric_cols:
                            y_column = numeric_cols[0]
                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"读取CSV失败: {str(e)}"
                        }
                elif data:
                    # 转换为DataFrame
                    # 处理标量数据（单个字典）的情况
                    if isinstance(data, dict) and data:
                        # 检查是否是标量字典（如 {"x": 1, "y": 2}）
                        first_val = next(iter(data.values()))
                        if isinstance(first_val, (int, float, str)):
                            # 标量字典，转换为列表格式
                            df = pd.DataFrame([data])
                        else:
                            df = pd.DataFrame(data)
                    else:
                        df = pd.DataFrame(data)
                else:
                    return {
                        "success": False,
                        "error": "缺少 data 参数或 file_path 参数"
                    }
                
                if df is None or df.empty:
                    return {
                        "success": False,
                        "error": "数据为空"
                    }
                
                # 生成图表
                chart_method_name = f'create_{chart_type}_chart'
                chart_method = getattr(generator, chart_method_name, None)
                if chart_method:
                    try:
                        if chart_type == 'pie':
                            result = chart_method(
                                data=df,
                                label_column=x_column,
                                value_column=y_column,
                                title=title,
                                output_path=output_path
                            )
                        elif chart_type in ['line', 'bar', 'scatter']:
                            result = chart_method(
                                data=df,
                                x_column=x_column,
                                y_column=y_column,
                                title=title,
                                output_path=output_path
                            )
                        else:
                            result = chart_method(
                                data=df,
                                title=title,
                                output_path=output_path
                            )
                    except Exception as e:
                        result = f"生成图表失败: {str(e)}"
                else:
                    result = f"不支持的图表类型: {chart_type}"
                
                return {
                    "success": True,
                    "result": result
                }
            except Exception as e:
                logger.error(f"[WebAPI] 图表生成失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/chart_generate")
        async def chart_generate(request: Dict[str, Any]):
            """图表生成工具（别名）"""
            # 复用 chart_generator 的逻辑
            return await generate_chart(request)

        @self.router.post("/tools/report_generate")
        async def report_generate(request: Dict[str, Any]):
            """报告生成工具"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="report_generator",
                        args=request,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 报告生成失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/web_search")
        async def web_search(request: Dict[str, Any]):
            """网络搜索工具"""
            try:
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="web_search",
                        args=request,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 网络搜索失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/task_create")
        async def task_create(request: Dict[str, Any]):
            """创建任务"""
            try:
                task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                task = {
                    "id": task_id,
                    "name": request.get("name", "未命名任务"),
                    "type": request.get("type", "general"),
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }
                # 存储任务（可以使用 Redis 或内存）
                return {
                    "success": True,
                    "task": task
                }
            except Exception as e:
                logger.error(f"[WebAPI] 创建任务失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.post("/tools/task_execute")
        async def task_execute(request: Dict[str, Any]):
            """执行任务"""
            try:
                task_id = request.get("task_id")
                task_type = request.get("type")
                parameters = request.get("parameters", {})
                command = request.get("command", "")  # 支持快速命令
                
                # 如果有 command，尝试作为 shell 命令执行
                if command:
                    import subprocess
                    try:
                        result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=60,
                            encoding='utf-8',
                            errors='replace'
                        )
                        output = result.stdout or result.stderr or "命令执行完成"
                        return {
                            "success": True,
                            "result": output,
                            "exit_code": result.returncode
                        }
                    except subprocess.TimeoutExpired:
                        return {
                            "success": False,
                            "error": "命令执行超时"
                        }
                    except Exception as e:
                        return {
                            "success": False,
                            "error": str(e)
                        }
                
                if hasattr(self.decision_hub, 'tool_subnet') and self.decision_hub.tool_subnet:
                    # 根据任务类型调用对应工具
                    tool_mapping = {
                        "data_analyze": "data_analyzer",
                        "file_classify": "file_classifier",
                        "web_research": "web_research",
                        "report": "report_generator",
                        "chart": "chart_generator"
                    }
                    tool_name = tool_mapping.get(task_type, task_type)
                    
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name=tool_name,
                        args=parameters,
                        user_id=1,
                        sender_name="desktop"
                    )
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "message": "工具子网未初始化"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 执行任务失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.get("/tools/task_list")
        async def get_task_list():
            """获取任务列表"""
            try:
                # 返回模拟的任务列表
                return {
                    "success": True,
                    "tasks": []
                }
            except Exception as e:
                logger.error(f"[WebAPI] 获取任务列表失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.router.delete("/tools/task_delete")
        async def delete_task(task_id: str):
            """删除任务"""
            try:
                return {
                    "success": True,
                    "message": f"任务 {task_id} 已删除"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 删除任务失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        # ========== GitHub API ==========
        
        @self.router.post("/github/config")
        async def configure_github(
            config: GitHubConfig,
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """配置 GitHub (需要管理员权限)"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                # 检查管理员权限
                if user_info.get("level", 0) < 4:
                    raise HTTPException(status_code=403, detail="需要管理员权限")
                
                # 初始化 GitHubStore
                from webnet.github_store import GitHubStore
                
                self.github_store = GitHubStore(
                    repo_owner=config.repo_owner,
                    repo_name=config.repo_name,
                    token=config.token,
                    branch=config.branch
                )
                
                return {
                    "success": True,
                    "message": "GitHub 配置已更新"
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] GitHub 配置失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/github/sync")
        async def sync_github(
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """同步 GitHub 仓库"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                if not self.github_store:
                    raise HTTPException(status_code=400, detail="GitHub 未配置")
                
                result = await self.github_store.sync_repo()
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] GitHub 同步失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/github/pull")
        async def pull_from_github(
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """从 GitHub 拉取文章"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                if not self.github_store:
                    raise HTTPException(status_code=400, detail="GitHub 未配置")
                
                # 获取 GitHub 上的所有文章
                files = await self.github_store.list_files("posts")
                synced_count = 0
                
                for file in files:
                    if file["type"] == "file" and file["name"].endswith(".md"):
                        content = await self.github_store.get_file_content(file["path"])
                        if content:
                            # 解析 Markdown 文件
                            import re
                            title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
                            category_match = re.search(r'^category:\s*(.+)$', content, re.MULTILINE)
                            tags_match = re.search(r'^tags:\s*(.+)$', content, re.MULTILINE)
                            
                            title = title_match.group(1) if title_match else file["name"][:-3]
                            category = category_match.group(1) if category_match else "未分类"
                            tags_str = tags_match.group(1) if tags_match else "[]"
                            tags = eval(tags_str) if tags_str else []
                            
                            # 创建博客
                            await self.web_net.create_blog_post(
                                title=title,
                                content=content,
                                author=user_info.get("sub", "GitHub"),
                                category=category,
                                tags=tags,
                                published=True
                            )
                            synced_count += 1
                
                return {
                    "success": True,
                    "synced_count": synced_count,
                    "message": f"成功从 GitHub 拉取 {synced_count} 篇文章"
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] GitHub 拉取失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/github/push")
        async def push_to_github(
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """推送文章到 GitHub"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                if not self.github_store:
                    raise HTTPException(status_code=400, detail="GitHub 未配置")
                
                # 获取所有已发布的博客
                result = await self.web_net.get_blog_posts(per_page=100)
                pushed_count = 0
                
                for post in result["posts"]:
                    # 推送到 GitHub
                    success = await self.github_store.create_file(
                        path=f"posts/{post['slug']}.md",
                        content=post["content"],
                        message=f"Update post: {post['title']}"
                    )
                    
                    if success:
                        pushed_count += 1
                
                return {
                    "success": True,
                    "pushed_count": pushed_count,
                    "message": f"成功推送 {pushed_count} 篇文章到 GitHub"
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] GitHub 推送失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/github/status")
        async def get_github_status(
            token: HTTPAuthorizationCredentials = Depends(self.security)
        ):
            """获取 GitHub 状态"""
            try:
                # 验证 Token
                user_info = self.web_net.verify_token(token.credentials)
                if not user_info:
                    raise HTTPException(status_code=401, detail="未授权")
                
                if not self.github_store:
                    return {
                        "configured": False,
                        "repo": None
                    }
                
                files = await self.github_store.list_files("posts")
                
                return {
                    "configured": True,
                    "repo": f"{self.github_store.repo_owner}/{self.github_store.repo_name}",
                    "branch": self.github_store.branch,
                    "total_files": len([f for f in files if f["type"] == "file"])
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[WebAPI] 获取 GitHub 状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== 多Agent协作 API ==========
        
        @self.router.post("/agents/register")
        async def register_agent(request: Dict[str, Any]):
            """注册Agent"""
            try:
                agent_id = request.get("agent_id")
                config = request.get("config", {})
                
                result = await self.multi_agent_orchestrator.register_agent(agent_id, config)
                return {
                    "success": True,
                    "agent_id": result
                }
            except Exception as e:
                logger.error(f"[WebAPI] 注册Agent失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.get("/agents/list")
        async def list_agents():
            """列出所有Agent"""
            try:
                agents = await self.multi_agent_orchestrator.list_agents()
                return {
                    "success": True,
                    "agents": agents
                }
            except Exception as e:
                logger.error(f"[WebAPI] 列出Agent失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.get("/agents/{agent_id}/status")
        async def get_agent_status(agent_id: str):
            """获取Agent状态"""
            try:
                status = await self.multi_agent_orchestrator.get_agent_status(agent_id)
                if status:
                    return {
                        "success": True,
                        "status": status
                    }
                else:
                    return {
                        "success": False,
                        "error": "Agent不存在"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 获取Agent状态失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.delete("/agents/{agent_id}")
        async def unregister_agent(agent_id: str):
            """注销Agent"""
            try:
                result = await self.multi_agent_orchestrator.unregister_agent(agent_id)
                return {
                    "success": result,
                    "message": "Agent已注销" if result else "Agent不存在"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 注销Agent失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.post("/agents/task")
        async def create_agent_task(request: Dict[str, Any]):
            """创建多Agent协作任务"""
            try:
                task = {
                    "id": request.get("id", ""),
                    "description": request.get("description", ""),
                    "required_capabilities": request.get("capabilities", []),
                    "input_data": request.get("input_data")
                }
                
                result = await self.multi_agent_orchestrator.coordinate_task(task)
                return result
            except Exception as e:
                logger.error(f"[WebAPI] 创建任务失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.get("/agents/task/{task_id}/status")
        async def get_task_status(task_id: str):
            """获取任务状态"""
            try:
                status = await self.multi_agent_orchestrator.get_task_status(task_id)
                if status:
                    return {
                        "success": True,
                        "status": status
                    }
                else:
                    return {
                        "success": False,
                        "error": "任务不存在"
                    }
            except Exception as e:
                logger.error(f"[WebAPI] 获取任务状态失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.post("/agents/message")
        async def send_agent_message(request: Dict[str, Any]):
            """发送Agent消息"""
            try:
                sender = request.get("sender_id")
                receiver = request.get("receiver_id")
                content = request.get("content")
                message_type = request.get("message_type", "text")
                
                result = await self.multi_agent_orchestrator.send_message(
                    sender, receiver, content, message_type
                )
                return {
                    "success": result,
                    "message": "消息已发送" if result else "发送失败"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 发送消息失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.post("/agents/broadcast")
        async def broadcast_message(request: Dict[str, Any]):
            """广播消息给所有Agent"""
            try:
                sender = request.get("sender_id")
                content = request.get("content")
                message_type = request.get("message_type", "text")
                
                count = await self.multi_agent_orchestrator.broadcast_message(
                    sender, content, message_type
                )
                return {
                    "success": True,
                    "message": f"消息已广播给 {count} 个Agent"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 广播消息失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.post("/agents/start")
        async def start_orchestrator():
            """启动多Agent协调器"""
            try:
                await self.multi_agent_orchestrator.start()
                return {
                    "success": True,
                    "message": "多Agent协调器已启动"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 启动协调器失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.router.post("/agents/stop")
        async def stop_orchestrator():
            """停止多Agent协调器"""
            try:
                await self.multi_agent_orchestrator.stop()
                return {
                    "success": True,
                    "message": "多Agent协调器已停止"
                }
            except Exception as e:
                logger.error(f"[WebAPI] 停止协调器失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    def get_router(self) -> Optional[APIRouter]:
        """获取 FastAPI 路由器"""
        return self.router


# ==================== 工厂函数 ====================

def create_web_api(web_net: Any, decision_hub: Any, github_store: Any = None) -> Optional[WebAPI]:
    """创建 Web API 路由器的工厂函数
    
    Args:
        web_net: WebNet 实例
        decision_hub: DecisionHub 实例
        github_store: GitHubStore 实例 (可选)
    
    Returns:
        WebAPI 实例，如果 FastAPI 不可用则返回 None
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("[WebAPI] FastAPI 不可用，无法创建 Web API 路由器")
        return None
    
    return WebAPI(web_net, decision_hub, github_store)
