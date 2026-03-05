"""
Redis A2A通信器
基于Nexus Agents，实现Agent-to-Agent的Redis通信
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    COORDINATION = "coordination"     # 协调消息
    STATUS_UPDATE = "status_update"   # 状态更新
    TASK_ASSIGNMENT = "task_assignment" # 任务分配
    RESULT_BROADCAST = "result_broadcast" # 结果广播
    HEARTBEAT = "heartbeat"         # 心跳


@dataclass
class A2AMessage:
    """A2A消息"""
    message_id: str
    sender: str
    recipient: Optional[str] = None  # None表示广播
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 优先级


class RedisA2ACommunicator:
    """Redis A2A通信器"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        agent_id: str,
        channel: str = "agent_coordination"
    ):
        self.redis_url = redis_url
        self.agent_id = agent_id
        self.channel = channel

        # Redis连接（延迟加载）
        self._redis = None
        self._pubsub = None

        # 消息处理器
        self.message_handlers: Dict[MessageType, List[Callable]] = {}

        # 已知Agent集合
        self.known_agents: Set[str] = set()

        # 心跳定时器
        self.heartbeat_interval = 30  # 秒
        self._heartbeat_task = None

    async def connect(self) -> bool:
        """
        连接到Redis

        Returns:
            是否成功
        """
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(self.redis_url)
            self._pubsub = self._redis.pubsub()

            await self._pubsub.subscribe(self.channel)

            logger.info(f"[A2A] 连接成功: {self.agent_id} -> {self.channel}")
            return True

        except Exception as e:
            logger.error(f"[A2A] 连接失败: {e}")
            return False

    async def disconnect(self):
        """断开Redis连接"""
        try:
            if self._heartbeat_task:
                self._heartbeat_task.cancel()

            if self._pubsub:
                await self._pubsub.unsubscribe(self.channel)

            if self._redis:
                await self._redis.close()

            logger.info(f"[A2A] 断开连接: {self.agent_id}")

        except Exception as e:
            logger.error(f"[A2A] 断开连接失败: {e}")

    async def broadcast_message(
        self,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: int = 0
    ) -> bool:
        """
        广播消息

        Args:
            message_type: 消息类型
            content: 消息内容
            priority: 优先级

        Returns:
            是否成功
        """
        message = A2AMessage(
            message_id=self._generate_message_id(),
            sender=self.agent_id,
            message_type=message_type,
            content=content,
            priority=priority
        )

        try:
            await self._redis.publish(
                self.channel,
                json.dumps({
                    'message_id': message.message_id,
                    'sender': message.sender,
                    'recipient': message.recipient,
                    'message_type': message.message_type.value,
                    'content': message.content,
                    'timestamp': message.timestamp,
                    'priority': message.priority
                })
            )

            logger.debug(
                f"[A2A] 广播消息: {message.message_type.value}, "
                f"优先级: {priority}"
            )
            return True

        except Exception as e:
            logger.error(f"[A2A] 广播失败: {e}")
            return False

    async def send_message(
        self,
        recipient: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: int = 0
    ) -> bool:
        """
        发送消息给特定Agent

        Args:
            recipient: 接收者ID
            message_type: 消息类型
            content: 消息内容
            priority: 优先级

        Returns:
            是否成功
        """
        message = A2AMessage(
            message_id=self._generate_message_id(),
            sender=self.agent_id,
            recipient=recipient,
            message_type=message_type,
            content=content,
            priority=priority
        )

        try:
            await self._redis.publish(
                self.channel,
                json.dumps({
                    'message_id': message.message_id,
                    'sender': message.sender,
                    'recipient': message.recipient,
                    'message_type': message.message_type.value,
                    'content': message.content,
                    'timestamp': message.timestamp,
                    'priority': message.priority
                })
            )

            logger.debug(f"[A2A] 发送消息: {self.agent_id} -> {recipient}")
            return True

        except Exception as e:
            logger.error(f"[A2A] 发送失败: {e}")
            return False

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[A2AMessage], Any]
    ):
        """
        注册消息处理器

        Args:
            message_type: 消息类型
            handler: 处理函数
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []

        self.message_handlers[message_type].append(handler)
        logger.debug(f"[A2A] 注册处理器: {message_type.value}")

    async def start_listening(self):
        """开始监听消息"""
        if not self._pubsub:
            logger.warning("[A2A] 未连接，无法监听")
            return

        async with self._pubsub as pubsub:
            await self._start_heartbeat()

            logger.info(f"[A2A] 开始监听: {self.channel}")

            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self._process_message(message['data'])

    async def _process_message(self, data: str):
        """处理接收到的消息"""
        try:
            # 解析消息
            message_dict = json.loads(data)

            # 过滤自己发送的消息
            sender = message_dict.get('sender', '')
            if sender == self.agent_id:
                return

            # 创建消息对象
            message = A2AMessage(
                message_id=message_dict.get('message_id', ''),
                sender=sender,
                recipient=message_dict.get('recipient'),
                message_type=MessageType(message_dict.get('message_type', 'coordination')),
                content=message_dict.get('content', {}),
                timestamp=message_dict.get('timestamp', time.time()),
                priority=message_dict.get('priority', 0)
            )

            # 检查是否是目标接收者
            if message.recipient and message.recipient != self.agent_id:
                return

            # 调用处理器
            handlers = self.message_handlers.get(message.message_type, [])
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"[A2A] 处理器失败: {e}")

        except Exception as e:
            logger.error(f"[A2A] 处理消息失败: {e}")

    async def _start_heartbeat(self):
        """启动心跳"""
        while True:
            await asyncio.sleep(self.heartbeat_interval)

            # 发送心跳
            await self.broadcast_message(
                MessageType.HEARTBEAT,
                content={'agent_id': self.agent_id}
            )

    async def get_online_agents(self, timeout: float = 5.0) -> Set[str]:
        """
        获取在线Agent列表

        Args:
            timeout: 超时时间

        Returns:
            在线Agent集合
        """
        try:
            # 发送状态查询
            await self.broadcast_message(
                MessageType.STATUS_UPDATE,
                content={'query': 'who_is_online'}
            )

            # 等待响应
            await asyncio.sleep(timeout)

            return self.known_agents

        except Exception as e:
            logger.error(f"[A2A] 获取在线Agent失败: {e}")
            return set()

    def _generate_message_id(self) -> str:
        """生成消息ID"""
        import uuid
        return f"{self.agent_id}_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'agent_id': self.agent_id,
            'channel': self.channel,
            'connected': self._redis is not None,
            'known_agents': len(self.known_agents),
            'registered_handlers': len(self.message_handlers),
            'handlers_by_type': {
                mt.value: len(handlers)
                for mt, handlers in self.message_handlers.items()
            }
        }
