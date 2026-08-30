"""
KOOK / Slack / 钉钉 / Satori / 企业微信 / 微信公众号 — 专用平台实现

所有平台使用 WebSocket 或 Webhook，不需要 ngrok（除微信公众号/企业微信 webhook 模式）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from typing import Any, List, Optional

from .webhook_base import WebhookPlatform

logger = logging.getLogger("Miya.Platform.RealPlatforms")


class KOOKPlatform(WebhookPlatform):
    """KOOK (开黑啦) — WebSocket 直连"""

    platform_id = "kook"
    platform_name = "KOOK"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._token = config.get("token", "") if config else ""
        self._ws = None
        self._heartbeat_task = None

    async def _do_connect(self) -> bool:
        if not self._token:
            return True
        try:
            import aiohttp

            platform = self

            async def heartbeat(ws, interval=30000):
                while True:
                    try:
                        await ws.send_json({"s": 2, "sn": 0})
                    except Exception:
                        break
                    await asyncio.sleep(interval / 1000)

            async def kook_loop():
                url = f"wss://ws.kookapp.com/ws?token={self._token}"
                async with aiohttp.ClientSession() as session, session.ws_connect(url) as ws:
                    self._ws = ws
                    self._heartbeat_task = asyncio.create_task(heartbeat(ws))
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("s") == 0:  # EVENT
                                d = data.get("d", {})
                                typ = d.get("type", 0)
                                content = ""
                                images = []
                                files_ctx = []

                                if typ == 1:  # TEXT
                                    content = d.get("content", "")
                                elif typ == 2:  # IMAGE
                                    content = "[图片]"
                                    from core.file_context import FileContext

                                    img_url = d.get("extra", {}).get("attachments", {}).get("url", "")
                                    if img_url:
                                        images.append(
                                            FileContext.from_image(
                                                url=img_url,
                                                file_name="kook_image.jpg",
                                            )
                                        )
                                elif typ == 3:  # VIDEO
                                    content = "[视频]"
                                elif typ == 4:  # FILE
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

                                author = d.get("extra", {}).get("author", {})
                                user_id = d.get("author_id", "") or author.get("id", "")
                                ch_type = d.get("channel_type", "PERSON")
                                if content.strip():
                                    await platform.route_to_decision_hub(
                                        content=content,
                                        user_id=str(user_id),
                                        message_type="group" if ch_type == "GROUP" else "private",
                                        images=images if images else None,
                                        files=files_ctx if files_ctx else None,
                                    )

            self._tasks.append(asyncio.create_task(kook_loop()))
            logger.info("[kook] 已连接")
            return True
        except ImportError:
            logger.error("[kook] 请安装 aiohttp")
            return True
        except Exception as e:
            logger.error(f"[kook] 连接失败: {e}")
            return True

    async def _do_disconnect(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()

    def get_webhook_routes(self) -> Optional[dict]:
        return None


class SlackPlatform(WebhookPlatform):
    """Slack — Socket Mode (WebSocket, 无需公网)"""

    platform_id = "slack"
    platform_name = "Slack"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._app_token = config.get("app_token", "") if config else ""
        self._bot_token = config.get("bot_token", "") if config else ""
        self._handler = None

    async def _do_connect(self) -> bool:
        if not self._app_token:
            return True
        try:
            from slack_sdk.socket_mode.aiohttp import SocketModeClient
            from slack_sdk.socket_mode.request import SocketModeRequest
            from slack_sdk.web.async_client import AsyncWebClient

            platform = self

            def process(client: SocketModeClient, req: SocketModeRequest):
                if req.type == "events_api":
                    event = req.payload.get("event", {})
                    if event.get("type") == "app_mention":
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
                            asyncio.create_task(
                                platform.route_to_decision_hub(
                                    content=text or "",
                                    user_id=user_id,
                                    message_type="group",
                                    group_id=channel,
                                    images=images if images else None,
                                    files=files_ctx if files_ctx else None,
                                )
                            )

            client = SocketModeClient(
                app_token=self._app_token,
                web_client=AsyncWebClient(token=self._bot_token),
            )
            client.socket_mode_request_listeners.append(process)

            async def slack_loop():
                await client.connect()
                await client.wait_for_disconnect()

            self._handler = client
            self._tasks.append(asyncio.create_task(slack_loop()))
            logger.info("[slack] Socket Mode 已启动")
            return True
        except ImportError:
            logger.warning("[slack] 请安装 slack-sdk: pip install slack-sdk")
            return True
        except Exception as e:
            logger.error(f"[slack] 连接失败: {e}")
            return True

    async def _do_disconnect(self):
        if self._handler:
            with contextlib.suppress(Exception):
                await self._handler.close()

    def get_webhook_routes(self) -> Optional[dict]:
        return None


class DingTalkPlatform(WebhookPlatform):
    """钉钉 — Stream 模式 (WebSocket, 无需公网)"""

    platform_id = "dingtalk"
    platform_name = "钉钉"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._client_id = config.get("app_key", "") if config else ""
        self._client_secret = config.get("app_secret", "") if config else ""
        self._client: Any = None

    async def _do_connect(self) -> bool:
        if not self._client_id:
            return True
        try:
            import sys

            _dingtalk_sdk = os.getenv("DINGTALK_STREAM_SDK_PATH", "").strip()
            if _dingtalk_sdk:
                sys.path.insert(0, _dingtalk_sdk)
            from dingtalk_stream import ChatbotHandler, Credential, DingTalkStreamClient

            platform = self

            class MiyaChatbotHandler(ChatbotHandler):
                async def process(self, callback):
                    text = callback.text.strip() if callback.text else ""
                    sender = callback.sender_id
                    msg_type_dt = (
                        getattr(callback, "message_type", "text") if hasattr(callback, "message_type") else "text"
                    )
                    images = []
                    files_ctx = []

                    if msg_type_dt == "image":
                        text = text or "[图片]"
                        from core.file_context import FileContext

                        dload_code = getattr(callback, "download_code", None)
                        if dload_code:
                            images.append(
                                FileContext.from_image(
                                    file_name=f"dingtalk_image_{dload_code}.jpg",
                                    file_id=str(dload_code),
                                )
                            )
                    elif msg_type_dt == "file":
                        fname = getattr(callback, "file_name", "") if hasattr(callback, "file_name") else ""
                        text = f"[文件: {fname}]" if fname else "[文件]"
                        dload_code = getattr(callback, "download_code", None)
                        if dload_code:
                            from core.file_context import FileContext

                            files_ctx.append(
                                FileContext.from_file(
                                    file_name=fname or f"dingtalk_file_{dload_code}.bin",
                                    file_id=str(dload_code),
                                )
                            )
                    elif msg_type_dt == "audio":
                        text = text or "[语音]"

                    if text:
                        await platform.route_to_decision_hub(
                            content=text or "",
                            user_id=str(sender) if sender else "unknown",
                            message_type="private",
                            images=images if images else None,
                            files=files_ctx if files_ctx else None,
                        )

            credential = Credential(self._client_id, self._client_secret)
            client = DingTalkStreamClient(credential)
            client.register_callback_handler("/v1.0/im/bot/messages/get", MiyaChatbotHandler())

            async def dingtalk_loop():
                await client.start()

            self._client = client
            self._tasks.append(asyncio.create_task(dingtalk_loop()))
            logger.info("[dingtalk] Stream 模式已启动")
            return True
        except ImportError as e:
            logger.warning(f"[dingtalk] SDK 缺失: {e}")
            return True
        except Exception as e:
            logger.error(f"[dingtalk] 连接失败: {e}")
            return True
        try:
            import dingtalk_stream
            from dingtalk_stream import ChatbotClient

            platform = self

            class MiyaCallback(dingtalk_stream.ChatbotMessageHandler):
                async def process(self, callback):
                    text = callback.text.strip() if callback.text else ""
                    if text:
                        await platform.route_to_decision_hub(
                            content=text,
                            user_id=str(callback.sender_id),
                            message_type="private",
                        )

            credential = dingtalk_stream.Credential(self._client_id, self._client_secret)
            client = ChatbotClient(credential)
            client.register_callback_handler(MiyaCallback())

            async def dingtalk_loop():
                await client.start_async()

            self._client = client
            self._tasks.append(asyncio.create_task(dingtalk_loop()))
            logger.info("[dingtalk] Stream 模式已启动")
            return True
        except ImportError:
            logger.warning("[dingtalk] 请安装 dingtalk-stream: pip install dingtalk-stream")
            return True
        except Exception as e:
            logger.error(f"[dingtalk] 连接失败: {e}")
            return True

    async def _do_disconnect(self):
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.stop()


class SatoriPlatform(WebhookPlatform):
    """Satori 通用协议 — WebSocket 直连"""

    platform_id = "satori"
    platform_name = "Satori"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        self._ws_url = config.get("ws_url", "ws://127.0.0.1:5500") if config else "ws://127.0.0.1:5500"

    async def _do_connect(self) -> bool:
        try:
            import aiohttp

            platform = self

            async def satori_loop():
                while True:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.ws_connect(self._ws_url) as ws:
                                logger.info(f"[satori] 已连接 {self._ws_url}")
                                async for msg in ws:
                                    if msg.type == aiohttp.WSMsgType.TEXT:
                                        data = json.loads(msg.data)
                                        if data.get("op") == 0:  # EVENT
                                            body = data.get("body", {})
                                            if body.get("type") == "message-created":
                                                msg_data = body.get("message", {})
                                                content = msg_data.get("content", "")
                                                elements = msg_data.get("elements", [])
                                                user = body.get("user", {})
                                                user_id = user.get("id", "")

                                                from core.file_context import FileContext

                                                images = []
                                                files_ctx = []
                                                content_parts = []

                                                if isinstance(elements, list) and elements:
                                                    for el in elements:
                                                        el_type = el.get("type", "")
                                                        if el_type == "text":
                                                            content_parts.append(el.get("attrs", {}).get("content", ""))
                                                        elif el_type == "img":
                                                            src = el.get("attrs", {}).get("src", "")
                                                            alt = el.get("attrs", {}).get("alt", "")
                                                            content_parts.append(f"[图片: {alt}]" if alt else "[图片]")
                                                            if src:
                                                                images.append(
                                                                    FileContext.from_image(
                                                                        url=src, file_name=alt or "satori_image.jpg"
                                                                    )
                                                                )
                                                        elif el_type in ("file", "attachment"):
                                                            src = el.get("attrs", {}).get("src", "")
                                                            name = el.get("attrs", {}).get("title", "")
                                                            content_parts.append(
                                                                f"[文件: {name}]" if name else "[文件]"
                                                            )
                                                            if src:
                                                                files_ctx.append(
                                                                    FileContext.from_file(
                                                                        url=src, file_name=name or "satori_file.bin"
                                                                    )
                                                                )
                                                        elif el_type == "audio":
                                                            src = el.get("attrs", {}).get("src", "")
                                                            content_parts.append("[语音]")
                                                            if src:
                                                                files_ctx.append(
                                                                    FileContext.from_voice(
                                                                        url=src, file_name="satori_audio.mp3"
                                                                    )
                                                                )
                                                        elif el_type == "video":
                                                            src = el.get("attrs", {}).get("src", "")
                                                            content_parts.append("[视频]")
                                                            if src:
                                                                files_ctx.append(
                                                                    FileContext.from_video(
                                                                        url=src, file_name="satori_video.mp4"
                                                                    )
                                                                )
                                                    content = content or " ".join(content_parts)

                                                if content.strip():
                                                    await platform.route_to_decision_hub(
                                                        content=content,
                                                        user_id=str(user_id),
                                                        message_type="private",
                                                        images=images if images else None,
                                                        files=files_ctx if files_ctx else None,
                                                    )
                    except Exception as e:
                        logger.warning(f"[satori] 断开: {e}, 5s 后重连")
                        await asyncio.sleep(5)

            self._tasks.append(asyncio.create_task(satori_loop()))
            return True
        except ImportError:
            logger.warning("[satori] 请安装 aiohttp")
            return True
        except Exception as e:
            logger.error(f"[satori] 连接失败: {e}")
            return True

    async def _do_disconnect(self):
        pass


class WeComPlatform(WebhookPlatform):
    """企业微信 — Webhook 模式"""

    platform_id = "wecom"
    platform_name = "企业微信"

    def get_webhook_routes(self) -> dict:
        async def verify(request):
            params = request.query_params
            return int(params.get("echostr", "0"))

        async def webhook_handler(request):
            try:
                body = await request.json()
                if isinstance(body, dict) and "xml" in body:
                    return "success"
                msg_type = body.get("MsgType", "text")
                if msg_type == "text":
                    text = body.get("Content", "")
                    user_id = body.get("FromUserName", "")
                    if text.strip():
                        await self.route_to_decision_hub(
                            content=text,
                            user_id=str(user_id),
                            message_type="private",
                        )
            except Exception as e:
                logger.warning(f"[wecom] webhook: {e}")
            return "success"

        return {
            "prefix": "/webhook/wecom",
            "routes": [
                ("GET", "", verify),
                ("POST", "", webhook_handler),
            ],
        }


class WeChatOfficialPlatform(WebhookPlatform):
    """微信公众号 — Webhook 模式"""

    platform_id = "weixin_official_account"
    platform_name = "微信公众号"

    def get_webhook_routes(self) -> dict:
        async def verify(request):
            params = request.query_params
            return params.get("echostr", "")

        async def webhook_handler(request):
            try:
                body = await request.text()
                if "<MsgType>" in body and "<![CDATA[text]]>" in body:
                    import re

                    content_match = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", body)
                    user_match = re.search(r"<FromUserName><!\[CDATA\[(.*?)\]\]></FromUserName>", body)
                    if content_match and user_match:
                        await self.route_to_decision_hub(
                            content=content_match.group(1),
                            user_id=user_match.group(1),
                            message_type="private",
                        )
            except Exception as e:
                logger.warning(f"[weixin] webhook: {e}")
            return "success"

        return {
            "prefix": "/webhook/weixin_offacc",
            "routes": [
                ("GET", "", verify),
                ("POST", "", webhook_handler),
            ],
        }
