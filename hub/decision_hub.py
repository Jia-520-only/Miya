"""
决策层 Hub
监听 M-Link 消息并协调各子网进行决策
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from mlink.message import Message, MessageType, FlowType
from core.constants import Encoding
from hub.decision_helper import count_memory_types


logger = logging.getLogger(__name__)


class DecisionHub:
    """
    决策层 Hub

    职责：
    1. 监听来自 QQNet 的感知数据（data_flow）
    2. 协调 AI 客户端、情绪系统、人格系统等生成响应
    3. 将响应通过 M-Link 发送回 QQNet
    4. 管理记忆存储和情绪更新
    """

    def __init__(self, mlink, ai_client, emotion, personality, prompt_manager, memory_net, decision_engine, tool_registry=None, memory_engine=None, scheduler=None, onebot_client=None, game_mode_adapter=None):
        """
        初始化决策层

        Args:
            mlink: M-Link 核心实例
            ai_client: AI 客户端
            emotion: 情绪系统
            personality: 人格系统
            prompt_manager: Prompt 管理器
            memory_net: MemoryNet 记忆系统
            decision_engine: 决策引擎
            tool_registry: 工具注册表
            memory_engine: 记忆引擎
            scheduler: 调度器
            onebot_client: OneBot 客户端（用于点赞等操作）
            game_mode_adapter: 游戏模式适配器（架构修复:封装WebNet层访问）
        """
        self.mlink = mlink
        self.ai_client = ai_client
        self.emotion = emotion
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.memory_net = memory_net
        self.decision_engine = decision_engine
        self.game_mode_adapter = game_mode_adapter  # 使用适配器而非直接导入
        self.tool_registry = tool_registry
        self.memory_engine = memory_engine
        self.scheduler = scheduler
        self.onebot_client = onebot_client

        # 架构修复: 移除game_mode_manager,使用game_mode_adapter代替
        # self.game_mode_manager = None  # 已废弃

        # 响应回调（用于发送回 QQNet）
        self.response_callback: Optional[callable] = None

        logger.info("决策层 Hub 初始化成功")

    def set_response_callback(self, callback: callable) -> None:
        """
        设置响应回调函数

        Args:
            callback: 回调函数，签名: callback(qq_message, response_text) -> None
        """
        self.response_callback = callback

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

    async def _handle_like_command(self, perception: Dict) -> Optional[str]:
        """
        处理点赞指令，直接调用工具

        Args:
            perception: 感知数据

        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')

        # 检查是否包含点赞关键词
        if not any(keyword in content for keyword in ['点赞', '点个赞', '喜欢', '爱', '太棒了']):
            return None

        logger.info(f"[决策层] 拦截到点赞指令: {content}")

        # 智能解析点赞次数
        times = 1
        if '十次' in content or '十个' in content or '一人点十个' in content or '10次' in content:
            times = 10
        elif '一次' in content or '1次' in content:
            times = 1
        elif '两次' in content or '2次' in content:
            times = 2
        elif '三次' in content or '3次' in content:
            times = 3

        # 确定目标用户ID
        target_user_id = perception.get('user_id')
        at_list = perception.get('at_list', [])

        # 如果@了其他人，给被@的用户点赞
        if at_list and len(at_list) > 0:
            # 检查用户是否明确给自己点赞
            if '给我点赞' in content or '帮我点个赞' in content:
                target_user_id = perception.get('user_id')
            else:
                # 默认给第一个@的用户点赞
                target_user_id = at_list[0]

        logger.info(f"[决策层] 点赞目标: {target_user_id}, 次数: {times}")

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
            at_list=at_list,
            send_like_callback=getattr(self.onebot_client, 'send_like', None) if self.onebot_client else None,
        )

        # 调用 qq_like 工具
        adapter = get_tool_adapter()
        try:
            result = await adapter.execute_tool(
                'qq_like',
                {'target_user_id': target_user_id, 'times': times},
                {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'sender_name': perception.get('sender_name'),
                    'superadmin': tool_context.superadmin,
                    'at_list': at_list,
                    'send_like_callback': tool_context.send_like_callback,
                }
            )
            logger.info(f"[决策层] 点赞工具调用结果: {result[:100]}")
            return result
        except Exception as e:
            logger.error(f"[决策层] 点赞工具调用失败: {e}", exc_info=True)
            return f"点赞失败: {str(e)}"

    async def _handle_profile_command(self, perception: Dict) -> Optional[str]:
        """
        处理用户profile查询指令，直接调用get_profile工具

        Args:
            perception: 感知数据

        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')

        # 检查是否包含profile关键词
        if not any(keyword in content for keyword in ['我的生日', '我的名字', '我的姓名', '我的资料', '我的信息', '我的简介']):
            return None

        logger.info(f"[决策层] 拦截到profile查询指令: {content}")

        # 构造工具上下文
        from core.tool_adapter import get_tool_adapter
        from webnet.tools.base import ToolContext

        tool_context = ToolContext(
            user_id=perception.get('user_id'),
            group_id=perception.get('group_id'),
            message_type=perception.get('message_type'),
            sender_name=perception.get('sender_name'),
        )

        # 调用 get_profile 工具
        adapter = get_tool_adapter()
        try:
            result = await adapter.execute_tool(
                'get_profile',
                {'user_id': perception.get('user_id')},
                {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'sender_name': perception.get('sender_name'),
                }
            )
            logger.info(f"[决策层] profile查询工具调用结果: {result[:100]}")
            return result
        except Exception as e:
            logger.error(f"[决策层] profile查询工具调用失败: {e}", exc_info=True)
            return f"查询资料失败: {str(e)}"

    async def _handle_time_command(self, perception: Dict) -> Optional[str]:
        """
        处理时间查询指令，直接调用工具

        Args:
            perception: 感知数据

        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')

        # 检查是否包含时间关键词
        if not any(keyword in content for keyword in ['几点', '时间', '现在几点', '什么时候', '日期', '今天']):
            return None

        logger.info(f"[决策层] 拦截到时间查询指令: {content}")

        # 构造工具上下文
        from core.tool_adapter import get_tool_adapter
        from webnet.tools.base import ToolContext

        tool_context = ToolContext(
            user_id=perception.get('user_id'),
            group_id=perception.get('group_id'),
            message_type=perception.get('message_type'),
            sender_name=perception.get('sender_name'),
        )

        # 调用 get_current_time 工具
        adapter = get_tool_adapter()
        try:
            result = await adapter.execute_tool(
                'get_current_time',
                {'format': 'text', 'include_lunar': True},
                {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'sender_name': perception.get('sender_name'),
                }
            )
            logger.info(f"[决策层] 时间查询工具调用结果: {result[:100]}")
            return result
        except Exception as e:
            logger.error(f"[决策层] 时间查询工具调用失败: {e}", exc_info=True)
            return f"查询时间失败: {str(e)}"

    async def _handle_save_command(self, perception: Dict) -> Optional[str]:
        """
        处理存档指令，直接调用工具

        Args:
            perception: 感知数据

        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')

        # 检查是否包含存档关键词
        if not any(keyword in content for keyword in ['存档', '保存进度', '创建存档', '记录进度']):
            return None

        logger.info(f"[决策层] 拦截到存档指令: {content}")

        # 提取存档名称
        import re
        save_name = '未命名存档'
        name_match = re.search(r'存档名[：:]\s*([^\s，,。]+)', content)
        if name_match:
            save_name = name_match.group(1)
        elif '存档为' in content:
            save_name_match = re.search(r'存档为[：:]\s*([^\s，,。]+)', content)
            if save_name_match:
                save_name = save_name_match.group(1)

        # 构造工具上下文
        from core.tool_adapter import get_tool_adapter
        from webnet.tools.base import ToolContext

        tool_context = ToolContext(
            user_id=perception.get('user_id'),
            group_id=perception.get('group_id'),
            message_type=perception.get('message_type'),
            sender_name=perception.get('sender_name'),
            game_mode_adapter=self.game_mode_adapter,
        )

        # 调用 create_game_save 工具
        adapter = get_tool_adapter()
        try:
            result = await adapter.execute_tool(
                'create_game_save',
                {'save_name': save_name},
                {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'sender_name': perception.get('sender_name'),
                    'game_mode_adapter': self.game_mode_adapter,
                }
            )
            logger.info(f"[决策层] 存档工具调用结果: {result[:100]}")
            return result
        except Exception as e:
            logger.error(f"[决策层] 存档工具调用失败: {e}", exc_info=True)
            return f"存档失败: {str(e)}"

    async def _handle_load_save_command(self, perception: Dict) -> Optional[str]:
        """
        处理加载存档指令，直接调用工具

        Args:
            perception: 感知数据

        Returns:
            如果调用了工具，返回工具结果；否则返回 None
        """
        content = perception.get('content', '')

        # 检查是否包含加载存档关键词
        if not any(keyword in content for keyword in ['加载存档', '恢复存档', '读取存档']):
            return None

        logger.info(f"[决策层] 拦截到加载存档指令: {content}")

        # 构造工具上下文
        from core.tool_adapter import get_tool_adapter
        from webnet.tools.base import ToolContext

        tool_context = ToolContext(
            user_id=perception.get('user_id'),
            group_id=perception.get('group_id'),
            message_type=perception.get('message_type'),
            sender_name=perception.get('sender_name'),
            game_mode_adapter=self.game_mode_adapter,
        )

        # 调用 load_game_save 工具
        adapter = get_tool_adapter()
        try:
            result = await adapter.execute_tool(
                'load_game_save',
                {'save_id': 'autosave'},
                {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'sender_name': perception.get('sender_name'),
                    'game_mode_adapter': self.game_mode_adapter,
                }
            )
            logger.info(f"[决策层] 加载存档工具调用结果: {result[:100]}")
            return result
        except Exception as e:
            logger.error(f"[决策层] 加载存档工具调用失败: {e}", exc_info=True)
            return f"加载存档失败: {str(e)}"

    def _get_chat_id(self, perception: Dict) -> str:
        """
        获取聊天ID（群号或用户号）
        """
        group_id = perception.get('group_id')
        user_id = perception.get('user_id')
        return str(group_id or user_id)

    # 架构修复: 移除_get_game_mode_manager方法
    # 原方法通过from webnet导入,违反分层架构原则
    # 现在通过game_mode_adapter访问游戏模式功能

    async def _generate_response(self, perception: Dict) -> str:
        """
        生成响应

        Args:
            perception: 感知数据

        Returns:
            响应文本
        """
        content = perception.get('content', '')
        sender_name = perception.get('sender_name', '用户')

        # 【点赞指令拦截】
        # 检测到点赞关键词时，调用工具，但让 AI 生成自然回复
        like_keywords = ['点赞', '点个赞', '喜欢', '爱', '太棒了']
        if any(keyword in content for keyword in like_keywords):
            logger.info(f"[决策层] 检测到点赞关键词，调用工具")
            tool_result = await self._handle_like_command(perception)
            # 执行工具后，继续让 AI 生成自然回复，不直接返回工具结果
            # 将工具结果作为系统信息传递给 AI
            if tool_result and "✅" in tool_result:
                # 工具执行成功，将成功信息添加到上下文，让 AI 生成自然回复
                perception['tool_context'] = tool_result
            # 继续执行后续的 AI 响应生成

        # 【用户profile查询拦截】
        # 只处理明确的"查看/获取"指令，不处理询问类问题（如"我的生日是什么时候"）
        profile_query_keywords = ['查看侧写', '用户画像', '我的资料', '我的信息', '我的简介']
        if any(keyword in content for keyword in profile_query_keywords):
            logger.info(f"[决策层] 检测到profile查询关键词，直接调用工具")
            tool_call_result = await self._handle_profile_command(perception)
            if tool_call_result:
                return tool_call_result

        # 【时间查询拦截】
        # 排除包含"我的"的查询，避免误判profile查询
        if '我的' not in content:
            time_keywords = ['几点', '时间', '现在几点', '什么时候', '日期', '今天']
            if any(keyword in content for keyword in time_keywords):
                logger.info(f"[决策层] 检测到时间查询关键词，直接调用工具")
                tool_call_result = await self._handle_time_command(perception)
                if tool_call_result:
                    return tool_call_result

        # 【存档相关拦截】
        save_keywords = ['存档', '保存进度', '创建存档', '记录进度']
        if any(keyword in content for keyword in save_keywords):
            logger.info(f"[决策层] 检测到存档关键词，直接调用工具")
            tool_call_result = await self._handle_save_command(perception)
            if tool_call_result:
                return tool_call_result

        # 【加载存档拦截】
        load_keywords = ['加载存档', '恢复存档', '读取存档']
        if any(keyword in content for keyword in load_keywords):
            logger.info(f"[决策层] 检测到加载存档关键词，直接调用工具")
            tool_call_result = await self._handle_load_save_command(perception)
            if tool_call_result:
                return tool_call_result

        # 如果没有 AI 客户端，使用简化回复
        if not self.ai_client:
            return self._fallback_response(content, sender_name)

        try:
            # 获取聊天ID
            chat_id = self._get_chat_id(perception)

            # 获取当前游戏模式 (通过适配器)
            game_mode = None
            prompt_key = "default"

            # 架构修复: 使用game_mode_adapter而非直接导入webnet
            if self.game_mode_adapter and self.game_mode_adapter.is_connected():
                game_mode = self.game_mode_adapter.get_mode(chat_id)
                if game_mode:
                    prompt_key = game_mode.get('prompt_key', 'default')
                    logger.debug(f"[决策层] {chat_id} 处于游戏模式: {game_mode.get('mode_type')}")

            # 获取上下文（根据模式选择记忆系统，避免双重加载）
            # 优化：游戏模式和普通模式互斥，只加载一套记忆系统
            memory_context = []
            game_memory_context = None

            # 架构修复: 使用适配器获取游戏记忆
            if game_mode and self.game_mode_adapter:
                game_id = game_mode.get('game_id')
                if game_id:
                    # 游戏模式: 只加载游戏记忆，不加载普通记忆（避免冲突）
                    game_memory_context = self.game_mode_adapter.get_game_memory(game_id)
                    if game_memory_context:
                        logger.debug(f"[决策层] 加载游戏记忆: {game_memory_context.get('game_id')}")
            else:
                # 普通模式: 加载跨平台记忆上下文
                if self.memory_net:
                    # 1. 获取跨平台记忆（整合对话历史 + Undefined + 潮汐记忆）
                    cross_platform_memories = await self.memory_net.get_cross_platform_memories(
                        user_id=perception.get('user_id'),
                        limit=10
                    )

                    # 2. 转换为记忆上下文格式
                    memory_context = []
                    for mem in cross_platform_memories:
                        mem_type = mem.get('memory_type', 'dialogue')

                        if mem_type == 'dialogue':
                            # 对话历史
                            memory_context.append({
                                'role': mem['role'],
                                'content': mem['content'],
                                'source': mem.get('source', 'unknown')
                            })
                        elif mem_type == 'fact':
                            # Undefined 记忆（手动记忆）
                            memory_context.append({
                                'role': 'system',
                                'content': f"[长期记忆] {mem['content']}",
                                'source': mem.get('source', 'undefined')
                            })
                        elif mem_type == 'tide':
                            # 潮汐记忆
                            memory_context.append({
                                'role': 'system',
                                'content': f"[短期记忆] {mem['content']}",
                                'source': 'tide'
                            })

                    # 3. 特殊处理：如果用户询问个人信息（生日、名字等），额外搜索相关记忆
                    personal_info_keywords = ['生日', '名字', '姓名', '年龄']
                    if any(kw in content for kw in personal_info_keywords):
                        logger.info(f"[决策层] 检测到个人信息查询，搜索相关记忆")
                        try:
                            # 搜索Undefined记忆中包含用户ID和关键词的记录
                            from memory.undefined_memory import get_undefined_memory_adapter
                            undefined_adapter = get_undefined_memory_adapter()
                            user_memories = await undefined_adapter.search(
                                query=str(perception.get('user_id')),
                                limit=5
                            )
                            for mem in user_memories:
                                if any(kw in mem.get('content', '') for kw in personal_info_keywords):
                                    memory_context.append({
                                        'role': 'system',
                                        'content': f"[用户资料] {mem['content']}",
                                        'source': 'undefined_search'
                                    })
                                    logger.info(f"[决策层] 找到相关用户资料: {mem['content'][:50]}")
                        except Exception as e:
                            logger.debug(f"[决策层] 搜索用户记忆失败: {e}")

                    logger.info(f"[决策层] 加载跨平台记忆上下文: {len(memory_context)} 条记录")
                    logger.info(f"[决策层] 记忆类型分布: {count_memory_types(memory_context)}")
                else:
                    logger.warning(f"[决策层] MemoryNet不可用")
                    memory_context = []

            personality_state = self.personality.get_profile()
            logger.info(f"[决策层] 人格状态: {dominant if (dominant := personality_state.get('dominant', '')) else '未设置'}, vectors={personality_state.get('vectors', {})}")

            # 构建提示词（根据游戏模式使用不同提示词）
            logger.debug(f"[决策层] 传递给PromptManager的additional_context: sender_name={sender_name}")

            # 准备额外上下文
            # 获取管理员信息，用于判断是否为造物主
            superadmin = None
            if self.onebot_client and hasattr(self.onebot_client, 'superadmin'):
                superadmin = self.onebot_client.superadmin

            additional_context = {
                'user_id': perception.get('user_id', 0),
                'sender_name': sender_name,
                'at_list': perception.get('at_list', []),
                'bot_qq': perception.get('bot_qq'),
                'game_mode': game_mode.get('mode_type') if game_mode else None,
                'tool_result': perception.get('tool_context'),  # 添加工具执行结果
                'is_creator': superadmin and perception.get('user_id') == superadmin  # 判断是否为造物主（管理员）
            }

            # 游戏模式下添加游戏记忆上下文
            # 架构修复: 使用适配器获取游戏记忆
            if game_mode and self.game_mode_adapter:
                game_id = game_mode.get('game_id')
                if game_id:
                    game_memory_context = self.game_mode_adapter.get_game_memory(game_id)
                    if game_memory_context:
                        # 添加角色卡信息到游戏记忆上下文
                        characters = self.game_mode_adapter.get_game_characters(
                            game_id,
                            perception.get('user_id', 0),
                            is_admin=False
                        )
                        if characters:
                            # 格式化角色卡信息
                            char_info_lines = []
                            for char in characters:
                                attrs = char.get('attributes', {})
                                char_info_lines.append(
                                    f"**{char.get('character_name', '?')}**: "
                                    f"HP {attrs.get('hp', '?')}/{attrs.get('max_hp', '?')}, "
                                    f"力量{attrs.get('str', '?')}, "
                                    f"敏捷{attrs.get('dex', '?')}, "
                                    f"体质{attrs.get('con', '?')}, "
                                    f"外貌{attrs.get('app', '?')}, "
                                    f"智力{attrs.get('int', '?')}, "
                                    f"意志{attrs.get('pow', '?')}"
                                )
                            game_memory_context['characters_info'] = '\n'.join(char_info_lines)

                            # 添加当前发言者的角色信息（用于提示词）
                            current_player_chars = self.game_mode_adapter.get_game_characters(
                                game_id,
                                perception.get('user_id', 0),
                                is_admin=False
                            )
                            if current_player_chars:
                                # 找到第一个角色（一个用户只有一个角色）
                                current_char = current_player_chars[0]
                                additional_context['current_character'] = {
                                    'name': current_char.get('character_name', sender_name),
                                    'player_id': current_char.get('player_id'),
                                    'player_name': current_char.get('player_name', sender_name)
                                }
                                logger.debug(f"[决策层] 当前发言者角色: {additional_context['current_character']['name']}")

                        additional_context['game_memory'] = game_memory_context
                        logger.debug(f"[决策层] 游戏记忆上下文已添加,包含角色卡信息")

            prompt_info = self.prompt_manager.build_full_prompt(
                user_input=content,
                memory_context=memory_context,
                additional_context=additional_context,
                prompt_key=prompt_key  # 传递游戏模式对应的提示词key
            )

            logger.debug(f"[系统提示词] {prompt_info['system'][:500]}")

            # 获取游戏对话历史 (Token感知版本)
            game_conversation_history = None
            if game_mode and self.game_mode_adapter:
                game_id = game_mode.get('game_id')
                if game_id:
                    # 架构修复: 使用适配器获取对话历史
                    game_conversation_history = self.game_mode_adapter.get_conversation_history(
                        game_id,
                        max_tokens=80000  # 设置最大token数为80000,留出50000给其他内容
                    )
                    if game_conversation_history:
                        # 检测用户是否刚加载了存档或继续游戏
                        just_loaded_save = content.strip() in ['继续游戏', '继续', '开始游戏', '开始', '开始故事', '继续故事']

                        # 如果刚加载存档，只保留最近5条消息，避免AI被历史中的错误响应影响
                        if just_loaded_save and len(game_conversation_history) > 10:
                            logger.info(f"[决策层] 检测到存档加载后继续游戏，清理对话历史（原长度: {len(game_conversation_history)}）")
                            # 保留最新的5条消息（通常包含存档加载后的对话）
                            game_conversation_history = game_conversation_history[-5:]

                            # 保存清理后的对话历史到文件
                            try:
                                game_memory_manager = self.game_mode_adapter._game_memory_manager if self.game_mode_adapter else None
                                if game_memory_manager and game_id:
                                    from pathlib import Path
                                    game_dir = game_memory_manager._find_game_path(game_id)
                                    if game_dir:
                                        conversation_file = game_dir / "conversation.json"
                                        import json
                                        conversation_file.write_text(
                                            json.dumps(game_conversation_history, ensure_ascii=False, indent=2),
                                            encoding=Encoding.UTF8
                                        )
                                        logger.info(f"[决策层] 已保存清理后的对话历史: {len(game_conversation_history)} 条消息")
                            except Exception as e:
                                logger.error(f"[决策层] 保存清理后的对话历史失败: {e}")

                        # 检查是否有重复的AI消息（防止AI重复返回相同内容）
                        if len(game_conversation_history) >= 2:
                            last_two_messages = game_conversation_history[-2:]
                            if (len(last_two_messages) == 2 and
                                last_two_messages[0].get('role') == 'assistant' and
                                last_two_messages[1].get('role') == 'assistant' and
                                last_two_messages[0].get('content') == last_two_messages[1].get('content')):
                                logger.warning(f"[决策层] 检测到重复的AI消息，移除最后一条")
                                game_conversation_history.pop()

                        # 估算对话历史的token数
                        history_tokens = self.game_mode_adapter.estimate_conversation_tokens(
                            game_conversation_history
                        )
                        logger.info(f"[决策层] 加载游戏对话历史: {len(game_conversation_history)} 条消息, {history_tokens} tokens")

                        # 监控token数,接近限制时触发压缩
                        if history_tokens > 90000:  # 超过90000 tokens时触发压缩
                            logger.warning(f"[决策层] 对话历史tokens {history_tokens} 接近限制,触发压缩")
                            try:
                                import asyncio
                                asyncio.create_task(
                                    self.game_mode_adapter.compress_conversation(game_id)
                                )
                            except Exception as e:
                                logger.error(f"[决策层] 触发对话压缩失败: {e}")

            # 设置工具上下文
            # 【新架构】使用工具健康监控自动过滤不健康的工具
            if self.tool_registry:
                # 获取所有可用工具（自动过滤已熔断的工具）
                tools_to_use = self.tool_registry.get_tools_schema()

                # 游戏模式工具过滤（通过适配器）
                if game_mode:
                    # 使用适配器过滤工具
                    filtered_tools = self.game_mode_adapter.filter_tools(
                        {tool['function']['name']: tool for tool in tools_to_use},
                        chat_id
                    )
                    # 转换回列表格式
                    tools_to_use = list(filtered_tools.values())
                    logger.info(f"[决策层] 游戏模式工具过滤: {len(tools_to_use)} 个工具可用")

                # 调试: 打印工具schema信息
                logger.info(f"[决策层] 工具数量: {len(tools_to_use)}")
                for tool in tools_to_use:
                    func_name = tool.get('function', {}).get('name', 'unknown')
                    func_desc = tool.get('function', {}).get('description', '')[:100]
                    if func_name in ['list_game_saves', 'load_game_save']:
                        logger.info(f"[决策层] 存档工具: {func_name} - {func_desc}")
                    else:
                        logger.debug(f"[决策层] 工具: {func_name} - {func_desc}")


                # 获取 superadmin（从 onebot_client 或感知数据）
                superadmin = None
                if self.onebot_client and hasattr(self.onebot_client, 'superadmin'):
                    superadmin = self.onebot_client.superadmin
                elif 'bot_qq' in perception:
                    # 尝试从 qq_net 的配置中获取（需要通过 mlink 访问）
                    pass  # 暂时跳过，稍后在工具中获取

                tool_context = {
                    'user_id': perception.get('user_id'),
                    'group_id': perception.get('group_id'),
                    'message_type': perception.get('message_type'),
                    'sender_name': sender_name,
                    'at_list': perception.get('at_list', []),
                    'memory_engine': self.memory_engine,
                    'memory_net': self.memory_net,
                    'emotion': self.emotion,
                    'personality': self.personality,
                    'scheduler': self.scheduler,
                    'onebot_client': self.onebot_client,
                    'send_like_callback': getattr(self.onebot_client, 'send_like', None) if self.onebot_client else None,
                    'game_mode': game_mode,  # 传递游戏模式信息
                    'game_mode_adapter': self.game_mode_adapter,  # 架构修复: 传递适配器而非直接传递manager
                    'bot_qq': perception.get('bot_qq'),  # 传递机器人QQ号
                    'superadmin': superadmin  # 传递超级管理员
                }
                self.ai_client.set_tool_context(tool_context)

                # 【新架构】使用游戏状态机，不再依赖对话历史标记
                tool_choice = "auto"  # 默认让 AI 自主决定

                # 获取游戏状态
                from webnet.EntertainmentNet.game_mode.mode_state import GameState
                game_state = GameState.NOT_STARTED
                if self.game_mode_adapter and self.game_mode_adapter._game_mode_manager:
                    game_state = self.game_mode_adapter._game_mode_manager.get_game_state(chat_id)

                # 根据游戏状态动态调整工具调用策略
                if game_state == GameState.LOADING:
                    # 加载状态：禁止所有工具调用
                    logger.info(f"[决策层] 游戏处于 LOADING 状态，禁止工具调用")
                    tool_choice = "none"
                elif game_state == GameState.IN_PROGRESS:
                    # 游戏进行中：禁止存档工具调用（已在 tool 层面控制）
                    logger.info(f"[决策层] 游戏处于 IN_PROGRESS 状态，正常进行")
                    # 此时 tool_choice 保持 auto，但 load_game_save 工具已被白名单过滤
                elif game_state == GameState.NOT_STARTED:
                    # 游戏未启动：允许所有工具
                    logger.info(f"[决策层] 游戏处于 NOT_STARTED 状态，允许工具调用")

                # 检测游戏启动关键词（仅在非游戏模式下强制工具调用）
                game_start_keywords = [
                    '启动跑团', '开始跑团', '进入跑团模式', '/trpg',
                    'COC7跑团', 'DND5E跑团', '跑团', '主持游戏',
                    'KP', '守秘人', 'start_trpg', '启动COC7跑团模式',
                    '你作为KP开始主持游戏', '/tavern', '酒馆', '进入酒馆模式',
                    '开启跑团', '开启跑团模式'
                ]
                if any(keyword in content for keyword in game_start_keywords) and not game_mode:
                    logger.info(f"[决策层] 检测到游戏启动关键词（非游戏模式）")
                    tool_choice = "required"

                # 如果已自动执行了工具（如点赞、时间查询等），禁止 AI 再调用工具
                if perception.get('tool_context'):
                    logger.info(f"[决策层] 工具已自动执行，禁止 AI 调用工具")
                    tool_choice = "none"

                # 调用 AI 客户端生成回复（带工具）
                logger.info(f"[决策层] 调用AI, game_mode={bool(game_mode)}, use_miya_prompt={not bool(game_mode)}, prompt_key={prompt_key}")
                logger.info(f"[决策层] 系统提示词前200字符: {prompt_info['system'][:200]}")
                
                response = await self.ai_client.chat_with_system_prompt(
                    system_prompt=prompt_info['system'],
                    user_message=prompt_info['user'],
                    tools=tools_to_use,
                    use_miya_prompt=not bool(game_mode),  # 游戏模式下不使用弥娅人设提示词
                    conversation_history=game_conversation_history,  # 传递游戏对话历史
                    tool_choice=tool_choice  # 始终使用 auto，让模型自然决定
                )
            else:
                # 调用 AI 客户端生成回复（不带工具）
                response = await self.ai_client.chat_with_system_prompt(
                    system_prompt=prompt_info['system'],
                    user_message=prompt_info['user'],
                    use_miya_prompt=not bool(game_mode),  # 游戏模式下不使用弥娅人设提示词
                    conversation_history=game_conversation_history  # 传递游戏对话历史
                )

            # 保存游戏对话（游戏模式下）
            if game_mode and self.game_mode_adapter:
                game_id = game_mode.get('game_id')
                if game_id:
                    # 架构修复: 使用适配器保存对话
                    # 保存用户消息
                    self.game_mode_adapter.add_conversation_message(
                        game_id,
                        role='user',
                        content=content,
                        player_id=perception.get('user_id'),
                        player_name=sender_name
                    )

                    # 【新架构】不再依赖 SYSTEM_FLAG 检测
                    # 游戏状态由 GameState 状态机管理，工具权限在 tool 层面控制
                    # 直接保存 AI 响应到对话历史

                    logger.info(f"[决策层] 响应完整内容长度: {len(response) if response else 0}")
                    logger.debug(f"[决策层] 响应完整内容:\n{response}")

                    # 保存 AI 回复到对话历史
                    self.game_mode_adapter.add_conversation_message(
                        game_id,
                        role='assistant',
                        content=response
                    )

            # 情绪染色（游戏模式下可能不应用）
            if not game_mode:
                response = self.emotion.influence_response(response)

            # 情绪衰减
            self.emotion.decay_coloring()

            return response

        except Exception as e:
            logger.error(f"AI 生成失败: {e}，使用简化回复", exc_info=True)
            return await self._fallback_response(content, sender_name)

    async def _fallback_response(self, content: str, sender_name: str) -> str:
        """降级回复"""
        if '你好' in content or 'hi' in content.lower():
            response = f"{sender_name}你好呀~我是{self.personality.get_profile()['name']}，很高兴认识你！"
        elif '你是谁' in content:
            response = f"我是{self.personality.get_profile()['name']}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命。"
        elif '状态' in content:
            emotion_state = self.emotion.get_emotion_state()
            memory_count = 0
            if self.memory_net:
                try:
                    conversations = await self.memory_net.get_all_conversations()
                    memory_count = len(conversations)
                except Exception as e:
                    logger.error(f"获取记忆数量失败: {e}")
                    memory_count = 0
            response = (
                f"当前情绪状态: {emotion_state['dominant']}，强度: {emotion_state['intensity']:.2f}\n"
                f"记忆数量: {memory_count}"
            )
        else:
            response = self.emotion.influence_response(
                f"收到了{sender_name}的消息: {content}"
            )

        return response
