"""
表情引擎 - 文本关键词 → Live2D 表情/动作映射 + 情感追踪

通过 routes.py 的 _live2d_cmd_queue 实现跨进程 Live2D 控制，
将 YinMei 的 emote 概念桥接到 MIYA 的 Live2D 引擎。
"""

import logging
import random
import time
from threading import Thread

from plugins.yinmei.tools import singleton, StringUtil
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)


@singleton
class EmoteEngine:
    """文本→表情映射引擎，通过 Live2D 队列驱动弥娅表情"""

    def __init__(self):
        self._data = SharedData()

    @staticmethod
    def _live2d_emotion(emotion: str):
        """通过 routes.py 的命令队列发送情绪到 Live2D"""
        try:
            from plugins.yinmei.routes import live2d_set_emotion

            live2d_set_emotion(emotion)
        except Exception as e:
            logger.debug(f"Live2D 情绪发送异常: {e}")

    @staticmethod
    def _live2d_action(action: str):
        try:
            from plugins.yinmei.routes import live2d_trigger_action

            live2d_trigger_action(action)
        except Exception as e:
            logger.debug(f"Live2D 动作发送异常: {e}")

    @staticmethod
    def _live2d_state(state: str):
        try:
            from plugins.yinmei.routes import live2d_set_state

            live2d_set_state(state)
        except Exception as e:
            logger.debug(f"Live2D 状态发送异常: {e}")

    # ============ 文本 → 表情匹配 ============

    def analyze(self, text: str) -> list:
        """
        分析文本内容，返回表情动作序列。
        每个元素: {"category": str, "emotion": str, "action": str, "num": int, "timesleep": float, "donum": int}
        """
        result = []

        # ── 开心 ──
        keywords = ["笑", "不错", "哈", "开心", "呵", "嘻", "画", "搜", "有趣"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "positive",
                    "emotion": "happy",
                    "action": "happy",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 伤心 ──
        keywords = ["哭", "悲伤", "伤心", "凄惨", "好惨", "呜呜", "悲哀"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 招呼 ──
        keywords = ["你好", "在吗", "干嘛", "名字", "欢迎", "我在", "玩笑", "逗"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "positive",
                    "emotion": "happy",
                    "action": "happy" if random.random() > 0.5 else "enjoy",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 生气 ──
        keywords = ["生气", "不理你", "骂", "臭", "打死", "可恶", "白痴", "气死"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 尴尬 ──
        keywords = ["尴尬", "无聊", "无奈", "傻子", "郁闷", "龟蛋", "傻逼", "逗比", "忘记", "怎么可能", "调侃"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 认同 ──
        keywords = ["认同", "点头", "嗯", "哦", "女仆"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "normal",
                    "emotion": "normal",
                    "action": "nod",
                    "num": num,
                    "timesleep": 0.2,
                    "donum": 3,
                }
            )

        # ── 汗颜 ──
        keywords = ["汗颜", "流汗", "郁闷", "笑死", "白痴", "渣渣", "搞笑", "恶心"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 晕 ──
        keywords = ["晕", "头晕", "晕死", "呕"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 可爱 ──
        keywords = ["可爱", "害羞", "爱你", "天真", "搞笑", "喜欢", "全知全能"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "positive",
                    "emotion": "happy",
                    "action": "happy",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 摸摸头 ──
        keywords = ["摸摸头", "摸摸脑袋", "乖", "做得好"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "positive",
                    "emotion": "happy",
                    "action": "happy",
                    "num": num,
                    "timesleep": 5,
                    "donum": 1,
                }
            )
            result.append(
                {
                    "category": "negative",
                    "emotion": "sad",
                    "action": "sad",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 惊讶 ──
        keywords = ["惊讶", "吃惊", "吓", "天啊", "不是吧", "居然"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "surprise",
                    "emotion": "surprise",
                    "action": "surprise",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        # ── 温柔 ──
        keywords = ["温柔", "抚摸", "抚媚", "骚", "唱歌"]
        num = StringUtil.is_index_nocontain_string(keywords, text)
        if num > 0:
            result.append(
                {
                    "category": "positive",
                    "emotion": "happy",
                    "action": "enjoy",
                    "num": num,
                    "timesleep": 0,
                    "donum": 0,
                }
            )

        return result

    # ============ 表情执行 ============

    def execute(self, emote_list: list):
        """执行表情序列"""
        for item in emote_list:
            num = item["num"]
            if num <= 0:
                continue

            timesleep = item.get("timesleep", 0)
            donum = item.get("donum", 0)
            emotion = item.get("emotion", "")
            action = item.get("action", "")

            # 延时执行（根据文本位置偏移）
            if num > 0:
                time.sleep(round(num * 0.4, 2))

            # 发送情绪
            if emotion:
                self._live2d_emotion(emotion)
                logger.debug(f"Live2D 情绪: {emotion}")

            # 发送动作
            if action:
                self._live2d_action(action)
                logger.debug(f"Live2D 动作: {action}")

            # 循环表情
            while donum > 0:
                time.sleep(timesleep)
                if action:
                    self._live2d_action(action)
                donum -= 1

    def execute_async(self, text: str):
        """异步分析并执行表情（在线程中运行）"""
        emote_list = self.analyze(text)
        if emote_list:
            logger.debug(f"表情序列: {emote_list}")
            Thread(target=self.execute, args=(emote_list,), daemon=True).start()

    # ============ 情感追踪 ============

    def track_mood(self, emotion: str):
        """追踪感情值累积"""
        if emotion in ("sad", "negative"):
            self._data.mood_num += 1
        elif emotion in ("happy", "positive"):
            self._data.mood_num += 2
        elif emotion in ("angry",):
            self._data.mood_num += 3

        if self._data.mood_num > 300:
            self._data.mood_num = 0

        return self._data.mood_num
