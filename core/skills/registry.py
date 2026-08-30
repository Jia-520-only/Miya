"""
弥娅技能注册系统 - 统一管理 Agents、Commands、Hooks、MCP Services
为 Terminal Ultra 提供完整的技能生态
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Miya.SkillsRegistry")


class SkillType(Enum):
    AGENT = "agent"  # Agent
    COMMAND = "command"  # Slash Command
    HOOK = "hook"  # Hook
    MCP = "mcp"  # MCP Service
    TOOL = "tool"  # 工具


@dataclass
class Skill:
    name: str
    type: SkillType
    description: str
    enabled: bool = True
    module: str = ""
    handler: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillsRegistry:
    """技能注册中心"""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._initialized = False

    async def initialize(self):
        """初始化所有技能"""
        if self._initialized:
            return

        logger.info("[Skills] 初始化技能注册表...")

        # 加载 Agents
        await self._load_agents()

        # 加载 Commands
        self._load_commands()

        # 加载 Hooks
        self._load_hooks()

        # 加载 MCP Services
        await self._load_mcp_services()

        self._initialized = True
        logger.info(f"[Skills] 已注册 {len(self.skills)} 个技能")

    async def _load_agents(self):
        """加载 Agents"""
        agents_dir = Path("core/skills/agents")
        if not agents_dir.exists():
            return

        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                self.skills[agent_dir.name] = Skill(
                    name=agent_dir.name,
                    type=SkillType.AGENT,
                    description=f"Agent: {agent_dir.name}",
                    module=f"core.skills.agents.{agent_dir.name}.handler",
                )
                logger.info(f"[Skills] 注册 Agent: {agent_dir.name}")

    def _load_commands(self):
        """加载 Slash Commands"""
        from core.skills.slash_commands import _command_manager

        for name, cmd in _command_manager.commands.items():
            self.skills[f"/{name}"] = Skill(
                name=f"/{name}",
                type=SkillType.COMMAND,
                description=cmd.description,
                module="core.skills.slash_commands",
            )
            logger.info(f"[Skills] 注册 Command: /{name}")

    def _load_hooks(self):
        """加载 Hooks"""
        self.skills["hooks"] = Skill(
            name="hooks",
            type=SkillType.HOOK,
            description="安全钩子系统",
            module="core.skills.hooks.hook_manager",
        )
        logger.info("[Skills] 注册 Hooks 系统")

    async def _load_mcp_services(self):
        """加载 MCP Services"""
        mcp_dir = Path("mcpserver")
        if not mcp_dir.exists():
            return

        for service_dir in mcp_dir.iterdir():
            if service_dir.is_dir():
                manifest_file = service_dir / "agent-manifest.json"
                if manifest_file.exists():
                    try:
                        data = json.loads(manifest_file.read_text(encoding="utf-8"))
                        self.skills[data["name"]] = Skill(
                            name=data["name"],
                            type=SkillType.MCP,
                            description=data.get("description", ""),
                            module=data.get("entryPoint", {}).get("module", ""),
                            metadata=data.get("capabilities", {}),
                        )
                        logger.info(f"[Skills] 注册 MCP: {data['name']}")
                    except Exception as e:
                        logger.warning(f"[Skills] 加载 MCP manifest 失败: {service_dir}: {e}")

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills.get(name)

    def list_skills(self, skill_type: SkillType = None) -> List[Skill]:
        """列出技能"""
        if skill_type:
            return [s for s in self.skills.values() if s.type == skill_type]
        return list(self.skills.values())

    def list_agents(self) -> List[str]:
        """列出所有 Agent 名称"""
        return [s.name for s in self.skills.values() if s.type == SkillType.AGENT]

    def list_commands(self) -> List[str]:
        """列出所有命令"""
        return [s.name for s in self.skills.values() if s.type == SkillType.COMMAND]

    def list_mcp_services(self) -> List[str]:
        """列出所有 MCP 服务"""
        return [s.name for s in self.skills.values() if s.type == SkillType.MCP]

    def get_help(self) -> str:
        """获取帮助信息"""
        lines = ["## 弥娅技能系统", ""]

        lines.append("### Agents")
        for skill in self.list_skills(SkillType.AGENT):
            lines.append(f"- **{skill.name}**: {skill.description}")

        lines.append("")
        lines.append("### Slash Commands")
        for skill in self.list_skills(SkillType.COMMAND):
            lines.append(f"- **{skill.name}**: {skill.description}")

        lines.append("")
        lines.append("### MCP Services")
        for skill in self.list_skills(SkillType.MCP):
            lines.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(lines)


_registry = None


async def get_skills_registry() -> SkillsRegistry:
    """获取技能注册表"""
    global _registry
    if _registry is None:
        _registry = SkillsRegistry()
        await _registry.initialize()
    return _registry


async def get_agent_handler(agent_name: str):
    """获取 Agent handler (供 ToolNet 调用)

    Args:
        agent_name: Agent 名称

    Returns:
        Agent handler 函数，如果不存在返回 None
    """
    registry = await get_skills_registry()
    skill = registry.get_skill(agent_name)

    if not skill or skill.type != SkillType.AGENT:
        return None

    try:
        skill.module.replace(".", "/") + ".py"
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            f"agent_{agent_name}", f"core/skills/agents/{agent_name}/handler.py"
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.handler
    except Exception as e:
        logger.warning(f"[Skills] 获取 Agent handler 失败: {agent_name} - {e}")

    return None


async def call_mcp_service(service_name: str, tool_name: str, params: Dict[str, Any]) -> str:
    """调用 MCP Service (供 ToolNet 调用)

    Args:
        service_name: 服务名称 (filesystem, memory, database, web_search, code_executor)
        tool_name: 工具名称
        params: 参数

    Returns:
        执行结果 JSON 字符串
    """
    registry = await get_skills_registry()
    skill = registry.get_skill(service_name)

    if not skill or skill.type != SkillType.MCP:
        return json.dumps({"error": f"服务不存在: {service_name}"})

    try:
        module_path = skill.module.replace(".", "/") + ".py"
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"mcp_{service_name}", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "service") or hasattr(module, "service"):
                result = await module.service.handle_handoff({"tool_name": tool_name, **params})
                return result
    except Exception as e:
        return json.dumps({"error": f"服务调用失败: {str(e)}"})

    return json.dumps({"error": "服务未正确实现"})


async def get_mcp_tools_schema() -> List[Dict[str, Any]]:
    """获取所有 MCP 服务的工具 schema (供 ToolNet 使用)"""
    registry = await get_skills_registry()
    tools = []

    for skill in registry.list_skills(SkillType.MCP):
        metadata = skill.metadata
        # 支持两种格式: capabilities.tools 或直接 tools
        tool_list = metadata.get("capabilities", {}).get("tools") or metadata.get("tools", [])
        for tool in tool_list:
            tools.append(
                {
                    "name": f"mcp_{skill.name}_{tool['name']}",
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                    "service": skill.name,
                    "tool": tool["name"],
                }
            )

    return tools


def list_all_skills() -> Dict[str, List[str]]:
    """列出所有技能"""

    async def get():
        registry = await get_skills_registry()
        return {
            "agents": registry.list_agents(),
            "commands": registry.list_commands(),
            "mcp_services": registry.list_mcp_services(),
        }

    import asyncio

    return asyncio.run(get())
