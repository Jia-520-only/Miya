"""
ToolNet 工具注册表（兼容层）

兼容旧版 tools/ 系统，同时支持子网架构
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """工具执行上下文"""
    # 核心组件
    memory_engine: Optional[Any] = None
    cognitive_memory: Optional[Any] = None
    onebot_client: Optional[Any] = None
    scheduler: Optional[Any] = None

    # 运行时信息
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    message_type: Optional[str] = None
    sender_name: Optional[str] = None
    is_at_bot: bool = False

    # 工具内部使用
    message_sent_this_turn: bool = False


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

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取所有工具配置（OpenAI Function Calling 格式）"""
        return [
            {
                "type": "function",
                "function": tool.config
            }
            for tool in self.tools.values()
        ]

    async def execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """执行工具"""
        tool = self.get_tool(name)
        if not tool:
            return f"❌ 工具不存在: {name}"

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

    def clear(self):
        """清空注册表"""
        self.tools.clear()
        self.logger.info("工具注册表已清空")

    def load_all_tools(self):
        """加载所有工具"""
        self._load_basic_tools()
        self._load_message_tools()
        self._load_group_tools()
        self._load_memory_tools()
        self._load_knowledge_tools()
        self._load_cognitive_tools()
        self._load_bilibili_tools()
        self._load_scheduler_tools()
        self._load_entertainment_tools()
        self._load_tavern_tools()

    def _load_basic_tools(self):
        """加载基础工具"""
        from webnet.BasicNet.tools.get_current_time import GetCurrentTime
        from webnet.BasicNet.tools.get_user_info import GetUserInfo
        from webnet.BasicNet.tools.python_interpreter import PythonInterpreter

        self.register(GetCurrentTime())
        self.register(GetUserInfo())
        self.register(PythonInterpreter())

    def _load_message_tools(self):
        """加载消息工具"""
        from webnet.MessageNet.tools.send_message import SendMessage
        from webnet.MessageNet.tools.get_recent_messages import GetRecentMessages
        from webnet.MessageNet.tools.send_text_file import SendTextFile
        from webnet.MessageNet.tools.send_url_file import SendUrlFile

        self.register(SendMessage())
        self.register(GetRecentMessages())
        self.register(SendTextFile())
        self.register(SendUrlFile())

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
        """加载记忆工具"""
        from webnet.MemoryNet.tools.memory_add import MemoryAdd
        from webnet.MemoryNet.tools.memory_list import MemoryList
        from webnet.MemoryNet.tools.memory_update import MemoryUpdate
        from webnet.MemoryNet.tools.memory_delete import MemoryDelete

        self.register(MemoryAdd())
        self.register(MemoryList())
        self.register(MemoryUpdate())
        self.register(MemoryDelete())

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
        from webnet.SchedulerNet.tools.create_schedule_task import CreateScheduleTask
        from webnet.SchedulerNet.tools.list_schedule_tasks import ListScheduleTasks
        from webnet.SchedulerNet.tools.delete_schedule_task import DeleteScheduleTask

        self.register(CreateScheduleTask())
        self.register(ListScheduleTasks())
        self.register(DeleteScheduleTask())

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
            from webnet.EntertainmentNet.trpg.tools.update_pc import UpdatePC, DeletePC
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
            self.register(DeletePC())
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
