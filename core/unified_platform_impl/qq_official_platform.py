"""
QQ 官方机器人平台 (从旧代码迁移)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Dict, List, Optional

from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.QQOfficial")


def _parse_attachments(msg: Any, file_category: str = "file") -> List[Any]:
    """解析 botpy Message 的附件为 FileContext 列表，并下载文件内容"""
    from core.file_context import FileContext

    result = []
    attachments = getattr(msg, "attachments", None)
    if not attachments:
        return result

    logger.info("[qqofficial] attachments: count=%d", len(attachments) if hasattr(attachments, "__len__") else 0)

    for att in attachments:
        ctype = getattr(att, "content_type", "") or ""
        url = getattr(att, "url", "") or ""
        fname = getattr(att, "filename", "") or ""
        fsize = getattr(att, "size", 0) or 0
        fid = getattr(att, "id", "") or ""

        if not url:
            continue

        # 下载文件内容
        file_data = _download_attachment_url(url)

        if file_category == "image" and ctype and ctype.startswith("image/"):
            fc = FileContext.from_image(
                url=url,
                file_name=fname or f"image_{fid}.jpg",
                file_id=fid,
                file_size=fsize,
                mime_type=ctype,
            )
        elif file_category == "file" and ctype and not ctype.startswith("image/"):
            fc = FileContext.from_file(
                url=url,
                file_name=fname,
                file_id=fid,
                file_size=fsize,
                mime_type=ctype,
            )
        elif file_category == "file" and not ctype and url:
            fc = FileContext.from_file(
                url=url,
                file_name=fname or f"file_{fid}.bin",
                file_id=fid,
                file_size=fsize,
            )
        else:
            continue

        if file_data:
            fc.file_data = file_data
            if not fsize:
                fc.file_size = len(file_data)
            fc.download_status = "done"
        result.append(fc)

    return result


def _download_attachment_url(url: str) -> Optional[bytes]:
    try:
        import requests

        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        logger.debug("[qqofficial] 附件下载失败: %s", e)
    return None


def _detect_qqofficial_reply(msg: Any) -> tuple:
    """检测 QQ Official 消息是否为引用回复，返回 (content_prefix, extra_dict)"""
    content_prefix = ""
    extra = {}

    msg_ref = getattr(msg, "message_reference", None)
    if msg_ref is None:
        return content_prefix, extra

    ref_msg_id = getattr(msg_ref, "message_id", None)
    if not ref_msg_id:
        return content_prefix, extra

    logger.info("[qqofficial] 检测到引用消息: ref_id=%s", ref_msg_id)
    content_prefix = f"[引用消息ID: {ref_msg_id}] "
    extra["reply_to_id"] = str(ref_msg_id)
    extra["reply_to_bot"] = False

    return content_prefix, extra


class QQOfficialPlatform(MessageMixin, BasePlatform):
    """QQ 官方机器人平台"""

    platform_id = "qqofficial"
    platform_name = "QQ 官方机器人"
    health_check_interval = 30.0

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._bot_client = None
        self._bot_task: Optional[asyncio.Task] = None
        self._msg_seq_counter = 0

        self.appid = self.config.get("appid", "")
        self.secret = self.config.get("secret", "")
        self.bot_qq = self.config.get("bot_qq", "")
        self.sandbox = self.config.get("sandbox", False)

    def _next_msg_seq(self) -> int:
        self._msg_seq_counter += 1
        return self._msg_seq_counter

    async def send_private_message(self, user_id: int, message: str) -> bool:
        """发送私聊消息（主动）"""
        if not self._bot_client:
            return False
        try:
            await self._bot_client.api.post_c2c_message(
                openid=str(user_id),
                msg_type=0,
                content=message,
                msg_seq=self._next_msg_seq(),
            )
            logger.info(f"[qqofficial] 主动私聊消息 -> {user_id}: {message[:30]}")
            return True
        except Exception as e:
            logger.error(f"[qqofficial] 主动私聊消息失败: {e}")
            return False

    async def send_group_message(self, group_id: int, message: str) -> bool:
        """发送群聊消息（主动）"""
        if not self._bot_client:
            return False
        try:
            await self._bot_client.api.post_group_message(
                group_openid=str(group_id),
                msg_type=0,
                content=message,
                msg_seq=self._next_msg_seq(),
            )
            logger.info(f"[qqofficial] 主动群聊消息 -> {group_id}: {message[:30]}")
            return True
        except Exception as e:
            logger.error(f"[qqofficial] 主动群聊消息失败: {e}")
            return False

    async def _do_connect(self) -> bool:
        if not self.appid or not self.secret:
            logger.error(f"[{self.platform_id}] 缺少 appid 或 secret")
            return False

        try:
            import botpy
            from botpy.flags import Intents

            platform = self

            intents = Intents(
                public_messages=True,
                public_guild_messages=True,
                direct_message=True,
            )

            class _MiyaBotClient(botpy.Client):
                async def on_ready(self):
                    logger.info(f"[qqofficial] Bot 已上线 (QQ: {platform.bot_qq})")

                async def on_at_message_create(self, message):
                    await _do_handle(message, "channel")

                async def on_group_at_message_create(self, message):
                    await _do_handle_group(message)

                async def on_direct_message_create(self, message):
                    await _do_handle(message, "private")

                async def on_c2c_message_create(self, message):
                    await _do_handle(message, "c2c")

            async def _do_handle(msg, msg_type):
                try:
                    author = msg.author
                    user_id = str(
                        getattr(author, "user_openid", None)
                        or getattr(author, "member_openid", None)
                        or getattr(author, "id", None)
                        or ""
                    )
                    user_name = getattr(author, "username", "") or getattr(author, "nick", "") or user_id
                    content = msg.content.strip() if msg.content else ""

                    # 解析附件/图片
                    from core.file_context import FileContext

                    images = _parse_attachments(msg, "image")
                    files = _parse_attachments(msg, "file")

                    # 检测引用回复
                    reply_prefix, reply_extra = _detect_qqofficial_reply(msg)
                    if reply_prefix:
                        content = reply_prefix + (content or "")

                    if not content and not images and not files:
                        return

                    extra = reply_extra if reply_extra else None

                    response = await platform.route_to_decision_hub(
                        content=content,
                        user_id=user_id,
                        user_name=user_name,
                        message_type=("c2c" if msg_type == "c2c" else "private"),
                        is_at_bot=True,
                        images=images if images else None,
                        files=files if files else None,
                        extra=extra,
                    )
                    resp_text = response or ""
                    if resp_text:
                        voice_sent = await platform._tts_process_and_send_qqofficial(resp_text, msg, None)
                        if not voice_sent:
                            for chunk in platform._split_message(resp_text, 500):
                                await msg.reply(
                                    content=chunk,
                                    msg_seq=platform._next_msg_seq(),
                                )
                except Exception as e:
                    logger.error(f"[qqofficial] 消息处理异常: {e}")

            async def _do_handle_group(msg):
                try:
                    user_id = str(msg.author.member_openid)
                    user_name = getattr(msg.author, "username", "") or getattr(msg.author, "nick", "") or user_id
                    content = msg.content.strip() if msg.content else ""
                    group_id = msg.group_openid

                    # 解析附件/图片
                    from core.file_context import FileContext

                    images = _parse_attachments(msg, "image")
                    files = _parse_attachments(msg, "file")

                    # 检测引用回复
                    reply_prefix, reply_extra = _detect_qqofficial_reply(msg)
                    if reply_prefix:
                        content = reply_prefix + (content or "")

                    if not content and not images and not files:
                        return

                    extra = reply_extra if reply_extra else None

                    response = await platform.route_to_decision_hub(
                        content=content,
                        user_id=user_id,
                        user_name=user_name,
                        message_type="group",
                        group_id=group_id,
                        is_at_bot=True,
                        images=images if images else None,
                        files=files if files else None,
                        extra=extra,
                    )
                    resp_text = response or ""
                    if resp_text:
                        voice_sent = await platform._tts_process_and_send_qqofficial(resp_text, None, msg)
                        if not voice_sent:
                            for chunk in platform._split_message(resp_text, 500):
                                await msg._api.post_group_message(
                                    group_openid=group_id,
                                    msg_type=0,
                                    msg_id=msg.id,
                                    content=chunk,
                                    msg_seq=platform._next_msg_seq(),
                                )
                            await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"[qqofficial] 群消息处理异常: {e}")

            self._bot_client = _MiyaBotClient(intents=intents, is_sandbox=self.sandbox)

            async def run_bot():
                params = {"appid": self.appid, "secret": self.secret}
                if self.sandbox:
                    params["sandbox"] = True
                try:
                    await self._bot_client.start(**params)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[qqofficial] Bot 运行异常: {e}")

            self._bot_task = asyncio.create_task(run_bot())
            await asyncio.sleep(0.5)
            return True

        except ImportError:
            logger.error(f"[{self.platform_id}] 请安装 qq-botpy")
            return False
        except Exception as e:
            logger.error(f"[{self.platform_id}] 连接异常: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        if self._bot_task and not self._bot_task.done():
            self._bot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bot_task
        self._bot_client = None
        self._bot_task = None

    async def _do_health_check(self) -> bool:
        if not self._bot_task:
            return False
        return not self._bot_task.done()

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """QQ Official 文件发送实现"""
        if not self._bot_client:
            logger.warning(f"[{self.platform_id}] Bot 客户端未就绪")
            return False

        try:
            import os as _os

            msg_type = kwargs.get("message_type", "private")
            caption = getattr(outbound_file, "caption", "") or kwargs.get("caption", "")

            if outbound_file.is_local and outbound_file.file_path:
                file_path = outbound_file.file_path
                if not _os.path.exists(file_path):
                    logger.warning(f"[{self.platform_id}] 文件不存在: {file_path}")
                    return False
            elif outbound_file.is_bytes and outbound_file.file_data:
                import tempfile

                suffix = outbound_file.extension or ""
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{suffix}" if suffix else "", prefix="miya_qo_send_"
                ) as tmp:
                    tmp.write(outbound_file.file_data)
                    file_path = tmp.name
                try:
                    result = await self._do_send_qqofficial_file(
                        file_path, outbound_file.file_name, caption, msg_type, target
                    )
                finally:
                    try:
                        _os.unlink(file_path)
                    except OSError:
                        pass
                return result
            elif outbound_file.is_url:
                return await self.send_file_from_url(
                    target,
                    outbound_file.metadata.get("url", ""),
                    file_name=outbound_file.file_name,
                    caption=caption,
                    message_type=msg_type,
                )
            else:
                logger.warning(f"[{self.platform_id}] 无效的 OutboundFile")
                return False

            result = await self._do_send_qqofficial_file(file_path, outbound_file.file_name, caption, msg_type, target)
            return result

        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送文件异常: {e}")
            return False

    async def _do_send_qqofficial_file(
        self, file_path: str, file_name: str, caption: str, msg_type: str, target: str
    ) -> bool:
        """QQ Official 底层文件发送"""
        import os as _os

        file_uri = f"file:///{file_path.replace(_os.sep, '/')}"
        is_image = _os.path.splitext(file_path)[1].lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        file_type = 1 if is_image else 4

        peer_id = self._resolve_qqofficial_openid(target)

        if not is_image:
            logger.warning(f"[{self.platform_id}] QQ 官方 bot API 不支持通用文件发送（仅支持 image/video/voice）")
            return False

        try:
            if msg_type == "private":
                await self._bot_client.api.post_c2c_file(
                    openid=peer_id,
                    file_type=file_type,
                    url=file_uri,
                )
            else:
                await self._bot_client.api.post_group_file(
                    group_openid=peer_id,
                    file_type=file_type,
                    url=file_uri,
                )

            self._record_message_out()
            logger.info(f"[{self.platform_id}] 文件已发送: {file_name} -> {peer_id}")
            return True

        except AttributeError:
            logger.warning(f"[{self.platform_id}] botpy SDK 不支持 post_c2c_file/post_group_file API")
            return False
        except Exception as e:
            logger.error(f"[{self.platform_id}] 文件发送 API 调用失败: {e}")
            return False

    @staticmethod
    def _resolve_qqofficial_openid(target: str) -> str:
        """QQ 号 → QQ Official openid"""
        if not target or not target.isdigit():
            return target
        try:
            import json
            from pathlib import Path

            perms_path = Path("config/permissions.json")
            if perms_path.exists():
                perms = json.loads(perms_path.read_text(encoding="utf-8"))
                superadmins = perms.get("superadmins", {})
                for sa_info in superadmins.values():
                    ids = sa_info.get("ids", {})
                    qqofficial_ids = ids.get("qqofficial", [])
                    for qoid in qqofficial_ids:
                        qoid_str = str(qoid)
                        if qoid_str != target and qoid_str:
                            logger.info("[qqofficial] QQ %s → openid %s", target, qoid_str)
                            return qoid_str
        except Exception:
            pass
        return target

    async def _tts_process_and_send_qqofficial(self, text: str, private_msg=None, group_msg=None) -> bool:
        """QQ 官方平台的 TTS 处理：合成 → 发语音 → 本地播，返回是否已发语音"""
        audio_path, sent = await self._tts_process(text)
        if not sent or not audio_path:
            return False
        try:
            import os

            file_uri = f"file:///{audio_path.replace(os.sep, '/')}"
            if private_msg:
                await private_msg._api.post_c2c_file(
                    openid=getattr(private_msg.author, "member_openid", "")
                    or getattr(private_msg.author, "user_openid", ""),
                    file_type=3,
                    url=file_uri,
                )
            elif group_msg:
                await group_msg._api.post_group_file(
                    group_openid=group_msg.group_openid,
                    file_type=3,
                    url=file_uri,
                )
            logger.info("[qqofficial] 语音消息已发送")
        except Exception as e:
            logger.warning(f"[qqofficial] 语音发送失败: {e}，回退文字")
            return False
        import asyncio as _asyncio

        _asyncio.get_event_loop().call_later(
            30,
            lambda p=audio_path: __import__("os").unlink(p) if __import__("os").path.exists(p) else None,
        )
        return True
