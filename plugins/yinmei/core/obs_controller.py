"""
OBS 直播软件控制模块 - 场景/视频/图片/文字
"""

import logging
from enum import Enum

from plugins.yinmei.tools import singleton
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)


class VideoControl(Enum):
    RESTART = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
    STOP = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP"
    PAUSE = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE"
    PLAY = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
    NEXT = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_NEXT"
    PREVIOUS = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PREVIOUS"


class VideoStatus(Enum):
    STOPPED = "OBS_MEDIA_STATE_STOPPED"
    PAUSED = "OBS_MEDIA_STATE_PAUSED"
    PLAYING = "OBS_MEDIA_STATE_PLAYING"
    ENDED = "OBS_MEDIA_STATE_ENDED"


@singleton
class OBSController:
    """OBS WebSocket 控制器"""

    def __init__(self):
        self._data = SharedData()
        self._ws = None
        self._connected = False
        self._init_connection()

    def _init_connection(self):
        if not self._data.obs_switch:
            logger.warning("OBS 直播开关已关闭")
            return
        try:
            from obswebsocket import obsws

            self._ws = obsws(
                self._data.obs_host,
                self._data.obs_port,
                self._data.obs_password,
            )
            self._ws.connect()
            self._connected = True
            logger.info("OBS 直播连接成功")
        except ImportError:
            logger.warning("obswebsocket 未安装，OBS 功能不可用")
        except Exception as e:
            logger.error(f"OBS 连接失败: {e}")

    def _ensure_connected(self):
        if not self._connected or self._ws is None:
            return False
        return True

    def play_video(self, input_name: str, file_path: str):
        if not self._ensure_connected():
            return
        from obswebsocket import requests

        self._ws.call(
            requests.SetInputSettings(
                inputName=input_name,
                inputSettings={"local_file": file_path},
            )
        )

    def control_video(self, input_name: str, action: VideoControl):
        if not self._ensure_connected():
            return
        from obswebsocket import requests

        self._ws.call(
            requests.TriggerMediaInputAction(
                inputName=input_name,
                mediaAction=action.value,
            )
        )

    def get_video_status(self, input_name: str) -> str:
        if not self._ensure_connected():
            return VideoStatus.ENDED.value
        from obswebsocket import requests

        data = self._ws.call(requests.GetMediaInputStatus(inputName=input_name))
        return data.datain["mediaState"]

    def change_scene(self, scene_name: str):
        if not self._ensure_connected():
            return
        from obswebsocket import requests

        self._ws.call(requests.SetCurrentProgramScene(sceneName=scene_name))

    def show_image(self, input_name: str, file_path: str):
        if not self._ensure_connected():
            return
        from obswebsocket import requests

        self._ws.call(
            requests.SetInputSettings(
                inputName=input_name,
                inputSettings={"file": file_path},
            )
        )

    def show_text(self, input_name: str, text: str):
        if not self._ensure_connected():
            return
        from obswebsocket import requests

        self._ws.call(
            requests.SetInputSettings(
                inputName=input_name,
                inputSettings={"text": text},
            )
        )

    def disconnect(self):
        if self._ws:
            self._ws.disconnect()
            self._connected = False
