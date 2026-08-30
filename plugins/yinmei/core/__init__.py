"""
吟美数据实体 - 队列驱动的直播数据模型
适配 MIYA 架构，去除了对原 func.gobal 的依赖
"""

import queue
import threading
import os

from plugins.yinmei.config import YinmeiConfig
from plugins.yinmei.tools import singleton, FileUtil

config = YinmeiConfig.get_instance()


@singleton
class SharedData:
    """所有模块共享的数据容器 (密钥/开关/队列/锁)"""

    def __init__(self):
        c = config
        self.Ai_Name: str = c.get("ai_name", "弥娅")
        self.mode: list = c.get("mode", ["api"])
        self.port: int = c.get("port", 1800)

        # ---- 主开关 ----
        self.yinmei_enabled = True

        # ---- LLM 聊天 ----
        self.QuestionList = queue.Queue()
        self.QuestionName = queue.Queue()
        self.AnswerList = queue.Queue()
        self.history = []
        self.is_ai_ready = True
        self.is_stream_out = False
        self.cmd = c.get("cmd", [""])
        self.relations = c.get("relations", {})
        self.split_flag = c.get("split_flag", ",|，|。|!|！|?|？|\n")
        self.split_str = self.split_flag.split("|")
        self.split_limit = c.get("split_limit", 4)
        self.public_sentiment_key = c.get("public_sentiment_key", "")

        # ---- 欢迎 ----
        self.WelcomeList = []
        self.is_llm_welcome = c.get("is_llm_welcome", False)
        self.welcome_not_allow = c.get("welcome_not_allow", [])

        # ---- TTS ----
        self.SayCount = 0
        self.say_lock = threading.Lock()
        self.ReplyTextList = queue.Queue()
        self.is_tts_ready = True
        self.select_tts = c.get("tts_engine", "edge-tts")
        self.tts_speaker = c.get("tts_speaker", "zh-CN-XiaoxiaoNeural")
        self.speech_max_threads = c.get("speech_max_threads", 5)

        # ---- OBS ----
        self.obs_switch = c.get("obs_switch", False)
        self.obs_host = c.get("obs_host", "127.0.0.1")
        self.obs_port = c.get("obs_port", 4455)
        self.obs_password = c.get("obs_password", "")
        self.song_background = c.get("song_background", {})

        # ---- 场景 / 换装 ----
        self.now_clothes = "便衣"
        self.swing_motion = 2
        self.auto_swing_lock = threading.Lock()
        self.mood_num = 0

        # ---- 唱歌 ----
        self.sing_url = c.get("sing_url", "")
        self.SongQueueList = queue.Queue()
        self.SongMenuList = queue.Queue()
        self.SongNowName = {}
        self.is_singing = 2
        self.is_creating_song = 2
        self.sing_play_flag = 0
        self.song_not_convert = c.get("song_not_convert", "")
        self.create_song_timout = c.get("create_song_timout", 500)
        self.create_song_lock = threading.Lock()
        self.play_song_lock = threading.Lock()

        # ---- 绘画 ----
        self.draw_url = c.get("draw_url", "")
        self.draw_width = c.get("draw_width", 980)
        self.draw_height = c.get("draw_height", 500)
        self.draw_physical_folder = c.get("draw_physical_save_folder", "./output/")
        self.draw_proxies = c.get("draw_proxies", {})
        self.DrawQueueList = queue.Queue()
        self.is_drawing = 3

        # ---- 鉴黄 ----
        self.nsfw_server = c.get("nsfw_server", "")
        self.nsfw_filter_en = c.get("nsfw_filter_en", "")
        self.nsfw_filter_ch = c.get("nsfw_filter_ch", "")
        self.nsfw_progress_limit = c.get("nsfw_progress_limit", 1)
        self.nsfw_limit = c.get("nsfw_limit", 0.2)
        self.nsfw_progress_nsfw_limit = c.get("nsfw_progress_nsfw_limit", 0.2)
        self.nsfw_lock = threading.Lock()

        # ---- 搜图 ----
        self.image_num = c.get("search_img_num", 10)
        self.image_width = c.get("search_img_width", 980)
        self.image_height = c.get("search_img_height", 500)
        self.image_physical_folder = c.get("search_img_physical_save_folder", "./output/")
        self.image_proxies = c.get("search_img_proxies", {})
        self.SearchImgList = queue.Queue()
        self.is_SearchImg = 2

        # ---- 搜文 ----
        self.search_num = c.get("search_num", 5)
        self.search_proxies = c.get("search_proxies", {})
        self.SearchTextList = queue.Queue()
        self.is_SearchText = 2

        # ---- 跳舞 / 表情 ----
        dance_path = c.get("obs_dance_path", "")
        emote_path = c.get("obs_emote_path", "")
        emote_font = c.get("obs_emote_font", "")
        self.DanceQueueList = queue.Queue()
        self.is_dance = 2
        if dance_path and os.path.exists(dance_path):
            self.dance_video = FileUtil.get_child_file_paths(dance_path)
        else:
            self.dance_video = []
        self.emote_video_lock = threading.Lock()
        self.emote_now_path = ""
        self.dance_now_path = ""
        if emote_path and os.path.exists(emote_path):
            self.emote_video = FileUtil.get_child_file_paths(emote_path)
        else:
            self.emote_video = []
        if emote_font and os.path.exists(emote_font):
            self.emote_list = FileUtil.get_subfolder_names(emote_font)
        else:
            self.emote_list = []
        self.singdance_now_path = ""

        # ---- B站弹幕 ----
        self.bili_room_id = c.get("bilibili_room_id", 0)
        self.bili_sessdata = c.get("bilibili_sessdata", "")
        self.bili_access_key_id = c.get("bilibili_access_key_id", "")
        self.bili_access_key_secret = c.get("bilibili_access_key_secret", "")
        self.bili_app_id = c.get("bilibili_app_id", 0)
        self.bili_auth_code = c.get("bilibili_auth_code", "")

        # ---- VTube Studio (可选) ----
        self.vtuber_switch = c.get("vtuber_switch", False)
        self.vtuber_websocket = c.get("vtuber_websocket", "127.0.0.1:8001")
        self.vtuber_plugin_name = c.get("vtuber_plugin_name", "winlonebot")
        self.vtuber_plugin_developer = c.get("vtuber_plugin_developer", "winlone")
        self.vtuber_auth_token = c.get("vtuber_auth_token", "")

        # ---- 场景昼夜背景 ----
        self.scene_backgrounds = c.get("scene_backgrounds", {})

    def get_scene_bg(self, scene: str, time_of_day: str) -> str:
        return self.scene_backgrounds.get(scene, {}).get(time_of_day, "")
