"""
QQ交互子网
完全吸收Undefined的QQ机器人能力，集成到弥娅架构
"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

import websockets
from mlink.message import Message, MessageType
from core.constants import NetworkTimeout


logger = logging.getLogger(__name__)


@dataclass
class QQMessage:
    """QQ消息数据类"""
    post_type: str = ""
    message_type: str = ""
    group_id: int = 0
    user_id: int = 0
    sender_id: int = 0
    message: str = ""
    raw_message: List[Dict] = field(default_factory=list)
    sender_name: str = ""
    group_name: str = ""
    sender_role: str = "member"
    sender_title: str = ""
    message_id: int = 0
    is_at_bot: bool = False
    time: datetime = field(default_factory=datetime.now)
    at_list: List[int] = field(default_factory=list)  # @提及的用户ID列表


@dataclass
class QQNotice:
    """QQ通知事件数据类"""
    notice_type: str = ""
    sub_type: str = ""
    group_id: int = 0
    user_id: int = 0
    target_id: int = 0
    sender_id: int = 0


class QQOneBotClient:
    """OneBot WebSocket客户端 - 完全吸收Undefined的实现"""

    def __init__(self, ws_url: str, token: str = ""):
        self.ws_url = ws_url
        self.token = token
        self.ws: Optional[websockets.asyncio.client.ClientConnection] = None
        self._message_id = 0
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._message_handler: Optional[Callable] = None
        self._running = False
        self._tasks: set = set()

    def set_message_handler(self, handler: Callable) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    def connection_status(self) -> Dict[str, Any]:
        """返回连接状态"""
        return {
            "connected": bool(self.ws) and self._running,
            "running": self._running,
            "ws_url": self.ws_url,
        }

    async def connect(self) -> None:
        """连接到OneBot WebSocket"""
        url = self.ws_url
        if self.token:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}access_token={self.token}"

        extra_headers = {}
        if self.token:
            extra_headers["Authorization"] = f"Bearer {self.token}"

        logger.info(f"[QQ] 正在连接到 {self.ws_url}...")

        try:
            self.ws = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=NetworkTimeout.WEBSOCKET_PING_TIMEOUT,
                max_size=100 * 1024 * 1024,
                additional_headers=extra_headers if extra_headers else None,
            )
            logger.info("[QQ] WebSocket连接成功")
        except Exception as e:
            logger.error(f"[QQ] WebSocket连接失败: {e}")
            raise

    async def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("[QQ] WebSocket连接已断开")

    async def _call_api(
        self,
        action: str,
        params: Optional[Dict] = None,
        *,
        suppress_error_retcodes: Optional[set] = None,
    ) -> Dict[str, Any]:
        """调用OneBot API"""
        if not self.ws:
            raise RuntimeError("WebSocket未连接")

        self._message_id += 1
        echo = str(self._message_id)

        request = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }

        future = asyncio.Future()
        self._pending_responses[echo] = future

        try:
            await self.ws.send(json.dumps(request))
            response = await asyncio.wait_for(future, timeout=480.0)

            status = response.get("status")
            if status == "failed":
                retcode = response.get("retcode", -1)
                msg = response.get("message", "未知错误")
                if suppress_error_retcodes and retcode in suppress_error_retcodes:
                    logger.warning(f"[QQ] API预期失败: {action} retcode={retcode}")
                else:
                    logger.error(f"[QQ] API失败: {action} retcode={retcode} msg={msg}")
                    raise RuntimeError(f"API调用失败: {msg} (retcode={retcode})")

            return response
        except asyncio.TimeoutError:
            logger.error(f"[QQ] API超时: {action}")
            raise
        finally:
            self._pending_responses.pop(echo, None)

    async def send_group_message(
        self,
        group_id: int,
        message: str | List[Dict],
        *,
        auto_escape: bool = False,
    ) -> Dict[str, Any]:
        """发送群消息"""
        return await self._call_api(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape,
            },
        )

    async def send_private_message(
        self,
        user_id: int,
        message: str | List[Dict],
        *,
        auto_escape: bool = False,
    ) -> Dict[str, Any]:
        """发送私聊消息"""
        return await self._call_api(
            "send_private_msg",
            {
                "user_id": user_id,
                "message": message,
                "auto_escape": auto_escape,
            },
        )

    async def get_group_msg_history(
        self,
        group_id: int,
        message_seq: Optional[int] = None,
        count: int = 500,
    ) -> List[Dict]:
        """获取群消息历史"""
        params: Dict = {
            "group_id": group_id,
            "count": count,
        }
        if message_seq is not None:
            params["message_seq"] = message_seq

        result = await self._call_api("get_group_msg_history", params)

        if not result:
            return []

        data = result.get("data", {})
        return data.get("messages", [])

    async def get_group_info(self, group_id: int) -> Optional[Dict]:
        """获取群信息"""
        try:
            result = await self._call_api("get_group_info", {"group_id": group_id})
            return result.get("data", {})
        except Exception as e:
            logger.error(f"[QQ] 获取群信息失败: {e}")
            return None

    async def get_stranger_info(self, user_id: int, no_cache: bool = False) -> Optional[Dict]:
        """获取陌生人信息"""
        try:
            params = {"user_id": user_id}
            if no_cache:
                params["no_cache"] = no_cache
            result = await self._call_api("get_stranger_info", params)
            return result.get("data", {})
        except Exception as e:
            logger.error(f"[QQ] 获取用户信息失败: {e}")
            return None

    async def get_group_member_info(
        self, group_id: int, user_id: int, no_cache: bool = False
    ) -> Optional[Dict]:
        """获取群成员信息"""
        try:
            result = await self._call_api(
                "get_group_member_info",
                {"group_id": group_id, "user_id": user_id, "no_cache": no_cache},
            )
            return result.get("data", {})
        except Exception as e:
            logger.error(f"[QQ] 获取群成员信息失败: {e}")
            return None

    async def get_group_member_list(self, group_id: int) -> List[Dict]:
        """获取群成员列表"""
        try:
            result = await self._call_api(
                "get_group_member_list", {"group_id": group_id}
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"[QQ] 获取群成员列表失败: {e}")
            return []

    async def get_friend_list(self) -> List[Dict]:
        """获取好友列表"""
        try:
            result = await self._call_api("get_friend_list")
            return result.get("data", [])
        except Exception as e:
            logger.error(f"[QQ] 获取好友列表失败: {e}")
            return []

    async def get_group_list(self) -> List[Dict]:
        """获取群列表"""
        try:
            result = await self._call_api("get_group_list")
            return result.get("data", [])
        except Exception as e:
            logger.error(f"[QQ] 获取群列表失败: {e}")
            return []

    async def send_group_poke(
        self, group_id: int, user_id: int
    ) -> Dict[str, Any]:
        """群聊拍一拍"""
        try:
            return await self._call_api(
                "group_poke", {"group_id": group_id, "user_id": user_id}
            )
        except RuntimeError:
            # 回退到 send_poke
            return await self._call_api(
                "send_poke",
                {"group_id": group_id, "user_id": user_id, "target_id": user_id},
            )

    async def send_private_poke(self, user_id: int) -> Dict[str, Any]:
        """私聊拍一拍"""
        try:
            return await self._call_api("friend_poke", {"user_id": user_id})
        except RuntimeError:
            # 回退到 send_poke
            return await self._call_api(
                "send_poke",
                {"user_id": user_id, "target_id": user_id},
            )

    async def send_like(self, user_id: int, times: int = 1) -> Dict[str, Any]:
        """发送好友点赞"""
        try:
            return await self._call_api(
                "send_like",
                {"user_id": user_id, "times": times},
            )
        except Exception as e:
            logger.error(f"[QQ] 点赞失败: {e}")
            raise

    async def get_msg(self, message_id: int) -> Optional[Dict]:
        """获取单条消息"""
        try:
            result = await self._call_api("get_msg", {"message_id": message_id})
            return result.get("data")
        except Exception as e:
            logger.error(f"[QQ] 获取消息失败: {e}")
            return None

    async def get_forward_msg(self, id: str) -> List[Dict]:
        """获取合并转发消息"""
        try:
            result = await self._call_api(
                "get_forward_msg",
                {"message_id": id},
                suppress_error_retcodes={1200},
            )
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("messages", [])
            elif isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"[QQ] 获取转发消息失败: {e}")
            return []

    async def run(self) -> None:
        """运行消息接收循环"""
        if not self.ws:
            raise RuntimeError("WebSocket未连接")

        self._running = True
        logger.info("[QQ] 消息接收循环已启动")

        try:
            while self._running:
                try:
                    message_data = await self.ws.recv()
                    if isinstance(message_data, bytes):
                        message_data = message_data.decode("utf-8")

                    data = json.loads(message_data)
                    await self._dispatch_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"[QQ] JSON解析失败: {e}")
                except websockets.ConnectionClosed:
                    logger.warning("[QQ] 连接已关闭")
                    break
                except Exception as e:
                    logger.exception(f"[QQ] 接收消息异常: {e}")
        finally:
            self._running = False
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            logger.info("[QQ] 消息接收循环已停止")

    async def _dispatch_message(self, data: Dict) -> None:
        """分发消息"""
        echo = data.get("echo")
        if echo is not None:
            echo_str = str(echo)
            if echo_str in self._pending_responses:
                self._pending_responses[echo_str].set_result(data)
            return

        post_type = data.get("post_type")
        if post_type == "message":
            logger.info(
                f"[QQ] 收到消息 type={data.get('message_type')} "
                f"sender={data.get('sender', {}).get('user_id')}"
            )
            if self._message_handler:
                task = asyncio.create_task(self._safe_handle_message(data))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

        elif post_type == "notice":
            self._handle_notice(data)

    def _handle_notice(self, data: Dict) -> None:
        """处理通知事件"""
        notice_type = data.get("notice_type", "")
        sub_type = data.get("sub_type", "")

        if notice_type == "notify" and sub_type == "poke":
            target_id = data.get("target_id", 0)
            sender_id = data.get("user_id", 0)
            group_id = data.get("group_id", 0)
            logger.info(
                f"[QQ] 收到拍一拍 sender={sender_id} target={target_id} group={group_id}"
            )

            if self._message_handler:
                poke_event = {
                    "post_type": "notice",
                    "notice_type": "poke",
                    "group_id": group_id,
                    "user_id": sender_id,
                    "sender": {"user_id": sender_id},
                    "target_id": target_id,
                    "message": [],
                }
                task = asyncio.create_task(self._safe_handle_message(poke_event))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    async def _safe_handle_message(self, data: Dict) -> None:
        """安全处理消息"""
        try:
            if self._message_handler:
                await self._message_handler(data)
        except Exception as e:
            logger.exception(f"[QQ] 处理消息出错: {e}")

    async def run_with_reconnect(self, reconnect_interval: float = 5.0) -> None:
        """带自动重连运行"""
        self._should_stop = False
        reconnect_count = 0

        while not self._should_stop:
            try:
                if reconnect_count > 0:
                    logger.info(f"[QQ] 尝试第 {reconnect_count} 次重连...")
                await self.connect()
                reconnect_count = 0
                await self.run()
            except websockets.ConnectionClosed:
                logger.warning("[QQ] 连接断开")
            except Exception as e:
                logger.error(f"[QQ] 运行错误: {e}")

            if self._should_stop:
                break

            reconnect_count += 1
            logger.info(f"{reconnect_interval}秒后重连...")
            await asyncio.sleep(reconnect_interval)

    def stop(self) -> None:
        """停止运行"""
        self._should_stop = True
        self._running = False


class QQNet:
    """
    QQ交互子网
    完全吸收Undefined的QQ机器人能力，作为弥娅的一个子网运行
    """

    def __init__(self, miya_core, mlink=None, memory_net=None, tts_net=None):
        """
        初始化QQ子网

        Args:
            miya_core: 弥娅核心实例
            mlink: M-Link 核心实例（用于全局记忆系统）
            memory_net: MemoryNet 全局记忆子网实例
            tts_net: TTSNet TTS子网实例
        """
        self.miya_core = miya_core
        self.mlink = mlink
        self.memory_net = memory_net
        self.tts_net = tts_net
        self.net_id = 'qq_net'
        self.capabilities = [
            'qq_group_chat',
            'qq_private_chat',
            'qq_command',
            'qq_message_history',
            'qq_poke',
            'qq_multimedia',
            'qq_tts',
        ]

        # 配置
        self.onebot_ws_url = None
        self.onebot_token = None
        self.bot_qq = None
        self.superadmin_qq = None

        # 客户端
        self.onebot_client: Optional[QQOneBotClient] = None

        # 对话历史持久化管理
        self.history_manager = None
        self.message_history = {}  # {chat_id: [messages]} - 内存缓存

        # 访问控制
        self.group_whitelist: Set[int] = set()
        self.group_blacklist: Set[int] = set()
        self.user_whitelist: Set[int] = set()
        self.user_blacklist: Set[int] = set()

        # TTS配置
        self.tts_enabled = True  # 默认启用TTS
        self.tts_voice_mode = "text"  # text 或 voice, 默认文本
        self.smart_tts_enabled = False  # 智能TTS判断开关，默认关闭

        # QQ消息分段配置
        self.qq_message_split = True
        self.qq_max_message_length = 200

        # 本地播放配置
        self.local_playback_enabled = False
        self.local_playback_volume = 1.0

        # 音频播放器
        self.audio_player = None

        # 消息处理回调
        self.on_message_callback: Optional[Callable] = None

    def configure(
        self,
        onebot_ws_url: str,
        onebot_token: str = "",
        bot_qq: int = 0,
        superadmin_qq: int = 0,
        group_whitelist: List[int] = None,
        group_blacklist: List[int] = None,
        user_whitelist: List[int] = None,
        user_blacklist: List[int] = None,
        tts_enabled: bool = True,
        tts_voice_mode: str = "text",
        smart_tts_enabled: bool = False,
        qq_message_split: bool = True,
        qq_max_message_length: int = 200,
        local_playback_enabled: bool = False,
        local_playback_volume: float = 1.0,
    ) -> None:
        """配置QQ子网"""
        self.onebot_ws_url = onebot_ws_url
        self.onebot_token = onebot_token
        self.bot_qq = bot_qq
        self.superadmin_qq = superadmin_qq

        if group_whitelist:
            self.group_whitelist = set(group_whitelist)
        if group_blacklist:
            self.group_blacklist = set(group_blacklist)
        if user_whitelist:
            self.user_whitelist = set(user_whitelist)
        if user_blacklist:
            self.user_blacklist = set(user_blacklist)

        self.tts_enabled = tts_enabled
        self.tts_voice_mode = tts_voice_mode
        self.smart_tts_enabled = smart_tts_enabled

        # QQ消息分段配置
        self.qq_message_split = qq_message_split
        self.qq_max_message_length = qq_max_message_length

        # 本地播放配置
        self.local_playback_enabled = local_playback_enabled
        self.local_playback_volume = local_playback_volume

        # 初始化音频播放器
        if local_playback_enabled:
            from core.audio_player import get_audio_player
            self.audio_player = get_audio_player()
            self.audio_player.set_volume(local_playback_volume)

        logger.info(
            f"[QQNet] 配置完成: bot_qq={bot_qq}, "
            f"superadmin={superadmin_qq}, "
            f"groups={len(self.group_whitelist)}/{len(self.group_blacklist)}, "
            f"tts_enabled={tts_enabled}, tts_mode={tts_voice_mode}, "
            f"smart_tts={smart_tts_enabled}, "
            f"message_split={self.qq_message_split}, max_length={self.qq_max_message_length}, "
            f"local_playback={self.local_playback_enabled}, local_volume={self.local_playback_volume}"
        )

    def set_message_callback(self, callback: Callable) -> None:
        """设置消息处理回调"""
        self.on_message_callback = callback

    async def connect(self) -> None:
        """连接到QQ"""
        if not self.onebot_ws_url:
            raise RuntimeError("未配置OneBot WebSocket URL")

        self.onebot_client = QQOneBotClient(
            self.onebot_ws_url,
            self.onebot_token
        )
        self.onebot_client.set_message_handler(self._handle_qq_message)

        await self.onebot_client.connect()
        logger.info("[QQNet] 已连接到QQ")

    async def start(self) -> None:
        """启动QQ子网"""
        await self.onebot_client.run_with_reconnect()

    async def stop(self) -> None:
        """停止QQ子网"""
        if self.onebot_client:
            self.onebot_client.stop()
            await self.onebot_client.disconnect()

    def _is_group_allowed(self, group_id: int) -> bool:
        """检查群是否允许处理"""
        if not self.group_whitelist and not self.group_blacklist:
            return True

        if group_id in self.group_blacklist:
            return False

        if self.group_whitelist:
            return group_id in self.group_whitelist

        return True

    def _is_user_allowed(self, user_id: int) -> bool:
        """检查用户是否允许处理"""
        if not self.user_whitelist and not self.user_blacklist:
            return True

        if user_id in self.user_blacklist:
            return False

        if self.user_whitelist:
            return user_id in self.user_whitelist

        return True

    async def _handle_qq_message(self, event: Dict) -> None:
        """处理QQ消息事件"""
        post_type = event.get("post_type", "")

        # 处理拍一拍
        if post_type == "notice" and event.get("notice_type") == "poke":
            await self._handle_poke(event)
            return

        # 处理消息
        if post_type == "message":
            message_type = event.get("message_type", "")

            if message_type == "group":
                await self._handle_group_message(event)
            elif message_type == "private":
                await self._handle_private_message(event)

    async def _handle_poke(self, event: Dict) -> None:
        """处理拍一拍事件"""
        target_id = event.get("target_id", 0)
        sender_id = event.get("user_id", 0)
        group_id = event.get("group_id", 0)

        # 只有拍机器人才响应
        if target_id != self.bot_qq:
            return

        logger.info(f"[QQNet] 收到拍一拍: sender={sender_id}, group={group_id}")

        # 访问控制
        if group_id == 0:
            if not self._is_user_allowed(sender_id):
                return
        else:
            if not self._is_group_allowed(group_id):
                return

        # 获取发送者信息
        sender_name = f"QQ{sender_id}"
        try:
            if group_id == 0:
                user_info = await self.onebot_client.get_stranger_info(sender_id)
                if user_info:
                    sender_name = user_info.get("nickname", sender_name)
            else:
                member_info = await self.onebot_client.get_group_member_info(
                    group_id, sender_id
                )
                if member_info:
                    card = member_info.get("card", "")
                    nickname = member_info.get("nickname", "")
                    sender_name = card or nickname or sender_name
        except Exception as e:
            logger.warning(f"[QQNet] 获取用户信息失败: {e}")

        # 构建拍一拍消息
        poke_message = QQMessage(
            post_type="notice",
            message_type="poke",
            group_id=group_id,
            user_id=sender_id,
            sender_id=sender_id,
            message=f"{sender_name} 拍了拍你",
            sender_name=sender_name,
            is_at_bot=True,
        )

        # 调用弥娅核心处理
        if self.on_message_callback:
            await self.on_message_callback(poke_message)

    async def _handle_group_message(self, event: Dict) -> None:
        """处理群消息"""
        group_id = event.get("group_id", 0)
        sender_id = event.get("sender", {}).get("user_id", 0)

        # 访问控制
        if not self._is_group_allowed(group_id):
            return

        # 忽略自己的消息
        if sender_id == self.bot_qq:
            return

        # 解析消息
        raw_message = event.get("message", [])

        # 处理不同 OneBot 实现的消息格式
        if isinstance(raw_message, str):
            # 简报模式：message 是字符串，无法直接解析@
            # 需要手动从文本提取@信息
            text = raw_message
            logger.info(f"[QQNet] 检测到简报模式消息: {text[:100]}")
        elif isinstance(raw_message, list):
            # 标准模式：message 是消息段数组
            text = self._extract_text(raw_message)
        else:
            # 未知格式，强制转换为字符串
            text = str(raw_message)
            logger.warning(f"[QQNet] 未知的消息格式: {type(raw_message)}")
            raw_message = []

        sender_info = event.get("sender", {})
        sender_card = sender_info.get("card", "")
        sender_nickname = sender_info.get("nickname", "")
        sender_role = sender_info.get("role", "member")
        sender_title = sender_info.get("title", "")

        # 获取群名
        group_name = ""
        try:
            group_info = await self.onebot_client.get_group_info(group_id)
            if group_info:
                group_name = group_info.get("group_name", "")
        except Exception as e:
            logger.warning(f"[QQNet] 获取群名失败: {e}")

        # 检测是否@机器人
        logger.info(f"[QQNet] 开始检测@消息: bot_qq={self.bot_qq}, raw_message={raw_message}")
        is_at_bot = self._is_at_bot(raw_message)
        logger.info(f"[QQNet] @检测结果: is_at_bot={is_at_bot}")

        # 保存到历史
        self._save_history(
            "group", group_id, sender_id, text,
            sender_name=sender_card or sender_nickname,
            group_name=group_name,
            raw_message=raw_message
        )

        # 提取@列表
        at_list = self._extract_at_list(raw_message)

        # 构建消息对象
        qq_message = QQMessage(
            post_type="message",
            message_type="group",
            group_id=group_id,
            user_id=sender_id,
            sender_id=sender_id,
            message=text,
            raw_message=raw_message,
            sender_name=sender_card or sender_nickname,
            group_name=group_name,
            sender_role=sender_role,
            sender_title=sender_title,
            message_id=event.get("message_id", 0),
            is_at_bot=is_at_bot,
            at_list=at_list,
        )

        # 调用弥娅核心处理
        if self.on_message_callback:
            await self.on_message_callback(qq_message)

    async def _handle_private_message(self, event: Dict) -> None:
        """处理私聊消息"""
        sender_id = event.get("sender", {}).get("user_id", 0)

        # 访问控制
        if not self._is_user_allowed(sender_id):
            return

        # 忽略自己的消息
        if sender_id == self.bot_qq:
            return

        # 解析消息
        raw_message = event.get("message", [])

        # 处理不同 OneBot 实现的消息格式
        if isinstance(raw_message, str):
            # 简报模式
            text = raw_message
        elif isinstance(raw_message, list):
            # 标准模式
            text = self._extract_text(raw_message)
        else:
            # 未知格式
            text = str(raw_message)
            raw_message = []

        sender_info = event.get("sender", {})
        sender_nickname = sender_info.get("nickname", "")

        # 获取用户名
        user_name = sender_nickname
        if not user_name:
            try:
                user_info = await self.onebot_client.get_stranger_info(sender_id)
                if user_info:
                    user_name = user_info.get("nickname", "")
            except Exception as e:
                logger.warning(f"[QQNet] 获取用户名失败: {e}")

        # 保存到历史
        self._save_history(
            "private", sender_id, sender_id, text,
            sender_name=sender_nickname,
            raw_message=raw_message
        )

        # 私聊消息无@列表
        at_list = []

        # 构建消息对象
        qq_message = QQMessage(
            post_type="message",
            message_type="private",
            user_id=sender_id,
            sender_id=sender_id,
            message=text,
            raw_message=raw_message,
            sender_name=user_name or sender_nickname,
            message_id=event.get("message_id", 0),
            at_list=at_list,
        )

        # 调用弥娅核心处理
        if self.on_message_callback:
            await self.on_message_callback(qq_message)

    def _extract_text(self, message: List[Dict]) -> str:
        """从消息段中提取纯文本"""
        text_parts = []
        for segment in message:
            if isinstance(segment, str):
                text_parts.append(segment)
            elif isinstance(segment, dict):
                if segment.get("type") == "text":
                    text_parts.append(segment.get("data", {}).get("text", ""))

        return "".join(text_parts)

    def _is_at_bot(self, message: List[Dict]) -> bool:
        """检测消息是否@了机器人"""
        if not self.bot_qq:
            logger.warning(f"[QQNet] bot_qq 未设置，无法检测@消息")
            return False

        logger.debug(f"[QQNet] 检测@消息: bot_qq={self.bot_qq}, message={message}")

        # 检测 at 消息段（标准 OneBot 格式）
        for segment in message:
            if isinstance(segment, dict):
                seg_type = segment.get("type")
                if seg_type == "at":
                    at_qq = segment.get("data", {}).get("qq")
                    # 统一转换为字符串比较（兼容 OneBot 不同实现）
                    at_qq_str = str(at_qq) if at_qq is not None else None
                    bot_qq_str = str(self.bot_qq)
                    logger.info(f"[QQNet] 发现@消息段: at_qq={at_qq}, bot_qq={self.bot_qq}, 匹配={at_qq_str == bot_qq_str}")
                    if at_qq_str == bot_qq_str:
                        return True

        return False

    def _extract_at_list(self, message: List[Dict]) -> List[int]:
        """提取消息中@的所有用户ID"""
        at_list = []

        # 方法1: 从消息段中提取（标准 OneBot 格式）
        for segment in message:
            if isinstance(segment, dict):
                seg_type = segment.get("type")
                if seg_type == "at":
                    at_qq = segment.get("data", {}).get("qq")
                    if at_qq is not None:
                        try:
                            at_list.append(int(at_qq))
                        except (ValueError, TypeError):
                            pass

        if at_list:
            logger.info(f"[QQNet] 从消息段提取到@列表: {at_list}")

        # 方法2: 如果没有找到@段，尝试从文本中提取（兼容某些 OneBot 实现）
        if not at_list:
            for segment in message:
                if isinstance(segment, dict):
                    seg_type = segment.get("type")
                    if seg_type == "text":
                        text_content = segment.get("data", {}).get("text", "")
                        logger.info(f"[QQNet] 尝试从文本提取@: {text_content}")

                        # 尝试匹配 @QQ号 格式（@12345678）
                        import re
                        qq_pattern = r'@(\d{5,11})'
                        matches = re.findall(qq_pattern, text_content)
                        for match in matches:
                            try:
                                at_qq = int(match)
                                # 避免重复
                                if at_qq not in at_list:
                                    at_list.append(at_qq)
                            except ValueError:
                                pass

                        if at_list:
                            logger.info(f"[QQNet] 从文本提取到@列表: {at_list}")

        return at_list

    def _save_history(
        self,
        msg_type: str,
        chat_id: int,
        sender_id: int,
        text: str,
        sender_name: str = "",
        group_name: str = "",
        raw_message: List[Dict] = None,
    ) -> None:
        """保存消息到历史（内存缓存 + 全局记忆）"""
        if chat_id not in self.message_history:
            self.message_history[chat_id] = []

        self.message_history[chat_id].append({
            "type": msg_type,
            "sender_id": sender_id,
            "text": text,
            "sender_name": sender_name,
            "group_name": group_name,
            "raw_message": raw_message,
            "timestamp": datetime.now(),
        })

        # 限制内存历史长度
        if len(self.message_history[chat_id]) > 100:
            self.message_history[chat_id] = self.message_history[chat_id][-100:]

        # 通过 M-Link memory_flow 保存到全局记忆系统
        asyncio.create_task(self._persist_to_global_memory(
            msg_type=msg_type,
            chat_id=chat_id,
            sender_id=sender_id,
            text=text,
            sender_name=sender_name,
            group_name=group_name
        ))

    async def _persist_to_global_memory(
        self,
        msg_type: str,
        chat_id: int,
        sender_id: int,
        text: str,
        sender_name: str = "",
        group_name: str = ""
    ):
        """持久化保存到全局记忆系统"""
        if not self.memory_net:
            logger.warning("[QQNet] MemoryNet 未初始化，无法保存到全局记忆")
            return

        try:
            # 直接调用 MemoryNet 的对话历史管理器
            await self.memory_net.conversation_history.add_message(
                session_id=f"{msg_type}_{chat_id}",
                role="user",
                content=text,
                agent_id="miya_default",
                metadata={
                    "source": "qq",
                    "msg_type": msg_type,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "group_name": group_name
                }
            )

            logger.debug(f"[QQNet] 消息已保存到全局记忆: {msg_type}_{chat_id}")

        except Exception as e:
            logger.error(f"[QQNet] 保存到全局记忆失败: {e}")

    def get_history(
        self,
        chat_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """获取历史消息"""
        if chat_id not in self.message_history:
            return []

        return self.message_history[chat_id][-limit:]

    async def send_group_message(self, group_id: int, message: str | List[Dict], use_tts: bool = None) -> bool:
        """发送群消息"""
        try:
            # 检查是否需要TTS
            should_use_tts = False
            if self.tts_enabled and self.tts_net and isinstance(message, str):
                if use_tts is None:
                    # 未显式指定，根据tts_voice_mode决定
                    if self.tts_voice_mode == "voice":
                        # 语音模式：启用TTS
                        should_use_tts = True
                        logger.debug(f"[QQNet] 语音模式，启用TTS")
                    elif self.tts_voice_mode == "text":
                        # 文本模式：使用智能判断
                        should_use_tts = self._should_use_tts(message)
                        logger.debug(f"[QQNet] 文本模式，使用智能判断: result={should_use_tts}")
                else:
                    # 显式指定模式，直接使用，跳过智能判断
                    should_use_tts = use_tts
                    logger.debug(f"[QQNet] 显式指定TTS模式: use_tts={use_tts}")

            # 使用TTS
            if should_use_tts:
                logger.debug(f"[QQNet] 使用TTS发送群消息: group={group_id}")
                await self._send_tts_group_message(group_id, message)
                return True

            # 普通消息 - 支持自动分段
            if isinstance(message, str):
                # 智能判断消息长度类型
                length_type = self._get_message_length_type(message)
                logger.info(f"[QQNet] 消息长度判断: type={length_type}, length={len(message)}")

                if self.qq_message_split and len(message) > self.qq_max_message_length:
                    logger.debug(f"[QQNet] 消息过长,自动分段: length={len(message)}")
                    segments = self._split_message(message, self.qq_max_message_length)
                    for i, segment in enumerate(segments):
                        await self.onebot_client.send_group_message(group_id, segment)
                        # 分段之间稍微延迟
                        if i < len(segments) - 1:
                            await asyncio.sleep(0.5)
                    return True
                else:
                    result = await self.onebot_client.send_group_message(group_id, message)
                    logger.debug(f"[QQNet] 发送群消息: group={group_id}")
                    return True

            # 列表格式消息(富文本)
            result = await self.onebot_client.send_group_message(group_id, message)
            logger.debug(f"[QQNet] 发送群消息: group={group_id}")
            return True
        except Exception as e:
            logger.error(f"[QQNet] 发送群消息失败: {e}")
            return False

    async def send_private_message(self, user_id: int, message: str | List[Dict], use_tts: bool = None) -> bool:
        """发送私聊消息"""
        try:
            # 检查是否需要TTS
            should_use_tts = False
            if self.tts_enabled and self.tts_net and isinstance(message, str):
                if use_tts is None:
                    # 未显式指定，根据tts_voice_mode决定
                    if self.tts_voice_mode == "voice":
                        # 语音模式：启用TTS
                        should_use_tts = True
                        logger.debug(f"[QQNet] 语音模式，启用TTS")
                    elif self.tts_voice_mode == "text":
                        # 文本模式：使用智能判断
                        should_use_tts = self._should_use_tts(message)
                        logger.debug(f"[QQNet] 文本模式，使用智能判断: result={should_use_tts}")
                else:
                    # 显式指定模式，直接使用，跳过智能判断
                    should_use_tts = use_tts
                    logger.debug(f"[QQNet] 显式指定TTS模式: use_tts={use_tts}")

            # 使用TTS
            if should_use_tts:
                logger.debug(f"[QQNet] 使用TTS发送私聊消息: user={user_id}")
                await self._send_tts_private_message(user_id, message)
                return True

            # 普通消息 - 支持自动分段
            if isinstance(message, str):
                # 智能判断消息长度类型
                length_type = self._get_message_length_type(message)
                logger.info(f"[QQNet] 消息长度判断: type={length_type}, length={len(message)}")

                if self.qq_message_split and len(message) > self.qq_max_message_length:
                    logger.debug(f"[QQNet] 消息过长,自动分段: length={len(message)}")
                    segments = self._split_message(message, self.qq_max_message_length)
                    for i, segment in enumerate(segments):
                        await self.onebot_client.send_private_message(user_id, segment)
                        # 分段之间稍微延迟
                        if i < len(segments) - 1:
                            await asyncio.sleep(0.5)
                    return True
                else:
                    result = await self.onebot_client.send_private_message(user_id, message)
                    logger.debug(f"[QQNet] 发送私聊消息: user={user_id}")
                    return True

            # 列表格式消息(富文本)
            result = await self.onebot_client.send_private_message(user_id, message)
            logger.debug(f"[QQNet] 发送私聊消息: user={user_id}")
            return True
        except Exception as e:
            logger.error(f"[QQNet] 发送私聊消息失败: {e}")
            return False

    def _split_message(self, text: str, max_length: int) -> list:
        """
        分割长消息为多个片段

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            list: 分割后的文本片段
        """
        import re

        if len(text) <= max_length:
            return [text]

        segments = []
        current = ""

        # 按句子分割
        sentences = re.split(r'([。！？\n])', text)

        for sentence in sentences:
            if not sentence:
                continue

            if len(current) + len(sentence) <= max_length:
                current += sentence
            else:
                if current:
                    segments.append(current)
                current = sentence

        if current:
            segments.append(current)

        return segments

    def _get_message_length_type(self, text: str) -> str:
        """
        智能判断消息长度类型

        根据消息长度和内容自动判断消息类型：
        - short: 短文本（1-50字）
        - medium: 中等文本（51-150字）
        - long: 长文本（151-300字）
        - extra_long: 超长文本（>300字）

        Args:
            text: 消息文本

        Returns:
            str: 消息长度类型 (short/medium/long/extra_long)
        """
        text_length = len(text)

        if text_length <= 50:
            return "short"
        elif text_length <= 150:
            return "medium"
        elif text_length <= 300:
            return "long"
        else:
            return "extra_long"

    def _should_use_tts(self, text: str) -> bool:
        """
        智能判断是否应该使用TTS发送语音

        根据消息内容、长度、格式等因素自动判断

        Args:
            text: 消息文本

        Returns:
            bool: 是否使用TTS
        """
        # 如果未启用智能TTS判断，直接返回False
        if not self.smart_tts_enabled:
            logger.debug(f"[QQNet] 智能TTS判断未启用，使用文字")
            return False

        text_length = len(text)
        text_stripped = text.strip()

        # 1. 极短消息（1-5字）- 纯文字
        if text_length <= 5:
            logger.debug(f"[QQNet] 消息过短，使用文字: length={text_length}")
            return False

        # 2. 包含大量代码或特殊格式 - 纯文字
        code_indicators = ["```", "```python", "```json", "```javascript",
                         "```html", "```css", "<code>", "<pre>"]
        if any(indicator in text for indicator in code_indicators):
            logger.debug(f"[QQNet] 包含代码块，使用文字")
            return False

        # 3. 包含大量特殊符号和换行（如表格、列表）- 纯文字
        special_char_count = sum(1 for c in text if c in ['|', '─', '│', '┌', '┐', '└', '┘', '├', '┤', '┬', '┴'])
        line_count = text.count('\n')
        if special_char_count > 10 or line_count > 15:
            logger.debug(f"[QQNet] 包含大量特殊符号或换行，使用文字: special_chars={special_char_count}, lines={line_count}")
            return False

        # 4. 超长消息（>300字）- 纯文字
        if text_length > 300:
            logger.debug(f"[QQNet] 消息过长，使用文字: length={text_length}")
            return False

        # 5. 短消息（6-50字）- 使用TTS语音
        if 6 <= text_length <= 50:
            logger.debug(f"[QQNet] 短消息，使用TTS语音: length={text_length}")
            return True

        # 6. 中等消息（51-150字）- 根据内容判断
        if 51 <= text_length <= 150:
            # 检查是否适合语音（对话、问候等）
            dialogue_indicators = ["好的", "明白", "收到", "没问题", "当然",
                               "你好", "谢谢", "再见", "晚安", "早安", "呢", "呀",
                               "哈", "嗯", "哦", "～", "~", "！", "!", "？", "?"]
            text_lower = text.lower()
            if any(indicator in text for indicator in dialogue_indicators):
                logger.debug(f"[QQNet] 中等对话消息，使用TTS语音: length={text_length}")
                return True
            # 其他中等消息用文字
            logger.debug(f"[QQNet] 中等非对话消息，使用文字: length={text_length}")
            return False

        # 7. 较长消息（151-300字）- 根据内容判断
        if 151 <= text_length <= 300:
            # 检查是否包含大量专业术语或数据
            technical_indicators = ["API", "HTTP", "JSON", "XML", "SQL", "数据库",
                                  "配置", "参数", "函数", "方法", "类", "变量",
                                  "数组", "对象", "字符串", "数字", "布尔"]
            technical_count = sum(1 for indicator in technical_indicators if indicator in text)
            if technical_count > 5:
                logger.debug(f"[QQNet] 技术性内容过多，使用文字: technical_count={technical_count}")
                return False
            # 检查句子结构（是否有大量标点符号）
            punctuation_count = text.count('，') + text.count('.') + text.count('。') + text.count('！')
            if punctuation_count > 10:
                logger.debug(f"[QQNet] 句子过多，使用文字: punctuation={punctuation_count}")
                return False
            # 其他较长消息可以用TTS
            logger.debug(f"[QQNet] 较长消息，使用TTS语音: length={text_length}")
            return True

        # 默认不使用TTS
        logger.debug(f"[QQNet] 默认使用文字: length={text_length}")
        return False

    async def _send_tts_group_message(self, group_id: int, text: str) -> bool:
        """使用TTS发送群语音消息"""
        try:
            # 分段处理长文本
            if self.qq_message_split and len(text) > self.qq_max_message_length:
                segments = self._split_message(text, self.qq_max_message_length)
                for segment in segments:
                    await self._send_tts_segment(group_id, segment, is_group=True)
                return True

            # 直接发送
            return await self._send_tts_segment(group_id, text, is_group=True)

        except Exception as e:
            logger.error(f"[QQNet] 发送TTS群消息失败: {e}")
            # 回退到文本
            await self.onebot_client.send_group_message(group_id, text)
            return False

    async def _send_tts_private_message(self, user_id: int, text: str) -> bool:
        """使用TTS发送私聊语音消息"""
        try:
            # 分段处理长文本
            if self.qq_message_split and len(text) > self.qq_max_message_length:
                segments = self._split_message(text, self.qq_max_message_length)
                for segment in segments:
                    await self._send_tts_segment(user_id, segment, is_group=False)
                return True

            # 直接发送
            return await self._send_tts_segment(user_id, text, is_group=False)

        except Exception as e:
            logger.error(f"[QQNet] 发送TTS私聊消息失败: {e}")
            # 回退到文本
            await self.onebot_client.send_private_message(user_id, text)
            return False

    async def _send_tts_segment(self, target_id: int, text: str, is_group: bool) -> bool:
        """发送单个TTS语音片段"""
        tmp_path = None
        wav_path = None
        try:
            # 合成语音 - QQ 需要 silk 格式
            audio_data = await self.tts_net.synthesize(text, output_format="silk")
            if not audio_data:
                logger.warning("[QQNet] TTS合成失败,回退到文本")
                if is_group:
                    await self.onebot_client.send_group_message(target_id, text)
                else:
                    await self.onebot_client.send_private_message(target_id, text)
                return False

            # 创建 silk 临时文件（QQ 用）
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix=".silk", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            # 如果需要本地播放，尝试合成 WAV 格式
            wav_path = None
            if self.local_playback_enabled and self.audio_player:
                try:
                    # 尝试用 WAV 格式再次合成（用于本地播放）
                    wav_data = await self.tts_net.synthesize(text, output_format="wav")
                    if wav_data:
                        wav_path = tmp_path.replace('.silk', '.wav')
                        with open(wav_path, 'wb') as wav_file:
                            wav_file.write(wav_data)
                        logger.debug(f"[QQNet] 创建 WAV 文件用于本地播放: {wav_path}")
                except Exception as e:
                    logger.warning(f"[QQNet] 创建 WAV 失败: {e}")
                    wav_path = None

            try:
                # 构建语音消息段
                voice_message = [{
                    "type": "record",
                    "data": {
                        "file": f"file:///{tmp_path.replace(os.sep, '/')}"
                    }
                }]

                # 发送语音消息
                if is_group:
                    result = await self.onebot_client.send_group_message(target_id, voice_message)
                else:
                    result = await self.onebot_client.send_private_message(target_id, voice_message)

                logger.info(f"[QQNet] TTS语音片段已发送: target={target_id}, text={text[:30]}...")

                # 本地播放（异步）- 使用 WAV 文件
                if self.local_playback_enabled and self.audio_player and wav_path:
                    asyncio.create_task(self._play_audio_async(wav_path))

                return True
            finally:
                # 延迟清理临时文件（等待本地播放完成）
                await asyncio.sleep(0.5)  # QQ 发送需要时间

                if self.local_playback_enabled and self.audio_player:
                    # 等待播放完成后再删除
                    await self.audio_player.wait_until_finished()

                # 清理临时文件
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    if wav_path and os.path.exists(wav_path):
                        os.unlink(wav_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"[QQNet] 发送TTS语音片段失败: {e}")
            return False



    def set_tts_mode(self, mode: str):
        """设置TTS模式 (text 或 voice)"""
        if mode in ["text", "voice"]:
            self.tts_voice_mode = mode
            logger.info(f"[QQNet] TTS模式已设置为: {mode}")
        else:
            logger.warning(f"[QQNet] 无效的TTS模式: {mode}")

    def toggle_tts(self, enabled: bool = None):
        """切换TTS开关"""
        if enabled is None:
            self.tts_enabled = not self.tts_enabled
        else:
            self.tts_enabled = enabled
        logger.info(f"[QQNet] TTS已{'启用' if self.tts_enabled else '禁用'}")
        return self.tts_enabled

    async def _play_audio_async(self, audio_path: str):
        """异步播放音频"""
        try:
            if self.audio_player:
                await self.audio_player.play(audio_path, self.local_playback_volume)
        except Exception as e:
            logger.error(f"[QQNet] 本地播放失败: {e}")

    def toggle_local_playback(self, enabled: bool = None):
        """切换本地播放开关"""
        if enabled is None:
            self.local_playback_enabled = not self.local_playback_enabled
        else:
            self.local_playback_enabled = enabled

        # 动态初始化音频播放器
        if self.local_playback_enabled and self.audio_player is None:
            from core.audio_player import get_audio_player
            self.audio_player = get_audio_player()
            self.audio_player.set_volume(self.local_playback_volume)

        logger.info(f"[QQNet] 本地播放已{'启用' if self.local_playback_enabled else '禁用'}")
        return self.local_playback_enabled

    def set_local_playback_volume(self, volume: float):
        """设置本地播放音量"""
        self.local_playback_volume = max(0.0, min(1.0, volume))
        if self.audio_player:
            self.audio_player.set_volume(self.local_playback_volume)
        logger.info(f"[QQNet] 本地播放音量设置为: {self.local_playback_volume}")

    def toggle_smart_tts(self, enabled: bool = None):
        """切换智能TTS判断开关"""
        if enabled is None:
            self.smart_tts_enabled = not self.smart_tts_enabled
        else:
            self.smart_tts_enabled = enabled
        logger.info(f"[QQNet] 智能TTS判断已{'启用' if self.smart_tts_enabled else '禁用'}")
        return self.smart_tts_enabled

    async def process_request(self, request: Dict) -> Dict:
        """处理QQ子网请求"""
        req_type = request.get("type")

        if req_type == "send_group":
            success = await self.send_group_message(
                request.get("group_id"),
                request.get("message")
            )
            return {"success": success}

        elif req_type == "send_private":
            success = await self.send_private_message(
                request.get("user_id"),
                request.get("message")
            )
            return {"success": success}

        elif req_type == "get_history":
            history = self.get_history(
                request.get("chat_id"),
                request.get("limit", 20)
            )
            return {"history": history}

        elif req_type == "get_connection_status":
            if self.onebot_client:
                return {"status": self.onebot_client.connection_status()}
            return {"status": {"connected": False}}

        elif req_type == "toggle_smart_tts":
            enabled = request.get("enabled")
            result = self.toggle_smart_tts(enabled)
            return {"success": True, "enabled": result}

        elif req_type == "get_tts_status":
            return {
                "tts_enabled": self.tts_enabled,
                "tts_voice_mode": self.tts_voice_mode,
                "smart_tts_enabled": self.smart_tts_enabled,
                "local_playback_enabled": self.local_playback_enabled,
                "local_playback_volume": self.local_playback_volume
            }

        else:
            return {"error": "Unknown request type"}
