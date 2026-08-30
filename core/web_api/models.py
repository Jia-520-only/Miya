"""
Web API 请求/响应模型
定义所有 API 的请求和响应数据结构
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


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
    user_id: Optional[str] = None
    usg_id: Optional[str] = None
    platform: Optional[str] = None
    image_data: Optional[str] = None


class TerminalChatRequest(BaseModel):
    """终端聊天请求"""

    message: str
    session_id: str = "terminal"
    from_terminal: Optional[str] = None  # 来自终端的标识


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""

    tool_name: str
    parameters: Dict[str, Any] = {}


class GitHubConfig(BaseModel):
    """GitHub 配置请求"""

    repo_owner: str
    repo_name: str
    token: str
    branch: str = "main"
