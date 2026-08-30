"""
AstrBot Agent 上下文管理
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentContext:
    """Agent执行上下文"""

    session_id: str = ""
    """会话ID"""

    user_id: str = ""
    """用户ID"""

    platform: str = ""
    """平台类型"""

    provider_id: Optional[str] = None
    """Provider ID"""

    persona: Optional[str] = None
    """人格配置"""

    tools: List[Any] = field(default_factory=list)
    """可用工具列表"""

    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    """MCP服务器配置"""

    skills: List[str] = field(default_factory=list)
    """激活的技能列表"""

    history: List[Dict[str, Any]] = field(default_factory=list)
    """对话历史"""

    extra: Dict[str, Any] = field(default_factory=dict)
    """额外数据"""

    def add_message(self, role: str, content: Any):
        """添加消息到历史"""
        self.history.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self.history

    def clear_history(self):
        """清空历史"""
        self.history.clear()

    def set_tool_registry(self, tools: List[Any]):
        """设置工具注册表"""
        self.tools = tools

    def add_mcp_server(self, name: str, config: Dict[str, Any]):
        """添加MCP服务器"""
        self.mcp_servers[name] = config

    def remove_mcp_server(self, name: str):
        """移除MCP服务器"""
        self.mcp_servers.pop(name, None)

    def activate_skill(self, skill_name: str):
        """激活技能"""
        if skill_name not in self.skills:
            self.skills.append(skill_name)

    def deactivate_skill(self, skill_name: str):
        """停用技能"""
        if skill_name in self.skills:
            self.skills.remove(skill_name)
