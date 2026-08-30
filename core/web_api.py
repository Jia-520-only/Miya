"""
弥娅 Web API 路由器 - 向后兼容层

该文件保留用于向后兼容，实际实现已迁移到 core/web_api/ 目录

新结构:
- core/web_api/__init__.py - 主 WebAPI 类
- core/web_api/models.py - 请求/响应模型
- core/web_api/auth.py - 认证路由
- core/web_api/blogs.py - 博客路由
- core/web_api/chat.py - 对话路由
- core/web_api/terminal.py - 终端路由
- core/web_api/system.py - 系统路由
- core/web_api/desktop.py - 桌面路由
- core/web_api/tools.py - 工具路由
- core/web_api/cross_terminal.py - 跨端消息路由

向后兼容: 所有旧的导入仍然有效:
- from core.web_api import WebAPI
- from core.web_api import create_web_api
- from core.web_api.models import BlogPostCreate, UserRegister, ...

模块化导入 (新增):
- from core.web_api.auth import AuthRoutes
- from core.web_api.blogs import BlogRoutes
- ...
"""

# 从新模块导入所有公开接口
from core.web_api.__init__ import WebAPI, create_web_api

# 从 models 导入所有模型（保持向后兼容）
from core.web_api.models import (
    BlogPostCreate,
    BlogPostUpdate,
    ChatRequest,
    GitHubConfig,
    TerminalChatRequest,
    ToolExecuteRequest,
    UserLogin,
    UserRegister,
)

# 导出所有公开接口
__all__ = [
    "WebAPI",
    "create_web_api",
    "BlogPostCreate",
    "BlogPostUpdate",
    "UserRegister",
    "UserLogin",
    "ChatRequest",
    "TerminalChatRequest",
    "GitHubConfig",
    "ToolExecuteRequest",
]
