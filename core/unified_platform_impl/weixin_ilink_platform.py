"""
弥娅微信 iLink 平台接入 (BasePlatform 方式)

直接使用 weixin-ilink-client SDK，通过 MessageMixin 路由到 DecisionHub。
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.WeixinIlink")


def _extract_weixin_ilink_reply(msg: Any) -> Optional[Dict]:
    """从 InboundMessage.raw 中提取引用/回复消息信息"""
    raw = getattr(msg, "raw", None)
    if not raw or not isinstance(raw, dict):
        return None

    # 策略1: 一级字段下直接找引用
    for key in (
        "quote_message",
        "quote_msg",
        "referenced_message",
        "reply_to",
        "reply_message",
        "quoted_message",
        "ref_message",
    ):
        quote = raw.get(key)
        if quote:
            return _build_reply_result(quote)

    # 策略2: context 子字段
    ctx = raw.get("context", {})
    if isinstance(ctx, dict):
        for key in ("quote_message", "quote_msg", "referenced_message", "reply_to"):
            quote = ctx.get(key)
            if quote:
                return _build_reply_result(quote)

    # 策略3: parent_id / root_id — 微信 iLink 的引用链
    # 注意：经实测，微信 iLink Bot API 的 parent_id/root_id 始终为空，不暴露引用数据
    parent_id = str(raw.get("parent_id", "") or "")
    root_id = str(raw.get("root_id", "") or "")
    ref_id = parent_id or root_id or ""
    msg_self_id = str(raw.get("message_id", "") or "")
    if ref_id and ref_id != msg_self_id:
        logger.info(
            "[weixin_ilink] 引用消息: parent_id=%s root_id=%s msg_id=%s", parent_id[:30], root_id[:30], msg_self_id[:30]
        )
        return {"reply_to_id": str(ref_id)}

    # 策略4: context_token 作为引用标记
    ctx_token = raw.get("context_token", "")
    if ctx_token and ctx_token != "":
        logger.debug("[weixin_ilink] context_token=%s, 但无直接引用内容", ctx_token[:60])

    return None


def _build_reply_result(quote: Any) -> Optional[Dict]:
    """从引用原始数据构建标准 reply 字典"""
    result = {}
    if isinstance(quote, dict):
        qt = quote.get("text", "") or quote.get("content", "") or ""
        qid = quote.get("message_id", "") or quote.get("msg_id", "") or ""
        quser = quote.get("from_user", "") or quote.get("sender", "") or ""
        if qt:
            result["reply_content"] = str(qt)
        if qid:
            result["reply_to_id"] = str(qid)
        if quser:
            result["reply_from"] = str(quser)
    elif isinstance(quote, str) and quote.strip():
        result["reply_content"] = quote.strip()

    return result if result else None


class WeixinIlinkPlatform(MessageMixin, BasePlatform):
    platform_id = "weixin_ilink"
    platform_name = "微信 iLink"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)

        self._base_url = str(self.config.get("base_url", "https://ilinkai.weixin.qq.com")).rstrip("/")
        self._cdn_base_url = str(self.config.get("cdn_base_url", "https://novac2c.cdn.weixin.qq.com/c2c")).rstrip("/")
        self._account_id: str | None = str(self.config.get("account_id", "")).strip() or None
        self._token: str | None = str(self.config.get("bot_token", "")).strip() or None
        self._user_id: str | None = str(self.config.get("user_id", "")).strip() or None

        self._client = None
        self._client_ready = False
        self._shutdown_event = asyncio.Event()
        self._message_task: asyncio.Task | None = None
        # iLink accepts individual uploads but can throttle several concurrent
        # sendmessage calls. Keep media sends ordered per account.
        self._media_send_lock = asyncio.Lock()
        self._last_media_send_at = 0.0
        try:
            configured_interval = float(self.config.get("media_send_interval", 0.6))
        except (TypeError, ValueError):
            configured_interval = 0.6
        self._media_send_interval = max(configured_interval, 0.0)

    async def _do_connect(self) -> bool:
        try:
            from weixin_ilink_client import (
                AsyncWeixinIlinkClient,
                ClientOptions,
                JsonCredentialStore,
                MemoryStateStore,
                WeixinCredentials,
                default_state_dir,
            )

            state_dir = str(self.config.get("state_dir", "")).strip()
            store_dir = Path(state_dir) if state_dir else default_state_dir()
            store_dir.mkdir(parents=True, exist_ok=True)

            credential_store = JsonCredentialStore(store_dir / "credentials.json")

            if not self._token or not self._account_id:
                try:
                    saved = await credential_store.get("weixin_ilink")
                    if saved:
                        self._account_id = saved.account_id
                        self._token = saved.bot_token
                        self._user_id = saved.user_id
                        if saved.base_url:
                            self._base_url = saved.base_url.rstrip("/")
                        logger.info("[weixin_ilink] 从缓存加载凭据: account=%s", self._account_id)
                except Exception as e:
                    logger.debug("[weixin_ilink] 无缓存凭据: %s", e)

                if not self._token:
                    acc_id, token, uid, url = self._load_fallback_credentials(store_dir)
                    if token:
                        self._account_id = acc_id
                        self._token = token
                        self._user_id = uid
                        if url:
                            self._base_url = url.rstrip("/")
                        logger.info(
                            "[weixin_ilink] 兜底凭据加载成功: account=%s",
                            self._account_id,
                        )

            if not self._token or not self._account_id or not self._user_id:
                logger.warning("[weixin_ilink] 未登录，请先运行: python scripts/weixin_ilink_login.py")
                return False

            credentials = WeixinCredentials(
                account_id=self._account_id,
                bot_token=self._token,
                base_url=self._base_url,
                user_id=self._user_id,
            )

            state_store = MemoryStateStore()

            options = ClientOptions(
                cdn_base_url=self._cdn_base_url,
                media_max_bytes=sys.maxsize,  # 不限制，交由微信实际能力决定
            )

            self._client = AsyncWeixinIlinkClient(
                credentials,
                state_store=state_store,
                options=options,
            )

            self._shutdown_event.clear()
            self._client_ready = False
            self._message_task = asyncio.create_task(self._run_message_loop())

            logger.info("[weixin_ilink] 已连接, account=%s", self._account_id)
            return True

        except Exception as e:
            logger.error("[weixin_ilink] 连接失败: %s", e, exc_info=True)
            return False

    async def _run_message_loop(self):
        from weixin_ilink_client.errors import SessionPausedError, WeixinIlinkError

        if not self._client:
            return

        async def on_message(msg):
            try:
                await self._handle_inbound_message(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "[weixin_ilink] 单条消息处理失败（已跳过，连接不受影响）: %s",
                    e,
                    exc_info=True,
                )

        while not self._shutdown_event.is_set():
            try:
                self._client_ready = True
                await self._client.run(on_message, stop_event=self._shutdown_event)
            except asyncio.CancelledError:
                break
            except SessionPausedError:
                logger.warning("[weixin_ilink] 会话暂停，等待恢复...")
                await asyncio.sleep(10)
            except WeixinIlinkError as e:
                logger.error("[weixin_ilink] iLink 错误: %s，5秒后重试", e)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("[weixin_ilink] 消息循环异常: %s，5秒后重试", e)
                await asyncio.sleep(5)
            finally:
                self._client_ready = False

    async def _handle_inbound_message(self, msg):
        from weixin_ilink_client import MessageItemType

        from_user_id = msg.from_user_id
        if not from_user_id:
            return

        from core.file_context import FileContext

        # 检测引用/回复消息
        reply_context = _extract_weixin_ilink_reply(msg)

        text_parts = []
        images: list = []
        files_ctx: list = []

        for item in msg.items or []:
            if item.type == MessageItemType.TEXT:
                t = (item.text or "").strip()
                if t:
                    text_parts.append(t)
            elif item.type == MessageItemType.IMAGE:
                text_parts.append("[图片]")
                fname = item.file_name or f"weixin_ilink_image_{getattr(msg, 'message_id', id(item))}.jpg"
                fctx = FileContext.from_image(
                    file_name=fname,
                    file_id=getattr(msg, "message_id", ""),
                )
                images.append(fctx)
                try:
                    media = await self._client.download_media(item)
                    if media and media.content:
                        fctx.file_data = media.content
                        fctx.mime_type = media.content_type or "image/jpeg"
                        fctx.file_name = media.file_name or fname
                        fctx.download_status = "done"  # type: ignore[assignment]
                except Exception as e:
                    logger.debug("[weixin_ilink] 图片下载失败: %s", e)
            elif item.type == MessageItemType.VOICE:
                text_parts.append("[语音]")
                fname = item.file_name or f"weixin_ilink_voice_{getattr(msg, 'message_id', id(item))}.amr"
                fctx = FileContext.from_voice(
                    file_name=fname,
                    file_id=getattr(msg, "message_id", ""),
                )
                files_ctx.append(fctx)
                try:
                    media = await self._client.download_media(item)
                    if media and media.content:
                        fctx.file_data = media.content
                        fctx.mime_type = media.content_type or "audio/amr"
                        fctx.file_name = media.file_name or fname
                        fctx.download_status = "done"  # type: ignore[assignment]
                except Exception as e:
                    logger.debug("[weixin_ilink] 语音下载失败: %s", e)
            elif item.type == MessageItemType.FILE:
                fname = item.file_name or f"weixin_ilink_file_{getattr(msg, 'message_id', id(item))}.bin"
                text_parts.append(f"[文件: {item.file_name}]" if item.file_name else "[文件]")
                fctx = FileContext.from_file(
                    file_name=fname,
                    file_id=getattr(msg, "message_id", ""),
                )
                files_ctx.append(fctx)
                try:
                    media = await self._client.download_media(item)
                    if media and media.content:
                        fctx.file_data = media.content
                        fctx.mime_type = media.content_type or "application/octet-stream"
                        fctx.file_name = media.file_name or fname
                        fctx.file_size = len(media.content)
                        fctx.download_status = "done"  # type: ignore[assignment]
                except Exception as e:
                    logger.debug("[weixin_ilink] 文件下载失败: %s", e)
            elif item.type == MessageItemType.VIDEO:
                fname = item.file_name or f"weixin_ilink_video_{getattr(msg, 'message_id', id(item))}.mp4"
                text_parts.append("[视频]")
                fctx = FileContext.from_video(
                    file_name=fname,
                    file_id=getattr(msg, "message_id", ""),
                )
                files_ctx.append(fctx)
                try:
                    media = await self._client.download_media(item)
                    if media and media.content:
                        fctx.file_data = media.content
                        fctx.mime_type = media.content_type or "video/mp4"
                        fctx.file_name = media.file_name or fname
                        fctx.file_size = len(media.content)
                        fctx.download_status = "done"  # type: ignore[assignment]
                except Exception as e:
                    logger.debug("[weixin_ilink] 视频下载失败: %s", e)
            else:
                logger.debug("[weixin_ilink] 未知消息类型: %s", item.type)

        text = "".join(text_parts)

        # 注入引用消息上下文
        extra = None
        if reply_context:
            quote_text = reply_context.get("reply_content", "")
            if quote_text:
                text = f'[引用"{quote_text}"] {text}' if text else f'[引用"{quote_text}"]'
            extra = reply_context

        if not text and not images and not files_ctx:
            return

        logger.debug("[weixin_ilink] 收到消息: %s → %s", from_user_id, text[:50] if text else "(纯媒体)")

        response = await self.route_to_decision_hub(
            content=text,
            user_id=from_user_id,
            user_name=from_user_id,
            message_type="private",
            is_at_bot=True,
            images=images if images else None,
            files=files_ctx if files_ctx else None,
            extra=extra,
        )

        if response and self._client and self._client_ready:
            try:
                await self._client.send_text(from_user_id, response)
            except Exception as e:
                logger.error("[weixin_ilink] 发送回复失败: %s", e)

    async def send_private_message(self, user_id: str, message: str) -> bool:
        """发送主动私聊消息 (v8.1: 含诊断日志 + 重试)"""
        if not self._client or not self._client_ready:
            logger.warning(
                "[weixin_ilink] 主动消息拒绝: client=%s, ready=%s",
                self._client is not None,
                self._client_ready,
            )
            return False
        uid = self._resolve_weixin_peer(str(user_id))
        msg_preview = message[:60]
        logger.info(
            "[weixin_ilink] 主动消息发送中: uid=%s, msg_len=%d, preview=%s",
            uid,
            len(message),
            msg_preview,
        )
        for attempt in range(2):
            try:
                await self._client.send_text(uid, message)
                logger.info("[weixin_ilink] 主动消息已发送 (attempt=%d): %s → %s", attempt + 1, uid, msg_preview)
                return True
            except Exception as e:
                logger.warning(
                    "[weixin_ilink] 主动消息发送失败 (attempt=%d/%d): uid=%s, error=%s",
                    attempt + 1,
                    2,
                    uid,
                    e,
                )
                if attempt == 0:
                    await asyncio.sleep(1.0)
        return False

    async def _do_disconnect(self):
        self._shutdown_event.set()
        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
        self._client_ready = False
        logger.info("[weixin_ilink] 已断开")

    async def _do_health_check(self) -> bool:
        return self._client_ready

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """微信 iLink 文件发送"""
        if not self._client or not self._client_ready:
            return False

        peer_id = self._resolve_weixin_peer(target)

        data = None
        if outbound_file.is_local and outbound_file.file_path:
            with open(outbound_file.file_path, "rb") as f:
                data = f.read()
        elif outbound_file.is_bytes and outbound_file.file_data:
            data = outbound_file.file_data

        if data:
            try:
                from weixin_ilink_client import MediaKind

                caption = (getattr(outbound_file, "caption", "") or "").strip() or None
                kind = MediaKind.IMAGE if outbound_file.is_image else MediaKind.FILE
                async with self._media_send_lock:
                    elapsed = time.monotonic() - self._last_media_send_at
                    if elapsed < self._media_send_interval:
                        await asyncio.sleep(self._media_send_interval - elapsed)
                    await self._client.send_media(
                        peer_id=peer_id,
                        content=data,
                        kind=kind,
                        file_name=outbound_file.file_name,
                        caption=caption,
                    )
                    self._last_media_send_at = time.monotonic()
                self._record_message_out()
                logger.info(f"[{self.platform_id}] 文件已发送: {outbound_file.file_name} -> {peer_id}")
                return True
            except Exception as e:
                error_code = getattr(e, "code", None)
                logger.warning(
                    "[%s] send_media 失败: file=%s peer=%s code=%s error=%s",
                    self.platform_id,
                    outbound_file.file_name,
                    peer_id,
                    error_code if error_code is not None else "-",
                    e,
                )
                return False

        return False

    @staticmethod
    def _resolve_weixin_peer(target: str) -> str:
        """解析微信 peer_id：纯数字 QQ 号 → 微信 iLink ID"""
        if not target:
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
                    for platform, id_list in ids.items():
                        if target in [str(i) for i in id_list]:
                            weixin_ids = ids.get("weixin_ilink", [])
                            if weixin_ids and weixin_ids[0]:
                                logger.info("[weixin_ilink] canonical %s → iLink ID %s", target, weixin_ids[0])
                                return str(weixin_ids[0])
        except Exception:
            pass
        return target

    @staticmethod
    def _load_fallback_credentials(store_dir: Path):
        import json

        fallback = store_dir / "credentials_fallback.json"
        if not fallback.exists():
            return
        try:
            data = json.loads(fallback.read_text())
            accounts = data.get("accounts", {})
            for alias, acc in accounts.items():
                logger.info(
                    "[weixin_ilink] 从兜底文件加载凭据: alias=%s, account=%s",
                    alias,
                    acc.get("account_id", ""),
                )
                return acc.get("account_id"), acc.get("bot_token"), acc.get("user_id"), acc.get("base_url", "")
        except Exception as e:
            logger.debug("[weixin_ilink] 兜底文件读取失败: %s", e)
        return None, None, None, None
