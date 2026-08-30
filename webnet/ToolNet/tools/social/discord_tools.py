"""
Discord工具 - 跨端共享

Discord平台交互工具，所有弥娅实例都可以使用。
支持消息发送、表情反应、角色管理等功能。
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .social_base import SocialBase

logger = logging.getLogger(__name__)


class DiscordTools(SocialBase):
    """Discord工具类"""

    def __init__(self, discord_client=None):
        """
        初始化Discord工具

        Args:
            discord_client: Discord客户端实例（可选）
        """
        super().__init__("discord")
        self.discord_client = discord_client

    async def send_message(self, target: str, message: str) -> Dict[str, Any]:
        """
        发送Discord消息

        Args:
            target: 频道ID或用户ID
            message: 消息内容

        Returns:
            发送结果
        """
        try:
            if not self._validate_target(target):
                raise ValueError("无效的目标ID")

            if not self._validate_message(message):
                raise ValueError("无效的消息内容")

            if self.discord_client:
                # 使用Discord客户端发送
                channel = self.discord_client.get_channel(int(target))
                if channel:
                    msg = await channel.send(message)

                    return {
                        "success": True,
                        "message": "消息发送成功",
                        "platform": "discord",
                        "target": target,
                        "message_id": str(msg.id),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    raise ValueError("频道不存在")
            else:
                # 模拟发送
                self.logger.info(f"[模拟] 发送Discord消息到 {target}: {message}")
                return {
                    "success": True,
                    "message": "消息发送成功（模拟模式）",
                    "platform": "discord",
                    "target": target,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "simulation",
                }

        except Exception as e:
            return await self._handle_error(e, "发送消息", target=target)

    async def send_image(self, target: str, image_path: str) -> Dict[str, Any]:
        """
        发送Discord图片

        Args:
            target: 频道ID
            image_path: 图片路径

        Returns:
            发送结果
        """
        try:
            if not self._validate_target(target):
                raise ValueError("无效的目标ID")

            if self.discord_client:
                channel = self.discord_client.get_channel(int(target))
                if channel:
                    with open(image_path, "rb") as f:
                        msg = await channel.send(file=f)

                    return {
                        "success": True,
                        "message": "图片发送成功",
                        "platform": "discord",
                        "target": target,
                        "message_id": str(msg.id),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    raise ValueError("频道不存在")
            else:
                self.logger.info(f"[模拟] 发送Discord图片到 {target}: {image_path}")
                return {
                    "success": True,
                    "message": "图片发送成功（模拟模式）",
                    "platform": "discord",
                    "target": target,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "simulation",
                }

        except Exception as e:
            return await self._handle_error(e, "发送图片", target=target)

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Discord用户信息

        Args:
            user_id: Discord用户ID

        Returns:
            用户信息
        """
        try:
            if self.discord_client:
                user = await self.discord_client.fetch_user(int(user_id))
                return {
                    "user_id": str(user.id),
                    "username": user.name,
                    "discriminator": user.discriminator,
                    "avatar": user.avatar,
                    "bot": user.bot,
                    "platform": "discord",
                }
            else:
                self.logger.info(f"[模拟] 获取Discord用户信息: {user_id}")
                return {"user_id": user_id, "username": f"User{user_id}", "platform": "discord", "mode": "simulation"}

        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}", exc_info=True)
            return None

    async def react_message(self, msg_id: str, emoji: str) -> Dict[str, Any]:
        """
        消息表情反应

        Args:
            msg_id: 消息ID
            emoji: 表情符号

        Returns:
            操作结果
        """
        try:
            if self.discord_client:
                channel = self.discord_client.get_channel(int(msg_id.split("-")[0]))
                if channel:
                    message = await channel.fetch_message(int(msg_id.split("-")[1]))
                    await message.add_reaction(emoji)

                    return {
                        "success": True,
                        "message": "表情反应添加成功",
                        "platform": "discord",
                        "msg_id": msg_id,
                        "emoji": emoji,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    raise ValueError("频道不存在")
            else:
                self.logger.info(f"[模拟] 添加表情反应: {msg_id} - {emoji}")
                return {
                    "success": True,
                    "message": "表情反应添加成功（模拟模式）",
                    "platform": "discord",
                    "msg_id": msg_id,
                    "emoji": emoji,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "simulation",
                }

        except Exception as e:
            return await self._handle_error(e, "添加表情反应", msg_id=msg_id, emoji=emoji)

    async def create_role(
        self, guild_id: str, name: str, color: int = 0x000000, permissions: int = 0
    ) -> Dict[str, Any]:
        """
        创建角色

        Args:
            guild_id: 服务器ID
            name: 角色名称
            color: 颜色（十六进制）
            permissions: 权限值

        Returns:
            操作结果
        """
        try:
            if self.discord_client:
                guild = self.discord_client.get_guild(int(guild_id))
                if guild:
                    role = await guild.create_role(name=name, color=color, permissions=permissions)

                    return {
                        "success": True,
                        "message": "角色创建成功",
                        "platform": "discord",
                        "guild_id": guild_id,
                        "role_id": str(role.id),
                        "role_name": name,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    raise ValueError("服务器不存在")
            else:
                self.logger.info(f"[模拟] 创建角色: {guild_id} - {name}")
                return {
                    "success": True,
                    "message": "角色创建成功（模拟模式）",
                    "platform": "discord",
                    "guild_id": guild_id,
                    "role_name": name,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "simulation",
                }

        except Exception as e:
            return await self._handle_error(e, "创建角色", guild_id=guild_id, name=name)

    async def kick_member(self, guild_id: str, user_id: str, reason: str = None) -> Dict[str, Any]:
        """
        踢出成员

        Args:
            guild_id: 服务器ID
            user_id: 用户ID
            reason: 原因

        Returns:
            操作结果
        """
        try:
            if self.discord_client:
                guild = self.discord_client.get_guild(int(guild_id))
                if guild:
                    member = await guild.fetch_member(int(user_id))
                    await member.kick(reason=reason)

                    return {
                        "success": True,
                        "message": "成员踢出成功",
                        "platform": "discord",
                        "guild_id": guild_id,
                        "user_id": user_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    raise ValueError("服务器不存在")
            else:
                self.logger.info(f"[模拟] 踢出成员: {guild_id} - {user_id}")
                return {
                    "success": True,
                    "message": "成员踢出成功（模拟模式）",
                    "platform": "discord",
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "simulation",
                }

        except Exception as e:
            return await self._handle_error(e, "踢出成员", guild_id=guild_id, user_id=user_id)
