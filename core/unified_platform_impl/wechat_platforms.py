"""
企业微信 / 微信公众号 / 微信开放平台 — WeChat 生态平台实现

企业微信 (wecom): webhook 模式，使用 wechatpy.enterprise 接收消息，WeChatClient API 发送回复
微信公众号 (weixin_official_account): webhook 模式，被动回复 + 主动发送双模式
微信开放平台 (weixin_oc): 长轮询模式，使用 token 认证同步消息
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, List, Optional, cast

from .webhook_base import WebhookPlatform

logger = logging.getLogger("Miya.Platform.WeChat")


async def _wecom_download_media(
    platform: Any,
    msg: Any,
    media_id: str,
    media_type: str,
    parent_msg: Any = None,
) -> Optional[Any]:
    """下载企业微信媒体文件，返回 FileContext"""
    if not media_id or not platform._client:
        return None

    from core.file_context import FileContext

    try:
        loop = asyncio.get_running_loop()
        media_data = await loop.run_in_executor(
            None,
            platform._client.media.download,
            media_id,
        )
        if not media_data:
            return None

        if media_type == "image":
            return FileContext.from_image(
                file_data=media_data,
                file_name=f"wecom_image_{media_id}.jpg",
                file_id=media_id,
            )
        elif media_type == "voice":
            return FileContext.from_voice(
                file_data=media_data,
                file_name=f"wecom_voice_{media_id}.amr",
                file_id=media_id,
            )
        else:
            return FileContext.from_file(
                file_data=media_data,
                file_name=f"wecom_{media_type}_{media_id}.bin",
                file_id=media_id,
            )
    except Exception as e:
        logger.debug(f"[wecom] 媒体下载失败 ({media_type}, {media_id}): {e}")
        return None


# ====================================================================
#                          企业微信 (WeCom)
# ====================================================================


class WeComPlatform(WebhookPlatform):
    """企业微信 — Webhook 模式接收消息，WeChatClient 主动发送回复"""

    platform_id = "wecom"
    platform_name = "企业微信"
    health_check_interval = 120.0

    def __init__(self, config=None):
        super().__init__(config)
        cfg = config or {}
        self._corpid = cfg.get("corpid", "")
        self._secret = cfg.get("corpsecret") or cfg.get("secret", "")
        self._token = cfg.get("token", "")
        self._encoding_aes_key = cfg.get("encoding_aes_key", "")
        self._agent_id = cfg.get("agent_id", "")
        self._crypto = None
        self._client = None

    async def _do_connect(self) -> bool:
        try:
            from wechatpy.enterprise import WeChatClient
            from wechatpy.enterprise.crypto import WeChatCrypto

            if not self._corpid or not self._secret:
                logger.error("[wecom] 缺少 corpid / corpsecret")
                return False

            self._client = WeChatClient(self._corpid, self._secret)

            if self._token and self._encoding_aes_key:
                self._crypto = WeChatCrypto(
                    self._token.strip(),
                    self._encoding_aes_key.strip(),
                    self._corpid.strip(),
                )
                logger.info("[wecom] 企业微信加解密已启用 (安全模式)")
            else:
                logger.info("[wecom] 未配置 token/encoding_aes_key，明文模式")

            logger.info(f"[wecom] 企业微信已就绪, agent_id={self._agent_id or 'N/A'}")
            return True

        except ImportError:
            logger.error("[wecom] 请安装 wechatpy: pip install wechatpy")
            return False
        except Exception as e:
            logger.error(f"[wecom] 初始化失败: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        self._client = None
        self._crypto = None

    async def _do_health_check(self) -> bool:
        return self._client is not None

    def get_webhook_routes(self) -> dict:
        platform = self

        async def verify_get(request):
            """企业微信 GET 验证回调地址"""
            if not platform._crypto:
                return "success"
            try:
                args = request.query_params

                echo_str = platform._crypto.check_signature(
                    args.get("msg_signature", ""),
                    args.get("timestamp", ""),
                    args.get("nonce", ""),
                    args.get("echostr", ""),
                )
                logger.info("[wecom] 验证回调地址成功")
                return echo_str
            except Exception as e:
                logger.error(f"[wecom] 验证回调地址失败: {e}")
                return "verify failed"

        async def callback_post(request):
            """企业微信 POST 消息回调"""
            try:
                body = await request.body()
                params = request.query_params
                msg_signature = params.get("msg_signature", "")
                timestamp = params.get("timestamp", "")
                nonce = params.get("nonce", "")

                if platform._crypto:
                    try:
                        from wechatpy.exceptions import InvalidSignatureException

                        xml = platform._crypto.decrypt_message(body, msg_signature, timestamp, nonce)
                    except InvalidSignatureException:
                        logger.error("[wecom] 消息解密失败，签名异常")
                        return "fail"
                else:
                    xml = body.decode("utf-8")

                from wechatpy.enterprise import parse_message

                msg = parse_message(xml)
                if msg is None:
                    logger.warning("[wecom] 解析消息失败")
                    return "success"

                from wechatpy.enterprise.messages import ImageMessage as WxImageMsg
                from wechatpy.enterprise.messages import TextMessage as WxTextMsg
                from wechatpy.enterprise.messages import VoiceMessage as WxVoiceMsg

                content = ""
                msg_type = "private"
                user_id = str(getattr(msg, "source", ""))
                agent_id = str(getattr(msg, "agent", ""))

                from core.file_context import FileContext

                images: List[FileContext] = []
                files: List[FileContext] = []

                if isinstance(msg, WxTextMsg):
                    content = cast(str, msg.content)
                elif isinstance(msg, WxImageMsg):
                    content = ""
                    fctx = await _wecom_download_media(platform, msg, msg.media_id, "image", parent_msg=msg)
                    if fctx:
                        images.append(fctx)
                        content = f"[图片: {fctx.file_name}]" if fctx.is_downloaded else "[图片]"
                    else:
                        content = "[图片]"
                elif isinstance(msg, WxVoiceMsg):
                    content = ""
                    fctx = await _wecom_download_media(platform, msg, msg.media_id, "voice", parent_msg=msg)
                    if fctx:
                        files.append(fctx)
                        content = f"[语音: {fctx.file_name}]" if fctx.is_downloaded else "[语音]"
                    else:
                        content = "[语音]"
                else:
                    logger.info(f"[wecom] 未处理的消息类型: {type(msg).__name__}")
                    return "success"

                if content.strip() and user_id:
                    response = await platform.route_to_decision_hub(
                        content=content,
                        user_id=user_id,
                        message_type=msg_type,
                        extra={"agent_id": agent_id, "raw_message": msg},
                        images=images if images else None,
                        files=files if files else None,
                    )
                    if response and platform._client:
                        try:
                            target_agent = agent_id or platform._agent_id
                            if target_agent:
                                await asyncio.get_running_loop().run_in_executor(
                                    None,
                                    platform._client.message.send_text,
                                    target_agent,
                                    user_id,
                                    response,
                                )
                        except Exception as e:
                            logger.warning(f"[wecom] 发送回复失败: {e}")

            except Exception as e:
                logger.error(f"[wecom] webhook 处理异常: {e}", exc_info=True)

            return "success"

        return {
            "prefix": "/webhook/wecom",
            "routes": [
                ("GET", "", verify_get),
                ("POST", "", callback_post),
            ],
        }


# ====================================================================
#                      微信公众号 (WeixinOfficialAccount)
# ====================================================================


class WeixinOfficialAccountPlatform(WebhookPlatform):
    """微信公众号 — Webhook 被动回复 + 主动发送模式"""

    platform_id = "weixin_official_account"
    platform_name = "微信公众号"
    health_check_interval = 120.0
    support_proactive_message = False  # 微信公众号受被动回复限制，不支持无条件主动消息

    def __init__(self, config=None):
        super().__init__(config)
        cfg = config or {}
        self._appid = cfg.get("appid", "")
        self._secret = cfg.get("secret", "")
        self._token = cfg.get("token", "")
        self._encoding_aes_key = cfg.get("encoding_aes_key", "")
        self._active_send_mode = cfg.get("active_send_mode", False)
        self._crypto = None
        self._client = None

    async def send_private_message(self, user_id: str, message: str) -> bool:
        """发送主动私聊消息 (v8.1: 使用微信公众号客服消息API)"""
        if not self._active_send_mode:
            logger.debug("[weixin_offacc] 主动消息跳过: active_send_mode=False")
            return False
        if not self._client:
            logger.debug("[weixin_offacc] 主动消息跳过: 客户端未就绪")
            return False
        try:
            import asyncio

            await asyncio.get_running_loop().run_in_executor(
                None,
                self._client.message.send_text,
                str(user_id),
                message,
            )
            logger.debug("[weixin_offacc] 主动消息已发送: %s → %s", user_id, message[:30])
            return True
        except Exception as e:
            logger.error("[weixin_offacc] 主动消息发送失败: %s", e)
            return False

    async def _do_connect(self) -> bool:
        try:
            from wechatpy import WeChatClient
            from wechatpy.crypto import WeChatCrypto

            if self._token and self._encoding_aes_key and self._appid:
                self._crypto = WeChatCrypto(self._token, self._encoding_aes_key, self._appid)
                logger.info("[weixin_offacc] 消息加解密已启用 (安全模式)")
            else:
                logger.info("[weixin_offacc] 明文模式 (建议配置加密)")

            if self._appid and self._secret:
                self._client = WeChatClient(self._appid, self._secret)
                logger.info("[weixin_offacc] 微信公众号 API 客户端已就绪")

            logger.info(f"[weixin_offacc] 微信公众号已就绪, active_send_mode={self._active_send_mode}")
            return True

        except ImportError:
            logger.error("[weixin_offacc] 请安装 wechatpy: pip install wechatpy")
            return False
        except Exception as e:
            logger.error(f"[weixin_offacc] 初始化失败: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        self._client = None
        self._crypto = None

    async def _do_health_check(self) -> bool:
        return True

    def get_webhook_routes(self) -> dict:
        platform = self

        async def verify_get(request):
            """微信公众号 GET 验证"""
            if not platform._token:
                return "success"
            try:
                from wechatpy.utils import check_signature

                args = request.query_params
                if not args.get("signature"):
                    logger.error("[weixin_offacc] 未知的响应，请检查回调地址")
                    return "err"
                check_signature(
                    platform._token,
                    args.get("signature", ""),
                    args.get("timestamp", ""),
                    args.get("nonce", ""),
                )
                logger.info("[weixin_offacc] 验证回调地址成功")
                return args.get("echostr", "empty")
            except Exception as e:
                logger.error(f"[weixin_offacc] 验证回调地址失败: {e}")
                return "err"

        async def callback_post(request):
            """微信公众号 POST 消息回调"""
            try:
                body = await request.body()
                params = request.query_params
                msg_signature = params.get("msg_signature", "")
                timestamp = params.get("timestamp", "")
                nonce = params.get("nonce", "")

                if platform._crypto:
                    try:
                        from wechatpy.exceptions import InvalidSignatureException

                        xml = platform._crypto.decrypt_message(body, msg_signature, timestamp, nonce)
                    except InvalidSignatureException:
                        logger.error("[weixin_offacc] 消息解密失败")
                        return "fail"
                else:
                    xml = body.decode("utf-8")

                from wechatpy import parse_message

                msg = parse_message(xml)
                if msg is None:
                    logger.warning("[weixin_offacc] 解析消息失败")
                    return "success"

                from wechatpy.messages import ImageMessage as WxImageMsg
                from wechatpy.messages import TextMessage as WxTextMsg
                from wechatpy.messages import VoiceMessage as WxVoiceMsg

                content = ""
                user_id = str(getattr(msg, "source", ""))

                from core.file_context import FileContext

                images: List[FileContext] = []
                files_ctx: List[FileContext] = []

                if isinstance(msg, WxTextMsg):
                    content = cast(str, msg.content)
                elif isinstance(msg, WxImageMsg):
                    content = ""
                    media_id = getattr(msg, "media_id", "")
                    if media_id and platform._client:
                        try:
                            media_data = await asyncio.get_running_loop().run_in_executor(
                                None, platform._client.media.download, media_id
                            )
                            fctx = FileContext.from_image(
                                file_data=media_data,
                                file_name=f"wechat_image_{media_id}.jpg",
                                file_id=media_id,
                            )
                            images.append(fctx)
                            content = f"[图片: {fctx.file_name}]"
                        except Exception as e:
                            logger.debug(f"[weixin_offacc] 图片下载失败: {e}")
                            content = "[图片]"
                    else:
                        content = "[图片]"
                elif isinstance(msg, WxVoiceMsg):
                    content = ""
                    media_id = getattr(msg, "media_id", "")
                    if media_id and platform._client:
                        try:
                            media_data = await asyncio.get_running_loop().run_in_executor(
                                None, platform._client.media.download, media_id
                            )
                            fctx = FileContext.from_voice(
                                file_data=media_data,
                                file_name=f"wechat_voice_{media_id}.amr",
                                file_id=media_id,
                            )
                            files_ctx.append(fctx)
                            content = f"[语音: {fctx.file_name}]"
                        except Exception as e:
                            logger.debug(f"[weixin_offacc] 语音下载失败: {e}")
                            content = "[语音]"
                    else:
                        content = "[语音]"
                else:
                    logger.info(f"[weixin_offacc] 未处理的消息类型: {type(msg).__name__}")
                    return "success"

                if content.strip() and user_id:

                    async def _process():
                        return await platform.route_to_decision_hub(
                            content=content,
                            user_id=user_id,
                            message_type="private",
                            extra={"raw_message": msg},
                            images=images if images else None,
                            files=files_ctx if files_ctx else None,
                        )

                    if platform._active_send_mode and platform._client:
                        response = await _process()
                        if response:
                            try:
                                await asyncio.get_running_loop().run_in_executor(
                                    None,
                                    platform._client.message.send_text,
                                    user_id,
                                    response,
                                )
                            except Exception as e:
                                logger.warning(f"[weixin_offacc] 主动发送失败: {e}")
                        return "success"
                    else:
                        # 被动回复模式：5 秒内需返回

                        async def _timed_task():
                            try:
                                reply = await _process()
                                return reply
                            except Exception:
                                return None

                        task = asyncio.create_task(_timed_task())
                        try:
                            reply = await asyncio.wait_for(task, timeout=4.0)
                            if reply and platform._crypto:
                                from wechatpy import create_reply

                                reply_obj = create_reply(reply, msg)
                                reply_xml = reply_obj if isinstance(reply_obj, str) else str(reply_obj)
                                encrypted = platform._crypto.encrypt_message(reply_xml, nonce, timestamp)
                                return encrypted
                            elif reply:
                                from wechatpy import create_reply

                                reply_obj = create_reply(reply, msg)
                                return reply_obj if isinstance(reply_obj, str) else str(reply_obj)
                            else:
                                from wechatpy import create_reply

                                reply_obj = create_reply("弥娅正在思考中，请稍后再试...", msg)
                                return reply_obj if isinstance(reply_obj, str) else str(reply_obj)
                        except asyncio.TimeoutError:
                            logger.debug("[weixin_offacc] 被动回复超时，返回占位符")
                            from wechatpy import create_reply

                            reply_obj = create_reply("弥娅正在思考中，回复任意文字获取回复~", msg)
                            return reply_obj if isinstance(reply_obj, str) else str(reply_obj)
                        except Exception as e:
                            logger.error(f"[weixin_offacc] 被动回复异常: {e}", exc_info=True)
                            return "success"

            except Exception as e:
                logger.error(f"[weixin_offacc] webhook 处理异常: {e}", exc_info=True)

            return "success"

        return {
            "prefix": "/webhook/weixin_offacc",
            "routes": [
                ("GET", "", verify_get),
                ("POST", "", callback_post),
            ],
        }


# ====================================================================
#                     微信开放平台 (WeixinOC / 个人微信)
# ====================================================================


class WeixinOCPlatform(WebhookPlatform):
    """
    微信开放平台 (个人微信) — 长轮询模式

    通过 token 认证同步消息，无需 QR 码登录流程，
    token 需要提前通过其他方式获取。

    配置项:
        weixin_oc_base_url: API 基础地址 (默认 https://ilinkai.weixin.qq.com)
        weixin_oc_token:    认证 token
        weixin_oc_account_id: 账号 ID
        weixin_oc_poll_interval: 轮询间隔秒数 (默认 5)
    """

    platform_id = "weixin_oc"
    platform_name = "微信开放平台"
    health_check_interval = 60.0
    auto_reconnect = True

    def __init__(self, config=None):
        super().__init__(config)
        cfg = config or {}
        self._base_url = str(cfg.get("weixin_oc_base_url", "https://ilinkai.weixin.qq.com")).rstrip("/")
        self._token = str(cfg.get("weixin_oc_token", "")).strip() or None
        self._account_id = str(cfg.get("weixin_oc_account_id", "")).strip() or None
        self._poll_interval = max(
            3,
            int(cfg.get("weixin_oc_poll_interval", 5)),
        )
        self._poll_timeout_ms = int(cfg.get("weixin_oc_long_poll_timeout_ms", 25_000))
        self._api_timeout_ms = int(cfg.get("weixin_oc_api_timeout_ms", 15_000))
        self._last_sync_key = ""
        self._poll_task: Optional[asyncio.Task] = None
        self._http_session: Any = None
        self._shutdown_event = asyncio.Event()
        self._context_tokens: dict = {}

    async def _ensure_session(self):
        if self._http_session is None or getattr(self._http_session, "closed", True):
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=self._api_timeout_ms / 1000)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def _do_connect(self) -> bool:
        if not self._token:
            logger.warning("[weixin_oc] 未配置 weixin_oc_token，请通过 AstrBot 适配器或管理后台获取登录 token")
            return False

        try:
            import aiohttp

            await self._ensure_session()

            logger.info("[weixin_oc] 微信开放平台: 正在验证 token...")
            self._shutdown_event.clear()

            self._poll_task = asyncio.create_task(self._poll_loop())
            self._tasks.append(self._poll_task)
            logger.info("[weixin_oc] 微信开放平台已就绪")
            return True

        except ImportError:
            logger.error("[weixin_oc] 请安装 aiohttp: pip install aiohttp")
            return False
        except Exception as e:
            logger.error(f"[weixin_oc] 连接失败: {e}", exc_info=True)
            return False

    async def _do_disconnect(self):
        self._shutdown_event.set()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        self._poll_task = None

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

        self._last_sync_key = ""

    async def _do_health_check(self) -> bool:
        return self._poll_task is not None and not self._poll_task.done()

    async def _poll_loop(self):
        """长轮询消息同步循环"""
        logger.info("[weixin_oc] 长轮询消息同步已启动")
        consecutive_errors = 0

        while not self._shutdown_event.is_set():
            try:
                messages = await self._sync_messages()
                if messages:
                    consecutive_errors = 0
                    for msg in messages:
                        await self._handle_inbound_message(msg)
                else:
                    consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:
                    logger.debug(f"[weixin_oc] 轮询异常 (第{consecutive_errors}次): {e}")
                else:
                    logger.warning(f"[weixin_oc] 轮询持续失败 (第{consecutive_errors}次): {e}")
                await asyncio.sleep(min(self._poll_interval * (1 + consecutive_errors), 30))
                continue

            await asyncio.sleep(self._poll_interval)

        logger.info("[weixin_oc] 长轮询消息同步已停止")

    async def _sync_messages(self) -> list:
        """同步获取新消息"""
        session = await self._ensure_session()
        import aiohttp

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        payload = {
            "limit": 50,
            "sync_key": self._last_sync_key,
        }

        url = f"{self._base_url}/ilink/bot/sync_msg"
        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._poll_timeout_ms / 1000),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[weixin_oc] sync_msg 返回 {resp.status}")
                    return []

                data = await resp.json()
                ret = data.get("ret", -1)
                if ret != 0:
                    logger.debug(f"[weixin_oc] sync_msg ret={ret}")
                    return []

                msgs = data.get("msg_list", data.get("messages", []))
                if not msgs:
                    return []

                sync_key = data.get("sync_key", "")
                if sync_key:
                    self._last_sync_key = sync_key

                return msgs
        except asyncio.TimeoutError:
            return []
        except Exception:
            raise

    async def _handle_inbound_message(self, msg: dict):
        """处理接收到的单条消息"""
        try:
            msg_type = msg.get("msg_type", 0)
            if msg_type != 1:  # 1 = text message
                return

            items = msg.get("item_list", msg.get("items", []))
            if not items:
                return

            sender_id = str(msg.get("sender_id", msg.get("from_user", "")))
            if not sender_id:
                return

            text_parts = []
            from core.file_context import FileContext

            images: List[FileContext] = []
            files_ctx: List[FileContext] = []

            for item in items:
                if isinstance(item, dict):
                    item_type = item.get("type", 0)
                    if item_type == 1:  # text
                        text = item.get("text_item", {}).get("text", "")
                    elif item_type == 2:  # image
                        img_info = item.get("image", {})
                        cdn_url = img_info.get("cdn_url", "")
                        media_id = img_info.get("media_id", "") or item.get("media_id", "")
                        if cdn_url:
                            fctx = FileContext.from_image(
                                url=cdn_url,
                                file_name=f"weixin_oc_image_{media_id}.jpg",
                                file_id=media_id,
                            )
                            images.append(fctx)
                            text = f"[图片: {fctx.file_name}]" if fctx.file_url else "[图片]"
                        else:
                            text = "[图片]"
                    elif item_type == 3:  # voice
                        voice_info = item.get("voice", {})
                        media_id = item.get("media_id", "")
                        voice_url = voice_info.get("cdn_url", "")
                        if voice_url:
                            fctx = FileContext.from_voice(
                                url=voice_url,
                                file_name=f"weixin_oc_voice_{media_id}.amr",
                                file_id=media_id,
                            )
                            files_ctx.append(fctx)
                            text = f"[语音: {fctx.file_name}]" if fctx.file_url else "[语音]"
                        else:
                            text = "[语音]"
                    elif item_type == 4:  # file
                        file_info = item.get("file", {})
                        file_url = file_info.get("cdn_url", "") or file_info.get("file_url", "")
                        file_name = file_info.get("file_name", "") or file_info.get("name", "")
                        file_size = file_info.get("file_size", 0)
                        if file_url:
                            fctx = FileContext.from_file(
                                url=file_url,
                                file_name=file_name or f"weixin_oc_file_{id(item)}.bin",
                                file_size=file_size,
                            )
                            files_ctx.append(fctx)
                            text = f"[文件: {file_name}]" if file_name else "[文件]"
                        else:
                            text = "[文件]"
                    elif item_type == 5:  # video
                        video_info = item.get("video", {})
                        video_url = video_info.get("cdn_url", "") or video_info.get("video_url", "")
                        video_name = video_info.get("name", "")
                        if video_url:
                            fctx = FileContext.from_video(
                                url=video_url,
                                file_name=video_name or f"weixin_oc_video_{id(item)}.mp4",
                            )
                            files_ctx.append(fctx)
                            text = f"[视频: {video_name}]" if video_name else "[视频]"
                        else:
                            text = "[视频]"
                    else:
                        text = ""
                    if text:
                        text_parts.append(text)
                elif isinstance(item, str):
                    text_parts.append(item)

            content = "".join(text_parts)
            if not content.strip():
                return

            logger.info(f"[weixin_oc] 收到消息 from={sender_id} content={content[:100]}")

            response = await self.route_to_decision_hub(
                content=content,
                user_id=sender_id,
                message_type="private",
                images=images if images else None,
                files=files_ctx if files_ctx else None,
            )

            if response:
                await self._send_text_message(sender_id, response)

        except Exception as e:
            logger.error(f"[weixin_oc] 处理消息异常: {e}", exc_info=True)

    async def _send_text_message(self, user_id: str, text: str) -> bool:
        """发送文本消息"""
        if not self._token:
            return False
        try:
            session = await self._ensure_session()
            import aiohttp

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            }

            payload = {
                "to_user": user_id,
                "msg_type": 1,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }

            url = f"{self._base_url}/ilink/bot/send_msg"
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                ret = data.get("ret", -1)
                if ret != 0:
                    logger.warning(f"[weixin_oc] 发送消息失败: ret={ret}, errmsg={data.get('errmsg', '')}")
                    return False
                return True
        except Exception as e:
            logger.warning(f"[weixin_oc] 发送消息异常: {e}")
            return False
