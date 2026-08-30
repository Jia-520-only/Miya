"""
主动屏幕监控 — AI 决策版

不做关键词匹配。每一帧截图 → 视觉 LLM 返回结构化 JSON → AI 决定是否说话。
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ProactiveScreenMonitor:
    """
    AI 驱动的主动屏幕监控 — 通用游戏陪玩的眼睛 & 嘴巴。

    不做关键词匹配——把画面丢给视觉 LLM，让 AI 自己决定要不要对玩家说话。

    自适应帧率:
    - combat   → 0.5s 高频
    - explore  → 3s 低频
    - cutscene → 暂停
    - menu     → 低频
    """

    def __init__(self):
        self._running = False
        self._active = False
        self._task: Optional[asyncio.Task] = None
        self._current_interval: float = 2.0
        self._last_speak_at: float = 0.0
        self._last_scene: str = "default"
        self._speak_cooldown: float = 4.0

        self._on_alert: Optional[Callable] = None
        self._screenshot_fn: Optional[Callable] = None
        self._analyzer_fn: Optional[Callable] = None

        self._profile: Any = None
        self._fps_map: dict[str, float] = {}
        self._silence_scenes: list[str] = []
        self._frame_count: int = 0

        self.alerts: list[dict[str, Any]] = []
        self.last_analysis: dict[str, Any] = {}

    def apply_profile(self, profile: Any):
        self._profile = profile
        self._fps_map = profile.adaptive_fps if profile else {}
        self._silence_scenes = profile.silence_scenes if profile else []
        self._speak_cooldown = profile.speak_cooldown if profile else 4.0
        logger.info(f"[ScreenMonitor] Profile 应用: fps_map={self._fps_map}, silence={self._silence_scenes}")

    def _get_fps_for_scene(self, scene: str) -> float:
        fps = self._fps_map.get(scene, self._fps_map.get("default", 2.0))
        return float("inf") if fps >= 999 else float(fps)

    def _update_interval(self, scene: str):
        fps = self._get_fps_for_scene(scene)
        self._current_interval = 1.0 / fps if fps > 0 else 10.0
        self._last_scene = scene

        if scene in self._silence_scenes:
            if self._active:
                logger.debug(f"[ScreenMonitor] 进入静默场景: {scene}")
                self._active = False
        else:
            if not self._active:
                logger.debug(f"[ScreenMonitor] 恢复监控，场景: {scene}")
                self._active = True

    def set_callbacks(self, on_alert: Callable, screenshot_fn: Callable, analyzer_fn: Callable):
        self._on_alert = on_alert
        self._screenshot_fn = screenshot_fn
        self._analyzer_fn = analyzer_fn

    async def start(self, interval: float = 2.0):
        if self._running:
            return
        self._current_interval = interval
        self._running = True
        self._active = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"[ScreenMonitor] 启动 (初始间隔 {interval}s)")

    async def stop(self):
        self._running = False
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[ScreenMonitor] 已停止")

    def set_active(self, active: bool):
        self._active = active
        logger.info(f"[ScreenMonitor] {'激活' if active else '暂停'}")

    async def _monitor_loop(self):
        while self._running:
            try:
                if self._active and self._screenshot_fn and self._analyzer_fn:
                    await self._check_frame()
                await asyncio.sleep(self._current_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ScreenMonitor] 异常: {e}")
                await asyncio.sleep(3.0)

    async def _check_frame(self):
        try:
            screenshot = await self._screenshot_fn()
            if not screenshot:
                logger.info("[ScreenMonitor] 截图返回空，跳过本帧")
                self._frame_count += 1
                return

            self._frame_count += 1
            logger.info(f"[ScreenMonitor] 第 {self._frame_count} 帧开始分析")
            import asyncio as _asyncio

            try:
                analysis_text = await _asyncio.wait_for(
                    self._analyzer_fn(screenshot["data_url"]),
                    timeout=90.0,
                )
            except _asyncio.TimeoutError:
                logger.warning("[ScreenMonitor] 视觉分析超时(90s)，跳过本帧")
                self._frame_count += 1
                return
            except Exception as e:
                logger.error(f"[ScreenMonitor] 分析异常: {e}")
                return

            parsed = self._try_parse_json(analysis_text)
            if not parsed:
                return

            self.last_analysis = parsed

            scene = parsed.get("scene", "default")
            self._update_interval(scene)

            should_speak = parsed.get("should_speak", False)
            urgency = parsed.get("urgency", 0)
            what_to_say = parsed.get("what_to_say", "")

            if not should_speak or not what_to_say:
                return

            min_urgency = 0
            if self._profile:
                min_urgency = getattr(self._profile, "min_urgency_for_speak", 3)
            if urgency < min_urgency:
                return

            elapsed_since_speak = time.time() - self._last_speak_at
            if elapsed_since_speak < self._speak_cooldown:
                return

            self._last_speak_at = time.time()

            alert = {
                "scene": scene,
                "urgency": urgency,
                "message": what_to_say,
                "frame": self._frame_count,
                "time": time.time(),
            }
            self.alerts.append(alert)
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-50:]

            if self._on_alert:
                await self._on_alert(what_to_say, scene, urgency)

            logger.info(f"[ScreenMonitor] {scene}#{urgency}: {what_to_say[:80]}")

        except Exception as e:
            logger.error(f"[ScreenMonitor] _check_frame 异常: {e}")

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict[str, Any]]:
        if not text:
            return None
        text = text.strip()
        try:
            return __import__("json").loads(text)
        except Exception:
            pass
        for prefix, suffix in [("{", "}"), ("```json\n", "\n```"), ("```\n", "\n```")]:
            try:
                start = text.index(prefix)
                end = text.rindex(suffix)
                return __import__("json").loads(text[start : end + len(suffix)])
            except (ValueError, Exception):
                continue
        return None

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "active": self._active,
            "current_interval": round(self._current_interval, 2),
            "last_scene": self._last_scene,
            "frame_count": self._frame_count,
            "alerts_count": len(self.alerts),
            "last_analysis": self.last_analysis,
        }

    def get_recent_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.alerts[-limit:]
