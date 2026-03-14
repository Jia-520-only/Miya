"""
ToolNet 工具注册表（兼容层）

兼容旧版 tools/ 系统，同时支持子网架构
注意：ToolContext 已统一到 webnet.tools.base，此处仅保留兼容导入
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING


logger = logging.getLogger(__name__)

# 统一使用 webnet.tools.base 中的 ToolContext
if TYPE_CHECKING:
    from webnet.tools.base import ToolContext as BaseToolContext
else:
    try:
        from webnet.tools.base import ToolContext
    except ImportError:
        # 回退定义（不应发生，但作为防御）
        from dataclasses import dataclass
        @dataclass
        class ToolContext:
            """工具执行上下文（回退定义）"""
            memory_engine: Optional[Any] = None
            cognitive_memory: Optional[Any] = None
            onebot_client: Optional[Any] = None
            scheduler: Optional[Any] = None
            user_id: Optional[int] = None
            group_id: Optional[int] = None
            message_type: Optional[str] = None
            sender_name: Optional[str] = None
            is_at_bot: bool = False
            at_list: list = None
            message_sent_this_turn: bool = False
            game_mode: Optional[Any] = None
            game_mode_manager: Optional[Any] = None
            bot_qq: Optional[int] = None
            superadmin: Optional[int] = None
            memory_net: Optional[Any] = None
            emotion: Optional[Any] = None
            personality: Optional[Any] = None
            send_like_callback: Optional[Any] = None
            def __post_init__(self):
                if self.at_list is None:
                    self.at_list = []


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, 'BaseTool'] = {}
        self.logger = logging.getLogger(__name__)

    def register(self, tool: 'BaseTool') -> bool:
        """注册工具"""
        try:
            tool_name = tool.config.get('name')
            if not tool_name:
                self.logger.error(f"工具缺少 name 属性: {tool.__class__.__name__}")
                return False

            self.tools[tool_name] = tool
            self.logger.info(f"已注册工具: {tool_name}")
            return True
        except Exception as e:
            self.logger.error(f"注册工具失败: {e}", exc_info=True)
            return False

    def get_tool(self, name: str) -> Optional['BaseTool']:
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
            description = tool_config.get('description', '')
            # 确保描述足够清晰，包含何时调用
            if '当' not in description and '调用' not in description and '如果' not in description:
                # 为没有明确调用时机描述的工具添加提示
                tool_config['description'] = f"[工具] {description}\n调用时机：当用户明确请求此功能时调用。"
            
            tools_schema.append({
                "type": "function",
                "function": tool_config
            })
        
        self.logger.info(f"[ToolRegistry] 生成工具schema，共{len(tools_schema)}个工具")
        return tools_schema

    async def execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """执行工具（含权限检查）"""
        tool = self.get_tool(name)
        if not tool:
            return f"❌ 工具不存在: {name}"

        # 【新增】权限检查
        permission_check = await self._check_tool_permission(name, context)
        if not permission_check['allowed']:
            self.logger.warning(f"[权限拒绝] 用户 {context.user_id} 尝试执行工具 {name}，缺少权限")
            return f"❌ 权限不足：执行工具 '{name}' 需要权限 '{permission_check['required_permission']}'"

        try:
            # 验证参数
            valid, error = tool.validate_args(args)
            if not valid:
                return f"❌ 参数错误: {error}"

            # 执行工具
            result = await tool.execute(args, context)
            return result
        except Exception as e:
            self.logger.error(f"执行工具失败 {name}: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    async def _check_tool_permission(
        self,
        tool_name: str,
        context: ToolContext
    ) -> Dict[str, Any]:
        """
        检查用户是否有执行工具的权限

        Args:
            tool_name: 工具名称
            context: 工具执行上下文

        Returns:
            包含 allowed 和 required_permission 的字典
        """
        try:
            # 从 AuthNet 获取权限核心
            from webnet.AuthNet.permission_core import PermissionCore
            from webnet.AuthNet.user_mapper import UserMapper

            # 确定用户ID和平台
            user_id = getattr(context, 'user_id', None) or getattr(context, 'superadmin', None)
            platform = getattr(context, 'platform', 'terminal')

            if user_id is None:
                # 没有用户ID，允许执行（可能是系统调用）
                return {'allowed': True, 'required_permission': None}

            # 生成统一用户ID
            user_mapper = UserMapper()
            platform = self._detect_platform_from_context(context)
            unified_user_id = user_mapper.generate_user_id(platform, str(user_id))

            # 构建权限节点
            required_permission = f"tool.{tool_name}"

            # 检查权限
            perm_core = PermissionCore()
            has_permission = perm_core.check_permission(unified_user_id, required_permission)

            # 如果没有直接权限，检查是否是超级管理员
            if not has_permission:
                # 尝试系统管理员
                has_permission = perm_core.check_permission('system_admin', required_permission)

            return {
                'allowed': has_permission,
                'required_permission': required_permission,
                'user_id': unified_user_id
            }

        except Exception as e:
            # 权限检查失败时，允许执行（降级处理）
            self.logger.warning(f"[权限检查异常] {e}，允许执行")
            return {'allowed': True, 'required_permission': None, 'error': str(e)}

    def _detect_platform_from_context(self, context: ToolContext) -> str:
        """从上下文检测平台类型"""
        # 尝试从多个属性检测平台
        if hasattr(context, 'platform'):
            return context.platform

        # 根据消息类型或其他属性推断
        if hasattr(context, 'message_type'):
            if context.message_type == 'private':
                return 'qq'  # 默认为QQ
            elif context.message_type == 'group':
                return 'qq'

        return 'terminal'  # 默认平台

    def clear(self):
        """清空注册表"""
        self.tools.clear()
        self.logger.info("工具注册表已清空")

    def load_all_tools(self):
        """加载所有工具"""
        self._load_basic_tools()
        self._load_terminal_tools()  # 新增：加载终端命令工具
        self._load_message_tools()
        self._load_group_tools()
        self._load_memory_tools()
        self._load_knowledge_tools()
        self._load_cognitive_tools()
        self._load_bilibili_tools()
        self._load_scheduler_tools()
        self._load_entertainment_tools()
        self._load_tavern_tools()
        self._load_game_mode_tools()
        self._load_lifenet_tools()
        self._load_web_search_tools()  # 新增：加载 Web 搜索工具
        self._load_visualization_tools()  # 新增：加载可视化工具
        self._load_model_management_tools()  # 新增：加载模型管理工具
        # 注意：查询工具已在 _load_entertainment_tools() 中加载

    def _load_basic_tools(self):
        """加载基础工具"""
        from webnet.BasicNet.tools.get_current_time import GetCurrentTime
        from webnet.BasicNet.tools.get_user_info import GetUserInfo
        from webnet.BasicNet.tools.python_interpreter import PythonInterpreter

        self.register(GetCurrentTime())
        self.register(GetUserInfo())
        self.register(PythonInterpreter())

    def _load_terminal_tools(self):
        """加载终端命令工具"""
        from webnet.TerminalNet.tools.terminal_command import TerminalCommandTool
        from webnet.TerminalNet.tools.multi_terminal import MultiTerminalTool
        from webnet.TerminalNet.tools.wsl_manager import WSLManagerTool
        from webnet.TerminalNet.tools.environment_detector import EnvironmentDetectorTool
        from webnet.TerminalNet.tools.system_info import SystemInfoTool

        self.register(TerminalCommandTool())
        self.register(MultiTerminalTool())
        self.register(WSLManagerTool())
        self.register(EnvironmentDetectorTool())
        self.register(SystemInfoTool())

    def _load_model_management_tools(self):
        """加载模型管理工具"""
        try:
            from webnet.ToolNet.tools.model_management import ModelManagementTool
            self.register(ModelManagementTool())
            self.logger.info("模型管理工具已注册")
        except Exception as e:
            self.logger.warning(f"加载模型管理工具失败: {e}")

    def _load_message_tools(self):
        """加载消息工具"""
        from webnet.MessageNet.tools.send_message import SendMessageTool
        from webnet.MessageNet.tools.get_recent_messages import GetRecentMessagesTool
        from webnet.MessageNet.tools.send_text_file import SendTextFileTool
        from webnet.MessageNet.tools.send_url_file import SendUrlFileTool

        self.register(SendMessageTool())
        self.register(GetRecentMessagesTool())
        self.register(SendTextFileTool())
        self.register(SendUrlFileTool())

    def _load_group_tools(self):
        """加载群工具"""
        from webnet.GroupNet.tools.get_member_list import GetMemberList
        from webnet.GroupNet.tools.get_member_info import GetMemberInfo
        from webnet.GroupNet.tools.find_member import FindMember
        from webnet.GroupNet.tools.filter_members import FilterMembers
        from webnet.GroupNet.tools.rank_members import RankMembers

        self.register(GetMemberList())
        self.register(GetMemberInfo())
        self.register(FindMember())
        self.register(FilterMembers())
        self.register(RankMembers())

    def _load_memory_tools(self):
        """加载记忆工具（使用统一记忆接口）"""
        from webnet.MemoryNet.tools.memory_add import MemoryAdd
        from webnet.MemoryNet.tools.memory_list import MemoryList
        from webnet.MemoryNet.tools.memory_update import MemoryUpdate
        from webnet.MemoryNet.tools.memory_delete import MemoryDelete
        from webnet.MemoryNet.tools.auto_extract_memory import AutoExtractMemory

        self.register(MemoryAdd())
        self.register(MemoryList())
        self.register(MemoryUpdate())
        self.register(MemoryDelete())
        self.register(AutoExtractMemory())
        logger.info("已加载记忆工具（统一记忆接口）")

    def _load_knowledge_tools(self):
        """加载知识库工具"""
        from webnet.KnowledgeNet.tools.knowledge_list import KnowledgeList
        from webnet.KnowledgeNet.tools.knowledge_text_search import KnowledgeTextSearch
        from webnet.KnowledgeNet.tools.knowledge_semantic_search import KnowledgeSemanticSearch

        self.register(KnowledgeList())
        self.register(KnowledgeTextSearch())
        self.register(KnowledgeSemanticSearch())

    def _load_cognitive_tools(self):
        """加载认知工具"""
        from webnet.CognitiveNet.tools.get_profile import GetProfile
        from webnet.CognitiveNet.tools.search_profiles import SearchProfiles
        from webnet.CognitiveNet.tools.search_events import SearchEvents

        self.register(GetProfile())
        self.register(SearchProfiles())
        self.register(SearchEvents())

    def _load_bilibili_tools(self):
        """加载B站工具"""
        from webnet.BilibiliNet.tools.bilibili_video import BilibiliVideo

        self.register(BilibiliVideo())

    def _load_scheduler_tools(self):
        """加载定时任务工具"""
        from webnet.SchedulerNet.tools.create_schedule_task import CreateScheduleTaskTool
        from webnet.SchedulerNet.tools.list_schedule_tasks import ListScheduleTasksTool
        from webnet.SchedulerNet.tools.delete_schedule_task import DeleteScheduleTaskTool

        self.register(CreateScheduleTaskTool())
        self.register(ListScheduleTasksTool())
        self.register(DeleteScheduleTaskTool())

    def _load_tavern_tools(self):
        """加载酒馆工具"""
        try:
            from webnet.EntertainmentNet.tavern.tools.start_tavern import StartTavern
            from webnet.EntertainmentNet.tavern.tools.tavern_chat import TavernChat
            from webnet.EntertainmentNet.tavern.tools.generate_story import GenerateStory
            from webnet.EntertainmentNet.tavern.tools.continue_story import ContinueStory
            from webnet.EntertainmentNet.tavern.tools.set_mood import SetMood
            from webnet.EntertainmentNet.tavern.tools.create_character import CreateTavernCharacter
            from webnet.EntertainmentNet.tavern.tools.list_characters import ListTavernCharacters
            from webnet.EntertainmentNet.tavern.tools.multi_character import (StartMultiChat,
                                                                                  MultiCharacterChat,
                                                                                  SetCharacterFocus)
            from webnet.EntertainmentNet.tavern.tools.story_branch import (CreateStoryBranch,
                                                                            AddStoryChoice,
                                                                            ShowStoryTree,
                                                                            SelectStoryBranch)

            self.register(StartTavern())
            self.register(TavernChat())
            self.register(GenerateStory())
            self.register(ContinueStory())
            self.register(SetMood())
            self.register(CreateTavernCharacter())
            self.register(ListTavernCharacters())
            self.register(StartMultiChat())
            self.register(MultiCharacterChat())
            self.register(SetCharacterFocus())
            self.register(CreateStoryBranch())
            self.register(AddStoryChoice())
            self.register(ShowStoryTree())
            self.register(SelectStoryBranch())
            self.logger.info("已加载酒馆工具")
        except Exception as e:
            self.logger.warning(f"加载酒馆工具失败: {e}")

    def _load_entertainment_tools(self):
        """加载娱乐工具"""
        from webnet.EntertainmentNet.tools.qqlike import QQLike
        from webnet.EntertainmentNet.tools.horoscope import Horoscope
        from webnet.EntertainmentNet.tools.wenchang_dijun import WenchangDijun
        from webnet.EntertainmentNet.tools.send_poke import SendPoke
        from webnet.EntertainmentNet.tools.react_emoji import ReactEmoji

        self.register(QQLike())
        self.register(Horoscope())
        self.register(WenchangDijun())
        self.register(SendPoke())
        self.register(ReactEmoji())

        # 加载 TRPG 工具
        try:
            from webnet.EntertainmentNet.trpg.tools.start_trpg import StartTRPG
            from webnet.EntertainmentNet.trpg.tools.roll_dice import RollDice
            from webnet.EntertainmentNet.trpg.tools.roll_secret import RollSecret
            from webnet.EntertainmentNet.trpg.tools.create_pc import CreatePC
            from webnet.EntertainmentNet.trpg.tools.show_pc import ShowPC
            from webnet.EntertainmentNet.trpg.tools.update_pc import UpdatePC
            from webnet.EntertainmentNet.trpg.tools.skill_check import SkillCheck
            from webnet.EntertainmentNet.trpg.tools.kp_command import KPCommand
            from webnet.EntertainmentNet.trpg.tools.combat import Attack, CombatLog
            from webnet.EntertainmentNet.trpg.tools.rest import Rest
            from webnet.EntertainmentNet.trpg.tools.initiative_command import (StartCombat,
                                                                                  AddInitiative,
                                                                                  NextTurn,
                                                                                  ShowInitiative,
                                                                                  EndCombat)

            self.register(StartTRPG())
            self.register(RollDice())
            self.register(RollSecret())
            self.register(CreatePC())
            self.register(ShowPC())
            self.register(UpdatePC())
            self.register(SkillCheck())
            self.register(KPCommand())
            self.register(Attack())
            self.register(CombatLog())
            self.register(Rest())
            self.register(StartCombat())
            self.register(AddInitiative())
            self.register(NextTurn())
            self.register(ShowInitiative())
            self.register(EndCombat())
            self.logger.info("已加载 TRPG 工具")
        except Exception as e:
            self.logger.warning(f"加载 TRPG 工具失败: {e}")

        # 加载查询工具
        try:
            from webnet.EntertainmentNet.query.tools.search_tavern_stories import (
                SearchTavernStories,
                SearchTavernCharacters,
                SearchTavernPreferences
            )
            from webnet.EntertainmentNet.query.tools.search_trpg_characters import (
                SearchTRPGCharacters,
                SearchTRPGByAttribute,
                SearchTRPGBySkill
            )

            # 酒馆查询工具
            self.register(SearchTavernStories())
            self.register(SearchTavernCharacters())
            self.register(SearchTavernPreferences())

            # 跑团查询工具
            self.register(SearchTRPGCharacters())
            self.register(SearchTRPGByAttribute())
            self.register(SearchTRPGBySkill())

            self.logger.info("已加载查询工具")
        except Exception as e:
            self.logger.warning(f"加载查询工具失败: {e}")

    def _load_game_mode_tools(self):
        """加载游戏模式工具"""
        try:
            from webnet.EntertainmentNet.game_mode.tools.exit_game import ExitGame
            from webnet.EntertainmentNet.game_mode.tools.search_normal_memory import SearchNormalMemory
            from webnet.EntertainmentNet.game_mode.tools.search_game_memory import SearchGameMemory
            from webnet.EntertainmentNet.game_mode.tools.list_saves import ListSaves
            from webnet.EntertainmentNet.game_mode.tools.create_save import CreateSave
            from webnet.EntertainmentNet.game_mode.tools.load_save import LoadSave

            self.register(ExitGame())
            self.register(SearchNormalMemory())
            self.register(SearchGameMemory())
            self.register(ListSaves())
            self.register(CreateSave())
            self.register(LoadSave())

            self.logger.info("已加载游戏模式工具")
        except Exception as e:
            self.logger.warning(f"加载游戏模式工具失败: {e}")

    def _load_web_search_tools(self):
        """加载 Web 搜索工具"""
        try:
            from webnet.WebSearchNet.tools.web_search import WebSearch, GetAvailableSearchEngines, GetSearchHistory

            self.register(WebSearch())
            self.register(GetAvailableSearchEngines())
            self.register(GetSearchHistory())

            self.logger.info("已加载 Web 搜索工具")
        except Exception as e:
            self.logger.warning(f"加载 Web 搜索工具失败: {e}")

    def _load_visualization_tools(self):
        """加载可视化工具（数据分析、图表生成）"""
        try:
            from tools.visualization.data_analyzer import DataAnalyzer
            from tools.visualization.chart_generator import ChartGenerator

            self.register(DataAnalyzer())
            self.register(ChartGenerator())

            self.logger.info("已加载可视化工具")
        except Exception as e:
            self.logger.warning(f"加载可视化工具失败: {e}")

    def _load_lifenet_tools(self):
        """加载 LifeNet 记忆管理工具"""
        try:
            # 导入 LifeNet 子网（使用动态导入避免循环依赖）
            from webnet.LifeNet.tools.life_add_diary import LifeAddDiary
            from webnet.LifeNet.tools.life_get_diary import LifeGetDiary
            from webnet.LifeNet.tools.life_add_summary import LifeAddSummary
            from webnet.LifeNet.tools.life_get_summary import LifeGetSummary
            from webnet.LifeNet.tools.life_create_character_node import LifeCreateCharacterNode
            from webnet.LifeNet.tools.life_create_stage_node import LifeCreateStageNode
            from webnet.LifeNet.tools.life_get_node import LifeGetNode
            from webnet.LifeNet.tools.life_list_nodes import LifeListNodes
            from webnet.LifeNet.tools.life_search_memory import LifeSearchMemory
            from webnet.LifeNet.tools.life_get_memory_context import LifeGetMemoryContext

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
        required_params = self.config.get('parameters', {}).get('required', [])
        for param in required_params:
            if param not in args or not args[param]:
                return False, f"缺少必填参数: {param}"
        return True, None
