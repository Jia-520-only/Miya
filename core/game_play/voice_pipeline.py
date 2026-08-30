"""
游戏陪玩 - 语音管线

将弥娅现有的 ASR + TTS 能力整合为游戏陪玩的语音管道。
支持: 麦克风输入 → ASR → 对话 → TTS 输出
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VoicePipeline:
    """
    语音管线 — 游戏陪玩的语音通道

    流程: 麦克风 → ASR → 对话引擎 → TTS → 扬声器

    复用弥娅现有的:
    - ASR: core/providers/bridge.py → speech_to_text()
    - TTS: core/tts/manager.py → get_tts_registry()
    """

    def __init__(self):
        self._tts_registry: Any = None
        self._asr_provider: Any = None
        self._enabled = False
        self._voice_active = False

    async def initialize(self):
        try:
            from core.tts.manager import get_tts_registry

            self._tts_registry = get_tts_registry()
            engines = self._tts_registry.engines
            if engines:
                logger.info(f"[VoicePipeline] TTS 引擎已就绪: {list(engines.keys())}")
            else:
                logger.warning("[VoicePipeline] 未找到可用的 TTS 引擎")

        except Exception as e:
            logger.warning(f"[VoicePipeline] TTS 初始化失败: {e}")

        try:
            from core.providers.bridge import ProviderBridge

            bridge = ProviderBridge()
            self._asr_provider = getattr(bridge, "speech_to_text", None)
            if self._asr_provider:
                logger.info("[VoicePipeline] ASR 已就绪")
            else:
                logger.warning("[VoicePipeline] ASR provider 未找到")
        except Exception as e:
            logger.warning(f"[VoicePipeline] ASR 初始化失败: {e}")

        self._enabled = self._tts_registry is not None
        logger.info(f"[VoicePipeline] 初始化完成 (enabled={self._enabled})")

    async def speak(self, text: str) -> bool:
        """
        将文本转为语音并播放。

        Args:
            text: 要说的文本

        Returns:
            是否成功播放
        """
        if not self._enabled or not self._tts_registry:
            logger.warning("[VoicePipeline] TTS 未就绪")
            return False

        engine_name = self._tts_registry.current_engine
        if not engine_name:
            logger.warning("[VoicePipeline] 没有活动的 TTS 引擎")
            return False

        try:
            self._tts_registry.speak(text, engine_name)
            logger.debug(f"[VoicePipeline] 语音输出: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"[VoicePipeline] 语音输出失败: {e}")
            return False

    async def synthesize(self, text: str) -> Optional[bytes]:
        """合成语音但不播放，返回音频字节"""
        if not self._enabled or not self._tts_registry:
            return None

        try:
            engine = self._tts_registry.get_engine()
            if engine is None:
                return None
            audio_bytes = await engine.synthesize(text)
            return audio_bytes
        except Exception as e:
            logger.error(f"[VoicePipeline] 语音合成失败: {e}")
            return None

    async def transcribe(self, audio_data: bytes) -> Optional[str]:
        """语音转文字"""
        if not self._asr_provider:
            logger.warning("[VoicePipeline] ASR 未就绪")
            return None

        try:
            text = await self._asr_provider(audio_data)
            return text
        except Exception as e:
            logger.error(f"[VoicePipeline] ASR 转写失败: {e}")
            return None

    def set_active(self, active: bool):
        self._voice_active = active
        logger.info(f"[VoicePipeline] 语音 {'激活' if active else '静默'}")

    @property
    def is_enabled(self) -> bool:
        return self._enabled
