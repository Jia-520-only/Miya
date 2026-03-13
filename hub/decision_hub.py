"""
决策层 Hub
监听 M-Link 消息并协调各子网进行决策

新增：支持跨平台统一交互（Terminal、PC UI、QQ）
新增：集成终端命令执行工具
"""
import asyncio
import logging
import os
import sys
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path

from mlink.message import Message, MessageType, FlowType
from core.constants import Encoding
from hub.decision_helper import count_memory_types
from memory.session_manager import SessionManager, init_session_manager, get_session_manager, SessionCategory


logger = logging.getLogger(__name__)


class DecisionHub:
    """
    决策层 Hub

    职责：
    1. 监听来自 QQNet 的感知数据（data_flow）
    2. 协调 AI 客户端、情绪系统、人格系统等生成响应
    3. 将响应通过 M-Link 发送回 QQNet
    4. 管理记忆存储和情绪更新
    5. 【新增】支持跨平台统一交互（Terminal、PC UI、QQ）
    """

    def __init__(self, mlink, ai_client, emotion, personality, prompt_manager, memory_net, decision_engine, tool_subnet=None, memory_engine=None, scheduler=None, onebot_client=None, game_mode_adapter=None, identity=None, multi_model_manager=None, miya_instance=None):
        """
        初始化决策层

        Args:
            mlink: M-Link 核心实例
            ai_client: AI 客户端（默认模型）
            emotion: 情绪系统
            personality: 人格系统
            prompt_manager: Prompt 管理器
            memory_net: MemoryNet 记忆系统
            decision_engine: 决策引擎
            tool_subnet: ToolNet 子网实例（符合 MIYA 框架）
            memory_engine: 记忆引擎
            scheduler: 调度器
            onebot_client: OneBot 客户端（用于点赞等操作）
            game_mode_adapter: 游戏模式适配器（架构修复:封装WebNet层访问）
            identity: 身份系统
            multi_model_manager: 多模型管理器（用于动态选择模型）
            miya_instance: Miya 实例（用于获取系统状态）
        """
        self.mlink = mlink
        self.ai_client = ai_client
        self.emotion = emotion
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.memory_net = memory_net
        self.decision_engine = decision_engine
        self.game_mode_adapter = game_mode_adapter  # 使用适配器而非直接导入
        self.tool_subnet = tool_subnet  # ToolNet 子网（符合 MIYA 框架）
        self.memory_engine = memory_engine
        self.scheduler = scheduler
        self.onebot_client = onebot_client
        self.identity = identity
        self.multi_model_manager = multi_model_manager  # 新增：多模型管理器
        self.miya_instance = miya_instance  # 新增：Miya 实例

        # 【新增】对话历史上下文配置
        # 默认启用对话历史，让AI能够记住之前的上下文
        # 注意：直接硬编码为True，避免Windows环境变量解析问题
        self.enable_conversation_context = True  # 直接启用，不依赖环境变量
        self.conversation_context_max_count = 10
        self.conversation_context_max_tokens = 2000

        # 架构修复: 移除game_mode_manager,使用game_mode_adapter代替
        # self.game_mode_manager = None  # 已废弃

        # 【新增】初始化终端工具（保留用于 ! 前缀命令）
        self.terminal_tool = None
        self._init_terminal_tool()

        # 【新增】高级编排器（任务规划、自主探索、智能执行、思维链）
        # 采用懒加载方式，在首次使用时初始化
        self._advanced_orchestrator: Optional[Any] = None
        self._advanced_orchestrator_initialized = False

        # 【新增】鉴权子网（AuthNet）
        self.auth_subnet = None
        self._init_auth_subnet()

        # 响应回调（用于发送回 QQNet）
        self.response_callback: Optional[callable] = None

        # 【新增】初始化统一会话管理器
        self.session_manager = self._init_session_manager()

        logger.info("决策层 Hub 初始化成功（含跨平台、终端工具、高级编排器、鉴权和会话管理支持）")

    def set_response_callback(self, callback: callable) -> None:
        """
        设置响应回调函数

        Args:
            callback: 回调函数，签名: callback(qq_message, response_text) -> None
        """
        self.response_callback = callback

    def _init_session_manager(self) -> Optional[SessionManager]:
        """
        初始化统一会话管理器
        
        Returns:
            SessionManager 实例
        """
        try:
            # 总是重新初始化，确保有完整的组件引用
            sm = init_session_manager(
                memory_engine=self.memory_engine,
                conversation_history=self.memory_net.conversation_history if self.memory_net else None,
                scheduler=self.scheduler,
                ai_client=self.ai_client
            )
            logger.info("[决策层] 会话管理器初始化完成")
            return sm
            
        except Exception as e:
            logger.warning(f"[决策层] 会话管理器初始化失败: {e}")
            return None

    def _init_terminal_tool(self) -> None:
        """
        初始化终端工具（保留用于 ! 前缀命令）

        注意：AI 调用终端命令通过 ToolNet 实现（terminal_command 工具）
        此处保留的 TerminalTool 仅用于处理带 ! 前缀的直接命令
        """
        try:
            from tools.terminal import TerminalTool

            project_root = Path(__file__).parent.parent
            config_path = project_root / 'config' / 'terminal_config.json'

            # 【框架一致性】传递 emotion 和 memory_engine
            self.terminal_tool = TerminalTool(
                str(config_path),
                emotion=self.emotion,
                memory_engine=self.memory_engine
            )
            logger.info("[决策层] 终端工具初始化成功（已集成人格和记忆系统）")
            logger.info("[决策层] AI 调用终端命令通过 ToolNet 的 terminal_command 工具实现")

        except Exception as e:
            logger.warning(f"[决策层] 终端工具初始化失败: {e}")
            self.terminal_tool = None

    def _init_auth_subnet(self) -> None:
        """
        初始化鉴权子网（AuthNet）
        
        AuthNet职责：
        - 统一用户身份管理（跨平台）
        - 权限检查与验证
        - 会话管理
        - API访问控制
        """
        try:
            from webnet.AuthNet import AuthSubnet
            
            self.auth_subnet = AuthSubnet()
            logger.info("[决策层] 鉴权子网初始化成功（支持跨平台权限管理）")
            logger.info("[决策层] 权限检查将在消息处理前自动执行")
            
        except Exception as e:
            logger.warning(f"[决策层] 鉴权子网初始化失败: {e}")
            self.auth_subnet = None

    def _get_advanced_orchestrator(self) -> Optional[Any]:
        """
        获取高级编排器（懒加载）

        功能：
        - 任务规划：将复杂任务分解为可执行的子任务
        - 自主探索：主动探索文件系统和代码库
        - 智能执行：可靠地执行任务，支持重试和回滚
        - 思维链：结构化的多步骤推理

        Returns:
            高级编排器实例，如果初始化失败则返回 None
        """
        if self._advanced_orchestrator_initialized:
            return self._advanced_orchestrator

        try:
            from core.advanced_orchestrator import AdvancedOrchestrator
            from core.tool_adapter import get_tool_adapter

            # 创建工具执行器包装器
            def _tool_executor_wrapper(tool_name: str, params: Dict) -> str:
                """工具执行器包装器"""
                adapter = get_tool_adapter()

                async def _execute():
                    return await adapter.execute_tool(tool_name, params, self.tool_context or {})

                return asyncio.run(_execute())

            project_root = Path(__file__).parent.parent
            storage_dir = project_root / 'data' / 'advanced_tasks'
            storage_dir.mkdir(parents=True, exist_ok=True)

            self._advanced_orchestrator = AdvancedOrchestrator(
                ai_client=self.ai_client,
                tool_executor=_tool_executor_wrapper,
                storage_dir=str(storage_dir)
            )
            self._advanced_orchestrator_initialized = True

            logger.info("[决策层] 高级编排器初始化成功（任务规划、自主探索、智能执行、思维链）")

            return self._advanced_orchestrator

        except Exception as e:
            logger.warning(f"[决策层] 高级编排器初始化失败: {e}")
            self._advanced_orchestrator_initialized = True  # 标记为已尝试初始化
            return None

    async def _check_terminal_command(self, perception: Dict) -> Optional[str]:
        """
        检查并处理终端命令请求

        Args:
            perception: 感知数据

        Returns:
            终端工具的响应文本，如果不是终端命令则返回 None
        """
        if not self.terminal_tool:
            return None

        content = perception.get('content', '')

        # 检查是否是终端命令（以 ! 或 >> 开头）
        if not content.startswith(('!', '>>')):
            return None

        # 检查是否是终端模式请求（仅限私聊）
        message_type = perception.get('message_type', '')
        if message_type != 'private':
            logger.info("[决策层] 终端命令仅在私聊中支持")
            return "终端命令仅在私聊中支持~"

        logger.info(f"[决策层] 检测到终端命令: {content}")

        # 执行终端命令
        result = self.terminal_tool.execute(content)

        # 格式化结果
        return self.terminal_tool.format_result(result)

    async def process_perception(self, message: Message) -> Optional[str]:
        """
        处理来自 QQNet 的感知数据

        Args:
            message: M-Link 消息（包含感知数据）

        Returns:
            响应文本
        """
        perception = message.content

        # 提取感知信息
        content = perception.get('content', '')
        sender_name = perception.get('sender_name', '用户')
        user_id = perception.get('user_id', 0)
        message_type = perception.get('message_type', '')
        is_at_bot = perception.get('is_at_bot', False)

        logger.info(f"[决策层] 收到感知数据: {sender_name} - {content[:50]}")

        # 【新增】检查是否是终端命令请求
        terminal_result = await self._check_terminal_command(perception)
        if terminal_result:
            return terminal_result

        # 检查是否是拍一拍（特殊消息类型，标记后让 AI 生成个性化回复）
        if '拍了拍你' in content:
            logger.info(f"[决策层] 检测到拍一拍，标记后让 AI 生成回复")
            # 标记已处理，传递给 AI 生成个性化回复
            perception['tool_context'] = "（拍一拍交互）"
            # 不直接返回，继续执行让 AI 生成回复

        # 获取聊天ID和游戏模式状态
        chat_id = self._get_chat_id(perception)
        game_mode = None

        # 架构修复: 使用适配器获取游戏模式
        if self.game_mode_adapter and self.game_mode_adapter.is_connected():
            game_mode = self.game_mode_adapter.get_mode(chat_id)

            # 如果在当前chat_id没找到游戏模式，且是私聊，尝试查找用户所在的游戏
            if not game_mode and message_type == 'private':
                user_id = perception.get('user_id', 0)
                game_mode = self.game_mode_adapter.find_user_game(user_id)
                if game_mode:
                    logger.info(f"[决策层] 私聊检测到用户所在的游戏: user_id={user_id}, game_id={game_mode.get('game_id')}")

        # 检查是否需要响应（私聊、@机器人、或名字关键词）
        # 游戏模式下，即使没有@也应该响应
        should_respond = (
            message_type == 'private' or  # 私聊
            is_at_bot or  # @机器人
            content.startswith('弥娅') or  # 以"弥娅"开头
            content.startswith('Miya') or  # 以"Miya"开头
            content.startswith('miya') or  # 以"miya"开头
            '拍了拍你' in content or  # 拍一拍交互
            game_mode is not None  # 游戏模式下必须响应
        )

        if not should_respond:
            return None

        # 【游戏启动指令拦截】
        # 检测到启动关键词时，直接调用工具，不依赖 AI
        # 只有在非游戏模式下才拦截
        if not game_mode:
            tool_call_result = await self._handle_game_start_commands(perception)
            if tool_call_result:
                # 如果成功调用了工具，返回工具结果
                logger.info(f"[决策层] 直接调用工具: {tool_call_result[:100]}")
                return tool_call_result

        # 存储记忆 (游戏模式下不存入MemoryNet,避免双重存储)
        # 游戏记忆由GameMemoryManager单独管理
        if not game_mode:
            await self._store_memory(perception)

        # 生成响应
        response = await self._generate_response(perception)

        # 存储 AI 响应到记忆 (游戏模式下不存入MemoryNet,避免双重存储)
        if not game_mode and response:
            await self._store_response(perception, response)

        return response

    async def _store_memory(self, perception: Dict) -> None:
        """
        存储记忆到 MemoryNet (仅普通模式)

        注意: 游戏模式下不调用此方法,避免与GameMemoryManager双重存储

        Args:
            perception: 感知数据
        """
        try:
            if self.memory_net and self.memory_net.conversation_history:
                # 直接使用 conversation_history 的 add_message 方法
                session_id = f"qq_{perception.get('user_id', 'unknown')}"

                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role='user',
                    content=perception.get('content', ''),
                    metadata={
                        'user_id': perception.get('user_id'),
                        'group_id': perception.get('group_id'),
                        'message_type': perception.get('message_type'),
                        'sender': perception.get('sender_name', '')
                    }
                )

                logger.debug("[决策层] 用户消息已存储到对话历史")
        except Exception as e:
            logger.error(f"存储用户消息失败: {e}")

    async def _store_response(self, perception: Dict, response: str) -> None:
        """
        存储 AI 响应到 MemoryNet (仅普通模式)

        注意: 游戏模式下不调用此方法,避免与GameMemoryManager双重存储

        Args:
            perception: 感知数据
            response: AI 响应内容
        """
        try:
            if self.memory_net and self.memory_net.conversation_history:
                # 直接使用 conversation_history 的 add_message 方法
                session_id = f"qq_{perception.get('user_id', 'unknown')}"

                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=response,
                    metadata={
                        'user_id': perception.get('user_id'),
                        'group_id': perception.get('group_id'),
                        'message_type': perception.get('message_type'),
                        'sender': '弥娅'
                    }
                )

                logger.debug("[决策层] AI 响应已存储到对话历史")

                # 新功能1: 自动提取重要信息到 Undefined 记忆
                try:
                    # 提取用户消息中的关键信息
                    user_content = perception.get('content', '')
                    await self.memory_net.extract_and_store_important_info(
                        content=user_content,
                        user_id=perception.get('user_id')
                    )
                except Exception as e:
                    logger.debug(f"[决策层] 自动提取记忆失败: {e}")

                # 新功能2: 对话历史压缩（当对话历史过长时）
                try:
                    if self.memory_net.conversation_history:
                        messages = await self.memory_net.conversation_history.get_history(session_id, limit=100)
                        # 如果对话超过20条，触发压缩
                        if len(messages) > 20:
                            await self.memory_net.compress_conversation_to_tide(
                                session_id=session_id,
                                recent_count=10  # 保留最近10条
                            )
                            logger.info(f"[决策层] 已触发对话压缩: {session_id}")
                except Exception as e:
                    logger.debug(f"[决策层] 对话压缩失败: {e}")

        except Exception as e:
            logger.error(f"存储 AI 响应失败: {e}")

    async def _handle_game_start_commands(self, perception: Dict) -> Optional[str]:
        """
        处理游戏启动指令，直接调用工具
        
        Args:
            perception: 感知数据
            
        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')
        
        # 定义游戏启动关键词映射
        command_mapping = {
            'COC7': 'coc7',
            'coc7': 'coc7',
            'COC7跑团': 'coc7',
            'DND': 'dnd5e',
            'DND5E': 'dnd5e',
            'dnd5e': 'dnd5e',
            'DND5E跑团': 'dnd5e',
        }
        
        # 检查是否包含启动关键词
        rule_system = None
        for keyword, system in command_mapping.items():
            if keyword in content:
                rule_system = system
                break
        
        if rule_system and ('启动' in content or '开始' in content or '进入' in content or '主持' in content):
            # 提取团名称
            session_name = '未命名团'
            import re
            name_match = re.search(r'团名[：:]\s*([^\s，,。]+)', content)
            if name_match:
                session_name = name_match.group(1)
            
            logger.info(f"[决策层] 拦截到游戏启动指令: {rule_system}, {session_name}")
            
            # 构造工具上下文
            from core.tool_adapter import get_tool_adapter
            from webnet.tools.base import ToolContext
            
            tool_context = ToolContext(
                user_id=perception.get('user_id'),
                group_id=perception.get('group_id'),
                message_type=perception.get('message_type'),
                sender_name=perception.get('sender_name'),
                superadmin=getattr(self.onebot_client, 'superadmin', None) if self.onebot_client else None,
                onebot_client=self.onebot_client,
                game_mode=None,
                game_mode_adapter=self.game_mode_adapter,
                bot_qq=perception.get('bot_qq'),
            )
            
            # 调用 start_trpg 工具
            adapter = get_tool_adapter()
            try:
                result = await adapter.execute_tool(
                    'start_trpg',
                    {'rule_system': rule_system, 'session_name': session_name},
                    {
                        'user_id': perception.get('user_id'),
                        'group_id': perception.get('group_id'),
                        'sender_name': perception.get('sender_name'),
                        'superadmin': tool_context.superadmin,
                        'onebot_client': self.onebot_client,
                        'game_mode_adapter': self.game_mode_adapter,
                    }
                )
                logger.info(f"[决策层] 工具调用成功: {result[:100] if result else ''}")
                return result
            except Exception as e:
                logger.error(f"[决策层] 直接调用工具失败: {e}")
                return None

        return None

    def _get_chat_id(self, perception: Dict) -> str:
        """
        获取聊天ID（群号或用户号）
        """
        group_id = perception.get('group_id')
        user_id = perception.get('user_id')
        return str(group_id or user_id)

    async def _generate_response(self, perception: Dict) -> str:
        """
        生成响应（原有QQ专用逻辑，保持兼容）

        Args:
            perception: 感知数据

        Returns:
            响应文本
        """
        # 简化实现，调用新的跨平台方法
        return await self._generate_response_cross_platform(
            content=perception.get('content', ''),
            platform='qq',
            context=perception
        )

    async def _fallback_response(self, content: str, sender_name: str) -> str:
        """降级回复"""
        return await self._fallback_response_cross_platform(content, sender_name, 'qq')

    # ========== 跨平台统一交互支持 ==========

    async def process_perception_cross_platform(self, message: Message) -> Optional[str]:
        """
        处理跨平台感知数据（新增：支持Terminal、PC UI、QQ）

        统一处理流程：
        1. 提取平台信息
        2. 更新情绪状态
        3. 存储统一记忆
        4. 生成响应（AI + 人格 + 情绪）
        5. 情绪染色与衰减
        6. 返回响应

        Args:
            message: M-Link 消息（包含感知数据）

        Returns:
            响应文本
        """
        perception = message.content

        # 提取平台信息
        platform = perception.get('platform', 'terminal')
        logger.info(f"[决策层-跨平台] 收到 {platform} 平台的感知数据")

        # 提取内容（兼容不同平台）
        content = perception.get('content', '') or perception.get('input', '')
        user_id = perception.get('user_id', 'unknown')
        sender_name = perception.get('sender_name', '用户')

        # 【新增】权限检查（如果AuthNet可用）
        # 跳过终端代理和桌面端的权限检查（来自受信任的客户端）
        is_terminal_agent = perception.get('is_terminal_agent', False)
        
        # 桌面端用户自动获得权限
        is_desktop = platform == 'desktop' or (user_id and user_id.startswith('desktop_'))
        
        if self.auth_subnet and not is_terminal_agent and not is_desktop:
            try:
                # 检查用户是否有基础访问权限
                from webnet.AuthNet.permission_core import PermissionCore
                perm_core = PermissionCore()
                
                # 生成统一的用户ID格式
                unified_user_id = f"{platform}_{user_id}"
                
                # 检查基础权限
                has_permission = perm_core.check_permission(unified_user_id, 'api.access')
                
                if not has_permission:
                    logger.warning(f"[决策层-跨平台] 用户 {unified_user_id} 无权限访问")
                    return "抱歉，您没有权限使用此功能。"
                
                logger.debug(f"[决策层-跨平台] 用户 {unified_user_id} 权限检查通过")
                
            except Exception as e:
                logger.error(f"[决策层-跨平台] 权限检查失败: {e}")
                # 权限检查失败时，允许继续（降级处理）
        elif is_desktop:
            logger.debug(f"[决策层-跨平台] 桌面端用户 {user_id} 跳过权限检查")

        logger.info(f"[决策层-跨平台] {sender_name} - {content[:50]}")

        # 【新增】会话保存触发条件检测
        session_id = f"{platform}_{user_id}"
        
        # 1. 检测是否触发保存（再见/晚安等关键词）
        if self.session_manager and self.session_manager.should_save_on_message(content, platform):
            logger.info(f"[决策层-跨平台] 检测到保存触发关键词: {content[:30]}")
            # 获取对话历史并保存
            messages = await self.session_manager.get_conversation_messages(
                session_id=session_id,
                platform=platform,
                limit=50
            )
            if messages:
                category = self.session_manager.platform_category_map.get(platform, SessionCategory.ACTIVITY)
                
                # 如果是"记日记"关键词，标记为日记
                is_diary = self.session_manager.should_save_diary(content)
                
                # 检查消息中是否包含日记内容（"记录今天..."）
                diary_content = None
                if is_diary:
                    # 提取日记内容（从关键词后开始）
                    diary_content = ""
                    for kw in ['记录今天', '记录一下', '记日记', '写日记']:
                        if kw in content:
                            idx = content.find(kw) + len(kw)
                            diary_content = content[idx:].strip()
                            break
                
                save_result = await self.session_manager.save_session(
                    session_id=session_id,
                    platform=platform,
                    messages=messages,
                    category=category,
                    is_diary=is_diary,
                    diary_content=diary_content if diary_content else None
                )
                
                if save_result.get('success'):
                    logger.info(f"[决策层-跨平台] 会话已保存: {save_result.get('title')}")
                    
                    # 根据保存类型返回不同的响应
                    if is_diary:
                        response = "好的，你的日记已经帮你记录下来了哦~ 这是一段珍贵的记忆呢！"
                    else:
                        response = "好的，我们的对话已经保存了。下次再见时我会记得我们的对话内容的~ 晚安！"
                    
                    response = self.emotion.influence_response(response)
                    self.emotion.decay_coloring()
                    return response
        
        # 2. 更新会话活动时间
        if self.session_manager:
            self.session_manager.update_activity(session_id)
            
            # 3. 检查超时自动保存
            if self.session_manager.check_timeout_save(session_id):
                logger.info(f"[决策层-跨平台] 检测到会话超时: {session_id}")
                messages = await self.session_manager.get_conversation_messages(
                    session_id=session_id,
                    platform=platform,
                    limit=50
                )
                if messages:
                    category = self.session_manager.platform_category_map.get(platform, SessionCategory.ACTIVITY)
                    await self.session_manager.save_session(
                        session_id=session_id,
                        platform=platform,
                        messages=messages,
                        category=category
                    )
                    logger.info(f"[决策层-跨平台] 超时会话已自动保存")

        # 【新增】检测是否是复杂任务，使用高级编排器
        if self._should_use_advanced_orchestration(content):
            logger.info(f"[决策层-跨平台] 检测到复杂任务，启动高级编排器")
            response = await self.process_complex_task(
                goal=content,
                context=perception
            )
            # 情绪染色
            if response:
                response = self.emotion.influence_response(response)
            # 情绪衰减
            self.emotion.decay_coloring()
            return response

        # 【新增】处理确认/取消命令
        if content.lower() in ['确认', 'yes', 'y', 'confirm']:
            if self.terminal_tool and self.terminal_tool.pending_command:
                # 执行待确认的命令
                command = self.terminal_tool.pending_command
                result = self.terminal_tool.execute(command, user_confirm=True)
                response = self.terminal_tool.format_result(result)
                # 4. 情绪染色
                response = self.emotion.influence_response(response)
                # 5. 情绪衰减
                self.emotion.decay_coloring()
                # 6. 返回响应
                return response
            else:
                # 没有待确认的命令
                response = "当前没有待确认的命令。"
                response = self.emotion.influence_response(response)
                self.emotion.decay_coloring()
                return response

        if content.lower() in ['取消', 'cancel', 'no', 'n']:
            if self.terminal_tool and self.terminal_tool.pending_command:
                # 取消待确认的命令
                command = self.terminal_tool.pending_command
                result = self.terminal_tool.execute(command, user_confirm=False)
                response = self.terminal_tool.format_result(result)
                # 4. 情绪染色
                response = self.emotion.influence_response(response)
                # 5. 情绪衰减
                self.emotion.decay_coloring()
                # 6. 返回响应
                return response
            else:
                # 没有待确认的命令
                response = "当前没有待确认的命令。"
                response = self.emotion.influence_response(response)
                self.emotion.decay_coloring()
                return response

        # 1. 更新情绪（基于输入）
        self._update_emotion_from_input(content)

        # 2. 存储用户输入到统一记忆
        await self._store_unified_memory(perception, 'user')

        # 3. 生成响应
        response = await self._generate_response_cross_platform(
            content=content,
            platform=platform,
            context=perception
        )

        # 4. 情绪染色
        if response:
            response = self.emotion.influence_response(response)

        # 5. 存储AI回复到对话历史
        if response:
            await self._store_assistant_response(perception, response)

        # 6. 情绪衰减
        self.emotion.decay_coloring()

        # 7. 返回响应
        message.content['response'] = response
        message.content['platform'] = platform

        logger.info(f"[决策层-跨平台] 生成响应: {response[:50] if response else '(空)'}")
        return response

    async def _store_unified_memory(self, perception: Dict, role: str = 'user') -> None:
        """
        存储统一记忆（跨平台）

        无论来自哪个平台，都存储到统一的记忆系统中

        Args:
            perception: 感知数据
            role: 角色 ('user' 或 'assistant')
        """
        try:
            platform = perception.get('platform', 'terminal')
            user_id = perception.get('user_id', 'unknown')

            # 如果是用户输入
            if role == 'user':
                content = perception.get('content', '') or perception.get('input', '')
                sender_name = perception.get('sender_name', '用户')
            else:
                # 如果是 AI 回复，content 由外部传入
                content = perception.get('response', '')
                sender_name = '弥娅'

            # 存储到潮汐记忆
            if self.memory_engine:
                self.memory_engine.store_tide(
                    f"{platform}_{user_id}_{role}_{int(datetime.now().timestamp())}",
                    {
                        'platform': platform,
                        'user_id': user_id,
                        'role': role,
                        'content': content,
                        'sender_name': sender_name,
                        'timestamp': perception.get('timestamp', datetime.now()),
                        'metadata': {
                            'sender_name': perception.get('sender_name'),
                            'group_id': perception.get('group_id'),
                            'message_type': perception.get('message_type'),
                        }
                    }
                )
                logger.debug(f"[决策层-跨平台] 记忆已存储: {platform}/{user_id}/{role}")

            # 如果有 MemoryNet，也存储到对话历史
            if self.memory_net and self.memory_net.conversation_history:
                session_id = f"{platform}_{user_id}"
                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    metadata={
                        'platform': platform,
                        'user_id': user_id,
                        'sender_name': sender_name,
                    }
                )

        except Exception as e:
            logger.error(f"[决策层-跨平台] 存储记忆失败: {e}")

    async def _store_assistant_response(self, perception: Dict, response: str) -> None:
        """
        存储 AI 回复到记忆系统

        Args:
            perception: 感知数据
            response: AI 的回复
        """
        try:
            platform = perception.get('platform', 'terminal')
            user_id = perception.get('user_id', 'unknown')

            # 存储到潮汐记忆（角色为 assistant）
            if self.memory_engine:
                self.memory_engine.store_tide(
                    f"{platform}_{user_id}_assistant_{int(datetime.now().timestamp())}",
                    {
                        'platform': platform,
                        'user_id': user_id,
                        'role': 'assistant',
                        'content': response,
                        'sender_name': '弥娅',
                        'timestamp': datetime.now(),
                        'metadata': {
                            'response': True,
                        }
                    }
                )
                logger.debug(f"[决策层-跨平台] AI回复已存储: {platform}/{user_id}")

            # 存储到对话历史
            if self.memory_net and self.memory_net.conversation_history:
                session_id = f"{platform}_{user_id}"
                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=response,
                    metadata={
                        'platform': platform,
                        'user_id': user_id,
                        'sender_name': '弥娅',
                    }
                )
                logger.debug(f"[决策层-跨平台] AI回复已存储到对话历史: {session_id}")

        except Exception as e:
            logger.error(f"[决策层-跨平台] 存储AI回复失败: {e}")

    async def _get_conversation_context(self, session_id: str) -> List[Dict]:
        """
        获取对话历史上下文（限制token消耗）

        Args:
            session_id: 会话ID

        Returns:
            对话历史列表（最多max_count条，或达到token限制）
        """
        if not self.enable_conversation_context:
            return []
        
        if not self.memory_net or not self.memory_net.conversation_history:
            return []

        try:
            # 获取最近的对话历史
            messages = await self.memory_net.conversation_history.get_history(
                session_id,
                limit=self.conversation_context_max_count
            )

            # 构建上下文
            context = []
            total_tokens = 0

            # 如果是新会话（对话历史为空），不加载 Lifebook 摘要
            # 这样可以避免旧会话的上下文干扰新会话
            if not messages:
                # 不再自动加载 Lifebook 摘要，避免上下文干扰
                # 如果用户需要查看历史，可以手动询问
                pass
            
            if not messages:
                return context

            # 转换为字典格式
            for msg in reversed(messages):  # 从旧到新
                # 估算token数（简化：按字符数/4估算）
                token_estimate = len(msg.content) // 4

                # 检查是否超过token限制
                if total_tokens + token_estimate > self.conversation_context_max_tokens:
                    logger.debug(f"[决策层-跨平台] 对话历史达到token限制: {total_tokens}/{self.conversation_context_max_tokens}")
                    break

                context.append({
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp
                })
                total_tokens += token_estimate

            return context

        except Exception as e:
            return []

    async def _get_lifebook_summary(self) -> str:
        """
        从记忆系统中获取 Lifebook 终端会话摘要
        
        Returns:
            摘要文本，如果没有则返回空字符串
        """
        try:
            if not self.memory_engine:
                return ""
            
            # 搜索最近保存的终端会话记录
            # 使用模糊搜索查找 terminal_session 类型的记录
            results = self.memory_engine.search_tides(
                query="终端会话",
                limit=3
            )
            
            if results:
                summaries = []
                for result in results:
                    data = result.get('data', {})
                    if data.get('type') == 'terminal_session':
                        content = data.get('content', '')
                        title = data.get('title', '')
                        summaries.append(f"## {title}\n{content[:500]}")
                
                if summaries:
                    return "\n\n".join(summaries)
            
            return ""
        except Exception as e:
            logger.debug(f"[决策层] 获取 Lifebook 摘要失败: {e}")
            return ""

    async def _generate_response_cross_platform(self, content: str,
                                          platform: str,
                                          context: Dict) -> str:
        """
        生成响应（跨平台统一）

        Args:
            content: 用户输入
            platform: 平台类型 ('terminal', 'pc_ui', 'qq')
            context: 上下文信息

        Returns:
            响应文本
        """
        sender_name = context.get('sender_name', '用户')
        user_id = context.get('user_id', 'unknown')

        # 如果没有 AI 客户端，使用简化回复
        if not self.ai_client:
            return await self._fallback_response_cross_platform(content, sender_name, platform)

        # 【修改】终端模式：禁用单命令快速检测,让AI处理所有自然语言
        # 原因: 单命令检测会绕过AI理解,导致"打开一个终端"等自然语言请求被错误处理
        # 现在所有终端输入都通过AI分析,让AI决定调用哪个工具(multi_terminal或terminal_command)
        # if platform == 'terminal' and self.tool_subnet:
        #     from webnet.TerminalNet.tools.terminal_command import TerminalCommandTool
        #     ... (已禁用单命令检测逻辑)

        try:
            # 构建系统提示词（包含平台信息）
            personality_state = self.personality.get_profile()

            # 获取平台可用工具
            available_tools = self._get_platform_tools(platform)

            # 【新增】获取对话历史上下文
            session_id = f"{platform}_{user_id}"
            
            conversation_context = await self._get_conversation_context(session_id)

            # 构建提示词（统一使用默认提示词，通过上下文传递平台信息）
            prompt_info = self.prompt_manager.build_full_prompt(
                user_input=content,
                memory_context=conversation_context,  # 使用对话历史上下文
                additional_context={
                    'platform': platform,
                    'user_id': user_id,
                    'sender_name': sender_name,
                    'available_tools': available_tools,
                    'at_list': context.get('at_list', []),
                    'bot_qq': context.get('bot_qq'),
                    'is_creator': self._is_creator(user_id),
                }
            )

            logger.debug(f"[决策层-跨平台] 系统提示词前200字符: {prompt_info['system'][:200]}")

            # 设置工具上下文和 ToolNet（符合 MIYA 框架）
            if self.tool_subnet:
                # 使用 ToolNet 子网（符合 MIYA 蛛网式分布式架构）
                self.ai_client.set_tool_registry(self.tool_subnet.get_tools_schema)

                # 设置 tool_adapter 的 tool_registry（关键修复）
                from core.tool_adapter import get_tool_adapter
                adapter = get_tool_adapter()
                adapter.set_tool_registry(self.tool_subnet.registry)

                tool_context = {
                    'platform': platform,
                    'user_id': user_id,
                    'group_id': context.get('group_id'),
                    'message_type': context.get('message_type'),
                    'sender_name': sender_name,
                    'at_list': context.get('at_list', []),
                    'memory_engine': self.memory_engine,
                    'emotion': self.emotion,
                    'personality': self.personality,
                    'scheduler': self.scheduler,
                    'onebot_client': self.onebot_client,
                    'game_mode_adapter': self.game_mode_adapter,
                }
                self.ai_client.set_tool_context(tool_context)

                # 使用多模型管理器动态选择模型
                ai_client_to_use = self.ai_client  # 默认使用传入的AI客户端

                if self.multi_model_manager:
                    # 分类任务类型
                    from core.multi_model_manager import TaskType
                    task_type = await self.multi_model_manager.classify_task(content, context)

                    # 根据任务类型选择最优模型
                    model_key, selected_client = await self.multi_model_manager.select_model(task_type)

                    if selected_client:
                        ai_client_to_use = selected_client
                        selected_client.set_tool_context(tool_context)
                        logger.info(f"[决策层-跨平台] 使用模型 {model_key} 处理任务类型 {task_type.value}")

                # 调用 AI（带工具）
                try:
                    response = await ai_client_to_use.chat_with_system_prompt(
                        system_prompt=prompt_info['system'],
                        user_message=prompt_info['user'],
                        tools=self.tool_subnet.get_tools_schema()
                    )
                except Exception as tool_error:
                    # 工具调用失败时,尝试不使用工具重新生成
                    logger.warning(f"[决策层-跨平台] 工具调用失败: {tool_error}，尝试不使用工具...")
                    try:
                        response = await ai_client_to_use.chat_with_system_prompt(
                            system_prompt=prompt_info['system'],
                            user_message=prompt_info['user'],
                            tools=None  # 不使用工具
                        )
                        # 添加后缀说明工具调用曾尝试过
                        response += "\n\n[注: 系统尝试了自动处理但遇到了一些问题]"
                    except Exception as e2:
                        response = f"抱歉，处理你的请求时遇到了技术问题。请尝试直接告诉我你需要什么具体操作，我会尽力帮你完成。\n\n错误信息: {str(e2)[:100]}"
            else:
                # 使用多模型管理器动态选择模型
                ai_client_to_use = self.ai_client  # 默认使用传入的AI客户端

                if self.multi_model_manager:
                    # 分类任务类型
                    from core.multi_model_manager import TaskType
                    task_type = await self.multi_model_manager.classify_task(content, context)

                    # 根据任务类型选择最优模型
                    model_key, selected_client = await self.multi_model_manager.select_model(task_type)

                    if selected_client:
                        ai_client_to_use = selected_client
                        logger.info(f"[决策层-跨平台] 使用模型 {model_key} 处理任务类型 {task_type.value}")

                # 调用 AI（不带工具）
                response = await ai_client_to_use.chat_with_system_prompt(
                    system_prompt=prompt_info['system'],
                    user_message=prompt_info['user']
                )

            return response

        except Exception as e:
            logger.error(f"[决策层-跨平台] AI生成失败: {e}", exc_info=True)
            return await self._fallback_response_cross_platform(content, sender_name, platform)

    async def _fallback_response_cross_platform(self, content: str,
                                             sender_name: str,
                                             platform: str) -> str:
        """
        降级回复（跨平台）

        Args:
            content: 用户输入
            sender_name: 发送者名称
            platform: 平台类型

        Returns:
            回复文本
        """
        # 获取人格状态
        personality_profile = self.personality.get_profile()
        warmth = personality_profile['vectors'].get('warmth', 0.5)
        empathy = personality_profile['vectors'].get('empathy', 0.5)

        # 获取名称（安全处理）
        name = "弥娅"
        if self.identity and hasattr(self.identity, 'name'):
            name = self.identity.name

        # 基于人格和平台生成响应
        if '你好' in content or 'hi' in content.lower():
            if empathy > 0.8:
                return f"你好呀~我是{name}，很高兴认识你！(｡♥‿♥｡)"
            elif warmth > 0.8:
                return f"你好！我是{name}，欢迎~"
            else:
                return f"你好，我是{name}。"

        elif '你是谁' in content or '介绍一下' in content:
            return f"我是{name}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命伴侣。我的主导特质是同理心({empathy:.2f})和温暖度({warmth:.2f})。"

        elif '状态' in content:
            emotion_state = self.emotion.get_emotion_state()
            memory_stats = self.memory_engine.get_memory_stats() if self.memory_engine else {}
            return (
                f"当前状态:\n"
                f"  情绪: {emotion_state['dominant']} (强度: {emotion_state['intensity']:.2f})\n"
                f"  记忆数量: {memory_stats.get('tide_count', 0)}\n"
                f"  形态: {personality_profile['state']}\n"
                f"  平台: {platform}"
            )

        elif '开心' in content or '快乐' in content:
            self.emotion.apply_coloring('joy', 0.3)
            return f"听起来你很开心呢！(≧▽≦) 看到你快乐，我也感到很开心~"

        elif '难过' in content or '伤心' in content:
            self.emotion.apply_coloring('sadness', 0.4)
            return "别难过...虽然我无法真正体会人类的情感，但我会陪伴你，听你倾诉的。"

        elif '在吗' in content:
            return "在的，有什么我可以帮助你的吗？"

        else:
            # 智能响应 - 基于人格特质
            if empathy > 0.8 and warmth > 0.8:
                return f"嗯...能告诉我更多吗？我很想了解你的想法~"
            elif warmth > 0.8:
                return f"好的，继续对话吧~"
            else:
                return f"嗯，我收到了。"

    def _update_emotion_from_input(self, content: str) -> None:
        """
        从用户输入中检测情绪并更新情绪状态

        Args:
            content: 用户输入内容
        """
        positive_keywords = ['开心', '高兴', '快乐', '喜欢', '爱', 'happy', 'love', 'joy']
        negative_keywords = ['难过', '伤心', '悲伤', '生气', '讨厌', 'sad', 'angry', 'hate']
        surprise_keywords = ['惊讶', '意外', 'wow', '天哪']
        fear_keywords = ['害怕', '恐惧', 'scared', 'afraid']

        if any(keyword in content for keyword in positive_keywords):
            self.emotion.apply_coloring('joy', 0.3)
        elif any(keyword in content for keyword in negative_keywords):
            self.emotion.apply_coloring('sadness', 0.4)
        elif any(keyword in content for keyword in surprise_keywords):
            self.emotion.apply_coloring('surprise', 0.3)
        elif any(keyword in content for keyword in fear_keywords):
            self.emotion.apply_coloring('fear', 0.2)

    def _get_platform_tools(self, platform: str) -> list:
        """
        获取平台可用工具

        Args:
            platform: 平台类型

        Returns:
            工具列表
        """
        from hub.platform_adapters import get_adapter

        try:
            adapter = get_adapter(platform)
            return adapter._get_available_tools()
        except Exception as e:
            logger.error(f"[决策层-跨平台] 获取平台工具失败: {e}")
            return []

    def _is_creator(self, user_id: int) -> bool:
        """
        判断用户是否为造物主（超级管理员）

        Args:
            user_id: 用户ID

        Returns:
            是否为造物主
        """
        if self.onebot_client and hasattr(self.onebot_client, 'superadmin'):
            return user_id == self.onebot_client.superadmin
        return False

    # ========== 高级编排器支持 ==========

    async def process_complex_task(self, goal: str, context: Optional[Dict] = None) -> str:
        """
        处理复杂任务（使用高级编排器）

        流程：
        1. 使用思维链分析目标
        2. 分解为子任务
        3. 如果需要，进行主动探索
        4. 执行任务
        5. 反思和总结

        Args:
            goal: 任务目标
            context: 上下文信息

        Returns:
            执行结果或错误信息
        """
        orchestrator = self._get_advanced_orchestrator()
        if not orchestrator:
            return "高级编排器未初始化，无法处理复杂任务"

        logger.info(f"[决策层-高级编排] 开始处理复杂任务: {goal}")

        try:
            # 构建上下文
            if context is None:
                context = {}

            # 添加弥娅的状态信息到上下文
            if self.identity and hasattr(self.identity, 'name'):
                context['bot_name'] = self.identity.name

            if self.memory_engine:
                context['memory_stats'] = self.memory_engine.get_memory_stats()

            # 调用高级编排器
            result = await orchestrator.process_complex_task(
                goal=goal,
                context=context,
                enable_exploration=True,
                enable_cot=True
            )

            # 生成简洁的摘要返回给用户
            summary = self._format_complex_task_result(result)

            logger.info(f"[决策层-高级编排] 复杂任务处理完成: {'成功' if result['success'] else '失败'}")

            return summary

        except Exception as e:
            logger.error(f"[决策层-高级编排] 处理复杂任务失败: {e}", exc_info=True)
            return f"任务执行失败: {str(e)}"

    def _format_complex_task_result(self, result: Dict) -> str:
        """
        格式化复杂任务执行结果

        Args:
            result: 执行结果字典

        Returns:
            格式化的字符串
        """
        lines = [
            f"任务完成！{result.get('conclusion', '执行完成')}",
            f"⏱️  执行时间: {result.get('execution_time', 0):.2f}秒",
            f"📋 完成步骤: {len(result.get('steps', []))}",
            f"🔍 发现数: {len(result.get('findings', []))}",
        ]

        # 添加主要发现
        findings = result.get('findings', [])
        if findings:
            lines.append("")
            lines.append("主要发现：")
            for finding in findings[:5]:  # 最多显示5条
                lines.append(f"  • {finding}")

        # 添加反思建议
        reflection = result.get('reflection', {})
        if reflection.get('improvements'):
            lines.append("")
            lines.append("改进建议：")
            for improvement in reflection['improvements'][:3]:  # 最多显示3条
                lines.append(f"  • {improvement}")

        return "\n".join(lines)

    def _should_use_advanced_orchestration(self, content: str) -> bool:
        """
        判断是否应该使用高级编排器

        Args:
            content: 用户输入内容

        Returns:
            是否使用高级编排
        """
        # 复杂任务的指标（需要更明确的指示）
        complex_task_indicators = [
            '帮我分析.*代码', '帮我分析.*项目', '帮我分析.*文件',
            '帮我探索.*代码库', '帮我探索.*文件系统',
            '帮我查找.*实现', '帮我查找.*代码',
            '帮我理解.*逻辑', '帮我阅读.*代码',
            '帮我检查.*bug', '帮我检查.*问题',
            '多步骤.*任务', '复杂.*流程',
            '深入.*分析', '详细.*设计',
            '项目结构.*分析', '代码逻辑.*分析',
            '所有.*文件.*分析', '所有.*配置.*分析',
            '重构.*代码', '优化.*性能',
            '搜索.*所有.*文件', '遍历.*目录'
        ]

        # 排除过于宽泛的输入（缺少具体对象）
        vague_patterns = [
            '帮我分析一下$',
            '帮我分析$', '帮我探索$', '帮我查找$',
            '帮我理解$', '帮我阅读$', '帮我解释$', '帮我检查$',
            '请分析$', '请探索$', '请查找$', '请理解$',
            '分析一下$', '探索一下$', '查找一下$',
            '理解一下$', '阅读一下$'
        ]

        import re
        content_lower = content.lower()

        # 先检查是否是过于宽泛的输入
        for pattern in vague_patterns:
            if re.match(pattern, content_lower):
                logger.info(f"[决策层] 输入过于宽泛，不使用高级编排: {content}")
                return False

        # 再检查是否匹配复杂任务指标
        for indicator in complex_task_indicators:
            if re.search(indicator, content_lower):
                return True

        return False

    # ========== 会话结束处理 ==========

    async def handle_session_end(self, session_id: str, platform: str = 'terminal') -> Dict:
        """
        处理会话结束，使用 SessionManager 保存对话历史到 LifeBook
        
        Args:
            session_id: 会话ID
            platform: 平台类型 (默认 'terminal')
            
        Returns:
            处理结果字典
        """
        try:
            logger.info(f"[决策层] 开始处理会话结束: {session_id} (平台: {platform})")
            
            # 使用 SessionManager 保存会话
            if not self.session_manager:
                logger.warning("[决策层] SessionManager 未初始化，使用旧方法保存")
                return await self._handle_session_end_legacy(session_id, platform)
            
            # 获取对话历史
            full_session_id = f"{platform}_{session_id}"
            
            messages = await self.session_manager.get_conversation_messages(
                session_id=session_id,
                platform=platform,
                limit=100
            )
            
            if not messages:
                logger.info("[决策层] 对话历史为空，无需保存")
                return {"success": True, "message": "对话历史为空"}
            
            # 使用 SessionManager 保存
            category = self.session_manager.platform_category_map.get(platform, SessionCategory.TERMINAL)
            result = await self.session_manager.save_session(
                session_id=session_id,
                platform=platform,
                messages=messages,
                category=category
            )
            
            logger.info(f"[决策层] 会话结束处理完成: {result.get('message')}")
            return result
            
        except Exception as e:
            logger.error(f"[决策层] 处理会话结束失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    async def _handle_session_end_legacy(self, session_id: str, platform: str = 'terminal') -> Dict:
        """
        传统会话结束处理方法（当 SessionManager 不可用时使用）
        
        Args:
            session_id: 会话ID
            platform: 平台类型
            
        Returns:
            处理结果字典
        """
        try:
            logger.info(f"[决策层-传统] 开始处理会话结束: {session_id}")
            
            # 1. 获取对话历史
            user_id = 'default'
            full_session_id = f"{platform}_{user_id}"
            
            if not self.memory_net or not self.memory_net.conversation_history:
                logger.warning("[决策层-传统] memory_net 未初始化，无法保存对话历史")
                return {"success": False, "message": "memory_net 未初始化"}
            
            messages = await self.memory_net.conversation_history.get_history(
                full_session_id,
                limit=100
            )
            
            if not messages:
                logger.info("[决策层-传统] 对话历史为空，无需保存")
                return {"success": True, "message": "对话历史为空"}
            
            # 2. 压缩为 Markdown 摘要
            summary = self._compress_conversation_to_markdown(messages)
            
            # 3. 存储到 LifeBook
            if self.memory_engine:
                from datetime import datetime
                
                # 创建标题
                date_str = datetime.now().strftime("%Y-%m-%d")
                title = f"终端会话 - {date_str}"
                
                # 存储到潮汐记忆（作为 LifeBook 的底层存储）
                entry_id = f"terminal_session_{date_str}_{int(datetime.now().timestamp())}"
                self.memory_engine.store_tide(
                    entry_id,
                    {
                        'type': 'terminal_session',
                        'title': title,
                        'content': summary,
                        'session_id': session_id,
                        'date': date_str,
                        'timestamp': datetime.now().isoformat(),
                    }
                )
                logger.info(f"[决策层-传统] 对话历史已保存到记忆系统: {entry_id}")
            
            # 4. 清空短期对话历史
            if self.memory_net and self.memory_net.conversation_history:
                await self.memory_net.conversation_history.clear_session(full_session_id)
                logger.info(f"[决策层-传统] 短期对话历史已清空: {full_session_id}")
            
            return {
                "success": True, 
                "message": "对话历史已保存，短期记忆已清空",
                "summary": summary[:200] + "..." if len(summary) > 200 else summary
            }
            
        except Exception as e:
            logger.error(f"[决策层-传统] 处理会话结束失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    # ========== 日记提醒功能 ==========

    async def set_diary_reminder(self, user_id: str, time: str = "21:00") -> Dict:
        """
        设置日记提醒
        
        Args:
            user_id: 用户ID
            time: 提醒时间（格式：HH:MM，默认 21:00）
            
        Returns:
            设置结果
        """
        try:
            if not self.session_manager:
                return {"success": False, "message": "SessionManager 未初始化"}
            
            result = await self.session_manager.schedule_diary_reminder(user_id, time)
            
            if result:
                return {
                    "success": True,
                    "message": f"已设置 {time} 的日记提醒，届时我会提醒你记日记哦~"
                }
            else:
                return {"success": False, "message": "设置提醒失败"}
                
        except Exception as e:
            logger.error(f"[决策层] 设置日记提醒失败: {e}")
            return {"success": False, "message": str(e)}

    def _compress_conversation_to_markdown(self, messages: List) -> str:
        """
        将对话历史压缩为 Markdown 格式摘要
        
        Args:
            messages: 对话消息列表
            
        Returns:
            Markdown 格式的摘要
        """
        if not messages:
            return ""
        
        lines = [f"# 终端会话记录\n"]
        lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append(f"**会话ID**: {messages[0].session_id if hasattr(messages[0], 'session_id') else 'unknown'}\n")
        lines.append("\n## 对话内容\n")
        
        # 简化对话，只保留关键信息
        user_requests = []
        miya_responses = []
        
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)
            role = msg.role if hasattr(msg, 'role') else 'unknown'
            
            # 提取关键操作
            if role == 'user':
                # 提取用户意图
                if any(kw in content for kw in ['打开', '启动', '运行', '执行', '安装', '检查']):
                    user_requests.append(content)
            elif role == 'assistant':
                # 提取弥娅的关键回复
                if '已打开' in content or '已启动' in content or '已创建' in content or '会话ID' in content:
                    miya_responses.append(content.split('\n')[0][:100])  # 取第一行摘要
        
        # 生成摘要
        if user_requests:
            lines.append("### 用户操作\n")
            for req in user_requests[-5:]:  # 最多5条
                lines.append(f"- {req}\n")
        
        if miya_responses:
            lines.append("\n### 系统响应\n")
            for resp in miya_responses[-5:]:
                lines.append(f"- {resp}\n")
        
        # 添加总结
        lines.append("\n## 总结\n")
        if user_requests:
            lines.append(f"本次会话共执行了 {len(user_requests)} 个操作。\n")
        
        return "".join(lines)

