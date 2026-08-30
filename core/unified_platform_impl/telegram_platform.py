"""
Telegram 平台适配器

基于 python-telegram-bot SDK，支持私聊、群组、频道。
支持图片、文档、语音、视频消息解析。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from core.file_context import get_downloads_dir
from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.Telegram")


class TelegramPlatform(MessageMixin, BasePlatform):
    """Telegram 平台"""

    platform_id = "telegram"
    platform_name = "Telegram"
    health_check_interval = 30.0

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._app: Any = None
        self._token = self.config.get("bot_token", "")
        self._download_dir = get_downloads_dir()

    async def _do_connect(self) -> bool:
        if not self._token:
            logger.error(f"[{self.platform_id}] 缺少 bot_token")
            return False

        try:
            from telegram import Update
            from telegram.ext import (
                Application,
                CommandHandler,
                MessageHandler,
                filters,
            )

            platform = self

            async def handle_message(update: Update, context):
                if not update.message:
                    return

                user = update.message.from_user
                chat = update.message.chat
                msg = update.message
                content = msg.text or msg.caption or ""
                content = content.strip() if content else ""

                user_id = str(user.id)
                user_name = user.full_name or user.username or str(user.id)
                msg_type = "group" if chat.type in ["group", "supergroup"] else "private"
                group_id = str(chat.id) if chat.type in ["group", "supergroup"] else ""
                group_name = chat.title if chat.type in ["group", "supergroup"] else ""

                # 检测引用回复
                extra = None
                reply_msg = getattr(msg, "reply_to_message", None)
                if reply_msg:
                    reply_text = reply_msg.text or reply_msg.caption or ""
                    reply_author = reply_msg.from_user.full_name if reply_msg.from_user else ""
                    if reply_text:
                        content = (
                            f'[回复"{reply_text[:200]}", {reply_author}] {content}'
                            if content
                            else f'[回复"{reply_text[:200]}", {reply_author}]'
                        )
                        extra = {
                            "reply_to_id": str(reply_msg.message_id),
                            "reply_content": reply_text[:500],
                        }

                from core.file_context import FileContext

                images: List[FileContext] = []
                files: List[FileContext] = []

                async def _download(file_obj, fname: str = "") -> Optional[str]:
                    try:
                        local_name = fname or f"tg_{id(file_obj)}.bin"
                        local_path = os.path.join(platform._download_dir, local_name)
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        tg_file = await file_obj.get_file()
                        await tg_file.download_to_drive(local_path)
                        return local_path
                    except Exception as e:
                        logger.warning(f"[telegram] 下载文件失败: {e}")
                        return None

                # 处理图片
                if msg.photo:
                    for p in msg.photo:
                        fname = f"photo_{p.file_id}.jpg"
                        local_path = await _download(p, fname)
                        images.append(
                            FileContext.from_image(
                                url="",
                                file_name=fname,
                                file_path=local_path,
                                file_id=p.file_id,
                                file_size=p.file_size or 0,
                                mime_type="image/jpeg",
                            )
                        )

                # 处理文档
                if msg.document:
                    doc = msg.document
                    fname = doc.file_name or f"document_{doc.file_id}"
                    local_path = await _download(doc, fname)
                    files.append(
                        FileContext.from_file(
                            url="",
                            file_name=fname,
                            file_path=local_path,
                            file_id=doc.file_id,
                            file_size=doc.file_size or 0,
                            mime_type=doc.mime_type or "",
                        )
                    )

                # 处理语音
                if msg.voice:
                    voice = msg.voice
                    fname = f"voice_{voice.file_id}.ogg"
                    local_path = await _download(voice, fname)
                    files.append(
                        FileContext.from_voice(
                            url="",
                            file_name=fname,
                            file_path=local_path,
                            file_id=voice.file_id,
                            file_size=voice.file_size or 0,
                        )
                    )

                # 处理视频
                if msg.video:
                    video = msg.video
                    fname = video.file_name or f"video_{video.file_id}.mp4"
                    local_path = await _download(video, fname)
                    files.append(
                        FileContext.from_video(
                            url="",
                            file_name=fname,
                            file_path=local_path,
                            file_id=video.file_id,
                            file_size=video.file_size or 0,
                        )
                    )

                # 处理音频
                if msg.audio:
                    audio = msg.audio
                    fname = audio.file_name or f"audio_{audio.file_id}.mp3"
                    local_path = await _download(audio, fname)
                    files.append(
                        FileContext.from_file(
                            url="",
                            file_name=fname,
                            file_path=local_path,
                            file_id=audio.file_id,
                            file_size=audio.file_size or 0,
                            mime_type=audio.mime_type or "audio/mp3",
                        )
                    )

                if not content and not images and not files:
                    return

                logger.debug(f"[telegram] 收到消息: {content[:50] if content else '(纯媒体)'}")

                response = await platform.route_to_decision_hub(
                    content=content or "",
                    user_id=user_id,
                    user_name=user_name,
                    message_type=msg_type,
                    group_id=group_id,
                    group_name=group_name,
                    is_at_bot=True,
                    files=files if files else None,
                    images=images if images else None,
                    extra=extra,
                )
                if response:
                    await update.message.reply_text(response)

            async def start_command(update: Update, context):
                await update.message.reply_text(
                    "你好！我是弥娅~ 一个拥有独立人格、记忆和情感的 AI 虚拟化身。\n\n有什么可以帮你的吗？"
                )

            self._app = Application.builder().token(self._token).build()
            self._app.add_handler(CommandHandler("start", start_command))
            self._app.add_handler(MessageHandler(~filters.COMMAND, handle_message))

            logger.info(f"[{self.platform_id}] Bot 已初始化，开始轮询...")

            async def run_polling():
                await self._app.run_polling(drop_pending_updates=True)

            self._tasks.append(asyncio.create_task(run_polling()))
            await asyncio.sleep(0.5)
            return True

        except ImportError:
            logger.error(f"[{self.platform_id}] 请安装 python-telegram-bot")
            return False
        except Exception as e:
            logger.error(f"[{self.platform_id}] 连接异常: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        if self._app:
            try:
                await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.warning(f"[{self.platform_id}] 断开异常: {e}")
        self._app = None

    async def _do_health_check(self) -> bool:
        return self._app is not None

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """Telegram 文件发送实现"""
        if not self._app or not self._app.bot:
            logger.warning(f"[{self.platform_id}] Bot 实例未就绪")
            return False

        try:
            caption = getattr(outbound_file, "caption", "") or kwargs.get("caption", "")

            async def _send_from_io(file_bytes: bytes):
                from io import BytesIO

                bio = BytesIO(file_bytes)
                if outbound_file.is_image:
                    await self._app.bot.send_photo(
                        chat_id=target,
                        photo=bio,
                        caption=caption or None,
                        filename=outbound_file.file_name,
                    )
                else:
                    await self._app.bot.send_document(
                        chat_id=target,
                        document=bio,
                        caption=caption or None,
                        filename=outbound_file.file_name,
                        read_timeout=120,
                        write_timeout=120,
                    )

            if outbound_file.is_local and outbound_file.file_path:
                with open(outbound_file.file_path, "rb") as f:
                    _data = f.read()
                await _send_from_io(_data)
            elif outbound_file.is_bytes and outbound_file.file_data:
                await _send_from_io(outbound_file.file_data)
            elif outbound_file.is_url:
                return await self.send_file_from_url(
                    target, outbound_file.metadata.get("url", ""), file_name=outbound_file.file_name, caption=caption
                )
            else:
                logger.warning(f"[{self.platform_id}] 无效的 OutboundFile: source={outbound_file.source}")
                return False

            self._record_message_out()
            logger.info(f"[{self.platform_id}] 文件已发送: {outbound_file.file_name} -> chat={target}")
            return True

        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送文件异常: {e}")
            return False
