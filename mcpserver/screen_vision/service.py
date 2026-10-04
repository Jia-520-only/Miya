#!/usr/bin/env python3
"""
屏幕视觉 MCP 服务 — 让弥娅「看到」用户屏幕

截取用户屏幕，用视觉 LLM 分析内容。
"""

import asyncio
import base64
import binascii
import json
import logging
import os
import threading
import time
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


# A vision provider that is out of balance will keep answering 429 for a while.
# Remembering that avoids paying a network round trip on every later request.
_CLOUD_COOLDOWN_FALLBACK_SECONDS = float(os.getenv("MIYA_VISION_CLOUD_COOLDOWN", "600"))
_cloud_blocked_until = 0.0
_cloud_block_reason = ""
_cloud_lock = threading.Lock()


def _cloud_cooldown_seconds() -> float:
    """Read the cooldown from config so operators can tune it without code."""
    try:
        from config.config_utils import get_qq_config

        configured = get_qq_config(
            "tools", "qq_image_analyzer", "camera_cloud_cooldown_seconds",
            default=_CLOUD_COOLDOWN_FALLBACK_SECONDS,
        )
        return max(30.0, float(configured))
    except (TypeError, ValueError):
        return _CLOUD_COOLDOWN_FALLBACK_SECONDS
    except Exception:
        return _CLOUD_COOLDOWN_FALLBACK_SECONDS


# Capabilities that mean a model can be handed an image. Verified empirically:
# `multimodal` + `image_description` is how the DeepSeek route is labelled, and
# it reads images correctly, so a filter that only looked for `vision_understanding`
# silently dropped the one fallback that was actually alive.
IMAGE_CAPABILITIES = ("vision_understanding", "image_description", "multimodal")


def _is_image_model(model: dict[str, Any]) -> bool:
    if str(model.get("type") or "") in {"vision", "multimodal"}:
        return True
    caps = model.get("capabilities") or []
    return any(cap in caps for cap in IMAGE_CAPABILITIES)


def _cloud_blocked() -> tuple[bool, str]:
    with _cloud_lock:
        if time.time() < _cloud_blocked_until:
            return True, _cloud_block_reason
    return False, ""


# Models that answered "suspended" or "insufficient balance" are remembered per
# model key: rotating away from them is what keeps one dead provider from
# consuming every vision request.
_image_failed: dict[str, float] = {}
_image_ok: dict[str, float] = {}
_IMAGE_FAIL_MEMORY_SECONDS = float(os.getenv("MIYA_VISION_FAIL_MEMORY", "1800"))


def _note_image_model_result(key: str, *, ok: bool) -> None:
    with _cloud_lock:
        if ok:
            _image_ok[key] = time.time()
            _image_failed.pop(key, None)
        else:
            _image_failed[key] = time.time()


def _image_failed_models() -> dict[str, float]:
    """Models excluded for now; entries expire so a topped-up key recovers."""
    now = time.time()
    with _cloud_lock:
        return {key: at for key, at in _image_failed.items() if now - at < _IMAGE_FAIL_MEMORY_SECONDS}


def _healthy_vision_models() -> dict[str, float] | None:
    """Models proven working recently, or ``None`` when nothing has been proven."""
    now = time.time()
    with _cloud_lock:
        proven = {key: at for key, at in _image_ok.items() if now - at < _IMAGE_FAIL_MEMORY_SECONDS}
    return proven or None


def _vision_health_snapshot() -> dict[str, Any]:
    now = time.time()
    with _cloud_lock:
        failed = {k: round(now - v, 1) for k, v in _image_failed.items() if now - v < _IMAGE_FAIL_MEMORY_SECONDS}
        ok = {k: round(now - v, 1) for k, v in _image_ok.items() if now - v < _IMAGE_FAIL_MEMORY_SECONDS}
        blocked = max(0.0, _cloud_blocked_until - now)
        reason = _cloud_block_reason
    return {
        "healthy_models": sorted(ok),
        "failed_models": sorted(failed),
        "seconds_since_failure": failed,
        "cooldown_remaining": round(blocked, 1),
        "cooldown_reason": reason,
    }


def _note_cloud_failure(status_code: int, body: str) -> None:
    """Quota and credit failures are sticky; other errors are transient."""
    global _cloud_blocked_until, _cloud_block_reason
    marker = f"{status_code} {body[:200]}"
    sticky = status_code in {401, 402, 403, 429} or "1113" in body or "insufficient" in body.lower()
    if not sticky:
        return
    cooldown = _cloud_cooldown_seconds()
    with _cloud_lock:
        _cloud_blocked_until = time.time() + cooldown
        _cloud_block_reason = f"视觉模型暂时不可用（{marker}）"
    logger.warning("[ScreenVision] 云端视觉进入 %ss 冷却: %s", int(cooldown), marker)


def _note_cloud_success() -> None:
    global _cloud_blocked_until, _cloud_block_reason
    with _cloud_lock:
        _cloud_blocked_until = 0.0
        _cloud_block_reason = ""


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
                return await self._camera_capabilities(tool_call)
            elif tool_name == "camera_devices":
                return await self._camera_devices(tool_call)
            elif tool_name == "camera_scan":
                return self._camera_scan(tool_call)
            elif tool_name == "camera_fuse":
                return await self._camera_fuse(tool_call)
            elif tool_name == "camera_activity":
                return self._camera_activity(tool_call)
            elif tool_name == "camera_watch":
                return await self._camera_watch(tool_call)
            elif tool_name == "camera_intent":
                return self._camera_intent(tool_call)
            elif tool_name == "camera_impressions":
                return self._camera_impressions(tool_call)
            elif tool_name == "vision_health":
                return self._vision_health(tool_call)
            elif tool_name == "camera_analyze_local":
                return await self._camera_analyze_local(tool_call)
            elif tool_name == "camera_event":
                return self._camera_event(tool_call)
            elif tool_name == "camera_presence":
                return self._camera_presence(tool_call)
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
                        "available": ["look_screen", "look_me", "camera_look", "look_both", "camera_capabilities", "camera_devices", "camera_scan", "camera_fuse", "camera_activity", "camera_watch", "camera_intent", "camera_impressions", "camera_analyze_local", "camera_event", "camera_presence", "camera_enroll_identity", "camera_list_identities", "camera_delete_identity", "vision_health", "screenshot"],
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
                local_result = await asyncio.to_thread(analyze_local_screen, screenshot.data_url)
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
                ocr_text = str(local_result.get("ocr_text") or "").strip()
                if ocr_text:
                    model_query = f"{query}\n\n本地 OCR 识别到的文字（供参考）：{ocr_text[:4000]}"
                accessibility = local_result.get("accessibility") or {}
                window_title = str(accessibility.get("window_title") or "").strip()
                if window_title:
                    model_query += f"\n\nWindows 前台窗口标题（供参考）：{window_title[:180]}"
                controls = accessibility.get("elements") or []
                control_lines = []
                for control in controls[:80]:
                    role = str(control.get("role") or "控件")
                    name = str(control.get("text") or "").strip()
                    if name:
                        state = control.get("enabled")
                        suffix = "可用" if state is True else "不可用" if state is False else "状态未知"
                        control_lines.append(f"[{role}] {name}（{suffix}）")
                if control_lines:
                    model_query += "\n\nWindows 本地 UI Automation 控件（供参考）：\n" + "\n".join(control_lines)
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
                        self._observe_presence(local_result, call)
                        self._record_camera_result(local_result, call, mode="local")
                        # Hybrid means "local first, cloud only for what local
                        # cannot answer" - not "local always wins". Without
                        # this the cloud leg was unreachable dead code.
                        if route == "hybrid" and self._should_deepen_with_cloud(local_result, call):
                            deepened = await self._deepen_camera_with_cloud(
                                image_url, query, local_result, call
                            )
                            if deepened is not None:
                                return json.dumps(deepened, ensure_ascii=False)
                        return json.dumps(local_result, ensure_ascii=False)
                except (ValueError, FileNotFoundError, RuntimeError) as exc:
                    logger.info("[ScreenVision] 本地摄像头分析不可用: %s", exc)
                    if force_local:
                        return json.dumps(local_only_error(), ensure_ascii=False)
        blocked, reason = _cloud_blocked()
        if blocked:
            logger.info("[ScreenVision] 云端视觉处于冷却期，跳过本次上传: %s", reason)
            return json.dumps(
                {
                    "status": "partial",
                    "message": f"{reason}；本次没有上传画面，只保留了本地信号。",
                    "source": "camera_local_degraded",
                    "persisted": False,
                },
                ensure_ascii=False,
            )
        try:
            compressed = compress_screenshot_data_url(image_url, max_width=1024, quality=76)
            description = await self._analyze_with_miya_vision(query, compressed)
            result = {"status": "success", "message": description, "source": "camera", "persisted": False}
            self._record_camera_result(result, call, mode="cloud")
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"[ScreenVision] 摄像头视觉分析失败: {exc}")
            return json.dumps({"status": "error", "message": f"摄像头视觉分析失败: {exc}"}, ensure_ascii=False)

    @staticmethod
    def _should_deepen_with_cloud(local_result: dict[str, Any], call: dict[str, Any]) -> bool:
        """Decide whether a hybrid camera request is worth one cloud call.

        Local ONNX produces geometry only: identity, expression, posture. It has
        nothing to say about *what is going on*. So the cloud leg is reserved
        for requests that actually asked a semantic question, or for images that
        are semantically interesting precisely because no face was found.
        """
        query = str(call.get("query") or "").strip()
        # The companion loop's own boilerplate prompt is not a user question.
        if not query or query.startswith("请观察我当前的画面"):
            return False
        if len(query) < 8:
            return False
        observations = local_result.get("observations") or []
        first = observations[0] if observations and isinstance(observations[0], dict) else {}
        # A face is the one case local models already cover well; a frame with
        # no face at all is exactly where a vision model adds information.
        return not first.get("box") and not first.get("face_signals")

    async def _deepen_camera_with_cloud(
        self,
        image_url: str,
        query: str,
        local_result: dict[str, Any],
        call: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Add one cloud reading on top of a local result, or give up quietly."""
        blocked, reason = _cloud_blocked()
        if blocked:
            local_result["cloud_skipped"] = reason
            return None
        try:
            note = str(local_result.get("message") or "")
            augmented = (
                f"{query}\n\n本机本地模型已经给出这些几何线索，请以此为基础补充你从画面里看到的内容，"
                f"不要与本地结论冲突：{note}"
            )
            compressed = compress_screenshot_data_url(image_url, max_width=1024, quality=76)
            description = await self._analyze_with_miya_vision(augmented, compressed)
            result = {
                "status": "success",
                "message": f"本地线索：{note}\n云端理解：{description}",
                "local": local_result,
                "source": "camera_local_and_cloud",
                "sources": ["camera_local", "camera_cloud"],
                "persisted": False,
            }
            self._observe_presence(local_result, call)
            self._record_camera_result(result, call, mode="hybrid")
            return result
        except Exception as exc:  # noqa: BLE001 - local already succeeded; never fail the request
            logger.info("[ScreenVision] 混合路线云端深化失败，保留本地结果: %s", exc)
            local_result["cloud_skipped"] = str(exc)
            return None

    async def _camera_look(self, call: dict[str, Any]) -> str:
        """Capture and analyze one physical camera frame without the frontend."""
        from .camera_capture import capture_camera_frame
        from .camera_manager import get_camera_manager, resolve_capture_index

        manager = get_camera_manager()
        capture_index = resolve_capture_index(call)
        try:
            captured = await __import__("asyncio").to_thread(
                capture_camera_frame,
                capture_index,
                width=call.get("width", 1280),
                height=call.get("height", 720),
            )
        except (ValueError, RuntimeError) as exc:
            manager.note_result(capture_index, luminance=None, usable=False)
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
        manager.note_result(capture_index, luminance=result.get("luminance"), usable=result.get("status") == "success")
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

    async def _camera_capabilities(self, call: dict[str, Any] | None = None) -> str:
        capabilities = discover_local_camera_capabilities()
        features = capabilities.get("features", {})
        logger.info(
            "[ScreenVision] 本地摄像头能力: status=%s runtime=%s pose=%s identity=%s emotion=%s",
            capabilities.get("status"),
            capabilities.get("runtime"),
            bool(features.get("pose", {}).get("available")),
            bool(features.get("identity", {}).get("available")),
            bool(features.get("emotion", {}).get("available")),
        )
        payload: dict[str, Any] = {
            "status": "success",
            "camera_mode": self._vision_mode("camera"),
            "vision_mode": self._vision_mode("camera"),
            "capabilities": capabilities,
        }
        # Probing physical devices opens hardware, so it stays opt-in instead of
        # running on every capability poll from the desktop.
        if (call or {}).get("include_devices"):
            from .camera_devices import list_camera_devices

            payload["devices"] = await asyncio.to_thread(list_camera_devices)
        return json.dumps(payload, ensure_ascii=False)

    async def _camera_devices(self, call: dict[str, Any]) -> str:
        """Enumerate OpenCV camera indices with a one-frame health probe."""
        from .camera_devices import list_camera_devices

        probe = call.get("probe", True)
        if isinstance(probe, str):
            probe = probe.strip().lower() not in {"false", "0", "no", "off"}
        try:
            result = await asyncio.to_thread(
                list_camera_devices,
                width=int(call.get("width") or 640),
                height=int(call.get("height") or 480),
                probe=bool(probe),
            )
        except (TypeError, ValueError) as exc:
            return json.dumps({"status": "error", "message": f"摄像头枚举参数无效: {exc}", "devices": []}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False)

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
            return await asyncio.to_thread(analyze_local_screen, screenshot.data_url)
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
        # Face detection is separately requestable: expression geometry needs it
        # even when identity and emotion are both off.
        faces_requested = call.get("faces")
        detect_faces = bool(identity_requested or bool(call.get("emotion", False)) or _as_bool(faces_requested))
        requested = []
        if detect_faces:
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
                    faces=detect_faces,
                    pose_history=call.get("pose_history") if isinstance(call.get("pose_history"), list) else None,
            )
            self._observe_presence(result, call)
            self._record_camera_result(result, call, mode="local")
            return json.dumps(result, ensure_ascii=False)
        except ValueError as exc:
            return json.dumps({"status": "error", "message": str(exc), "persisted": False}, ensure_ascii=False)
        except (FileNotFoundError, RuntimeError) as exc:
            return json.dumps({"status": "unavailable", "message": str(exc), "persisted": False}, ensure_ascii=False)

    @staticmethod
    def _observe_presence(result: dict[str, Any], call: dict[str, Any]) -> None:
        """Feed one local result into the shared presence and activity trackers."""
        try:
            from .presence import presence_from_local_result

            motion = call.get("motion_score")
            presence_from_local_result(result, motion=float(motion or 0.0))
        except (TypeError, ValueError):
            logger.debug("[ScreenVision] 在场状态更新失败", exc_info=True)
        try:
            from .activity import observe_action

            observations = result.get("observations") or []
            first = observations[0] if observations and isinstance(observations[0], dict) else {}
            action = first.get("action") if isinstance(first.get("action"), dict) else None
            if action:
                observe_action(action)
        except Exception:
            logger.debug("[ScreenVision] 活动累积更新失败", exc_info=True)

    @staticmethod
    def _camera_activity(call: dict[str, Any]) -> str:
        """Report what Jia has been doing, and surface a change at most once."""
        from .activity import (
            activity_card,
            activity_change_card,
            get_activity_tracker,
            take_activity_change,
        )

        tracker = get_activity_tracker()
        payload: dict[str, Any] = {
            "status": "success",
            "activity": tracker.snapshot().to_dict(),
            "message": tracker.snapshot().describe(),
            "card": activity_card(),
        }
        pending = activity_change_card()
        if pending:
            payload["change_card"] = pending
        if _as_bool(call.get("consume_change")):
            # Consuming is opt-in so a read-only caller cannot swallow the change
            # that the conversation layer was about to use.
            change = take_activity_change()
            if change is not None:
                payload["change"] = change.to_dict()
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _camera_scan(call: dict[str, Any]) -> str:
        """Re-discover every usable camera, picking up a phone that woke up."""
        from .camera_manager import get_camera_manager

        manager = get_camera_manager()
        manager.scan(force=True)
        return json.dumps({"status": "success", **manager.describe()}, ensure_ascii=False)

    # ===== 弥娅自己掌控摄像头 =====

    async def _camera_watch(self, call: dict[str, Any]) -> str:
        """Start or stop Miya's own watching loop, and let her set the cadence."""
        from .vision_agent import configured_start_kwargs, get_vision_agent

        agent = get_vision_agent()
        action = str(call.get("action") or "status").strip().lower()
        if action in {"start", "on", "resume"}:
            # Start from what `camera_agency` says, then let an explicit argument
            # win. Reading only the argument meant a manual start silently used
            # the code defaults for cadence, adaptive pacing and thumbnails.
            settings = configured_start_kwargs()
            interval = call.get("interval_seconds")
            if interval is not None:
                try:
                    settings["interval_seconds"] = float(interval)
                except (TypeError, ValueError):
                    pass
            requested_mode = str(call.get("mode") or "").strip()
            if requested_mode:
                settings["mode"] = requested_mode
            state = agent.start(**settings)
        elif action in {"stop", "off", "pause"}:
            state = await agent.stop()
        elif action in {"tick", "look", "now"}:
            result = await agent.tick(interpret=not _as_bool(call.get("skip_interpret")))
            return json.dumps({"status": "success", **result}, ensure_ascii=False)
        else:
            state = agent.state()
        from .vision_agent import get_vision_agency

        return json.dumps(
            {"status": "success", "agent": state, "agency": get_vision_agency().describe()},
            ensure_ascii=False,
        )

    @staticmethod
    def _camera_intent(call: dict[str, Any]) -> str:
        """Miya writes down what she wants to watch for, in her own words."""
        from .vision_agent import get_vision_agency

        agency = get_vision_agency()
        action = str(call.get("action") or "list").strip().lower()
        if action in {"add", "set", "want"}:
            intent = agency.add_intent(
                str(call.get("text") or ""),
                speak=not _as_bool(call.get("silent", False)),
                note=str(call.get("note") or ""),
                source=str(call.get("source") or "miya"),
            )
            if intent is None:
                return json.dumps({"status": "error", "message": "观察意图不能为空。"}, ensure_ascii=False)
            return json.dumps({"status": "success", "intent": intent.to_dict(), **agency.describe()}, ensure_ascii=False)
        if action in {"remove", "delete", "forget"}:
            removed = agency.remove_intent(str(call.get("intent_id") or ""))
            return json.dumps({"status": "success" if removed else "error",
                               "message": "已删除" if removed else "没有找到这个观察意图",
                               **agency.describe()}, ensure_ascii=False)
        if action in {"enable", "disable"}:
            changed = agency.set_intent_active(str(call.get("intent_id") or ""), action == "enable")
            return json.dumps({"status": "success" if changed else "error",
                               "message": "已更新" if changed else "没有找到这个观察意图",
                               **agency.describe()}, ensure_ascii=False)
        return json.dumps({"status": "success", **agency.describe()}, ensure_ascii=False)

    @staticmethod
    def _camera_impressions(call: dict[str, Any]) -> str:
        """What Miya has noticed lately, and whether she has something to say."""
        from .vision_agent import get_vision_agency, get_vision_agent

        agency = get_vision_agency()
        agent = get_vision_agent()
        try:
            limit = max(1, min(int(call.get("limit") or 8), 50))
        except (TypeError, ValueError):
            limit = 8
        payload: dict[str, Any] = {
            "status": "success",
            "impressions": [item.to_dict() for item in agency.impressions(limit=limit)],
            "memory_card": agency.memory_card(limit=limit),
            "intent_card": agency.intent_card(),
            "agent": agent.state(),
        }
        pending = agent.peek_messages()
        payload["pending_messages"] = pending
        payload["message"] = pending[0] if pending else None
        if _as_bool(call.get("consume_message")):
            payload["message"] = agent.take_message()
            payload["pending_messages"] = agent.peek_messages()
        return json.dumps(payload, ensure_ascii=False)

    async def _camera_fuse(self, call: dict[str, Any]) -> str:
        """Look through every usable camera at once and fuse what they see.

        A browser can only open one camera at a time, so genuine multi-camera
        coverage lives here: each usable index is captured separately and the
        derived observations are merged into one reading of what Jia is doing.
        """
        from .camera_capture import capture_camera_frame
        from .camera_manager import fuse_observations, get_camera_manager, narrative_for_fused
        from .activity import get_activity_tracker

        manager = get_camera_manager()
        manager.scan()
        indices = manager.usable_indices()
        requested = call.get("indices")
        if isinstance(requested, list) and requested:
            wanted = []
            for value in requested:
                try:
                    wanted.append(max(0, int(value)))
                except (TypeError, ValueError):
                    continue
            indices = wanted or indices
        if call.get("camera_index") is not None:
            try:
                indices = [max(0, int(call["camera_index"]))]
            except (TypeError, ValueError):
                pass
        if not indices:
            return json.dumps({
                "status": "unavailable",
                "message": "现在没有任何摄像头能出画面；如果用的是手机，请确认它没有息屏。",
                "persisted": False,
            }, ensure_ascii=False)

        width = int(call.get("width") or 1280)
        height = int(call.get("height") or 720)
        observations: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for index in indices:
            try:
                captured = await asyncio.to_thread(capture_camera_frame, index, width=width, height=height)
            except Exception as exc:  # noqa: BLE001 - one bad device must not abort fusion
                # OpenCV backends can raise their own exception types during
                # teardown/open. Keep the other camera angles usable and leave
                # a bounded health record for the next scan.
                manager.note_result(
                    index,
                    luminance=None,
                    usable=False,
                    reason=str(exc),
                )
                failures.append({"index": index, "message": str(exc)})
                continue
            try:
                result = analyze_local_frame(
                    captured["image_data"],
                    identity=bool(call.get("identity", True)),
                    emotion=bool(call.get("emotion", False)),
                    pose=bool(call.get("pose", True)),
                    pose_history=call.get("pose_history") if isinstance(call.get("pose_history"), list) else None,
                )
            except (ValueError, FileNotFoundError, RuntimeError) as exc:
                failures.append({"index": index, "message": str(exc)})
                continue
            manager.note_result(index, luminance=result.get("luminance"), usable=result.get("status") == "success")
            if result.get("status") != "success":
                failures.append({"index": index, "message": str(result.get("message") or "没有得到有效画面"),
                                 "blank_frame": bool(result.get("blank_frame"))})
                continue
            observations.append({"index": index, "result": result})

        fused = fuse_observations(observations)
        action = fused.get("action") or {}
        if action:
            get_activity_tracker().observe(
                str(action.get("kind") or ""),
                str(action.get("label") or ""),
                confidence=float(action.get("confidence") or 0.0),
            )
        # Present the fused reading to the presence model as one combined sample.
        self._observe_presence({"observations": [{
            "face_signals": fused.get("face_signals"),
            "pose_quality": fused.get("pose_quality"),
            "action": action,
        }], "faces": fused.get("faces"), "luminance": None}, call)

        activity = get_activity_tracker().snapshot()
        fused["message"] = narrative_for_fused(fused, activity=activity.phrase, duration=activity.duration)
        fused["activity"] = activity.to_dict()
        fused["failures"] = failures
        fused["source"] = "camera_fused"
        fused["persisted"] = False
        self._record_camera_result(fused, call, mode="fused")
        return json.dumps(fused, ensure_ascii=False)

    @staticmethod
    def _camera_presence(call: dict[str, Any]) -> str:
        """Report whether Jia is at the computer, from derived signals only."""
        from .presence import get_presence_tracker

        tracker = get_presence_tracker()
        try:
            motion = float(call.get("motion_score") or 0.0)
        except (TypeError, ValueError):
            motion = 0.0
        if call.get("faces_in_frame") is not None or motion or call.get("report_frame"):
            tracker.note_frame(motion=motion)
            if call.get("faces_in_frame") is not None:
                tracker.observe(faces=int(call.get("faces_in_frame") or 0), motion=motion)
        snapshot = tracker.snapshot() if not call.get("refresh") else tracker.evaluate()
        return json.dumps(
            {"status": "success", "presence": snapshot.to_dict(), "message": snapshot.describe()},
            ensure_ascii=False,
        )

    @staticmethod
    def _camera_event(call: dict[str, Any]) -> str:
        event = call.get("event") if isinstance(call.get("event"), dict) else call
        if str(event.get("kind") or "").strip().lower() == "preview_released":
            from .camera_manager import get_camera_manager
            from .camera_stream import get_camera_pool

            raw_index = call.get("camera_index")
            if raw_index is None:
                raw_index = event.get("camera_index")
            try:
                index = int(raw_index) if raw_index is not None else None
            except (TypeError, ValueError):
                index = None
            manager = get_camera_manager()
            source_ids = call.get("browser_source_ids") or event.get("browser_source_ids") or []
            if isinstance(source_ids, list) and source_ids:
                for source_id in source_ids:
                    # A browser-only phone source has no OpenCV index; the
                    # source id is the authoritative release key.
                    manager.forget_browser_frame(None, browser_source_id=str(source_id))
            else:
                manager.forget_browser_frame(
                    index,
                    browser_source_id=call.get("browser_source_id") or event.get("browser_source_id"),
                )
            # When the browser reports source ids it may be holding several
            # cameras at once. Releasing only the selected primary index leaves
            # the other frame buffers owned by the stopped preview.
            get_camera_pool().release_browser(None if source_ids else index)
            return json.dumps({"status": "success", "released": index}, ensure_ascii=False)

        from core.vision_context import get_vision_context

        event_kind = str(event.get("kind") or "observation")
        # A preview heartbeat carries pixels to the backend but has no semantic
        # meaning. Storing it as the latest camera event used to hide real
        # gestures from the proactive trigger every 15 seconds.
        recorded = None
        if event_kind not in {"companion_frame", "preview_heartbeat"}:
            recorded = get_vision_context().add({
                "source": "camera",
                "kind": event_kind,
                "summary": str(event.get("summary") or "摄像头事件"),
                "confidence": float(event.get("confidence") or 0),
                "mode": str(event.get("mode") or "companion"),
                "status": "success",
            })
        logger.info(
            "[ScreenVision] 摄像头事件: kind=%s summary=%s confidence=%.2f",
            event_kind, (recorded or {}).get("summary", "取帧心跳"),
            float((recorded or {}).get("confidence") or 0),
        )
        # The desktop preview owns the device while it is running, so the frame it
        # sends here is the only way the backend can see through that camera.
        frame = str(call.get("image_data") or event.get("image_data") or "").strip()
        if frame.startswith("data:image/"):
            from .camera_manager import get_camera_manager

            try:
                index = call.get("camera_index") if call.get("camera_index") is not None else event.get("camera_index")
                # No index means the browser device could not be proven to be
                # the same physical source as an OpenCV camera. Keep the frame
                # usable for inference without inventing a source attribution.
                index = int(index) if index is not None else None
                if index is not None and index < 0:
                    index = None
                get_camera_manager().remember_browser_frame(
                    index=index,
                    data_url=frame,
                    browser_source_id=call.get("browser_source_id") or event.get("browser_source_id"),
                    device_id_hash=call.get("device_id_hash") or event.get("device_id_hash"),
                    label=call.get("camera_label") or event.get("camera_label") or "",
                )
                # Also publish into the shared pool: the preview owns that device,
                # so this frame is the only way anything else can see through it.
                if index is not None and index >= 0:
                    from .camera_capture import thumbnail_from_data_url
                    from .camera_stream import get_camera_pool

                    get_camera_pool().publish_browser_frame(
                        int(index), frame, thumbnail=thumbnail_from_data_url(frame))
            except (TypeError, ValueError):
                logger.debug("[ScreenVision] 缓存浏览器帧失败", exc_info=True)
        # The companion loop already sends a motion score with every event, so
        # this is the cheapest place to keep the presence model current.
        presence: dict[str, Any] | None = None
        try:
            from .presence import get_presence_tracker

            motion = event.get("motion_score")
            snapshot = get_presence_tracker().note_frame(motion=float(motion or 0.0))
            presence = snapshot.to_dict()
        except (TypeError, ValueError):
            logger.debug("[ScreenVision] 事件附带在场状态失败", exc_info=True)
        return json.dumps(
            {"status": "success", "event": recorded, "presence": presence, "persisted": False},
            ensure_ascii=False,
        )

    async def _camera_enroll_identity(self, call: dict[str, Any]) -> str:
        try:
            return json.dumps(
                enroll_identity(str(call.get("image_data") or call.get("image_url") or ""), str(call.get("name", ""))),
                ensure_ascii=False,
            )
        except Exception as exc:
            logger.warning("[ScreenVision] 本地身份登记失败: %s", exc, exc_info=True)
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
            local_only=(
                call.get("local_only")
                if call.get("local_only") is not None
                else state.get("local_only", True)
            ),
        )
        result = await asyncio.to_thread(wait_for_observation_result, request["request_id"], 25.0)
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

        candidates = self._vision_candidates()

        import httpx

        user_content: list[dict[str, Any]] = [{"type": "text", "text": query}]
        for label, image_url in sources:
            user_content.append({"type": "text", "text": f"以下是【{label}】。"})
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        errors: list[str] = []
        sticky_status = 0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for key, api_key, base_url, model_id in candidates:
                try:
                    response = await client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
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
                except Exception as exc:  # noqa: BLE001 - try the next provider
                    errors.append(f"{key}: {type(exc).__name__}: {exc}")
                    _note_image_model_result(key, ok=False)
                    continue
                if response.status_code != 200:
                    # A single provider being out of balance must not cool down
                    # the whole route: remember it per model and rotate instead.
                    _note_image_model_result(key, ok=False)
                    errors.append(f"{key} 返回 {response.status_code}: {response.text[:160]}")
                    logger.info("[ScreenVision] 视觉模型 %s 不可用，换下一个", key)
                    if response.status_code in {401, 402, 403, 429} and not sticky_status:
                        # Keep the real status: the global cooldown is only
                        # armed after every candidate failed, and a synthesised
                        # status would lose the "out of balance" signal.
                        sticky_status = response.status_code
                    continue
                data = response.json()
                content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
                if not content:
                    _note_image_model_result(key, ok=False)
                    errors.append(f"{key} 返回了空内容")
                    continue
                _note_image_model_result(key, ok=True)
                _note_cloud_success()
                return content

        # Nothing worked. Now, and only now, cool the whole route down.
        _note_cloud_failure(sticky_status or 503, " | ".join(errors[:3]))
        raise RuntimeError("所有视觉模型都不可用: " + (" | ".join(errors[:3]) or "没有配置可用模型"))

    @staticmethod
    def _vision_health(call: dict[str, Any]) -> str:
        """Report which vision models are working right now.

        Configuration alone cannot answer this: several endpoints are suspended
        for non-payment, so health has to come from actual calls.
        """
        service = ScreenVisionService()
        try:
            candidates = service._vision_candidates()
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": str(exc),
                               "health": _vision_health_snapshot()}, ensure_ascii=False)
        try:
            requested = int(call.get("limit") or 0)
        except (TypeError, ValueError):
            requested = 0
        # No limit means "show the whole chain"; a limit of 0 must not be read
        # as an empty slice.
        shown = candidates[:max(1, min(requested, len(candidates)))] if requested > 0 else candidates
        return json.dumps({
            "status": "success",
            "candidates": [{"key": key, "model": name, "base_url": base_url}
                           for key, _api_key, base_url, name in shown],
            "health": _vision_health_snapshot(),
            "message": f"共有 {len(candidates)} 个配置可用的视觉模型，按优先级排列。",
        }, ensure_ascii=False)

    def _vision_candidates(self) -> list[tuple[str, str, str, str]]:
        """All usable vision models, best first, as (key, api_key, base_url, name).

        Only models that have a key are returned. Which of them is *actually*
        healthy is discovered by calling them: several configured endpoints are
        suspended for non-payment, and picking one blind used to burn the whole
        request before falling back.
        """
        import json
        from pathlib import Path

        from config.config_utils import get_api_key

        miya_root = Path(__file__).resolve().parent.parent.parent
        cfg_path = miya_root / "config" / "multi_model_config.json"
        if not cfg_path.exists():
            raise RuntimeError("[ScreenVision] 模型配置文件不存在: multi_model_config.json")

        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        models = cfg.get("models", {})
        prefs = (cfg.get("vision_preferences") or {}).get("model_preferences") or {}
        active_vision = (cfg.get("vision_preferences") or {}).get("active_vision")

        # Honour the configured intent first, then the declared fallbacks, then
        # anything else that can see an image.
        ordered_keys: list[str] = []
        for key in (active_vision, prefs.get("primary"), prefs.get("secondary"), prefs.get("fallback")):
            if isinstance(key, str) and key and key not in ordered_keys:
                # "@active_vision" is a pointer, not a model name.
                ordered_keys.append(key[1:] if key.startswith("@") else key)
        if active_vision and active_vision not in ordered_keys:
            ordered_keys.insert(0, active_vision)
        ordered_keys = [key for key in ordered_keys if key in models]
        for key, model in models.items():
            if key in ordered_keys or not isinstance(model, dict):
                continue
            if _is_image_model(model):
                ordered_keys.append(key)

        candidates: list[tuple[str, str, str, str]] = []
        healthy = _healthy_vision_models()
        previously_bad = _image_failed_models()
        for key in ordered_keys:
            model = models.get(key)
            if not isinstance(model, dict):
                continue
            if not _is_image_model(model):
                continue
            if model.get("enabled") is False:
                continue
            if key in previously_bad and (healthy is None or key not in healthy):
                continue
            api_key = get_api_key(model.get("env_key", "")) if model.get("env_key") else ""
            base_url = str(model.get("base_url") or "").rstrip("/")
            name = str(model.get("name") or "")
            if not api_key or not base_url or not name:
                continue
            candidates.append((key, api_key, base_url, name))

        if not candidates:
            raise RuntimeError(
                "[ScreenVision] 未找到可用的视觉模型。请在 multi_model_config.json 中配置 vision_preferences"
            )
        return candidates

    def _resolve_vision_model(self) -> tuple[str, str, str]:
        """Pick the best configured vision model (key, base_url, name)."""
        candidates = self._vision_candidates()
        key, api_key, base_url, name = candidates[0]
        logger.info(f"[ScreenVision] 使用视觉模型: {key} → {name} @ {base_url}")
        return api_key, base_url, name
