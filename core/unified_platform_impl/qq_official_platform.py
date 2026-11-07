"""
QQ 官方机器人平台 (从旧代码迁移)
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os
import re
from contextvars import ContextVar
from pathlib import Path
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

        # 分类后再下载，同一附件不会被图片/文件两个分支重复下载。
        file_data = _download_attachment_url(url)
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
    command_reply_via_response = True
    supports_channel_reaction = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._bot_client = None
        self._bot_task: Optional[asyncio.Task] = None
        self._msg_seq_counter = 0
        self._reply_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
            f"qqofficial_reply_{id(self)}", default=None
        )

        self.appid = self.config.get("appid", "")
        self.secret = self.config.get("secret", "")
        self.bot_qq = self.config.get("bot_qq", "")
        self.sandbox = self.config.get("sandbox", False)

    def _next_msg_seq(self) -> int:
        context = self._reply_context.get()
        if context is not None:
            context["seq"] += 1
            return context["seq"]
        self._msg_seq_counter += 1
        return self._msg_seq_counter

    async def set_channel_reaction(
        self, channel_id: str, message_id: str, emoji_id: str, emoji_type: int = 1
    ) -> bool:
        """添加频道消息表态；QQ 群和 C2C 不使用此接口。"""
        if not self._bot_client or emoji_type not in (1, 2):
            return False
        await self._bot_client.api.put_reaction(
            str(channel_id), str(message_id), emoji_type, str(emoji_id)
        )
        return True

    def _reply_params(self, target: str, message_type: str) -> Dict[str, Any]:
        context = self._reply_context.get()
        params = {}
        if context and context["target"] == str(target) and context["kind"] == message_type:
            if context["message_id"]:
                params["msg_id"] = context["message_id"]
        params["msg_seq"] = self._next_msg_seq()
        return params

    @staticmethod
    def _message_delivered(result: Any) -> bool:
        return bool(result.get("id")) if isinstance(result, dict) else bool(getattr(result, "id", None))

    async def send_private_message(self, user_id: int | str, message: str) -> bool:
        return await self._send_text(self._resolve_qqofficial_openid(str(user_id)), message, "c2c")

    async def send_group_message(self, group_id: int | str, message: str) -> bool:
        return await self._send_text(str(group_id), message, "group")

    async def _send_text(self, target: str, message: str, message_type: str) -> bool:
        if not self._bot_client:
            return False
        try:
            for chunk in self._split_long_line(message, 500):
                params = self._reply_params(target, message_type)
                if message_type == "group":
                    result = await self._bot_client.api.post_group_message(
                        group_openid=target, msg_type=0, content=chunk, **params
                    )
                else:
                    result = await self._bot_client.api.post_c2c_message(
                        openid=target, msg_type=0, content=chunk, **params
                    )
                if not self._message_delivered(result):
                    logger.warning("[qqofficial] 文本发送未返回消息回执")
                    return False
                self._record_message_out()
            return bool(message.strip())
        except Exception as e:
            logger.error("[qqofficial] 文本发送失败: %s", e)
            return False

    async def _handle_message(self, msg: Any, kind: str) -> None:
        """统一处理群聊、C2C、频道及频道私信，回复上下文按请求隔离。"""
        if msg is None or getattr(msg, "author", None) is None:
            return
        author = msg.author
        user_id = str(
            getattr(author, "member_openid", None)
            or getattr(author, "user_openid", None)
            or getattr(author, "id", None)
            or ""
        )
        if not user_id:
            return
        group_id = str(getattr(msg, "group_openid", "") or "")
        channel_id = str(getattr(msg, "channel_id", "") or "")
        target = group_id if kind == "group" else channel_id if kind == "channel" else user_id
        if not target:
            return
        token = self._reply_context.set({
            "kind": kind, "target": target, "message_id": str(getattr(msg, "id", "") or ""), "seq": 0
        })
        try:
            content = (getattr(msg, "content", "") or "").strip()
            if kind in {"group", "channel"}:
                bot_id = self.bot_qq or str(getattr(getattr(self._bot_client, "robot", None), "id", "") or "")
                if bot_id:
                    content = re.sub(r"<@!?" + re.escape(str(bot_id)) + r">", "", content).strip()
            images, files = await asyncio.gather(
                asyncio.to_thread(_parse_attachments, msg, "image"),
                asyncio.to_thread(_parse_attachments, msg, "file"),
            )
            prefix, extra = _detect_qqofficial_reply(msg)
            content = prefix + content
            if not content and not images and not files:
                return
            extra["message_id"] = str(getattr(msg, "id", "") or "")
            if kind == "channel":
                extra["channel_id"] = channel_id
            response = await self.route_to_decision_hub(
                content=content,
                user_id=user_id,
                user_name=getattr(author, "username", "") or getattr(author, "nick", "") or user_id,
                message_type="group" if kind in {"group", "channel"} else "private",
                group_id=target if kind in {"group", "channel"} else "",
                is_at_bot=True,
                images=images or None,
                files=files or None,
                extra=extra,
            )
            if response:
                # 频道及频道私信保留 botpy 的原事件回复方法。
                if kind in {"channel", "direct"}:
                    for chunk in self._split_long_line(response, 500):
                        await msg.reply(content=chunk)
                elif not await self._tts_process_and_send_qqofficial(
                    response, msg if kind == "c2c" else None, msg if kind == "group" else None
                ):
                    await self._send_text(target, response, kind)
        except Exception:
            logger.exception("[qqofficial] %s 消息处理失败", kind)
        finally:
            self._reply_context.reset(token)

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
                    await platform._handle_message(message, "channel")

                async def on_group_at_message_create(self, message):
                    await platform._handle_message(message, "group")

                async def on_direct_message_create(self, message):
                    await platform._handle_message(message, "direct")

                async def on_c2c_message_create(self, message):
                    await platform._handle_message(message, "c2c")

            http_timeout = max(10, int(self.config.get("http_timeout", 30)))
            self._bot_client = _MiyaBotClient(
                intents=intents,
                is_sandbox=self.sandbox,
                timeout=http_timeout,
            )

            async def run_bot():
                params = {"appid": self.appid, "secret": self.secret}
                try:
                    await self._bot_client.start(**params)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    if isinstance(e, AttributeError) and "NoneType" in str(e) and ".get" in str(e):
                        logger.error(
                            "[qqofficial] Bot 登录/初始化失败：QQ API 没有返回有效 JSON；"
                            "通常是网络超时、代理或 appid/secret 无效。"
                            "已将该连接标记为失败，等待统一重连。异常=%s",
                            e,
                            exc_info=True,
                        )
                    else:
                        logger.error("[qqofficial] Bot 运行异常: %s", e, exc_info=True)
                finally:
                    # botpy owns an aiohttp session. A failed login also creates
                    # that session, so reconnecting without closing it produces
                    # an unclosed-client-session warning during boot.
                    client = self._bot_client
                    close = getattr(client, "close", None) if client is not None else None
                    if close is not None:
                        with contextlib.suppress(Exception):
                            await close()

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
        if self._bot_client is not None:
            close = getattr(self._bot_client, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()
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
        file_type = self._qq_official_file_type(file_path)
        if file_type is None:
            logger.warning("[qqofficial] 当前适配器不支持发送该格式: %s", os.path.splitext(file_path)[1])
            return False
        if msg_type not in {"group", "private", "c2c"}:
            return False
        try:
            data = await asyncio.to_thread(Path(file_path).read_bytes)
            encoded = base64.b64encode(data).decode("ascii")
            return await self._send_media(
                target, "group" if msg_type == "group" else "c2c", file_type, encoded, caption
            )
        except Exception:
            logger.exception("[qqofficial] 读取或发送媒体失败")
            return False

    async def _send_media(
        self, target: str, kind: str, file_type: int, encoded: str, caption: str = ""
    ) -> bool:
        """上传本地内容，再携带 file_info 回复；只有消息回执才代表投递成功。"""
        if not self._bot_client or kind not in {"group", "c2c"}:
            return False
        from botpy.http import Route

        peer_id = str(target) if kind == "group" else self._resolve_qqofficial_openid(str(target))
        if not peer_id or not encoded:
            return False
        try:
            if kind == "group":
                route = Route("POST", "/v2/groups/{group_openid}/files", is_sandbox=self.sandbox, group_openid=peer_id)
            else:
                route = Route("POST", "/v2/users/{openid}/files", is_sandbox=self.sandbox, openid=peer_id)
            uploaded = await self._bot_client.api._http.request(
                route, json={"file_type": file_type, "file_data": encoded, "srv_send_msg": False}
            )
            file_info = uploaded.get("file_info") if isinstance(uploaded, dict) else None
            if not file_info:
                logger.warning("[qqofficial] 上传媒体未返回 file_info")
                return False
            params = self._reply_params(peer_id, kind)
            payload = {"msg_type": 7, "media": {"file_info": file_info}, **params}
            if caption:
                payload["content"] = caption
            if kind == "group":
                result = await self._bot_client.api.post_group_message(group_openid=peer_id, **payload)
            else:
                result = await self._bot_client.api.post_c2c_message(openid=peer_id, **payload)
            if not self._message_delivered(result):
                logger.warning("[qqofficial] 媒体发送未返回消息回执")
                return False
            self._record_message_out()
            return True
        except Exception as e:
            logger.warning("[qqofficial] 媒体发送失败: %s", e)
            return False

    @staticmethod
    def _qq_official_file_type(file_path: str) -> Optional[int]:
        """Map a local file to QQ Official's supported file_type values."""
        ext = os.path.splitext(file_path)[1].lower()
        # QQ Official documents only JPG/PNG image uploads.
        if ext in {".jpg", ".jpeg", ".png"}:
            return 1  # image
        # The video endpoint accepts MP4, and voice uploads must be Silk.
        if ext == ".mp4":
            return 2  # video
        if ext == ".silk":
            return 3  # voice
        return None

    @staticmethod
    def _resolve_qqofficial_openid(target: str) -> str:
        """只转换明确绑定到同一人的 QQ ID，绝不使用其他账号的 OpenID。"""
        target = str(target or "")
        if not target.isdigit():
            return target
        try:
            import json

            perms_path = Path("config/permissions.json")
            if not perms_path.exists():
                return target
            perms = json.loads(perms_path.read_text(encoding="utf-8"))
            for info in perms.get("superadmins", {}).values():
                ids = info.get("ids", {})
                qq_ids = []
                for platform in ("qq", "aiocqhttp", "onebot"):
                    values = ids.get(platform, [])
                    qq_ids.extend([values] if isinstance(values, (str, int)) else values or [])
                if target not in {str(uid) for uid in qq_ids}:
                    continue
                openids = ids.get("qqofficial") or ids.get("qq_official") or []
                if isinstance(openids, (str, int)):
                    openids = [openids]
                return next((str(uid) for uid in openids if uid), target)
        except Exception:
            logger.debug("[qqofficial] 无法解析用户绑定", exc_info=True)
        return target

    async def _tts_send_voice(self, audio_path: str, text: str, **kwargs) -> bool:
        """共享 TTS 在合成后调用此方法；格式转换仅操作临时副本。"""
        context = self._reply_context.get()
        target = kwargs.get("target") or (context or {}).get("target", "")
        kind = kwargs.get("kind") or (context or {}).get("kind", "")
        if not target or kind not in {"group", "c2c"}:
            return False
        try:
            if Path(audio_path).suffix.lower() == ".silk":
                data = await asyncio.to_thread(Path(audio_path).read_bytes)
                encoded = base64.b64encode(data).decode("ascii")
            else:
                import shutil
                import tempfile

                from astrbot.core.utils.tencent_record_helper import audio_to_tencent_silk_base64

                with tempfile.TemporaryDirectory(prefix="miya_qq_voice_") as temp_dir:
                    source = Path(temp_dir) / ("voice" + Path(audio_path).suffix)
                    await asyncio.to_thread(shutil.copyfile, audio_path, source)
                    encoded, _duration = await audio_to_tencent_silk_base64(str(source))
            return await self._send_media(target, kind, 3, encoded)
        except Exception as e:
            logger.warning("[qqofficial] 语音发送失败，回退文字: %s", e)
            return False

    async def _tts_process_and_send_qqofficial(self, text: str, private_msg=None, group_msg=None) -> bool:
        msg = group_msg if group_msg is not None else private_msg
        if msg is None:
            return False
        kind = "group" if group_msg is not None else "c2c"
        author = getattr(msg, "author", None)
        target = str(
            getattr(msg, "group_openid", "") if kind == "group"
            else getattr(author, "user_openid", None) or getattr(author, "member_openid", "")
        )
        token = None
        if self._reply_context.get() is None:
            token = self._reply_context.set({
                "kind": kind, "target": target, "message_id": str(getattr(msg, "id", "") or ""), "seq": 0
            })
        try:
            _audio_path, sent = await self._tts_process(text, target=target, kind=kind)
            return sent
        finally:
            if token is not None:
                self._reply_context.reset(token)
