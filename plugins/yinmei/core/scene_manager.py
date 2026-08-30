"""
场景 & 换装管理器

场景：OBS 场景切换 + 昼夜自动切换 + 夜间限制
换装：Live2D 参数控制 + 服装状态追踪
"""

import logging
import re
import time
from threading import Thread

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController, VideoControl, VideoStatus

logger = logging.getLogger(__name__)


# 昼夜时间范围
DAY_START = "06:00:00"
DAY_END = "16:59:59"
TWILIGHT_START = "17:00:00"
TWILIGHT_END = "17:59:59"

# 夜间允许访问的场景
NIGHT_ALLOWED = {"神社", "粉色房间", "海岸花坊"}


@singleton
class SceneClothesManager:
    """场景切换 + 换装一体化管理"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()
        self._default_scene = "海岸花坊"

    # ==================== 场景初始化 ====================

    def init_scene(self):
        """初始化默认场景"""
        scene_name = self._default_scene
        self._obs.change_scene(scene_name)
        logger.info(f"初始化场景: {scene_name}")

        if scene_name in self._data.song_background:
            song = self._data.song_background[scene_name]
            self._obs.play_video("背景音乐", song)
            time.sleep(1)
            self._obs.control_video("背景音乐", VideoControl.RESTART)

    # ==================== 场景切换 ====================

    def change_scene(self, scene_name: str) -> bool:
        """切换场景（带夜间限制检查）"""
        if not self._allow_scene(scene_name):
            logger.info(f"当前时间不允许进入场景: {scene_name}")
            return False

        self._obs.change_scene(scene_name)
        logger.info(f"切换场景: {scene_name}")

        if scene_name in self._data.song_background:
            song = self._data.song_background[scene_name]
            if self._obs.get_video_status("背景音乐") == VideoStatus.PAUSED.value:
                self._obs.play_video("背景音乐", song)
                time.sleep(1)
                self._obs.control_video("背景音乐", VideoControl.PAUSE)
            else:
                self._obs.play_video("背景音乐", song)
        return True

    def _allow_scene(self, scene_name: str, now: str = "") -> bool:
        """检查当前时间是否允许访问该场景"""
        now = now or time.strftime("%H:%M:%S", time.localtime())
        is_night = ("18:00:00" <= now <= "24:00:00") or ("00:00:00" < now < "06:00:00")
        if is_night and scene_name not in NIGHT_ALLOWED:
            return False
        return True

    # ==================== 昼夜切换 ====================

    def check_scene_time(self):
        """根据时间切换昼夜背景"""
        now = time.strftime("%H:%M:%S", time.localtime())

        if DAY_START <= now <= DAY_END:
            logger.info("现在是白天，切换白天背景")
            self._apply_daytime()
        elif TWILIGHT_START <= now <= TWILIGHT_END:
            logger.info("现在是黄昏，切换黄昏背景")
            self._apply_twilight()
        else:
            logger.info("现在是晚上，切换夜晚背景")
            self._apply_night()

    def _apply_daytime(self):
        """应用白天 OBS 素材"""
        self._obs.show_image("海岸花坊背景", self._data.get_scene_bg("海岸花坊", "day"))
        self._obs.show_image("粉色房间背景", self._data.get_scene_bg("粉色房间", "day"))
        self._obs.show_image("粉色房间桌面", self._data.get_scene_bg("粉色房间桌面", "day"))
        self._obs.play_video("神社背景", self._data.get_scene_bg("神社", "day"))

    def _apply_twilight(self):
        """应用黄昏 OBS 素材"""
        self._obs.show_image("粉色房间背景", self._data.get_scene_bg("粉色房间", "twilight"))
        self._obs.show_image("粉色房间桌面", self._data.get_scene_bg("粉色房间桌面", "twilight"))

    def _apply_night(self):
        """应用夜景 OBS 素材"""
        self._obs.show_image("海岸花坊背景", self._data.get_scene_bg("海岸花坊", "night"))
        self._obs.show_image("粉色房间背景", self._data.get_scene_bg("粉色房间", "night"))
        self._obs.show_image("粉色房间桌面", self._data.get_scene_bg("粉色房间桌面", "night"))
        self._obs.play_video("神社背景", self._data.get_scene_bg("神社", "night"))

    # ==================== 换装 ====================

    def change_clothes(self, clothes_name: str) -> bool:
        """切换服装"""
        if not clothes_name:
            return False

        logger.info(f"换装: {self._data.now_clothes} → {clothes_name}")

        # 脱掉当前服装
        self._live2d_action(self._data.now_clothes)

        # 穿上新服装
        Thread(target=self._live2d_action, args=(clothes_name,), daemon=True).start()
        self._data.now_clothes = clothes_name
        return True

    @staticmethod
    def _live2d_action(action: str):
        try:
            from plugins.yinmei.routes import live2d_trigger_action

            live2d_trigger_action(action)
        except Exception as e:
            logger.debug(f"Live2D 动作发送异常: {e}")

    def msg_deal_scene(self, traceid: str, query: str, uid: str, username: str) -> bool:
        """处理场景切换消息"""
        text = ["切换", "进入"]
        num = StringUtil.is_index_contain_string(text, query)
        if num > 0:
            scene_name = re.sub("(。|,|，)", "", query[num:].strip())
            logger.info(f"[{traceid}]切换场景: {scene_name}")
            self.change_scene(scene_name)
            return True
        return False

    def msg_deal_clothes(self, traceid: str, query: str, uid: str, username: str) -> bool:
        """处理换装消息"""
        text = ["换装", "换衣服", "穿衣服"]
        num = StringUtil.is_index_contain_string(text, query)
        if num > 0:
            clothes_name = re.sub("(。|,|，)", "", query[num:].strip())
            logger.info(f"[{traceid}]换装: {clothes_name}")
            self.change_clothes(clothes_name)
            return True
        return False
