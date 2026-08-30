"""
跳舞/表情视频模块
"""

import logging
import random
import time
from threading import Thread

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController, VideoControl, VideoStatus

logger = logging.getLogger(__name__)


@singleton
class DanceEngine:
    """跳舞 + 表情视频引擎"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()

    def check_dance(self, sched=None):
        if not self._data.DanceQueueList.empty() and self._data.is_dance == 2:
            self._data.is_dance = 1
            if sched:
                sched.pause()
            item = self._data.DanceQueueList.get()
            self._play_dance(item)
            if sched:
                sched.resume()
            self._data.is_dance = 2

    def _play_dance(self, item: dict):
        video_path = item["video_path"]
        logger.info(f"播放跳舞: {video_path}")
        self._obs.control_video("背景音乐", VideoControl.PAUSE)

        if video_path != self._data.dance_now_path:
            self._obs.play_video("video", video_path)
        else:
            self._obs.control_video("video", VideoControl.RESTART)

        self._data.dance_now_path = video_path
        time.sleep(1)
        while self._obs.get_video_status("video") != VideoStatus.ENDED.value and self._data.is_dance == 1:
            time.sleep(1)

        self._obs.control_video("video", VideoControl.STOP)
        self._obs.control_video("背景音乐", VideoControl.PLAY)

    def _find_video(self, query: str, videos: list) -> str:
        if not videos:
            return ""
        if not query:
            return random.choice(videos)
        matches = StringUtil.fuzzy_match_list(query, videos)
        if matches:
            return random.choice(matches)
        return ""

    def msg_deal_dance(self, traceid: str, query: str, uid: str, username: str) -> bool:
        text = ["跳舞", "跳一下", "舞蹈"]
        is_contain = StringUtil.has_string_reg_list(f"^{text}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(text, query)
            q = query[num:].strip()
            video_path = self._find_video(q, self._data.dance_video)
            if video_path:
                self._data.DanceQueueList.put(
                    {
                        "traceid": traceid,
                        "prompt": q,
                        "username": username,
                        "video_path": video_path,
                    }
                )
            else:
                logger.info(f"跳舞视频不存在: {q}")
            return True
        return False

    def msg_deal_emote(self, traceid: str, query: str, uid: str, username: str) -> bool:
        text = ["#", "表情"]
        is_contain = StringUtil.has_string_reg_list(f"^{text}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(text, query)
            q = query[num:].strip()
            video_path = ""
            if q in ("rnd", "随机"):
                if self._data.emote_video:
                    video_path = random.choice(self._data.emote_video)
            else:
                video_path = self._find_video(q, self._data.emote_video)
            if video_path:
                self._emote_play(video_path, self._data.is_dance == 1)
            return True
        if self._data.is_dance == 1:
            return True
        return False

    def _emote_play(self, video_path: str, is_dancing: bool):
        self._data.emote_video_lock.acquire()
        try:
            if is_dancing:
                self._obs.control_video("video", VideoControl.PAUSE)

            if video_path != self._data.emote_now_path:
                self._obs.play_video("表情", video_path)
            else:
                self._obs.control_video("表情", VideoControl.RESTART)

            self._data.emote_now_path = video_path
            time.sleep(1)
            sec = 20
            while self._obs.get_video_status("表情") != VideoStatus.ENDED.value and sec > 0:
                time.sleep(1)
                sec -= 1
            time.sleep(1)
            self._obs.control_video("表情", VideoControl.STOP)

            if is_dancing:
                self._obs.control_video("video", VideoControl.PLAY)
        finally:
            self._data.emote_video_lock.release()
