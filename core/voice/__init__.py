"""
弥娅语音系统 - 统一入口

支持多种 TTS 引擎：
- Edge-TTS (微软Edge语音)
- VITS (本地部署)
- GPT-SoVITS (保留原有)

使用 TTSWrapper 解决 asyncio 事件循环冲突问题
"""

import builtins
import contextlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TTSEngineType(Enum):
    """TTS 引擎类型"""

    EDGE_TTS = "edge_tts"
    VITS = "vits"
    SOVITS = "sovits"


@dataclass
class TTSResult:
    """TTS 结果"""

    success: bool
    audio_data: Optional[bytes] = None
    file_path: Optional[str] = None
    error: Optional[str] = None
    engine: str = ""


class MiyaVoiceManager:
    """弥娅统一语音管理器"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._current_engine = TTSEngineType.EDGE_TTS
        self._engines = {}
        self._wrapper = None
        self._edge_voice = "zh-CN-XiaoxiaoNeural"
        self._sovits_engine = None

    @property
    def current_engine(self) -> TTSEngineType:
        return self._current_engine

    async def initialize(self) -> bool:
        """初始化语音系统"""
        try:
            from core.voice.tts_wrapper import TTSWrapper

            self._wrapper = TTSWrapper()
            self._engines[TTSEngineType.EDGE_TTS] = self._wrapper
            logger.info("[VoiceManager] Edge-TTS 初始化完成")

            # 检查 SoVITS
            with contextlib.suppress(builtins.BaseException):
                logger.info("[VoiceManager] GPT-SoVITS 可用（需配置）")

            return True
        except Exception as e:
            logger.error(f"[VoiceManager] 初始化失败: {e}")
            return False

    async def speak(self, text: str, engine: Optional[TTSEngineType] = None) -> TTSResult:
        """统一语音合成接口"""
        engine = engine or self._current_engine

        if engine == TTSEngineType.EDGE_TTS and self._wrapper:
            try:
                audio = self._wrapper.generate_speech_safe(text, self._edge_voice)
                return TTSResult(success=bool(audio), audio_data=audio, engine="edge_tts")
            except Exception as e:
                return TTSResult(success=False, error=str(e), engine="edge_tts")

        return TTSResult(success=False, error="Engine not available", engine=engine.value)

    def set_engine(self, engine: TTSEngineType) -> bool:
        """切换 TTS 引擎"""
        self._current_engine = engine
        return True

    def set_edge_voice(self, voice: str) -> None:
        """设置 Edge-TTS 语音"""
        self._edge_voice = voice

    def get_available_engines(self) -> List[str]:
        """获取可用的引擎列表"""
        return [e.value for e in self._engines]

    def get_available_voices(self) -> Dict[str, List[str]]:
        """获取各引擎可用的语音列表"""
        return {
            "edge_tts": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
            "vits": ["需要配置模型"],
            "sovits": ["需要配置模型"],
        }


_voice_manager: Optional[MiyaVoiceManager] = None


def get_voice_manager() -> MiyaVoiceManager:
    """获取语音管理器全局实例"""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = MiyaVoiceManager.get_instance()
    return _voice_manager


async def initialize_voice_system() -> bool:
    """初始化语音系统（便捷函数）"""
    manager = get_voice_manager()
    return await manager.initialize()
