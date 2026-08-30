"""
弥娅多模态融合层 — 视觉/听觉/TTS 接入弥娅系统

QQ收到图片 → 视觉分析 → 感知上下文
QQ收到语音 → 听觉分析 → STT转写
弥娅回复   → 情绪驱动 → TTS语音输出
"""

from __future__ import annotations

import base64
import io
import logging
import os
from tempfile import NamedTemporaryFile
from typing import Any

logger = logging.getLogger("miya.multimodal_fusion")


class MiyaMultiModalFusion:
    """弥娅多模态融合 — 连接弥娅的图片/语音/TTS"""

    def __init__(self):
        self._last_vision: dict | None = None
        self._last_audio: dict | None = None

    # ── 视觉: QQ图片 → AP感知 ──

    def process_qq_image(self, image_data: bytes, image_url: str = "") -> dict:
        """
        QQ收到的图片 → 视觉分析 → 感知上下文

        Returns: {"description": str, "features": dict}
        """
        from miya_senses.multimodal import perceive_image

        perception = perceive_image(image_data)

        # 尝试视觉LLM描述
        description = self._try_vision_llm(image_data)
        if not description:
            description = self._describe_from_features(perception)

        result = {
            "width": perception.width,
            "height": perception.height,
            "brightness": round(perception.avg_brightness, 3),
            "contrast": round(perception.contrast, 3),
            "complexity": round(perception.complexity, 3),
            "dominant_colors": perception.dominant_colors[:3],
            "description": description,
        }

        self._last_vision = result
        return result

    def _describe_from_features(self, perception) -> str:
        parts = []
        if perception.avg_brightness < 0.3:
            parts.append("画面偏暗")
        elif perception.avg_brightness > 0.7:
            parts.append("画面明亮")
        if perception.contrast > 0.3:
            parts.append("高对比度")
        parts.append(f"{perception.width}x{perception.height}")
        return ", ".join(parts) if parts else "图片"

    def _try_vision_llm(self, image_data: bytes) -> str:
        try:
            import asyncio
            from core.multi_vision_analyzer import MultiVisionAnalyzer

            async def _run():
                a = MultiVisionAnalyzer()
                await a.initialize()
                r = await a.analyze_image(image_data)
                return r.description if r.success else ""

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.new_event_loop().run_until_complete(_run()))
                    return future.result(timeout=12)
            else:
                return loop.run_until_complete(asyncio.wait_for(_run(), timeout=12))
        except Exception as e:
            logger.debug(f"Vision LLM: {e}")
            return ""

    def _try_vision_llm(self, image_data: bytes) -> str:
        try:
            import asyncio
            from core.multi_vision_analyzer import MultiVisionAnalyzer

            async def _run():
                a = MultiVisionAnalyzer()
                await a.initialize()  # 初始化加载 API 配置
                r = await a.analyze_image(image_data)
                if r.success and r.description:
                    return r.description
                return ""

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.new_event_loop().run_until_complete(_run()))
                    return future.result(timeout=12)
            else:
                return loop.run_until_complete(_run())
        except Exception as e:
            logger.debug(f"Vision LLM failed: {e}")
            return ""

    def get_vision_context(self) -> str:
        if not self._last_vision:
            return ""
        v = self._last_vision
        desc = v.get("description", "")
        if desc:
            return f"[弥娅看到的图片] {desc} ({v['width']}x{v['height']})"
        return ""

    # ── 听觉: QQ语音 → AP感知 ──

    def process_qq_voice(self, audio_data: bytes) -> dict:
        from miya_senses.multimodal import perceive_audio

        perception = perceive_audio(audio_data)
        transcript = ""
        if perception.has_voice:
            transcript = self._try_stt(audio_data)

        result = {
            "duration_ms": round(perception.duration_ms, 0),
            "max_amplitude": round(perception.max_amplitude, 3),
            "has_voice": perception.has_voice,
            "transcript": transcript,
        }

        self._last_audio = result
        return result

    def _try_stt(self, audio_data: bytes) -> str:
        try:
            import asyncio
            from core.providers_astrbot.provider import ProviderManager

            mgr = ProviderManager()
            stt = mgr.get_provider("speech_to_text")
            if stt:
                loop = asyncio.get_event_loop()

                async def _run():
                    return await stt.transcribe(audio_data)

                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(lambda: asyncio.new_event_loop().run_until_complete(_run()))
                        return future.result(timeout=15)
                else:
                    return loop.run_until_complete(_run())
        except Exception as e:
            logger.debug(f"STT failed: {e}")
        return ""

    def get_audio_context(self) -> str:
        if not self._last_audio:
            return ""
        a = self._last_audio
        if a.get("transcript"):
            return f"[弥娅听到的语音] {a['transcript']}"
        if a.get("has_voice"):
            return f"[弥娅听到] 语音 {a['duration_ms']:.0f}ms"
        return f"[弥娅听到] 音频 {a['duration_ms']:.0f}ms"

    # ── TTS: 语音输出 ──

    def speak_with_emotion(self, text: str, engine=None) -> bytes | None:
        """合成语音（emotion/speed 可选，默认中性）"""
        emotion = "neutral"
        speed = 1.0

        try:
            import asyncio
            from core.providers_astrbot.provider import ProviderManager

            mgr = ProviderManager()
            tts = mgr.get_provider("text_to_speech")
            if tts:
                loop = asyncio.get_event_loop()

                async def _run():
                    return await tts.synthesize(text, emotion=emotion, speed=speed)

                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(lambda: asyncio.new_event_loop().run_until_complete(_run()))
                        return future.result(timeout=20)
                else:
                    return loop.run_until_complete(_run())
        except Exception as e:
            logger.debug(f"TTS failed: {e}")
        return None


# 全局单例
_fusion: MiyaMultiModalFusion | None = None


def get_multimodal_fusion() -> MiyaMultiModalFusion:
    global _fusion
    if _fusion is None:
        _fusion = MiyaMultiModalFusion()
    return _fusion
