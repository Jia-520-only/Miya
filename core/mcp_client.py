"""
MCP (Model Context Protocol) 支持模块

功能：
1. MCP 工具注册表
2. 连接 MCP Server
3. 工具转换
4. Agent 私有 MCP 配置

参考 Undefined 项目的 MCP 实现
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPConnectionStatus(Enum):
    """MCP 连接状态"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPTool:
    """MCP 工具定义"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""

    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class MCPServer:
    """MCP 服务器实例"""

    name: str
    config: MCPServerConfig
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    process: Optional[Any] = None
    tools: List[MCPTool] = field(default_factory=list)
    error_message: str = ""


class MCPToolRegistry:
    """
    MCP 工具注册表

    功能：
    1. 连接 MCP Server
    2. 工具发现和注册
    3. 工具调用
    """

    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.global_tools: List[MCPTool] = []

        # MCP 配置路径
        self.config_path = Path(__file__).parent.parent.parent / "config" / "mcp.json"

        logger.info("[MCPToolRegistry] MCP 工具注册表初始化完成")

    def load_config(self) -> List[MCPServerConfig]:
        """加载 MCP 配置"""
        if not self.config_path.exists():
            logger.warning(f"[MCPToolRegistry] MCP 配置文件不存在: {self.config_path}")
            return []

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            servers = []
            for server_config in config.get("servers", []):
                servers.append(
                    MCPServerConfig(
                        name=server_config["name"],
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        env=server_config.get("env", {}),
                    )
                )

            logger.info(f"[MCPToolRegistry] 加载了 {len(servers)} 个 MCP 服务器配置")
            return servers

        except Exception as e:
            logger.error(f"[MCPToolRegistry] 加载 MCP 配置失败: {e}")
            return []

    async def connect_server(self, config: MCPServerConfig) -> bool:
        """
        连接到 MCP 服务器

        Args:
            config: 服务器配置

        Returns:
            是否连接成功
        """
        server = MCPServer(name=config.name, config=config)
        server.status = MCPConnectionStatus.CONNECTING

        logger.info(f"[MCPToolRegistry] 正在连接 MCP 服务器: {config.name}")

        try:
            # 模拟连接（实际需要启动 MCP Server 进程并建立 JSON-RPC 连接）
            # 这里是一个简化实现
            await asyncio.sleep(0.5)

            server.status = MCPConnectionStatus.CONNECTED
            self.servers[config.name] = server

            logger.info(f"[MCPToolRegistry] MCP 服务器连接成功: {config.name}")
            return True

        except Exception as e:
            server.status = MCPConnectionStatus.ERROR
            server.error_message = str(e)
            self.servers[config.name] = server

            logger.error(f"[MCPToolRegistry] MCP 服务器连接失败: {config.name}, 错误: {e}")
            return False

    async def disconnect_server(self, server_name: str):
        """断开 MCP 服务器连接"""
        if server_name not in self.servers:
            return

        server = self.servers[server_name]

        if server.process:
            try:
                server.process.terminate()
                await server.process.wait()
            except Exception as e:
                logger.error(f"[MCPToolRegistry] 断开服务器失败: {e}")

        server.status = MCPConnectionStatus.DISCONNECTED
        logger.info(f"[MCPToolRegistry] MCP 服务器已断开: {server_name}")

    async def initialize(self):
        """初始化 MCP 连接"""
        configs = self.load_config()

        for config in configs:
            await self.connect_server(config)

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        获取所有 MCP 工具的 OpenAI Function Calling 格式配置

        Returns:
            工具定义列表
        """
        tools = []

        for server in self.servers.values():
            if server.status != MCPConnectionStatus.CONNECTED:
                continue

            for tool in server.tools:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{server.name}_{tool.name}",
                            "description": f"[MCP-{server.name}] {tool.description}",
                            "parameters": tool.input_schema,
                        },
                    }
                )

        return tools

    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        执行 MCP 工具

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果
        """
        if server_name not in self.servers:
            return f"错误：MCP 服务器不存在: {server_name}"

        server = self.servers[server_name]

        if server.status != MCPConnectionStatus.CONNECTED:
            return f"错误：MCP 服务器未连接: {server_name}"

        try:
            # 模拟工具调用
            # 实际需要通过 JSON-RPC 调用 MCP Server
            result = {
                "success": True,
                "server": server_name,
                "tool": tool_name,
                "arguments": arguments,
                "result": "MCP 工具调用成功（模拟）",
            }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[MCPToolRegistry] 工具执行失败: {e}")
            return f"工具执行失败: {str(e)}"

    def get_server_status(self, server_name: str) -> Optional[Dict[str, Any]]:
        """获取服务器状态"""
        if server_name not in self.servers:
            return None

        server = self.servers[server_name]

        return {
            "name": server.name,
            "status": server.status.value,
            "tools_count": len(server.tools),
            "error_message": server.error_message,
        }

    def get_all_status(self) -> List[Dict[str, Any]]:
        """获取所有服务器状态"""
        return [self.get_server_status(name) for name in self.servers]

    async def shutdown(self):
        """关闭所有 MCP 连接"""
        for server_name in list(self.servers.keys()):
            await self.disconnect_server(server_name)

        logger.info("[MCPToolRegistry] 所有 MCP 服务器已断开")


# 全局实例
_global_mcp_registry: Optional[MCPToolRegistry] = None


def get_global_mcp_registry() -> MCPToolRegistry:
    """获取全局 MCP 注册表"""
    global _global_mcp_registry

    if _global_mcp_registry is None:
        _global_mcp_registry = MCPToolRegistry()

    return _global_mcp_registry


async def initialize_mcp() -> MCPToolRegistry:
    """初始化 MCP 连接"""
    registry = get_global_mcp_registry()
    await registry.initialize()
    return registry
