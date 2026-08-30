"""
弥娅音频引擎 Python 宿主
通过 pip 安装 simpleaudio 即可播放 MIDI 渲染的 WAV
"""

import json
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional

SAMPLE_RATE = 44100
DEFAULT_VOLUME = 0.3
MAX_AMPLITUDE = 32767 * DEFAULT_VOLUME

MIDI_NOTE_FREQUENCIES = {n: 440.0 * (2 ** ((n - 69) / 12.0)) for n in range(0, 128)}


def _note_to_samples(
    pitch: int,
    start_beat: float,
    duration_beats: float,
    velocity: int,
    bpm: float = 120.0,
) -> list[float]:
    """将单个 MIDI 音符渲染为浮点样本列表"""
    freq = MIDI_NOTE_FREQUENCIES.get(pitch, 440.0)
    vel_ratio = velocity / 127.0

    beat_duration = 60.0 / bpm
    num_samples = int(duration_beats * beat_duration * SAMPLE_RATE)

    if num_samples <= 0:
        return []

    amplitude = vel_ratio * MAX_AMPLITUDE
    samples = []

    for i in range(num_samples):
        t = i / SAMPLE_RATE
        envelope = _adsr_envelope(i, num_samples, vel_ratio)
        val = math.sin(2.0 * math.pi * freq * t) * amplitude * envelope
        samples.append(val)

    return samples


def _adsr_envelope(i: int, total: int, velocity: float) -> float:
    """简易 ADSR 包络"""
    attack = min(total // 8, 2205)
    decay = min(total // 4, 4410)
    sustain_level = 0.7 * velocity

    if i < attack:
        return i / attack
    elif i < attack + decay:
        progress = (i - attack) / decay
        return 1.0 - (1.0 - sustain_level) * progress
    else:
        release_start = max(attack + decay, int(total * 0.75))
        if i >= release_start and total > release_start:
            return sustain_level * (1.0 - (i - release_start) / (total - release_start))
        return sustain_level


def render_project_to_wav(
    project: dict,
    output_path: Optional[Path] = None,
    bpm: float = 120.0,
) -> Path:
    """将 MIYA 音乐项目渲染为 WAV 文件"""
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".wav"))

    bpm = project.get("tempo", bpm)
    length_beats = project.get("length_beats", 16.0)

    beat_duration = 60.0 / bpm
    total_samples = int(length_beats * beat_duration * SAMPLE_RATE) + SAMPLE_RATE

    mixed = [0.0] * total_samples

    for track in project.get("tracks", []):
        if track.get("mute", False):
            continue
        vol = track.get("volume", 0.8)

        for note in track.get("notes", []):
            if not isinstance(note, dict):
                continue
            pitch = note.get("pitch", 60)
            start = note.get("start", 0.0)
            duration = note.get("duration", 0.25)
            velocity = note.get("velocity", 96)

            samples = _note_to_samples(pitch, start, duration, velocity, bpm)
            start_sample = int(start * beat_duration * SAMPLE_RATE)

            for i, s in enumerate(samples):
                idx = start_sample + i
                if idx < len(mixed):
                    mixed[idx] += s * vol

    # 归一化
    max_val = max(abs(v) for v in mixed) if mixed else 1.0
    if max_val > MAX_AMPLITUDE * 2:
        scale = MAX_AMPLITUDE / max_val
        mixed = [v * scale for v in mixed]

    # 写入 WAV
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for sample in mixed:
            clamped = max(-32767, min(32767, int(sample)))
            wf.writeframes(struct.pack("<h", clamped))

    return output_path


def play_project(project: dict, bpm: float = 120.0) -> Path:
    """渲染并播放音乐项目（子进程隔离播放，避免 simpleaudio 崩溃拖垮主进程）"""
    wav_path = render_project_to_wav(project, bpm=bpm)

    from core.audio_player import play_audio_isolated

    play_audio_isolated(str(wav_path))

    return wav_path


def render_project_to_wav_bytes(project: dict, bpm: float = 120.0) -> bytes:
    """渲染为 WAV 字节（用于流式传输或 MCP 返回）"""
    path = render_project_to_wav(project, bpm=bpm)
    data = path.read_bytes()
    path.unlink()
    return data
