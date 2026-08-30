"""
系统TTS引擎实现
使用操作系统内置的TTS能力
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import tempfile
import os
import platform
import subprocess

from .tts_engine import TTSEngine


logger = logging.getLogger(__name__)


class SystemTTSEngine(TTSEngine):
    """系统TTS引擎,使用操作系统内置TTS"""

    def __init__(self):
        super().__init__("system_tts")
        self.voice_id = None
        self.speed = 1.0
        self.volume = 0.8
        self.os_type = platform.system()

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化系统TTS引擎

        Args:
            config: 配置字典,包含:
                - voice_id: 音色ID
                - speed: 语速(默认1.0)
                - volume: 音量(默认0.8)

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.voice_id = config.get("voice_id")
            self.speed = config.get("speed", 1.0)
            self.volume = config.get("volume", 0.8)

            # 检查系统TTS是否可用
            if self.os_type == "Windows":
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    logger.info("Windows SAPI TTS available")
                except ImportError:
                    logger.warning("pywin32 not installed, Windows TTS unavailable")
                    return False
            elif self.os_type == "Darwin":  # macOS
                logger.info("macOS say command available")
            elif self.os_type == "Linux":
                logger.info("Linux espeak/festival available (need manual check)")
            else:
                logger.warning(f"Unsupported OS: {self.os_type}")
                return False

            self.is_initialized = True
            logger.info(f"System TTS engine initialized successfully on {self.os_type}")
            return True

        except Exception as e:
            logger.error(f"System TTS initialization failed: {e}")
            return False

    async def synthesize(self, text: str, output_format: str = "mp3", **kwargs) -> Optional[bytes]:
        """
        合成语音

        Args:
            text: 要合成的文本
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            bytes: 语音数据
        """
        try:
            # 创建临时文件保存输出
            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            result_path = await self.synthesize_to_file(text, output_path, output_format, **kwargs)

            if result_path and os.path.exists(result_path):
                with open(result_path, "rb") as f:
                    audio_data = f.read()

                # 清理临时文件
                try:
                    os.unlink(result_path)
                except:
                    pass

                return audio_data

            return None

        except Exception as e:
            logger.error(f"System TTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(self, text: str, output_path: str,
                                output_format: str = "mp3", **kwargs) -> Optional[str]:
        """
        合成语音并保存到文件

        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            str: 输出文件路径
        """
        try:
            speed = kwargs.get("speed", self.speed)
            voice_id = kwargs.get("voice_id", self.voice_id)

            if self.os_type == "Windows":
                return await self._synthesize_windows(text, output_path, voice_id, speed)
            elif self.os_type == "Darwin":
                return await self._synthesize_macos(text, output_path, voice_id, speed, output_format)
            elif self.os_type == "Linux":
                return await self._synthesize_linux(text, output_path, voice_id, speed, output_format)
            else:
                logger.error(f"Unsupported OS: {self.os_type}")
                return None

        except Exception as e:
            logger.error(f"System TTS synthesis to file failed: {e}")
            return None

    async def _synthesize_windows(self, text: str, output_path: str,
                                  voice_id: Optional[str], speed: float) -> Optional[str]:
        """Windows系统使用SAPI"""
        try:
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")

            # 设置语速
            speaker.Rate = int((speed - 1.0) * 10)

            # 设置音色
            if voice_id:
                voices = speaker.GetVoices()
                for i in range(voices.Count):
                    if voice_id.lower() in voices.Item(i).GetDescription().lower():
                        speaker.Voice = voices.Item(i)
                        break

            # 保存到文件
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Format.Type = 39  # Standard WAV format
            stream.Open(output_path, 3)  # SSFMCreateForWrite

            speaker.AudioOutputStream = stream
            speaker.Speak(text)
            stream.Close()

            return output_path

        except Exception as e:
            logger.error(f"Windows TTS synthesis failed: {e}")
            return None

    async def _synthesize_macos(self, text: str, output_path: str,
                              voice_id: Optional[str], speed: float,
                              output_format: str) -> Optional[str]:
        """macOS使用say命令"""
        try:
            cmd = ["say", "-o", output_path]

            if voice_id:
                cmd.extend(["-v", voice_id])

            # say语速通过--rate参数
            rate = int(speed * 200)  # 默认200
            cmd.extend(["--rate", str(rate)])

            cmd.append(text)

            # 使用run_in_executor避免阻塞
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=True))

            return output_path

        except Exception as e:
            logger.error(f"macOS TTS synthesis failed: {e}")
            return None

    async def _synthesize_linux(self, text: str, output_path: str,
                              voice_id: Optional[str], speed: float,
                              output_format: str) -> Optional[str]:
        """Linux使用espeak或festival"""
        try:
            # 优先尝试espeak
            if self._check_command("espeak"):
                cmd = ["espeak", "-f", output_path]

                if voice_id:
                    cmd.extend(["-v", voice_id])

                # 语速
                speed_value = int(speed * 175)  # 默认175
                cmd.extend(["-s", str(speed_value)])

                cmd.append(text)

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=True))

                return output_path

            # 尝试festival
            elif self._check_command("festival"):
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                    tmp.write(f'(SayText "{text}")\n')
                    tmp_script = tmp.name

                cmd = ["text2wave", "-o", output_path, tmp_script]

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=True))

                os.unlink(tmp_script)
                return output_path

            else:
                logger.error("Neither espeak nor festival found on Linux")
                return None

        except Exception as e:
            logger.error(f"Linux TTS synthesis failed: {e}")
            return None

    def _check_command(self, cmd: str) -> bool:
        """检查命令是否存在"""
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        if self.os_type == "Windows":
            return ["wav"]
        elif self.os_type == "Darwin":
            return ["aiff", "wav", "mp3"]
        elif self.os_type == "Linux":
            return ["wav"]
        return ["wav"]

    def get_voice_list(self) -> List[str]:
        """获取可用音色列表"""
        try:
            if self.os_type == "Windows":
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                voices = speaker.GetVoices()
                return [voices.Item(i).GetDescription() for i in range(voices.Count)]

            elif self.os_type == "Darwin":
                result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    voices = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
                    return voices[:20]  # 限制数量

            elif self.os_type == "Linux":
                if self._check_command("espeak"):
                    result = subprocess.run(["espeak", "--voices"], capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')[1:]  # 跳过表头
                        voices = [line.split()[-1] for line in lines if line.strip()]
                        return voices

            return []

        except Exception as e:
            logger.error(f"Failed to get voice list: {e}")
            return []

    def set_voice(self, voice_id: str):
        """设置音色"""
        self.voice_id = voice_id
        logger.info(f"Voice set to: {voice_id}")

    def set_speed(self, speed: float):
        """设置语速"""
        self.speed = max(0.5, min(2.0, speed))
        logger.info(f"Speed set to: {self.speed}")

    def set_volume(self, volume: float):
        """设置音量"""
        self.volume = max(0.0, min(1.0, volume))
        logger.info(f"Volume set to: {self.volume}")
