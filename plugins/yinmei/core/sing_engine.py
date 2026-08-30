"""
唱歌模块 - AI 翻唱+播放
"""

import json
import logging
import os
import re
import time
from threading import Thread

import requests

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController, VideoControl, VideoStatus

logger = logging.getLogger(__name__)


@singleton
class SingEngine:
    """AI 唱歌引擎"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()

    def check_sing(self):
        if not self._data.SongQueueList.empty():
            item = self._data.SongQueueList.get()
            logger.info(f"启动唱歌: {item}")
            Thread(target=self._sing, args=(item["prompt"], item["username"]), daemon=True).start()

    def check_playlist(self):
        if not self._data.SongMenuList.empty() and self._data.is_singing == 2:
            self._data.play_song_lock.acquire()
            try:
                item = self._data.SongMenuList.get()
                self._data.SongNowName = item
                self._data.is_singing = 1
                self._obs.control_video("背景音乐", VideoControl.PAUSE)
                self._play(item["is_created"], item["songname"], item["song_path"], item["username"], item["query"])
                if self._data.SongMenuList.qsize() == 0:
                    self._obs.control_video("背景音乐", VideoControl.PLAY)
            finally:
                self._data.is_singing = 2
                self._data.SongNowName = {}
                self._data.play_song_lock.release()

    def _sing(self, songname: str, username: str):
        try:
            resp = requests.get(f"{self._data.sing_url}/musicInfo/{songname}", timeout=(5, 10))
            music = resp.json()
            sid = music.get("id", 0)
            real_name = music.get("songName", songname)

            if sid == 0:
                logger.info(f"歌库不存在《{songname}》")
                return

            song_path = f"./output/{real_name}/"

            if self._exist_in_queue(self._data.SongMenuList, real_name):
                return

            is_created = 0
            if os.path.exists(f"{song_path}/accompany.wav") or os.path.exists(f"{song_path}/vocal.wav"):
                logger.info(f"本地存在歌曲: {song_path}")
                is_created = 1
            else:
                is_created = self._check_remote(songname)
                if is_created == 1:
                    self._download(songname, "get_accompany", "accompany", song_path)
                    self._download(songname, "get_vocal", "vocal", song_path)
                    logger.info(f"远程已转换歌曲《{songname}》")

            if is_created == 0:
                logger.info(f"需要生成歌曲《{songname}》")
                while self._data.is_creating_song == 1:
                    time.sleep(1)
                is_created = self._create_song(real_name, songname, song_path)

            if is_created == 2:
                return

            self._obs.show_text("状态提示", f"{self._data.Ai_Name}已经学会歌曲《{real_name}》")
            self._data.SongMenuList.put(
                {
                    "username": username,
                    "songname": real_name,
                    "is_created": is_created,
                    "song_path": song_path,
                    "query": songname,
                }
            )
        except Exception:
            logger.exception("【唱歌】异常")

    def _create_song(self, real_name: str, query: str, song_path: str) -> int:
        try:
            self._data.create_song_lock.acquire()
            self._data.is_creating_song = 1

            match = re.search(self._data.song_not_convert, real_name) if self._data.song_not_convert else None
            if match:
                resp = requests.get(f"{self._data.sing_url}/download_origin_song/{real_name}", timeout=(5, 120))
                info = resp.json()
                self._download(info["songName"], "get_audio", "vocal", song_path)
                return 1

            resp = requests.get(f"{self._data.sing_url}/append_song/{query}", timeout=(5, 10))
            info = resp.json()
            real_name = info.get("songName", real_name)
            song_path = f"./output/{real_name}/"
            status = info.get("status", "")

            if status in ("processing", "processed", "waiting"):
                for i in range(self._data.create_song_timout):
                    if self._data.is_creating_song != 1:
                        break
                    created = self._check_remote(real_name)
                    if created == 2:
                        return 2
                    if created == 1:
                        self._download(real_name, "get_accompany", "accompany", song_path)
                        self._download(real_name, "get_vocal", "vocal", song_path)
                        return 1
                    self._obs.show_text("状态提示", f"当前{self._data.Ai_Name}学唱歌曲《{real_name}》第{i}秒")
                    time.sleep(1)
            return 2
        except Exception:
            logger.exception(f"《{real_name}》创建歌曲异常")
            return 2
        finally:
            self._data.is_creating_song = 2
            self._data.create_song_lock.release()

    def _check_remote(self, songname: str) -> int:
        try:
            resp = requests.get(f"{self._data.sing_url}/accompany_vocal_status", timeout=(5, 10))
            info = resp.json()
            converted = info.get("converted_file", [])
            failed = info.get("convertfail", [])
            if songname in failed:
                return 2
            for fname in converted:
                if songname == fname:
                    return 1
        except Exception:
            pass
        return 0

    def _download(self, songname: str, endpoint: str, filename: str, folder: str):
        try:
            resp = requests.get(f"{self._data.sing_url}/{endpoint}/{songname}", timeout=(5, 120))
            os.makedirs(folder, exist_ok=True)
            with open(f"{folder}/{filename}.wav", "wb") as f:
                f.write(resp.content)
        except Exception:
            logger.exception(f"下载歌曲文件异常: {songname}")

    def _play(self, is_created: int, songname: str, song_path: str, username: str, query: str):
        try:
            if is_created != 1:
                return
            logger.info(f"播放歌曲《{songname}》")

            from plugins.yinmei.core.image_search import ImageSearch

            Thread(
                target=ImageSearch()._search_and_output, args=({"prompt": query, "username": username},), daemon=True
            ).start()

            import subprocess

            def _play_audio(exe: str, path: str):
                self._data.sing_play_flag = 1
                subprocess.run(f'{exe} -vo null --volume=70 --start=0 "{path}" 1>nul', shell=True)
                self._data.sing_play_flag = 0

            Thread(target=_play_audio, args=("accompany.exe", song_path + "accompany.wav"), daemon=True).start()
            Thread(target=_play_audio, args=("song.exe", song_path + "vocal.wav"), daemon=True).start()

            time.sleep(3)
            while self._data.sing_play_flag == 1:
                time.sleep(1)
            self._obs.control_video("伴奏", VideoControl.STOP)
        except Exception:
            logger.exception(f"《{songname}》播放异常")

    def _exist_in_queue(self, queue_obj, name: str) -> bool:
        if self._data.SongNowName.get("songname") == name:
            return True
        return any(queue_obj.queue[i].get("songname") == name for i in range(queue_obj.qsize()))

    def msg_deal(self, traceid: str, query: str, uid: str, username: str) -> bool:
        text = ["唱一下", "唱一首", "唱歌", "点歌", "点播"]
        is_contain = StringUtil.has_string_reg_list(f"^{text}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(text, query)
            q = query[num:].strip()
            if q:
                self._data.SongQueueList.put({"traceid": traceid, "prompt": q, "username": username})
            return True
        return False
