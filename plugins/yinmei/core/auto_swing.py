"""
自动摇摆引擎 - 说话/唱歌时身体自然动画

驱动 MIYA Live2D 的状态通道 (idle → talking / thinking)，
配合动作通道触发随机身体动画，让弥娅看起来"有生气"。
"""

import logging
import random
import time
from threading import Thread

from plugins.yinmei.tools import singleton
from plugins.yinmei.core import SharedData

logger = logging.getLogger(__name__)


@singleton
class AutoSwingEngine:
    """自动身体动画引擎"""

    # 摇摆动作列表（对应 MIYA Live2D naga-actions.json 中的动作名）
    SWING_ACTIONS = ["nod", "shake"]
    SWING_INTERVAL = (4, 10)  # 摇摆间隔范围 (秒)

    def __init__(self):
        self._data = SharedData()
        self._swing_thread: Thread | None = None

    @staticmethod
    def _live2d_state(state: str):
        try:
            from plugins.yinmei.routes import live2d_set_state

            live2d_set_state(state)
        except Exception as e:
            logger.debug(f"Live2D 状态发送异常: {e}")

    @staticmethod
    def _live2d_action(action: str):
        try:
            from plugins.yinmei.routes import live2d_trigger_action

            live2d_trigger_action(action)
        except Exception as e:
            logger.debug(f"Live2D 动作发送异常: {e}")

    def start(self):
        """开始自动摇摆循环"""
        self._data.auto_swing_lock.acquire()
        try:
            # 只在未摇摆 + (唱歌中 或 说话中) 时启动
            if self._data.swing_motion == 2 and (self._data.is_singing == 1 or not self._data.is_tts_ready):
                logger.debug("进入自动摇摆状态")
                self._data.swing_motion = 1
            else:
                return
        finally:
            self._data.auto_swing_lock.release()

        self._swing_thread = Thread(target=self._swing_loop, daemon=True)
        self._swing_thread.start()

    def stop(self):
        """停止自动摇摆"""
        self._data.swing_motion = 2
        self._live2d_state("idle")

    def _swing_loop(self):
        """摇摆循环：在说话/唱歌期间，每隔几秒随机触发一个身体动作"""
        logger.debug("自动摇摆循环启动")
        try:
            while self._swing_should_continue():
                action = random.choice(self.SWING_ACTIONS)
                logger.debug(f"摇摆动作: {action}")
                self._live2d_state("talking")
                self._live2d_action(action)

                # 随机间隔
                interval = random.uniform(*self.SWING_INTERVAL)
                elapsed = 0
                while elapsed < interval and self._swing_should_continue():
                    time.sleep(0.5)
                    elapsed += 0.5
        finally:
            self._data.swing_motion = 2
            self._live2d_state("idle")
            logger.debug("自动摇摆循环结束")

    def _swing_should_continue(self) -> bool:
        """检查是否应该保持摇摆"""
        return self._data.swing_motion == 1 and (self._data.is_singing == 1 or not self._data.is_tts_ready)
