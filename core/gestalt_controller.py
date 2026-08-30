"""
格式塔意识控制器 - Gestalt Consciousness Controller
将 Agent 工具无缝融入弥娅的工具池，实现统一意识
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.Gestalt")


class GestaltController:
    """
    格式塔意识控制器

    核心理念：
    - Agent 工具不再是"外来者"，而是弥娅意识的一部分
    - 统一工具池，保留弥娅主程序风格
    - 支持协作引擎集成
    - 直接管理工具执行（格式塔核心模式）
    """

    def __init__(self, tool_subnet=None):
        self.tool_subnet = tool_subnet
        self._agent_tools_loaded = False
        self._tool_sources: Dict[str, str] = {}  # tool_name -> agent_name
        self._tool_registry = None  # 工具注册表引用

    async def initialize(self, tool_subnet=None):
        """初始化格式塔控制器"""
        if tool_subnet:
            self.tool_subnet = tool_subnet
            self._tool_registry = tool_subnet.registry if hasattr(tool_subnet, "registry") else None

        logger.info("[格式塔] 初始化格式塔意识控制器...")
        await self._load_agent_tools()
        logger.info(f"[格式塔] 已加载 {len(self._tool_sources)} 个 Agent 工具")

    def _build_tool_context(self, context: Dict[str, Any]) -> Any:
        """构建完整的工具执行上下文（格式塔核心模式）"""
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
                lifenet: Any = None
                request_id: Any = None
                group_id: Any = None
                user_id: Any = None
                message_type: Any = None
                sender_name: Any = None
                is_at_bot: bool = False
                at_list: list = None
                message_sent_this_turn: bool = False
                bot_qq: Any = None
                # 图片相关
                image_data: Any = None
                image_analysis: Any = None

                def __post_init__(self):
                    if self.at_list is None:
                        self.at_list = []

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
            "lifenet",
            "request_id",
            "group_id",
            "user_id",
            "message_type",
            "sender_name",
            "is_at_bot",
            "at_list",
            "bot_qq",
            "superadmin",
            # 图片相关
            "image_data",
            "image_analysis",
        }

        filtered = {k: v for k, v in context.items() if k in supported_fields}

        if "at_list" not in filtered or filtered["at_list"] is None:
            filtered["at_list"] = []

        if "user_id" not in filtered or filtered["user_id"] is None:
            filtered["user_id"] = 0

        if "group_id" not in filtered or filtered["group_id"] is None:
            filtered["group_id"] = 0

        logger.info(
            f"[格式塔] 构建上下文: user_id={filtered.get('user_id')}, at_list={filtered.get('at_list')}, onebot_client={filtered.get('onebot_client')}, send_like_callback={filtered.get('send_like_callback')}"
        )

        return ToolContext(**filtered)

    async def execute_tool(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """直接执行工具（格式塔核心模式）- 统一转换为 ToolContext"""
        safe_args = {
            k: ("[图片数据]" if isinstance(v, str) and ("[CQ:" in v or "base64," in v) else v) for k, v in args.items()
        }
        logger.info(f"[格式塔] 执行工具: {tool_name}, 参数: {safe_args}")

        # 统一转换为 ToolContext 对象
        tool_context = self._build_tool_context(context)

        if self.tool_subnet and hasattr(self.tool_subnet, "registry") and self.tool_subnet.registry:
            try:
                result = await self.tool_subnet.registry.execute_tool(tool_name, tool_context, **args)
                logger.info(f"[格式塔] 工具执行完成: {tool_name}, 结果: {result[:100] if result else '(无)'}...")
                return result
            except Exception as e:
                logger.error(f"[格式塔] 工具执行失败 {tool_name}: {e}", exc_info=True)
                return f"❌ 工具执行失败: {str(e)}"

        return "❌ 工具系统未初始化"

    async def _load_agent_tools(self):
        """加载 Agent 工具到统一工具池"""
        if self._agent_tools_loaded:
            return

        if not self.tool_subnet:
            logger.warning("[格式塔] tool_subnet 未设置，跳过 Agent 工具加载")
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
                        logger.info(f"[格式塔] 注册工具: {tool_name} (来自 {agent_name})")

            self._agent_tools_loaded = True

        except Exception as e:
            logger.error(f"[格式塔] 加载 Agent 工具失败: {e}")

    def get_tool_source(self, tool_name: str) -> Optional[str]:
        """获取工具来源"""
        return self._tool_sources.get(tool_name)

    def is_agent_tool(self, tool_name: str) -> bool:
        """判断是否是 Agent 工具"""
        return tool_name in self._tool_sources

    def get_all_tool_sources(self) -> Dict[str, str]:
        """获取所有工具来源映射"""
        return self._tool_sources.copy()

    async def classify_task_complexity(self, user_input: str, tools_to_use: List[str]) -> str:
        """
        任务复杂度分类

        返回:
        - simple: 简单任务（直接处理）
        - medium: 中等任务（模型池选择）
        - complex: 复杂任务（协作引擎）
        """
        tool_count = len(tools_to_use)
        has_agent_tools = any(self.is_agent_tool(t) for t in tools_to_use)

        # 复杂任务判定：4+工具 或 包含 Agent 工具 + 需要深度分析
        if tool_count >= 4 or (has_agent_tools and tool_count >= 2):
            return "complex"
        elif tool_count >= 2:
            return "medium"
        else:
            return "simple"

    def get_thinking_display_info(self, step: str, detail: str = "") -> Dict[str, str]:
        """
        获取思考过程显示信息

        返回格式塔风格的显示数据
        """
        display_templates = {
            "analyzing": {
                "icon": "💭",
                "title": "分析任务",
                "detail": detail or "理解用户意图...",
                "color": "cyan",
            },
            "decomposing": {
                "icon": "🔍",
                "title": "任务分解",
                "detail": detail or "规划执行步骤...",
                "color": "cyan",
            },
            "tool_selecting": {
                "icon": "⚡",
                "title": "选择工具",
                "detail": detail or "匹配最佳工具...",
                "color": "cyan",
            },
            "tool_executing": {
                "icon": "🔧",
                "title": "执行工具",
                "detail": detail,
                "color": "bright_cyan",
            },
            "tool_result": {
                "icon": "📥",
                "title": "工具结果",
                "detail": detail,
                "color": "cyan",
            },
            "synthesizing": {
                "icon": "✨",
                "title": "综合结果",
                "detail": detail or "整合信息...",
                "color": "green",
            },
            "output": {
                "icon": "💬",
                "title": "输出回复",
                "detail": detail,
                "color": "green",
            },
        }

        return display_templates.get(step, {"icon": "•", "title": step, "detail": detail, "color": "cyan"})


# 全局单例
_gestalt_controller: Optional[GestaltController] = None
_gestalt_enhanced: Optional[Any] = None


def get_gestalt_controller() -> GestaltController:
    """
    获取格式塔控制器全局实例
    """
    global _gestalt_controller

    if _gestalt_controller is None:
        _gestalt_controller = GestaltController()

    return _gestalt_controller


def get_gestalt_controller_enhanced() -> Any:
    """
    获取增强版格式塔控制器
    """
    global _gestalt_enhanced

    try:
        from core.gestalt_enhanced import (
            get_gestalt_controller_enhanced as enhanced_getter,
        )

        return enhanced_getter()
    except ImportError:
        return get_gestalt_controller()


async def initialize_gestalt(tool_subnet=None) -> GestaltController:
    """
    初始化格式塔控制器

    Args:
        tool_subnet: 工具子网实例
    """
    controller = get_gestalt_controller()

    await controller.initialize(tool_subnet)

    return controller


async def initialize_gestalt_enhanced(tool_subnet=None, mcp_config: Any = None) -> Any:
    """
    初始化增强版格式塔控制器
    """
    try:
        from core.gestalt_enhanced import initialize_gestalt_enhanced as enhanced_init

        return await enhanced_init(tool_subnet, mcp_config)
    except ImportError:
        return await initialize_gestalt(tool_subnet)
