"""
工具系统基础类
提供稳定、独立、可维修、故障隔离的工具架构
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from functools import wraps
import asyncio


logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """工具执行上下文"""
    # OneBot 相关
    qq_net: Optional[Any] = None  # QQNet 实例
    onebot_client: Optional[Any] = None  # OneBot 客户端
    send_like_callback: Optional[Any] = None  # 点赞回调函数

    # 弥娅核心
    memory_engine: Optional[Any] = None  # 记忆引擎（兼容）
    unified_memory: Optional[Any] = None  # 统一记忆接口（新）
    memory_net: Optional[Any] = None  # MemoryNet 记忆系统
    emotion: Optional[Any] = None  # 情绪系统
    personality: Optional[Any] = None  # 人格系统
    scheduler: Optional[Any] = None  # 调度器
    lifenet: Optional[Any] = None  # LifeNet 记忆管理网络

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

    # 游戏模式
    game_mode: Optional[Any] = None
    game_mode_manager: Optional[Any] = None
    game_mode_adapter: Optional[Any] = None  # 游戏模式适配器（架构优化）

    # QQ 相关
    bot_qq: Optional[int] = None
    superadmin: Optional[int] = None


class BaseTool:
    """工具基类（符合弥娅框架：稳定、独立、可维修、故障隔离）"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"Tool.{self.name}")
        self.fallback_message: Optional[str] = None  # 降级消息
        self.retry_count: int = 0  # 重试次数
        self.max_retries: int = 0  # 最大重试次数

    async def safe_execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        安全执行工具（自动错误处理和降级）

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果或降级消息
        """
        last_error = None

        # 重试机制
        for attempt in range(self.max_retries + 1):
            try:
                result = await self.execute(args, context)
                # 成功执行
                return result

            except Exception as e:
                last_error = e
                self.logger.error(
                    f"[{self.name}] 执行失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}",
                    exc_info=True
                )

                if attempt < self.max_retries:
                    # 等待后重试
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    # 重试次数用尽，返回降级消息
                    self.logger.error(f"[{self.name}] 所有重试均失败，使用降级策略")
                    return self._get_fallback_result(e)

        # 不应该到达这里
        return self._get_fallback_result(last_error)

    def _get_fallback_result(self, error: Exception) -> str:
        """获取降级结果"""
        if self.fallback_message:
            return self.fallback_message

        tool_name = self.config.get('name', self.name)
        return f"⚠️ 工具 {tool_name} 暂时不可用，请稍后重试。错误: {error}"

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
    """
    工具注册表（升级版）
    符合弥娅框架：稳定、独立、可维修、故障隔离
    """

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._tool_order: List[str] = []  # 保持注册顺序

        # 新增：工具实例管理
        from .tool_instance import ToolInstance
        self.tool_instances: Dict[str, ToolInstance] = {}

        # 新增：工具别名
        self.aliases: Dict[str, str] = {}  # 别名 -> 原始名称

    def register(self, tool: BaseTool, alias: Optional[str] = None):
        """
        注册工具

        Args:
            tool: 工具实例
            alias: 工具别名（可选）
        """
        self.tools[tool.name] = tool
        if tool.name not in self._tool_order:
            self._tool_order.append(tool.name)

        # 创建工具实例（用于熔断和监控）
        from .tool_instance import ToolInstance
        self.tool_instances[tool.name] = ToolInstance(
            tool_name=tool.name,
            tool_class=tool.__class__,
            tool_config=tool.config
        )

        # 注册别名
        if alias and alias != tool.name:
            self.aliases[alias] = tool.name

        logger.info(f"注册工具: {tool.name}" + (f" (别名: {alias})" if alias else ""))

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        # 处理别名
        name = self.aliases.get(name, name)
        return self.tools.get(name)

    def get_tool_instance(self, name: str) -> Optional['ToolInstance']:
        """获取工具实例（用于监控和熔断）"""
        name = self.aliases.get(name, name)
        return self.tool_instances.get(name)

    def get_tools_schema(self, tool_names: Optional[list[str]] = None) -> list[Dict[str, Any]]:
        """
        获取工具的配置（OpenAI 格式）
        自动过滤掉熔断的工具

        Args:
            tool_names: 要获取的工具名称列表，None 表示获取所有工具

        Returns:
            工具配置列表
        """
        schemas = []
        names_to_fetch = tool_names if tool_names is not None else self._tool_order
        for name in names_to_fetch:
            if name in self.tools:
                # 检查工具是否可用
                instance = self.tool_instances.get(name)
                if instance and not instance.is_healthy:
                    logger.debug(f"工具 {name} 不健康，跳过")
                    continue

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
        执行工具（带熔断和降级）

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 执行上下文

        Returns:
            执行结果或降级消息
        """
        # 处理别名
        tool_name = self.aliases.get(tool_name, tool_name)

        # 获取工具
        tool = self.get_tool(tool_name)
        if not tool:
            return f"错误：未找到工具 '{tool_name}'"

        # 获取工具实例
        instance = self.get_tool_instance(tool_name)
        if instance and not instance.should_execute():
            # 工具不可用，返回降级消息
            return f"⚠️ 工具 {tool_name} 暂时不可用，请稍后重试"

        # 验证参数
        valid, error_msg = tool.validate_args(args)
        if not valid:
            return error_msg

        try:
            logger.info(f"执行工具: {tool_name}, 参数: {args}")

            # 使用安全执行（带重试和降级）
            if instance:
                result = await tool.safe_execute(args, context)

                # 记录结果
                if "暂时不可用" in result or "⚠️" in result:
                    instance.record_failure("工具执行失败")
                else:
                    instance.record_success()
            else:
                # 兼容旧工具
                result = await tool.execute(args, context)

            logger.info(f"工具执行完成: {tool_name}")
            return result

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # 记录失败
            if instance:
                instance.record_failure(str(e))

            return error_msg

    def get_tool_health(self, tool_name: str) -> Optional[Dict]:
        """
        获取工具健康状态

        Args:
            tool_name: 工具名称

        Returns:
            工具健康信息
        """
        tool_name = self.aliases.get(tool_name, tool_name)
        instance = self.get_tool_instance(tool_name)

        if not instance:
            return None

        return instance.to_dict()

    def get_all_tools_health(self) -> Dict[str, Dict]:
        """
        获取所有工具的健康状态

        Returns:
            所有工具的健康信息
        """
        return {
            name: instance.to_dict()
            for name, instance in self.tool_instances.items()
        }

    def reset_tool(self, tool_name: str) -> bool:
        """
        重置工具状态

        Args:
            tool_name: 工具名称

        Returns:
            是否重置成功
        """
        tool_name = self.aliases.get(tool_name, tool_name)
        instance = self.get_tool_instance(tool_name)

        if not instance:
            return False

        instance.reset()
        logger.info(f"工具 {tool_name} 已重置")
        return True

    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        tool_name = self.aliases.get(tool_name, tool_name)
        instance = self.get_tool_instance(tool_name)

        if not instance:
            return False

        instance.enabled = False
        logger.warning(f"工具 {tool_name} 已禁用")
        return True

    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        tool_name = self.aliases.get(tool_name, tool_name)
        instance = self.get_tool_instance(tool_name)

        if not instance:
            return False

        instance.enabled = True
        logger.info(f"工具 {tool_name} 已启用")
        return True

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
        self._load_game_mode_tools()
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

    def _load_entertainment_tools(self):
        """加载娱乐工具"""
        from webnet.EntertainmentNet.tools.qqlike import QQLike
        from webnet.EntertainmentNet.tools.horoscope import Horoscope
        from webnet.EntertainmentNet.tools.wenchang_dijun import WenchangDijun
        from webnet.EntertainmentNet.tools.send_poke import SendPoke
        from webnet.EntertainmentNet.tools.react_emoji import ReactEmoji
        from webnet.EntertainmentNet.trpg.tools.start_trpg import StartTRPG
        from webnet.EntertainmentNet.trpg.tools.roll_dice import RollDice
        from webnet.EntertainmentNet.trpg.tools.roll_secret import RollSecret
        from webnet.EntertainmentNet.trpg.tools.create_pc import CreatePC
        from webnet.EntertainmentNet.trpg.tools.show_pc import ShowPC
        from webnet.EntertainmentNet.trpg.tools.update_pc import UpdatePC, DeletePC
        from webnet.EntertainmentNet.trpg.tools.skill_check import SkillCheck
        from webnet.EntertainmentNet.trpg.tools.kp_command import KPCommand
        from webnet.EntertainmentNet.trpg.tools.combat import Attack, CombatLog
        from webnet.EntertainmentNet.trpg.tools.initiative_command import (
            StartCombat, AddInitiative, NextTurn, ShowInitiative, EndCombat
        )
        from webnet.EntertainmentNet.trpg.tools.rest import Rest

        self.register(QQLike())
        self.register(Horoscope())
        self.register(WenchangDijun())
        self.register(SendPoke())
        self.register(ReactEmoji())
        # 注册 TRPG 工具
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
        # 先攻管理工具
        self.register(StartCombat())
        self.register(AddInitiative())
        self.register(NextTurn())
        self.register(ShowInitiative())
        self.register(EndCombat())
        self.register(Rest())

    def _load_game_mode_tools(self):
        """加载游戏模式工具"""
        from webnet.EntertainmentNet.game_mode.tools.create_save import CreateSave
        from webnet.EntertainmentNet.game_mode.tools.load_save import LoadSave
        from webnet.EntertainmentNet.game_mode.tools.list_saves import ListSaves
        from webnet.EntertainmentNet.game_mode.tools.exit_game import ExitGame
        from webnet.EntertainmentNet.game_mode.tools.search_game_memory import SearchGameMemory
        from webnet.EntertainmentNet.game_mode.tools.search_normal_memory import SearchNormalMemory

        self.register(CreateSave())
        self.register(LoadSave())
        self.register(ListSaves())
        self.register(ExitGame())
        self.register(SearchGameMemory())
        self.register(SearchNormalMemory())

    def _load_tavern_tools(self):
        """加载酒馆工具"""
        from webnet.EntertainmentNet.tavern.tools.create_character import CreateTavernCharacter
        from webnet.EntertainmentNet.tavern.tools.continue_story import ContinueStory
        from webnet.EntertainmentNet.query.tools.search_tavern_stories import SearchTavernStories
        from webnet.EntertainmentNet.query.tools.search_trpg_characters import SearchTRPGCharacters

        self.register(CreateTavernCharacter())
        self.register(ContinueStory())
        self.register(SearchTavernStories())
        self.register(SearchTRPGCharacters())

