"""
OneBot / NapCat 平台适配器

基于 OneBot v11 反向 WebSocket 协议。
支持 QQ (NapCat、LLOneBot、Lagrange 等)。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.unified_platform.base import BasePlatform

from .message_mixin import MessageMixin

logger = logging.getLogger("Miya.Platform.OneBot")


class OneBotPlatform(MessageMixin, BasePlatform):
    """OneBot / NapCat 平台"""

    platform_id = "aiocqhttp"
    platform_name = "OneBot/NapCat"
    health_check_interval = 30.0
    auto_reconnect = False  # OneBot 监听循环自带重连，不触发系统级重连

    # 社交能力声明
    supports_like = True
    supports_poke = True
    supports_emoji_reaction = True
    supports_group_members = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BasePlatform.__init__(self, config)
        self._ws_url = self._read_ws_url()
        self._bot_qq = os.getenv("QQ_BOT_QQ", self.config.get("bot_qq", ""))
        self._ws: Optional[Any] = None
        self._connected = False
        self._shutting_down = False
        self._pending_echoes: Dict[str, asyncio.Future] = {}
        self._loaded_config: dict = {}
        self._process_locks: Dict[str, asyncio.Lock] = {}
        self._poke_cooldown: Dict[str, float] = {}  # user_id → last_poke_time
        self._hub_refs_set = False
        self._queue_initialized = False
        # 群聊忙时消息合并缓冲: group_id → [消息上下文, ...]（缓解多人同时@时处理不过来）
        self._pending_group_messages: Dict[str, list] = {}
        # 群成员缓存: group_id → (timestamp, [member_info_dict, ...])
        self._group_member_cache: Dict[int, tuple] = {}
        # 群文件上传缓存: group_id → [(user_id, file_name, file_size, timestamp), ...]
        self._recent_uploads: Dict[int, list] = {}
        # 文件/图片发送串行锁：NapCat 并发上传多文件易触发限流/失败
        self._file_send_lock = asyncio.Lock()
        # 事件消息后台任务集合（WS 接收循环不得被长耗时 AI 管线阻塞）
        self._event_tasks: set = set()

    @staticmethod
    def _read_ws_url() -> str:
        """从 .env 读取 OneBot WebSocket 地址"""
        ws_url = os.getenv("QQ_ONEBOT_WS_URL", "")
        if ws_url:
            return ws_url
        # 回退: 反向 WS 模式 — 弥娅监听，NapCat 主动连接
        return "ws://127.0.0.1:3001"

    @property
    def _config_data(self) -> dict:
        if not self._loaded_config:
            self._loaded_config = self._load_qq_config()
        return self._loaded_config

    def _load_qq_config(self) -> dict:
        """加载 qq_config.yaml 配置"""
        try:
            from pathlib import Path

            import yaml

            config_path = Path(__file__).parent.parent.parent / "config" / "qq_config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    full = yaml.safe_load(f) or {}
                    qq = full.get("qq", {})
                    return {
                        "superadmin_qq": os.getenv("QQ_SUPERADMIN_QQ", ""),
                        "group_whitelist": qq.get("access_control", {}).get("group_whitelist", []),
                        "group_blacklist": qq.get("access_control", {}).get("group_blacklist", []),
                        "user_whitelist": qq.get("access_control", {}).get("user_whitelist", []),
                        "user_blacklist": qq.get("access_control", {}).get("user_blacklist", []),
                        "access_control_enabled": qq.get("access_control", {}).get("enabled", False),
                        "max_message_length": qq.get("commands", {}).get("qq_max_message_length", 200),
                        "image_analysis_enabled": qq.get("image_recognition", {})
                        .get("ai_analysis", {})
                        .get("enabled", True),
                        "image_analysis_timeout": qq.get("image_recognition", {})
                        .get("ai_analysis", {})
                        .get("timeout", 30),
                    }
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 加载 qq_config.yaml 失败: {e}")
        return {}

    # ============ 决策中心引用登记 ============

    def _ensure_decision_hub_refs(self):
        """一次性设置决策中心引用 & 启动调度器 & 注册 M-Link 节点"""
        self._hub_refs_set = True
        try:
            miya = getattr(self, "_miya_core", None)
            if not miya or not hasattr(miya, "decision_hub"):
                return
            miya.decision_hub.onebot_client = self
            miya.decision_hub.qq_net = self
            logger.info(f"[{self.platform_id}] DecisionHub 引用已登记")
        except Exception as e:
            logger.debug(f"[{self.platform_id}] DecisionHub 引用登记失败: {e}")

        # 启动调度器（定时任务 / 主动聊天 / 时段问候）
        try:
            miya = getattr(self, "_miya_core", None)
            if miya and hasattr(miya, "scheduler") and miya.scheduler:
                from hub.scheduler import set_global_scheduler

                miya.scheduler.onebot_client = self
                miya.scheduler.main_event_loop = asyncio.get_running_loop()
                set_global_scheduler(miya.scheduler)
                # 注入跨平台分发器，让定时任务支持所有平台（微信/QQ/飞书/Telegram 等）
                if (
                    hasattr(miya, "decision_hub")
                    and miya.decision_hub
                    and getattr(miya.scheduler, "cross_platform_sender", None) is None
                ):
                    miya.scheduler.cross_platform_sender = miya.decision_hub._dispatch_proactive_message
                    logger.info(f"[{self.platform_id}] 调度器跨平台分发器已注入")
                if not getattr(miya.scheduler, "_started", False):
                    miya.scheduler.start_background()
                    logger.info(f"[{self.platform_id}] 调度器已启动")
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 调度器启动失败: {e}")

        # 注册 M-Link 节点
        try:
            miya = getattr(self, "_miya_core", None)
            if miya and hasattr(miya, "mlink") and miya.mlink:
                miya.mlink.register_node(
                    "onebot_platform",
                    [
                        "onebot_group_chat",
                        "onebot_private_chat",
                        "onebot_command",
                        "onebot_message_history",
                        "onebot_poke",
                        "onebot_multimedia",
                        "onebot_image_analysis",
                    ],
                )
                logger.info(f"[{self.platform_id}] M-Link 节点已注册")
        except Exception as e:
            logger.debug(f"[{self.platform_id}] M-Link 节点注册失败: {e}")

    # ============ 访问控制 ============

    def _is_group_allowed(self, group_id: str) -> bool:
        cfg = self._config_data
        if not cfg.get("access_control_enabled", False):
            return True
        try:
            gid = int(group_id)
        except ValueError:
            return True
        blacklist = cfg.get("group_blacklist", [])
        if gid in blacklist:
            logger.debug(f"[{self.platform_id}] 群黑名单拦截: {gid}")
            return False
        whitelist = cfg.get("group_whitelist", [])
        if whitelist:
            return gid in whitelist
        return True

    def _is_user_allowed(self, user_id: str) -> bool:
        cfg = self._config_data
        if not cfg.get("access_control_enabled", False):
            return True
        try:
            uid = int(user_id)
        except ValueError:
            return True
        blacklist = cfg.get("user_blacklist", [])
        if uid in blacklist:
            logger.debug(f"[{self.platform_id}] 用户黑名单拦截: {uid}")
            return False
        whitelist = cfg.get("user_whitelist", [])
        if whitelist:
            return uid in whitelist
        return True

    # ============ @ 检测 ============

    def _is_at_bot(self, message, bot_qq: str) -> bool:
        if isinstance(message, str):
            return f"@{bot_qq}" in message or f"[CQ:at,qq={bot_qq}]" in message
        for seg in message:
            if isinstance(seg, dict) and seg.get("type") == "at":
                at_qq = str(seg.get("data", {}).get("qq", ""))
                if at_qq == bot_qq:
                    return True
        return False

    def _extract_at_list(self, message) -> list:
        import re

        at_list = []
        if isinstance(message, str):
            for m in re.finditer(r"\[CQ:at,qq=(\d+)\]", message):
                with contextlib.suppress(ValueError):
                    at_list.append(int(m.group(1)))
            return at_list
        for seg in message:
            if isinstance(seg, dict) and seg.get("type") == "at":
                at_qq = seg.get("data", {}).get("qq")
                if at_qq:
                    with contextlib.suppress(ValueError, TypeError):
                        at_list.append(int(at_qq))
        return at_list

    # ============ 群名解析 (OneBot 专用) ============

    async def _resolve_group_name(self, group_id: str) -> str:
        try:
            info = await self._call_onebot_api("get_group_info", {"group_id": int(group_id)})
            if isinstance(info, dict):
                return info.get("group_name", "")
        except Exception:
            pass
        return ""

    async def _do_connect(self) -> bool:
        try:
            import aiohttp

            self._shutting_down = False

            # 清理已死亡的任务，防止 accumulate dead tasks
            self._tasks[:] = [t for t in self._tasks if not t.done()]

            # 如果已有后台任务在运行，不重复创建
            if self._tasks:
                self._connected = True
                return True

            self._ws = None
            self._connected = True  # 乐观标记，实际连接由后台任务管理

            async def listen_loop():
                retry_delay = 1
                while not self._shutting_down:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.ws_connect(self._ws_url) as ws:
                                self._ws = ws
                                self._connected = True
                                logger.info(f"[{self.platform_id}] 已连接到 {self._ws_url}")
                                retry_delay = 1

                                async for msg in ws:
                                    if msg.type == aiohttp.WSMsgType.TEXT:
                                        data = json.loads(msg.data)
                                        # 处理 echo 响应（必须优先、即时读取）
                                        echo = data.get("echo")
                                        if echo and echo in self._pending_echoes:
                                            self._pending_echoes.pop(echo).set_result(data)
                                            continue
                                        # 事件消息：交给后台任务处理。若在此处直接 await，
                                        # 长耗时的 AI 决策管线会阻塞整个接收循环，
                                        # 导致 echo 应答无法读取、所有 API 调用超时
                                        await self._dispatch_event(data)
                                    elif msg.type == aiohttp.WSMsgType.ERROR:
                                        logger.error(f"[{self.platform_id}] WebSocket 错误")
                                        break

                    except asyncio.CancelledError:
                        logger.info(f"[{self.platform_id}] listen_loop 任务取消")
                        break
                    except Exception as e:
                        if self._shutting_down:
                            break
                        if retry_delay <= 4:
                            logger.warning(f"[{self.platform_id}] 连接断开: {e}, {retry_delay}s 后重连")
                        else:
                            logger.debug(f"[{self.platform_id}] 连接断开: {e}, {retry_delay}s 后重连")
                        self._connected = False
                        self._ws = None
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)

                self._connected = False
                self._ws = None

            self._tasks.append(asyncio.create_task(listen_loop()))
            await asyncio.sleep(0.5)
            return True

        except ImportError:
            logger.error(f"[{self.platform_id}] 请安装 aiohttp")
            return False
        except Exception as e:
            logger.error(f"[{self.platform_id}] 连接异常: {e}", exc_info=True)
            return False

    async def _handle_onebot_message(self, data: Dict):
        """处理 OneBot 消息"""
        try:
            post_type = data.get("post_type", "")
            if post_type == "message":
                await self._handle_chat_message(data)
            elif post_type == "notice":
                await self._handle_notice(data)
            elif post_type == "request":
                logger.debug(f"[{self.platform_id}] 请求: {data.get('request_type')}")
        except Exception as e:
            logger.error(f"[{self.platform_id}] 消息处理异常: {e}")

    async def _dispatch_event(self, data: Dict):
        """将 OneBot 事件交给后台任务处理（不阻塞 WS 接收循环）

        同一会话内的消息顺序由 _process_locks（按会话加锁）保证；
        不同会话可并发处理。任务异常已在此兜底，避免“从未被检索的异常”。

        高并发优化：
        - 群聊消息先做触发预过滤，确定不会触发弥娅回复的消息直接丢弃，
          避免无意义地占用锁与 AI 管线（DecisionHub 内部仍有同款兜底判定）。
        - 事件任务数超限时丢弃低优先级群消息，防止刷屏时任务无限堆积。
        """
        if not self._should_dispatch(data):
            return
        if len(self._event_tasks) >= self._max_event_tasks():
            # 仅丢弃群消息（私聊与 notice 事件始终保留）
            if data.get("post_type") == "message" and data.get("message_type") == "group":
                logger.warning(f"[{self.platform_id}] 事件任务积压({len(self._event_tasks)})，丢弃群消息")
                return

        async def _run():
            try:
                await self._handle_onebot_message(data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[{self.platform_id}] 事件后台处理异常: {e}", exc_info=True)

        task = asyncio.create_task(_run())
        self._event_tasks.add(task)
        task.add_done_callback(self._event_tasks.discard)

    def _should_dispatch(self, data: Dict) -> bool:
        """群聊消息触发预过滤：确定不会触发弥娅回复的群消息直接丢弃。

        保留条件（任一满足）：
        - 非群聊事件（私聊/通知/请求）
        - @了机器人 / 机器人QQ未知（保守放行）
        - 超级管理员发送
        - 包含自动回复关键词（弥娅/亲爱的等，与决策层一致）
        - 包含引用回复段（需查询引用内容才能判断是否回复弥娅）
        - 包含媒体段（图片/文件/语音，需要进一步解析）
        - 非“仅关键词触发”模式下，用户仍在与弥娅活跃对话

        注意：斜杠命令本身不构成群聊触发条件 —— 群聊中必须@或带触发关键词
        才能执行命令（与决策层群聊命令守卫一致）。
        """
        try:
            if data.get("post_type") != "message":
                return True
            if data.get("message_type", "private") != "group":
                return True

            message = data.get("message", data.get("raw_message", ""))
            bot_qq = str(self.config.get("bot_qq") or data.get("self_id", "") or "")
            if self._is_at_bot(message, bot_qq) if bot_qq else True:
                return True

            sender = data.get("sender", {})
            user_id = str(sender.get("user_id", ""))

            # 超管豁免
            try:
                from core.unified_permission import get_permission_engine

                if get_permission_engine().is_superadmin(user_id, platform=self.platform_id):
                    return True
            except Exception:
                pass

            # 解析文本内容与特殊消息段
            content = ""
            has_media = False
            has_reply = False
            if isinstance(message, list):
                for seg in message:
                    seg_type = (seg or {}).get("type", "")
                    if seg_type == "text":
                        content += (seg.get("data") or {}).get("text", "")
                    elif seg_type in ("image", "video", "record", "file"):
                        has_media = True
                    elif seg_type == "reply":
                        has_reply = True
            else:
                content = str(message)
                if any(tag in content for tag in ("[CQ:image", "[CQ:video", "[CQ:record", "[CQ:file", "[CQ:reply")):
                    has_media = True

            if has_media or has_reply:
                return True

            # 触发关键词（与决策层群聊关键词检测一致）
            try:
                from core.text_loader import get_chatbot_keywords

                content_lower = content.lower()
                if any(kw.lower() in content_lower for kw in get_chatbot_keywords()):
                    return True
            except Exception:
                pass

            # 活跃对话（仅非“仅关键词触发”模式）
            try:
                from config.config_utils import get_qq_config

                keyword_only = bool(
                    get_qq_config("qq", "features", "passive_chat_keyword_only", default=True)
                )
                if not keyword_only:
                    from memory.diteng_listener import get_diting

                    if get_diting().is_user_active_with_bot(str(data.get("group_id", "")), user_id):
                        return True
            except Exception:
                return True  # 谛听状态不可用时保守放行

            logger.debug(f"[{self.platform_id}] 群消息预过滤丢弃: {content[:40]}")
            return False
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 触发预过滤异常，保守放行: {e}")
            return True

    @staticmethod
    def _max_event_tasks() -> int:
        """事件后台任务数上限（从 qq_config 读取）"""
        try:
            from config.config_utils import get_qq_config

            return int(get_qq_config("qq", "performance", "max_event_tasks", default=100) or 100)
        except Exception:
            return 100

    def _notify_scheduler_online(self, user_id: str):
        """通知调度器用户上线（条件触发支持）"""
        try:
            from hub.scheduler import get_global_scheduler

            s = get_global_scheduler()
            if s and s._running:
                s.notify_user_online(user_id)
                logger.debug(f"[{self.platform_id}] 调度器已通知: 用户 {user_id} 在线")
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 通知调度器失败: {e}")

    async def _handle_notice(self, data: Dict):
        """处理通知事件（拍一拍等）"""
        notice_type = data.get("notice_type", "")
        if notice_type == "notify":
            sub_type = data.get("sub_type", "")
            if sub_type == "poke":
                target_id = str(data.get("target_id", ""))
                user_id = str(data.get("user_id", ""))
                self_id = str(data.get("self_id", ""))
                group_id = str(data.get("group_id", "")) if data.get("group_id") else ""

                bot_qq = self.config.get("bot_qq", "") or self_id
                is_bot_poked = str(target_id) == str(bot_qq) or str(target_id) == str(self_id)

                logger.info(f"[{self.platform_id}] 拍一拍: target={target_id}, bot_qq={bot_qq}, is_bot={is_bot_poked}")

                if is_bot_poked:
                    # 拍一拍冷却 (15s)
                    now = asyncio.get_event_loop().time()
                    last = self._poke_cooldown.get(user_id, 0)
                    if now - last < 15:
                        logger.debug(f"[{self.platform_id}] 拍一拍冷却: {user_id}")
                        return
                    self._poke_cooldown[user_id] = now

                    # 第一层：瞬间回复固定文字 + 随机表情包
                    from core.config_loader import load_text_config

                    poke_text = load_text_config().get("poke_responses", {}).get("local_emoji", "")
                    await self._send_onebot_poke_reply(user_id, group_id, poke_text)

                    # 第二层：异步走 AI 生成情感回复
                    content = f"[拍一拍] 用户 {user_id} 拍了拍你"
                    ai_response = await self.route_to_decision_hub(
                        content=content,
                        user_id=user_id,
                        user_name=user_id,
                        message_type="private" if not group_id else "group",
                        group_id=group_id,
                    )
                    if ai_response and self._ws and self._connected:
                        action = "send_group_msg" if group_id else "send_private_msg"
                        target = "group_id" if group_id else "user_id"
                        target_val = int(group_id) if group_id else int(user_id)
                        await self._ws.send_str(
                            json.dumps(
                                {
                                    "action": action,
                                    "params": {
                                        target: target_val,
                                        "message": [
                                            {
                                                "type": "text",
                                                "data": {"text": ai_response},
                                            }
                                        ],
                                    },
                                }
                            )
                        )
            else:
                logger.info(f"[{self.platform_id}] notify: {sub_type}")
                # input_status = 对方正在输入 → 通知调度器用户在线
                if sub_type == "input_status":
                    user_id = str(data.get("user_id", ""))
                    if user_id:
                        self._notify_scheduler_online(user_id)
        elif notice_type in ("group_increase", "group_decrease"):
            logger.info(f"[{self.platform_id}] 群变动: {notice_type}")
        elif notice_type == "group_upload":
            await self._handle_group_upload(data)
        else:
            logger.info(f"[{self.platform_id}] 通知: {notice_type}")

    async def _handle_group_upload(self, data: Dict):
        """处理群文件上传通知，缓存文件信息并自动下载到本地"""
        try:
            group_id = int(data.get("group_id", 0))
            user_id = str(data.get("user_id", ""))
            file_info = data.get("file", {})
            file_name = file_info.get("name", "")
            file_size = file_info.get("size", 0)
            file_id = file_info.get("id", "")
            busid = file_info.get("busid", 0)

            if not group_id or not file_name:
                return

            entry = {
                "user_id": user_id,
                "file_name": file_name,
                "file_size": file_size,
                "file_id": file_id,
                "busid": busid,
                "timestamp": time.time(),
                "local_path": "",  # 下载后填充
            }

            # 尝试自动下载文件到 Miya 内部目录
            try:
                url = await self.get_group_file_url(group_id, file_id)
                if url:
                    download_dir = Path(__file__).resolve().parent.parent.parent / "data" / "downloads"
                    download_dir.mkdir(parents=True, exist_ok=True)
                    local_path = str(download_dir / file_name)
                    success = await self.download_group_file(url, local_path)
                    if success and Path(local_path).exists():
                        entry["local_path"] = local_path
                        logger.info(f"[{self.platform_id}] 群文件已自动下载: {file_name} → {local_path}")
            except Exception as e:
                logger.debug(f"[{self.platform_id}] 自动下载群文件失败: {e}")

            if group_id not in self._recent_uploads:
                self._recent_uploads[group_id] = []
            self._recent_uploads[group_id].append(entry)

            # 只保留最近 30 分钟内的上传
            cutoff = time.time() - 1800
            self._recent_uploads[group_id] = [e for e in self._recent_uploads[group_id] if e["timestamp"] > cutoff]

            logger.info(f"[{self.platform_id}] 群文件上传缓存: group={group_id}, user={user_id}, file={file_name}")
        except Exception as e:
            logger.warning(f"[{self.platform_id}] 处理群文件上传失败: {e}")

    def _get_recent_uploads(self, group_id: int, user_id: str = "") -> list:
        """获取最近的群文件上传记录"""
        uploads = self._recent_uploads.get(group_id, [])
        if user_id:
            uploads = [u for u in uploads if u["user_id"] == user_id]
        # 只返回最近 5 分钟内的
        cutoff = time.time() - 300
        return [u for u in uploads if u["timestamp"] > cutoff]

    async def _send_onebot_poke_reply(self, user_id: str, group_id: str, text: str):
        """拍一拍回复：文字 + data/emoji 随机图"""
        import random
        from pathlib import Path

        is_group = bool(group_id)
        action = "send_group_msg" if is_group else "send_private_msg"
        target = "group_id" if is_group else "user_id"
        target_val = int(group_id) if is_group else int(user_id)

        logger.info(f"[{self.platform_id}] 发送拍一拍回复: {text[:30]}...")
        await self._ws.send_str(
            json.dumps(
                {
                    "action": action,
                    "params": {
                        target: target_val,
                        "message": [{"type": "text", "data": {"text": text}}],
                    },
                }
            )
        )
        try:
            emoji_dir = Path(__file__).parent.parent.parent / "data" / "emoji"
            images = (
                [p for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif") for p in emoji_dir.rglob(ext)]
                if emoji_dir.exists()
                else []
            )
            if images:
                img = str(random.choice(images).absolute())
                logger.info(f"[{self.platform_id}] 发送随机表情: {img[-30:]}")
                await self._ws.send_str(
                    json.dumps(
                        {
                            "action": action,
                            "params": {
                                target: target_val,
                                "message": [{"type": "image", "data": {"file": img}}],
                            },
                        }
                    )
                )
        except Exception as e:
            logger.warning(f"[{self.platform_id}] emoji发送失败: {e}")

    # 发送类（非幂等）动作：echo 超时时消息可能已经送达，禁止 HTTP 重发回退
    _SEND_ACTIONS = {
        "send_private_msg",
        "send_group_msg",
        "send_like",
        "group_poke",
        "friend_poke",
        "set_msg_emoji_like",
        "upload_group_file",
        "upload_private_file",
        "delete_msg",
        "set_group_ban",
    }

    async def _call_onebot_api(self, action: str, params: Dict, timeout: float = 3.0) -> Optional[Dict]:
        """调用 OneBot API — 优先 WebSocket echo；查询类动作失败才回退 HTTP。

        发送类动作（消息/文件/点赞/拍一拍）非幂等：echo 超时并不意味着发送失败
        （NapCat 上传图片/文件后才应答，耗时常超过 3 秒），此时通过 HTTP 重发
        会造成群聊/私聊收到重复消息。因此发送类动作：
        - 使用更长的 echo 超时（15s）
        - 永不回退 HTTP 重发
        - 超时时返回 {"echo_timeout": True} 标记，视为"结果未知但已处理"
        """
        if not self._ws or not self._connected:
            return None

        is_send = action in self._SEND_ACTIONS
        effective_timeout = 15.0 if is_send else timeout
        echo = f"miya_{action}_{id(params)}"
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_echoes[echo] = future
        try:
            await self._ws.send_str(
                json.dumps(
                    {
                        "action": action,
                        "params": params,
                        "echo": echo,
                    }
                )
            )
            result = await asyncio.wait_for(future, timeout=effective_timeout)
            if result and result.get("status") == "ok":
                return result.get("data")
            if is_send:
                # NapCat 明确返回失败状态 → 不重试，避免重复发送
                return None
        except asyncio.TimeoutError:
            if is_send:
                logger.warning(
                    f"[{self.platform_id}] {action} echo 超时({effective_timeout:.0f}s)："
                    f"消息可能已送达，跳过 HTTP 重发以避免重复发送"
                )
                return {"status": "ok", "data": {"echo_timeout": True}}
        except Exception as e:
            if is_send:
                logger.warning(f"[{self.platform_id}] {action} WS 发送异常，跳过 HTTP 重发: {e}")
                return None
        finally:
            self._pending_echoes.pop(echo, None)

        # 查询类动作：WS 失败时回退 HTTP API (NapCat 默认 port 3000)
        try:
            import aiohttp

            http_url = f"http://127.0.0.1:3000/{action}"
            async with (
                aiohttp.ClientSession() as session,
                session.post(http_url, json=params, timeout=aiohttp.ClientTimeout(total=3)) as resp,
            ):
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "ok":
                        return data.get("data")
        except Exception:
            pass
        return None

    async def _handle_chat_message(self, data: Dict):
        """处理聊天消息 (v2 — 完整功能迁移自 qq_main.py)"""
        import re as _re

        msg_type = data.get("message_type", "private")
        sender = data.get("sender", {})
        raw_message = data.get("raw_message", data.get("message", ""))

        # === 1. 基础信息 ===
        user_id = str(sender.get("user_id", ""))
        sender_card = sender.get("card", "")
        sender_nickname = sender.get("nickname", "")
        user_name = sender_card or sender_nickname or user_id
        group_id_str = str(data.get("group_id", ""))
        bot_qq = str(self.config.get("bot_qq") or data.get("self_id", "") or "")

        # === 2. 自身消息过滤 ===
        if user_id and bot_qq and str(user_id) == str(bot_qq):
            return

        # === 2.5. 决策中心引用登记（一次性） ===
        if not self._hub_refs_set:
            self._ensure_decision_hub_refs()

        # === 3. 群聊 / 用户黑白名单 ===
        if group_id_str and not self._is_group_allowed(group_id_str):
            return
        if not self._is_user_allowed(user_id):
            return

        # === 4. 发送者角色 ===
        sender_role = sender.get("role", "member")
        sender.get("title", "")

        # === 5. @检测 + at列表 ===
        # 优先使用结构化 message 数组（现代 OneBot 的 raw_message 不含 CQ 码）
        message_array = data.get("message", raw_message)
        is_at_bot = self._is_at_bot(message_array, bot_qq) if bot_qq else True
        at_list = self._extract_at_list(message_array)

        # === 6. 消息段解析（text / reply / image / file / face） ===
        reply_id = ""
        image_segments = []
        voice_segments = []
        file_segments = []
        face_only = False
        content = ""

        if isinstance(raw_message, list):
            face_seg_count = 0
            for p in raw_message:
                seg_type = p.get("type", "")
                seg_data = p.get("data", {})
                if seg_type == "text":
                    content += seg_data.get("text", "")
                elif seg_type == "reply":
                    reply_id = str(seg_data.get("id", ""))
                elif seg_type == "image":
                    image_segments.append(p)
                elif seg_type == "file":
                    file_segments.append(
                        {
                            "file_id": seg_data.get("id", seg_data.get("file", "")),
                            "name": seg_data.get("name", ""),
                            "size": seg_data.get("size", 0),
                            "file_type": seg_data.get("type", ""),
                        }
                    )
                elif seg_type == "face":
                    face_seg_count += 1
                elif seg_type == "video":
                    image_segments.append(p)  # 视频同图片处理
                elif seg_type == "record":
                    voice_segments.append(p)
            # 是否纯表情消息
            non_face = [p for p in raw_message if p.get("type") != "face"]
            face_only = face_seg_count > 0 and not non_face
        else:
            content = str(raw_message)
            reply_match = _re.search(r"\[CQ:reply,id=(\d+)\]", content)
            if reply_match:
                reply_id = reply_match.group(1)
            # 从 CQ 字符串提取图片
            if "[CQ:image" in content:
                cq_images = _re.findall(r"\[CQ:image,file=([^,\]]+)", content)
                for fid in cq_images:
                    image_segments.append({"type": "image", "data": {"file": fid}})
            content = _re.sub(r"\[CQ:[^\]]+\]", "", content).strip()

        content = content.strip()

        # === 7. 超级管理员检测 ===
        is_owner = False
        try:
            from core.unified_permission import get_permission_engine

            is_owner = get_permission_engine().is_superadmin(user_id, platform=self.platform_id)
        except Exception:
            pass

        # === 8. 自动保存所有图片（在任何拦截之前） ===
        has_direct_images = bool(image_segments)
        if has_direct_images:
            asyncio.ensure_future(self._auto_save_images(image_segments, user_id))
            # 字符串格式的 CQ 图片也保存（可能在过滤前漏掉）
        if isinstance(raw_message, str) and "[CQ:image" in raw_message:
            asyncio.ensure_future(self._auto_save_string_images(raw_message, user_id))

        # === 9. 图片 / 表情预过滤（纯图片且非@非超管的群消息跳过） ===
        if (
            msg_type == "group"
            and not is_at_bot
            and not is_owner
            and has_direct_images
            and (not content or content in ("[图片]", "[动画表情]", ""))
        ):
            logger.debug(f"[{self.platform_id}] 预过滤纯图片群消息: group={group_id_str}")
            return
        if msg_type == "group" and not is_at_bot and not is_owner and face_only and not content:
            logger.debug(f"[{self.platform_id}] 预过滤纯表情群消息: group={group_id_str}")
            return

        # === 9. 直接图片 AI 视觉分析 ===
        extra = {}
        extra["at_list"] = at_list
        if at_list and group_id_str and msg_type == "group":
            names = await self.resolve_at_names(int(group_id_str), at_list)
            if names:
                extra["at_names"] = names
        has_media = has_direct_images

        if has_direct_images and not reply_id:
            # 直接发送的图片（非引用）→ 下载 + 视觉分析
            for seg in image_segments[:2]:
                img_data = seg.get("data", {})
                image_bytes = await self._download_reference_image(img_data)
                if not image_bytes:
                    continue
                asyncio.ensure_future(self._auto_save_image_bytes(image_bytes, user_id, img_data))
                try:
                    from core.multi_vision_analyzer import get_vision_analyzer

                    analyzer = await get_vision_analyzer()
                    result = await analyzer.analyze_image(image_bytes)
                    if result.success:
                        extra["image_analysis"] = result.to_context_dict()
                        extra["has_image"] = True
                        extra["has_media"] = True
                        has_media = True
                        if not content:
                            content = f"[图片]"
                        # 视觉融合 — 注入感知上下文
                        try:
                            from core.miya_multimodal_fusion import get_multimodal_fusion

                            fusion = get_multimodal_fusion()
                            fusion.process_qq_image(image_bytes, image_url="")
                        except Exception:
                            pass
                    break
                except Exception as e:
                    logger.debug(f"[{self.platform_id}] 直接图片分析失败: {e}")

        # === 语音消息处理: 下载 + AP听觉 + STT ===
        if voice_segments:
            for seg in voice_segments[:2]:
                try:
                    voice_bytes = await self._download_reference_image(seg.get("data", {}))
                    if voice_bytes:
                        from core.miya_multimodal_fusion import get_multimodal_fusion

                        fusion = get_multimodal_fusion()
                        info = fusion.process_qq_voice(voice_bytes)
                        if info.get("transcript"):
                            content = f"[语音: {info['transcript']}] " + content
                        elif info.get("has_voice"):
                            content = f"[语音 {info['duration_ms']:.0f}ms] " + content
                        break
                except Exception as e:
                    logger.debug(f"[{self.platform_id}] 语音处理失败: {e}")

        # === 10. 自动保存直接图片 ===
        if has_direct_images:
            asyncio.ensure_future(self._auto_save_images(image_segments, user_id))

        # === 11. 文件附件 ===
        if file_segments:
            extra["files"] = file_segments
            has_media = True

        # === 11b. 群文件上传引用检测 ===
        # QQ群文件没有本地路径，需要AI先用 group_file_downloader 下载再 analyze_file
        # 这里注入文件元信息为文本提示，让AI知道有文件需要下载分析
        if not file_segments and msg_type == "group" and group_id_str:
            file_keywords = ("文件", "文档", "分析", "看看", "附件", "pdf", "doc", "xls", "ppt", "txt")
            if any(kw in content.lower() for kw in file_keywords):
                recent = self._get_recent_uploads(int(group_id_str), user_id)
                if recent:
                    latest = recent[-1]
                    local = latest.get("local_path", "")
                    if local and Path(local).exists():
                        hint = (
                            f"\n[系统提示] 用户刚上传了文件 '{latest['file_name']}'，"
                            f"已自动下载到本地: {local}"
                            f"\n可直接使用 analyze_file 工具分析，file_path='{local}'"
                        )
                        content = content + hint
                    else:
                        hint = (
                            f"\n[系统提示] 用户 {user_id} 在 {latest['timestamp']:.0f} 秒前上传了群文件: "
                            f"'{latest['file_name']}' ({latest['file_size']} 字节)"
                            f"\n如需分析此文件，请使用 group_file_downloader 工具下载，"
                            f"参数: group_id={group_id_str}, file_name='{latest['file_name']}'"
                        )
                        content = content + hint
                    has_media = True
                    logger.info(f"[{self.platform_id}] 关联最近上传文件: {latest['file_name']} → 消息 '{content[:30]}'")
                else:
                    # 没有缓存的上传记录，提示用户先上传
                    content = content + (
                        f"\n[系统提示] 用户提到了'文件'，但未检测到最近的文件上传。"
                        f"请询问用户具体要分析哪个文件，或让用户先上传文件到群聊。"
                    )

        # === 纯图片消息拦截（无文字、非引用）→ 不触发对话 ===
        # 单独发送图片时不回复，只有"图片 + 文字"一起发送才回复
        if has_direct_images and not reply_id and not voice_segments and (not content or content == "[图片]"):
            logger.debug(f"[{self.platform_id}] 纯图片消息（无文字）不触发对话")
            return

        if not content and not has_media and not reply_id:
            return

        # === 12. 引用消息处理（文本 / 图片视觉分析） ===
        if reply_id:
            logger.info(f"[{self.platform_id}] 尝试获取引用: id={reply_id}")
            reply_data = await self._call_onebot_api("get_msg", {"message_id": int(reply_id)})
            if reply_data:
                logger.info(f"[{self.platform_id}] 引用获取成功: {str(reply_data)[:80]}")
                reply_data.get("sender", {}).get("nickname", "")
                reply_raw = reply_data.get("message", "")
                # 调试日志
                logger.debug(
                    f"[{self.platform_id}] reply_raw type={type(reply_raw).__name__}, "
                    f"len={len(reply_raw) if hasattr(reply_raw, '__len__') else 'N/A'}"
                )
                # reply_to_bot 检测
                reply_sender_id = str(reply_data.get("sender", {}).get("user_id", ""))
                extra["reply_to_bot"] = reply_sender_id == bot_qq
                # 提取引用文本
                reply_content = ""
                if isinstance(reply_raw, list):
                    reply_content = "".join(
                        s.get("data", {}).get("text", "") for s in reply_raw if s.get("type") == "text"
                    )
                    # 同时提取引用消息中的文件信息
                    for s in reply_raw:
                        if s.get("type") == "file":
                            sd = s.get("data", {})
                            file_segments.append(
                                {
                                    "file_id": sd.get("id", sd.get("file", "")),
                                    "name": sd.get("name", ""),
                                    "size": sd.get("size", 0),
                                    "file_type": sd.get("type", ""),
                                    "source": "reply",
                                }
                            )
                else:
                    reply_content = _re.sub(r"\[CQ:[^\]]+\]", "", str(reply_raw)).strip()
                if reply_content:
                    extra["reply_to_id"] = reply_id
                    extra["reply_content"] = reply_content
                    content = f'[回复"{reply_content}"] {content}'
                elif isinstance(reply_raw, list) and any(s.get("type") in ("image", "video") for s in reply_raw):
                    reply_image_segs = [s for s in reply_raw if s.get("type") in ("image", "video")]
                    analyzed = False
                    for seg in reply_image_segs[:2]:
                        img_data = seg.get("data", {})
                        image_bytes = await self._download_reference_image(img_data)
                        if not image_bytes:
                            continue
                        asyncio.ensure_future(self._auto_save_image_bytes(image_bytes, user_id, img_data))
                        try:
                            from core.multi_vision_analyzer import (
                                get_vision_analyzer,
                            )

                            analyzer = await get_vision_analyzer()
                            result = await analyzer.analyze_image(image_bytes)
                            if result.success:
                                extra["image_analysis"] = result.to_context_dict()
                                extra["has_image"] = True
                                has_media = True
                                desc = result.description or f"图片({result.format})"
                                content = f"[回复图片: {desc[:100]}] {content}"
                                analyzed = True
                                logger.info(f"[{self.platform_id}] 引用图片分析完成: {desc[:50]}...")
                                break
                        except Exception as e:
                            logger.warning(f"[{self.platform_id}] 引用图片视觉分析失败: {e}")
                    if not analyzed:
                        content = f"[回复图片] {content}"
                elif "[CQ:image" in str(reply_raw):
                    # 字符串格式的引用图片 — 也尝试下载分析
                    cq_files = _re.findall(r"\[CQ:image,file=([^,\]]+)", str(reply_raw))
                    analyzed_str = False
                    for fid in cq_files[:2]:
                        image_bytes = await self._download_reference_image({"file": fid})
                        if not image_bytes:
                            continue
                        asyncio.ensure_future(self._auto_save_image_bytes(image_bytes, user_id, {"file": fid}))
                        try:
                            from core.multi_vision_analyzer import (
                                get_vision_analyzer,
                            )

                            analyzer = await get_vision_analyzer()
                            result = await analyzer.analyze_image(image_bytes)
                            if result.success:
                                extra["image_analysis"] = result.to_context_dict()
                                extra["has_image"] = True
                                has_media = True
                                desc = result.description or f"图片({result.format})"
                                content = f"[回复图片: {desc[:100]}] {content}"
                                analyzed_str = True
                                logger.info(f"[{self.platform_id}] 引用图片(CQ)分析完成: {desc[:50]}...")
                                break
                        except Exception as e:
                            logger.warning(f"[{self.platform_id}] 引用图片(CQ)视觉分析失败: {e}")
                    if not analyzed_str:
                        content = f"[回复图片] {content}"
            else:
                logger.warning(f"[{self.platform_id}] 引用获取失败: id={reply_id}")

        if not content and not has_media:
            return

        # === 13. 群名解析 ===
        group_name = ""
        if group_id_str and msg_type == "group":
            group_name = await self._resolve_group_name(group_id_str)

        # === 13. 谛听 / 全局记忆 (decision_hub 已内置) ===

        if has_media:
            extra["has_media"] = True

        logger.debug(f"[{self.platform_id}] 收到消息: {content[:50]}, reply_id={reply_id}, is_at={is_at_bot}")

        # === 16. 路由到决策中心（按会话加锁，私聊与群聊可并发处理） ===
        conv_key = f"private_{user_id}" if msg_type == "private" else f"group_{group_id_str}"
        if conv_key not in self._process_locks:
            self._process_locks[conv_key] = asyncio.Lock()
        lock = self._process_locks[conv_key]

        if msg_type == "group":
            # 群聊走合并窗口：群锁忙时后续触发消息进入缓冲，
            # 当前处理完成后合并成一次请求，避免多人同时@时排队处理不过来
            await self._route_group_with_merge(
                lock=lock,
                data=data,
                content=content,
                user_id=user_id,
                user_name=user_name,
                group_id=group_id_str,
                group_name=group_name,
                sender_role=sender_role,
                is_at_bot=is_at_bot,
                extra=extra,
            )
        else:
            async with lock:
                response = await self.route_to_decision_hub(
                    content=content,
                    user_id=user_id,
                    user_name=user_name,
                    message_type=msg_type,
                    group_id=group_id_str,
                    group_name=group_name,
                    sender_role=sender_role,
                    is_at_bot=is_at_bot,
                    extra=extra,
                )

            if response:
                await self._send_onebot_reply(data, response)
            elif has_media and not is_at_bot:
                pass

    async def _route_group_with_merge(
        self,
        lock: asyncio.Lock,
        data: Dict,
        content: str,
        user_id: str,
        user_name: str,
        group_id: str,
        group_name: str,
        sender_role: str,
        is_at_bot: bool,
        extra: Dict,
    ) -> None:
        """群聊消息路由（合并窗口优化）。

        群锁空闲：直接处理并回复，随后冲刷合并缓冲。
        群锁忙：把消息放入缓冲，待当前处理完成后合并成一次请求处理，
        避免多人同时@时同群消息排长队导致"处理不过来"。
        """
        if self._group_batching_enabled() and lock.locked():
            pending = self._pending_group_messages.setdefault(group_id, [])
            max_messages = self._group_batch_max()
            if len(pending) >= max_messages:
                logger.warning(
                    f"[{self.platform_id}] 群 {group_id} 消息积压超限({max_messages})，丢弃: {content[:30]}"
                )
                return
            pending.append(
                {
                    "data": data,
                    "content": content,
                    "user_id": user_id,
                    "user_name": user_name,
                    "group_id": group_id,
                    "group_name": group_name,
                    "sender_role": sender_role,
                    "is_at_bot": is_at_bot,
                    "extra": extra,
                }
            )
            logger.info(
                f"[{self.platform_id}] 群 {group_id} 处理中，消息进入合并缓冲 ({len(pending)}): {content[:30]}"
            )
            return

        async with lock:
            response = await self.route_to_decision_hub(
                content=content,
                user_id=user_id,
                user_name=user_name,
                message_type="group",
                group_id=group_id,
                group_name=group_name,
                sender_role=sender_role,
                is_at_bot=is_at_bot,
                extra=extra,
            )
            if response:
                await self._send_onebot_reply(data, response)

        # 释放锁后再冲刷合并缓冲（asyncio.Lock 不可重入，必须在锁外调用）
        await self._flush_group_pending(group_id, lock)

    async def _flush_group_pending(self, group_id: str, lock: asyncio.Lock) -> None:
        """合并处理缓冲中的群消息（最多连续处理 3 批，防止持续刷屏时无限合并）"""
        for _ in range(3):
            pending = self._pending_group_messages.pop(group_id, None)
            if not pending:
                return
            first = pending[0]
            if len(pending) == 1:
                merged_content = first["content"]
                merged_user_id = first["user_id"]
                merged_user_name = first["user_name"]
            else:
                lines = []
                for i, p in enumerate(pending, 1):
                    name = p["user_name"] or p["user_id"]
                    lines.append(f"{i}. {name}: {p['content'][:200]}")
                merged_content = f"[群聊合并消息 {len(pending)} 条]\n" + "\n".join(lines)
                merged_user_id = first["user_id"]
                merged_user_name = "多人"

            logger.info(f"[{self.platform_id}] 合并处理群 {group_id} 的 {len(pending)} 条消息")
            async with lock:
                response = await self.route_to_decision_hub(
                    content=merged_content,
                    user_id=merged_user_id,
                    user_name=merged_user_name,
                    message_type="group",
                    group_id=group_id,
                    group_name=first.get("group_name", ""),
                    sender_role=first.get("sender_role", "member"),
                    is_at_bot=True,
                    extra=first.get("extra") or {},
                )
                if response:
                    await self._send_onebot_reply(first["data"], response)

    def _group_batching_enabled(self) -> bool:
        """群聊消息合并窗口开关（从 qq_config.yaml 读取）"""
        try:
            from config.config_utils import get_qq_config

            return bool(get_qq_config("qq", "message_batching", "enabled", default=True))
        except Exception:
            return True

    def _group_batch_max(self) -> int:
        """合并缓冲最大消息数（超过则丢弃新消息，防止无限积压）"""
        try:
            from config.config_utils import get_qq_config

            return int(get_qq_config("qq", "message_batching", "max_messages", default=15) or 15)
        except Exception:
            return 15

    async def _send_onebot_reply(self, original: Dict, text: str):
        """发送 OneBot 回复（根据 TTS 配置自动选择文字/语音）"""
        if not self._ws or not self._connected:
            return

        msg_type = original.get("message_type", "private")
        target_id = original.get("sender", {}).get("user_id") if msg_type == "private" else original.get("group_id")

        use_voice = self._tts_should_voice() and self._tts_platform_supports_voice()

        if use_voice and text.strip():
            logger.info(f"[{self.platform_id}] TTS 语音模式回复")
            audio_path, result = await self._tts_process(text, msg_type=msg_type, target_id=target_id)
            if result:
                return

        # 文字模式或 TTS 回退
        max_len = self._config_data.get("max_message_length", 200)
        for chunk in self._split_message(text, max_len):
            chunk = self.resolve_at_mentions(chunk)
            reply_data = {
                "action": "send_msg",
                "params": {
                    "message_type": msg_type,
                    "message": chunk,
                },
            }
            if msg_type == "private":
                reply_data["params"]["user_id"] = original.get("sender", {}).get("user_id")
            elif msg_type == "group":
                reply_data["params"]["group_id"] = original.get("group_id")
                reply_data["params"]["message"] = chunk
            try:
                await self._ws.send_str(json.dumps(reply_data))
                if len(chunk) < len(text):
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"[{self.platform_id}] 发送回复异常: {e}")
                break

    async def _tts_send_voice(self, audio_path: str, text: str, **kwargs) -> bool:
        """发送语音到 OneBot（record 结构化段 + file:// 本地路径，由 NapCat 自动上传）"""
        import os as _os

        if not self._ws or not self._connected:
            return False
        msg_type = kwargs.get("msg_type", "private")
        target_id = kwargs.get("target_id", "")

        file_uri = f"file:///{audio_path.replace(_os.sep, '/')}"
        reply_data = {
            "action": "send_msg",
            "params": {
                "message_type": msg_type,
                "message": [{"type": "record", "data": {"file": file_uri}}],
            },
        }
        if msg_type == "private":
            reply_data["params"]["user_id"] = target_id
        elif msg_type == "group":
            reply_data["params"]["group_id"] = target_id

        await self._ws.send_str(json.dumps(reply_data))
        logger.info(f"[{self.platform_id}] 语音消息已发送")
        return True

    # ============ OneBot API 辅助 ============

    async def send_group_message(self, group_id: int, message: str) -> bool:
        """发送群消息"""
        if not self._ws or not self._connected:
            return False
        try:
            segments = self.message_to_segments(message)
            await self._ws.send_str(
                json.dumps(
                    {
                        "action": "send_group_msg",
                        "params": {
                            "group_id": group_id,
                            "message": segments,
                        },
                    }
                )
            )
            logger.info(f"[{self.platform_id}] 群消息已发送到 {group_id}")
            return True
        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送群消息失败: {e}")
            return False

    async def send_private_message(self, user_id: int, message: str) -> bool:
        """发送私聊消息"""
        if not self._ws or not self._connected:
            return False
        try:
            message = self.resolve_at_mentions(message)
            segments = self.message_to_segments(message)
            await self._ws.send_str(
                json.dumps(
                    {
                        "action": "send_private_msg",
                        "params": {
                            "user_id": user_id,
                            "message": segments,
                        },
                    }
                )
            )
            logger.info(f"[{self.platform_id}] 私聊消息已发送给 {user_id}")
            return True
        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送私聊消息失败: {e}")
            return False

    async def send_like(self, user_id: int, times: int = 1):
        """给用户点赞"""
        await self._call_onebot_api("send_like", {"user_id": user_id, "times": times})

    async def send_poke(self, user_id: int, group_id: int = 0):
        """拍一拍用户"""
        if group_id:
            await self._call_onebot_api("group_poke", {"group_id": group_id, "user_id": user_id})
        else:
            await self._call_onebot_api("friend_poke", {"user_id": user_id})

    async def upload_image(self, file_path: str) -> Optional[str]:
        """返回可发送的图片 file 引用（file:// URI）。

        NapCat / 新版 OneBot 实现不支持 upload_image API（报
        "不支持的API upload_image"），故不再调用该 API，而是直接返回
        file:// 本地路径 URI，由 NapCat 在发送消息时自动上传。
        对标表情包系统与语音发送（_send_voice）的结构化消息段做法。
        """
        import os as _os

        if not _os.path.exists(file_path):
            logger.warning(f"[{self.platform_id}] 图片文件不存在: {file_path}")
            return None
        abs_path = _os.path.abspath(file_path).replace(_os.sep, "/")
        return f"file:///{abs_path}"

    async def send_image(
        self,
        target: str = "",
        image_path: str = "",
        file_data: Optional[bytes] = None,
        file_name: str = "",
        caption: str = "",
        **kwargs,
    ) -> bool:
        """发送图片（统一接口，兼容 BasePlatform.send_image 签名）

        供 send_platform_file 等跨平台工具调用。内部通过 upload_image 拿到
        file:// 本地路径引用后，用结构化消息段发送，由 NapCat 自动上传。
        """
        import os as _os
        import tempfile

        msg_type = kwargs.get("message_type", "private")
        if msg_type not in ("private", "group"):
            msg_type = "private"

        tmp_path = None
        try:
            if file_data and not image_path:
                suffix = _os.path.splitext(file_name or "image.png")[1] or ".png"
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp_path = tmp.name
                tmp.write(file_data)
                tmp.close()
                image_path = tmp_path

            if not image_path or not _os.path.exists(image_path):
                logger.warning(f"[{self.platform_id}] 图片文件不存在: {image_path}")
                return False

            file_id = await self.upload_image(image_path)
            if not file_id:
                logger.warning(f"[{self.platform_id}] 图片上传失败: {image_path}")
                return False

            segments = []
            if caption:
                segments.append({"type": "text", "data": {"text": caption}})
            segments.append({"type": "image", "data": {"file": file_id}})

            try:
                target_id = int(target)
            except (TypeError, ValueError):
                target_id = target

            if not self._ws or not self._connected:
                logger.warning(f"[{self.platform_id}] 图片发送失败(未连接): {target}")
                return False

            if msg_type == "group":
                params = {"group_id": target_id, "message": segments}
                action = "send_group_msg"
            else:
                params = {"user_id": target_id, "message": segments}
                action = "send_private_msg"

            # 与文字消息相同的直发路径（不等待 echo 回执），避免 NapCat 上传
            # 耗时长/确认事件超时时白等 15 秒或触发重发
            try:
                await self._ws.send_str(json.dumps({"action": action, "params": params}))
            except Exception as e:
                logger.warning(f"[{self.platform_id}] 图片发送失败: {target}: {e}")
                return False
            self._record_message_out()
            logger.info(f"[{self.platform_id}] 图片已发送到 {target} (file_id={file_id})")
            return True
        finally:
            if tmp_path and _os.path.exists(tmp_path):

                def _cleanup(p=tmp_path):
                    with contextlib.suppress(Exception):
                        if _os.path.exists(p):
                            _os.unlink(p)

                asyncio.get_event_loop().call_later(30, _cleanup)

    @staticmethod
    def cq_at(qq: int) -> str:
        return f"[CQ:at,qq={qq}]"

    @staticmethod
    def resolve_at_mentions(text: str) -> str:
        """将 @数字 转换为 [CQ:at,qq=数字] 格式，让 QQ 渲染为 @昵称卡片"""
        import re

        return re.sub(r"@(\d{5,15})", r"[CQ:at,qq=\1]", text)

    @staticmethod
    def _build_structured_message(text: str) -> list:
        """将包含 @<QQ号> 的文本拆分为结构化消息段，确保 @ 正确渲染"""
        import re

        segments = []
        last_end = 0
        for m in re.finditer(r"@(\d{5,15})", text):
            if m.start() > last_end:
                segments.append({"type": "text", "data": {"text": text[last_end : m.start()]}})
            segments.append({"type": "at", "data": {"qq": m.group(1)}})
            last_end = m.end()
        if last_end < len(text):
            segments.append({"type": "text", "data": {"text": text[last_end:]}})
        return segments or [{"type": "text", "data": {"text": text}}]

    @staticmethod
    def message_to_segments(message: str) -> list:
        """将包含 CQ 码的字符串解析为 OneBot 消息段数组"""
        import re

        CQ_PATTERN = re.compile(r"\[CQ:([a-zA-Z0-9_-]+),?([^\]]*)\]")
        segments: list = []
        last_pos = 0

        for match in CQ_PATTERN.finditer(message):
            text_part = message[last_pos : match.start()]
            if text_part:
                segments.append({"type": "text", "data": {"text": text_part}})
            cq_type = match.group(1)
            cq_args_str = match.group(2)
            data: dict = {}
            if cq_args_str:
                for arg_pair in cq_args_str.split(","):
                    if "=" in arg_pair:
                        k, v = arg_pair.split("=", 1)
                        data[k.strip()] = v.strip()
            segments.append({"type": cq_type, "data": data})
            last_pos = match.end()

        remaining_text = message[last_pos:]
        if remaining_text:
            segments.append({"type": "text", "data": {"text": remaining_text}})

        return segments or [{"type": "text", "data": {"text": message}}]

    async def resolve_at_names(self, group_id: int, at_list: list) -> dict:
        """解析 @列表中的 QQ 号 → 显示名映射（card > nickname > QQ号）"""
        result = {}
        if not at_list or not group_id:
            return result

        now = time.time()
        cached = self._group_member_cache.get(group_id)
        members = None
        if cached and now - cached[0] < 300:
            members = cached[1]

        if members is None:
            member_list = await self.get_group_member_list(group_id)
            if member_list:
                members = member_list
                self._group_member_cache[group_id] = (now, members)

        if not members:
            return result

        for qq in at_list:
            qq_str = str(qq)
            name = qq_str
            for m in members:
                if str(m.get("user_id")) == qq_str:
                    name = m.get("card") or m.get("nickname") or qq_str
                    break
            result[qq_str] = name

        return result

    @staticmethod
    def cq_image(file: str) -> str:
        return f"[CQ:image,file={file}]"

    @staticmethod
    def cq_face(face_id: int) -> str:
        return f"[CQ:face,id={face_id}]"

    # ============ 扩展 OneBot API ============

    async def get_group_info(self, group_id: int) -> Optional[dict]:
        return await self._call_onebot_api("get_group_info", {"group_id": group_id})

    async def get_group_list(self) -> Optional[list]:
        result = await self._call_onebot_api("get_group_list", {})
        return result if isinstance(result, list) else None

    async def get_group_member_list(self, group_id: int) -> Optional[list]:
        result = await self._call_onebot_api("get_group_member_list", {"group_id": group_id})
        return result if isinstance(result, list) else None

    async def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = False) -> Optional[dict]:
        return await self._call_onebot_api(
            "get_group_member_info",
            {"group_id": group_id, "user_id": user_id, "no_cache": no_cache},
        )

    async def get_friend_list(self) -> Optional[list]:
        result = await self._call_onebot_api("get_friend_list", {})
        return result if isinstance(result, list) else None

    async def get_stranger_info(self, user_id: int, no_cache: bool = False) -> Optional[dict]:
        return await self._call_onebot_api("get_stranger_info", {"user_id": user_id, "no_cache": no_cache})

    async def get_group_msg_history(self, group_id: int, message_seq: int = 0, count: int = 20) -> Optional[dict]:
        return await self._call_onebot_api(
            "get_group_msg_history",
            {"group_id": group_id, "message_seq": message_seq, "count": count},
        )

    async def get_msg(self, message_id: int) -> Optional[dict]:
        return await self._call_onebot_api("get_msg", {"message_id": message_id})

    async def get_forward_msg(self, forward_id: str) -> Optional[dict]:
        return await self._call_onebot_api("get_forward_msg", {"id": forward_id})

    async def send_face_message(
        self,
        face_id: int = 0,
        msg_type: str = "private",
        target_id: int = 0,
        target_type: str = "",
    ):
        """发送 QQ 内置表情（兼容两种参数签名）"""
        # 兼容 QQOneBotClient 风格: (target_type, target_id, face_id)
        if target_type and not face_id:
            face_id = target_id if isinstance(target_id, int) and target_id > 0 else 0
            target_id_val = target_id
            msg_type_val = target_type
        else:
            target_id_val = target_id
            msg_type_val = msg_type

        cq = self.cq_face(face_id)
        if self._ws and self._connected:
            params = {"message_type": msg_type_val, "message": cq}
            if msg_type_val == "private":
                params["user_id"] = target_id_val
            else:
                params["group_id"] = target_id_val
            await self._ws.send_str(json.dumps({"action": "send_msg", "params": params}))
            return {"status": "ok"}

    async def send_image_message(
        self,
        target_type: str = "",
        target_id: int = 0,
        image_data: bytes = b"",
        image_name: str = "",
        msg_type: str = "",
    ):
        """发送图片消息（兼容两种参数签名，结构化消息段）"""
        import os
        import tempfile

        if not image_data:
            return None
        if not target_type:
            target_type = msg_type or "private"

        # 写入临时文件，用 file:// 结构化段发送（NapCat 自动上传）
        tmp = tempfile.NamedTemporaryFile(suffix=os.path.splitext(image_name)[1] or ".png", delete=False)
        tmp_path = tmp.name
        tmp.close()
        with open(tmp_path, "wb") as f:
            f.write(image_data)

        try:
            file_ref = await self.upload_image(tmp_path)
            if not file_ref:
                return None
            segments = [{"type": "image", "data": {"file": file_ref}}]
            if self._ws and self._connected:
                params = {"message_type": target_type, "message": segments}
                if target_type == "private":
                    params["user_id"] = target_id
                else:
                    params["group_id"] = target_id
                await self._ws.send_str(json.dumps({"action": "send_msg", "params": params}))
                return {"status": "ok"}
            return None
        finally:

            def _cleanup(p=tmp_path):
                with contextlib.suppress(Exception):
                    if os.path.exists(p):
                        os.unlink(p)

            asyncio.get_event_loop().call_later(30, _cleanup)

    async def send_group_image(self, group_id: int, image_path: str, caption: str = ""):
        """发送群图片消息（结构化消息段 + file:// 本地路径，由 NapCat 自动上传）"""
        import os as _os

        if not _os.path.exists(image_path):
            logger.warning(f"[{self.platform_id}] 图片文件不存在: {image_path}")
            return None
        if not self._ws or not self._connected:
            return None

        file_id = await self.upload_image(image_path)
        if not file_id:
            logger.warning(f"[{self.platform_id}] 图片上传失败: {image_path}")
            return None

        segments = []
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})
        segments.append({"type": "image", "data": {"file": file_id}})

        result = await self._call_onebot_api("send_group_msg", {"group_id": group_id, "message": segments})
        if result is None:
            logger.warning(f"[{self.platform_id}] 群图片发送失败: {group_id}")
            return None
        logger.info(f"[{self.platform_id}] 群图片已发送到 {group_id} (file_id={file_id})")
        return {"status": "ok"}

    async def send_private_image(self, user_id: int, image_path: str, caption: str = ""):
        """发送私聊图片消息（结构化消息段 + file:// 本地路径，由 NapCat 自动上传）"""
        import os as _os

        if not _os.path.exists(image_path):
            logger.warning(f"[{self.platform_id}] 图片文件不存在: {image_path}")
            return None
        if not self._ws or not self._connected:
            return None

        file_id = await self.upload_image(image_path)
        if not file_id:
            logger.warning(f"[{self.platform_id}] 图片上传失败: {image_path}")
            return None

        segments = []
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})
        segments.append({"type": "image", "data": {"file": file_id}})

        result = await self._call_onebot_api("send_private_msg", {"user_id": user_id, "message": segments})
        if result is None:
            logger.warning(f"[{self.platform_id}] 私聊图片发送失败: {user_id}")
            return None
        logger.info(f"[{self.platform_id}] 私聊图片已发送给 {user_id} (file_id={file_id})")
        return {"status": "ok"}

    async def send_group_file(self, group_id: int, file_path: str, caption: str = ""):
        """发送群文件消息（file 结构化段 + file:// 本地路径）"""
        file_ref = await self.upload_file(file_path)
        if not file_ref:
            return None
        segments = []
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})
        segments.append({"type": "file", "data": {"file": file_ref}})
        if self._ws and self._connected:
            await self._ws.send_str(
                json.dumps(
                    {
                        "action": "send_group_msg",
                        "params": {"group_id": group_id, "message": segments},
                    }
                )
            )
            return {"status": "ok"}

    async def send_private_file(self, user_id: int, file_path: str, caption: str = ""):
        """发送私聊文件消息（file 结构化段 + file:// 本地路径）"""
        file_ref = await self.upload_file(file_path)
        if not file_ref:
            return None
        segments = []
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})
        segments.append({"type": "file", "data": {"file": file_ref}})
        if self._ws and self._connected:
            await self._ws.send_str(
                json.dumps(
                    {
                        "action": "send_private_msg",
                        "params": {"user_id": user_id, "message": segments},
                    }
                )
            )
            return {"status": "ok"}

    async def download_image(self, url: str) -> Optional[bytes]:
        """从 URL 下载图片数据"""
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp,
            ):
                if resp.status == 200:
                    return await resp.read()
        except Exception as e:
            logger.error(f"[{self.platform_id}] 下载图片失败: {e}")
        return None

    async def upload_file(self, file_path: str) -> Optional[str]:
        """返回可发送的文件 file 引用（file:// URI）。

        NapCat / 新版 OneBot 实现不支持 upload_file API（同 upload_image），
        故直接返回 file:// 本地路径 URI，由 NapCat 在发送时自动上传。
        """
        import os as _os

        if not _os.path.exists(file_path):
            logger.warning(f"[{self.platform_id}] 文件不存在: {file_path}")
            return None
        abs_path = _os.path.abspath(file_path).replace(_os.sep, "/")
        return f"file:///{abs_path}"

    async def upload_group_file(self, group_id: int, file_path: str, filename: str) -> bool:
        """上传文件到群文件"""
        import os as _os

        try:
            await self._call_onebot_api(
                "upload_group_file",
                {
                    "group_id": group_id,
                    "file": f"file:///{file_path.replace(_os.sep, '/')}",
                    "name": filename,
                },
            )
            return True
        except Exception as e:
            logger.error(f"[{self.platform_id}] 上传群文件失败: {e}")
            return False

    async def upload_private_file(self, user_id: int, file_path: str, filename: str) -> bool:
        """上传文件到私聊"""
        # OneBot v11 没有专门的私聊文件上传 API，用 send_private_file 代替
        return bool(await self.send_private_file(user_id, file_path, filename))

    async def get_group_root_files(self, group_id: int) -> dict:
        """获取群根目录文件列表"""
        result = await self._call_onebot_api("get_group_root_files", {"group_id": group_id})
        if isinstance(result, dict):
            return result
        return {"files": [], "folders": []}

    async def get_group_files(self, group_id: int, folder_id: str) -> dict:
        """获取群文件夹内的文件列表"""
        result = await self._call_onebot_api(
            "get_group_files",
            {"group_id": group_id, "folder_id": folder_id},
        )
        if isinstance(result, dict):
            return result
        return {"files": [], "folders": []}

    async def get_group_file_url(self, group_id: int, file_id: str) -> Optional[str]:
        """获取群文件下载链接"""
        result = await self._call_onebot_api(
            "get_group_file_url",
            {"group_id": group_id, "file_id": file_id},
        )
        if isinstance(result, dict):
            return result.get("url")
        return None

    async def download_group_file(self, url: str, save_path: str) -> bool:
        """下载群文件到本地"""
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response,
            ):
                if response.status == 200:
                    with open(save_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    return True
        except Exception as e:
            logger.error(f"[{self.platform_id}] 下载群文件失败: {e}")
        return False

    async def get_group_admin_list(self, group_id: int) -> list:
        """获取群管理员列表"""
        members = await self.get_group_member_list(group_id)
        if not members:
            return []
        return [m.get("user_id") for m in members if m.get("role") in ("admin", "owner")]

    async def set_msg_emoji_like(self, message_id: int, emoji_id: str) -> bool:
        """给消息设置表情表态"""
        try:
            await self._call_onebot_api(
                "set_msg_emoji_like",
                {"message_id": message_id, "emoji_id": emoji_id},
            )
            return True
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 表情表态失败: {e}")
            return False

    def _find_named_emoji(self, name: str) -> Optional[Path]:
        """在本地表情包仓库中按名称查找"""
        from pathlib import Path as _Path

        emoji_dirs = ["data/emoji", "data"]
        name_lower = name.lower()
        for d in emoji_dirs:
            root = _Path(d)
            if not root.exists():
                continue
            for img_file in root.rglob("*"):
                if img_file.suffix.lower() not in (
                    ".gif",
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".bmp",
                ):
                    continue
                stem = img_file.stem.lower()
                # 忽略 tmp 前缀的自动保存文件
                if stem.startswith("tmp"):
                    continue
                if name_lower in stem or stem in name_lower:
                    return img_file
        return None

    async def _download_reference_image(self, image_data: dict) -> Optional[bytes]:
        """下载引用消息中的图片

        OneBot 图片消息段: {"type": "image", "data": {"url": "...", "file": "..."}}
        优先 OneBot get_image API（返回 base64），失败回退直接 HTTP 下载 url
        """
        import base64 as _base64

        file_id = image_data.get("file", "")
        url = image_data.get("url", "")

        # 方案1: 通过 OneBot API get_image（最可靠，返回 base64 编码的文件）
        if file_id:
            result = await self._call_onebot_api("get_image", {"file": file_id})
            if isinstance(result, dict):
                b64 = result.get("file") or result.get("data")
                if b64:
                    try:
                        raw = _base64.b64decode(b64)
                        if len(raw) > 1024:  # 至少 1KB 才算是有效图片
                            logger.debug(f"[{self.platform_id}] OneBot get_image 成功: {len(raw) / 1024:.1f}KB")
                            return raw
                    except Exception as e:
                        logger.debug(f"[{self.platform_id}] base64 解码失败: {e}")

        # 方案2: 直接 HTTP 下载 url（QQ 内部 url 可能过期或需要特定 header）
        if url:
            try:
                import aiohttp

                headers = {
                    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
                    "Referer": "https://qun.qq.com/",
                }
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp,
                ):
                    if resp.status == 200:
                        raw = await resp.read()
                        if len(raw) > 1024:
                            logger.debug(f"[{self.platform_id}] HTTP 下载成功(url): {len(raw) / 1024:.1f}KB")
                            return raw
                        else:
                            logger.debug(f"[{self.platform_id}] HTTP 下载数据过小: {len(raw)}B")
            except Exception as e:
                logger.debug(f"[{self.platform_id}] 直接下载图片失败(url): {e}")

        logger.debug(f"[{self.platform_id}] 图片下载失败: file={file_id[:30] if file_id else '-'}")
        return None

    async def _auto_save_images(self, image_segments: list, user_id: str):
        """自动保存消息中的图片到表情包仓库（消息段格式）"""
        for seg in image_segments[:3]:  # 单条消息最多保存3张
            img_data = seg.get("data", {})
            image_bytes = await self._download_reference_image(img_data)
            if image_bytes:
                try:
                    from utils.auto_emoji_saver import get_auto_emoji_saver

                    saver = get_auto_emoji_saver()
                    await saver.auto_save_emoji(int(user_id), image_bytes, image_info=img_data)
                except Exception as e:
                    logger.debug(f"[{self.platform_id}] 自动保存图片失败: {e}")

    async def _auto_save_string_images(self, raw_message: str, user_id: str):
        """自动保存 CQ 字符串格式消息中的图片"""
        import re as _re

        cq_images = _re.findall(r"\[CQ:image,file=([^,\]]+)", raw_message)
        for file_id in cq_images[:3]:
            image_bytes = await self._download_reference_image({"file": file_id})
            if image_bytes:
                try:
                    from utils.auto_emoji_saver import get_auto_emoji_saver

                    saver = get_auto_emoji_saver()
                    await saver.auto_save_emoji(
                        int(user_id),
                        image_bytes,
                        image_info={"file_name": file_id},
                    )
                except Exception as e:
                    logger.debug(f"[{self.platform_id}] 自动保存图片失败(CQ): {e}")

    async def _auto_save_image_bytes(self, image_bytes: bytes, user_id: str, image_info: Optional[Dict] = None):
        """保存已下载的图片字节到表情包仓库"""
        try:
            from utils.auto_emoji_saver import get_auto_emoji_saver

            saver = get_auto_emoji_saver()
            await saver.auto_save_emoji(int(user_id), image_bytes, image_info=image_info)
        except Exception as e:
            logger.debug(f"[{self.platform_id}] 自动保存图片失败(bytes): {e}")

    async def _do_disconnect(self):
        self._shutting_down = True
        self._connected = False
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
        self._ws = None

    async def _do_health_check(self) -> bool:
        return self._connected and self._ws is not None

    async def _do_send_file(self, target: str, outbound_file: Any, **kwargs) -> bool:
        """OneBot 文件发送实现"""
        if not self._ws or not self._connected:
            logger.warning(f"[{self.platform_id}] WebSocket 未连接")
            return False

        try:
            msg_type = kwargs.get("message_type", "private")
            caption = getattr(outbound_file, "caption", "") or kwargs.get("caption", "")

            if outbound_file.is_local and outbound_file.file_path:
                file_path = outbound_file.file_path
                if not os.path.exists(file_path):
                    logger.warning(f"[{self.platform_id}] 文件不存在: {file_path}")
                    return False
            elif outbound_file.is_bytes and outbound_file.file_data:
                import tempfile

                suffix = outbound_file.extension or ""
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{suffix}" if suffix else "", prefix="miya_send_"
                ) as tmp:
                    tmp.write(outbound_file.file_data)
                    file_path = tmp.name
                try:
                    result = await self._do_send_onebot_file(
                        file_path, outbound_file.file_name, caption, msg_type, target
                    )
                finally:

                    def _cleanup(p=file_path):
                        try:
                            if os.path.exists(p):
                                os.unlink(p)
                        except OSError:
                            pass

                    asyncio.get_event_loop().call_later(30, _cleanup)
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

            result = await self._do_send_onebot_file(file_path, outbound_file.file_name, caption, msg_type, target)
            return result

        except Exception as e:
            logger.error(f"[{self.platform_id}] 发送文件异常: {e}")
            return False

    async def _do_send_onebot_file(
        self, file_path: str, file_name: str, caption: str, msg_type: str, target: str
    ) -> bool:
        """OneBot 文件/图片发送 — 均走 file:// 结构化段（NapCat 自动上传），echo 确认。

        串行化发送：NapCat 并发上传多文件容易触发限流导致大批失败，
        串行后每次发送都能在 echo 超时窗口内完成，且不会重复发送。
        """
        async with self._file_send_lock:
            return await self._send_onebot_file_inner(file_path, file_name, caption, msg_type, target)

    async def _send_onebot_file_inner(
        self, file_path: str, file_name: str, caption: str, msg_type: str, target: str
    ) -> bool:
        """单文件发送核心逻辑（需在 _file_send_lock 内调用）"""
        import os as _os

        is_image = self._is_image_file(file_path)
        file_size = _os.path.getsize(file_path)

        try:
            target_id = int(target)
        except (TypeError, ValueError):
            target_id = target

        segments: list = []
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})

        if is_image:
            file_id = await self.upload_image(file_path)
            if not file_id:
                logger.warning(f"[{self.platform_id}] 图片上传失败: {file_path}")
                return False
            segments.append({"type": "image", "data": {"file": file_id}})
        else:
            file_id = await self.upload_file(file_path)
            if not file_id:
                logger.warning(f"[{self.platform_id}] 文件上传失败: {file_path}")
                return False
            segments.append({"type": "file", "data": {"file": file_id}})

        action = "send_private_msg" if msg_type == "private" else "send_group_msg"
        params: dict = {"message": segments}
        if msg_type == "private":
            params["user_id"] = target_id
        else:
            params["group_id"] = target_id

        # 与文字消息相同的直发路径（不等待 echo 回执）：
        # NapCat 上传图片/文件耗时较长，且其内部确认事件偶发超时（sendMsg Timeout）。
        # 若等待回执，每次发送会白卡 15 秒甚至触发重发；直发后由 NapCat 自行完成上传送达。
        await self._ws.send_str(
            json.dumps(
                {
                    "action": action,
                    "params": params,
                }
            )
        )
        self._record_message_out()
        logger.info(f"[{self.platform_id}] 文件已发送: {file_name} -> {target} (action={action}, size={file_size}B)")
        return True

    @staticmethod
    def _is_image_file(file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"}
