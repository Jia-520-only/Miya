"""
音频播放器 - 使用 simpleaudio 实现
支持异步播放、音量控制、播放状态管理
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional
import wave
import array

try:
    import simpleaudio as sa
    SIMPLEAUDIO_AVAILABLE = True
except ImportError:
    SIMPLEAUDIO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("simpleaudio 未安装，本地播放功能不可用")


logger = logging.getLogger(__name__)


class AudioPlayer:
    """音频播放器类"""

    def __init__(self):
        """初始化音频播放器"""
        self._playing = False
        self._volume = 1.0
        self._current_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._play_obj = None

    def set_volume(self, volume: float):
        """
        设置播放音量

        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        self._volume = max(0.0, min(1.0, volume))
        logger.debug(f"[AudioPlayer] 音量设置为: {self._volume}")

    def get_volume(self) -> float:
        """获取当前音量"""
        return self._volume

    def is_playing(self) -> bool:
        """检查是否正在播放"""
        return self._playing

    async def play(self, audio_path: str, volume: Optional[float] = None):
        """
        播放音频文件（异步）

        Args:
            audio_path: 音频文件路径
            volume: 播放音量（可选，默认使用当前设置的音量）
        """
        if not SIMPLEAUDIO_AVAILABLE:
            logger.warning("[AudioPlayer] simpleaudio 未安装，无法播放")
            return

        if self._playing:
            logger.warning("[AudioPlayer] 已有音频在播放，停止当前播放")
            self.stop()

        play_volume = volume if volume is not None else self._volume

        if not Path(audio_path).exists():
            logger.error(f"[AudioPlayer] 音频文件不存在: {audio_path}")
            return

        self._playing = True
        self._stop_event.clear()

        # 在后台任务中播放
        self._current_task = asyncio.create_task(
            self._play_in_background(audio_path, play_volume)
        )

        try:
            await self._current_task
        except asyncio.CancelledError:
            logger.debug("[AudioPlayer] 播放任务被取消")
        finally:
            self._playing = False

    async def _play_in_background(self, audio_path: str, volume: float):
        """
        在后台线程中播放音频

        Args:
            audio_path: 音频文件路径
            volume: 播放音量
        """
        loop = asyncio.get_event_loop()

        def play_audio_thread():
            """在线程池中播放音频"""
            try:
                logger.debug(f"[AudioPlayer] 开始播放: {audio_path}, 音量: {volume}")

                # 读取 WAV 文件
                with wave.open(audio_path, 'rb') as wav_file:
                    # 获取音频参数
                    n_channels = wav_file.getnchannels()
                    sampwidth = wav_file.getsampwidth()
                    framerate = wav_file.getframerate()
                    n_frames = wav_file.getnframes()

                    # 读取音频数据
                    audio_data = wav_file.readframes(n_frames)

                    # 应用音量
                    if volume != 1.0 and sampwidth == 2:
                        # 16-bit 音频
                        samples = array.array('h', audio_data)
                        for i in range(len(samples)):
                            samples[i] = int(samples[i] * volume)
                        audio_data = samples.tobytes()

                # 播放音频
                play_obj = sa.play_buffer(
                    audio_data,
                    n_channels,
                    sampwidth,
                    framerate
                )

                # 保存播放对象以便停止
                self._play_obj = play_obj

                # 等待播放完成
                play_obj.wait_done()

                logger.debug(f"[AudioPlayer] 播放完成: {audio_path}")

            except Exception as e:
                logger.error(f"[AudioPlayer] 播放失败: {e}", exc_info=True)

        # 在线程池中执行播放
        await loop.run_in_executor(None, play_audio_thread)

    def stop(self):
        """停止当前播放"""
        if self._play_obj:
            self._play_obj.stop()
            self._play_obj = None
            logger.debug("[AudioPlayer] 停止播放")

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            logger.debug("[AudioPlayer] 停止播放任务")

        self._stop_event.set()

    async def wait_until_finished(self):
        """等待播放完成"""
        if self._current_task:
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

    def cleanup(self):
        """清理资源"""
        self.stop()
        logger.info("[AudioPlayer] 音频播放器已清理")


# 单例实例
_audio_player_instance: Optional[AudioPlayer] = None


def get_audio_player() -> AudioPlayer:
    """
    获取音频播放器单例

    Returns:
        AudioPlayer: 音频播放器实例
    """
    global _audio_player_instance
    if _audio_player_instance is None:
        _audio_player_instance = AudioPlayer()
    return _audio_player_instance
