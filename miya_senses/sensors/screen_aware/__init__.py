from __future__ import annotations

"""
弥娅 Screen-Aware Proactive 模块 v2 — 混合感知策略

让弥娅「看见」佳在做什么，并主动搭话。

核心管线:
  Tier 0 (零成本)  → 图像哈希判断画面是否变化
  Tier 1 (轻量)   → 活跃窗口标题 → 推算活动类型
  Tier 2 (中量)   → 活动切换 / 攒够N次 → 截图视觉模型分析
  Tier 3 (重量)   → 用户主动要求 / 长时间陌生画面 → 完整视觉分析

Token 消耗策略 (v2.1 + OCR):
  - Tier 0:  图像哈希 → 画面没变，零成本 (~50%)
  - Tier 1:  窗口标题 → 本地检测 (~25%)
  - Tier 15: OCR识字 → 本地PaddleOCR，零token (~15%)
  - Tier 2:  视觉模型轻问 → 少量token (~8%)
  - Tier 3:  视觉模型全问 → 完整分析 (~2%)
  - 视觉模型调用间隔 ≥ 5分钟，24小时内最多 24次
"""

import asyncio
import hashlib
import io
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("miya_senses.screen_aware")

try:
    import imagehash
    from PIL import Image

    _HAS_IMAGEHASH = True
except ImportError:
    _HAS_IMAGEHASH = False

_IS_WINDOWS = __import__("platform").system() == "Windows"

_OCR_INIT_WARNED = False
_OCR_MODEL_DIR: str = ""  # 可在模块导入前通过环境变量 PADDLE_PDX_CACHE_HOME 覆盖


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class ScreenObservation:
    """弥娅对屏幕的「一瞥」— 含原始感官数据和硬编码分类"""

    timestamp: float = field(default_factory=time.time)
    window_title: str = ""  # 窗口标题（原始感官）
    ocr_text: str = ""  # OCR 文字（原始感官）
    description: str = ""  # 视觉模型描述
    detected_activity: str = ""  # 硬编码分类 (coding/gaming/...)
    detected_apps: list[str] = field(default_factory=list)
    attention_score: float = 0.0
    proactive_trigger_score: float = 0.0
    mood_hint: str = ""
    raw_response: str = ""
    analysis_tier: int = 0
    image_hash: str = ""


@dataclass
class ProactiveIntent:
    intent_id: str = ""
    trigger_type: str = ""
    description: str = ""
    priority: float = 0.0
    suggested_topic: str = ""
    suggested_tone: str = ""
    observation: Optional[ScreenObservation] = None


# ── 主引擎 ────────────────────────────────────────────────


class ScreenAwareProactive:
    """
    屏幕感知主动聊天引擎 v2 — 混合感知策略。

    Token 预算: vision_daily_quota 次/天, vision_cooldown 秒最小间隔。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        min_interval_seconds: float = 15.0,  # 轻量观察间隔（可以更频繁）
        adaptive_framerate: bool = True,
        idle_threshold_seconds: float = 300.0,
        attention_threshold: float = 0.35,
        proactive_threshold: float = 0.35,  # 主动说话阈值（低于此不开口）
        max_observations_history: int = 100,
        # ── Token 控制 ──
        vision_cooldown_seconds: float = 300.0,  # 视觉模型最小间隔（5分钟）
        vision_daily_quota: int = 24,  # 每天最多调用视觉模型次数
        vision_trigger_activity_change: bool = True,  # 活动切换时触发视觉模型
        vision_trigger_light_count: int = 10,  # 攒够N次轻量观察触发一次视觉
        hash_similarity_threshold: int = 8,  # pHash 汉明距离 < 此值视为相同画面
        # ── 视觉模型开关 ──
        vision_mode: str = "hybrid",  # ocr_only | api_only | hybrid
        model_dir: str = "",  # 本地 OCR 模型目录，留空自动检测
        ocr_startup_grace_seconds: float = 120.0,  # 启动后延迟加载 OCR，避免阻塞启动
    ) -> None:
        self.enabled = bool(enabled)
        self.min_interval = max(5.0, float(min_interval_seconds))
        self.adaptive_framerate = bool(adaptive_framerate)
        self.idle_threshold = float(idle_threshold_seconds)
        self.attention_threshold = max(0.0, min(1.0, float(attention_threshold)))
        self.proactive_threshold = max(0.0, min(1.0, float(proactive_threshold)))
        self.max_history = max(10, int(max_observations_history))

        self.vision_cooldown = max(60.0, float(vision_cooldown_seconds))
        self.vision_daily_quota = max(1, int(vision_daily_quota))
        self.vision_trigger_activity_change = bool(vision_trigger_activity_change)
        self.vision_trigger_light_count = max(1, int(vision_trigger_light_count))
        self.hash_similarity = max(0, int(hash_similarity_threshold))
        self.vision_mode = str(vision_mode) if vision_mode in ("ocr_only", "api_only", "hybrid") else "hybrid"
        self._model_dir = str(model_dir) if model_dir else ""

        self._observations: list[ScreenObservation] = []
        self._last_observe_time: float = 0.0
        self._last_proactive_time: float = 0.0
        self._last_vision_time: float = 0.0
        self._activity_history: list[tuple[float, str]] = []
        self._current_interval: float = self.min_interval
        self._hash_cache: dict[str, str] = {}  # hash → activity
        self._light_count_since_vision: int = 0
        self._vision_count_today: int = 0
        self._day_reset_time: float = time.time()

        self._last_screenshot_bytes: bytes | None = None
        self._last_image_hash: str = ""

        self._ocr_engine: Any = None
        self._ocr_enabled: bool = True
        self._ocr_loading: bool = False
        self._ocr_grace: float = max(0.0, float(ocr_startup_grace_seconds))
        self._init_time: float = time.time()

    def _reset_daily_quota(self) -> None:
        now = time.time()
        if now - self._day_reset_time > 86400:
            self._vision_count_today = 0
            self._day_reset_time = now

    @property
    def should_observe(self) -> bool:
        if not self.enabled:
            return False
        return (time.time() - self._last_observe_time) >= self._current_interval

    def set_vision_mode(self, mode: str) -> str:
        """运行时切换: ocr_only | api_only | hybrid"""
        if mode in ("ocr_only", "api_only", "hybrid"):
            self.vision_mode = mode
            logger.info(f"[ScreenAware] 视觉模式切换为: {mode}")
        return self.vision_mode

    def _should_use_vision(self, activity_changed: bool = False) -> bool:
        if self.vision_mode == "ocr_only":
            return False
        if self.vision_mode == "api_only":
            pass
        elif self.vision_mode == "hybrid":
            pass
        self._reset_daily_quota()
        if self._vision_count_today >= self.vision_daily_quota:
            logger.debug("[ScreenAware] 今日视觉模型配额已用完")
            return False
        if (time.time() - self._last_vision_time) < self.vision_cooldown:
            return False
        if activity_changed and self.vision_trigger_activity_change:
            return True
        if self._light_count_since_vision >= self.vision_trigger_light_count:
            return True
        return False

    # ── Tier 0: 图像哈希对比 ──

    def _capture_and_hash(self) -> tuple[bytes, str]:
        """截图并计算感知哈希。零 token 消耗。"""
        try:
            from mcpserver.screen_vision.screenshot_provider import get_screenshot_provider

            screenshot = get_screenshot_provider().capture_data_url()
            raw = screenshot.data_url
            if raw.startswith("data:") and "base64," in raw:
                raw = raw.split("base64,", 1)[1]
            img_bytes = __import__("base64").b64decode(raw)
        except Exception as exc:
            logger.debug(f"[ScreenAware] 截图失败: {exc}")
            return b"", ""

        if _HAS_IMAGEHASH and img_bytes:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                h = imagehash.phash(img)
                return img_bytes, str(h)
            except Exception:
                img_hash = hashlib.md5(img_bytes).hexdigest()[:16]
                return img_bytes, img_hash
        else:
            img_hash = hashlib.md5(img_bytes).hexdigest()[:16] if img_bytes else ""
            return img_bytes, img_hash

    def _hash_distance(self, h1: str, h2: str) -> int:
        if not h1 or not h2 or len(h1) != len(h2):
            return 999
        try:
            return sum(c1 != c2 for c1, c2 in zip(h1, h2))
        except Exception:
            return 999

    def _hash_changed(self, new_hash: str) -> bool:
        if not self._last_image_hash or not new_hash:
            return True
        return self._hash_distance(new_hash, self._last_image_hash) > self.hash_similarity

    # ── Tier 1: 窗口标题检测 ──

    @staticmethod
    def _get_active_window_title() -> str:
        """获取当前活跃窗口标题 — 零 token 消耗。"""
        if _IS_WINDOWS:
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value.strip()
            except Exception:
                pass
        else:
            try:
                import subprocess

                r = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                return r.stdout.strip()
            except Exception:
                pass
        return ""

    @staticmethod
    def _guess_activity_from_window(title: str) -> tuple[str, list[str], str]:
        """
        从窗口标题推算活动类型。
        返回 (activity, apps, mood_hint)
        """
        t = title.lower() if title else ""
        apps: list[str] = []

        # IDE / 编辑器
        code_indicators = [
            "visual studio code",
            "vscode",
            "pycharm",
            "intellij",
            "webstorm",
            "sublime text",
            "notepad++",
            "neovim",
            "vim",
            "atom",
            "cursor",
            "windsurf",
        ]
        terminal_indicators = [
            "terminal",
            "powershell",
            "cmd",
            "命令提示符",
            "终端",
            "alacritty",
            "kitty",
            "wezterm",
            "windows terminal",
        ]
        game_indicators = [
            "steam",
            "game",
            "游戏",
            "league of legends",
            "英雄联盟",
            "genshin",
            "原神",
            "star rail",
            "崩坏",
            "valorant",
            "elden ring",
            "dota",
            "minecraft",
            "我的世界",
        ]
        video_indicators = [
            "youtube",
            "bilibili",
            "netflix",
            "twitch",
            "播放",
            "video",
            "media player",
            "potplayer",
            "vlc",
        ]
        chat_indicators = ["discord", "微信", "wechat", "qq", "telegram", "slack", "line", "signal", "messages"]
        browser_indicators = ["chrome", "firefox", "edge", "safari", "opera", "brave", "arc", "浏览器"]
        doc_indicators = ["pdf", "word", "excel", "ppt", "文档", "wps", "libreoffice", "notion", "obsidian", "typora"]

        for kw in code_indicators:
            if kw in t:
                apps.append("编辑器")
                return ("coding", apps, "认真")
        for kw in terminal_indicators:
            if kw in t:
                apps.append("终端")
                return ("coding", apps, "认真")
        for kw in game_indicators:
            if kw in t:
                apps.append("游戏")
                return ("gaming", apps, "专注")
        for kw in video_indicators:
            if kw in t:
                apps.append("视频")
                return ("video", apps, "休闲")
        for kw in chat_indicators:
            if kw in t:
                apps.append("聊天")
                return ("chat", apps, "社交")
        for kw in doc_indicators:
            if kw in t:
                apps.append("文档")
                return ("reading", apps, "平静")
        for kw in browser_indicators:
            if kw in t:
                apps.append("浏览器")
                # 浏览器窗口本身没有更具体的活动线索时，归类为浏览网页。
                # 之前在循环后无条件返回 unknown，导致 Edge/Chrome 即使被
                # 识别出 apps=["浏览器"] 仍显示“未知窗口”。
                return ("browsing", apps, "放松")

        if not t:
            return ("idle", apps, "放空")

        return ("unknown", apps, "")

    # ── Tier 2+3: 视觉模型分析 ──

    async def _analyze_with_vision(self, tier: int = 2) -> str:
        """
        调用视觉模型分析截图。

        Tier 2: 轻量 prompt，只问「在做什么」，token 少
        Tier 3: 完整 prompt，问描述+元素+情绪
        """
        import json

        self._last_vision_time = time.time()
        self._vision_count_today += 1
        self._light_count_since_vision = 0

        if tier == 2:
            query = "请用一句话描述：用户正在做什么（编程/游戏/浏览/视频/聊天/阅读/空闲）？用中文。"
        else:
            query = (
                "请描述屏幕上显示的内容。关注："
                "1. 用户正在做什么？"
                "2. 有哪些应用窗口？"
                "3. 有什么值得注意的元素？"
                "4. 推测用户情绪。"
                "用简洁中文，每项一行。"
            )

        try:
            from mcpserver.screen_vision.service import ScreenVisionService

            svc = ScreenVisionService()
            result = await svc._look_screen({"query": query, "compress": True})
            parsed = json.loads(result)
            return parsed.get("message", "")
        except Exception as exc:
            logger.warning(f"[ScreenAware] 视觉分析失败: {exc}")
            return ""

    # ── Tier 15: 本地 OCR 识字 ──

    @staticmethod
    def _has_ocr_models(models_dir: Path) -> bool:
        """检查目录下是否包含完整的 PaddleOCR 模型"""
        required = [
            "PP-LCNet_x1_0_doc_ori",
            "PP-LCNet_x1_0_textline_ori",
            "PP-OCRv5_server_det",
            "PP-OCRv5_server_rec",
            "UVDoc",
        ]
        official = models_dir / "official_models"
        return all((official / d).exists() for d in required)

    def _lazy_init_ocr(self) -> Any:
        if self._ocr_engine is not None:
            return self._ocr_engine
        if not self._ocr_enabled or self._ocr_loading:
            return None

        elapsed = time.time() - self._init_time
        if elapsed < self._ocr_grace:
            logger.debug(f"[ScreenAware] OCR 启动宽限期内 ({elapsed:.0f}s/{self._ocr_grace:.0f}s)，延迟加载")
            return None

        self._ocr_loading = True
        try:
            import threading

            def _load_ocr():
                try:
                    engine = self._init_paddle_ocr()
                    self._ocr_engine = engine
                    logger.info("[ScreenAware] PaddleOCR 本地引擎后台初始化完成")
                except Exception as exc:
                    global _OCR_INIT_WARNED
                    if not _OCR_INIT_WARNED:
                        logger.warning(f"[ScreenAware] PaddleOCR 后台初始化失败: {exc}")
                        _OCR_INIT_WARNED = True
                    self._ocr_enabled = False
                finally:
                    self._ocr_loading = False

            threading.Thread(target=_load_ocr, daemon=True, name="PaddleOCR-Loader").start()
            # 真正的懒加载：不在观察线程里 join，等待后续观察周期自然复用已加载引擎。
            return None
        except Exception as exc:
            global _OCR_INIT_WARNED
            if not _OCR_INIT_WARNED:
                logger.warning(f"[ScreenAware] PaddleOCR 初始化失败: {exc}")
                _OCR_INIT_WARNED = True
            self._ocr_enabled = False
            self._ocr_loading = False
        return self._ocr_engine

    def _init_paddle_ocr(self) -> Any:
        """实际初始化 PaddleOCR（在后台线程中调用）"""
        global _OCR_INIT_WARNED

        _project_models = (
            Path(self._model_dir)
            if self._model_dir
            else (Path(__file__).resolve().parent.parent.parent.parent / "models" / "paddle_ocr")
        )
        _system_cache = Path.home() / ".paddlex"

        if self._has_ocr_models(_system_cache):
            logger.debug("[ScreenAware] 使用系统 PaddleX 缓存模型")
        elif self._has_ocr_models(_project_models):
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(_project_models))
            logger.info(f"[ScreenAware] 系统缓存缺失，回退到项目模型: {_project_models}")
        else:
            logger.warning("[ScreenAware] 未找到本地 OCR 模型，可能需联网下载")

        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        from paddleocr import PaddleOCR

        return PaddleOCR(lang="ch")

    def _analyze_with_ocr(self, img_bytes: bytes) -> tuple[str, float]:
        """
        本地 OCR 识字。零 token、零网络。

        返回 (extracted_text, confidence)
        """
        engine = self._lazy_init_ocr()
        if engine is None:
            return "", 0.0

        try:
            img = Image.open(io.BytesIO(img_bytes))
            result = engine.ocr(__import__("numpy").array(img), cls=False)

            if not result or not result[0]:
                return "", 0.0

            texts: list[str] = []
            confidences: list[float] = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = str(line[1][0]) if line[1] else ""
                    conf = float(line[1][1]) if len(line[1]) > 1 else 0.0
                    if text and len(text.strip()) >= 2:
                        texts.append(text.strip())
                        confidences.append(conf)

            combined = " ".join(texts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return combined, avg_conf
        except Exception as exc:
            logger.debug(f"[ScreenAware] OCR 分析失败: {exc}")
            return "", 0.0

    @staticmethod
    def _classify_from_ocr_text(ocr_text: str) -> tuple[str, list[str], str, float]:
        """
        从 OCR 提取的文字推断活动类型。零 token。

        返回 (activity, apps, mood, confidence)
        """
        t = ocr_text.lower() if ocr_text else ""

        classifiers: dict[str, tuple[list[str], list[str], str]] = {
            "coding": (
                [
                    "def ",
                    "class ",
                    "function",
                    "import ",
                    "const ",
                    "let ",
                    "var ",
                    "return",
                    "async ",
                    "await ",
                    "print(",
                    "console.",
                    "self.",
                    "this.",
                    ".py",
                    ".js",
                    ".ts",
                    ".go",
                    ".rs",
                    "{",
                    "}",
                ],
                ["编辑器", "IDE", "终端"],
                "认真",
            ),
            "gaming": (
                [
                    "hp",
                    "mp",
                    "level",
                    "attack",
                    "防御",
                    "攻击力",
                    "血量",
                    "伤害",
                    "任务",
                    "quest",
                    "inventory",
                    "装备",
                    "技能",
                    "经验",
                    "exp",
                    "fps",
                    "ping",
                    "latency",
                    "k/d",
                ],
                ["游戏"],
                "专注",
            ),
            "browsing": (
                ["http", "www.", ".com", ".cn", ".org", "搜索", "百度", "google", "新闻", "github", "首页"],
                ["浏览器"],
                "放松",
            ),
            "video": (
                ["订阅", "subscribe", "点赞", "弹幕", "播放量", "评论", "分享", "关注", "视频", "直播"],
                ["视频"],
                "休闲",
            ),
            "chat": (
                ["在吗", "哈哈", "嗯嗯", "好的", "收到", "ok", "哈哈哈", "表情", "图片", "文件", "@"],
                ["聊天"],
                "社交",
            ),
            "reading": (
                ["第", "章", "节", "页", "摘要", "引言", "结论", "参考文献", "目录", "前言"],
                ["文档"],
                "平静",
            ),
        }

        scores: dict[str, float] = {}
        for activity, (keywords, apps, mood) in classifiers.items():
            matched = sum(1.0 for kw in keywords if kw in t)
            ratio = matched / max(len(keywords), 1)
            scores[activity] = ratio

        if not scores or max(scores.values()) < 0.02:
            if not t or len(t) < 10:
                return ("idle", [], "放空", 0.3)
            return ("browsing", [], "放松", 0.15)

        best = max(scores, key=scores.get)
        best_score = scores[best]
        _, best_apps, best_mood = classifiers[best]
        confidence = max(0.1, min(1.0, best_score * 2.5))

        return (best, list(best_apps), best_mood, confidence)

    # ── 主观察方法 ──

    async def observe(self, *, allow_vision: bool = False) -> ScreenObservation:
        """
        混合感知观察 v2.2。

        allow_vision=False（默认）: 只用 Tier 0/1/15，零 token
        allow_vision=True: 允许 Tier 2/3 视觉模型（仅当佳主动要求时）
        """
        t0 = time.monotonic()
        logger.info(f"[弥娅之眼] 开始观察 (mode={self.vision_mode})...")

        obs = ScreenObservation()

        try:
            img_bytes, img_hash = self._capture_and_hash()
            obs.image_hash = img_hash
            window_title = self._get_active_window_title()
            logger.info(f"[弥娅之眼] 窗口: '{window_title[:60]}', hash_changed={self._hash_changed(img_hash)}")

            changed = self._hash_changed(img_hash)
            gu_activity, gu_apps, gu_mood = self._guess_activity_from_window(window_title)
            obs.window_title = window_title

            # 不过滤任何窗口 — 弥娅看见一切

            self._last_observe_time = time.time()

            last_activity = self._activity_history[-1][1] if self._activity_history else ""
            activity_changed = gu_activity != last_activity
            # 首次观察不触发视觉模型，allow_vision=False 时也禁止
            is_first = len(self._activity_history) == 0
            use_vision = allow_vision and (not is_first) and self._should_use_vision(activity_changed)

            if use_vision:
                tier = 3 if activity_changed else 2
                obs.analysis_tier = tier
                obs.raw_response = await self._analyze_with_vision(tier)

                if obs.raw_response:
                    self._parse_observation(obs)
                else:
                    self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
            elif changed:
                self._light_count_since_vision += 1

                window_confident = (
                    gu_activity != "browsing" or len(gu_apps) >= 1 or (window_title and len(window_title) > 4)
                )

                if self.vision_mode == "api_only":
                    if window_confident:
                        obs.analysis_tier = 1
                        self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
                    elif allow_vision and self._should_use_vision(activity_changed):
                        obs.analysis_tier = 3
                        obs.raw_response = await self._analyze_with_vision(3)
                        if obs.raw_response:
                            self._parse_observation(obs)
                        else:
                            self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
                    else:
                        obs.analysis_tier = 1
                        self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)

                elif self.vision_mode == "ocr_only":
                    # OCR  →
                    ocr_text, ocr_conf = self._analyze_with_ocr(img_bytes)
                    ocr_activity, ocr_apps, ocr_mood, ocr_confidence = self._classify_from_ocr_text(ocr_text)
                    obs.ocr_text = ocr_text[:300]
                    if ocr_confidence > 0.15 and ocr_text:
                        obs.analysis_tier = 15
                        obs.detected_activity = ocr_activity
                        obs.detected_apps = ocr_apps or gu_apps
                        obs.mood_hint = ocr_mood or gu_mood
                        obs.description = f"OCR: {ocr_text[:120]}"
                        obs.attention_score = max(0.15, ocr_confidence * 0.6)
                    else:
                        obs.analysis_tier = 1
                        self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)

                else:  # hybrid
                    if window_confident:
                        obs.analysis_tier = 1
                        self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
                    else:
                        ocr_text, ocr_conf = self._analyze_with_ocr(img_bytes)
                        obs.ocr_text = ocr_text[:300]
                        ocr_activity, ocr_apps, ocr_mood, ocr_confidence = self._classify_from_ocr_text(ocr_text)
                        if ocr_confidence > 0.2 and ocr_text:
                            obs.analysis_tier = 15
                            obs.detected_activity = ocr_activity
                            obs.detected_apps = ocr_apps or gu_apps
                            obs.mood_hint = ocr_mood or gu_mood
                            obs.description = f"OCR: {ocr_text[:120]}"
                            obs.attention_score = max(0.15, ocr_confidence * 0.6)
                        elif allow_vision and self._should_use_vision(activity_changed):
                            obs.analysis_tier = 2
                            obs.raw_response = await self._analyze_with_vision(2)
                            if obs.raw_response:
                                self._parse_observation(obs)
                            else:
                                self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
                        else:
                            obs.analysis_tier = 1
                            self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)
            else:
                obs.analysis_tier = 0
                prev = self._observations[-1] if self._observations else None
                if prev:
                    obs.detected_activity = prev.detected_activity
                    obs.detected_apps = list(prev.detected_apps)
                    obs.mood_hint = prev.mood_hint
                    obs.description = f"(画面未变化) {prev.description}"
                    obs.attention_score = prev.attention_score * 0.5
                    obs.proactive_trigger_score = 0.05
                else:
                    self._apply_light_result(obs, gu_activity, gu_apps, gu_mood, window_title)

            if img_hash and gu_activity:
                self._hash_cache[img_hash] = gu_activity
            self._last_screenshot_bytes = img_bytes
            self._last_image_hash = img_hash

            if activity_changed:
                obs.proactive_trigger_score = max(obs.proactive_trigger_score, 0.55)

            self._update_adaptive_framerate(obs)
            self._activity_history.append((time.time(), obs.detected_activity))
            if len(self._activity_history) > 200:
                self._activity_history = self._activity_history[-200:]

            self._observations.append(obs)
            if len(self._observations) > self.max_history:
                self._observations = self._observations[-self.max_history :]

            # 终端的可见日志 — 弥娅的内心独白
            tier_mark = {0: "⏭ 复用", 1: "🪟 窗口", 15: "📖 识字", 2: "👁 一瞥", 3: "🔍 细看"}.get(
                obs.analysis_tier, "❓"
            )
            act_desc = {
                "coding": ("写代码", "代码编辑器里敲着键盘"),
                "gaming": ("玩游戏", "沉浸在游戏世界里"),
                "browsing": ("浏览网页", "在网上随意看着"),
                "video": ("看视频", "看着屏幕上的画面"),
                "chat": ("聊天", "和人聊着天"),
                "reading": ("阅读", "静静地读着东西"),
                "idle": ("空闲", "屏幕安静着"),
                "unknown": ("未知窗口", f"窗口: {obs.window_title[:40]}" if obs.window_title else ""),
            }
            cn, detail = act_desc.get(obs.detected_activity, (obs.detected_activity, obs.detected_activity))
            mood_text = obs.mood_hint or ""
            app_hint = f" · {', '.join(obs.detected_apps[:2])}" if obs.detected_apps else ""

            speaks = ""
            if obs.proactive_trigger_score >= self.proactive_threshold:
                if obs.analysis_tier >= 2 and obs.description:
                    glimpse = obs.description[:60].replace("\n", " ")
                    speaks = f"\n    ↳ 弥娅心想: 「{glimpse}...」"
                else:
                    acts = self.get_activity_trend()
                    if len(acts) >= 2 and acts[-1]["activity"] != acts[-2]["activity"]:
                        prev = act_desc.get(
                            acts[-2]["activity"],
                            (acts[-2]["activity"], acts[-2]["activity"]),
                        )[0]
                        speaks = f"\n    ↳ 弥娅注意到: 佳从 {prev} 换到了 {cn}"

            logger.info(
                f"[弥娅之眼] {tier_mark} 佳在{cn}{app_hint} · {detail}{mood_text and ' · 看起来' + mood_text}{speaks}"
            )
        except Exception as exc:
            logger.warning(f"[ScreenAware] 观察失败: {exc}")
            obs.description = f"观察失败: {exc}"
            obs.detected_activity = "unknown"

        obs.timestamp = time.time()
        return obs

    def _apply_light_result(
        self, obs: ScreenObservation, activity: str, apps: list[str], mood: str, title: str
    ) -> None:
        obs.detected_activity = activity
        obs.detected_apps = list(apps)
        obs.mood_hint = mood
        obs.description = f"窗口: {title}" if title else f"活动: {activity}"
        obs.attention_score = {
            "gaming": 0.45,
            "coding": 0.40,
            "browsing": 0.25,
            "video": 0.30,
            "chat": 0.20,
            "reading": 0.22,
            "idle": 0.08,
        }.get(activity, 0.20)
        obs.proactive_trigger_score = 0.08

    def _parse_observation(self, obs: ScreenObservation) -> None:
        text = obs.raw_response.lower() if obs.raw_response else ""

        activities = {
            "coding": ["编程", "写代码", "代码", "编辑器", "ide", "vscode", "terminal", "终端"],
            "gaming": ["游戏", "玩游戏", "steam", "game", "角色"],
            "browsing": ["浏览器", "浏览", "网页", "搜索", "阅读"],
            "video": ["视频", "播放", "youtube", "bilibili", "直播"],
            "chat": ["聊天", "消息", "对话", "微信", "qq", "discord"],
            "reading": ["阅读", "文档", "文章", "pdf", "看书"],
            "idle": ["空闲", "桌面", "屏保", "锁屏", "安静"],
        }
        scores = {}
        for activity, keywords in activities.items():
            score = sum(1.0 for kw in keywords if kw in text) / max(len(keywords), 1)
            scores[activity] = score

        best = max(scores, key=scores.get)
        obs.detected_activity = best if scores[best] > 0.06 else "browsing"

        apps_keywords = ["浏览器", "编辑器", "终端", "聊天", "游戏", "播放器", "文档"]
        obs.detected_apps = [kw for kw in apps_keywords if kw in text]

        obs.attention_score = max(0.0, min(1.0, scores[best] * 0.55))

    def _update_adaptive_framerate(self, obs: ScreenObservation) -> None:
        if not self.adaptive_framerate:
            return
        intervals = {
            "idle": self.min_interval * 3.5,
            "reading": self.min_interval * 2.5,
            "chat": self.min_interval * 2.0,
            "browsing": self.min_interval * 1.5,
            "video": self.min_interval * 1.2,
            "coding": self.min_interval * 0.8,
            "gaming": self.min_interval * 1.0,
        }
        self._current_interval = intervals.get(obs.detected_activity, self.min_interval)

    # ── 主动意图 ──

    def should_proactive(self) -> ProactiveIntent | None:
        if not self._observations:
            return None

        latest = self._observations[-1]
        if latest.proactive_trigger_score < self.proactive_threshold:
            return None
        if (time.time() - self._last_proactive_time) < self.min_interval * 2:
            return None

        self._last_proactive_time = time.time()

        return ProactiveIntent(
            intent_id=f"screen_{int(time.time())}",
            trigger_type=("activity_change" if self._is_activity_change() else "screen_content"),
            description=f"看到佳在{latest.detected_activity}",
            priority=latest.proactive_trigger_score,
            suggested_topic=self._suggest_topic(latest),
            suggested_tone=self._suggest_tone(latest),
            observation=latest,
        )

    def _is_activity_change(self) -> bool:
        if len(self._activity_history) < 2:
            return False
        return self._activity_history[-2][1] != self._activity_history[-1][1]

    def _suggest_topic(self, obs: ScreenObservation) -> str:
        return {
            "coding": "佳在写代码呢，可以问问他在做什么项目",
            "gaming": "佳在玩游戏，可以评论一下画面或操作",
            "browsing": "佳在看网页，可以问他在找什么",
            "video": "佳在看视频，可以问他在看什么有趣的",
            "chat": "佳在聊天，不要打扰",
            "reading": "佳在阅读，可以静静陪着",
            "idle": "佳好像在想事情，可以温柔地问一下",
        }.get(obs.detected_activity, "看到佳在忙，可以轻声问候一下")

    def _suggest_tone(self, obs: ScreenObservation) -> str:
        return {
            "coding": "casual",
            "gaming": "excited",
            "browsing": "curious",
            "video": "casual",
            "chat": "",
            "reading": "gentle",
            "idle": "concerned",
        }.get(obs.detected_activity, "casual")

    # ── 查询 ──

    def get_last_observation(self) -> Optional[ScreenObservation]:
        return self._observations[-1] if self._observations else None

    def get_activity_trend(self) -> list[dict]:
        return [{"time": t, "activity": a} for t, a in self._activity_history[-20:]]

    def build_timeline_card(self, max_entries: int = 8) -> str:
        """生成最简感官卡片 — 不加判断，原样给AI"""
        from datetime import datetime

        entries = self._observations[-max_entries:] if self._observations else []
        if not entries:
            return ""

        lines = ["[弥娅看到的画面]"]
        for e in entries:
            t = datetime.fromtimestamp(e.timestamp).strftime("%H:%M:%S")
            w = (e.window_title or "未知").strip()
            lines.append(f"- {t} 「{w[:60]}」")
            if e.ocr_text:
                lines.append(f"  OCR: {e.ocr_text[:200]}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def get_stats(self) -> dict:
        return {
            "total_observations": len(self._observations),
            "vision_calls_today": self._vision_count_today,
            "vision_quota_remaining": max(0, self.vision_daily_quota - self._vision_count_today),
            "light_count_since_vision": self._light_count_since_vision,
            "ocr_available": self._ocr_enabled and self._ocr_engine is not None,
            "current_interval": self._current_interval,
            "tier_distribution": {
                str(t): sum(1 for o in self._observations[-100:] if o.analysis_tier == t) for t in (0, 1, 15, 2, 3)
            },
        }

    def to_ap_state_items(self) -> list[dict]:
        if not self._observations:
            return []

        latest = self._observations[-1]
        items: list[dict] = []

        items.append(
            {
                "label": "miya::screen_activity",
                "value": latest.detected_activity,
                "energy": max(0.1, latest.attention_score),
                "source": "screen_aware",
                "timestamp": latest.timestamp,
            }
        )
        items.append(
            {
                "label": "miya::screen_proactive_drive",
                "value": latest.proactive_trigger_score,
                "energy": max(0.1, latest.proactive_trigger_score * 0.8),
                "source": "screen_aware",
                "timestamp": latest.timestamp,
            }
        )
        for app in latest.detected_apps[:4]:
            items.append(
                {
                    "label": f"miya::screen_app_{app}",
                    "value": app,
                    "energy": 0.3,
                    "source": "screen_aware",
                    "timestamp": latest.timestamp,
                }
            )
        items.append(
            {
                "label": "miya::screen_mood",
                "value": latest.mood_hint,
                "energy": 0.25,
                "source": "screen_aware",
                "timestamp": latest.timestamp,
            }
        )

        return items


_global_screen_aware: Optional[ScreenAwareProactive] = None


def get_screen_aware(**kwargs) -> ScreenAwareProactive:
    global _global_screen_aware
    if _global_screen_aware is None:
        _global_screen_aware = ScreenAwareProactive(**kwargs)
    elif kwargs:
        if "vision_mode" in kwargs:
            _global_screen_aware.set_vision_mode(kwargs["vision_mode"])
        if "enabled" in kwargs:
            _global_screen_aware.enabled = kwargs["enabled"]
    return _global_screen_aware
