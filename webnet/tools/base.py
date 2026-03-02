"""
工具系统基础类
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """工具执行上下文"""
    # OneBot 相关
    qq_net: Optional[Any] = None  # QQNet 实例
    onebot_client: Optional[Any] = None  # OneBot 客户端
    send_like_callback: Optional[Any] = None  # 点赞回调函数

    # 弥娅核心
    memory_engine: Optional[Any] = None  # 记忆引擎
    memory_net: Optional[Any] = None  # MemoryNet 记忆系统
    emotion: Optional[Any] = None  # 情绪系统
    personality: Optional[Any] = None  # 人格系统
    scheduler: Optional[Any] = None  # 调度器

    # 运行时信息
    request_id: Optional[str] = None  # 请求ID
    group_id: Optional[int] = None  # 群号
    user_id: Optional[int] = None  # 用户ID
    message_type: Optional[str] = None  # 消息类型 (group/private)
    sender_name: Optional[str] = None  # 发送者名称
    is_at_bot: bool = False  # 是否@机器人
    at_list: list = field(default_factory=list)  # 消息中@的用户ID列表

    # 工具内部使用
    message_sent_this_turn: bool = field(default=False, init=False)


class BaseTool:
    """工具基类"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"Tool.{self.name}")

    @property
    def config(self) -> Dict[str, Any]:
        """
        工具配置（OpenAI Function Calling 格式）

        Returns:
            工具配置字典
        """
        raise NotImplementedError

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        执行工具

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        raise NotImplementedError

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证参数

        Args:
            args: 工具参数

        Returns:
            (是否有效, 错误信息)
        """
        required_params = self.config.get('parameters', {}).get('required', [])
        for param in required_params:
            if param not in args or not args[param]:
                return False, f"缺少必填参数: {param}"
        return True, None


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._tool_order: list[str] = []  # 保持注册顺序

    def register(self, tool: BaseTool):
        """
        注册工具

        Args:
            tool: 工具实例
        """
        self.tools[tool.name] = tool
        if tool.name not in self._tool_order:
            self._tool_order.append(tool.name)
        logger.info(f"注册工具: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return self.tools.get(name)

    def get_tools_schema(self) -> list[Dict[str, Any]]:
        """
        获取所有工具的配置（OpenAI 格式）

        Returns:
            工具配置列表
        """
        schemas = []
        for name in self._tool_order:
            tool = self.tools[name]
            schemas.append({
                "type": "function",
                "function": tool.config
            })
        return schemas

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return f"错误：未找到工具 '{tool_name}'"

        # 验证参数
        valid, error_msg = tool.validate_args(args)
        if not valid:
            return error_msg

        try:
            logger.info(f"执行工具: {tool_name}, 参数: {args}")
            result = await tool.execute(args, context)
            logger.info(f"工具执行完成: {tool_name}")
            return result
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

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
