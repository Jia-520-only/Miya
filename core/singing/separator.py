"""
弥娅内置唱歌引擎 — 人声分离模块

- DemucsSeparator: demucs CLI (htdemucs_ft → htdemucs → mdx_extra)
- FFmpegSeparator: 回退方案
"""

import asyncio
import logging
import os
import shutil
import sys
from abc import ABC, abstractmethod
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class VocalSeparator(ABC):
    """人声分离抽象基类"""

    def __init__(self, name: str):
        self.name = name
        self.is_initialized = False

    @abstractmethod
    def initialize(self, config: dict) -> bool:
        pass

    @abstractmethod
    async def separate(self, audio_path: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
        pass

    def cleanup(self):
        self.is_initialized = False


class DemucsSeparator(VocalSeparator):
    """demucs CLI 人声分离器"""

    def __init__(self):
        super().__init__("demucs")
        self.python_exe: str = "python"
        self.models: list = ["htdemucs_ft", "htdemucs", "mdx_extra"]
        self.timeout: int = 300

    def initialize(self, config: dict) -> bool:
        self.python_exe = config.get("demucs_python", "python")
        self.models = config.get("demucs_models", ["htdemucs_ft", "htdemucs", "mdx_extra"])
        self.timeout = config.get("demucs_timeout", 300)
        self.is_initialized = True
        logger.info(f"Demucs ready: models={self.models}")
        return True

    async def separate(self, audio_path: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
        import subprocess as _sp

        src_abs = os.path.abspath(audio_path)
        tmp_dir = os.path.abspath(os.path.join(output_dir, "_dmc"))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        tmp_src = os.path.join(tmp_dir, "_src" + os.path.splitext(src_abs)[1])
        shutil.copy2(src_abs, tmp_src)

        for model in self.models:
            shutil.rmtree(os.path.join(tmp_dir, "out"), ignore_errors=True)
            logger.info(f"[分离] demucs [{model}]: {os.path.basename(src_abs)}")
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda m=model: _sp.run(
                        [
                            self.python_exe,
                            "-m",
                            "demucs",
                            "--two-stems=vocals",
                            "-n",
                            m,
                            "-o",
                            os.path.join(tmp_dir, "out"),
                            tmp_src,
                        ],
                        capture_output=True,
                        timeout=self.timeout,
                    ),
                )
            except (_sp.TimeoutExpired, Exception) as e:
                logger.warning(f"[分离] demucs [{model}] error: {e}")
                continue

            if result.returncode != 0:
                logger.warning(f"[分离] demucs [{model}] rc={result.returncode}")
                continue

            dmc_base = os.path.join(tmp_dir, "out")
            dmc_out = os.path.join(dmc_base, model)
            if not os.path.isdir(dmc_out):
                try:
                    for entry in os.listdir(dmc_base):
                        candidate = os.path.join(dmc_base, entry)
                        if os.path.isdir(candidate):
                            dmc_out = candidate
                            break
                except Exception:
                    pass

            dmc_v = None
            stem_files = {}
            for root, _dirs, files in os.walk(dmc_out):
                for f in files:
                    fp = os.path.join(root, f)
                    if f == "vocals.wav":
                        dmc_v = fp
                    elif f in ("drums.wav", "bass.wav", "other.wav", "no_vocals.wav"):
                        stem_files[f] = fp

            if not dmc_v:
                logger.warning(f"[分离] demucs [{model}] no vocals.wav in output")
                continue

            base = os.path.abspath(output_dir)
            vocal_out = os.path.join(base, "Vocals.wav")
            shutil.move(dmc_v, vocal_out)

            inst_out = await _build_instrumental(stem_files, base)

            usable, peak, nonzero_pct = _check_amplitude(vocal_out, inst_out)
            if usable:
                logger.info(f"[分离] demucs OK [{model}]")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return vocal_out, inst_out
            logger.warning(f"[分离] demucs [{model}] 人声薄弱 peak={peak} nonzero={nonzero_pct:.0f}%, 尝试下一模型")

        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.warning("[分离] all models failed, fallback to ffmpeg")
        return await _ffmpeg_fallback(src_abs, output_dir)


class FFmpegSeparator(VocalSeparator):
    """ffmpeg 回退 — 全曲当人声"""

    def __init__(self):
        super().__init__("ffmpeg")

    def initialize(self, config: dict) -> bool:
        self.is_initialized = True
        return True

    async def separate(self, audio_path: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
        return await _ffmpeg_fallback(audio_path, output_dir)


class UVR5Separator(VocalSeparator):
    """UVR5 分离器 — 支持两种 provider:
    - sovits: GPT-SoVITS 整合包的 BS-Roformer/VR 模型 (质量最高, SDR 12.97)
    - rvc:    RVC 整合包自带的 HP5 等模型 (无需 GPT-SoVITS)
    """

    def __init__(self, provider: str = "sovits"):
        super().__init__("uvr5")
        self.provider = provider
        self.python_exe: str = ""
        self.cli_script: str = ""
        self.models: list = []
        self.device: str = "cuda"
        self.timeout: int = 600

    def initialize(self, config: dict) -> bool:
        from .paths import expand_path

        self.provider = config.get("provider", self.provider)
        self.python_exe = config.get("uvr5_python", sys.executable)
        if self.provider == "rvc":
            self.cli_script = config.get(
                "uvr5_cli",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "rvc_uvr5_cli.py"),
            )
        else:
            self.cli_script = config.get(
                "uvr5_cli",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "uvr5_cli.py"),
            )
        self.models = [
            {**m, "path": expand_path(m.get("path", ""))}
            for m in (config.get("uvr5_models") or [])
        ]
        self.device = config.get("uvr5_device", "cuda")
        self.timeout = config.get("uvr5_timeout", 600)
        self.is_initialized = True
        logger.info(f"UVR5 ready (provider={self.provider}): models={[m.get('type') for m in self.models]}")
        return True

    async def separate(self, audio_path: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
        import subprocess as _sp

        src_abs = os.path.abspath(audio_path)
        out_abs = os.path.abspath(output_dir)

        wav_input = os.path.join(out_abs, "_uvr5_input.wav")
        try:
            _sp.run(
                [
                    _find_ffmpeg(),
                    "-y",
                    "-i",
                    src_abs,
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-sample_fmt",
                    "s16",
                    wav_input,
                ],
                capture_output=True,
                timeout=120,
            )
            if os.path.exists(wav_input) and os.path.getsize(wav_input) > 0:
                src_abs = wav_input
                logger.info(f"[UVR5] WAV 预转换完成: {os.path.getsize(wav_input)}B")
        except Exception as e:
            logger.warning(f"[UVR5] WAV 预转换失败, 使用原始文件: {e}")

        for model_cfg in self.models:
            model_type = model_cfg["type"]
            model_path = model_cfg.get("path", "")

            if self.provider != "rvc" and not os.path.exists(model_path):
                logger.warning(f"[UVR5] 模型不存在: {model_path}")
                continue

            logger.info(f"[UVR5] {model_type}: {os.path.basename(src_abs)}")
            from .paths import get_gpt_sovits_root, get_rvc_root

            _sovits_root = get_gpt_sovits_root()
            _rvc_root = get_rvc_root()

            if self.provider == "rvc":
                cmd = [
                    self.python_exe,
                    self.cli_script,
                    src_abs,
                    out_abs,
                    "--model",
                    model_cfg.get("name", model_path or "HP5_only_main_vocal"),
                    "--device",
                    self.device,
                    "--rvc-root",
                    _rvc_root or "",
                ]
            else:
                cmd = [
                    self.python_exe,
                    self.cli_script,
                    src_abs,
                    out_abs,
                    "--model-type",
                    model_type,
                    "--model-path",
                    model_path,
                    "--device",
                    self.device,
                    "--sovits-root",
                    _sovits_root,
                ]
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda c=cmd: _sp.run(
                        c,
                        capture_output=True,
                        timeout=self.timeout,
                        encoding="utf-8",
                        errors="replace",
                    ),
                )
            except (_sp.TimeoutExpired, Exception) as e:
                logger.warning(f"[UVR5] {model_type} error: {e}")
                continue

            if result.returncode != 0:
                logger.warning(f"[UVR5] {model_type} rc={result.returncode} stderr={result.stderr[-2000:]}")
                continue

            vocal_out = os.path.join(out_abs, "Vocals.wav")
            inst_out = os.path.join(out_abs, "Instrumental.wav")

            if os.path.exists(vocal_out):
                usable, peak, nonzero_pct = _check_amplitude(vocal_out, inst_out)
                if usable:
                    logger.info(f"[UVR5] OK [{model_type}] stdout={result.stdout.strip()}")
                    return vocal_out, inst_out
                logger.warning(f"[UVR5] {model_type} 人声薄弱 peak={peak} nonzero={nonzero_pct:.0f}%")
            else:
                logger.warning(f"[UVR5] {model_type} no Vocals.wav output")

        logger.warning("[UVR5] all models failed")
        return None, None


async def _build_instrumental(stem_files: dict, output_dir: str) -> Optional[str]:
    if not stem_files:
        return None

    no_vocals = stem_files.get("no_vocals.wav")
    if no_vocals:
        import os
        import shutil

        target = os.path.join(output_dir, "Instrumental.wav")
        shutil.move(no_vocals, target)
        return target

    inst_parts = [p for k, p in stem_files.items() if k in ("drums.wav", "bass.wav", "other.wav")]
    if not inst_parts:
        return None

    import os
    import subprocess as _sp

    target = os.path.join(output_dir, "Instrumental.wav")
    inputs = []
    for p in inst_parts:
        inputs.extend(["-i", p])
    labels = "".join(f"[{i}]" for i in range(len(inst_parts)))
    amix = f"{labels}amix=inputs={len(inst_parts)}:duration=longest"
    try:
        _sp.run(
            [_find_ffmpeg(), "-y"] + inputs + ["-filter_complex", amix, target],
            capture_output=True,
            timeout=120,
        )
        if os.path.exists(target) and os.path.getsize(target) > 0:
            return target
    except Exception:
        pass
    return None


async def _ffmpeg_fallback(src: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
    import subprocess as _sp

    v_out = os.path.join(output_dir, "Vocals.wav")
    i_out = os.path.join(output_dir, "Instrumental.wav")
    marker = os.path.join(output_dir, "_fallback.marker")

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _sp.run(
                [_find_ffmpeg(), "-y", "-i", src, "-ac", "1", v_out],
                capture_output=True,
                timeout=120,
            ),
        )
        shutil.copy2(v_out, i_out) if os.path.exists(v_out) else None
        with open(marker, "w") as f:
            f.write("fallback")
        logger.info("[分离] ffmpeg fallback (full song as both tracks)")
        return (
            v_out if os.path.exists(v_out) else None,
            i_out if os.path.exists(i_out) else None,
        )
    except Exception:
        return None, None


def _find_ffmpeg() -> str:
    from .paths import find_ffmpeg

    return find_ffmpeg()


def _check_amplitude(vocal_path: Optional[str], inst_path: Optional[str]):
    import numpy as np

    vocal_usable = True
    vocal_peak = 0.0
    vocal_nonzero_pct = 0.0

    try:
        import soundfile as sf
    except ImportError:
        sf = None

    for label, path in [("vocal", vocal_path), ("inst", inst_path)]:
        if not path or not os.path.exists(path):
            continue
        try:
            max_read = 48000 * 3
            start_frame = 0
            if sf is not None:
                info = sf.info(path)
                total_frames = info.frames
                if total_frames > max_read * 3:
                    start_frame = total_frames // 3
                data, _sr = sf.read(path, frames=max_read, start=start_frame, dtype="float32")
            else:
                import array as _arr
                import wave

                with wave.open(path, "rb") as w:
                    sw = w.getsampwidth()
                    n_frames = min(w.getnframes(), max_read)
                    frames = w.readframes(n_frames)
                    n_frames * w.getnchannels()
                    if sw == 2:
                        raw = _arr.array("h", frames)
                    elif sw == 4:
                        raw = _arr.array("i", frames)
                    elif sw == 1:
                        raw = _arr.array("b", frames)
                    else:
                        raw = _arr.array("h", frames)
                data = np.array(raw, dtype=np.float32)
                if sf is None and sw == 2:
                    data /= 32768.0

            if data.ndim == 1:
                data = data.reshape(-1, 1)

            peak = float(np.max(np.abs(data)))
            nonzero = float(np.count_nonzero(np.abs(data) > 0.005) / max(data.size, 1) * 100)

            if peak < 0.01 and nonzero < 1.0:
                logger.warning(f"[分离] {label} 振幅极低 peak={peak:.4f} nonzero={nonzero:.1f}%")
            else:
                logger.info(f"[分离] {label} peak={peak:.4f} nonzero={nonzero:.1f}%")

            if label == "vocal":
                vocal_peak = peak
                vocal_nonzero_pct = nonzero
                if peak < 0.01 and nonzero < 1.0:
                    vocal_usable = False
        except Exception as e:
            logger.warning(f"[分离] {label} 振幅检查异常: {e}")
            if label == "vocal":
                vocal_usable = False

    return vocal_usable, vocal_peak, vocal_nonzero_pct
