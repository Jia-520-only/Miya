#!/usr/bin/env python3
"""
屏幕视觉 MCP 服务 — 让弥娅「看到」用户屏幕

截取用户屏幕，用视觉 LLM 分析内容。
"""

import json
import logging
import time
import base64
import binascii
from typing import Any

from .screenshot_provider import (
    compress_screenshot_data_url,
    get_screenshot_provider,
)
from .local_camera import (
    analyze_local_frame,
    delete_identity,
    discover_local_camera_capabilities,
    enroll_identity,
    list_identities,
    local_only_error,
)
from .local_screen import analyze_local_screen

logger = logging.getLogger("screen_vision.service")


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _validate_camera_image(image_url: str) -> str | None:
    header, separator, payload = image_url.partition(",")
    mime = header.removeprefix("data:").split(";", 1)[0].lower()
    if not separator or mime not in {"image/jpeg", "image/png", "image/webp"} or ";base64" not in header:
        return "缺少有效的摄像头画面，只接受 JPEG、PNG 或 WebP base64 图片。"
    if len(image_url) > 12_000_000:
        return "摄像头画面过大。"
    try:
        decoded_size = len(base64.b64decode(payload, validate=True))
    except (binascii.Error, ValueError):
        return "摄像头画面编码无效。"
    if decoded_size > 8 * 1024 * 1024:
        return "摄像头画面过大。"
    return None


class ScreenVisionService:
    """屏幕视觉 MCP 服务"""

    def __init__(self):
        self.name = "screen_vision"
        self.description = "统一视觉调度 - 本地 OCR/姿态/身份能力与云端视觉模型"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: dict[str, Any]) -> str:
        tool_name = str(tool_call.get("tool_name", "")).strip()

        try:
            if tool_name == "look_screen":
                return await self._look_screen(tool_call)
            elif tool_name == "look_both":
                return await self._look_both(tool_call)
            elif tool_name == "look_me":
                return await self._look_me(tool_call)
            elif tool_name == "camera_look":
                return await self._camera_look(tool_call)
            elif tool_name == "camera_capabilities":
                return await self._camera_capabilities()
            elif tool_name == "camera_analyze_local":
                return await self._camera_analyze_local(tool_call)
            elif tool_name == "camera_event":
                return self._camera_event(tool_call)
            elif tool_name == "camera_enroll_identity":
                return await self._camera_enroll_identity(tool_call)
            elif tool_name == "camera_list_identities":
                return json.dumps(list_identities(), ensure_ascii=False)
            elif tool_name == "camera_delete_identity":
                return json.dumps(delete_identity(str(tool_call.get("identity_id", ""))), ensure_ascii=False)
            elif tool_name == "request_camera_observation":
                return await self._request_camera_observation(tool_call)
            elif tool_name == "screenshot":
                return await self._screenshot(tool_call)
            else:
                return json.dumps(
                    {
                        "error": f"未知工具: {tool_name}",
                        "available": ["look_screen", "look_me", "camera_look", "look_both", "camera_capabilities", "camera_analyze_local", "camera_enroll_identity", "camera_list_identities", "camera_delete_identity", "screenshot"],
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

        route = self._vision_mode("screen")
        local_result: dict[str, Any] | None = None
        screenshot = None
        if route in {"local", "hybrid"}:
            try:
                screenshot = get_screenshot_provider().capture_data_url()
                local_result = analyze_local_screen(screenshot.data_url)
            except Exception as exc:
                logger.info("[ScreenVision] 本地屏幕 OCR 不可用: %s", exc)
                local_result = {"status": "unavailable", "message": f"本地 OCR 不可用：{exc}", "persisted": False}
            if route == "local":
                if local_result.get("status") == "success":
                    self._record_screen_result(local_result, query=query, mode="local")
                return json.dumps(local_result, ensure_ascii=False)

        t_start = time.monotonic()

        # 1. 截图
        try:
            t0 = time.monotonic()
            if screenshot is None:
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
            model_query = query
            if route == "hybrid" and local_result and local_result.get("status") == "success":
                ocr_text = str(local_result.get("ocr_text") or local_result.get("message") or "").strip()
                if ocr_text:
                    model_query = f"{query}\n\n本地 OCR 识别到的文字（供参考）：{ocr_text[:4000]}"
            description = await self._analyze_with_miya_vision(model_query, image_url)
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

        result = {
                "status": "success",
                "message": description,
                "source": screenshot.source,
                "width": screenshot.width,
                "height": screenshot.height,
            }
        self._record_screen_result(result, query=query, mode="cloud")
        return json.dumps(result, ensure_ascii=False)

    async def _look_me(self, call: dict[str, Any]) -> str:
        """Analyze one explicitly supplied camera frame without persisting it."""
        image_url = str(call.get("image_data") or call.get("image_url") or "").strip()
        validation_error = _validate_camera_image(image_url)
        if validation_error:
            return json.dumps({"status": "error", "message": validation_error}, ensure_ascii=False)

        query = str(
            call.get("query")
            or "请描述画面中可见的人、姿态、动作和环境，只说可以从画面确认的内容。"
        ).strip()[:2000]
        route = self._camera_analysis_mode()
        force_local = _as_bool(call.get("local_only", False)) or route == "local"
        if force_local or route == "hybrid":
            capabilities = discover_local_camera_capabilities()
            required = capabilities.get("features", {})
            identity_requested = bool(call.get("identity", True))
            pose_requested = bool(call.get("pose", True))
            requested = []
            if identity_requested or bool(call.get("emotion", False)):
                requested.append("face_detection")
            if identity_requested:
                requested.append("identity")
            if bool(call.get("emotion", False)):
                requested.append("emotion")
            if pose_requested:
                requested.append("pose")
            if not all(required.get(name, {}).get("available", False) for name in requested):
                if force_local:
                    return json.dumps(local_only_error(), ensure_ascii=False)
            else:
                try:
                    local_result = analyze_local_frame(
                        image_url,
                        identity=bool(call.get("identity", True)),
                        emotion=bool(call.get("emotion", False)),
                        pose=pose_requested,
                        pose_history=call.get("pose_history") if isinstance(call.get("pose_history"), list) else None,
                    )
                    if force_local or local_result.get("status") == "success":
                        self._record_camera_result(local_result, call, mode="local")
                        return json.dumps(local_result, ensure_ascii=False)
                except (ValueError, FileNotFoundError, RuntimeError) as exc:
                    logger.info("[ScreenVision] 本地摄像头分析不可用: %s", exc)
                    if force_local:
                        return json.dumps(local_only_error(), ensure_ascii=False)
        try:
            compressed = compress_screenshot_data_url(image_url, max_width=1024, quality=76)
            description = await self._analyze_with_miya_vision(query, compressed)
            result = {"status": "success", "message": description, "source": "camera", "persisted": False}
            self._record_camera_result(result, call, mode="cloud")
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"[ScreenVision] 摄像头视觉分析失败: {exc}")
            return json.dumps({"status": "error", "message": f"摄像头视觉分析失败: {exc}"}, ensure_ascii=False)

    async def _camera_look(self, call: dict[str, Any]) -> str:
        """Capture and analyze one physical camera frame without the frontend."""
        from .camera_capture import capture_camera_frame

        try:
            captured = await __import__("asyncio").to_thread(
                capture_camera_frame,
                call.get("camera_index", 0),
                width=call.get("width", 640),
                height=call.get("height", 480),
            )
        except (ValueError, RuntimeError) as exc:
            return json.dumps({"status": "error", "message": str(exc), "persisted": False}, ensure_ascii=False)

        analysis_call = dict(call)
        analysis_call["image_data"] = captured["image_data"]
        # Terminal capture is an explicit local action. Cloud upload must be
        # opt-in rather than inherited accidentally from a global route.
        analysis_call["local_only"] = call.get("local_only", True)
        result = json.loads(await self._look_me(analysis_call))
        result["source"] = "camera_terminal"
        result["capture"] = {
            "camera_index": captured["camera_index"],
            "width": captured["width"],
            "height": captured["height"],
        }
        result["persisted"] = False
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _record_camera_result(result: dict[str, Any], call: dict[str, Any], *, mode: str) -> None:
        try:
            from core.vision_context import record_camera_observation

            record_camera_observation(
                result,
                query=str(call.get("query") or ""),
                mode=mode,
                local_only=call.get("local_only"),
                proactive=bool(call.get("proactive")),
            )
        except Exception:
            logger.debug("[ScreenVision] 写入统一视觉上下文失败", exc_info=True)

    @staticmethod
    def _record_screen_result(result: dict[str, Any], *, query: str, mode: str) -> None:
        try:
            from core.vision_context import get_vision_context

            get_vision_context().add({
                "source": "screen",
                "kind": "explicit_observation",
                "summary": str(result.get("message") or result.get("ocr_text") or "屏幕观察完成"),
                "query": query[:300],
                "mode": mode,
                "status": result.get("status"),
            })
        except Exception:
            logger.debug("[ScreenVision] 写入统一屏幕上下文失败", exc_info=True)

    async def _look_both(self, call: dict[str, Any]) -> str:
        """Analyze one explicit camera frame alongside a fresh screen capture."""
        route = self._vision_mode("combined")
        local_only = call.get("local_only", False)
        if isinstance(local_only, str):
            local_only = local_only.strip().lower() in {"true", "1", "yes", "on"}
        if _as_bool(local_only) or route == "local":
            return await self._look_both_local(call)

        if route not in {"cloud", "hybrid"}:
            return json.dumps({
                "status": "unavailable",
                "message": "一起观察的视觉路线不可用。",
                "persisted": False,
            }, ensure_ascii=False)

        camera_image = str(call.get("image_data") or call.get("image_url") or "").strip()
        validation_error = _validate_camera_image(camera_image)
        if validation_error:
            return json.dumps({"status": "error", "message": validation_error}, ensure_ascii=False)

        try:
            screenshot = get_screenshot_provider().capture_data_url()
            screen_image = compress_screenshot_data_url(screenshot.data_url, max_width=1280, quality=78)
            camera_image = compress_screenshot_data_url(camera_image, max_width=1024, quality=76)
            query = str(call.get("query") or "请分别描述屏幕和摄像头中的内容，再结合两边信息回答。").strip()[:2000]
            description = await self._analyze_with_miya_vision_sources(query, [
                ("屏幕截图", screen_image),
                ("摄像头画面（用户本人）", camera_image),
            ])
            result = {
                "status": "success",
                "message": description,
                "source": "screen_and_camera",
                "sources": ["screen", "camera"],
                "persisted": False,
            }
            self._record_camera_result(result, call, mode="combined")
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("[ScreenVision] 屏幕与摄像头联合分析失败: %s", exc)
            return json.dumps({
                "status": "error",
                "message": f"一起观察失败: {exc}",
                "persisted": False,
            }, ensure_ascii=False)

    async def _look_both_local(self, call: dict[str, Any]) -> str:
        """Combine local OCR and local camera signals without a cloud call."""
        camera_image = str(call.get("image_data") or call.get("image_url") or "").strip()
        validation_error = _validate_camera_image(camera_image)
        if validation_error:
            return json.dumps({"status": "error", "message": validation_error}, ensure_ascii=False)

        screen_result = await self._look_screen_local()
        capabilities = discover_local_camera_capabilities()
        pose_ready = capabilities.get("features", {}).get("pose", {}).get("available", False)
        camera_result: dict[str, Any]
        if pose_ready:
            try:
                camera_result = analyze_local_frame(
                    camera_image,
                    identity=False,
                    emotion=False,
                    pose=True,
                    pose_history=call.get("pose_history") if isinstance(call.get("pose_history"), list) else None,
                )
            except (ValueError, FileNotFoundError, RuntimeError) as exc:
                camera_result = {"status": "unavailable", "message": f"本地摄像头分析不可用：{exc}"}
        else:
            camera_result = local_only_error()

        screen_message = screen_result.get("message", "本地屏幕 OCR 不可用")
        camera_message = camera_result.get("message", "本地摄像头分析不可用")
        complete = screen_result.get("status") == "success" and camera_result.get("status") == "success"
        return json.dumps({
            "status": "success" if complete else "partial",
            "message": f"本地联合观察（不上传云端）：\n屏幕：{screen_message}\n摄像头：{camera_message}",
            "source": "screen_and_camera_local",
            "sources": ["screen_local_ocr", "camera_local"],
            "screen": screen_result,
            "camera": camera_result,
            "persisted": False,
        }, ensure_ascii=False)

    async def _camera_capabilities(self) -> str:
        return json.dumps(
            {
                "status": "success",
                "camera_mode": self._vision_mode("camera"),
                "vision_mode": self._vision_mode("camera"),
                "capabilities": discover_local_camera_capabilities(),
            },
            ensure_ascii=False,
        )

    def _vision_mode(self, source: str) -> str:
        """Read the unified route, with legacy per-source compatibility."""
        # Vision must fail closed: a missing or malformed route configuration
        # must never spend cloud balance unexpectedly. Cloud use is explicit.
        safe_default = "local"
        try:
            from config.config_utils import get_qq_config

            mode = str(get_qq_config("tools", "qq_image_analyzer", "vision_mode", default=""))
            if mode not in {"local", "cloud", "hybrid"}:
                mode = safe_default
            # Per-source settings intentionally override the shared route when
            # explicitly configured. This keeps legacy deployments compatible
            # while allowing screen and camera to use different providers.
            key = {"camera": "camera_analysis_mode", "screen": "screen_analysis_mode"}.get(source)
            if key:
                try:
                    override = str(get_qq_config("tools", "qq_image_analyzer", key, default="")).strip().lower()
                except Exception:
                    override = ""
                if override in {"local", "cloud", "hybrid"}:
                    mode = override
        except Exception:
            logger.warning("[ScreenVision] 视觉路由配置不可读，按本地模式处理", exc_info=True)
            return safe_default
        if mode not in {"local", "cloud", "hybrid"}:
            logger.warning("[ScreenVision] 未知视觉模式 %r，按本地模式处理", mode)
            return safe_default
        return mode

    def _camera_analysis_mode(self) -> str:
        """Backward-compatible alias for older integrations."""
        return self._vision_mode("camera")

    async def _look_screen_local(self) -> dict[str, Any]:
        try:
            screenshot = get_screenshot_provider().capture_data_url()
            return analyze_local_screen(screenshot.data_url)
        except Exception as exc:
            logger.info("[ScreenVision] 本地屏幕 OCR 不可用: %s", exc)
            return {"status": "unavailable", "message": f"本地 OCR 不可用：{exc}", "persisted": False}

    async def _camera_analyze_local(self, call: dict[str, Any]) -> str:
        image_url = str(call.get("image_data") or call.get("image_url") or "").strip()
        capabilities = discover_local_camera_capabilities()
        required = capabilities.get("features", {})
        identity_requested = bool(call.get("identity", True))
        # The low-level local tool only runs explicitly requested features;
        # callers such as the companion loop pass pose=true when available.
        pose_requested = bool(call.get("pose", False))
        requested = []
        if identity_requested or bool(call.get("emotion", False)):
            requested.append("face_detection")
        if identity_requested:
            requested.append("identity")
        if bool(call.get("emotion", False)):
            requested.append("emotion")
        if pose_requested:
            requested.append("pose")
        if not all(required.get(name, {}).get("available", False) for name in requested):
            return json.dumps(local_only_error(), ensure_ascii=False)
        try:
            result = analyze_local_frame(
                    image_url,
                    identity=bool(call.get("identity", True)),
                    emotion=bool(call.get("emotion", False)),
                    pose=pose_requested,
                    pose_history=call.get("pose_history") if isinstance(call.get("pose_history"), list) else None,
            )
            self._record_camera_result(result, call, mode="local")
            return json.dumps(result, ensure_ascii=False)
        except ValueError as exc:
            return json.dumps({"status": "error", "message": str(exc), "persisted": False}, ensure_ascii=False)
        except (FileNotFoundError, RuntimeError) as exc:
            return json.dumps({"status": "unavailable", "message": str(exc), "persisted": False}, ensure_ascii=False)

    @staticmethod
    def _camera_event(call: dict[str, Any]) -> str:
        from core.vision_context import get_vision_context

        event = call.get("event") if isinstance(call.get("event"), dict) else call
        recorded = get_vision_context().add({
            "source": "camera",
            "kind": str(event.get("kind") or "observation"),
            "summary": str(event.get("summary") or "摄像头事件"),
            "confidence": float(event.get("confidence") or 0),
            "mode": str(event.get("mode") or "companion"),
            "status": "success",
        })
        return json.dumps({"status": "success", "event": recorded, "persisted": False}, ensure_ascii=False)

    async def _camera_enroll_identity(self, call: dict[str, Any]) -> str:
        try:
            return json.dumps(
                enroll_identity(str(call.get("image_data") or call.get("image_url") or ""), str(call.get("name", ""))),
                ensure_ascii=False,
            )
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return json.dumps({"status": "error", "message": str(exc), "persisted": False}, ensure_ascii=False)

    async def _request_camera_observation(self, call: dict[str, Any]) -> str:
        """Let the model request one frame after the user enabled autonomous vision."""
        from core.camera_control import request_observation, read_state, wait_for_observation_result

        state = read_state()
        if not state.get("autonomous") or state.get("mode") == "off":
            return json.dumps(
                {"status": "consent_required", "message": "弥娅自主观察尚未开启，请先在桌面端开启自主视觉。", "persisted": False},
                ensure_ascii=False,
            )
        request = request_observation(
            str(call.get("query") or "请观察我当前的姿态、动作和环境。"),
            local_only=call.get("local_only"),
        )
        result = await __import__("asyncio").to_thread(wait_for_observation_result, request["request_id"], 25.0)
        if result is None:
            return json.dumps(
                {"status": "timeout", "message": "桌面端没有在时限内返回摄像头观察结果。", "request_id": request["request_id"], "persisted": False},
                ensure_ascii=False,
            )
        return json.dumps(result, ensure_ascii=False)

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
        return await self._analyze_with_miya_vision_sources(query, [("画面", image_url)])

    async def _analyze_with_miya_vision_sources(self, query: str, sources: list[tuple[str, str]]) -> str:
        system_prompt = (
            "你是一个视觉助手，请根据用户问题分析提供的画面。"
            "当用户提供多个来源时，严格区分每张图的来源，不要把屏幕内容误认为摄像头中的人，也不要把摄像头画面误认为屏幕内容。"
            "先分别说明屏幕与摄像头中的可见信息，再结合它们回答用户问题；看不清或无法确认时明确说明。"
            "描述要准确、简洁，重点关注用户问题相关的内容。"
            "用中文回答。"
        )

        # 优先走 model-bridge
        api_key, base_url, model_id = self._resolve_vision_model()

        # 调用
        import httpx

        base_url = base_url.rstrip("/")
        user_content: list[dict[str, Any]] = [{"type": "text", "text": query}]
        for label, image_url in sources:
            user_content.append({"type": "text", "text": f"以下是【{label}】。"})
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
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
