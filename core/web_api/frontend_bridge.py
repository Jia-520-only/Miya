"""前端桥接路由 — 补齐前端已调用但后端缺失的断链端点

- GET  /api/config/get      读取前端 CONFIG 持久化（config/frontend.json）
- POST /api/config/set      保存前端 CONFIG（防抖后整包提交，备份 + 原子写）
- GET  /api/system/prompt   读取系统提示词（frontend.json 的 system_prompt 键）
- POST /api/system/prompt   保存系统提示词
- POST /api/document/parse  文本类文件解析（返回内容，供前端注入对话）
- POST /api/document/upload 任意文件上传（返回落盘路径）
- POST /api/audio/transcribe 语音转文字（miya_senses speech_to_text provider）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException, UploadFile

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception
    UploadFile = object

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_FRONTEND_CONFIG_PATH = _PROJECT_ROOT / "config" / "frontend.json"
_DOWNLOAD_DIR = _PROJECT_ROOT / "data" / "downloads"
_MAX_PARSE_BYTES = 2 * 1024 * 1024  # 解析上限 2MB 文本

_PARSEABLE_EXTS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".csv", ".log",
    ".py", ".js", ".ts", ".html", ".css", ".sql", ".sh", ".bat", ".ini", ".toml",
}


def _load_frontend_config() -> dict:
    if _FRONTEND_CONFIG_PATH.exists():
        try:
            return json.loads(_FRONTEND_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[FrontendBridge] 读取 frontend.json 失败: {e}")
    return {}


def _save_frontend_config(data: dict) -> None:
    """深合并保存：前端整包提交时保留文件里已有的非前端键（如 api_server）"""
    from .config_routes import _atomic_write, _backup_file

    merged = _load_frontend_config()

    def _deep_merge(target: dict, source: dict) -> dict:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                _deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    _deep_merge(merged, data)
    _FRONTEND_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _FRONTEND_CONFIG_PATH.exists():
        _backup_file(_FRONTEND_CONFIG_PATH)
    _atomic_write(_FRONTEND_CONFIG_PATH, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")


class FrontendBridgeRoutes:
    """前端断链端点桥接路由"""

    def __init__(self, web_net: Any = None, decision_hub: Any = None):
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            self.router = None
            return

        self.router = APIRouter(tags=["FrontendBridge"])
        self._setup_routes()
        logger.info("[FrontendBridge] 前端桥接路由已初始化")

    def _setup_routes(self):

        @self.router.get("/api/config/get")
        async def config_get():
            """前端 CONFIG 单例读取（启动时合并默认值）"""
            return _load_frontend_config()

        @self.router.post("/api/config/set")
        async def config_set(request: dict = None):
            """前端 CONFIG 单例持久化（防抖后整包提交）"""
            if not isinstance(request, dict) or not request:
                raise HTTPException(status_code=400, detail="配置内容不能为空")
            try:
                _save_frontend_config(request)
                return {"success": True, "message": "已保存"}
            except OSError as e:
                logger.error(f"[FrontendBridge] 保存前端配置失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"保存失败: {e}")

        @self.router.get("/api/system/prompt")
        async def system_prompt_get():
            """系统提示词读取"""
            return {"prompt": _load_frontend_config().get("system_prompt", "")}

        @self.router.post("/api/system/prompt")
        async def system_prompt_set(request: dict = None):
            """系统提示词保存"""
            request = request or {}
            prompt = str(request.get("prompt", ""))
            data = _load_frontend_config()
            data["system_prompt"] = prompt
            try:
                _save_frontend_config(data)
                return {"success": True}
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"保存失败: {e}")

        @self.router.post("/api/document/parse")
        async def document_parse(file: UploadFile):
            """文本类文件解析：返回内容（前端注入对话上下文）"""
            content_bytes = await file.read()
            if len(content_bytes) > _MAX_PARSE_BYTES:
                raise HTTPException(status_code=400, detail="文件过大（上限 2MB）")
            name = file.filename or "untitled"
            if Path(name).suffix.lower() not in _PARSEABLE_EXTS:
                raise HTTPException(status_code=400, detail=f"不支持的解析类型: {name}")
            try:
                text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = content_bytes.decode("gbk")
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="无法解码的文本文件")
            truncated = len(text) > 60000
            return {"content": text[:60000], "truncated": truncated, "filename": name}

        @self.router.post("/api/document/upload")
        async def document_upload(file: UploadFile):
            """任意文件上传：保存到 data/downloads/ 并返回路径"""
            _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = file.filename or "unknown_file"
            target = _DOWNLOAD_DIR / safe_name
            content = await file.read()
            target.write_bytes(content)
            logger.info(f"[FrontendBridge] 文件上传: {safe_name} ({len(content)} bytes)")
            return {"success": True, "filePath": str(target), "filename": safe_name, "size": len(content)}

        @self.router.post("/api/audio/transcribe")
        async def audio_transcribe(file: UploadFile, language: str = "zh"):
            """语音转文字：走 miya_senses 的 speech_to_text provider"""
            audio = await file.read()
            if not audio:
                raise HTTPException(status_code=400, detail="音频内容为空")
            try:
                from core.providers_astrbot.provider import ProviderManager

                stt = ProviderManager().get_provider("speech_to_text")
                if not stt:
                    raise HTTPException(
                        status_code=501,
                        detail="未配置 speech_to_text provider，无法转写",
                    )
                text = await stt.transcribe(audio)
                return {"text": text or ""}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[FrontendBridge] 语音转写失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"转写失败: {e}")

    def get_router(self):
        return self.router
