"""
音频播放器 - 使用 simpleaudio 实现
支持异步播放、音量控制、播放状态管理
"""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Optional

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
        self._proc = None

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
        self._current_task = asyncio.create_task(self._play_in_background(audio_path, play_volume))

        try:
            await self._current_task
        except asyncio.CancelledError:
            logger.debug("[AudioPlayer] 播放任务被取消")
        finally:
            self._playing = False

    async def _play_in_background(self, audio_path: str, volume: float):
        """在独立子进程中播放音频（隔离 simpleaudio 崩溃）"""
        loop = asyncio.get_event_loop()

        def _start_proc():
            return start_audio_subprocess(audio_path, volume)

        self._proc = await loop.run_in_executor(None, _start_proc)
        if self._proc is None:
            return

        while self._proc.is_alive():
            if self._stop_event.is_set():
                break
            await asyncio.sleep(0.2)

    def stop(self):
        """停止当前播放"""
        if self._proc is not None:
            with contextlib.suppress(Exception):
                if self._proc.is_alive():
                    self._proc.terminate()
            self._proc = None
            logger.debug("[AudioPlayer] 停止播放")

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            logger.debug("[AudioPlayer] 停止播放任务")

        self._stop_event.set()

    async def wait_until_finished(self):
        """等待播放完成"""
        if self._current_task:
            with contextlib.suppress(asyncio.CancelledError):
                await self._current_task

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


def _subprocess_play_worker(audio_path: str, volume: float = 1.0):
    """子进程播放入口：winsound 优先（WAV），回退 simpleaudio（含音量缩放）。"""
    try:
        import os
        import winsound

        if os.path.splitext(audio_path)[1].lower() == ".wav":
            winsound.PlaySound(audio_path, winsound.SND_FILENAME)
            return
    except Exception:
        pass

    try:
        import array
        import wave

        import simpleaudio as sa

        with wave.open(audio_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            audio_data = wf.readframes(n_frames)

        if volume != 1.0:
            if sampwidth == 2:
                samples = array.array("h", audio_data)
                for i in range(len(samples)):
                    samples[i] = int(samples[i] * volume)
                audio_data = samples.tobytes()
            elif sampwidth == 1:
                samples = array.array("B", audio_data)
                for i in range(len(samples)):
                    samples[i] = max(0, min(255, int((samples[i] - 128) * volume + 128)))
                audio_data = samples.tobytes()
            elif sampwidth == 3:
                count = len(audio_data) // 3
                result = bytearray(len(audio_data))
                for i in range(count):
                    raw = int.from_bytes(audio_data[i * 3 : i * 3 + 3], "little", signed=True)
                    val = max(-8388608, min(8388607, int(raw * volume)))
                    result[i * 3 : i * 3 + 3] = val.to_bytes(3, "little", signed=True)
                audio_data = bytes(result)
            elif sampwidth == 4:
                samples = array.array("i", audio_data)
                for i in range(len(samples)):
                    samples[i] = int(samples[i] * volume)
                audio_data = samples.tobytes()

        play_obj = sa.play_buffer(audio_data, n_channels, sampwidth, framerate)
        play_obj.wait_done()
    except Exception:
        pass


def start_audio_subprocess(audio_path: str, volume: float = 1.0):
    """启动音频播放子进程，返回 Process（供 stop/wait 控制）。

    simpleaudio 在 Windows 上播放某些 WAV（如 GPT-SoVITS 合成）时可能触发
    access violation 拖垮整个守护进程，因此播放必须隔离到子进程。
    """
    import multiprocessing

    path = str(audio_path)
    if not path or not Path(path).exists():
        return None
    try:
        proc = multiprocessing.Process(target=_subprocess_play_worker, args=(path, volume), daemon=True)
        proc.start()
        return proc
    except Exception:
        return None


def play_audio_isolated(audio_path: str, volume: float = 1.0) -> bool:
    """fire-and-forget 子进程播放（用于 TTS 本地播放等无需控制的生命周期）。"""
    return start_audio_subprocess(audio_path, volume) is not None
