"""
TTS 提供商实现
包含多个TTS引擎的具体实现

MIYA TTS 系统的提供商层
"""

import asyncio
import builtins
import contextlib
import logging
import os
import platform
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from core.constants import HTTPStatus

from .base import TTSEngine

logger = logging.getLogger(__name__)


class APITTSEngine(TTSEngine):
    """通用API TTS引擎 - 支持各种第三方TTS API"""

    def __init__(self):
        super().__init__("api_tts")
        self.api_url = None
        self.api_key = None
        self.api_type = "openai"  # openai, azure, baidu, ali, custom
        self.voice = "alloy"
        self.speed = 1.0
        self.format = "mp3"

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化API TTS引擎"""
        try:
            self.api_url = config.get("api_url")
            self.api_key = config.get("api_key", "")
            self.api_type = config.get("api_type", "openai")
            self.voice = config.get("voice", "alloy")
            self.speed = config.get("speed", 1.0)
            self.format = config.get("format", "mp3")

            if not self.api_url:
                logger.error("API TTS api_url is required")
                return False

            self.is_initialized = True
            logger.info(f"API TTS engine initialized: type={self.api_type}")
            return True

        except Exception as e:
            logger.error(f"API TTS initialization failed: {e}")
            return False

    async def synthesize(self, text: str, output_format: str = "mp3", **kwargs) -> Optional[bytes]:
        """合成语音"""
        try:
            speed = kwargs.get("speed", self.speed)
            voice = kwargs.get("voice", self.voice)

            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            result_path = await self._call_api(text, output_path, voice, speed)

            if result_path and os.path.exists(result_path):
                with open(result_path, "rb") as f:
                    audio_data = f.read()
                with contextlib.suppress(builtins.BaseException):
                    os.unlink(result_path)
                return audio_data

            return None

        except Exception as e:
            logger.error(f"API TTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(
        self, text: str, output_path: str, output_format: str = "mp3", **kwargs
    ) -> Optional[str]:
        """合成语音并保存到文件"""
        try:
            speed = kwargs.get("speed", self.speed)
            voice = kwargs.get("voice", self.voice)
            return await self._call_api(text, output_path, voice, speed)

        except Exception as e:
            logger.error(f"API TTS synthesis to file failed: {e}")
            return None

    async def _call_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用TTS API"""
        try:
            if self.api_type == "openai":
                return await self._call_openai_api(text, output_path, voice, speed)
            elif self.api_type == "azure":
                return await self._call_azure_api(text, output_path, voice, speed)
            else:
                logger.error(f"Unsupported API type: {self.api_type}")
                return None
        except Exception as e:
            logger.error(f"TTS API call failed: {e}")
            return None

    async def _call_openai_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用OpenAI TTS API"""
        try:
            import requests

            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            data = {"model": "tts-1", "input": text, "voice": voice, "response_format": self.format}
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.post(self.api_url, headers=headers, json=data, timeout=60)
            )
            if response.status_code == HTTPStatus.OK:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"OpenAI TTS API error: {response.status_code}")
                return None
        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"OpenAI TTS API call failed: {e}")
            return None

    async def _call_azure_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用Azure TTS API"""
        try:
            import requests

            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": f"audio-{self.format}",
            }
            ssml = f"""
            <speak version='1.0' xml:lang='zh-CN'>
                <voice name='{voice}'>
                    <prosody rate='{speed}'>
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.post(self.api_url, headers=headers, data=ssml, timeout=60)
            )
            if response.status_code == HTTPStatus.OK:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"Azure TTS API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Azure TTS API call failed: {e}")
            return None

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return ["mp3", "wav", "flac", "aac"]

    def get_voice_list(self) -> List[str]:
        """获取可用音色列表"""
        if self.api_type == "openai":
            return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        elif self.api_type == "azure":
            return ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunyangNeural"]
        else:
            return ["default"]

    def set_voice(self, voice_id: str) -> None:
        """设置音色"""
        self.voice = voice_id
        logger.info(f"Voice set to: {voice_id}")

    def set_speed(self, speed: float) -> None:
        """设置语速"""
        self.speed = max(0.5, min(2.0, speed))
        logger.info(f"Speed set to: {self.speed}")


class SystemTTSEngine(TTSEngine):
    """系统TTS引擎,使用操作系统内置TTS"""

    def __init__(self):
        super().__init__("system_tts")
        self.voice_id = None
        self.speed = 1.0
        self.volume = 0.8
        self.os_type = platform.system()

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化系统TTS引擎"""
        try:
            self.voice_id = config.get("voice_id")
            self.speed = config.get("speed", 1.0)
            self.volume = config.get("volume", 0.8)

            if self.os_type == "Windows":
                try:
                    import win32com.client

                    win32com.client.Dispatch("SAPI.SpVoice")
                    logger.info("Windows SAPI TTS available")
                except ImportError:
                    logger.warning("pywin32 not installed, Windows TTS unavailable")
                    return False
            elif self.os_type == "Darwin":
                logger.info("macOS say command available")
            elif self.os_type == "Linux":
                logger.info("Linux espeak/festival available")
            else:
                logger.warning(f"Unsupported OS: {self.os_type}")
                return False

            self.is_initialized = True
            logger.info(f"System TTS engine initialized on {self.os_type}")
            return True

        except Exception as e:
            logger.error(f"System TTS initialization failed: {e}")
            return False

    async def synthesize(self, text: str, output_format: str = "mp3", **kwargs) -> Optional[bytes]:
        """合成语音"""
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            result_path = await self.synthesize_to_file(text, output_path, output_format, **kwargs)

            if result_path and os.path.exists(result_path):
                with open(result_path, "rb") as f:
                    audio_data = f.read()
                with contextlib.suppress(builtins.BaseException):
                    os.unlink(result_path)
                return audio_data

            return None

        except Exception as e:
            logger.error(f"System TTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(
        self, text: str, output_path: str, output_format: str = "mp3", **kwargs
    ) -> Optional[str]:
        """合成语音并保存到文件"""
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

    async def _synthesize_windows(
        self, text: str, output_path: str, voice_id: Optional[str], speed: float
    ) -> Optional[str]:
        """Windows系统使用SAPI"""
        try:
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = int((speed - 1.0) * 10)
            if voice_id:
                voices = speaker.GetVoices()
                for i in range(voices.Count):
                    if voice_id.lower() in voices.Item(i).GetDescription().lower():
                        speaker.Voice = voices.Item(i)
                        break
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Format.Type = 39
            stream.Open(output_path, 3)
            speaker.AudioOutputStream = stream
            speaker.Speak(text)
            stream.Close()
            return output_path
        except Exception as e:
            logger.error(f"Windows TTS synthesis failed: {e}")
            return None

    async def _synthesize_macos(
        self, text: str, output_path: str, voice_id: Optional[str], speed: float, output_format: str
    ) -> Optional[str]:
        """macOS使用say命令"""
        try:
            cmd = ["say", "-o", output_path]
            if voice_id:
                cmd.extend(["-v", voice_id])
            rate = int(speed * 200)
            cmd.extend(["--rate", str(rate)])
            cmd.append(text)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=True))
            return output_path
        except Exception as e:
            logger.error(f"macOS TTS synthesis failed: {e}")
            return None

    async def _synthesize_linux(
        self, text: str, output_path: str, voice_id: Optional[str], speed: float, output_format: str
    ) -> Optional[str]:
        """Linux使用espeak或festival"""
        try:
            if self._check_command("espeak"):
                cmd = ["espeak", "-f", output_path]
                if voice_id:
                    cmd.extend(["-v", voice_id])
                speed_value = int(speed * 175)
                cmd.extend(["-s", str(speed_value)])
                cmd.append(text)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=True))
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
                    lines = result.stdout.split("\n")
                    voices = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
                    return voices[:20]
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


class GPTSoviTSEngine(TTSEngine):
    """GPT-SOViTS TTS引擎 (v2 API)"""

    def __init__(self):
        super().__init__("gpt_sovits")
        self.api_url = None
        self.reference_audio = None
        self.reference_text = None
        self.language = "zh"
        self.speed = 1.0
        self.format = "wav"
        self.top_k = 15
        self.top_p = 1.0
        self.temperature = 1.0
        self.ref_free = False
        self.filter_brackets = True
        self.filter_special_chars = True
        self.streaming = False
        self.chunk_size = 1024

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化GPT-SOViTS引擎"""
        try:
            self.api_url = config.get("api_url")
            self.reference_audio = config.get("reference_audio")
            self.reference_text = config.get("reference_text", "")
            self.language = config.get("language", "zh")
            self.speed = config.get("speed", 1.0)
            self.top_k = config.get("top_k", 15)
            self.top_p = config.get("top_p", 1.0)
            self.temperature = config.get("temperature", 1.0)
            self.ref_free = config.get("ref_free", False)
            self.filter_brackets = config.get("filter_brackets", True)
            self.filter_special_chars = config.get("filter_special_chars", True)
            self.streaming = config.get("streaming", False)
            self.chunk_size = config.get("chunk_size", 1024)

            if not self.api_url:
                logger.error("GPT-SOViTS api_url is required")
                return False

            if not self.api_url.endswith("/tts"):
                self.api_url = f"{self.api_url.rstrip('/')}/tts"

            self.is_initialized = True
            logger.info(f"GPT-SOViTS v2 engine initialized: {self.api_url}")
            return True

        except Exception as e:
            logger.error(f"GPT-SOViTS initialization failed: {e}")
            return False

    async def synthesize(self, text: str, output_format: str = "wav", **kwargs) -> Optional[bytes]:
        """合成语音"""
        try:
            speed = kwargs.get("speed", self.speed)
            reference_audio = kwargs.get("reference_audio", self.reference_audio)
            reference_text = kwargs.get("reference_text", self.reference_text)

            from .utils import filter_text

            text = filter_text(text, self.filter_brackets, self.filter_special_chars)

            if not text:
                logger.warning("Text is empty after filtering")
                return None

            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            result_path = await self._call_api(text, output_path, speed, reference_audio, reference_text)

            if result_path and os.path.exists(result_path):
                with open(result_path, "rb") as f:
                    audio_data = f.read()
                with contextlib.suppress(builtins.BaseException):
                    os.unlink(result_path)
                return audio_data

            return None

        except Exception as e:
            logger.error(f"GPT-SOViTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(
        self, text: str, output_path: str, output_format: str = "wav", **kwargs
    ) -> Optional[str]:
        """合成语音并保存到文件"""
        try:
            speed = kwargs.get("speed", self.speed)
            reference_audio = kwargs.get("reference_audio", self.reference_audio)
            reference_text = kwargs.get("reference_text", self.reference_text)

            from .utils import filter_text

            text = filter_text(text, self.filter_brackets, self.filter_special_chars)

            if not text:
                logger.warning("Text is empty after filtering")
                return None

            return await self._call_api(text, output_path, speed, reference_audio, reference_text)

        except Exception as e:
            logger.error(f"GPT-SOViTS synthesis to file failed: {e}")
            return None

    async def _call_api(
        self, text: str, output_path: str, speed: float, reference_audio: Optional[str], reference_text: Optional[str]
    ) -> Optional[str]:
        """调用GPT-SOViTS v2 API"""
        try:
            import requests

            data = {
                "text": text,
                "text_lang": self.language,
                "streaming": self.streaming,
            }

            if reference_audio and os.path.exists(reference_audio):
                data["ref_audio_path"] = reference_audio
            else:
                logger.warning(f"Reference audio not found: {reference_audio}")

            if reference_text:
                data["prompt_text"] = reference_text
                data["prompt_lang"] = self.language
            else:
                data["prompt_lang"] = self.language

            data["speed_factor"] = speed
            data["top_k"] = self.top_k
            data["top_p"] = self.top_p
            data["temperature"] = self.temperature

            if self.ref_free:
                data["ref_free"] = True

            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(None, lambda: requests.post(self.api_url, json=data, timeout=60))

            if response.status_code == HTTPStatus.OK:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"GPT-SOViTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                return None

        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"GPT-SOViTS API call failed: {e}")
            return None

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return ["wav", "mp3", "flac", "ogg", "silk"]

    def get_voice_list(self) -> List[str]:
        """获取可用音色列表"""
        return ["custom"]

    def set_reference(self, reference_audio: str, reference_text: str = ""):
        """设置参考音频"""
        self.reference_audio = reference_audio
        self.reference_text = reference_text
        logger.info(f"Reference audio set: {reference_audio}")

    def set_speed(self, speed: float):
        """设置语速"""
        self.speed = max(0.5, min(2.0, speed))
        logger.info(f"Speed set to: {self.speed}")

    def set_filter_options(self, brackets: bool, special_chars: bool):
        """设置文本过滤选项"""
        self.filter_brackets = brackets
        self.filter_special_chars = special_chars
        logger.info(f"Filter options set: brackets={brackets}, special_chars={special_chars}")

    def set_streaming(self, enabled: bool):
        """设置流式输出"""
        self.streaming = enabled
        logger.info(f"Streaming set to: {enabled}")
