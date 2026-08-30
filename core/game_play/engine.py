"""
游戏陪玩核心引擎 — 弥娅的感知器

通用游戏陪玩，不绑定特定游戏。
作为弥娅系统的感知器（sensor）—— 截图 + 视觉分析 + 主动提醒。

架构:
- get_screen_summary() → 画面简述 → 注入弥娅主对话上下文（DecisionHub 调用）
- 相机循环 → 独立后台运行 → 主动 TTS 提醒（危险/发现时）
- 弥娅用自己的主 LLM（人格 + 记忆 + 情绪）来回应
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GamePlayState:
    active: bool = False
    game_id: Optional[str] = None
    game_name: Optional[str] = None
    voice_enabled: bool = True
    vision_enabled: bool = True
    control_enabled: bool = False
    started_at: float = 0.0
    screenshot_count: int = 0
    last_screenshot_at: float = 0.0


class GamePlayEngine:
    """
    游戏陪玩感知器 — 弥娅的"眼睛"。

    - get_screen_summary() → 给 DecisionHub 注入上下文用
    - 相机循环 → 后台异步主动提醒
    """

    _SUMMARY_PROMPT = (
        "用一段简短的话描述当前游戏画面中的关键信息。"
        "包括：游戏类型、场景、角色状态（血量/资源）、敌人在做什么、有什么需要注意的。"
        "用中文，控制在 2-3 句话以内。不要 JSON，直接说话。"
    )

    def __init__(self):
        self._state = GamePlayState()
        self._voice: Any = None
        self._monitor: Any = None
        self._controller: Any = None
        self._profile_manager: Any = None
        self._profile: Any = None
        self._monitor_active: bool = False
        self._initialized = False
        self._last_summary: str = ""
        self._http_client: Any = None

    async def initialize(self):
        if self._initialized:
            return
        from .profiles import GameProfileManager

        self._profile_manager = GameProfileManager()
        self._initialized = True
        logger.info("[GamePlay] 感知器就绪")

    def _ensure_profile(self, game_id: Optional[str] = None):
        if self._profile_manager is None:
            from .profiles import GameProfileManager

            self._profile_manager = GameProfileManager()
        self._profile = self._profile_manager.get_profile(game_id)
        logger.info(f"[GamePlay] Profile: {self._profile.game_name} ({self._profile.game_id})")

    # ── 生命周期 ────────────────────────────────────

    async def start_game(
        self,
        game_id: Optional[str] = None,
        voice_enabled: bool = True,
        vision_enabled: bool = True,
        control_enabled: bool = False,
        auto_speak: bool = False,
    ) -> dict[str, Any]:
        if self._state.active:
            return {
                "status": "warning",
                "message": f"游戏陪玩已在运行中 ({self._state.game_name or '通用模式'})",
            }
        await self.initialize()
        if game_id:
            self._profile_manager.reload()
            self._ensure_profile(game_id)
        elif not self._profile:
            self._ensure_profile(None)
        if self._profile is None:
            return {"status": "error", "message": "无法加载 Profile"}

        self._state.active = True
        self._state.game_id = self._profile.game_id
        self._state.game_name = self._profile.game_name
        self._state.voice_enabled = voice_enabled
        self._state.vision_enabled = vision_enabled
        self._state.control_enabled = control_enabled
        self._state.started_at = time.time()
        self._last_summary = ""

        if auto_speak and vision_enabled:
            await self._init_camera_loop()
        elif vision_enabled:
            logger.info(f"[GamePlay] 陪玩已启动 {self._profile.game_name} (手动模式，发消息触发分析)")

        logger.info(f"[GamePlay] 陪玩已启动 {self._profile.game_name}")
        return {
            "status": "success",
            "message": f"游戏陪玩已启动~ {self._profile.game_name}",
            "game_id": self._profile.game_id,
            "game_name": self._profile.game_name,
            "mode": "通用" if self._profile.game_id == "general" else "专属",
        }

    async def stop_game(self) -> dict[str, Any]:
        if not self._state.active:
            return {"status": "info", "message": "游戏陪玩未在运行中"}
        game_name = self._state.game_name or "通用模式"
        await self._stop_camera_loop()
        self._state.active = False
        self._state.game_id = None
        self._state.game_name = None
        self._last_summary = ""
        logger.info(f"[GamePlay] 已停止 ({game_name})")
        return {"status": "success", "message": f"已退出 {game_name}"}

    # ── 核心能力：画面感知（供 DecisionHub 调用）─────────────────

    async def get_screen_summary(self) -> str:
        """
        获取当前游戏画面简述 —— 供 DecisionHub 注入到弥娅的对话上下文中。

        调用流程:
        1. 如果相机循环有最近的主动提醒 (alert)，直接返回
        2. 否则截一帧 + 视觉 LLM 简短分析 → 返回文本
        """
        if not self._state.active or not self._state.vision_enabled:
            return ""

        # 优先使用最近的主动提醒（已经分析好的，避免重复 LLM 调用）
        if self._monitor and self._monitor.alerts:
            recent = self._monitor.alerts[-1]
            age = time.time() - recent.get("time", 0)
            if age < 5.0:  # 5 秒内的提醒直接复用
                summary = f"[屏幕: {recent.get('scene', '')}] {recent.get('message', '')}"
                self._last_summary = summary
                return summary

        # 否则截一帧分析
        scr = await self._take_screenshot()
        if not scr:
            return self._last_summary or ""

        self._state.screenshot_count += 1
        self._state.last_screenshot_at = time.time()

        try:
            description = await self._call_vision(
                self._SUMMARY_PROMPT,
                scr["data_url"],
                "描述当前游戏画面",
            )
            if description:
                self._last_summary = description
                return description
        except Exception as e:
            logger.warning(f"[GamePlay] 画面描述失败: {e}")

        return self._last_summary or ""

    # ── 状态查询 ────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        monitor_status = self._monitor.get_status() if self._monitor else {}
        return {
            "active": self._state.active,
            "game_id": self._state.game_id,
            "game_name": self._state.game_name,
            "voice_enabled": self._state.voice_enabled,
            "vision_enabled": self._state.vision_enabled,
            "control_enabled": self._state.control_enabled,
            "started_at": self._state.started_at,
            "screenshot_count": self._state.screenshot_count,
            "monitor": monitor_status,
        }

    def list_games(self) -> list[dict[str, Any]]:
        if not self._initialized:
            return []
        return self._profile_manager.list_profiles()

    # ── 相机循环（独立后台，只做主动提醒）─────────────────

    async def _init_camera_loop(self):
        if self._monitor is not None and self._monitor_active:
            return
        from .screen_monitor import ProactiveScreenMonitor

        self._monitor = ProactiveScreenMonitor()
        self._monitor.apply_profile(self._profile)

        async def on_alert(message: str, scene: str, urgency: int):
            if self._state.voice_enabled:
                await self._speak_async(message)

        self._monitor.set_callbacks(
            on_alert=on_alert,
            screenshot_fn=self._take_screenshot,
            analyzer_fn=lambda url: self._call_vision(
                self._profile.system_prompt if self._profile else "分析游戏画面并返回 JSON。",
                url,
                "返回 JSON",
            ),
        )
        await self._monitor.start(interval=2.0)
        self._monitor_active = True
        logger.info("[GamePlay] 相机循环已启动")

    async def _stop_camera_loop(self):
        if self._monitor:
            await self._monitor.stop()
            self._monitor = None
        self._monitor_active = False

    # ── 内部工具 ────────────────────────────────────

    async def _take_screenshot(self) -> Optional[dict[str, Any]]:
        try:
            from mcpserver.screen_vision.screenshot_provider import (
                compress_screenshot_data_url,
                get_screenshot_provider,
            )

            screenshot = get_screenshot_provider().capture_data_url()
            compressed_url = compress_screenshot_data_url(screenshot.data_url, max_width=1280, quality=75)
            self._state.screenshot_count += 1
            return {"data_url": compressed_url, "width": screenshot.width, "height": screenshot.height}
        except Exception as e:
            logger.error(f"[GamePlay] 截图失败: {e}")
            return None

    async def _call_vision(self, system_prompt: str, image_url: str, user_query: str) -> str:
        try:
            api_key, base_url, model_id = self._resolve_vision_model()
            logger.info(f"[GamePlay] 视觉模型: {model_id} @ {base_url}")
        except Exception as e:
            logger.error(f"[GamePlay] 模型配置错误: {e}")
            return ""

        try:
            import httpx

            base_url = base_url.rstrip("/")
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_query},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ]
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=120.0)
            response = await self._http_client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": messages, "max_tokens": 1024, "temperature": 0.7},
            )
            if response.status_code != 200:
                raise RuntimeError(f"视觉 LLM 返回 {response.status_code}: {response.text[:300]}")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"[GamePlay] 视觉完成 ({len(content)} chars): {content[:150]}...")
            return content
        except Exception as e:
            logger.error(f"[GamePlay] 视觉调用失败: {e}", exc_info=True)
            return ""

    def _resolve_vision_model(self) -> tuple[str, str, str]:
        from config.config_utils import get_api_key

        miya_root = Path(__file__).resolve().parent.parent.parent
        cfg_path = miya_root / "config" / "multi_model_config.json"
        if not cfg_path.exists():
            raise RuntimeError("[GamePlay] 模型配置文件不存在")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        models = cfg.get("models", {})
        vision_prefs = cfg.get("vision_preferences", {}).get("model_preferences", {})
        active_vision = cfg.get("vision_preferences", {}).get("active_vision", "")
        for raw_key in [vision_prefs.get("primary"), vision_prefs.get("secondary")]:
            key = active_vision if raw_key == "@active_vision" else raw_key
            if not key or key not in models:
                continue
            m = models[key]
            env_key = m.get("env_key", "")
            api_key = get_api_key(env_key) if env_key else ""
            if api_key and m.get("name"):
                return api_key, m.get("base_url", ""), m.get("name", "")
        for model_key, m in models.items():
            if m.get("type") == "vision" or "vision" in m.get("capabilities", []):
                env_key = m.get("env_key", "")
                api_key = get_api_key(env_key) if env_key else ""
                if api_key:
                    return api_key, m.get("base_url", ""), m.get("name", "")
        raise RuntimeError("[GamePlay] 未找到可用的视觉模型")

    async def _speak_async(self, text: str):
        if not text:
            return
        logger.info(f"[GamePlay] TTS: {text[:60]}...")
        try:
            from .voice_pipeline import VoicePipeline

            if self._voice is None:
                self._voice = VoicePipeline()
            await self._voice.speak(text)
        except Exception as e:
            logger.warning(f"[GamePlay] TTS 播放失败: {e}")


_engine: Optional[GamePlayEngine] = None


def get_game_play_engine() -> GamePlayEngine:
    global _engine
    if _engine is None:
        _engine = GamePlayEngine()
    return _engine
