from __future__ import annotations

"""
弥娅多模态感知系统

支持弥娅「看」图片、「听」音频——感知结果供弥娅感知上下文使用。

图片：PIL 分析（颜色、亮度、复杂度）+ LLM 描述
音频：wave 分析（振幅、频谱、时长）+ LLM 转写
"""


import io
import logging
import math
import struct
import wave
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("miya_senses.multimodal")


# ── 视觉感知 ──


@dataclass
class VisualPerception:
    """图片分析结果"""

    width: int = 0
    height: int = 0
    aspect_ratio: float = 1.0
    dominant_colors: list[tuple[int, int, int]] = field(default_factory=list)
    avg_brightness: float = 0.5
    contrast: float = 0.0
    complexity: float = 0.0
    has_text: bool = False
    llm_description: str = ""
    raw_bytes: bytes | None = None


def perceive_image(image_bytes: bytes, *, thumbnail_size: int = 128) -> VisualPerception:
    """用 PIL 分析图片"""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return VisualPerception(llm_description="[PIL not available]")

    result = VisualPerception()
    result.raw_bytes = image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        result.width, result.height = img.size
        result.aspect_ratio = result.width / max(result.height, 1)

        # 缩略图用于快速分析
        thumb = img.convert("RGB").resize((thumbnail_size, thumbnail_size), Image.LANCZOS)
        pixels = list(thumb.getdata())

        # 亮度
        result.avg_brightness = sum(r + g + b for r, g, b in pixels) / (len(pixels) * 3 * 255)

        # 主导颜色（简单像素聚类）
        color_counts: dict[tuple[int, int, int], int] = {}
        for r, g, b in pixels:
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            color_counts[key] = color_counts.get(key, 0) + 1
        result.dominant_colors = sorted(color_counts, key=color_counts.get, reverse=True)[:5]

        # 对比度（相邻像素亮度差）
        diffs = []
        for i in range(len(pixels) - 1):
            b1 = sum(pixels[i]) / 3
            b2 = sum(pixels[i + 1]) / 3
            diffs.append(abs(b1 - b2) / 255)
        result.contrast = sum(diffs) / max(len(diffs), 1)

        # 复杂度（色彩熵）
        probs = [c / len(pixels) for c in color_counts.values()]
        entropy = -sum(p * math.log2(max(p, 1e-9)) for p in probs)
        result.complexity = min(1.0, entropy / 8.0)

        img.close()
    except Exception as e:
        logger.warning(f"Image analysis failed: {e}")

    return result


# ── 听觉感知 ──


@dataclass
class AudioPerception:
    """音频分析结果"""

    duration_ms: float = 0.0
    sample_rate: int = 0
    channels: int = 1
    max_amplitude: float = 0.0
    avg_amplitude: float = 0.0
    dominant_freq: float = 0.0
    has_voice: bool = False
    llm_transcript: str = ""
    waveform_preview: list[float] = field(default_factory=list)


def perceive_audio(audio_bytes: bytes) -> AudioPerception:
    """分析 WAV 音频"""
    result = AudioPerception()

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            result.sample_rate = wf.getframerate()
            result.channels = wf.getnchannels()
            n_frames = wf.getnframes()
            n_channels = result.channels
            result.duration_ms = (n_frames / max(result.sample_rate, 1)) * 1000

            frames = wf.readframes(min(n_frames, result.sample_rate * 30))
    except Exception as e:
        logger.warning(f"Audio decode failed: {e}")
        return result

    if not frames:
        return result

    # 解码
    try:
        fmt = f"<{len(frames) // 2}h"
        raw = list(struct.unpack(fmt, frames[: len(frames) // 2 * 2]))
        samples = raw if n_channels == 1 else [raw[i] for i in range(0, len(raw), n_channels)]
    except Exception as e:
        logger.warning(f"Audio sample decode failed: {e}")
        return result

    if not samples:
        return result

    # 振幅
    abs_samples = [abs(s) for s in samples]
    result.max_amplitude = max(abs_samples) / 32768.0
    result.avg_amplitude = sum(abs_samples) / (len(abs_samples) * 32768.0)

    # 粗略频谱（简单自相关估算主导频率）
    if len(samples) > 1000:
        chunk = samples[:1000]
        result.dominant_freq = _rough_dominant_freq(chunk, result.sample_rate)

    # 波形预览
    step = max(1, len(samples) // 64)
    preview = []
    for i in range(0, min(len(samples), step * 64), step):
        chunk = samples[i : min(i + step, len(samples))]
        if chunk:
            preview.append(round(max(abs(s) for s in chunk) / 32768.0, 3))
    result.waveform_preview = preview[:64]

    # 简单判断是否有人声（频谱集中在人声范围内）
    result.has_voice = (
        result.avg_amplitude > 0.01
        and result.dominant_freq > 80
        and result.dominant_freq < 3000
        and result.duration_ms > 500
    )

    return result


def _rough_dominant_freq(samples: list[int], sample_rate: int) -> float:
    """简单自相关法估算主导频率"""
    n = len(samples)
    if n < 100:
        return 0.0
    # 检测过零点
    zero_crossings = 0
    for i in range(1, n):
        if (samples[i] >= 0) != (samples[i - 1] >= 0):
            zero_crossings += 1
    return (zero_crossings * sample_rate) / (2 * max(n, 1))
