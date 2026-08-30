"""
飞书 / KOOK / Slack / LINE / 钉钉 / Satori — Webhook 平台实现

所有 webhook 平台共享 FastAPI 路由，通过 management_api 动态注册。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from .webhook_base import WebhookPlatform

logger = logging.getLogger("Miya.Platform.Webhooks")


class LarkPlatform(WebhookPlatform):
    """飞书 (Lark) — SDK 长连接"""

    platform_id = "lark"
    platform_name = "飞书"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        from config.config_utils import get_api_key

        self._app_id = (config.get("app_id", "") if config else "") or get_api_key("LARK_APP_ID")
        self._app_secret = (config.get("app_secret", "") if config else "") or get_api_key("LARK_APP_SECRET")
        self._ws_client = None

    async def _do_connect(self) -> bool:
        if not self._app_id or not self._app_secret:
            logger.error("[lark] 缺少 app_id 或 app_secret")
            return False
        try:
            from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import (
                P2ImMessageReceiveV1,
            )
            from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
            from lark_oapi.ws import Client

            platform = self

            def on_message(data: P2ImMessageReceiveV1):
                try:
                    event = data.event
                    msg = event.message
                    content = ""
                    images = []
                    files_ctx = []

                    msg_type_val = msg.message_type if hasattr(msg, "message_type") else "text"
                    msg_id = msg.message_id if hasattr(msg, "message_id") else ""

                    if msg_type_val == "text":
                        content = json.loads(msg.content).get("text", "") if msg.content else ""
                    elif msg_type_val == "image":
                        img_key = json.loads(msg.content).get("image_key", "") if msg.content else ""
                        content = f"[图片: {img_key}]" if img_key else "[图片]"
                        if img_key:
                            from core.file_context import FileContext

                            fctx = FileContext.from_image(
                                file_name=f"lark_image_{img_key}.jpg",
                                file_id=img_key,
                            )
                            _download_lark_sync(platform, "image", img_key, fctx, msg_id)
                            if fctx.file_data:
                                images.append(fctx)
                    elif msg_type_val == "file":
                        fkey = json.loads(msg.content).get("file_key", "") if msg.content else ""
                        fname = json.loads(msg.content).get("file_name", "") if msg.content else ""
                        content = f"[文件: {fname}]" if fname else "[文件]"
                        if fkey:
                            from core.file_context import FileContext

                            fctx = FileContext.from_file(
                                file_name=fname or f"lark_file_{fkey}.bin",
                                file_id=fkey,
                            )
                            _download_lark_sync(platform, "file", fkey, fctx, msg_id)
                            if fctx.file_data:
                                files_ctx.append(fctx)
                    elif msg_type_val == "audio":
                        content = "[语音]"
                    else:
                        content = f"[{msg_type_val}消息]"

                    user_id = event.sender.sender_id.user_id if event.sender else ""
                    chat_id = msg.chat_id or ""
                    msg_type = "group" if msg.chat_type == "group" else "private"
                    if content:
                        asyncio.create_task(
                            platform._handle_lark_message(
                                content,
                                user_id,
                                chat_id,
                                msg_type,
                                images=images if images else None,
                                files_ctx=files_ctx if files_ctx else None,
                            )
                        )
                except Exception as e:
                    logger.warning(f"[lark] 消息异常: {e}")

            handler = EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()
            self._ws_client = Client(
                app_id=self._app_id,
                app_secret=self._app_secret,
                event_handler=handler,
            )

            async def run_lark_ws():
                await self._ws_client._connect()
                await self._ws_client._ping_loop()
                await self._ws_client._receive_message_loop()

            self._tasks.append(asyncio.create_task(run_lark_ws()))
            logger.info("[lark] 飞书长连接已启动")
            return True
        except ImportError:
            logger.error("[lark] 请安装 lark-oapi")
            return False
        except Exception as e:
            logger.error(f"[lark] 连接失败: {e}", exc_info=True)
            return False

    async def _handle_lark_message(
        self,
        content,
        user_id,
        chat_id,
        msg_type,
        images=None,
        files_ctx=None,
    ):
        response = await self.route_to_decision_hub(
            content=content,
            user_id=str(user_id),
            user_name=str(user_id),
            message_type=msg_type,
            group_id=chat_id,
            is_at_bot="@_all" in content or "@全员" in content,
            images=images,
            files=files_ctx,
        )
        if response:
            try:
                import lark_oapi as lark
                from lark_oapi.api.im.v1 import (
                    CreateMessageRequest,
                    CreateMessageRequestBody,
                )

                body = (
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": response}))
                    .build()
                )
                req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build()
                client = lark.Client.builder().app_id(self._app_id).app_secret(self._app_secret).build()
                client.im.v1.message.create(req)
            except Exception as e:
                logger.warning(f"[lark] 回复失败: {e}")

    async def send_private_message(self, user_id: str, message: str) -> bool:
        """发送主动私聊消息 (v8.1)"""
        if not self._app_id or not self._app_secret:
            logger.debug("[lark] 主动消息跳过: 未配置 app_id/app_secret")
            return False
        try:
            import json

            import lark_oapi as lark
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )

            body = (
                CreateMessageRequestBody.builder()
                .receive_id(str(user_id))
                .msg_type("text")
                .content(json.dumps({"text": message}))
                .build()
            )
            req = (
                CreateMessageRequest.builder()
                .receive_id_type("user_id")  # v8.2: 修复 — 入站 user_id 不能当 open_id 用
                .request_body(body)
                .build()
            )
            client = lark.Client.builder().app_id(self._app_id).app_secret(self._app_secret).build()
            client.im.v1.message.create(req)
            logger.debug("[lark] 主动消息已发送: %s → %s", user_id, message[:30])
            return True
        except Exception as e:
            logger.error("[lark] 主动消息发送失败: %s", e)
            return False

    async def _do_disconnect(self):
        if self._ws_client:
            with contextlib.suppress(Exception):
                await self._ws_client._disconnect()
        self._ws_client = None

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """飞书文件发送 — upload + send"""
        if not self._app_id or not self._app_secret:
            logger.warning("[lark] 未配置 app_id/app_secret，无法发送文件")
            return False

        data = None
        if outbound_file.is_local and outbound_file.file_path:
            with open(outbound_file.file_path, "rb") as f:
                data = f.read()
        elif outbound_file.is_bytes and outbound_file.file_data:
            data = outbound_file.file_data

        if not data:
            return False

        import json as _json
        from io import BytesIO

        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateFileRequest,
            CreateFileRequestBody,
            CreateMessageRequest,
            CreateMessageRequestBody,
        )

        client = lark.Client.builder().app_id(self._app_id).app_secret(self._app_secret).build()

        peer_id = self._resolve_lark_peer(target)

        try:
            file_type = "stream"
            if outbound_file.is_image:
                file_type = "image"

            upload_body = (
                CreateFileRequestBody.builder()
                .file_type(file_type)
                .file_name(outbound_file.file_name)
                .file(BytesIO(data))
                .build()
            )
            upload_req = CreateFileRequest.builder().request_body(upload_body).build()
            upload_resp = client.im.v1.file.create(upload_req)

            if not upload_resp.success():
                logger.error(f"[lark] 文件上传失败 ({upload_resp.code}): {upload_resp.msg}")
                return False

            file_key = upload_resp.data.file_key

            if outbound_file.is_image:
                msg_content = json.dumps({"image_key": file_key})
                msg_type = "image"
            else:
                msg_content = json.dumps({"file_key": file_key})
                msg_type = "file"

            caption = getattr(outbound_file, "caption", "") or ""
            if caption:
                msg_content = json.dumps({"file_key": file_key, "caption": caption})

            msg_body = (
                CreateMessageRequestBody.builder().receive_id(peer_id).msg_type(msg_type).content(msg_content).build()
            )
            msg_req = CreateMessageRequest.builder().receive_id_type("user_id").request_body(msg_body).build()
            msg_resp = client.im.v1.message.create(msg_req)

            if not msg_resp.success():
                logger.error(f"[lark] 文件消息发送失败 ({msg_resp.code}): {msg_resp.msg}")
                return False

            self._record_message_out()
            logger.info(f"[lark] 文件已发送: {outbound_file.file_name} -> {peer_id}")
            return True

        except Exception as e:
            logger.error(f"[lark] 发送文件异常: {e}")
            return False

    @staticmethod
    def _resolve_lark_peer(target: str) -> str:
        """解析飞书 peer_id"""
        if not target:
            return target
        try:
            perms_path = Path("config/permissions.json")
            if perms_path.exists():
                perms = json.loads(perms_path.read_text(encoding="utf-8"))
                superadmins = perms.get("superadmins", {})
                for sa_info in superadmins.values():
                    ids = sa_info.get("ids", {})
                    for platform, id_list in ids.items():
                        if target in [str(i) for i in id_list]:
                            lark_ids = ids.get("lark", [])
                            if lark_ids and lark_ids[0]:
                                logger.info("[lark] canonical %s -> lark ID %s", target, lark_ids[0])
                                return str(lark_ids[0])
        except Exception:
            pass
        return target
        return self._ws_client is not None


class KOOKPlatform(WebhookPlatform):
    """KOOK (开黑啦) 平台"""

    platform_id = "kook"
    platform_name = "KOOK"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._token = config.get("token", "") if config else ""
        self._verify_token = config.get("verify_token", "") if config else ""

    def get_webhook_routes(self) -> dict:
        async def webhook_handler(request):
            try:
                body = await request.json()
                d = body.get("d", {})
                challenge = d.get("challenge")
                if challenge:
                    return {"challenge": challenge}

                channel_type = d.get("channel_type", "")
                author = d.get("extra", {}).get("author", {})
                content = d.get("content", "")
                user_id = d.get("author_id", "") or author.get("id", "")
                msg_type_num = d.get("type", 1)
                images = []
                files_ctx = []

                if msg_type_num == 1:
                    content = content
                elif msg_type_num == 2:
                    content = "[图片]"
                    from core.file_context import FileContext

                    img_url = d.get("extra", {}).get("attachments", {}).get("url", "")
                    if img_url:
                        images.append(FileContext.from_image(url=img_url, file_name="kook_image.jpg"))
                elif msg_type_num == 3:
                    content = "[视频]"
                elif msg_type_num == 4:
                    content = "[文件]"
                    from core.file_context import FileContext

                    fname = d.get("extra", {}).get("attachments", {}).get("name", "")
                    furl = d.get("extra", {}).get("attachments", {}).get("url", "")
                    fsize = d.get("extra", {}).get("attachments", {}).get("size", 0)
                    if furl:
                        files_ctx.append(
                            FileContext.from_file(
                                url=furl,
                                file_name=fname or "kook_file.bin",
                                file_size=fsize,
                            )
                        )
                else:
                    content = content

                if content.strip():
                    await self.route_to_decision_hub(
                        content=content,
                        user_id=str(user_id),
                        message_type=channel_type if channel_type else "private",
                        images=images if images else None,
                        files=files_ctx if files_ctx else None,
                    )
                    return {"code": 0}
            except Exception as e:
                logger.warning(f"[kook] webhook error: {e}")
            return {"code": 0}

        return {"prefix": "/webhook/kook", "routes": [("POST", "", webhook_handler)]}


class SlackPlatform(WebhookPlatform):
    """Slack 平台"""

    platform_id = "slack"
    platform_name = "Slack"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._signing_secret = config.get("signing_secret", "") if config else ""

    def get_webhook_routes(self) -> dict:
        async def webhook_handler(request):
            try:
                body = await request.json()
                event_type = body.get("type", "")

                if event_type == "url_verification":
                    return {"challenge": body.get("challenge", "")}

                event = body.get("event", {})
                if event.get("type") != "app_mention" and event.get("type") != "message":
                    return {"ok": True}

                text = event.get("text", "")
                user_id = event.get("user", "")
                channel = event.get("channel", "")

                from core.file_context import FileContext

                images = []
                files_ctx = []

                sfiles = event.get("files", [])
                if isinstance(sfiles, list):
                    for sf in sfiles:
                        if not isinstance(sf, dict):
                            continue
                        sftype = sf.get("mimetype", "")
                        sfurl = sf.get("url_private", sf.get("url_private_download", sf.get("permalink", "")))
                        sfname = sf.get("name", f"slack_file_{sf.get('id', id(sf))}.bin")
                        sfsize = sf.get("size", 0)
                        sfid = sf.get("id", "")
                        if not sfurl:
                            continue
                        if sftype and sftype.startswith("image/"):
                            images.append(
                                FileContext.from_image(
                                    url=sfurl,
                                    file_name=sfname,
                                    file_size=sfsize,
                                    mime_type=sftype,
                                    file_id=sfid,
                                )
                            )
                        else:
                            files_ctx.append(
                                FileContext.from_file(
                                    url=sfurl,
                                    file_name=sfname,
                                    file_size=sfsize,
                                    mime_type=sftype,
                                    file_id=sfid,
                                )
                            )

                if text.strip() or images or files_ctx:
                    await self.route_to_decision_hub(
                        content=text or "",
                        user_id=str(user_id),
                        message_type="group",
                        group_id=channel,
                        images=images if images else None,
                        files=files_ctx if files_ctx else None,
                    )
            except Exception as e:
                logger.warning(f"[slack] webhook error: {e}")
                return {"ok": True}

        return {"prefix": "/webhook/slack", "routes": [("POST", "", webhook_handler)]}


class LINEPlatform(WebhookPlatform):
    """LINE 平台"""

    platform_id = "line"
    platform_name = "LINE"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._channel_secret = config.get("channel_secret", "") if config else ""

    def get_webhook_routes(self) -> dict:
        async def webhook_handler(request):
            try:
                body = await request.json()
                events = body.get("events", [])
                for event in events:
                    if event.get("type") != "message":
                        continue
                    message = event.get("message", {})
                    msg_type_line = message.get("type", "text")
                    text = ""
                    images = []
                    files_ctx = []

                    if msg_type_line == "text":
                        text = message.get("text", "")
                    elif msg_type_line == "image":
                        text = "[图片]"
                        from core.file_context import FileContext

                        img_id = message.get("id", "")
                        if img_id:
                            images.append(
                                FileContext.from_image(
                                    file_name=f"line_image_{img_id}.jpg",
                                    file_id=img_id,
                                    metadata={"line_message_id": event.get("message", {}).get("id", "")},
                                )
                            )
                    elif msg_type_line == "video":
                        text = "[视频]"
                        from core.file_context import FileContext

                        vid_id = message.get("id", "")
                        if vid_id:
                            files_ctx.append(
                                FileContext.from_video(
                                    file_name=f"line_video_{vid_id}.mp4",
                                    file_id=vid_id,
                                )
                            )
                    elif msg_type_line == "audio":
                        text = "[语音]"
                        from core.file_context import FileContext

                        aud_id = message.get("id", "")
                        if aud_id:
                            files_ctx.append(
                                FileContext.from_voice(
                                    file_name=f"line_audio_{aud_id}.m4a",
                                    file_id=aud_id,
                                )
                            )
                    elif msg_type_line == "file":
                        fname = message.get("fileName", "")
                        fsize = message.get("fileSize", 0)
                        text = f"[文件: {fname}]" if fname else "[文件]"
                        from core.file_context import FileContext

                        fid = message.get("id", "")
                        if fid:
                            files_ctx.append(
                                FileContext.from_file(
                                    file_name=fname or f"line_file_{fid}.bin",
                                    file_id=fid,
                                    file_size=fsize,
                                )
                            )
                    else:
                        continue

                    user_id = event.get("source", {}).get("userId", "")
                    msg_type = "group" if event.get("source", {}).get("type") == "group" else "private"

                    if text or images or files_ctx:
                        await self.route_to_decision_hub(
                            content=text or "",
                            user_id=str(user_id),
                            message_type=msg_type,
                            images=images if images else None,
                            files=files_ctx if files_ctx else None,
                        )
            except Exception as e:
                logger.warning(f"[line] webhook error: {e}")
            return {"status": "ok"}

        return {"prefix": "/webhook/line", "routes": [("POST", "", webhook_handler)]}


class DingTalkPlatform(WebhookPlatform):
    """钉钉 平台"""

    platform_id = "dingtalk"
    platform_name = "钉钉"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._app_key = config.get("app_key", "") if config else ""
        self._app_secret = config.get("app_secret", "") if config else ""

    def get_webhook_routes(self) -> dict:
        async def webhook_handler(request):
            try:
                body = await request.json()
                text = body.get("text", {}).get("content", "") if isinstance(body, dict) else ""
                sender_id = body.get("senderId", "") if isinstance(body, dict) else ""

                if text.strip():
                    response = await self.route_to_decision_hub(
                        content=text,
                        user_id=str(sender_id),
                        message_type="private",
                    )
                    return {"msgtype": "text", "text": {"content": response}}
            except Exception as e:
                logger.warning(f"[dingtalk] webhook error: {e}")
            return {"errcode": 0}

        return {
            "prefix": "/webhook/dingtalk",
            "routes": [("POST", "", webhook_handler)],
        }


class SatoriPlatform(WebhookPlatform):
    """Satori 统一协议平台"""

    platform_id = "satori"
    platform_name = "Satori"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)

    def get_webhook_routes(self) -> dict:
        async def webhook_handler(request):
            try:
                body = await request.json()
                op = body.get("op", "")
                if op != "message_create":
                    return {"code": 0}

                msg = body.get("message", body.get("payload", {}).get("message", {}))
                content = msg.get("content", "")
                user = body.get("user", body.get("payload", {}).get("user", {}))
                user_id = user.get("id", "")
                body.get("channel", body.get("payload", {}).get("channel", {}))

                if content.strip():
                    await self.route_to_decision_hub(
                        content=content,
                        user_id=str(user_id),
                        message_type="private",
                    )
            except Exception as e:
                logger.warning(f"[satori] webhook error: {e}")
            return {"code": 0}

        return {"prefix": "/webhook/satori", "routes": [("POST", "", webhook_handler)]}


def _download_lark_sync(platform: Any, media_type: str, key: str, fctx: Any, msg_id: str = "") -> None:
    if not key:
        return
    try:
        import lark_oapi as lark

        client = lark.Client.builder().app_id(platform._app_id).app_secret(platform._app_secret).build()

        # 优先使用消息资源 API（兼容"非发送者"场景）
        if msg_id and media_type in ("file", "image"):
            from lark_oapi.api.im.v1 import GetMessageResourceRequest

            req = GetMessageResourceRequest.builder().message_id(msg_id).file_key(key).type(media_type).build()
            resp = client.im.v1.message_resource.get(req)
        elif media_type == "image":
            from lark_oapi.api.im.v1 import GetImageRequest

            req = GetImageRequest.builder().image_key(key).build()
            resp = client.im.v1.image.get(req)
        else:
            from lark_oapi.api.im.v1 import GetFileRequest

            req = GetFileRequest.builder().file_key(key).build()
            resp = client.im.v1.file.get(req)

        if resp and resp.code == 0 and resp.file:
            fctx.file_data = resp.file.read() if hasattr(resp.file, "read") else resp.file
            fctx.file_size = len(fctx.file_data)
            fctx.download_status = "done"
            logger.info("[lark] 媒体下载成功: %s (%d bytes)", key[:20], fctx.file_size)
        else:
            logger.warning("[lark] 下载媒体失败: code=%s msg=%s", getattr(resp, "code", "?"), getattr(resp, "msg", "?"))
    except Exception as e:
        logger.warning("[lark] 下载媒体异常 (%s, %s): %s", media_type, key[:20], e)


# ==================== (old async helpers removed) ====================
# 保留 _download_lark_media / _lark_client 以确保编译通过（未被引用）
# 见 git history for original implementation
