#!/usr/bin/env python3
"""
屏幕视觉 MCP 服务 — 让弥娅「看到」用户屏幕

截取用户屏幕，用视觉 LLM 分析内容。
"""

import json
import logging
import time
from typing import Any

from .screenshot_provider import (
    compress_screenshot_data_url,
    get_screenshot_provider,
)

logger = logging.getLogger("screen_vision.service")


class ScreenVisionService:
    """屏幕视觉 MCP 服务"""

    def __init__(self):
        self.name = "screen_vision"
        self.description = "屏幕视觉 - 截图 + AI 分析屏幕内容"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: dict[str, Any]) -> str:
        tool_name = str(tool_call.get("tool_name", "")).strip()

        try:
            if tool_name == "look_screen":
                return await self._look_screen(tool_call)
            elif tool_name == "screenshot":
                return await self._screenshot(tool_call)
            else:
                return json.dumps(
                    {
                        "error": f"未知工具: {tool_name}",
                        "available": ["look_screen", "screenshot"],
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.exception(f"[ScreenVision] 工具调用异常: {tool_name}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ===== look_screen =====

    async def _look_screen(self, call: dict[str, Any]) -> str:
        query = str(
            call.get("query")
            or call.get("content")
            or call.get("message")
            or "请描述屏幕上显示的内容，包括窗口、文字、按钮、图片等所有可见元素。"
        ).strip()

        compress = call.get("compress", True)
        if isinstance(compress, str):
            compress = compress.lower() not in ("false", "0", "no")

        t_start = time.monotonic()

        # 1. 截图
        try:
            t0 = time.monotonic()
            screenshot = get_screenshot_provider().capture_data_url()
            t_cap = time.monotonic() - t0
            logger.info(
                f"[ScreenVision] 截图: {t_cap:.2f}s, {screenshot.width}x{screenshot.height}, {screenshot.source}"
            )
        except Exception as exc:
            logger.error(f"[ScreenVision] 截图失败: {exc}")
            return json.dumps({"status": "error", "message": f"截图失败: {exc}"}, ensure_ascii=False)

        # 2. 压缩
        if compress:
            try:
                t0 = time.monotonic()
                raw_len = len(screenshot.data_url)
                image_url = compress_screenshot_data_url(screenshot.data_url, max_width=1280, quality=80)
                compressed_len = len(image_url)
                t_compress = time.monotonic() - t0
                logger.info(f"[ScreenVision] 压缩: {t_compress:.2f}s, {raw_len // 1024}KB → {compressed_len // 1024}KB")
            except Exception as exc:
                logger.warning(f"[ScreenVision] 压缩失败，使用原图: {exc}")
                image_url = screenshot.data_url
        else:
            image_url = screenshot.data_url

        # 3. 视觉 LLM 分析
        try:
            t0 = time.monotonic()
            description = await self._analyze_with_miya_vision(query, image_url)
            t_llm = time.monotonic() - t0
            logger.info(f"[ScreenVision] AI 分析: {t_llm:.2f}s")
        except Exception as exc:
            logger.error(f"[ScreenVision] AI 分析失败: {exc}")
            return json.dumps(
                {
                    "status": "partial",
                    "message": f"截图成功但 AI 分析失败: {exc}",
                    "screenshot": image_url[:100] + "... (已截取)",
                },
                ensure_ascii=False,
            )

        t_total = time.monotonic() - t_start
        logger.info(f"[ScreenVision] 总耗时: {t_total:.2f}s (截图={t_cap:.2f}s + 压缩=...s + LLM={t_llm:.2f}s)")

        return json.dumps(
            {
                "status": "success",
                "message": description,
                "source": screenshot.source,
                "width": screenshot.width,
                "height": screenshot.height,
            },
            ensure_ascii=False,
        )

    # ===== screenshot only =====

    async def _screenshot(self, call: dict[str, Any]) -> str:
        compress = call.get("compress", True)
        if isinstance(compress, str):
            compress = compress.lower() not in ("false", "0", "no")

        try:
            screenshot = get_screenshot_provider().capture_data_url()
        except Exception as exc:
            return json.dumps({"status": "error", "message": f"截图失败: {exc}"}, ensure_ascii=False)

        if compress:
            try:
                image_url = compress_screenshot_data_url(screenshot.data_url)
            except Exception:
                image_url = screenshot.data_url
        else:
            image_url = screenshot.data_url

        return json.dumps(
            {
                "status": "success",
                "message": "截图完成",
                "screenshot": image_url[:200] + f"... ({len(image_url)} 字符)",
                "source": screenshot.source,
                "width": screenshot.width,
                "height": screenshot.height,
            },
            ensure_ascii=False,
        )

    # ===== 弥娅视觉 LLM =====

    async def _analyze_with_miya_vision(self, query: str, image_url: str) -> str:
        """
        用弥娅模型池中的视觉模型分析截图。

        优先通过 model-bridge MCP 获取 vision 模型配置，
        回退到 multi_model_config.json 中激活的模型。
        """
        system_prompt = (
            "你是一个屏幕视觉助手。用户会给你一张屏幕截图，请根据用户的问题分析截图内容。"
            "描述要准确、简洁，重点关注用户问题相关的内容。"
            "如果用户没有具体问题，请描述屏幕上可见的主要元素：打开的窗口、文字内容、按钮、图标等。"
            "用中文回答。"
        )

        # 优先走 model-bridge
        api_key, base_url, model_id = self._resolve_vision_model()

        # 调用
        import httpx

        base_url = base_url.rstrip("/")

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            )

            if response.status_code != 200:
                raise RuntimeError(f"视觉 LLM 返回 {response.status_code}: {response.text[:500]}")

            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "无法分析截图")

    def _resolve_vision_model(self) -> tuple[str, str, str]:
        """
        从 multi_model_config.json 的 vision_preferences 获取视觉模型配置。

        读取 env_key → 环境变量获取 api_key，而不是直接读 api_key 字段。
        """
        import json
        from pathlib import Path

        from config.config_utils import get_api_key

        miya_root = Path(__file__).resolve().parent.parent.parent
        cfg_path = miya_root / "config" / "multi_model_config.json"

        if not cfg_path.exists():
            raise RuntimeError("[ScreenVision] 模型配置文件不存在: multi_model_config.json")

        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            models = cfg.get("models", {})
            vision_prefs = cfg.get("vision_preferences", {}).get("model_preferences", {})

            # 试 primary → secondary 顺序
            for key in [vision_prefs.get("primary"), vision_prefs.get("secondary")]:
                if not key or key not in models:
                    continue
                m = models[key]
                env_key = m.get("env_key", "")
                api_key = get_api_key(env_key) if env_key else ""
                base_url = m.get("base_url", "")
                model_name = m.get("name", "")

                if api_key and model_name:
                    logger.info(f"[ScreenVision] 使用视觉模型: {key} → {model_name} @ {base_url}")
                    return api_key, base_url, model_name
                else:
                    logger.warning(f"[ScreenVision] 模型 {key} 缺少 api_key (env:{env_key}) 或 name")

            # 回退：找一个 type=vision 或 capabilities 含 vision 的
            for model_key, m in models.items():
                if m.get("type") == "vision" or "vision" in m.get("capabilities", []):
                    env_key = m.get("env_key", "")
                    api_key = get_api_key(env_key) if env_key else ""
                    if api_key:
                        logger.info(f"[ScreenVision] 回退视觉模型: {model_key}")
                        return api_key, m.get("base_url", ""), m.get("name", "")

        except Exception as e:
            logger.error(f"[ScreenVision] 解析模型配置失败: {e}")

        raise RuntimeError(
            "[ScreenVision] 未找到可用的视觉模型。请在 multi_model_config.json 中配置 vision_preferences"
        )
