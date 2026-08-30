"""
Discord 平台适配器

基于 discord.py SDK，支持私聊、服务器频道。
支持附件解析：图片、文件等。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.Discord")


class DiscordPlatform(MessageMixin, BasePlatform):
    """Discord 平台"""

    platform_id = "discord"
    platform_name = "Discord"
    health_check_interval = 30.0

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._client: Any = None
        self._token = self.config.get("bot_token", "")

    async def _do_connect(self) -> bool:
        if not self._token:
            logger.error(f"[{self.platform_id}] 缺少 bot_token")
            return False

        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            self._client = discord.Client(intents=intents)
            platform = self

            @self._client.event
            async def on_ready():
                logger.info(f"[{platform.platform_id}] Bot 已上线: {platform._client.user}")

            @self._client.event
            async def on_message(message):
                if message.author == platform._client.user:
                    return

                content = message.content.strip() if message.content else ""
                user_id = str(message.author.id)
                user_name = str(message.author)
                msg_type = "group" if message.guild else "private"
                group_id = str(message.guild.id) if message.guild else ""
                group_name = str(message.guild.name) if message.guild else ""

                # 检测引用回复
                extra = {}
                if message.reference and message.reference.message_id:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        ref_content = ref_msg.content.strip() if ref_msg.content else ""
                        ref_author = str(ref_msg.author)
                        if ref_content:
                            content = f'[回复"{ref_content}", {ref_author}] {content}'
                            extra["reply_to_id"] = str(message.reference.message_id)
                            extra["reply_content"] = ref_content[:500]
                    except Exception:
                        pass

                from core.file_context import FileContext

                images: List[FileContext] = []
                files: List[FileContext] = []

                for attachment in message.attachments:
                    if not attachment.url:
                        continue
                    fname = attachment.filename or ""
                    fsize = attachment.size or 0
                    ctype = attachment.content_type or ""
                    furl = str(attachment.url)

                    if ctype and ctype.startswith("image/"):
                        images.append(
                            FileContext.from_image(
                                url=furl,
                                file_name=fname,
                                file_size=fsize,
                                mime_type=ctype,
                                file_id=str(attachment.id),
                                platform_attachment=attachment,
                            )
                        )
                    else:
                        files.append(
                            FileContext.from_file(
                                url=furl,
                                file_name=fname,
                                file_size=fsize,
                                mime_type=ctype,
                                file_id=str(attachment.id),
                                platform_attachment=attachment,
                            )
                        )

                if not content and not images and not files:
                    return

                logger.debug(f"[{platform.platform_id}] 收到消息: {content[:50] if content else '(纯附件)'}")

                response = await platform.route_to_decision_hub(
                    content=content,
                    user_id=user_id,
                    user_name=user_name,
                    message_type=msg_type,
                    group_id=group_id,
                    group_name=group_name,
                    is_at_bot=True,
                    files=files if files else None,
                    images=images if images else None,
                    extra=extra if extra else None,
                )
                if response:
                    await message.reply(response)

            async def start_client():
                await platform._client.start(platform._token)

            logger.info(f"[{platform.platform_id}] Bot 已初始化，正在连接...")
            self._tasks.append(asyncio.create_task(start_client()))
            await asyncio.sleep(1)
            return True

        except ImportError:
            logger.error(f"[{self.platform_id}] 请安装 discord.py")
            return False
        except Exception as e:
            logger.error(f"[{self.platform_id}] 连接异常: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"[{self.platform_id}] 断开异常: {e}")
        self._client = None

    async def _do_health_check(self) -> bool:
        return self._client is not None and hasattr(self._client, "is_ready")

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """Discord 文件发送实现"""
        if not self._client or not hasattr(self._client, "is_ready") or not self._client.is_ready():
            logger.warning(f"[{self.platform_id}] 客户端未就绪")
            return False

        try:
            import discord

            channel = self._client.get_channel(int(target))
            if not channel:
                try:
                    channel = await self._client.fetch_channel(int(target))
                except Exception:
                    pass
            if not channel:
                logger.warning(f"[{self.platform_id}] 无法获取频道: {target}")
                return False

            caption = getattr(outbound_file, "caption", "") or kwargs.get("caption", "")

            if outbound_file.is_local and outbound_file.file_path:
                with open(outbound_file.file_path, "rb") as f:
                    discord_file = discord.File(f, filename=outbound_file.file_name)
                    await channel.send(file=discord_file, content=caption or None)
            elif outbound_file.is_bytes and outbound_file.file_data:
                from io import BytesIO

                discord_file = discord.File(BytesIO(outbound_file.file_data), filename=outbound_file.file_name)
                await channel.send(file=discord_file, content=caption or None)
            elif outbound_file.is_url:
                return await self.send_file_from_url(
                    target, outbound_file.metadata.get("url", ""), file_name=outbound_file.file_name, caption=caption
                )
            else:
                logger.warning(f"[{self.platform_id}] 无效的 OutboundFile: source={outbound_file.source}")
                return False

            self._record_message_out()
            logger.info(f"[{self.platform_id}] 文件已发送: {outbound_file.file_name} -> channel={target}")
            return True

        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送文件异常: {e}")
            return False
