"""
GPT-SOViTS TTS引擎实现 (支持v2 API)
支持GPT-SOViTS语音合成,包含文本过滤和流式输出控制
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import tempfile
import os
import re

from .tts_engine import TTSEngine


logger = logging.getLogger(__name__)


def filter_text(text: str,
               filter_brackets: bool = True,
               filter_special_chars: bool = True) -> str:
    """
    过滤文本,移除括号和特殊字符

    Args:
        text: 原始文本
        filter_brackets: 是否过滤括号
        filter_special_chars: 是否过滤特殊字符

    Returns:
        str: 过滤后的文本
    """
    # 过滤括号内容 【xxx】 (xxx) <xxx>
    if filter_brackets:
        text = re.sub(r'【.*?】', '', text)
        text = re.sub(r'（.*?）', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'<.*?>', '', text)

    # 过滤特殊字符
    if filter_special_chars:
        # 保留中文、英文、数字、基本标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''（）《》【】\s,\.!?;:\'\-]', '', text)

    # 清理多余空格
    text = re.sub(r'\s+', '', text)

    return text.strip()


def split_text_for_qq(text: str, max_length: int = 200) -> List[str]:
    """
    将文本分割为适合QQ发送的片段

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        List[str]: 分割后的文本片段
    """
    if len(text) <= max_length:
        return [text]

    segments = []
    current = ""

    # 按句子分割
    sentences = re.split(r'([。！？\n])', text)

    for sentence in sentences:
        if not sentence:
            continue

        if len(current) + len(sentence) <= max_length:
            current += sentence
        else:
            if current:
                segments.append(current)
            current = sentence

    if current:
        segments.append(current)

    return segments


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

        # v2 API 参数
        self.top_k = 15
        self.top_p = 1.0
        self.temperature = 1.0
        self.ref_free = False

        # 文本过滤
        self.filter_brackets = True
        self.filter_special_chars = True

        # 流式输出
        self.streaming = False
        self.chunk_size = 1024

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化GPT-SOViTS引擎

        Args:
            config: 配置字典,包含:
                - api_url: GPT-SOViTS API地址 (如 http://127.0.0.1:9880)
                - api_key: API密钥(可选)
                - reference_audio: 参考音频路径
                - reference_text: 参考文本
                - language: 语言(默认zh)
                - speed: 语速(默认1.0)
                - top_k: top_k采样参数
                - top_p: top_p采样参数
                - temperature: 温度参数
                - ref_free: 是否使用无参考模式
                - filter_brackets: 是否过滤括号
                - filter_special_chars: 是否过滤特殊字符
                - streaming: 是否启用流式输出

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.api_url = config.get("api_url")
            self.reference_audio = config.get("reference_audio")
            self.reference_text = config.get("reference_text", "")
            self.language = config.get("language", "zh")
            self.speed = config.get("speed", 1.0)

            # v2 API 参数
            self.top_k = config.get("top_k", 15)
            self.top_p = config.get("top_p", 1.0)
            self.temperature = config.get("temperature", 1.0)
            self.ref_free = config.get("ref_free", False)

            # 文本过滤
            self.filter_brackets = config.get("filter_brackets", True)
            self.filter_special_chars = config.get("filter_special_chars", True)

            # 流式输出
            self.streaming = config.get("streaming", False)
            self.chunk_size = config.get("chunk_size", 1024)

            if not self.api_url:
                logger.error("GPT-SOViTS api_url is required")
                return False

            # 确保API URL以 /tts 结尾
            if not self.api_url.endswith('/tts'):
                self.api_url = f"{self.api_url.rstrip('/')}/tts"

            self.is_initialized = True
            logger.info(f"GPT-SOViTS v2 engine initialized: {self.api_url}")
            return True

        except Exception as e:
            logger.error(f"GPT-SOViTS initialization failed: {e}")
            return False

    async def synthesize(self, text: str, output_format: str = "wav", **kwargs) -> Optional[bytes]:
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
            reference_audio = kwargs.get("reference_audio", self.reference_audio)
            reference_text = kwargs.get("reference_text", self.reference_text)

            # 过滤文本
            filter_brackets = kwargs.get("filter_brackets", self.filter_brackets)
            filter_special_chars = kwargs.get("filter_special_chars", self.filter_special_chars)
            text = filter_text(text, filter_brackets, filter_special_chars)

            if not text:
                logger.warning("Text is empty after filtering")
                return None

            # 创建临时文件保存输出
            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                output_path = tmp_file.name

            # 调用GPT-SOViTS API
            result_path = await self._call_api(
                text=text,
                output_path=output_path,
                speed=speed,
                reference_audio=reference_audio,
                reference_text=reference_text
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
            logger.error(f"GPT-SOViTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(self, text: str, output_path: str,
                                output_format: str = "wav", **kwargs) -> Optional[str]:
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
            reference_audio = kwargs.get("reference_audio", self.reference_audio)
            reference_text = kwargs.get("reference_text", self.reference_text)

            # 过滤文本
            filter_brackets = kwargs.get("filter_brackets", self.filter_brackets)
            filter_special_chars = kwargs.get("filter_special_chars", self.filter_special_chars)
            text = filter_text(text, filter_brackets, filter_special_chars)

            if not text:
                logger.warning("Text is empty after filtering")
                return None

            return await self._call_api(
                text=text,
                output_path=output_path,
                speed=speed,
                reference_audio=reference_audio,
                reference_text=reference_text
            )

        except Exception as e:
            logger.error(f"GPT-SOViTS synthesis to file failed: {e}")
            return None

    async def _call_api(self, text: str, output_path: str, speed: float,
                       reference_audio: Optional[str],
                       reference_text: Optional[str]) -> Optional[str]:
        """
        调用GPT-SOViTS v2 API

        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            speed: 语速
            reference_audio: 参考音频
            reference_text: 参考文本

        Returns:
            str: 输出文件路径
        """
        try:
            import requests

            # GPT-SOViTS v2 API 使用 JSON 格式
            data = {
                "text": text,
                "text_lang": self.language,
                "streaming": self.streaming,
            }

            # 参考音频路径
            if reference_audio and os.path.exists(reference_audio):
                data["ref_audio_path"] = reference_audio
            else:
                logger.warning(f"Reference audio not found: {reference_audio}")

            # 参考文本和语言（prompt_lang 是必需参数）
            if reference_text:
                data["prompt_text"] = reference_text
                data["prompt_lang"] = self.language
            else:
                # 即使没有参考文本，也需要提供 prompt_lang
                data["prompt_lang"] = self.language

            # v2 参数
            data["speed_factor"] = speed
            data["top_k"] = self.top_k
            data["top_p"] = self.top_p
            data["temperature"] = self.temperature

            if self.ref_free:
                data["ref_free"] = True

            # 使用run_in_executor避免阻塞
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.api_url,
                    json=data,
                    timeout=60
                )
            )

            if response.status_code == 200:
                # 保存返回的音频数据
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"GPT-SOViTS API error: {response.status_code}")
                logger.error(f"API URL: {self.api_url}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"Request data: {data}")
                logger.error(f"Reference audio exists: {reference_audio and os.path.exists(reference_audio)}")
                return None

        except ImportError:
            logger.error("requests library not installed, please install with: pip install requests")
            return None
        except Exception as e:
            logger.error(f"GPT-SOViTS API call failed: {e}")
            return None

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return ["wav", "mp3", "flac", "ogg", "silk"]

    def get_voice_list(self) -> List[str]:
        """获取可用音色列表"""
        return ["custom"]  # GPT-SOViTS使用参考音频,不预设音色

    def set_reference(self, reference_audio: str, reference_text: str = ""):
        """
        设置参考音频

        Args:
            reference_audio: 参考音频路径
            reference_text: 参考文本
        """
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
