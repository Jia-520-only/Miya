"""
TTS引擎抽象基类
定义所有TTS引擎必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path


class TTSEngine(ABC):
    """TTS引擎抽象基类"""

    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.is_initialized = False

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化TTS引擎

        Args:
            config: 引擎配置字典

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    async def synthesize(self, text: str, output_format: str = "mp3", **kwargs) -> bytes:
        """
        合成语音

        Args:
            text: 要合成的文本
            output_format: 输出格式 (mp3, wav, silk等)
            **kwargs: 其他参数

        Returns:
            bytes: 语音数据
        """
        pass

    @abstractmethod
    async def synthesize_to_file(self, text: str, output_path: str, output_format: str = "mp3", **kwargs) -> str:
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
        pass

    @abstractmethod
    def get_supported_formats(self) -> list:
        """
        获取支持的音频格式

        Returns:
            list: 支持的格式列表
        """
        pass

    @abstractmethod
    def get_voice_list(self) -> list:
        """
        获取可用音色列表

        Returns:
            list: 音色列表
        """
        pass

    def set_voice(self, voice_id: str):
        """
        设置音色

        Args:
            voice_id: 音色ID
        """
        raise NotImplementedError(f"{self.engine_name} engine does not support voice selection")

    def set_speed(self, speed: float):
        """
        设置语速

        Args:
            speed: 语速倍率 (0.5-2.0)
        """
        raise NotImplementedError(f"{self.engine_name} engine does not support speed adjustment")

    def set_volume(self, volume: float):
        """
        设置音量

        Args:
            volume: 音量 (0.0-1.0)
        """
        raise NotImplementedError(f"{self.engine_name} engine does not support volume adjustment")

    def cleanup(self):
        """清理资源"""
        self.is_initialized = False

    def __repr__(self):
        return f"<TTSEngine: {self.engine_name}>"
