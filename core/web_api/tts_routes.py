"""
弥娅 TTS API 路由
提供 /tts/speech 端点，连接前端 TTS 播放到后端多引擎
"""

import contextlib
import json
import logging
import os
from typing import Optional

from starlette.responses import Response

try:
    from fastapi import APIRouter, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception

logger = logging.getLogger(__name__)


def _load_tts_config():
    try:
        with open("config/tts_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class TTSRoutes:
    """TTS API 路由"""

    def __init__(self):
        self.router: Optional[APIRouter] = None
        if not FASTAPI_AVAILABLE:
            logger.warning("[TTSRoutes] FastAPI 不可用")
            return

        self.router = APIRouter(prefix="/tts", tags=["TTS"])
        self._setup_routes()

    def _setup_routes(self):
        router = self.router

        @router.post("/speech")
        async def tts_speech(request: dict):
            """TTS 语音合成，支持多引擎"""
            input_text = request.get("input") or request.get("text", "")
            voice = request.get("voice", "zh-CN-XiaoxiaoNeural")
            speed = request.get("speed", 1.0)
            response_format = request.get("response_format") or request.get("format", "mp3")
            engine = request.get("engine") or request.get("model", "")

            if not input_text:
                raise HTTPException(status_code=400, detail="input text is required")

            config = _load_tts_config()
            if not engine or engine in ("default", "tts-1"):
                engine = config.get("preferred_engine", "edge_tts")

            logger.info(f"[TTS] {engine} request: voice={voice}, speed={speed}, len={len(input_text)}")

            try:
                from core.tts.engine_router import synthesize

                audio_path = await synthesize(input_text, engine=engine, voice=voice, speed=speed, fmt=response_format)
                if not audio_path:
                    raise RuntimeError("synthesis returned empty path")

                with open(audio_path, "rb") as f:
                    audio_data = f.read()
                with contextlib.suppress(OSError):
                    os.unlink(audio_path)

                content_type_map = {
                    "mp3": "audio/mpeg",
                    "wav": "audio/wav",
                    "ogg": "audio/ogg",
                    "aac": "audio/aac",
                    "flac": "audio/flac",
                }
                if engine == "gpt_sovits":
                    content_type = "audio/wav"
                elif engine == "api_tts":
                    api_fmt = config.get("engines", {}).get("api_tts", {}).get("format", "mp3")
                    content_type = content_type_map.get(api_fmt, "audio/mpeg")
                else:
                    content_type = content_type_map.get(response_format, "audio/mpeg")

                logger.info(f"[TTS] {engine} 合成成功: {len(audio_data)} bytes")
                return Response(
                    content=audio_data,
                    media_type=content_type,
                    headers={
                        "Content-Length": str(len(audio_data)),
                        "Cache-Control": "no-cache",
                    },
                )

            except ImportError:
                logger.error(f"[TTS] {engine} 依赖未安装")
                raise HTTPException(status_code=500, detail=f"{engine} dependencies missing")
            except Exception as e:
                logger.error(f"[TTS] {engine} 合成失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def get_router(self) -> Optional[APIRouter]:
        return self.router
