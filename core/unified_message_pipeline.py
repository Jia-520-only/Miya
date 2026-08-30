"""
消息系统统一模块

统一 Miya mlink 消息系统和 AstrBot 平台消息系统
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageSource(Enum):
    """消息来源"""

    MIYA = "miya"
    ASTRBOT = "astrbot"
    QQ = "qq"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    DESKTOP = "desktop"


class MessageType(Enum):
    """消息类型"""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    SYSTEM = "system"


class MessageDirection(str, Enum):
    """消息方向"""

    INBOUND = "in"
    OUTBOUND = "out"


@dataclass
class UnifiedMessage:
    """统一消息格式"""

    id: str
    msg_type: MessageType
    content: str
    sender: str
    receiver: str
    source: MessageSource
    platform: str
    timestamp: datetime
    direction: MessageDirection = MessageDirection.INBOUND
    message_id: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedMessagePipeline:
    """
    统一消息处理管道

    功能：
    - 消息格式统一
    - 消息过滤和转换
    - 多平台适配
    """

    def __init__(self):
        self._parsers: Dict[MessageSource, Callable] = {}
        self._processors: List[Callable] = []
        self._handlers: Dict[MessageType, List[Callable]] = {}
        self._initialized = False

    async def initialize(self):
        """初始化消息管道"""
        logger.info("[UnifiedMessagePipeline] 初始化...")

        await self._register_parsers()
        await self._register_processors()
        await self._register_handlers()

        self._initialized = True
        logger.info("[UnifiedMessagePipeline] 初始化完成")

    async def _register_parsers(self):
        """注册消息解析器"""
        self._parsers = {
            MessageSource.MIYA: self._parse_miya_message,
            MessageSource.ASTRBOT: self._parse_astrbot_message,
            MessageSource.QQ: self._parse_qq_message,
            MessageSource.TELEGRAM: self._parse_telegram_message,
            MessageSource.DISCORD: self._parse_discord_message,
            MessageSource.DESKTOP: self._parse_desktop_message,
        }

    async def _register_processors(self):
        """注册消息处理器"""
        self._processors = [
            self._process_filter,
            self._process_transform,
            self._process_validate,
        ]

    async def _register_handlers(self):
        """注册消息类型处理器"""
        for msg_type in MessageType:
            self._handlers[msg_type] = []

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)

    async def process(self, raw_message: Any, source: MessageSource) -> UnifiedMessage:
        """处理消息"""
        try:
            parser = self._parsers.get(source)
            if not parser:
                logger.warning(f"[UnifiedMessagePipeline] 无解析器: {source}")
                return None

            message = await parser(raw_message)

            for processor in self._processors:
                message = await processor(message)
                if not message:
                    return None

            return message

        except Exception as e:
            logger.error(f"[UnifiedMessagePipeline] 消息处理失败: {e}")
            return None

    async def _parse_miya_message(self, raw: Any) -> UnifiedMessage:
        """解析Miya消息"""
        try:
            from mlink.message import Message as MiyaMessage

            if isinstance(raw, MiyaMessage):
                return UnifiedMessage(
                    id=getattr(raw, "msg_id", str(id(raw))),
                    msg_type=MessageType.TEXT,
                    content=getattr(raw, "content", ""),
                    sender=getattr(raw, "sender", ""),
                    receiver=getattr(raw, "receiver", ""),
                    source=MessageSource.MIYA,
                    platform=getattr(raw, "platform", "unknown"),
                    timestamp=getattr(raw, "timestamp", datetime.now()),
                    metadata=getattr(raw, "extra", {}),
                )

            return UnifiedMessage(
                id=str(id(raw)),
                msg_type=MessageType.TEXT,
                content=str(raw),
                sender="unknown",
                receiver="miya",
                source=MessageSource.MIYA,
                platform="unknown",
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"[UnifiedMessagePipeline] Miya消息解析失败: {e}")
            return None

    async def _parse_astrbot_message(self, raw: Any) -> UnifiedMessage:
        """解析AstrBot消息 (可选)"""
        try:
            from astrbot.core.platform.astr_message_event import AstrMessageEvent

            if isinstance(raw, AstrMessageEvent):
                return UnifiedMessage(
                    id=getattr(raw, "message_id", str(id(raw))),
                    msg_type=MessageType.TEXT,
                    content=getattr(raw, "message", ""),
                    sender=getattr(raw, "sender", ""),
                    receiver=getattr(raw, "robot_uin", ""),
                    source=MessageSource.ASTRBOT,
                    platform=getattr(raw, "platform", "unknown"),
                    timestamp=getattr(raw, "time", datetime.now()),
                    metadata={},
                )

            return UnifiedMessage(
                id=str(id(raw)),
                msg_type=MessageType.TEXT,
                content=str(raw),
                sender="unknown",
                receiver="astrbot",
                source=MessageSource.ASTRBOT,
                platform="unknown",
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"[UnifiedMessagePipeline] AstrBot消息解析失败: {e}")
            return None

    async def _parse_qq_message(self, raw: Any) -> UnifiedMessage:
        """解析QQ消息"""
        return UnifiedMessage(
            id=str(id(raw)),
            msg_type=MessageType.TEXT,
            content=str(raw),
            sender="qq_user",
            receiver="miya",
            source=MessageSource.QQ,
            platform="qq",
            timestamp=datetime.now(),
        )

    async def _parse_telegram_message(self, raw: Any) -> UnifiedMessage:
        """解析Telegram消息"""
        return UnifiedMessage(
            id=str(id(raw)),
            msg_type=MessageType.TEXT,
            content=str(raw),
            sender="telegram_user",
            receiver="miya",
            source=MessageSource.TELEGRAM,
            platform="telegram",
            timestamp=datetime.now(),
        )

    async def _parse_discord_message(self, raw: Any) -> UnifiedMessage:
        """解析Discord消息"""
        return UnifiedMessage(
            id=str(id(raw)),
            msg_type=MessageType.TEXT,
            content=str(raw),
            sender="discord_user",
            receiver="miya",
            source=MessageSource.DISCORD,
            platform="discord",
            timestamp=datetime.now(),
        )

    async def _parse_desktop_message(self, raw: Any) -> UnifiedMessage:
        """解析桌面端/手机端消息"""
        return UnifiedMessage(
            id=str(id(raw)),
            msg_type=MessageType.TEXT,
            content=str(raw),
            sender="desktop_user",
            receiver="miya",
            source=MessageSource.DESKTOP,
            platform="desktop",
            timestamp=datetime.now(),
        )

    async def _process_filter(self, message: UnifiedMessage) -> UnifiedMessage:
        """消息过滤"""
        if not message.content or message.content.strip() == "":
            return None
        return message

    async def _process_transform(self, message: UnifiedMessage) -> UnifiedMessage:
        """消息转换"""
        message.content = message.content.strip()
        return message

    async def _process_validate(self, message: UnifiedMessage) -> UnifiedMessage:
        """消息验证"""
        if len(message.content) > 10000:
            message.content = message.content[:10000]
        return message

    async def send(self, message: UnifiedMessage, target_platform: Optional[str] = None) -> Dict[str, Any]:
        """发送消息"""
        try:
            if message.source == MessageSource.MIYA:
                return await self._send_via_miya(message)
            elif message.source == MessageSource.ASTRBOT:
                return await self._send_via_astrbot(message)
            else:
                return await self._send_via_platform(message, target_platform)
        except Exception as e:
            logger.error(f"[UnifiedMessagePipeline] 发送失败: {e}")
            return {"success": False, "error": str(e)}

    async def _send_via_miya(self, message: UnifiedMessage) -> Dict[str, Any]:
        """通过Miya发送"""
        return {"success": True, "message": "Miya发送待实现"}

    async def _send_via_astrbot(self, message: UnifiedMessage) -> Dict[str, Any]:
        """通过AstrBot发送"""
        return {"success": True, "message": "AstrBot发送待实现"}

    async def _send_via_platform(self, message: UnifiedMessage, platform: Optional[str]) -> Dict[str, Any]:
        """通过平台发送"""
        return {"success": True, "message": f"发送到 {platform}"}


_unified_message_pipeline: Optional[UnifiedMessagePipeline] = None


def get_unified_message_pipeline() -> UnifiedMessagePipeline:
    """获取全局统一消息管道"""
    global _unified_message_pipeline
    if _unified_message_pipeline is None:
        _unified_message_pipeline = UnifiedMessagePipeline()
    return _unified_message_pipeline
