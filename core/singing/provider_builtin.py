"""
弥娅内置唱歌引擎 — BuiltinSingingEngine

自包含的本地唱歌管线：
  音乐源 → 下载 → 多轮人声分离(BS-Roformer → VR和声 → VR去混响)
           → 归一化 → RVC换声 → 人声后处理效果 → 多轨混音 → 播放
"""

import asyncio
import logging
import os
import shutil
import sys
from typing import Any, Dict, List, Optional

import numpy as np

from .base import LearnStatus, LearnTask, SingingEngine, SongInfo
from .music_source import MusicSource
from .separator import VocalSeparator

logger = logging.getLogger(__name__)


class BuiltinSingingEngine(SingingEngine):
    """内置唱歌引擎 — 本地全流程管线"""

    def __init__(self):
        super().__init__("builtin")
        self.output_base_dir: str = "data/singing"
        self.volume_vocal: int = 70
        self.volume_accompany: int = 70
        self.learn_timeout: int = 300

        self.music_source: Optional[MusicSource] = None
        self.source_type: str = "local"

        self.separator: Optional[VocalSeparator] = None
        self._demucs_separator: Optional[VocalSeparator] = None

        self.separation_stages: List[Dict[str, str]] = []
        self.separation_stages_enabled: bool = False

        self.effects_enabled: bool = True
        self.effects_compressor_threshold: float = -12.0
        self.effects_compressor_ratio: float = 2.5
        self.effects_highpass_hz: float = 80.0
        self.effects_highshelf_gain_db: float = -1.5
        self.effects_highshelf_freq_hz: float = 8000.0
        self.effects_limiter_threshold_db: float = -3.0
        self.effects_gain_db: float = 2.0
        self.effects_reverb_room: float = 0.0
        self.effects_reverb_wet: float = 0.0

        self.mix_chord_enabled: bool = True
        self.mix_chord_volume: int = 50

        self.uvr5_python: str = "python"
        self.uvr5_cli: str = ""
        self.uvr5_device: str = "cuda"
        self.uvr5_timeout: int = 600

        self.rvc_api_url: str = "http://127.0.0.1:7897"
        self.rvc_model: str = "guanguanV1"
        self.rvc_f0_up_key: int = 0
        self.rvc_f0_method: str = "rmvpe"
        self.rvc_index_path: str = ""
        self.rvc_index_rate: float = 0.7
        self.rvc_filter_radius: int = 3
        self.rvc_resample_sr: int = 0
        self.rvc_rms_mix_rate: float = 0.5
        self.rvc_protect: float = 0.3
        self.rvc_auto_launch: bool = False
        self.rvc_launch_bat: str = ""
        self.rvc_health_timeout: int = 180
        self.rvc_auto_pitch: bool = True
        self.rvc_model_pitch_center: float = 300.0
        self.rvc_auto_pitch_max_hz: float = 1000.0
        self.rvc_auto_pitch_clamp: int = 5
        self.rvc_transpose_accompany: bool = True

        self._rvc_client = None
        self._last_applied_key: int = 0

        self._current_song: Optional[str] = None
        self._available_songs: List[str] = []

    def initialize(self, config: Dict[str, Any]) -> bool:
        try:
            self.output_base_dir = config.get("output_dir", "data/singing")
            self.volume_vocal = config.get("volume_vocal", 70)
            self.volume_accompany = config.get("volume_accompany", 70)
            self.learn_timeout = config.get("learn_timeout", 300)

            # 外部工具路径推导（换机器只需改 config/singing_config.json 的 paths 节）
            from .paths import expand_path, get_gpt_sovits_root, get_mdx_root, get_rvc_root, resolve_runtime_python

            self._rvc_root = get_rvc_root()
            self._sovits_root = get_gpt_sovits_root()
            self._mdx_root = get_mdx_root()
            self._mdx_python = resolve_runtime_python(self._mdx_root, "", "")
            self._mdx_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mdx_sep_cli.py")

            self.rvc_api_url = config.get("rvc_api_url", "http://127.0.0.1:7897").rstrip("/")
            self.rvc_model = config.get("rvc_model", "guanguanV1")
            self.rvc_f0_up_key = config.get("rvc_f0_up_key", 0)
            self.rvc_f0_method = config.get("rvc_f0_method", "rmvpe")
            self.rvc_index_path = expand_path(config.get("rvc_index_path", ""))
            self.rvc_index_rate = config.get("rvc_index_rate", 0.7)
            self.rvc_filter_radius = config.get("rvc_filter_radius", 3)
            self.rvc_resample_sr = config.get("rvc_resample_sr", 0)
            self.rvc_rms_mix_rate = config.get("rvc_rms_mix_rate", 0.5)
            self.rvc_protect = config.get("rvc_protect", 0.3)
            self.rvc_auto_pitch = config.get("rvc_auto_pitch", True)
            self.rvc_model_pitch_center = config.get("rvc_model_pitch_center", 300.0)
            self.rvc_auto_pitch_max_hz = config.get("rvc_auto_pitch_max_hz", 1000.0)
            self.rvc_auto_pitch_clamp = config.get("rvc_auto_pitch_clamp", 5)
            self.rvc_transpose_accompany = config.get("rvc_transpose_accompany", True)

            rvc_server_cfg = config.get("rvc_server", {})
            self.rvc_auto_launch = rvc_server_cfg.get("auto_launch", False)
            self.rvc_launch_bat = rvc_server_cfg.get("launch_bat", "")
            self.rvc_health_timeout = rvc_server_cfg.get("health_timeout", 180)

            if not self.rvc_launch_bat and self._rvc_root:
                self.rvc_launch_bat = os.path.join(self._rvc_root, "start_api.bat")

            self.separation_stages_enabled = config.get("separation_stages_enabled", False)
            self.separation_stages = [
                {**s, "model_path": expand_path(s.get("model_path", ""))}
                for s in (config.get("separation_stages") or [])
            ]

            eff = config.get("vocal_effects", {})
            self.effects_enabled = eff.get("enabled", True)
            self.effects_compressor_threshold = eff.get("compressor_threshold_db", -12.0)
            self.effects_compressor_ratio = eff.get("compressor_ratio", 2.5)
            self.effects_highpass_hz = eff.get("highpass_hz", 80.0)
            self.effects_highshelf_gain_db = eff.get("highshelf_gain_db", -1.5)
            self.effects_highshelf_freq_hz = eff.get("highshelf_freq_hz", 8000.0)
            self.effects_limiter_threshold_db = eff.get("limiter_threshold_db", -3.0)
            self.effects_gain_db = eff.get("gain_db", 2.0)
            self.effects_reverb_room = eff.get("reverb_room_size", 0.0)
            self.effects_reverb_wet = eff.get("reverb_wet_level", 0.0)

            self.mix_chord_enabled = config.get("mix_chord_enabled", True)
            self.mix_chord_volume = config.get("mix_chord_volume", 50)

            self.uvr5_python = resolve_runtime_python(
                self._sovits_root, config.get("uvr5_python", ""), sys.executable
            )
            self.uvr5_cli = config.get(
                "uvr5_cli",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "uvr5_cli.py"),
            )
            self.uvr5_device = config.get("uvr5_device", "cuda")
            self.uvr5_timeout = config.get("uvr5_timeout", 600)

            self.source_type = config.get("music_source", "auto")
            source_cfg = dict(config.get("source_config", {}) or {})
            if not source_cfg.get("bilibili_python") and self._rvc_root:
                source_cfg["bilibili_python"] = resolve_runtime_python(self._rvc_root, "", "")

            if self.source_type == "auto":
                from .music_source import AutoMusicSource

                self.music_source = AutoMusicSource()
            elif self.source_type == "netease":
                from .music_source import NeteaseMusicSource

                self.music_source = NeteaseMusicSource()
            elif self.source_type == "bilibili":
                from .music_source import BilibiliMusicSource

                self.music_source = BilibiliMusicSource()
            else:
                from .music_source import LocalFileSource

                self.music_source = LocalFileSource()

            if not self.music_source.initialize(source_cfg):
                logger.error("Builtin: music source init failed")
                return False

            if self.separation_stages_enabled and self.separation_stages:
                self.separator = None
                logger.info(f"Builtin: 多轮分离模式 ({len(self.separation_stages)} stages)")
            else:
                # 分离器回退链: GPT-SoVITS BS-Roformer → RVC 自带 HP5 → demucs → ffmpeg
                uvr5_models = config.get("uvr5_models")
                uvr5_provider = "sovits"
                if not uvr5_models and self._sovits_root:
                    wdir = os.path.join(self._sovits_root, "tools", "uvr5", "uvr5_weights")
                    uvr5_models = [
                        {
                            "type": "bs_roformer",
                            "path": os.path.join(wdir, "model_bs_roformer_ep_317_sdr_12.9755.ckpt"),
                        },
                        {"type": "vr", "path": os.path.join(wdir, "HP5_only_main_vocal.pth")},
                    ]
                if not uvr5_models and self._rvc_root:
                    uvr5_provider = "rvc"
                    uvr5_models = [
                        {
                            "type": "rvc_hp5",
                            "name": config.get("rvc_uvr5_model", "HP5_only_main_vocal"),
                            "path": "",
                        }
                    ]
                uvr5_cfg = {
                    k: config.get(k)
                    for k in (
                        "uvr5_python",
                        "uvr5_cli",
                        "uvr5_device",
                        "uvr5_timeout",
                    )
                    if config.get(k) is not None
                }
                uvr5_cfg["provider"] = uvr5_provider
                if uvr5_models:
                    uvr5_cfg["uvr5_models"] = uvr5_models
                if uvr5_provider == "rvc":
                    uvr5_cfg["uvr5_python"] = resolve_runtime_python(
                        self._rvc_root, config.get("uvr5_python", ""), sys.executable
                    )
                else:
                    uvr5_cfg["uvr5_python"] = self.uvr5_python

                demucs_python = resolve_runtime_python(
                    self._rvc_root, config.get("demucs_python", ""), sys.executable
                )
                demucs_cfg = {
                    "demucs_python": demucs_python,
                    "demucs_models": config.get("demucs_models", ["htdemucs_ft", "htdemucs"]),
                    "demucs_timeout": config.get("demucs_timeout", 300),
                }

                from .separator import DemucsSeparator, FFmpegSeparator, UVR5Separator

                self.separator = FFmpegSeparator()
                self.separator.initialize({})
                self._demucs_separator = None

                uvr5 = UVR5Separator(provider=uvr5_provider)
                if uvr5.initialize(uvr5_cfg):
                    self.separator = uvr5
                    if uvr5_provider == "rvc":
                        logger.info("Builtin: UVR5 分离器就绪 (RVC 自带 HP5)")
                    else:
                        logger.info("Builtin: UVR5 分离器就绪 (BS-Roformer, SDR 12.97)")
                else:
                    logger.info("Builtin: UVR5 不可用，回退 Demucs")

                demucs = DemucsSeparator()
                if demucs.initialize(demucs_cfg):
                    if self.separator.name == "ffmpeg":
                        self.separator = demucs
                    self._demucs_separator = demucs
                    logger.info("Builtin: Demucs 备用分离器就绪")

            os.makedirs(self.output_base_dir, exist_ok=True)
            self.is_initialized = True
            logger.info(
                f"BuiltinSingingEngine initialized: source={self.source_type} "
                f"rvc={self.rvc_api_url} model={self.rvc_model} "
                f"multi_stage={self.separation_stages_enabled} "
                f"effects={self.effects_enabled} chord_mix={self.mix_chord_enabled}"
            )
            return True
        except Exception as e:
            logger.error(f"BuiltinSingingEngine init failed: {e}")
            return False

    async def search_song(self, query: str) -> Optional[SongInfo]:
        if not self.music_source:
            return None
        result = await self.music_source.search(query)
        if result is None:
            return None
        return SongInfo(
            song_id=result.song_id,
            song_name=result.song_name,
            source=result.source,
        )

    async def get_available_songs(self) -> List[str]:
        return self._available_songs

    async def download_song_audio(self, song_name: str, output_dir: str) -> Optional[str]:
        """下载歌曲音频（给 workflow 用）"""
        if not self.music_source:
            return None
        result = await self.music_source.search(song_name)
        if result is None:
            return None
        return await self.music_source.download(result, output_dir)

    async def separate_vocals(self, audio_path: str, output_dir: str):
        """人声分离 → (vocal_path, instrumental_path)"""
        if not self.separator:
            return None, None
        return await self.separator.separate(audio_path, output_dir)

    async def _run_uvr5_stage(
        self, audio_path: str, output_dir: str, model_type: str, model_path: str
    ) -> Optional[dict]:
        """运行单个 UVR5 分离阶段，返回 {vocal_path, inst_path} 或 None"""
        import subprocess as _sp

        src_abs = os.path.abspath(audio_path)
        out_abs = os.path.abspath(output_dir)
        os.makedirs(out_abs, exist_ok=True)

        # 在 ASCII 临时目录工作 (GPT-SoVITS 旧版 soundfile 读不了中文路径)
        import tempfile as _tempfile

        work = _tempfile.mkdtemp(prefix="uvr5stage_")
        try:
            wav_input = os.path.join(work, "_input.wav")
            try:
                from .paths import find_ffmpeg

                _sp.run(
                    [
                        find_ffmpeg(),
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
                    logger.info(f"[UVR5 stage] WAV 预转换: {os.path.getsize(wav_input)}B")
            except Exception as e:
                logger.warning(f"[UVR5 stage] WAV 预转换跳过: {e}")

            if not os.path.exists(model_path):
                logger.warning(f"[UVR5 stage] 模型不存在: {model_path}")
                return None

            logger.info(f"[UVR5 stage] {model_type}: {os.path.basename(src_abs)}")
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _sp.run(
                        [
                            self.uvr5_python,
                            self.uvr5_cli,
                            src_abs,
                            work,
                            "--model-type",
                            model_type,
                            "--model-path",
                            model_path,
                            "--device",
                            self.uvr5_device,
                            "--sovits-root",
                            self._sovits_root or "",
                        ],
                        capture_output=True,
                        timeout=self.uvr5_timeout,
                        encoding="utf-8",
                        errors="replace",
                    ),
                )
            except (_sp.TimeoutExpired, Exception) as e:
                logger.warning(f"[UVR5 stage] error: {e}")
                return None

            if result.returncode != 0:
                logger.warning(f"[UVR5 stage] rc={result.returncode} stderr={result.stderr[-500:]}")
                return None

            work_vocal = os.path.join(work, "Vocals.wav")
            work_inst = os.path.join(work, "Instrumental.wav")

            if os.path.exists(work_vocal):
                vocal_out = os.path.join(out_abs, "Vocals.wav")
                inst_out = os.path.join(out_abs, "Instrumental.wav")
                shutil.move(work_vocal, vocal_out)
                if os.path.exists(work_inst):
                    shutil.move(work_inst, inst_out)
                logger.info(f"[UVR5 stage] OK [{model_type}]")
                return {"vocal_path": vocal_out, "inst_path": inst_out}

            logger.warning(f"[UVR5 stage] no output: {model_type}")
            return None
        finally:
            shutil.rmtree(work, ignore_errors=True)

    async def _run_mdx_stage(self, audio_path: str, output_dir: str, model_path: str) -> Optional[dict]:
        """运行单个 MDX 分离阶段 (audio_separator + onnx, 参考项目式)

        返回 {vocal_path, inst_path} 或 None
        """
        import subprocess as _sp

        if not self._mdx_python or not os.path.exists(self._mdx_python):
            logger.warning("[MDX stage] 参考项目 runtime 不可用 (paths.mdx_root 未配置)")
            return None
        if not os.path.exists(model_path):
            logger.warning(f"[MDX stage] 模型不存在: {model_path}")
            return None

        src_abs = os.path.abspath(audio_path)
        out_abs = os.path.abspath(output_dir)
        os.makedirs(out_abs, exist_ok=True)

        logger.info(f"[MDX stage] {os.path.basename(model_path)}: {os.path.basename(src_abs)}")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _sp.run(
                    [
                        self._mdx_python,
                        self._mdx_cli,
                        src_abs,
                        out_abs,
                        "--model-file",
                        model_path,
                    ],
                    capture_output=True,
                    timeout=self.uvr5_timeout,
                    encoding="utf-8",
                    errors="replace",
                ),
            )
        except (_sp.TimeoutExpired, Exception) as e:
            logger.warning(f"[MDX stage] error: {e}")
            return None

        if result.returncode != 0:
            logger.warning(f"[MDX stage] rc={result.returncode} stderr={result.stderr[-500:]}")
            return None

        vocal_out = os.path.join(out_abs, "Vocals.wav")
        inst_out = os.path.join(out_abs, "Instrumental.wav")
        if os.path.exists(vocal_out):
            logger.info(f"[MDX stage] OK [{os.path.basename(model_path)}] stdout={result.stdout.strip()}")
            return {"vocal_path": vocal_out, "inst_path": inst_out}

        logger.warning(f"[MDX stage] no output: {os.path.basename(model_path)}")
        return None

    async def _multi_stage_separate(self, audio_path: str, output_dir: str) -> Optional[dict]:
        """多轮人声分离流水线：
        Stage 0: BS-Roformer → Vocals + Instrumental(backing)
        Stage 1: VR 和声提取 → Clean Vocals + Chord(harmony)
        Stage 2: VR 去混响  → Final Vocals + Echo(reverb)
        返回 {vocal_path, accompany_path, chord_path, echo_path} 或 None
        """
        stages_output = []
        current_input = audio_path

        for idx, stage in enumerate(self.separation_stages):
            stage_dir = os.path.join(output_dir, f"_stage{idx}")
            stage_type = stage.get("model_type", "bs_roformer")
            stage_path = stage.get("model_path", "")

            if stage_type == "mdx":
                result = await self._run_mdx_stage(current_input, stage_dir, stage_path)
            else:
                result = await self._run_uvr5_stage(current_input, stage_dir, stage_type, stage_path)
            if result is None:
                logger.error(f"[多轮分离] Stage {idx} ({stage_type}) 失败")
                return None

            stages_output.append(result)
            current_input = result["vocal_path"]
            logger.info(f"[多轮分离] Stage {idx} ({stage_type}) 完成: vocal={os.path.getsize(result['vocal_path'])}B")

        final_idx = len(stages_output) - 1

        final_vocal = os.path.join(output_dir, "Vocals.wav")
        shutil.move(stages_output[final_idx]["vocal_path"], final_vocal)

        accompany_path = os.path.join(output_dir, "Instrumental.wav")
        shutil.move(stages_output[0]["inst_path"], accompany_path)

        chord_path = None
        if final_idx >= 1:
            # 和声轨 = 从人声流中最后剥离的成分
            # 2 阶段 (人声→和声提取): 取 Stage1 的 inst (和声)
            # 3 阶段 (人声→和声→去混响): 取 Stage1 的 inst (和声, Stage2 inst 是混响残响)
            chord_src_idx = final_idx - 1 if final_idx >= 2 else final_idx
            chord_path = os.path.join(output_dir, "Chord.wav")
            shutil.move(stages_output[chord_src_idx]["inst_path"], chord_path)
            logger.info(f"[多轮分离] 和声轨: Chord.wav ({os.path.getsize(chord_path)}B)")

        echo_path = None
        if final_idx >= 2:
            echo_path = os.path.join(output_dir, "Echo.wav")
            shutil.move(stages_output[final_idx]["inst_path"], echo_path)
            logger.info(f"[多轮分离] 混响轨: Echo.wav ({os.path.getsize(echo_path)}B)")

        for idx in range(len(self.separation_stages)):
            stage_dir = os.path.join(output_dir, f"_stage{idx}")
            shutil.rmtree(stage_dir, ignore_errors=True)

        return {
            "vocal_path": final_vocal,
            "accompany_path": accompany_path,
            "chord_path": chord_path,
            "echo_path": echo_path,
        }

    def _apply_vocal_effects(self, vocal_path: str, output_dir: str) -> Optional[str]:
        """人声后处理 — 高音保护链: HPF → Compressor → HighShelf衰减 → Limiter → Gain → (可选)Reverb

        优先使用 pedalboard，回退到 numpy + scipy 实现
        """
        import numpy as np

        if not os.path.exists(vocal_path):
            return None

        out_path = os.path.join(output_dir, "Vocals_processed.wav")

        try:
            import soundfile as sf

            data, sr = sf.read(vocal_path, dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)
        except Exception as e:
            logger.warning(f"[效果] 读取失败: {e}")
            return vocal_path

        try:
            import pedalboard
            from pedalboard import Compressor, Gain, HighShelfFilter, HighpassFilter, Limiter, Reverb

            input_peak = float(np.max(np.abs(data))) if len(data) else 0.0
            effects = [HighpassFilter(cutoff_frequency_hz=self.effects_highpass_hz)]
            effects.append(
                Compressor(
                    threshold_db=self.effects_compressor_threshold,
                    ratio=self.effects_compressor_ratio,
                    attack_ms=5,
                    release_ms=150,
                )
            )
            # 高架滤波仅在配置了非零增益时启用 (0dB 时不插入, 保留高频细节)
            if abs(self.effects_highshelf_gain_db) > 0.05:
                effects.append(
                    HighShelfFilter(
                        cutoff_frequency_hz=self.effects_highshelf_freq_hz,
                        gain_db=self.effects_highshelf_gain_db,
                    )
                )
            # 自适应限幅: 仅当输入峰值超过阈值时才启用, 避免正常人声被压扁
            limiter_threshold_linear = 10 ** (self.effects_limiter_threshold_db / 20)
            if input_peak > limiter_threshold_linear:
                effects.append(
                    Limiter(threshold_db=self.effects_limiter_threshold_db, release_ms=150)
                )
            if abs(self.effects_gain_db) > 0.05:
                effects.append(Gain(gain_db=self.effects_gain_db))
            if self.effects_reverb_wet > 0:
                effects.append(
                    Reverb(
                        room_size=self.effects_reverb_room,
                        damping=0.5,
                        wet_level=self.effects_reverb_wet,
                        dry_level=1.0 - self.effects_reverb_wet,
                        width=0.66,
                    )
                )
            board = pedalboard.Pedalboard(effects)
            data = data.T if data.ndim > 1 and data.shape[1] > 1 else data.flatten()
            effected = board(data, sr)
            effected = effected.reshape(-1, 1) if effected.ndim == 1 else effected.T

            peak = np.max(np.abs(effected))
            if peak > 0.98:
                effected = np.clip(effected / peak * 0.98, -1.0, 1.0)

            sf.write(out_path, effected, sr, subtype="PCM_16")
            chain = (
                f"HPF({self.effects_highpass_hz:.0f}Hz)"
                f"→Comp({self.effects_compressor_threshold:.0f}dB,{self.effects_compressor_ratio}:1)"
            )
            if abs(self.effects_highshelf_gain_db) > 0.05:
                chain += f"→Shelf({self.effects_highshelf_gain_db:+.1f}dB@{self.effects_highshelf_freq_hz:.0f}Hz)"
            chain += f"→Limit({self.effects_limiter_threshold_db:.0f}dB)" if input_peak > limiter_threshold_linear else ""
            chain += f"→Gain(+{self.effects_gain_db:.0f}dB)" if abs(self.effects_gain_db) > 0.05 else ""
            chain += "→Reverb" if self.effects_reverb_wet > 0 else ""
            logger.info(f"[效果] pedalboard: {chain} (input_peak={input_peak:.3f})")
            return out_path

        except ImportError:
            logger.info("[效果] pedalboard 不可用，使用 numpy/scipy 回退")

        try:
            data, sr = sf.read(vocal_path, dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            _numpy_compressor(data, self.effects_compressor_threshold, self.effects_compressor_ratio)

            try:
                from scipy.signal import butter, sosfilt

                nyq = sr / 2
                cutoff = self.effects_highpass_hz / nyq
                if 0 < cutoff < 1:
                    sos = butter(4, cutoff, btype="high", output="sos")
                    data = sosfilt(sos, data, axis=0)
                    logger.info(f"[效果] HPF {self.effects_highpass_hz}Hz (scipy)")
            except ImportError:
                logger.warning("[效果] scipy 不可用，跳过 HPF")

            gain_linear = 10 ** (self.effects_gain_db / 20)
            data = data * gain_linear

            if self.effects_reverb_wet > 0:
                data = _numpy_reverb(data, sr, self.effects_reverb_room, self.effects_reverb_wet)

            peak = np.max(np.abs(data))
            if peak > 0.95:
                data = _soft_clip(data, 0.95)
                logger.info(f"[效果] soft-clip 限幅 (peak={peak:.3f})")

            sf.write(out_path, data, sr, subtype="PCM_16")
            logger.info(
                f"[效果] numpy: Comp→HPF({self.effects_highpass_hz}Hz)"
                f"→Gain(+{self.effects_gain_db}dB)→SoftClip"
                f"{'→Reverb' if self.effects_reverb_wet > 0 else ''}"
            )
            return out_path
        except Exception as e:
            logger.warning(f"[效果] numpy 回退失败: {e}")
            return vocal_path

    async def _normalize_vocal(self, vocal_path: str) -> Optional[str]:
        """人声归一化到 -6dB + 立体声→单声道，输出 16-bit PCM WAV

        Demucs 输出的立体声两通道存在微小时延差，不能用 np.mean() 取均值
        (会导致相位抵消/梳状滤波)，而应取左通道。RVC HuBERT 只需单声道输入。
        """
        import numpy as np

        if not os.path.exists(vocal_path):
            return None

        try:
            import soundfile as sf

            data, sr = sf.read(vocal_path, dtype="float32")
            orig_channels = 1
            if data.ndim > 1 and data.shape[1] > 1:
                orig_channels = data.shape[1]
                data = data[:, 0:1]
                logger.info(f"[归一化] 立体声→单声道: 取左通道 ({orig_channels}ch→1ch)")

            data = data.reshape(-1, 1) if data.ndim == 1 else data

            peak = float(np.max(np.abs(data)))
            if peak <= 0:
                return vocal_path

            target_peak = 0.5
            out_path = vocal_path.replace(".wav", "_norm.wav")

            if peak > target_peak:
                gain = target_peak / peak
                data = np.clip(data * gain, -1.0, 1.0)
                logger.info(f"[归一化] 衰减 peak {peak:.4f} → {target_peak:.4f} (x{gain:.2f})")
            elif peak > target_peak * 0.9:
                logger.info(f"[归一化] 已够响亮 peak={peak:.4f}")
            else:
                gain = target_peak / peak
                data = np.clip(data * gain, -1.0, 1.0)
                logger.info(f"[归一化] 提升 peak {peak:.4f} → {target_peak:.4f} (x{gain:.1f})")

            sf.write(out_path, data, sr, subtype="PCM_16")
            return out_path
        except Exception as e:
            logger.warning(f"[归一化] 失败: {e}")
            return vocal_path

    def _check_vocal_quality(self, vocal_path: str, source_path: str, inst_path: Optional[str]) -> Optional[str]:
        """检测人声分离质量，太弱时用原始音频替代"""
        import numpy as np

        try:
            import soundfile as sf

            data, _sr = sf.read(vocal_path, frames=48000 * 5, dtype="float32")
            peak = float(np.max(np.abs(data)))

            if peak >= 0.03:
                return vocal_path

            logger.warning(f"[质量] demucs 人声过弱 peak={peak:.4f}, 回退全曲模式")

            full_vocal = os.path.join(os.path.dirname(vocal_path), "Vocals_full.wav")
            if not os.path.exists(full_vocal):
                import subprocess

                from .separator import _find_ffmpeg

                subprocess.run(
                    [_find_ffmpeg(), "-y", "-i", source_path, "-ac", "1", full_vocal],
                    capture_output=True,
                    timeout=60,
                )

            if os.path.exists(full_vocal) and os.path.getsize(full_vocal) > 0:
                logger.info(f"[质量] 全曲 WAV 已生成: {full_vocal}")
                return full_vocal

            logger.warning("[质量] ffmpeg 转换失败，用原始人声")
            return vocal_path
        except Exception as e:
            logger.warning(f"[质量] 检测失败: {e}")
            return vocal_path

    def _get_rvc_client(self):
        """懒创建 RVC Gradio 客户端（复用已加载模型，避免重复加载）"""
        if self._rvc_client is None:
            from .rvc_client import RVCGradioClient

            self._rvc_client = RVCGradioClient(
                api_url=self.rvc_api_url,
                model=self.rvc_model,
                f0_up_key=self.rvc_f0_up_key,
                f0_method=self.rvc_f0_method,
                index_path=self.rvc_index_path,
                index_rate=self.rvc_index_rate,
                filter_radius=self.rvc_filter_radius,
                resample_sr=self.rvc_resample_sr,
                rms_mix_rate=self.rvc_rms_mix_rate,
                protect=self.rvc_protect,
                auto_launch=self.rvc_auto_launch,
                launch_bat=self.rvc_launch_bat,
                health_timeout=self.rvc_health_timeout,
                auto_pitch=self.rvc_auto_pitch,
                model_pitch_center=self.rvc_model_pitch_center,
                auto_pitch_max_hz=self.rvc_auto_pitch_max_hz,
                auto_pitch_clamp=self.rvc_auto_pitch_clamp,
            )
        return self._rvc_client

    def _rvc_cache_fingerprint(self, vocal_path: str) -> dict:
        """RVC 转换参数指纹 — 任一项变化即视为缓存失效，需重新转换

        注意: 不含 applied_key (变调值由声源内容决定, 同一指纹下必然相同);
        applied_key 随指纹一起落盘供伴奏移调使用。
        """
        import json

        return {
            "rvc_model": self.rvc_model,
            "f0_up_key": self.rvc_f0_up_key,
            "f0_method": self.rvc_f0_method,
            "index_path": self.rvc_index_path,
            "index_rate": self.rvc_index_rate,
            "filter_radius": self.rvc_filter_radius,
            "resample_sr": self.rvc_resample_sr,
            "rms_mix_rate": self.rvc_rms_mix_rate,
            "protect": self.rvc_protect,
            "auto_pitch": self.rvc_auto_pitch,
            "model_pitch_center": self.rvc_model_pitch_center,
            "auto_pitch_max_hz": self.rvc_auto_pitch_max_hz,
            "auto_pitch_clamp": self.rvc_auto_pitch_clamp,
            "src_mtime": os.path.getmtime(vocal_path),
        }

    def _params_file(self, output_dir: str) -> str:
        return os.path.join(output_dir, f"Vocals_{self.rvc_model}.wav.params.json")

    def _read_applied_key(self, output_dir: str) -> int:
        """读取缓存指纹里的实际变调值 (旧缓存无此字段返回 0)"""
        import json

        try:
            with open(self._params_file(output_dir), "r", encoding="utf-8") as f:
                return int(json.load(f).get("applied_key", 0) or 0)
        except Exception:
            return 0

    def is_conversion_current(self, output_dir: str) -> bool:
        """当前换声产物是否仍与配置+声源匹配 (供缓存命中路径校验)"""
        import json

        converted = os.path.join(output_dir, f"Vocals_{self.rvc_model}.wav")
        fp_file = self._params_file(output_dir)
        if not (os.path.exists(converted) and os.path.exists(fp_file)):
            return False
        try:
            with open(fp_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached.pop("applied_key", None)
        except Exception:
            return False
        for cand in (
            os.path.join(output_dir, "Vocals_norm.wav"),
            os.path.join(output_dir, "Vocals.wav"),
        ):
            if os.path.exists(cand):
                return cached == self._rvc_cache_fingerprint(cand)
        return False

    def get_cached_song_tracks(self, output_dir: str):
        """缓存命中路径取轨: (converted, accompany, chord) — 无效/缺失返回 None

        自动变调时伴奏/和声轨已按同一半音数移调 (Instrumental_T{key}.wav)。
        """
        converted = os.path.join(output_dir, f"Vocals_{self.rvc_model}.wav")
        inst = os.path.join(output_dir, "Instrumental.wav")
        if not (os.path.exists(converted) and os.path.exists(inst)):
            return None
        if not self.is_conversion_current(output_dir):
            return None
        key = self._read_applied_key(output_dir)
        if key != 0:
            t_inst = os.path.join(output_dir, f"Instrumental_T{key:+d}.wav")
            if os.path.exists(t_inst):
                inst = t_inst
        chord = os.path.join(output_dir, "Chord.wav")
        if not os.path.exists(chord):
            chord = os.path.join(output_dir, "Harmony.wav")
        if key != 0 and os.path.exists(chord):
            t_chord = os.path.join(output_dir, f"Chord_T{key:+d}.wav")
            if os.path.exists(t_chord):
                chord = t_chord
        if not os.path.exists(chord):
            chord = ""
        return converted, inst, chord

    async def convert_voice(self, vocal_path: str, output_dir: str) -> Optional[str]:
        """RVC 语音转换 — Gradio API (infer_change_voice + infer_convert)

        缓存校验: 转换参数或输入人声变化时自动重新转换。
        成功/命中缓存后 self._last_applied_key 为本次实际变调半音数。
        """
        if not os.path.exists(vocal_path):
            return None

        output_path = os.path.join(output_dir, f"Vocals_{self.rvc_model}.wav")
        fp_file = output_path + ".params.json"
        if os.path.exists(output_path) and os.path.exists(fp_file):
            try:
                import json

                with open(fp_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                applied_key = int(cached.get("applied_key", 0) or 0)
                cached.pop("applied_key", None)
                if cached == self._rvc_cache_fingerprint(vocal_path):
                    self._last_applied_key = applied_key
                    logger.info(f"[RVC] cached: {output_path} (key={applied_key:+d})")
                    return output_path
            except Exception:
                pass

        client = self._get_rvc_client()
        ok, applied_key = await asyncio.get_event_loop().run_in_executor(
            None, client.convert_ex, vocal_path, output_path
        )
        if ok:
            try:
                import json

                with open(fp_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {**self._rvc_cache_fingerprint(vocal_path), "applied_key": applied_key},
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except Exception as e:
                logger.warning(f"[RVC] 缓存指纹写入失败: {e}")
            self._last_applied_key = applied_key
            return output_path
        logger.error(f"[RVC] 换声失败: model={self.rvc_model} url={self.rvc_api_url}")
        return None

    def _transpose_accompany(self, src_path: str, output_dir: str, key: int) -> Optional[str]:
        """伴奏/和声轨整曲移调 (与人声同一半音数, 保持人声伴奏同调)

        ffmpeg asetrate→aresample→atempo 组合: 先变速变调再恢复时长,
        旋律音程整体平移、时长不变。移调失败时回退原始轨 (宁可不移调也不无伴奏)。
        """
        import subprocess

        if not src_path or not os.path.exists(src_path):
            return src_path
        factor = 2 ** (key / 12)
        base = os.path.splitext(os.path.basename(src_path))[0]
        dst = os.path.join(output_dir, f"{base}_T{key:+d}.wav")
        if os.path.exists(dst):
            logger.info(f"[变调] 伴奏移调已存在: {os.path.basename(dst)}")
            return dst

        af = (
            "aresample=44100,"
            f"asetrate=44100*{factor:.6f},"
            "aresample=44100,"
            f"atempo={1 / factor:.6f}"
        )
        from .paths import find_ffmpeg

        try:
            result = subprocess.run(
                [
                    find_ffmpeg(),
                    "-y",
                    "-i",
                    os.path.abspath(src_path),
                    "-af",
                    af,
                    "-ar",
                    "44100",
                    dst,
                ],
                capture_output=True,
                timeout=180,
            )
            if result.returncode != 0 or not os.path.exists(dst):
                logger.warning(f"[变调] 伴奏移调失败 rc={result.returncode}: {os.path.basename(src_path)}")
                return src_path
            logger.info(f"[变调] 伴奏移调 {key:+d} 半音: {os.path.basename(dst)}")
            return dst
        except Exception as e:
            logger.warning(f"[变调] 伴奏移调异常 ({e}), 回退原始轨")
            return src_path

    async def request_learn(self, song_name: str) -> LearnTask:
        """发起学唱 — 实际由 workflow 的 _learn_and_download 处理"""
        return LearnTask(song_name=song_name, status=LearnStatus.WAITING)

    async def get_learn_status(self, song_name: str) -> LearnStatus:
        output_dir = os.path.join(self.output_base_dir, song_name)
        vocal = os.path.join(output_dir, "Vocals.wav")
        inst = os.path.join(output_dir, "Instrumental.wav")
        if os.path.exists(vocal) or os.path.exists(inst):
            return LearnStatus.PROCESSED
        return LearnStatus.PROCESSING

    async def download_vocal(self, song_name: str, output_dir: str) -> Optional[str]:
        path = os.path.join(output_dir, f"Vocals_{self.rvc_model}.wav")
        return path if os.path.exists(path) else None

    async def download_accompany(self, song_name: str, output_dir: str) -> Optional[str]:
        path = os.path.join(output_dir, "Instrumental.wav")
        return path if os.path.exists(path) else None

    async def download_origin(self, song_name: str, output_dir: str) -> Optional[str]:
        return None

    async def download_mix(self, song_name: str, output_dir: str) -> Optional[str]:
        return None

    async def process_full_pipeline(self, song_name: str, output_dir: str) -> Optional[dict]:
        """完整唱歌管线：下载 → 多轮分离 → 归一化 → 换声 → 效果 → 返回路径

        Returns dict with vocal_path, accompany_path, chord_path, output_dir or None
        """
        logger.info(f"[Builtin] 全流程开始: {song_name}")

        os.makedirs(output_dir, exist_ok=True)

        # 断点续传：已有分离产物时跳过下载与分离
        cached_vocal = os.path.join(output_dir, "Vocals.wav")
        cached_inst = os.path.join(output_dir, "Instrumental.wav")
        cached_chord = os.path.join(output_dir, "Chord.wav")
        if not os.path.exists(cached_chord):
            cached_chord = os.path.join(output_dir, "Harmony.wav")

        if os.path.exists(cached_vocal) and os.path.getsize(cached_vocal) > 0:
            vocal_path = cached_vocal
            inst_path = cached_inst if os.path.exists(cached_inst) else ""
            chord_path = cached_chord if os.path.exists(cached_chord) else None
            audio_path = cached_vocal  # fallback 质量检查用
            logger.info(f"[Builtin] 复用已有分离产物: vocal={vocal_path} inst={inst_path or '(无)'}")
        else:
            audio_path = await self.download_song_audio(song_name, output_dir)
            if not audio_path:
                logger.error(f"[Builtin] 下载失败: {song_name}")
                return None
            logger.info(f"[Builtin] 音频下载完成: {audio_path}")

            if self.separation_stages_enabled and self.separation_stages:
                sep_result = await self._multi_stage_separate(audio_path, output_dir)
                if sep_result is None:
                    logger.warning("[Builtin] 多轮分离失败，回退到传统分离")
                    vocal_path, inst_path = await self.separate_vocals(audio_path, output_dir)
                    chord_path = None
                else:
                    vocal_path = sep_result["vocal_path"]
                    inst_path = sep_result["accompany_path"]
                    chord_path = sep_result.get("chord_path")
                    logger.info(f"[Builtin] 多轮分离完成: vocal={vocal_path}, inst={inst_path}, chord={chord_path}")
            else:
                vocal_path, inst_path = await self.separate_vocals(audio_path, output_dir)
                chord_path = None

                if not vocal_path and self._demucs_separator:
                    logger.info("[Builtin] UVR5 分离失败，回退 Demucs...")
                    vocal_path, inst_path = await self._demucs_separator.separate(audio_path, output_dir)

                if not vocal_path:
                    from .separator import _ffmpeg_fallback

                    vocal_path, inst_path = await _ffmpeg_fallback(audio_path, output_dir)
                    if not vocal_path:
                        logger.error(f"[Builtin] 分离失败: {song_name}")
                        return None
                logger.info(f"[Builtin] 人声分离完成: vocal={vocal_path}, inst={inst_path}")

        fallback_marker = os.path.join(output_dir, "_fallback.marker")
        if os.path.exists(fallback_marker):
            logger.warning("[Builtin] 分离降级，跳过 RVC 直接播放原曲")
            vocal_path = self._check_vocal_quality(vocal_path, audio_path, inst_path)
            if not vocal_path:
                return None
            return {
                "vocal_path": vocal_path,
                "accompany_path": inst_path or "",
                "output_dir": output_dir,
                "skip_rvc": True,
            }

        vocal_path = await self._normalize_vocal(vocal_path)
        if not vocal_path:
            logger.error(f"[Builtin] 人声归一化失败: {song_name}")
            return None

        converted = await self.convert_voice(vocal_path, output_dir)
        if not converted:
            logger.error(f"[Builtin] RVC 换声失败: {song_name}")
            return None
        logger.info(f"[Builtin] 换声完成: {converted}")

        # 整曲一致变调: 人声被 RVC 移调后, 伴奏/和声轨必须同步移调,
        # 否则人声与伴奏不在一个调上 (整首跑调)。
        applied_key = self._last_applied_key
        if self.rvc_transpose_accompany and applied_key != 0:
            inst_path = self._transpose_accompany(inst_path, output_dir, applied_key)
            if chord_path:
                chord_path = self._transpose_accompany(chord_path, output_dir, applied_key)
            logger.info(
                f"[Builtin] 整曲一致变调: 人声与伴奏同步 {applied_key:+d} 半音 "
                f"(accompany={os.path.basename(inst_path or '')})"
            )

        # 换声/变调参数变化 → 旧混音成品作废, 播放时按新轨重新混音
        for f in os.listdir(output_dir):
            if f.endswith("_mix.wav"):
                try:
                    os.remove(os.path.join(output_dir, f))
                    logger.info(f"[Builtin] 旧混音已作废: {f}")
                except OSError:
                    pass

        if self.effects_enabled:
            processed = self._apply_vocal_effects(converted, output_dir)
            if processed:
                converted = processed
                logger.info(f"[Builtin] 效果处理完成: {converted}")

        result = {
            "vocal_path": converted,
            "accompany_path": inst_path or "",
            "output_dir": output_dir,
        }

        if self.mix_chord_enabled and chord_path and os.path.exists(chord_path):
            result["chord_path"] = chord_path

        return result

    def cleanup(self):
        if self._rvc_client is not None:
            try:
                self._rvc_client.close()
            except Exception as e:
                logger.warning(f"[RVC] client close failed: {e}")
            self._rvc_client = None
        if self.music_source:
            self.music_source.cleanup()
        if self.separator:
            self.separator.cleanup()
        self.is_initialized = False


def _numpy_compressor(data: "np.ndarray", threshold_db: float, ratio: float):
    """简易下行压缩器 — 对超过阈值的信号按 ratio 衰减"""
    import numpy as np

    threshold_linear = 10 ** (threshold_db / 20) * 0.7
    mask = np.abs(data) > threshold_linear
    if np.any(mask):
        excess = np.abs(data[mask]) - threshold_linear
        attenuated = excess / ratio
        sign = np.sign(data[mask])
        data[mask] = sign * (threshold_linear + attenuated)


def _soft_clip(data: "np.ndarray", threshold: float = 0.95) -> "np.ndarray":
    """tanh 软限幅 — 平滑压缩峰值，避免硬削波带来的高频失真/爆音"""
    import numpy as np

    return threshold * np.tanh(data / max(threshold, 1e-6))


def _numpy_reverb(data: "np.ndarray", sr: int, room_size: float, wet_level: float) -> "np.ndarray":
    """简易卷积混响 — 指数衰减噪声脉冲响应 (FFT 加速)"""
    import numpy as np

    ir_duration = room_size * 3.0 + 0.3
    ir_len = int(sr * ir_duration)
    t = np.arange(ir_len) / sr
    decay = np.exp(-t / (room_size * 2.0 + 0.15))
    ir = np.random.randn(ir_len).astype(np.float32) * decay
    ir = ir / (np.max(np.abs(ir)) + 1e-8) * 0.6

    dry_level = 1.0 - wet_level
    output = np.zeros_like(data, dtype=np.float32)

    try:
        from scipy.signal import oaconvolve

        _conv = oaconvolve
    except ImportError:
        try:
            from scipy.signal import fftconvolve

            _conv = fftconvolve
        except ImportError:
            _conv = np.convolve

    if data.ndim == 2:
        for ch in range(data.shape[1]):
            conv = _conv(data[:, ch], ir, mode="full")
            conv = conv[: len(data)]
            output[:, ch] = dry_level * data[:, ch] + wet_level * conv
    else:
        conv = _conv(data, ir, mode="full")
        conv = conv[: len(data)]
        output = dry_level * data + wet_level * conv

    peak = np.max(np.abs(output))
    if peak > 0.0:
        output = output / peak * 0.95

    return output
