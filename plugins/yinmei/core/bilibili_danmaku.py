"""
B站弹幕平台适配器 - 将 B站直播间弹幕接入弥娅消息流

基于 bilibili-api-python 的弹幕采集，
消息通过 LiveStreamHub.process_message() 路由。
"""

import asyncio
import logging
import threading
from typing import Callable

from plugins.yinmei.tools import singleton
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)


@singleton
class BilibiliDanmaku:
    """B站弹幕采集器"""

    def __init__(self):
        self._data = SharedData()
        self._running = False
        self._thread: threading.Thread | None = None
        self._message_callback: Callable | None = None
        self._client = None

    @property
    def room_id(self) -> int:
        return self._data.bili_room_id

    @property
    def is_enabled(self) -> bool:
        return self._data.bili_room_id > 0 and bool(self._data.bili_sessdata)

    def set_callback(self, callback: Callable):
        """设置消息回调 callback(traceid: str, msg: str, uid: str, username: str)"""
        self._message_callback = callback

    def start(self):
        """启动弹幕采集"""
        if not self.is_enabled:
            logger.warning("B站弹幕未配置 (room_id 或 sessdata 为空)")
            return

        if self._running:
            logger.info("B站弹幕已在运行中")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()
        logger.info(f"B站弹幕采集已启动，房间号: {self._data.bili_room_id}")

    def stop(self):
        """停止弹幕采集"""
        self._running = False
        if self._client:
            try:
                self._client.stop()
            except Exception:
                pass
            self._client = None
        logger.info("B站弹幕采集已停止")

    def _run_async(self):
        try:
            asyncio.run(self._listen())
        except Exception as e:
            logger.exception(f"B站弹幕运行异常: {e}")
        finally:
            self._running = False

    async def _listen(self):
        try:
            from bilibili_api import live, sync

            room = live.LiveDanmaku(self._data.bili_room_id)

            @room.on("DANMU_MSG")
            async def on_danmaku(event):
                try:
                    info = event.get("data", {}).get("info", [])
                    if len(info) >= 2:
                        msg = str(info[1])
                        uid = str(info[2][0]) if len(info) > 2 else "0"
                        username = str(info[2][1]) if len(info) > 2 and len(info[2]) > 1 else "bilibili_user"
                        logger.debug(f"弹幕 [{username}]: {msg}")

                        if self._message_callback:
                            import uuid

                            traceid = str(uuid.uuid4())
                            self._message_callback(traceid, msg, uid, username)
                except Exception as e:
                    logger.error(f"弹幕处理异常: {e}")

            logger.info(f"B站弹幕连接房间 {self._data.bili_room_id} ...")
            await room.connect()
        except ImportError:
            logger.warning("bilibili-api-python 未安装，B站弹幕功能不可用。pip install bilibili-api-python")
        except Exception as e:
            if self._running:
                logger.exception(f"B站弹幕连接异常: {e}")
