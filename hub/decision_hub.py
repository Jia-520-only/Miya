"""
决策层 Hub
监听 M-Link 消息并协调各子网进行决策
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from mlink.message import Message, MessageType, FlowType


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

    def __init__(self, mlink, ai_client, emotion, personality, prompt_manager, memory_net, decision_engine, tool_registry=None, memory_engine=None, scheduler=None, onebot_client=None):
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
        """
        self.mlink = mlink
        self.ai_client = ai_client
        self.emotion = emotion
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.memory_net = memory_net
        self.decision_engine = decision_engine
        self.tool_registry = tool_registry
        self.memory_engine = memory_engine
        self.scheduler = scheduler
        self.onebot_client = onebot_client

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

        # 检查是否是拍一拍（特殊消息类型，优先响应）
        if '拍了拍你' in content:
            logger.info(f"[决策层] 检测到拍一拍，生成响应中...")
            response = self.emotion.influence_response(
                f"被{sender_name}拍了呢~"
            )
            logger.info(f"[决策层] 拍一拍响应生成: {response}")
            return response

        # 检查是否需要响应（私聊、@机器人、或名字关键词）
        should_respond = (
            message_type == 'private' or  # 私聊
            is_at_bot or  # @机器人
            content.startswith('弥娅') or  # 以"弥娅"开头
            content.startswith('Miya') or  # 以"Miya"开头
            content.startswith('miya')  # 以"miya"开头
        )

        if not should_respond:
            return None

        # 存储记忆
        await self._store_memory(perception)

        # 生成响应
        response = await self._generate_response(perception)

        return response

    async def _store_memory(self, perception: Dict) -> None:
        """
        存储记忆到 MemoryNet

        Args:
            perception: 感知数据
        """
        try:
            if self.memory_net and self.memory_net.conversation_history:
                # 使用 MemoryNet 存储记忆
                session_id = f"qq_{perception.get('user_id', 'unknown')}"

                memory_data = {
                    'type': 'conversation',
                    'session_id': session_id,
                    'role': 'user',
                    'content': perception.get('content', ''),
                    'sender': perception.get('sender_name', ''),
                    'timestamp': datetime.now().isoformat(),
                    'metadata': {
                        'user_id': perception.get('user_id'),
                        'group_id': perception.get('group_id'),
                        'message_type': perception.get('message_type')
                    }
                }

                # 调用 MemoryNet 存储方法
                if hasattr(self.memory_net, 'store'):
                    await self.memory_net.store(memory_data)
                    logger.debug("[决策层] 记忆已存储到 MemoryNet")
        except Exception as e:
            logger.error(f"存储记忆失败: {e}")

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

        # 如果没有 AI 客户端，使用简化回复
        if not self.ai_client:
            return self._fallback_response(content, sender_name)

        try:
            # 获取上下文（异步调用）
            memory_context = []
            if self.memory_net and hasattr(self.memory_net, 'get_recent_conversations'):
                memory_context = await self.memory_net.get_recent_conversations(
                    user_id=perception.get('user_id'),
                    limit=5
                )

            personality_state = self.personality.get_profile()

            # 构建提示词
            prompt_info = self.prompt_manager.build_full_prompt(
                user_input=content,
                memory_context=memory_context,
                additional_context={
                    'user_id': perception.get('user_id', 0),
                    'at_list': perception.get('at_list', []),
                    'bot_qq': perception.get('bot_qq')
                }
            )

            logger.debug(f"[系统提示词] {prompt_info['system'][:500]}")

            # 设置工具上下文
            if self.tool_registry:
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
                    'send_like_callback': getattr(self.onebot_client, 'send_like', None) if self.onebot_client else None
                }
                self.ai_client.set_tool_context(tool_context)

                # 调用 AI 客户端生成回复（带工具）
                response = await self.ai_client.chat_with_system_prompt(
                    system_prompt=prompt_info['system'],
                    user_message=prompt_info['user'],
                    tools=self.tool_registry.get_tools_schema()
                )
            else:
                # 调用 AI 客户端生成回复（不带工具）
                response = await self.ai_client.chat_with_system_prompt(
                    system_prompt=prompt_info['system'],
                    user_message=prompt_info['user']
                )

            # 情绪染色
            response = self.emotion.influence_response(response)

            # 情绪衰减
            self.emotion.decay_coloring()

            return response

        except Exception as e:
            logger.error(f"AI 生成失败: {e}，使用简化回复", exc_info=True)
            return self._fallback_response(content, sender_name)

    def _fallback_response(self, content: str, sender_name: str) -> str:
        """降级回复"""
        if '你好' in content or 'hi' in content.lower():
            response = f"{sender_name}你好呀~我是{self.personality.get_profile()['name']}，很高兴认识你！"
        elif '你是谁' in content:
            response = f"我是{self.personality.get_profile()['name']}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命。"
        elif '状态' in content:
            emotion_state = self.emotion.get_emotion_state()
            memory_count = len(self.memory_net.get_all_conversations()) if self.memory_net else 0
            response = (
                f"当前情绪状态: {emotion_state['dominant']}，强度: {emotion_state['intensity']:.2f}\n"
                f"记忆数量: {memory_count}"
            )
        else:
            response = self.emotion.influence_response(
                f"收到了{sender_name}的消息: {content}"
            )

        return response
