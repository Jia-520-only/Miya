"""
通用API TTS引擎
支持调用第三方TTS API服务(如Azure TTS, 百度语音, 阿里云TTS等)
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import tempfile
import os
import json

from .tts_engine import TTSEngine


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
        """
        初始化API TTS引擎

        Args:
            config: 配置字典,包含:
                - api_url: API地址
                - api_key: API密钥
                - api_type: API类型 (openai, azure, baidu, ali, custom)
                - voice: 音色(默认alloy)
                - speed: 语速(默认1.0)
                - format: 输出格式(默认mp3)

        Returns:
            bool: 初始化是否成功
        """
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
            speed = kwargs.get("speed", self.speed)
            voice = kwargs.get("voice", self.voice)

            # 创建临时文件保存输出
            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            # 调用API
            result_path = await self._call_api(
                text=text,
                output_path=output_path,
                voice=voice,
                speed=speed
            )

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
            logger.error(f"API TTS synthesis failed: {e}")
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
            voice = kwargs.get("voice", self.voice)

            return await self._call_api(
                text=text,
                output_path=output_path,
                voice=voice,
                speed=speed
            )

        except Exception as e:
            logger.error(f"API TTS synthesis to file failed: {e}")
            return None

    async def _call_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """
        调用TTS API

        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            voice: 音色
            speed: 语速

        Returns:
            str: 输出文件路径
        """
        try:
            if self.api_type == "openai":
                return await self._call_openai_api(text, output_path, voice, speed)
            elif self.api_type == "azure":
                return await self._call_azure_api(text, output_path, voice, speed)
            elif self.api_type == "baidu":
                return await self._call_baidu_api(text, output_path, voice, speed)
            elif self.api_type == "ali":
                return await self._call_ali_api(text, output_path, voice, speed)
            elif self.api_type == "custom":
                return await self._call_custom_api(text, output_path, voice, speed)
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

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "response_format": self.format
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.api_url, headers=headers, json=data, timeout=30)
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"OpenAI TTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"Request data: {data}")
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
                "X-Microsoft-OutputFormat": f"audio-{self.format}"
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
                None,
                lambda: requests.post(self.api_url, headers=headers, data=ssml, timeout=30)
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"Azure TTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"SSML: {ssml[:100]}...")
                return None

        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"Azure TTS API call failed: {e}")
            return None

    async def _call_baidu_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用百度语音合成API"""
        try:
            import requests
            import hashlib
            import time

            # 百度API需要token,这里简化处理
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }

            params = {
                "tex": text,
                "tok": self.api_key,
                "cuid": "miya_tts",
                "ctp": "1",
                "lan": "zh",
                "spd": int(speed * 5)
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.api_url, headers=headers, params=params, timeout=30)
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"Baidu TTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"Request params: {params}")
                return None

        except Exception as e:
            logger.error(f"Baidu TTS API call failed: {e}")
            return None

    async def _call_ali_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用阿里云TTS API"""
        try:
            import requests

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            data = {
                "text": text,
                "voice": voice,
                "speech_rate": str(speed)
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.api_url, headers=headers, json=data, timeout=30)
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"Aliyun TTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"Request data: {data}")
                return None

        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"Aliyun TTS API call failed: {e}")
            return None

    async def _call_custom_api(self, text: str, output_path: str, voice: str, speed: float) -> Optional[str]:
        """调用自定义API"""
        try:
            import requests

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = {
                "text": text,
                "voice": voice,
                "speed": speed,
                "format": self.format
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.api_url, headers=headers, json=data, timeout=30)
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"Custom TTS API error: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"API URL: {self.api_url}")
                logger.error(f"Request data: {data}")
                return None

        except ImportError:
            logger.error("requests library not installed")
            return None
        except Exception as e:
            logger.error(f"Custom TTS API call failed: {e}")
            return None

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return ["mp3", "wav", "flac", "aac"]

    def get_voice_list(self) -> List[str]:
        """获取可用音色列表"""
        if self.api_type == "openai":
            return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        elif self.api_type == "azure":
            return [
                "zh-CN-XiaoxiaoNeural",
                "zh-CN-YunxiNeural",
                "zh-CN-YunyangNeural",
                "zh-CN-XiaohanNeural",
                "zh-CN-XiaomoNeural"
            ]
        elif self.api_type == "baidu":
            return ["0", "1", "3", "4", "5"]
        elif self.api_type == "ali":
            return ["xiaoyun", "xiaogang", "xiaofang"]
        else:
            return ["default"]

    def set_voice(self, voice_id: str):
        """设置音色"""
        self.voice = voice_id
        logger.info(f"Voice set to: {voice_id}")

    def set_speed(self, speed: float):
        """设置语速"""
        self.speed = max(0.5, min(2.0, speed))
        logger.info(f"Speed set to: {self.speed}")
