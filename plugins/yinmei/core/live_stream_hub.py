"""
直播中枢 - 整合所有虚拟主播管线

消息入口 → 命令解析 → 意图分发 → 功能执行
调度系统：定时器轮询各路队列
"""

import logging
import os
import uuid
from threading import Thread

from plugins.yinmei.core import SharedData
from plugins.yinmei.core.obs_controller import OBSController
from plugins.yinmei.core.nsfw_filter import NSFWFilter
from plugins.yinmei.core.image_search import ImageSearch
from plugins.yinmei.core.web_search import WebSearch
from plugins.yinmei.core.draw_engine import DrawEngine
from plugins.yinmei.core.sing_engine import SingEngine
from plugins.yinmei.core.dance_engine import DanceEngine
from plugins.yinmei.core.emote_engine import EmoteEngine
from plugins.yinmei.core.auto_swing import AutoSwingEngine
from plugins.yinmei.core.scene_manager import SceneClothesManager
from plugins.yinmei.core.bilibili_danmaku import BilibiliDanmaku
from plugins.yinmei.tools import singleton, StringUtil

logger = logging.getLogger(__name__)


@singleton
class LiveStreamHub:
    """直播中枢 - 虚拟主播主控制器"""

    def __init__(self):
        self._data = SharedData()
        self._obs = OBSController()
        self._nsfw = NSFWFilter()
        self._image_search = ImageSearch()
        self._web_search = WebSearch()
        self._draw = DrawEngine()
        self._sing = SingEngine()
        self._dance = DanceEngine()
        self._emote = EmoteEngine()
        self._swing = AutoSwingEngine()
        self._scene = SceneClothesManager()
        self._bilibili = BilibiliDanmaku()

        self._tts_callback = None
        self._llm_chat_callback = None
        self._emote_callback = None
        self._scheduler = None

        self._talking = False

    # ============ 回调注册 (对接 MIYA 现有系统) ============

    def set_tts_callback(self, callback):
        """注册 TTS 回调: callback(text: str)"""
        self._tts_callback = callback

    def set_llm_chat_callback(self, callback):
        """注册 LLM 对话回调: callback(question_list_item: dict)"""
        self._llm_chat_callback = callback

    def set_emote_callback(self, callback):
        """注册表情回调: callback(text: str) -> list[dict]"""
        self._emote_callback = callback

    def set_live2d_state(self, state: str):
        """通过 API 向 Live2D 窗口发送状态"""
        try:
            from plugins.yinmei.routes import live2d_set_state

            live2d_set_state(state)
        except Exception:
            pass

    def set_live2d_emotion(self, emotion: str):
        """通过 API 向 Live2D 窗口发送情绪"""
        try:
            from plugins.yinmei.routes import live2d_set_emotion

            live2d_set_emotion(emotion)
        except Exception:
            pass

    def set_live2d_mouth(self, params: dict):
        """通过 API 向 Live2D 窗口发送口型参数"""
        try:
            from plugins.yinmei.routes import live2d_set_mouth

            live2d_set_mouth(params)
        except Exception:
            pass

    # ============ 消息入口 ============

    def process_message(self, traceid: str, query: str, uid: str, username: str):
        """处理来自任意平台的输入消息"""

        # 主开关命令 — 无论开关状态都允许
        if query == "/主播 on" or query == "/主播 off":
            self._handle_power_toggle(traceid, query, uid, username)
            return

        if not self._data.yinmei_enabled:
            # 关闭模式下：只保留表情分析 + 聊天，跳过主播功能
            self._emote.execute_async(query)
            self._handle_chat(traceid, query, uid, username)
            return

        query = self._nsfw.filter_text(query)
        logger.info(f"[{traceid}]消息捕获 [{username}]: {query}")

        # 1. 命令处理
        if self._handle_command(traceid, query, uid, username):
            return

        # 2. 跳过 "\" 开头的消息
        if query.startswith("\\"):
            return

        # 3. 表情/跳舞
        if self._dance.msg_deal_emote(traceid, query, uid, username):
            return

        # 4. 搜索
        if self._web_search.msg_deal(traceid, query, uid, username):
            return

        # 5. 搜图
        if self._image_search.msg_deal(traceid, query, uid, username):
            return

        # 6. 绘画
        if self._draw.msg_deal(traceid, query, uid, username):
            return

        # 7. 唱歌
        if self._sing.msg_deal(traceid, query, uid, username):
            return

        # 8. 跳舞
        if self._dance.msg_deal_dance(traceid, query, uid, username):
            return

        # 9. 换装
        if self._scene.msg_deal_clothes(traceid, query, uid, username):
            return

        # 10. 场景切换
        if self._scene.msg_deal_scene(traceid, query, uid, username):
            return

        # 11. 聊天入口
        self._handle_chat(traceid, query, uid, username)

    # ============ 命令处理 ============

    def _handle_power_toggle(self, traceid: str, query: str, uid: str, username: str):
        if query == "/主播 on":
            self.enable()
            logger.info(f"[{traceid}] 虚拟主播已开启")
        elif query == "/主播 off":
            self.disable()
            logger.info(f"[{traceid}] 虚拟主播已关闭")

    def enable(self):
        self._data.yinmei_enabled = True
        self._bilibili.start()

    def disable(self):
        self._data.yinmei_enabled = False
        self._bilibili.stop()

    def _handle_command(self, traceid: str, query: str, uid: str, username: str) -> bool:
        if query == "\\stop":
            self._data.is_singing = 2
            self._data.is_SearchText = 2
            self._data.is_SearchImg = 2
            self._data.is_drawing = 3
            self._data.is_ai_ready = True
            self._data.is_tts_ready = True
            os.system("taskkill /T /F /IM song.exe 2>nul")
            os.system("taskkill /T /F /IM accompany.exe 2>nul")
            os.system("taskkill /T /F /IM mpv.exe 2>nul")
            return True

        if query == "\\dance":
            os.system("taskkill /T /F /IM song.exe 2>nul")
            os.system("taskkill /T /F /IM accompany.exe 2>nul")
            os.system("taskkill /T /F /IM mpv.exe 2>nul")
            return True

        next_text = ["\\next", "下一首", "下首", "切歌", "next"]
        if StringUtil.has_string_reg_list(f"^{next_text}", query):
            os.system("taskkill /T /F /IM song.exe 2>nul")
            os.system("taskkill /T /F /IM accompany.exe 2>nul")
            self._data.is_singing = 2
            return True

        if "停止学歌" in query:
            self._data.is_creating_song = 2
            return True

        stop_dance_text = ["\\停止跳舞", "停止跳舞", "不要跳舞", "stop dance"]
        if StringUtil.has_string_reg_list(f"^{stop_dance_text}", query):
            self._data.is_dance = 2
            return True

        return False

    # ============ 聊天入口 ============

    def _handle_chat(self, traceid: str, query: str, uid: str, username: str):
        cmd = self._data.cmd
        is_contain = StringUtil.has_string_reg_list(f"^{cmd}", query)
        if is_contain is not None:
            num = StringUtil.is_index_contain_string(cmd, query)
            extracted = query[num:].strip()
            if not extracted:
                return
            logger.info(f"[{traceid}]用户对话: {extracted}")
            self._data.QuestionList.put(
                {
                    "traceid": traceid,
                    "prompt": query,
                    "uid": uid,
                    "username": username,
                }
            )

    # ============ 定时器轮询 (FastAPI/APScheduler 驱动) ============

    def check_answer(self):
        """LLM 回复调度"""
        if not self._data.QuestionList.empty() and self._data.is_ai_ready:
            self._data.is_ai_ready = False
            if self._llm_chat_callback:
                Thread(target=self._llm_chat_callback, daemon=True).start()
            else:
                self._data.is_ai_ready = True

    def check_tts(self):
        """TTS 语音合成调度"""
        if not self._data.AnswerList.empty() and self._data.is_tts_ready:
            item = self._data.AnswerList.get()
            text = item.get("text", "")
            if text and self._tts_callback:
                Thread(target=self._tts_callback, args=(text,), daemon=True).start()

    def check_sing(self):
        """唱歌调度"""
        self._sing.check_sing()

    def check_playlist(self):
        """歌单播放调度"""
        self._sing.check_playlist()

    def check_draw(self):
        """绘画调度"""
        self._draw.check_draw()

    def check_img_search(self):
        """搜图调度"""
        self._image_search.check_img_search()

    def check_text_search(self):
        """搜文调度"""
        self._web_search.check_text_search()

    def check_dance(self):
        """跳舞调度"""
        self._dance.check_dance()

    def check_welcome(self):
        """欢迎语调度"""
        if self._data.WelcomeList:
            names = str(self._data.WelcomeList).replace("['", "").replace("']", "")
            count = len(self._data.WelcomeList)
            suffix = f"{count}位" if count > 1 else ""
            text = f'欢迎"{names}"{suffix}同学来到{self._data.Ai_Name}的直播间,跪求关注一下'
            self._data.WelcomeList.clear()
            if self._data.is_llm_welcome:
                self._data.QuestionList.put(
                    {
                        "traceid": str(uuid.uuid4()),
                        "prompt": text,
                        "uid": "0",
                        "username": self._data.Ai_Name,
                    }
                )
            elif self._tts_callback:
                Thread(target=self._tts_callback, args=(text,), daemon=True).start()

    # ============ 启动/停止 ============

    def change_scene(self, scene_name: str):
        return self._scene.change_scene(scene_name)

    def start_bilibili(self):
        self._bilibili.set_callback(self.process_message)
        self._bilibili.start()

    def init_scene(self):
        self._scene.init_scene()

    def on_tts_start(self):
        """TTS 开始说话时触发——启动自动摇摆"""
        self._talking = True
        Thread(target=self._swing.start, daemon=True).start()

    def on_tts_end(self):
        """TTS 说完话时触发——停止自动摇摆"""
        self._talking = False
        self._swing.stop()

    def on_chat_reply(self, reply_text: str):
        """聊天回复时触发——表情分析"""
        self._emote.execute_async(reply_text)

    def register_scheduler(self, scheduler):
        """注册 APScheduler 实例，注册全部定时任务"""
        self._scheduler = scheduler
        scheduler.add_job(
            func=self.check_answer,
            trigger="interval",
            seconds=1,
            id="yinmei_answer",
            max_instances=100,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_tts,
            trigger="interval",
            seconds=1,
            id="yinmei_tts",
            max_instances=1000,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_sing,
            trigger="interval",
            seconds=1,
            id="yinmei_sing",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_playlist,
            trigger="interval",
            seconds=1,
            id="yinmei_playlist",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_draw,
            trigger="interval",
            seconds=1,
            id="yinmei_draw",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_img_search,
            trigger="interval",
            seconds=1,
            id="yinmei_img",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_text_search,
            trigger="interval",
            seconds=1,
            id="yinmei_text",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_dance,
            trigger="interval",
            seconds=1,
            id="yinmei_dance",
            kwargs={"sched": scheduler},
            max_instances=10,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self.check_welcome,
            trigger="interval",
            seconds=20,
            id="yinmei_welcome",
            max_instances=50,
            replace_existing=True,
        )
        scheduler.add_job(
            func=self._check_scene_time, trigger="cron", hour="6,17,18", id="yinmei_scene_time", replace_existing=True
        )
        logger.info("吟美直播定时任务注册完成")

    def _check_scene_time(self):
        self._scene.check_scene_time()

    def shutdown(self):
        """停止所有"""
        self._data.is_singing = 2
        self._data.is_creating_song = 2
        self._data.is_drawing = 3
        self._data.is_dance = 2
        self._swing.stop()
        self._bilibili.stop()
        self._obs.disconnect()
        logger.info("吟美直播中枢已停止")
