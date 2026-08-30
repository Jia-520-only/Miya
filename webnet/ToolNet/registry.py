"""
ToolNet 工具注册表（兼容层）

兼容旧版 tools/ 系统，同时支持子网架构
注意：ToolContext 已统一到 webnet.tools.base，此处仅保留兼容导入
"""

import logging
from typing import Any, Dict, List, Optional

from webnet.ToolNet.base import ToolContext

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.logger = logging.getLogger(__name__)

    def register(self, tool: "BaseTool") -> bool:
        """注册工具"""
        try:
            tool_name = tool.config.get("name")
            if not tool_name:
                self.logger.error(f"工具缺少 name 属性: {tool.__class__.__name__}")
                return False

            self.tools[tool_name] = tool
            self.logger.info(f"已注册工具: {tool_name}")
            return True
        except Exception as e:
            self.logger.error(f"注册工具失败: {e}", exc_info=True)
            return False

    def get_tool(self, name: str) -> Optional["BaseTool"]:
        """获取工具实例"""
        return self.tools.get(name)

    def get_tools_schema(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        获取工具配置（OpenAI Function Calling 格式）

        Args:
            tool_names: 要获取的工具名称列表，None 表示获取所有工具

        Returns:
            工具配置列表
        """
        tools_to_fetch = self.tools
        if tool_names is not None:
            tools_to_fetch = {name: tool for name, tool in self.tools.items() if name in tool_names}

        tools_schema = []
        for tool in tools_to_fetch.values():
            tool_config = tool.config.copy()
            # 增强工具描述：添加明确的调用时机说明
            description = tool_config.get("description", "")
            # 确保描述足够清晰，包含何时调用
            if "当" not in description and "调用" not in description and "如果" not in description:
                # 为没有明确调用时机描述的工具添加提示
                tool_config["description"] = f"[工具] {description}\n调用时机：当用户明确请求此功能时调用。"

            tools_schema.append({"type": "function", "function": tool_config})

        self.logger.info(f"[ToolRegistry] 生成工具schema，共{len(tools_schema)}个工具")
        return tools_schema

    async def execute_tool(self, name: str, context, **kwargs) -> str:
        """执行工具（含权限检查）- BaseTool 标准签名"""
        tool = self.get_tool(name)
        if not tool:
            return f"❌ 工具不存在: {name}"

        # 【新增】权限检查
        permission_check = await self._check_tool_permission(name, context)
        if not permission_check["allowed"]:
            self.logger.warning(
                f"[权限拒绝] 用户 {getattr(context, 'user_id', 'unknown')} 尝试执行工具 {name}，缺少权限"
            )
            from core.text_loader import get_permission

            denied_msg = get_permission("tool_permissions.denied_message", "")
            if denied_msg:
                return denied_msg.format(
                    tool_name=name,
                    permission=permission_check.get("required_permission", "unknown"),
                )
            return get_permission(
                "tool_permissions.denied_message",
                "❌ 权限不足：执行工具 '{tool_name}' 需要权限 '{permission}'",
            ).format(
                tool_name=name,
                permission=permission_check.get("required_permission", "unknown"),
            )

        try:
            # 验证参数（如果工具实现了validate_args方法）
            if hasattr(tool, "validate_args") and callable(tool.validate_args):
                valid, error = tool.validate_args(kwargs)
                if not valid:
                    return f"❌ 参数错误: {error}"

            # 执行工具 - 检测工具的签名类型并适配调用
            logger.info(f"[Registry] 执行工具: {name}, kwargs: {list(kwargs.keys())}")

            # 统一签名: execute(self, args, context)。保留旧签名 (context, **kwargs) 兜底。
            try:
                result = await tool.execute(kwargs, context)
            except TypeError:
                result = await tool.execute(context, **kwargs)

            return result
        except Exception as e:
            self.logger.error(f"执行工具失败 {name}: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    async def _check_tool_permission(self, tool_name: str, context: ToolContext) -> Dict[str, Any]:
        """
        检查用户是否有执行工具的权限

        Args:
            tool_name: 工具名称
            context: 工具执行上下文

        Returns:
            包含 allowed 和 required_permission 的字典
        """
        try:
            from webnet.AuthNet.permission_core import PermissionCore
            from webnet.AuthNet.user_mapper import UserMapper

            user_id = getattr(context, "user_id", None)
            group_id = getattr(context, "group_id", None)
            platform = getattr(context, "platform", None)

            if platform is None:
                platform = self._detect_platform_from_context(context)

            superadmin = getattr(context, "superadmin", None)
            onebot_client = getattr(context, "onebot_client", None)

            if user_id is None or user_id == 0:
                self.logger.info("[权限检查] user_id 未指定，跳过权限检查")
                return {"allowed": True, "required_permission": None}

            if superadmin and user_id == superadmin:
                self.logger.info(f"[权限检查] 用户 {user_id} 是超级管理员，放行")
                return {"allowed": True, "required_permission": None}

            if group_id and onebot_client:
                try:
                    member_info = await onebot_client.get_group_member_info(group_id=group_id, user_id=user_id)
                    role = member_info.get("role", "member")
                    if role in ["owner", "admin"]:
                        self.logger.info(f"[权限检查] 用户 {user_id} 是群管理员(role={role})，放行")
                        return {"allowed": True, "required_permission": None}
                except Exception as e:
                    self.logger.warning(f"[权限检查] 获取群成员信息失败: {e}")

            user_mapper = UserMapper()
            unified_user_id = user_mapper.generate_user_id(platform, str(user_id))
            required_permission = f"tool.{tool_name}"

            perm_core = PermissionCore()
            has_permission = perm_core.check_permission(unified_user_id, required_permission)

            if not has_permission:
                has_permission = perm_core.check_permission("system_admin", required_permission)

            return {
                "allowed": has_permission,
                "required_permission": required_permission,
                "user_id": unified_user_id,
            }

        except Exception as e:
            self.logger.warning(f"[权限检查异常] {e}，允许执行")
            return {"allowed": True, "required_permission": None, "error": str(e)}

    def _detect_platform_from_context(self, context: ToolContext) -> str:
        """从上下文检测平台类型"""
        # 尝试从多个属性检测平台
        if hasattr(context, "platform"):
            return context.platform

        # 根据消息类型或其他属性推断
        if hasattr(context, "message_type"):
            if context.message_type == "private":
                return "qq"  # 默认为QQ
            elif context.message_type == "group":
                return "qq"

        return "terminal"  # 默认平台

    def clear(self):
        """清空注册表"""
        self.tools.clear()
        self.logger.info("工具注册表已清空")

    def load_all_tools(self):
        """加载所有工具"""
        self._load_basic_tools()
        self._load_terminal_tools()
        self._load_message_tools()
        self._load_group_tools()
        self._load_memory_tools()
        self._load_knowledge_tools()
        self._load_cognitive_tools()
        self._load_bilibili_tools()
        self._load_scheduler_tools()
        self._load_entertainment_tools()
        self._load_qq_multimedia_tools()
        self._load_file_library_tools()
        self._load_lifenet_tools()
        self._load_model_management_tools()
        self._load_cross_terminal_tools()
        self._load_visualization_tools()
        self._load_network_tools()
        self._load_core_tools()
        self._load_social_tools()
        self._load_agent_tools()
        self._load_music_tools()
        self._load_mcp_tools()
        self._load_file_analysis_tools()
        self._load_group_analysis_tools()
        self._load_render_tools()
        self._load_earth_online_tools()

    def _load_basic_tools(self):
        """加载基础工具"""
        from webnet.ToolNet.tools.basic.get_current_time import GetCurrentTime
        from webnet.ToolNet.tools.basic.get_user_info import GetUserInfo
        from webnet.ToolNet.tools.basic.python_interpreter import PythonInterpreter
        from webnet.ToolNet.tools.basic.video_download import VideoDownloadTool
        from webnet.ToolNet.tools.basic.download_file import DownloadFileTool
        from webnet.ToolNet.tools.basic.resource_find import ResourceFindTool
        from webnet.ToolNet.tools.basic.browse_web import BrowseWebTool
        from webnet.ToolNet.tools.basic.jmcomic_download import JmcomicDownloadTool

        self.register(GetCurrentTime())
        self.register(GetUserInfo())
        self.register(PythonInterpreter())
        self.register(VideoDownloadTool())
        self.register(DownloadFileTool())
        self.register(ResourceFindTool())
        self.register(BrowseWebTool())
        self.register(JmcomicDownloadTool())

    def _load_terminal_tools(self):
        """终端功能已由 Open-ClaudeCode 提供"""
        self.logger.info("终端功能由 Open-ClaudeCode 提供")

    def _load_terminal_net_tools(self):
        """终端功能已由 Open-ClaudeCode 提供"""
        self.logger.info("终端功能由 Open-ClaudeCode 提供")

    def _load_ultra_terminal_tools(self):
        """终端功能已由 Open-ClaudeCode 提供"""
        self.logger.info("终端功能由 Open-ClaudeCode 提供")

    def _load_model_management_tools(self):
        """加载模型管理工具"""
        try:
            from webnet.ToolNet.tools.model_management import ModelManagementTool

            self.register(ModelManagementTool())
            self.logger.info("模型管理工具已注册")
        except Exception as e:
            self.logger.warning(f"加载模型管理工具失败: {e}")

    def _load_cross_terminal_tools(self):
        """跨端功能已由 Open-ClaudeCode 提供"""
        self.logger.info("跨端功能由 Open-ClaudeCode 提供")

    def _register_cross_terminal_tool(self, name: str, func):
        """跨端功能已由 Open-ClaudeCode 提供"""
        pass

    def _load_message_tools(self):
        """加载消息工具"""
        from webnet.ToolNet.tools.message.get_recent_messages import (
            GetRecentMessagesTool,
        )
        from webnet.ToolNet.tools.message.send_message import SendMessageTool
        from webnet.ToolNet.tools.message.send_platform_file import (
            ListDataFilesTool,
            SendPlatformFileTool,
        )

        self.register(SendMessageTool())
        self.register(GetRecentMessagesTool())
        self.register(SendPlatformFileTool())
        self.register(ListDataFilesTool())
        self.logger.info(
            "已加载消息工具: SendMessageTool, GetRecentMessagesTool, SendPlatformFileTool, ListDataFilesTool"
        )

    def _load_auth_tools(self):
        """加载认证工具"""
        from webnet.ToolNet.tools.auth.add_user import AddUserTool
        from webnet.ToolNet.tools.auth.check_permission import CheckPermissionTool
        from webnet.ToolNet.tools.auth.grant_permission import GrantPermissionTool
        from webnet.ToolNet.tools.auth.list_groups import ListGroupsTool
        from webnet.ToolNet.tools.auth.list_permissions import ListPermissionsTool
        from webnet.ToolNet.tools.auth.remove_user import RemoveUserTool
        from webnet.ToolNet.tools.auth.revoke_permission import RevokePermissionTool

        self.register(AddUserTool())
        self.register(RemoveUserTool())
        self.register(CheckPermissionTool())
        self.register(GrantPermissionTool())
        self.register(RevokePermissionTool())
        self.register(ListGroupsTool())
        self.register(ListPermissionsTool())
        self.logger.info(
            "已加载认证工具: AddUserTool, RemoveUserTool, CheckPermissionTool, GrantPermissionTool, RevokePermissionTool, ListGroupsTool, ListPermissionsTool"
        )

    def _load_group_tools(self):
        """加载群工具"""
        from webnet.ToolNet.tools.group.add_member import AddMemberTool
        from webnet.ToolNet.tools.group.get_group_info import GetGroupInfoTool
        from webnet.ToolNet.tools.group.list_members import ListMembersTool
        from webnet.ToolNet.tools.group.remove_member import RemoveMemberTool
        from webnet.ToolNet.tools.group.set_group_name import SetGroupNameTool

        self.register(ListMembersTool())
        self.register(AddMemberTool())
        self.register(RemoveMemberTool())
        self.register(SetGroupNameTool())
        self.register(GetGroupInfoTool())
        self.logger.info(
            "已加载群工具: ListMembersTool, AddMemberTool, RemoveMemberTool, SetGroupNameTool, GetGroupInfoTool"
        )

    def _load_memory_tools(self):
        """加载记忆工具（使用统一记忆接口）"""
        from webnet.ToolNet.tools.memory.auto_extract_memory import AutoExtractMemory
        from webnet.ToolNet.tools.memory.memory_add import MemoryAdd
        from webnet.ToolNet.tools.memory.memory_delete import MemoryDelete
        from webnet.ToolNet.tools.memory.memory_list import MemoryList
        from webnet.ToolNet.tools.memory.memory_query import MemoryQueryTool
        from webnet.ToolNet.tools.memory.memory_stats import (
            MemorySearchByCategory,
            MemoryStats,
        )
        from webnet.ToolNet.tools.memory.memory_update import MemoryUpdate
        from webnet.ToolNet.tools.memory.thinking_query import ThinkingQueryTool

        self.register(MemoryAdd())
        self.register(MemoryDelete())
        self.register(MemoryUpdate())
        self.register(MemoryList())
        self.register(AutoExtractMemory())
        self.register(MemoryStats())
        self.register(MemorySearchByCategory())
        self.register(MemoryQueryTool())
        self.register(ThinkingQueryTool())
        self.logger.info(
            "已加载记忆工具: MemoryAdd, MemoryDelete, MemoryUpdate, MemoryList, AutoExtractMemory, MemoryStats, MemorySearchByCategory, MemoryQuery, ThinkingQuery"
        )

    def _load_knowledge_tools(self):
        """加载知识库工具"""
        from webnet.ToolNet.tools.knowledge.add_knowledge import AddKnowledgeTool
        from webnet.ToolNet.tools.knowledge.delete_knowledge import DeleteKnowledgeTool
        from webnet.ToolNet.tools.knowledge.search_knowledge import SearchKnowledgeTool

        self.register(AddKnowledgeTool())
        self.register(SearchKnowledgeTool())
        self.register(DeleteKnowledgeTool())
        self.logger.info("已加载知识库工具: AddKnowledgeTool, SearchKnowledgeTool, DeleteKnowledgeTool")

    def _load_cognitive_tools(self):
        """加载认知工具"""
        from webnet.ToolNet.tools.cognitive.get_profile import GetProfileTool
        from webnet.ToolNet.tools.cognitive.search_events import SearchEventsTool
        from webnet.ToolNet.tools.cognitive.search_profiles import SearchProfilesTool

        self.register(GetProfileTool())
        self.register(SearchProfilesTool())
        self.register(SearchEventsTool())
        self.logger.info("已加载认知工具: GetProfileTool, SearchProfilesTool, SearchEventsTool")

    def _load_bilibili_tools(self):
        """加载B站工具"""
        from webnet.ToolNet.tools.bilibili.bilibili_video import BilibiliVideoTool

        self.register(BilibiliVideoTool())
        self.logger.info("已加载B站工具: BilibiliVideoTool")

    def _load_scheduler_tools(self):
        """加载定时任务工具"""
        from webnet.ToolNet.tools.scheduler.create_schedule_task import (
            CreateScheduleTaskTool,
        )
        from webnet.ToolNet.tools.scheduler.delete_schedule_task import (
            DeleteScheduleTaskTool,
        )
        from webnet.ToolNet.tools.scheduler.get_schedule_stats import (
            GetScheduleStatsTool,
        )
        from webnet.ToolNet.tools.scheduler.list_schedule_tasks import (
            ListScheduleTasksTool,
        )
        from webnet.ToolNet.tools.scheduler.update_schedule_task import (
            UpdateScheduleTaskTool,
        )

        self.register(CreateScheduleTaskTool())
        self.register(DeleteScheduleTaskTool())
        self.register(GetScheduleStatsTool())
        self.register(ListScheduleTasksTool())
        self.register(UpdateScheduleTaskTool())
        self.logger.info("已加载定时任务工具: CRUD + Stats (5 tools)")

    def _load_entertainment_tools(self):
        """加载娱乐工具"""
        try:
            from webnet.ToolNet.tools.entertainment.horoscope import Horoscope
            from webnet.ToolNet.tools.entertainment.qqlike import QQLike
            from webnet.ToolNet.tools.entertainment.react_emoji import ReactEmoji
            from webnet.ToolNet.tools.entertainment.send_poke import SendPoke
            from webnet.ToolNet.tools.entertainment.wenchang_dijun import WenchangDijun

            self.register(QQLike())
            self.register(Horoscope())
            self.register(WenchangDijun())
            self.register(SendPoke())
            self.register(ReactEmoji())
            self.logger.info("已加载娱乐工具: QQLike, Horoscope, WenchangDijun, SendPoke, ReactEmoji")
        except Exception as e:
            self.logger.warning(f"加载娱乐工具失败: {e}")

    def _load_qq_multimedia_tools(self):
        """加载QQ多媒体工具"""
        try:
            from webnet.ToolNet.tools.qq.qq_emoji import QQEmojiTool
            from webnet.ToolNet.tools.qq.qq_file_reader import QQFileReaderTool
            from webnet.ToolNet.tools.qq.qq_image_analyzer import QQImageAnalyzerTool

            self.register(QQEmojiTool())
            self.register(QQFileReaderTool())
            self.register(QQImageAnalyzerTool())
            self.logger.info("已加载QQ多媒体工具: QQEmojiTool, QQFileReaderTool, QQImageAnalyzerTool")
        except Exception as e:
            self.logger.warning(f"加载QQ多媒体工具失败: {e}")

    def _load_file_library_tools(self):
        """加载弥娅文件库工具"""
        try:
            from webnet.ToolNet.tools.file_library import get_file_library_tools

            for tool in get_file_library_tools():
                self.register(tool)
            self.logger.info(
                "已加载文件库工具: file_library_list, file_library_search, file_library_read, file_library_stats"
            )
        except Exception as e:
            self.logger.warning(f"加载文件库工具失败: {e}")

    def _load_web_search_tools(self):
        """加载 Web 搜索工具"""
        pass

    def _load_visualization_tools(self):
        """加载可视化工具（数据分析、图表生成）"""
        try:
            from webnet.ToolNet.tools.visualization.chart_generator import (
                ChartGenerator,
            )
            from webnet.ToolNet.tools.visualization.data_analyzer import DataAnalyzer

            self.register(DataAnalyzer())
            self.register(ChartGenerator())
            self.logger.info("已加载可视化工具: DataAnalyzer, ChartGenerator")
        except Exception as e:
            self.logger.warning(f"加载可视化工具失败: {e}")

    def _load_lifenet_tools(self):
        """加载 LifeNet 记忆管理工具"""
        try:
            from webnet.ToolNet.tools.life.life_add_diary import LifeAddDiary
            from webnet.ToolNet.tools.life.life_add_summary import LifeAddSummary
            from webnet.ToolNet.tools.life.life_create_character_node import (
                LifeCreateCharacterNode,
            )
            from webnet.ToolNet.tools.life.life_create_stage_node import (
                LifeCreateStageNode,
            )
            from webnet.ToolNet.tools.life.life_get_diary import LifeGetDiary
            from webnet.ToolNet.tools.life.life_get_memory_context import (
                LifeGetMemoryContext,
            )
            from webnet.ToolNet.tools.life.life_get_node import LifeGetNode
            from webnet.ToolNet.tools.life.life_get_summary import LifeGetSummary
            from webnet.ToolNet.tools.life.life_list_nodes import LifeListNodes
            from webnet.ToolNet.tools.life.life_search_memory import LifeSearchMemory

            # 注册所有 LifeNet 工具
            self.register(LifeAddDiary())
            self.register(LifeGetDiary())
            self.register(LifeAddSummary())
            self.register(LifeGetSummary())
            self.register(LifeCreateCharacterNode())
            self.register(LifeCreateStageNode())
            self.register(LifeGetNode())
            self.register(LifeListNodes())
            self.register(LifeSearchMemory())
            self.register(LifeGetMemoryContext())

            self.logger.info("已加载 LifeNet 记忆管理工具")
        except Exception as e:
            self.logger.warning(f"加载 LifeNet 工具失败: {e}")

    def _load_network_tools(self):
        """加载网络工具"""
        try:
            # from webnet.ToolNet.tools.network.grok_search import GrokSearchTool  # 无免费额度，已禁用
            from webnet.ToolNet.tools.network.arxiv_search import ArxivSearchTool
            from webnet.ToolNet.tools.network.crawl_webpage import CrawlWebpageTool
            from webnet.ToolNet.tools.network.github_repo import GithubRepoTool
            from webnet.ToolNet.tools.network.speed_test import SpeedTestTool
            from webnet.ToolNet.tools.network.tavily_search_tool import TavilySearchTool
            from webnet.ToolNet.tools.network.tcping import TCPingTool
            from webnet.ToolNet.tools.network.weather_query import WeatherQueryTool
            from webnet.ToolNet.tools.network.whois_query import WhoisQueryTool

            # self.register(GrokSearchTool())  # 无免费额度，已禁用
            self.register(ArxivSearchTool())
            self.register(CrawlWebpageTool())
            self.register(GithubRepoTool())
            self.register(WhoisQueryTool())
            self.register(TCPingTool())
            self.register(SpeedTestTool())
            self.register(TavilySearchTool())
            self.register(WeatherQueryTool())

            self.logger.info(
                "已加载网络工具: ArxivSearch, CrawlWebpage, GithubRepo, WhoisQuery, TCPing, SpeedTest, TavilySearch, WeatherQuery"
            )
        except Exception as e:
            self.logger.warning(f"加载网络工具失败: {e}")

    def _load_core_tools(self):
        """加载核心工具（新增）"""
        try:
            from webnet.ToolNet.tools.core.changelog import ChangelogTool
            from webnet.ToolNet.tools.core.daemon_logs import DaemonLogsTool
            from webnet.ToolNet.tools.core.self_check import SelfCheckTool

            self.register(ChangelogTool())
            self.register(DaemonLogsTool())
            self.register(SelfCheckTool())

            self.logger.info("已加载核心工具: Changelog, DaemonLogs, SelfCheck")
        except Exception as e:
            self.logger.warning(f"加载核心工具失败: {e}")

    def _load_social_tools(self):
        """加载社交工具（新增）"""
        try:
            from webnet.ToolNet.tools.social.qq_level import QQLevelTool

            self.register(QQLevelTool())

            self.logger.info("已加载社交工具: QQLevel")
        except Exception as e:
            self.logger.warning(f"加载社交工具失败: {e}")

    def _load_agent_tools(self):
        """加载 Agent 专用工具（新增）"""
        try:
            import json
            from pathlib import Path

            agents_base = Path(__file__).parent / "agents"
            if not agents_base.exists():
                return

            for agent_dir in agents_base.iterdir():
                if not agent_dir.is_dir():
                    continue

                tools_dir = agent_dir / "tools"
                if not tools_dir.exists():
                    continue

                for tool_dir in tools_dir.iterdir():
                    if not tool_dir.is_dir():
                        continue

                    handler_file = tool_dir / "handler.py"
                    config_file = tool_dir / "config.json"

                    if not (handler_file.exists() and config_file.exists()):
                        continue

                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            config = json.load(f)

                        if "type" in config and "function" in config:
                            tool_name = config["function"]["name"]
                            tool_desc = config["function"].get("description", "")
                            tool_params = config["function"].get("parameters", {})

                            class DynamicTool:
                                def __init__(
                                    self,
                                    name,
                                    desc,
                                    params,
                                    handler_path,
                                    agent_name,
                                    tool_dir_name,
                                ):
                                    self._name = name
                                    self._desc = desc
                                    self._params = params
                                    self._handler_path = handler_path
                                    self._agent_name = agent_name
                                    self._tool_dir = tool_dir_name

                                @property
                                def config(self):
                                    return {
                                        "name": self._name,
                                        "description": self._desc,
                                        "parameters": self._params,
                                    }

                                async def execute(self, args, context=None):
                                    try:
                                        from importlib import import_module

                                        # 将 ToolContext 转换为字典
                                        ctx_dict = {}
                                        if context:
                                            # 检查是否是 dataclass (ToolContext)
                                            if hasattr(context, "__dataclass_fields__"):
                                                ctx_dict = {
                                                    f.name: getattr(context, f.name)
                                                    for f in context.__dataclass_fields__.values()
                                                }
                                            elif isinstance(context, dict):
                                                ctx_dict = context

                                        module_path = (
                                            f"webnet.ToolNet.agents.{self._agent_name}.tools.{self._tool_dir}.handler"
                                        )
                                        module = import_module(module_path)
                                        if hasattr(module, "execute"):
                                            return await module.execute(
                                                args,
                                                ctx_dict if ctx_dict else context,
                                            )
                                        return f"工具 {self._name} 没有 execute 函数"
                                    except Exception as e:
                                        return f"执行工具失败: {str(e)}"

                            tool = DynamicTool(
                                tool_name,
                                tool_desc,
                                tool_params,
                                handler_file,
                                agent_dir.name,
                                tool_dir.name,
                            )
                            self.register(tool)
                            self.logger.info(f"已加载 Agent 工具: {agent_dir.name}/{tool_dir.name}")
                    except Exception as e:
                        self.logger.warning(f"加载 Agent 工具失败 {tool_dir.name}: {e}")

            self.logger.info("Agent 工具加载完成")
        except Exception as e:
            self.logger.warning(f"加载 Agent 工具失败: {e}")

    def _load_music_tools(self):
        """加载 MIDI 音乐作曲+播放工具"""
        try:
            from webnet.MusicNet.midi_tools import (
                MidiWriteTool,
                MidiDiffTool,
                MidiBatchEditTool,
                MidiQueryTool,
                MidiInspectTool,
                MidiPlayTool,
                MidiRenderTool,
            )

            self.register(MidiWriteTool())
            self.register(MidiDiffTool())
            self.register(MidiBatchEditTool())
            self.register(MidiQueryTool())
            self.register(MidiInspectTool())
            self.register(MidiPlayTool())
            self.register(MidiRenderTool())
            self.logger.info("MusicNet MIDI 工具已加载: 7 个工具")
        except Exception as e:
            self.logger.warning(f"加载 MusicNet 工具失败: {e}")

    def _load_mcp_tools(self):
        """加载 MCP 服务工具到格式塔 Agent"""
        try:
            from webnet.ToolNet.tools.mcp.mcp_adapter import discover_mcp_tools

            tools = discover_mcp_tools()
            for tool in tools:
                self.register(tool)
            self.logger.info(f"[ToolRegistry] MCPNet 已加载 {len(tools)} 个工具: {[t._full_name for t in tools]}")
        except Exception as e:
            self.logger.warning(f"加载 MCP 工具失败（MCP 可能尚未初始化）: {e}")

    def _load_file_analysis_tools(self):
        """加载文件分析工具"""
        try:
            from webnet.ToolNet.tools.file_analysis.file_analyzer import (
                FileAnalysisTool,
                DetectFileTypeTool,
            )

            self.register(FileAnalysisTool())
            self.register(DetectFileTypeTool())
            self.logger.info("已加载文件分析工具: FileAnalysisTool, DetectFileTypeTool")
        except Exception as e:
            self.logger.warning(f"加载文件分析工具失败: {e}")

    def _load_group_analysis_tools(self):
        """加载群聊分析工具"""
        try:
            from webnet.ToolNet.tools.group_analysis.group_tools import (
                GroupMemberStructureTool,
                GroupMemberActivityTool,
                GroupInactiveRiskTool,
                GroupMessageMixTool,
            )

            self.register(GroupMemberStructureTool())
            self.register(GroupMemberActivityTool())
            self.register(GroupInactiveRiskTool())
            self.register(GroupMessageMixTool())
            self.logger.info("已加载群聊分析工具: member_structure, member_activity, inactive_risk, message_mix")
        except Exception as e:
            self.logger.warning(f"加载群聊分析工具失败: {e}")

    def _load_earth_online_tools(self):
        """加载地球online 工具（现实游戏化模块）"""
        try:
            from config.config_utils import get_qq_config

            if not get_qq_config("earth_online", "enabled", default=True):
                self.logger.info("地球online 功能未启用，跳过工具加载")
                return

            from webnet.ToolNet.tools.earth_online import get_earth_online_tools

            tools = get_earth_online_tools()
            for tool in tools:
                self.register(tool)
            self.logger.info(f"已加载地球online 工具: {len(tools)} 个")
        except Exception as e:
            self.logger.warning(f"加载地球online 工具失败: {e}")

    def _load_render_tools(self):
        try:
            from webnet.ToolNet.tools.render.render_html import RenderHtmlTool
            from webnet.ToolNet.tools.render.render_markdown import RenderMarkdownTool

            self.register(RenderHtmlTool())
            self.register(RenderMarkdownTool())
            self.logger.info("已加载渲染工具: render_html, render_markdown")
        except Exception as e:
            self.logger.warning(f"加载渲染工具失败: {e}")


class BaseTool:
    """工具基类（兼容层）"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"Tool.{self.name}")

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        raise NotImplementedError

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        raise NotImplementedError

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        required_params = self.config.get("parameters", {}).get("required", [])
        for param in required_params:
            if param not in args or not args[param]:
                return False, f"缺少必填参数: {param}"
        return True, None
