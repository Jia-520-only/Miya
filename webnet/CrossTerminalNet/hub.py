"""
跨端互联核心Hub

功能：
1. 消息转发 - QQ→桌面/终端/网页
2. 跨端控制 - 一个端发送命令，另一个端执行
3. 状态同步 - 多端配置实时同步
4. 设备发现 - 局域网设备感知
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TerminalType(Enum):
    """终端类型"""
    QQ = "qq"
    WEB = "web"
    DESKTOP = "desktop"
    TERMINAL = "terminal"
    SERVER = "server"


# 导出供外部使用
TERMINAL_TYPE_DESKTOP = TerminalType.DESKTOP


@dataclass
class CrossTerminalMessage:
    """跨端消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: TerminalType = TerminalType.QQ
    source_id: str = ""
    target_type: Optional[TerminalType] = None  # None 表示广播
    target_id: str = ""
    message_type: str = "text"  # text, command, notification, sync
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    device_type: TerminalType
    device_name: str
    online: bool = True
    last_seen: float = 0
    ip_address: str = ""


class CrossTerminalHub:
    """
    跨端互联Hub

    使用Redis Pub/Sub实现跨端通信
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._running = False
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._devices: Dict[str, DeviceInfo] = {}
        self._state_cache: Dict[str, Any] = {}
        self._subscribe_task: Optional[asyncio.Task] = None

        # 消息存储（用于轮询）
        self._desktop_messages: List[Dict[str, Any]] = []
        self._max_messages = 100

        # 频道名称
        self.CHANNEL_PREFIX = "miya:cross:"
        self.CHANNEL_MESSAGE = f"{self.CHANNEL_PREFIX}message"
        self.CHANNEL_STATE = f"{self.CHANNEL_PREFIX}state"
        self.CHANNEL_DISCOVER = f"{self.CHANNEL_PREFIX}discover"

        # 设备注册
        self._device_id = f"server_{uuid.uuid4().hex[:8]}"

    async def start(self):
        """启动Hub"""
        if self._running:
            return

        self._running = True

        # 启动订阅任务
        if self.redis:
            self._subscribe_task = asyncio.create_task(self._subscribe_loop())

        # 广播设备上线
        await self._broadcast_device_online()

        logger.info("[CrossTerminalHub] 跨端Hub已启动")

    async def stop(self):
        """停止Hub"""
        self._running = False

        # 广播设备离线
        await self._broadcast_device_offline()

        if self._subscribe_task:
            self._subscribe_task.cancel()
            try:
                await self._subscribe_task
            except asyncio.CancelledError:
                pass

        logger.info("[CrossTerminalHub] 跨端Hub已停止")

    async def _subscribe_loop(self):
        """订阅消息循环"""
        if not self.redis:
            return

        try:
            async for message in self.redis.subscribe(self.CHANNEL_MESSAGE):
                if not self._running:
                    break
                if message:
                    try:
                        data = json.loads(message) if isinstance(message, str) else message
                        await self._handle_message(data)
                    except Exception as e:
                        logger.error(f"[CrossTerminalHub] 处理消息失败: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[CrossTerminalHub] 订阅循环异常: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """处理收到的跨端消息"""
        try:
            msg = CrossTerminalMessage(
                id=data.get('id', str(uuid.uuid4())),
                source_type=TerminalType(data.get('source_type', 'qq')),
                source_id=data.get('source_id', ''),
                target_type=TerminalType(data.get('target_type')) if data.get('target_type') else None,
                target_id=data.get('target_id', ''),
                message_type=data.get('message_type', 'text'),
                content=data.get('content', ''),
                metadata=data.get('metadata', {}),
                timestamp=data.get('timestamp', datetime.now().timestamp())
            )

            # 存储消息供桌面端轮询
            target = data.get('target_type')
            if target is None or target == 'desktop':
                self._desktop_messages.append(data)
                # 限制消息数量
                if len(self._desktop_messages) > self._max_messages:
                    self._desktop_messages = self._desktop_messages[-self._max_messages:]

            # 触发消息处理器
            handlers = self._message_handlers.get(msg.message_type, [])
            for handler in handlers:
                try:
                    await handler(msg)
                except Exception as e:
                    logger.error(f"[CrossTerminalHub] 消息处理器异常: {e}")

            # 放入订阅队列
            for queue in self._subscribers.values():
                await queue.put(msg)

        except Exception as e:
            logger.error(f"[CrossTerminalHub] 解析消息失败: {e}")

    async def publish_message(
        self,
        content: str,
        message_type: str = "text",
        source_type: TerminalType = TerminalType.QQ,
        source_id: str = "",
        target_type: Optional[TerminalType] = None,
        target_id: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """发布跨端消息"""
        message = CrossTerminalMessage(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )

        data = {
            'id': message.id,
            'source_type': message.source_type.value,
            'source_id': message.source_id,
            'target_type': message.target_type.value if message.target_type else None,
            'target_id': message.target_id,
            'message_type': message.message_type,
            'content': message.content,
            'metadata': message.metadata,
            'timestamp': message.timestamp
        }

        # 存储消息供桌面端轮询
        if target_type is None or target_type == TerminalType.DESKTOP:
            self._desktop_messages.append(data)
            if len(self._desktop_messages) > self._max_messages:
                self._desktop_messages = self._desktop_messages[-self._max_messages:]

        if self.redis:
            await self.redis.publish(self.CHANNEL_MESSAGE, data)

        # 本地也处理（如果是本机发往本机）
        await self._handle_message(data)

        logger.info(f"[CrossTerminalHub] 发布消息: {message_type} -> {target_type}")
        return message.id

    # ========== 消息转发功能 ==========

    async def send_to_desktop(
        self,
        content: str,
        source_type: TerminalType = TerminalType.QQ,
        source_id: str = "",
        notification: bool = False
    ) -> str:
        """发送消息到桌面端"""
        return await self.publish_message(
            content=content,
            message_type="notification" if notification else "text",
            source_type=source_type,
            source_id=source_id,
            target_type=TerminalType.DESKTOP
        )

    async def send_to_qq(
        self,
        content: str,
        target_qq: str = "",
        source_type: TerminalType = TerminalType.DESKTOP,
        source_id: str = ""
    ) -> str:
        """发送消息到QQ端"""
        return await self.publish_message(
            content=content,
            message_type="text",
            source_type=source_type,
            source_id=source_id,
            target_type=TerminalType.QQ,
            target_id=target_qq
        )

    async def send_to_terminal(
        self,
        content: str,
        source_type: TerminalType = TerminalType.QQ,
        source_id: str = ""
    ) -> str:
        """发送消息到终端"""
        return await self.publish_message(
            content=content,
            message_type="text",
            source_type=source_type,
            source_id=source_id,
            target_type=TerminalType.TERMINAL
        )

    async def send_to_web(
        self,
        content: str,
        source_type: TerminalType = TerminalType.DESKTOP,
        source_id: str = ""
    ) -> str:
        """发送消息到Web端"""
        return await self.publish_message(
            content=content,
            message_type="text",
            source_type=source_type,
            source_id=source_id,
            target_type=TerminalType.WEB
        )

    # ========== 跨端控制功能 ==========

    async def send_command(
        self,
        command: str,
        target_type: TerminalType,
        source_type: TerminalType = TerminalType.QQ,
        source_id: str = ""
    ) -> str:
        """发送命令到指定终端执行"""
        return await self.publish_message(
            content=command,
            message_type="command",
            source_type=source_type,
            source_id=source_id,
            target_type=target_type
        )

    # ========== 状态同步功能 ==========

    async def set_state(self, key: str, value: Any):
        """设置状态（广播到所有端）"""
        self._state_cache[key] = value

        if self.redis:
            await self.redis.publish(self.CHANNEL_STATE, {
                'key': key,
                'value': value,
                'timestamp': datetime.now().timestamp()
            })

        logger.info(f"[CrossTerminalHub] 状态同步: {key}")

    async def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self._state_cache.get(key, default)

    # ========== 设备发现功能 ==========

    async def _broadcast_device_online(self):
        """广播设备上线"""
        if not self.redis:
            return

        device_info = {
            'device_id': self._device_id,
            'device_type': 'server',
            'action': 'online',
            'timestamp': datetime.now().timestamp()
        }
        await self.redis.publish(self.CHANNEL_DISCOVER, device_info)

    async def _broadcast_device_offline(self):
        """广播设备离线"""
        if not self.redis:
            return

        device_info = {
            'device_id': self._device_id,
            'device_type': 'server',
            'action': 'offline',
            'timestamp': datetime.now().timestamp()
        }
        await self.redis.publish(self.CHANNEL_DISCOVER, device_info)

    async def get_online_devices(self) -> List[DeviceInfo]:
        """获取在线设备列表"""
        return list(self._devices.values())

    # ========== 订阅功能 ==========

    def subscribe(self, terminal_type: TerminalType) -> asyncio.Queue:
        """订阅指定终端的消息"""
        queue = asyncio.Queue()
        self._subscribers[terminal_type.value] = queue
        return queue

    def unsubscribe(self, terminal_type: TerminalType):
        """取消订阅"""
        self._subscribers.pop(terminal_type.value, None)

    def add_message_handler(self, message_type: str, handler: Callable):
        """添加消息处理器"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    # ========== WebSocket支持 ==========

    def get_server_device_id(self) -> str:
        """获取服务器设备ID"""
        return self._device_id


# 全局实例
_cross_terminal_hub: Optional[CrossTerminalHub] = None


def get_cross_terminal_hub() -> CrossTerminalHub:
    """获取跨端Hub实例"""
    global _cross_terminal_hub
    if _cross_terminal_hub is None:
        _cross_terminal_hub = CrossTerminalHub()
    return _cross_terminal_hub
