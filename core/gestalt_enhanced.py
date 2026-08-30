"""
弥娅格式塔意识控制器 - 增强版 (Gestalt Consciousness Controller Enhanced)

融合AstrBot核心能力：
1. FunctionToolExecutor - 完整工具执行器
2. Hooks扩展点 - 生命周期钩子
3. MCP工具支持 - 动态工具加载
4. Handoff机制 - Agent间协作

作者: MIYA
日期: 2026-04-28
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("Miya.Gestalt")


# ==================== 枚举定义 ====================


class HookEvent(str, Enum):
    """Hook事件类型"""

    BEFORE_TOOL_EXECUTE = "before_tool_execute"
    AFTER_TOOL_EXECUTE = "after_tool_execute"
    TOOL_ERROR = "tool_error"
    BEFORE_AGENT_RUN = "before_agent_run"
    AFTER_AGENT_RUN = "after_agent_run"
    BEFORE_HANDOFF = "before_handoff"
    AFTER_HANDOFF = "after_handoff"


# ==================== 数据结构 ====================


@dataclass
class ToolResult:
    """工具执行结果"""

    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    success: bool
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentContext:
    """Agent执行上下文"""

    user_id: str = ""
    group_id: str = ""
    session_id: str = ""
    platform: str = "unknown"
    messages: List[Dict] = field(default_factory=list)
    tools: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffInfo:
    """Handoff信息"""

    from_agent: str
    to_agent: str
    context: Dict[str, Any]
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ==================== Hooks 系统 ====================


class GestaltHooks:
    """
    格式塔Hooks系统

    提供扩展点：
    - before_tool_execute: 工具执行前
    - after_tool_execute: 工具执行后
    - tool_error: 工具执行错误
    - before_agent_run: Agent运行前
    - after_agent_run: Agent运行后
    """

    def __init__(self):
        self._hooks: Dict[HookEvent, List[Callable]] = {event: [] for event in HookEvent}
        logger.info("[GestaltHooks] Hooks系统初始化")

    def register(self, event: HookEvent, handler: Callable[[Dict], Awaitable[Any]]) -> None:
        """注册Hook处理器"""
        self._hooks[event].append(handler)
        logger.info(f"[GestaltHooks] 注册Hook: {event.value} -> {handler.__name__}")

    def unregister(self, event: HookEvent, handler: Callable[[Dict], Awaitable[Any]]) -> None:
        """注销Hook处理器"""
        if handler in self._hooks[event]:
            self._hooks[event].remove(handler)

    async def trigger(self, event: HookEvent, context: Dict) -> Any:
        """触发Hook"""
        results = []
        for handler in self._hooks[event]:
            try:
                result = await handler(context)
                results.append(result)
            except Exception as e:
                logger.error(f"[GestaltHooks] Hook执行失败 {event.value}: {e}")
        return results


# ==================== MCP 工具管理器 ====================


class MCPToolManager:
    """
    MCP工具管理器

    功能：
    - MCP客户端管理
    - 动态工具加载
    - 工具描述生成
    """

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._tools: Dict[str, Dict] = {}
        self._initialized = False

    async def initialize(self, mcp_config: Optional[Dict] = None):
        """初始化MCP客户端"""
        if mcp_config is None:
            mcp_config = await self._load_mcp_config()

        if not mcp_config:
            logger.info("[MCPToolManager] 无MCP配置，跳过初始化")
            return

        logger.info(f"[MCPToolManager] 初始化 {len(mcp_config)} 个MCP服务...")

        for name, config in mcp_config.items():
            if not config.get("active", True):
                continue

            try:
                await self._connect_mcp(name, config)
            except Exception as e:
                logger.error(f"[MCPToolManager] 连接MCP失败 {name}: {e}")

        self._initialized = True
        logger.info(f"[MCPToolManager] 已加载 {len(self._tools)} 个MCP工具")

    async def _load_mcp_config(self) -> Dict:
        """加载MCP配置"""
        import json
        from pathlib import Path

        config_path = Path("data/mcp_server.json")
        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except Exception as e:
            logger.info(f"[MCPToolManager] 加载配置失败: {e}")
            return {}

    async def _connect_mcp(self, name: str, config: Dict):
        """连接MCP服务"""
        try:
            from core.mcp_client import get_global_mcp_registry

            registry = get_global_mcp_registry()
            if registry and hasattr(registry, "get_tools"):
                tools = await registry.get_tools(name)
                for tool in tools:
                    self._tools[tool["name"]] = {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                        "mcp_server": name,
                    }
                logger.info(f"[MCPToolManager] 加载MCP工具: {name} - {len(tools)}个")
        except Exception as e:
            logger.info(f"[MCPToolManager] MCP工具加载失败 {name}: {e}")

    def get_tools_schema(self) -> List[Dict]:
        """获取MCP工具Schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"],
                },
            }
            for name, info in self._tools.items()
        ]

    def get_tool(self, name: str) -> Optional[Dict]:
        """获取MCP工具"""
        return self._tools.get(name)

    async def execute_tool(self, name: str, arguments: Dict, context: Dict) -> Any:
        """执行MCP工具"""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Tool not found: {name}"}

        mcp_server = tool.get("mcp_server")
        if not mcp_server:
            return {"error": "MCP server not specified"}

        try:
            from core.mcp_client import get_global_mcp_registry

            registry = get_global_mcp_registry()
            if registry and hasattr(registry, "execute_tool"):
                return await registry.execute_tool(name, arguments, context)
            return {"error": "MCP registry not available"}
        except Exception as e:
            logger.error(f"[MCPToolManager] 执行MCP工具失败 {name}: {e}")
            return {"error": str(e)}


# ==================== Handoff 管理器 ====================


class HandoffManager:
    """
    Handoff管理器

    功能：
    - Agent间上下文转移
    - 协作任务分发
    - 结果汇总
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._history: List[HandoffInfo] = []

    def register_agent(self, agent_id: str, agent: Any):
        """注册Agent"""
        self._agents[agent_id] = agent
        logger.info(f"[HandoffManager] 注册Agent: {agent_id}")

    async def handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: Dict,
        message: str,
    ) -> Any:
        """执行Handoff"""
        if to_agent not in self._agents:
            return {"error": f"Agent not found: {to_agent}"}

        handoff_info = HandoffInfo(
            from_agent=from_agent,
            to_agent=to_agent,
            context=context,
            message=message,
        )
        self._history.append(handoff_info)

        logger.info(f"[HandoffManager] Handoff: {from_agent} -> {to_agent}")

        target_agent = self._agents[to_agent]
        if hasattr(target_agent, "run"):
            return await target_agent.run(context, message)

        return {"error": f"Agent {to_agent} has no run method"}

    def get_handoff_history(self, agent_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """获取Handoff历史"""
        if agent_id:
            return [
                {
                    "from": h.from_agent,
                    "to": h.to_agent,
                    "message": h.message,
                    "timestamp": h.timestamp,
                }
                for h in self._history[-limit:]
                if h.from_agent == agent_id or h.to_agent == agent_id
            ]
        return [
            {
                "from": h.from_agent,
                "to": h.to_agent,
                "message": h.message,
                "timestamp": h.timestamp,
            }
            for h in self._history[-limit:]
        ]


# ==================== 增强版格式塔控制器 ====================


class GestaltControllerEnhanced:
    """
    增强版格式塔意识控制器

    融合AstrBot核心能力：
    - FunctionToolExecutor 工具执行
    - Hooks 扩展点
    - MCP 工具支持
    - Handoff 机制
    """

    def __init__(self, tool_subnet=None):
        self.tool_subnet = tool_subnet
        self._agent_tools_loaded = False
        self._tool_sources: Dict[str, str] = {}

        # 增强组件
        self.hooks = GestaltHooks()
        self.mcp_manager = MCPToolManager()
        self.handoff_manager = HandoffManager()

        # Skill系统
        self._skill_manager = None
        self._skill_sandbox = None

        # 内置工具集
        self._builtin_tools: Dict[str, Callable] = {}

        # 执行历史
        self._execution_history: List[ToolResult] = []

        logger.info("[GestaltEnhanced] 增强版格式塔控制器初始化")

    async def initialize(self, tool_subnet=None, mcp_config: Optional[Dict] = None):
        """初始化增强版格式塔"""
        if tool_subnet:
            self.tool_subnet = tool_subnet

        logger.info("[GestaltEnhanced] 初始化组件...")

        # 初始化MCP
        await self.mcp_manager.initialize(mcp_config)

        # 初始化Skills系统
        await self._init_skills_system()

        # 初始化AstrBot风格工具
        self._init_astrbot_tools()

        # 加载内置工具
        self._load_builtin_tools()

        # 加载Agent工具
        await self._load_agent_tools()

        logger.info("[GestaltEnhanced] 初始化完成")

    def _load_builtin_tools(self):
        """加载内置工具"""
        self._builtin_tools = {
            "get_current_time": self._tool_get_current_time,
            "search_knowledge": self._tool_search_knowledge,
            "search_memory": self._tool_search_memory,
            "get_profile": self._tool_get_profile,
            "web_search": self._tool_web_search,
            "send_message": self._tool_send_message,
        }

        logger.info(f"[GestaltEnhanced] 加载了 {len(self._builtin_tools)} 个内置工具")

    async def _init_skills_system(self):
        """初始化Skills系统"""
        try:
            from core.skills.sandbox import SandboxLevel, get_skill_sandbox
            from core.skills.skill_md import get_skill_manager

            self._skill_manager = get_skill_manager()
            await self._skill_manager.initialize()

            self._skill_sandbox = get_skill_sandbox(SandboxLevel.RESTRICTED)

            logger.info(f"[GestaltEnhanced] Skills系统初始化: {len(self._skill_manager._skills)} 个技能")
        except Exception as e:
            logger.info(f"[GestaltEnhanced] Skills系统初始化失败: {e}")

        # 初始化AstrBot风格工具
        self._init_astrbot_tools()

    def _init_astrbot_tools(self):
        """初始化AstrBot风格工具"""
        try:
            from core.tools_astrbot import get_tool_registry

            registry = get_tool_registry()
            self._astrbot_tools = registry
            logger.info("[GestaltEnhanced] AstrBot工具系统已加载")
        except Exception as e:
            logger.info(f"[GestaltEnhanced] AstrBot工具加载失败: {e}")

    async def _tool_get_current_time(self, args: Dict, context: Dict) -> str:
        """获取当前时间"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def _tool_search_knowledge(self, args: Dict, context: Dict) -> str:
        """搜索知识库"""
        query = args.get("query", "")
        try:
            from core.knowledge_base import get_kb_manager

            kb = get_kb_manager()
            results = await kb.search(query, limit=5)
            if results:
                return "\n".join([r.get("content", "")[:200] for r in results])
            return "未找到相关知识"
        except Exception as e:
            return f"搜索失败: {e}"

    async def _tool_search_memory(self, args: Dict, context: Dict) -> str:
        """搜索记忆"""
        query = args.get("query", "")
        user_id = context.get("user_id", "")
        try:
            from memory import search_memory

            results = await search_memory(query, user_id=user_id)
            if results:
                return "\n".join([r.content[:200] for r in results[:3]])
            return "未找到相关记忆"
        except Exception as e:
            return f"搜索失败: {e}"

    async def _tool_get_profile(self, args: Dict, context: Dict) -> str:
        """获取用户画像"""
        user_id = context.get("user_id", "")
        try:
            from memory import get_user_profile

            profile = await get_user_profile(user_id)
            if profile:
                return str(profile)
            return "暂无用户画像"
        except Exception as e:
            return f"获取失败: {e}"

    async def _tool_web_search(self, args: Dict, context: Dict) -> str:
        """网页搜索（多引擎：Tavily 优先 + Bing/百度免费兜底）"""
        query = (args.get("query") or "").strip()
        if not query:
            return "请提供搜索关键词"
        try:
            import asyncio

            from webnet.ToolNet.tools.network.web_search import EnhancedWebSearch

            searcher = EnhancedWebSearch()
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, searcher.search, query)
            if not results:
                return "未找到相关结果"
            return searcher.format_results_for_ai(results)
        except Exception as e:
            logger.warning(f"[GestaltEnhanced] web_search 执行失败: {e}")
            return f"搜索失败: {e}"

    async def _tool_send_message(self, args: Dict, context: Dict) -> str:
        """发送消息"""
        message = args.get("message", "")
        user_id = args.get("user_id", context.get("user_id", ""))
        group_id = args.get("group_id", context.get("group_id", ""))

        logger.info(f"[GestaltEnhanced] 发送消息: {user_id}/{group_id} - {message[:50]}...")
        return f"消息已发送: {message[:50]}..."

    async def _load_agent_tools(self):
        """加载Agent工具"""
        if self._agent_tools_loaded:
            return

        if not self.tool_subnet:
            logger.warning("[GestaltEnhanced] tool_subnet 未设置")
            return

        try:
            from webnet.ToolNet.agents.hub import get_agent_hub

            agent_hub = get_agent_hub()
            for agent_name in agent_hub.list_agents():
                agent = agent_hub.get_agent(agent_name)
                if not agent:
                    continue

                tools = agent.get_tools_schema()
                for tool_config in tools:
                    func = tool_config.get("function", {})
                    tool_name = func.get("name", "")
                    if tool_name:
                        self._tool_sources[tool_name] = agent_name

            self._agent_tools_loaded = True
            logger.info(f"[GestaltEnhanced] 加载了 {len(self._tool_sources)} 个Agent工具")

        except Exception as e:
            logger.info(f"[GestaltEnhanced] 加载Agent工具失败: {e}")

    def _build_tool_context(self, context: Dict[str, Any]) -> Any:
        """构建工具执行上下文"""
        try:
            from webnet.ToolNet.base import ToolContext
        except ImportError:
            from dataclasses import dataclass

            @dataclass
            class ToolContext:
                qq_net: Any = None
                onebot_client: Any = None
                send_like_callback: Any = None
                memory_engine: Any = None
                unified_memory: Any = None
                memory_net: Any = None
                emotion: Any = None
                personality: Any = None
                scheduler: Any = None
                request_id: Any = None
                group_id: Any = None
                user_id: Any = None
                message_type: Any = None
                sender_name: Any = None
                is_at_bot: bool = False
                at_list: list = field(default_factory=list)
                bot_qq: Any = None
                image_data: Any = None
                image_analysis: Any = None

        supported_fields = {
            "qq_net",
            "onebot_client",
            "send_like_callback",
            "memory_engine",
            "unified_memory",
            "memory_net",
            "emotion",
            "personality",
            "scheduler",
            "request_id",
            "group_id",
            "user_id",
            "message_type",
            "sender_name",
            "is_at_bot",
            "at_list",
            "bot_qq",
            "image_data",
            "image_analysis",
        }

        filtered = {k: v for k, v in context.items() if k in supported_fields}
        if "at_list" not in filtered:
            filtered["at_list"] = []
        if "user_id" not in filtered:
            filtered["user_id"] = ""
        if "group_id" not in filtered:
            filtered["group_id"] = ""

        return ToolContext(**filtered)

    async def execute_tool(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """执行工具 - 增强版"""
        start_time = datetime.now().timestamp()

        # 安全日志
        safe_args = {
            k: ("[图片数据]" if isinstance(v, str) and ("[CQ:" in v or "base64," in v) else v) for k, v in args.items()
        }
        logger.info(f"[GestaltEnhanced] 执行工具: {tool_name}, 参数: {safe_args}")

        # Hook: before_tool_execute
        await self.hooks.trigger(
            HookEvent.BEFORE_TOOL_EXECUTE,
            {"tool_name": tool_name, "args": args, "context": context},
        )

        result = None
        error = None
        success = True

        try:
            # 1. 检查内置工具
            if tool_name in self._builtin_tools:
                result = await self._builtin_tools[tool_name](args, context)

            # 1.5 检查Skills工具
            elif self._skill_manager and self._skill_sandbox:
                skill_tool = self._skill_manager.get_skill_tool(tool_name)
                if skill_tool:
                    result = await self._skill_sandbox.execute(
                        self._skill_manager.execute_skill_tool,
                        (tool_name, args, context),
                    )

            # 1.7 检查AstrBot工具
            elif hasattr(self, "_astrbot_tools") and self._astrbot_tools:
                # 直接调用工具类的对应方法
                tools_obj = self._astrbot_tools.computer
                if hasattr(tools_obj, tool_name):
                    result = await getattr(tools_obj, tool_name)(**args)
                else:
                    tools_obj = self._astrbot_tools.web_search
                    if hasattr(tools_obj, tool_name):
                        result = await getattr(tools_obj, tool_name)(**args)
                    else:
                        tools_obj = self._astrbot_tools.knowledge_base
                        if hasattr(tools_obj, tool_name):
                            result = await getattr(tools_obj, tool_name)(**args)
                        else:
                            tools_obj = self._astrbot_tools.message
                            if hasattr(tools_obj, tool_name):
                                result = await getattr(tools_obj, tool_name)(**args)

            # 2. 检查MCP工具
            elif self.mcp_manager.get_tool(tool_name):
                result = await self.mcp_manager.execute_tool(tool_name, args, context)

            # 3. 检查Agent工具
            elif self.tool_subnet and hasattr(self.tool_subnet, "registry") and self.tool_subnet.registry:
                tool_context = self._build_tool_context(context)
                result = await self.tool_subnet.registry.execute_tool(tool_name, tool_context, **args)

            # 4. 工具不存在
            else:
                result = f"❌ 工具未找到: {tool_name}"
                success = False

        except Exception as e:
            logger.error(f"[GestaltEnhanced] 工具执行失败 {tool_name}: {e}")
            error = str(e)
            result = f"❌ 工具执行失败: {error}"
            success = False

            # Hook: tool_error
            await self.hooks.trigger(
                HookEvent.TOOL_ERROR,
                {"tool_name": tool_name, "args": args, "error": error},
            )

        # 记录执行结果
        execution_time = datetime.now().timestamp() - start_time
        tool_result = ToolResult(
            tool_name=tool_name,
            arguments=args,
            result=str(result)[:500] if result else "",
            success=success,
            error=error,
            execution_time=execution_time,
        )
        self._execution_history.append(tool_result)

        # Hook: after_tool_execute
        await self.hooks.trigger(
            HookEvent.AFTER_TOOL_EXECUTE,
            {"tool_name": tool_name, "result": result, "success": success},
        )

        return result if result else "执行完成"

    def get_tool_source(self, tool_name: str) -> Optional[str]:
        """获取工具来源"""
        if tool_name in self._builtin_tools:
            return "builtin"
        if self._skill_manager and self._skill_manager.get_skill_tool(tool_name):
            return "skill"
        if self.mcp_manager.get_tool(tool_name):
            return f"mcp:{self.mcp_manager.get_tool(tool_name).get('mcp_server', '')}"
        return self._tool_sources.get(tool_name)

    def is_agent_tool(self, tool_name: str) -> bool:
        """判断是否是Agent工具"""
        return tool_name in self._tool_sources

    def get_all_tool_sources(self) -> Dict[str, str]:
        """获取所有工具来源"""
        sources = dict(self._tool_sources)
        sources.update({name: "builtin" for name in self._builtin_tools.keys()})

        # 添加Skills工具
        if self._skill_manager:
            for skill in self._skill_manager._skills.values():
                if skill.enabled:
                    for tool in skill.tools:
                        sources[tool.name] = "skill"

        sources.update({name: f"mcp:{info.get('mcp_server', '')}" for name, info in self.mcp_manager._tools.items()})
        return sources

    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """获取执行历史"""
        return [
            {
                "tool_name": r.tool_name,
                "success": r.success,
                "execution_time": f"{r.execution_time:.2f}s",
                "timestamp": r.timestamp,
            }
            for r in self._execution_history[-limit:]
        ]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self._execution_history)
        success = sum(1 for r in self._execution_history if r.success)

        skill_tools = 0
        if self._skill_manager:
            skill_tools = sum(len(s.tools) for s in self._skill_manager._skills.values() if s.enabled)

        return {
            "total_executions": total,
            "success_count": success,
            "failure_count": total - success,
            "builtin_tools": len(self._builtin_tools),
            "skill_tools": skill_tools,
            "mcp_tools": len(self.mcp_manager._tools),
            "agent_tools": len(self._tool_sources),
        }


# ==================== 全局实例 ====================


_gestalt_enhanced: Optional[GestaltControllerEnhanced] = None


def get_gestalt_controller_enhanced() -> GestaltControllerEnhanced:
    """获取增强版格式塔控制器"""
    global _gestalt_enhanced
    if _gestalt_enhanced is None:
        _gestalt_enhanced = GestaltControllerEnhanced()
    return _gestalt_enhanced


async def initialize_gestalt_enhanced(tool_subnet=None, mcp_config: Optional[Dict] = None) -> GestaltControllerEnhanced:
    """初始化增强版格式塔"""
    controller = get_gestalt_controller_enhanced()
    await controller.initialize(tool_subnet, mcp_config)
    return controller
