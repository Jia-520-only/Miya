"""
弥娅 TTS 引擎路由 — 跨平台共享模块
供 OneBot / QQOfficial / 其他平台复用
"""

import hashlib
import logging
import os
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

_CLEANUP_QUEUE: list[str] = []


def _load_config():
    import json

    config_path = "config/tts_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _schedule_cleanup(path: str, delay: float = 30.0):
    """延迟清理临时音频文件"""
    from threading import Timer

    def _clean(path):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except (PermissionError, OSError):
            import time

            time.sleep(5)
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except (PermissionError, OSError):
                pass

    Timer(delay, _clean, (path,)).start()


async def synthesize(
    text: str, engine: str = None, voice: str = None, speed: float = None, fmt: str = None
) -> str | None:
    """合成语音 → 返回文件路径，失败返回 None

    voice/speed/fmt 为请求级覆盖（仅 edge_tts 引擎生效），
    用于 Web API 等需要临时覆盖配置参数的场景。
    """
    config = _load_config()
    if not engine:
        engine = config.get("preferred_engine", "edge_tts")
    try:
        if engine == "gpt_sovits":
            path = await _synthesize_gpt_sovits(config, text)
        elif engine == "api_tts":
            path = await _synthesize_api_tts(config, text)
        else:
            path = await _synthesize_edge_tts(config, text, voice=voice, speed=speed, fmt=fmt)
    except Exception as e:
        logger.warning(f"TTS {engine} 失败: {e}，回退 edge-tts")
        if engine != "edge_tts":
            try:
                path = await _synthesize_edge_tts(config, text, voice=voice, speed=speed, fmt=fmt)
            except Exception:
                return None
        else:
            return None

    if not path:
        return None

    if config.get("save_audio", False):
        _archive_audio(path, text, config)
    else:
        _schedule_cleanup(path, 30.0)

    return path


def _archive_audio(audio_path: str, text: str, config: dict):
    """将音频存档到 data/tts_audio/"""
    import shutil

    save_dir = config.get("save_audio_dir", "data/tts_audio")
    os.makedirs(save_dir, exist_ok=True)
    suffix = os.path.splitext(audio_path)[1] or ".wav"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    filename = f"{timestamp}_{text_hash}{suffix}"
    dest = os.path.join(save_dir, filename)
    try:
        shutil.copy2(audio_path, dest)
        logger.info(f"[TTS] 音频已存档: {dest}")
    except Exception as e:
        logger.warning(f"[TTS] 存档失败: {e}")


async def _synthesize_edge_tts(config: dict, text: str, voice: str = None, speed: float = None, fmt: str = None) -> str:
    import edge_tts

    engine_cfg = config.get("engines", {}).get("edge_tts", {})
    voice = voice or engine_cfg.get("voice", "zh-CN-XiaoxiaoNeural")
    speed = speed if speed is not None else engine_cfg.get("speed", 1.0)
    rate_str = f"+{int((speed - 1) * 100)}%"
    suffix = fmt or "mp3"
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    tmp = tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False)
    tmp_path = tmp.name
    tmp.close()
    await communicate.save(tmp_path)
    return tmp_path


async def _synthesize_gpt_sovits(config: dict, text: str) -> str:
    import re

    import aiohttp

    sovits = config.get("engines", {}).get("gpt_sovits", {})
    api_url = sovits.get("api_url", "http://127.0.0.1:9880")
    timeout = sovits.get("timeout", 30)

    filtered = text
    if sovits.get("filter_brackets", True):
        filtered = re.sub(r"【.*?】", "", filtered)
        filtered = re.sub(r"\[.*?\]", "", filtered)
    if sovits.get("filter_special_chars", True):
        filtered = re.sub(r"[\U00010000-\U0010FFFF]", "", filtered)

    payload = {
        "text": filtered,
        "text_lang": sovits.get("language", "zh"),
        "ref_audio_path": sovits.get("reference_audio", ""),
        "prompt_text": sovits.get("reference_text", ""),
        "prompt_lang": sovits.get("language", "zh"),
        "top_k": sovits.get("top_k", 15),
        "top_p": sovits.get("top_p", 1.0),
        "temperature": sovits.get("temperature", 1.0),
        "speed_factor": sovits.get("speed", 1.0),
        "ref_free": sovits.get("ref_free", False),
    }
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
        async with s.post(f"{api_url.rstrip('/')}/tts", json=payload) as r:
            if r.status != 200:
                raise RuntimeError(f"GPT-SoVITS {r.status}")
            data = await r.read()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as f:
        f.write(data)
    return tmp_path


async def _synthesize_api_tts(config: dict, text: str) -> str:
    import aiohttp

    api_conf = config.get("engines", {}).get("api_tts", {})
    api_url = api_conf.get("api_url", "https://api.openai.com/v1/audio/speech")
    api_key = api_conf.get("api_key", "")
    if not api_key:
        raise RuntimeError("API Key 未配置")
    fmt = api_conf.get("format", "mp3")
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": api_conf.get("voice", "alloy"),
        "response_format": fmt,
        "speed": api_conf.get("speed", 1.0),
    }
    async with (
        aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s,
        s.post(api_url, json=payload, headers={"Authorization": f"Bearer {api_key}"}) as r,
    ):
        if r.status != 200:
            raise RuntimeError(f"API TTS {r.status}")
        data = await r.read()
    tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as f:
        f.write(data)
    return tmp_path
