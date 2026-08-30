"""
RVC (Retrieval-based Voice Conversion) Gradio API 客户端

对接 RVC WebUI (infer-web.py) 的 Gradio API 端点：
  POST /run/infer_change_voice  → 加载/切换声线模型 (vc.get_vc)
  POST /run/infer_convert       → 单文件声线转换 (vc.vc_single)

协议参数顺序与 infer-web.py 中 but0.click(vc.vc_single, [...], api_name="infer_convert") 一致：
  [spk_item, input_audio, f0_up_key, f0_file, f0_method,
   file_index1, file_index2, index_rate, filter_radius,
   resample_sr, rms_mix_rate, protect]

本机 RVC 整合包由 start_api.bat 启动（默认端口 7897）。
"""

import base64
import logging
import os
import shutil
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RVCGradioClient:
    """RVC Gradio API 客户端 — 健康检查 / 模型加载 / 声线转换 / 可选自动拉起服务"""

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:7897",
        model: str = "",
        f0_up_key: int = 0,
        f0_method: str = "rmvpe",
        index_path: str = "",
        index_rate: float = 0.7,
        filter_radius: int = 3,
        resample_sr: int = 0,
        rms_mix_rate: float = 0.5,
        protect: float = 0.3,
        auto_launch: bool = False,
        launch_bat: str = "",
        health_timeout: int = 180,
        auto_pitch: bool = False,
        model_pitch_center: float = 300.0,
        auto_pitch_max_hz: float = 880.0,
        auto_pitch_clamp: int = 5,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.f0_up_key = f0_up_key
        self.f0_method = f0_method
        self.index_path = index_path
        self.index_rate = index_rate
        self.filter_radius = filter_radius
        self.resample_sr = resample_sr
        self.rms_mix_rate = rms_mix_rate
        self.protect = protect
        self.auto_launch = auto_launch
        self.launch_bat = launch_bat
        self.health_timeout = health_timeout
        self.auto_pitch = auto_pitch
        self.model_pitch_center = model_pitch_center
        self.auto_pitch_max_hz = auto_pitch_max_hz
        self.auto_pitch_clamp = max(0, int(auto_pitch_clamp))

        self._proc: Optional[subprocess.Popen] = None
        self._loaded_model: Optional[str] = None
        self._need_load = True
        self._launch_attempted = False
        self.last_f0_key: int = 0  # 最近一次转换实际应用的变调半音数 (含自动变调+音域保护)

    # ------------------------------------------------------------------ utils

    def _model_file(self, model: str) -> str:
        """配置模型名可能省略 .pth 后缀，补齐（get_vc 用 weight_root/{sid} 拼路径）"""
        model = (model or "").strip().strip('"')
        if model and not model.lower().endswith(".pth"):
            model += ".pth"
        return model

    def _requests(self):
        import requests

        return requests

    def _post_json(self, path: str, payload: dict, timeout: int):
        requests = self._requests()
        url = f"{self.api_url}{path}"
        resp = requests.post(url, json=payload, timeout=(10, timeout))
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ server

    def health_check(self, timeout: float = 5.0) -> bool:
        """GET / 返回 200 即认为 Gradio 服务可用"""
        requests = self._requests()
        try:
            resp = requests.get(f"{self.api_url}/", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def ensure_server(self) -> bool:
        """确保 RVC 服务在线：健康检查失败时（且开启 auto_launch）自动拉起 start_api.bat"""
        if self.health_check():
            return True

        if not self.auto_launch or self._launch_attempted:
            logger.warning(
                f"[RVC] 服务不可达: {self.api_url} "
                f"(请启动 RVC WebUI: start_api.bat, 或开启 auto_launch)"
            )
            return False

        self._launch_attempted = True
        if not self.launch_bat or not os.path.exists(self.launch_bat):
            logger.warning(f"[RVC] 自动启动脚本不存在: {self.launch_bat}")
            return False

        logger.info(f"[RVC] 服务未启动，自动拉起: {self.launch_bat}")
        cwd = os.path.dirname(os.path.abspath(self.launch_bat))
        try:
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self._proc = subprocess.Popen(
                ["cmd", "/c", self.launch_bat],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception as e:
            logger.error(f"[RVC] 启动失败: {e}")
            return False

        deadline = time.time() + max(self.health_timeout, 10)
        while time.time() < deadline:
            if self.health_check():
                self._need_load = True
                logger.info(f"[RVC] 服务已就绪: {self.api_url}")
                return True
            time.sleep(3)

        logger.error(f"[RVC] 服务启动超时 ({self.health_timeout}s): {self.api_url}")
        return False

    # ------------------------------------------------------------------ voice

    @staticmethod
    def _estimate_average_pitch(input_path: str, max_seconds: int = 30) -> Optional[float]:
        """自相关法估计音频平均基频 (Hz)，用于自动变调判断

        从歌曲中段 (人声密集区) 采样，搜索范围 60-600Hz。
        返回 None 表示无法估计。
        """
        try:
            import numpy as np
            import soundfile as sf

            info = sf.info(input_path)
            sr = info.samplerate
            total_sec = info.frames / sr if sr else 0
            if total_sec <= 0:
                return None
            offset = min(max(total_sec * 0.4, 0.0), max(total_sec - max_seconds, 0.0))
            data, sr = sf.read(
                input_path,
                dtype="float32",
                start=int(offset * sr),
                frames=int(max_seconds * sr),
            )
            if data.ndim > 1:
                data = data[:, 0]
            if len(data) < sr:  # 不足 1 秒
                return None

            target_sr = 8000
            if sr != target_sr:
                n = int(len(data) * target_sr / sr)
                data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data)
                sr = target_sr

            frame = int(sr * 0.03)
            hop = max(frame // 2, 1)
            min_lag = int(sr / 600)  # 对应 600Hz
            max_lag = int(sr / 60)  # 对应 60Hz
            pitches = []
            window = np.hanning(frame)
            for st in range(0, len(data) - frame, hop):
                seg = data[st : st + frame] * window
                seg = seg - seg.mean()
                if np.abs(seg).max() < 0.02:  # 静音帧跳过
                    continue
                ac = np.correlate(seg, seg, "full")[frame - 1 :]
                if len(ac) <= max_lag:
                    continue
                region = ac[min_lag:max_lag]
                if len(region) < 10:
                    continue
                lag = min_lag + int(np.argmax(region))
                f0 = sr / lag
                if 60 <= f0 <= 600:
                    pitches.append(f0)
            if not pitches:
                return None
            return float(np.median(pitches))
        except Exception as e:
            logger.warning(f"[RVC] 基频估计失败: {e}")
            return None

    def _resolve_f0_up_key(self, input_path: str) -> int:
        """计算最终变调值 — 任意声源自动适配模型音域

        1. 自动变调: key = round(12 * log2(model_pitch_center / 源平均基频))
           被 clamp 在 ±auto_pitch_clamp 半音内 — RVC 大跨度变调 (>±6 半音)
           音色劣化明显，宁可少升少降也不硬顶。
           例: 男声源 190Hz + 模型音域中心 300Hz → 原始值 +8, clamp 后 +5
        2. 整曲音域保护 (见 _fit_key_to_range): 变调后高音超出上限时
           整体下调变调值，保持旋律内部音程一致，不产生局部跑调。
        """
        key = int(self.f0_up_key)
        if not self.auto_pitch:
            return key

        import numpy as np

        avg = self._estimate_average_pitch(input_path)
        if avg is None:
            return key
        auto = int(round(12 * np.log2(self.model_pitch_center / avg)))
        auto = max(-self.auto_pitch_clamp, min(self.auto_pitch_clamp, auto))
        if auto != 0:
            logger.info(
                f"[RVC] 自动变调: 源平均基频 {avg:.0f}Hz → 适配模型音域中心 "
                f"{self.model_pitch_center:.0f}Hz → {auto:+d} 半音"
            )
        else:
            logger.info(
                f"[RVC] 自动变调: 源平均基频 {avg:.0f}Hz ≈ 模型音域中心，保持原调"
            )
        key += auto
        return self._fit_key_to_range(input_path, key)

    def change_voice(self, model: Optional[str] = None) -> bool:
        """加载/切换声线模型 — POST /run/infer_change_voice"""
        model = self._model_file(model or self.model)
        if not model:
            logger.error("[RVC] 未配置模型名")
            return False

        try:
            body = self._post_json(
                "/run/infer_change_voice",
                {"data": [model, 0.33, 0.33]},
                timeout=180,
            )
            data = body.get("data")
            if not data:
                logger.error(f"[RVC] 模型加载无响应数据: {model}")
                return False
            first = data[0]
            if isinstance(first, str) and "Error" in first:
                logger.error(f"[RVC] 模型加载失败: {first[:300]}")
                return False
            self.model = model
            self._loaded_model = model
            self._need_load = False
            logger.info(f"[RVC] 模型已加载: {model}")
            return True
        except Exception as e:
            logger.error(f"[RVC] 模型加载失败 ({model}): {e}")
            return False

    def convert(self, input_path: str, output_path: str) -> bool:
        """声线转换 — 自动变调时整曲一致变调 (全局音域保护，无接缝无跑调)"""
        ok, _key = self.convert_ex(input_path, output_path)
        return ok

    def convert_ex(self, input_path: str, output_path: str) -> tuple:
        """声线转换，返回 (ok, applied_key)

        applied_key 为最终实际应用的变调半音数 (含自动变调 + 音域保护下调)。
        调用方必须据此同步移调伴奏/和声轨 — 只移人声不移伴奏会导致整首跑调。
        """
        if not os.path.exists(input_path):
            logger.error(f"[RVC] 输入音频不存在: {input_path}")
            return False, 0

        if not self.ensure_server():
            return False, 0

        model_file = self._model_file(self.model)
        if self._need_load or self._loaded_model != model_file:
            if not self.change_voice(model_file):
                return False, 0

        f0_key = self._resolve_f0_up_key(input_path)
        self.last_f0_key = f0_key
        return self._convert_single(input_path, output_path, f0_key), f0_key

    def _convert_single(self, input_path: str, output_path: str, f0_key: int) -> bool:
        """单次整体转换 — POST /run/infer_convert，输出复制到 output_path"""
        model_file = self._model_file(self.model)
        payload = {
            "data": [
                0,  # spk_item: 单说话人模型取 0；模型本体已由 infer_change_voice 加载
                os.path.abspath(input_path),
                f0_key,
                None,  # f0_file
                self.f0_method,
                "",  # file_index1 (手动 index 路径)
                self.index_path or "",  # file_index2 (下拉选择的 index)
                float(self.index_rate),
                int(self.filter_radius),
                int(self.resample_sr),
                float(self.rms_mix_rate),
                float(self.protect),
            ]
        }

        try:
            logger.info(
                f"[RVC] 转换中: {os.path.basename(input_path)} "
                f"(model={model_file}, key={f0_key}, method={self.f0_method}, "
                f"index={self.index_path or '(none)'}, rate={self.index_rate})"
            )
            body = self._post_json("/run/infer_convert", payload, timeout=600)
            data = body.get("data")
            if not data or len(data) < 2:
                logger.error("[RVC] 转换响应格式异常")
                return False

            info = data[0]
            out = data[1] if isinstance(data[1], dict) else {}

            src_path = out.get("name") or ""
            if not src_path and out.get("data"):
                # 输出以 base64 内联返回时解码写盘
                try:
                    raw = base64.b64decode(out["data"])
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(raw)
                    logger.info(f"[RVC] 转换完成 (base64): {output_path} ({len(raw)}B)")
                    return True
                except Exception as e:
                    logger.error(f"[RVC] base64 输出解码失败: {e}")
                    return False

            if not src_path or not os.path.exists(src_path):
                msg = (info or "")[:500]
                logger.error(f"[RVC] 转换失败，服务端信息: {msg}")
                return False

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            shutil.copyfile(src_path, output_path)
            logger.info(
                f"[RVC] 转换完成: {output_path} ({os.path.getsize(output_path)}B)"
            )
            return True
        except Exception as e:
            logger.error(f"[RVC] 转换请求失败: {e}")
            return False

    # ------------------------------------------------------------------ smart pitch

    @staticmethod
    def _frame_f0_curve(input_path: str):
        """逐帧基频曲线 (自相关法, 3点中值滤波): 返回 (times_sec_array, f0_hz_array, 未检出=nan)

        中值滤波用于抑制自相关法的倍频误判 (基频被判成 2 倍频) 与孤立跳变。
        """
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(input_path, dtype="float32", always_2d=True)
        data = data[:, 0]
        target = 16000
        if sr != target:
            n = int(len(data) * target / sr)
            data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data)
            sr = target
        frame = int(sr * 0.04)
        hop = int(sr * 0.02)
        min_lag = int(sr / 900)
        max_lag = int(sr / 60)
        window = np.hanning(frame)
        times, f0s = [], []
        for st in range(0, len(data) - frame, hop):
            seg = data[st : st + frame] * window
            seg = seg - seg.mean()
            if np.abs(seg).max() < 0.02:
                times.append((st + frame / 2) / sr)
                f0s.append(np.nan)
                continue
            ac = np.correlate(seg, seg, "full")[frame - 1 :]
            region = ac[min_lag:max_lag]
            if len(region) < 10:
                times.append((st + frame / 2) / sr)
                f0s.append(np.nan)
                continue
            lag = min_lag + int(np.argmax(region))
            f = sr / lag
            f0s.append(f if 60 <= f <= 900 else np.nan)
            times.append((st + frame / 2) / sr)

        f0 = np.array(f0s, dtype=np.float64)
        if len(f0) >= 3:  # 3 点中值滤波
            smooth = f0.copy()
            for i in range(1, len(smooth) - 1):
                win = smooth[i - 1 : i + 2]
                win = win[np.isfinite(win)]
                smooth[i] = float(np.median(win)) if len(win) else np.nan
            f0 = smooth
        return np.array(times), f0

    def _fit_key_to_range(self, input_path: str, base_key: int) -> int:
        """整曲音域保护: 若变调后高音超出上限的帧占比过高, 整体降低变调值

        与逐段降调不同，全局降调保持旋律内部音程一致，不会造成局部跑调。
        最多整体下调 4 半音；超限帧占比 ≤5% 视为可接受 (交给 RVC 自己处理)。
        """
        if self.auto_pitch_max_hz <= 0 or base_key <= 0:
            return base_key
        try:
            import numpy as np

            _t, f0 = self._frame_f0_curve(input_path)
            if len(f0) < 2:
                return base_key
            finite = np.isfinite(f0)
            n_finite = int(finite.sum())
            if n_finite < 10:
                return base_key

            max_ratio = 0.05
            key = base_key
            for drop in range(1, 5):
                cand = base_key - drop
                out = f0 * (2 ** (cand / 12))
                over = np.isfinite(out) & (out > self.auto_pitch_max_hz)
                if over.sum() / max(n_finite, 1) <= max_ratio:
                    key = cand
                    break
                key = cand
            if key != base_key:
                logger.info(
                    f"[RVC] 音域保护: 变调 {base_key:+d} → {key:+d} 半音 "
                    f"(避免高音超过 {self.auto_pitch_max_hz:.0f}Hz 破音)"
                )
            return key
        except Exception as e:
            logger.warning(f"[RVC] 音域保护分析失败, 保持原变调: {e}")
            return base_key

    # ------------------------------------------------------------------ close

    def close(self):
        """终止由本客户端自动拉起的 RVC 进程（外部启动的不动）"""
        proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=30,
                )
                logger.info("[RVC] 自动启动的服务已关闭")
            except Exception as e:
                logger.warning(f"[RVC] 关闭服务失败: {e}")
        self._loaded_model = None
        self._need_load = True
