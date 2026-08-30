"""
社交工具基类

所有社交平台工具的基类，提供统一的接口和功能。
支持跨端共享，所有弥娅实例都可以使用。
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SocialBase(ABC):
    """社交工具基类"""

    def __init__(self, platform_type: str):
        """
        初始化社交工具

        Args:
            platform_type: 平台类型 ('qq' | 'wechat' | 'discord' | 'desktop')
        """
        self.platform_type = platform_type
        self.logger = logging.getLogger(f"SocialBase.{platform_type}")

    @abstractmethod
    async def send_message(self, target: str, message: str) -> Dict[str, Any]:
        """
        发送消息

        Args:
            target: 目标（用户ID/群组ID）
            message: 消息内容

        Returns:
            发送结果
        """
        pass

    @abstractmethod
    async def send_image(self, target: str, image_path: str) -> Dict[str, Any]:
        """
        发送图片

        Args:
            target: 目标（用户ID/群组ID）
            image_path: 图片路径

        Returns:
            发送结果
        """
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            用户信息
        """
        pass

    async def like_message(self, msg_id: str) -> Dict[str, Any]:
        """
        点赞消息（默认实现，子类可覆盖）

        Args:
            msg_id: 消息ID

        Returns:
            操作结果
        """
        result = {
            "success": False,
            "message": "点赞功能未实现",
            "platform": self.platform_type,
            "msg_id": msg_id,
            "timestamp": datetime.now().isoformat(),
        }
        self.logger.warning(f"点赞功能未实现: {msg_id}")
        return result

    async def react_message(self, msg_id: str, emoji: str) -> Dict[str, Any]:
        """
        消息表情反应

        Args:
            msg_id: 消息ID
            emoji: 表情符号

        Returns:
            操作结果
        """
        result = {
            "success": False,
            "message": "表情反应功能未实现",
            "platform": self.platform_type,
            "msg_id": msg_id,
            "emoji": emoji,
            "timestamp": datetime.now().isoformat(),
        }
        self.logger.warning(f"表情反应功能未实现: {msg_id}")
        return result

    async def get_message_history(self, target: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取消息历史

        Args:
            target: 目标（用户ID/群组ID）
            limit: 消息数量限制

        Returns:
            消息列表
        """
        self.logger.warning(f"消息历史功能未实现: {target}")
        return []

    async def forward_message(self, msg_id: str, target: str) -> Dict[str, Any]:
        """
        转发消息

        Args:
            msg_id: 消息ID
            target: 目标（用户ID/群组ID）

        Returns:
            转发结果
        """
        result = {
            "success": False,
            "message": "消息转发功能未实现",
            "platform": self.platform_type,
            "msg_id": msg_id,
            "target": target,
            "timestamp": datetime.now().isoformat(),
        }
        self.logger.warning(f"消息转发功能未实现: {msg_id}")
        return result

    def get_platform_info(self) -> Dict[str, Any]:
        """
        获取平台信息

        Returns:
            平台信息
        """
        return {
            "platform": self.platform_type,
            "type": self.__class__.__name__,
            "features": [
                "send_message",
                "send_image",
                "get_user_info",
                "like_message",
                "react_message",
            ],
        }

    def _validate_target(self, target: str) -> bool:
        """
        验证目标ID

        Args:
            target: 目标ID

        Returns:
            是否有效
        """
        return bool(target and isinstance(target, str))

    def _validate_message(self, message: str) -> bool:
        """
        验证消息内容

        Args:
            message: 消息内容

        Returns:
            是否有效
        """
        return bool(message and isinstance(message, str))

    async def _handle_error(self, error: Exception, operation: str, **kwargs) -> Dict[str, Any]:
        """
        处理错误

        Args:
            error: 异常对象
            operation: 操作名称
            **kwargs: 额外参数

        Returns:
            错误结果
        """
        self.logger.error(f"{operation} 失败: {error}", exc_info=True)

        return {
            "success": False,
            "message": str(error),
            "operation": operation,
            "platform": self.platform_type,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
