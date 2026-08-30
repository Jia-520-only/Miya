"""
平台消息处理辅助 Mixin

提供所有平台共享的消息转换、路由逻辑和通用后处理。
每个平台只需：解析消息 → route_to_decision_hub() → 拆分发送
"""

from __future__ import annotations

import asyncio
import contextlib
import json as _json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.PlatformMessageMixin")


def _set_live2d_state(state: str) -> None:
    """Best-effort bridge for platform-side TTS playback."""
    try:
        from plugins.yinmei.routes import live2d_set_state

        live2d_set_state(state)
    except Exception:
        logger.debug("Live2D state bridge unavailable", exc_info=True)


class MessageMixin:
    """消息处理辅助：将平台消息转换为 M-Link 格式并路由到 DecisionHub"""

    _miya_core: Any = None
    platform_id: str = ""

    def set_miya_core(self, miya):
        self._miya_core = miya

    # ============ 通用后处理 (所有平台自动享有) ============

    @staticmethod
    def _filter_thinking(text: str) -> str:
        """过滤思考过程（DeepSeek R1 等推理模型的残留）"""
        import re

        # v4.5.1: 移除英文/代码风格前缀（如 [Paste..., [Write..., etc）
        lines = text.split("\n")
        if lines:
            first_line = lines[0].strip()
            if (first_line.startswith("[") and not re.search(r"[\u4e00-\u9fff]", first_line)) or (
                re.match(r"^[A-Za-z][a-z]+\s", first_line) and not re.search(r"[\u4e00-\u9fff]", first_line)
            ):
                lines.pop(0)
                while lines and not lines[0].strip():
                    lines.pop(0)
                text = "\n".join(lines).strip()

        patterns = [
            r"^好的，用户是在.*?\n",
            r"^首先，用户.*?\n",
            r"^接下来，我需要.*?\n",
            r"^在之前的对话中.*?\n",
            r"^所以我的回答.*?\n",
            r"^综上所述.*?\n",
            r"^嗯，我是弥娅.*?\n",
            r"^这个问题的回答.*?\n",
            r"^根据设定，我.*?\n",
            r"^作为.*?我.*?\n",
        ]
        for p in patterns:
            text = re.sub(p, "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _filter_output(text: str) -> str:
        """感叹号刷屏过滤"""
        try:
            import json
            import random
            from pathlib import Path

            config_path = Path(__file__).parent.parent.parent / "config" / "text_config.json"
            if not config_path.exists():
                return text

            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            of = cfg.get("output_filter", {})
            if not of.get("enabled", False):
                return text

            threshold = of.get("exclamation_threshold", 0)
            if threshold > 0:
                count = text.count("!")
                if count >= threshold:
                    fallbacks = of.get("fallback_responses", ["好的~"])
                    logger.info(f"[MessageMixin] 刷屏过滤: {count}个感叹号 → 替换")
                    return random.choice(fallbacks)
        except Exception:
            pass
        return text

    async def _after_route(self, content: str, response: str, user_id: str) -> None:
        """路由后副作用: 离别检测"""
        if not response or not content:
            return
        try:
            miya = getattr(self, "_miya_core", None)
            if not miya or not hasattr(miya, "decision_hub"):
                return

            from core.qq_command_config import is_farewell_keyword

            if is_farewell_keyword(content):
                logger.info(f"[{self.platform_id}] 检测到离别语")
                await miya.decision_hub.handle_session_end(session_id=user_id, platform=self.platform_id)
        except Exception:
            pass

    @staticmethod
    def _split_message(text: str, max_len: int = 200) -> list:
        """按自然段落拆分——只有双换行(\n\n)视为分条信号，单换行保持在同一消息内"""
        if "\n\n" not in text:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(para) <= max_len:
                chunks.append(para)
            else:
                chunks.extend(MessageMixin._split_long_line(para, max_len))

        return chunks

    @staticmethod
    def _split_long_line(line: str, max_len: int) -> list:
        """拆分超长单行——按标点找断点"""

        chunks = []
        remaining = line
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining.strip())
                break
            segment = remaining[:max_len]
            break_points = []
            for punct in ["。", "！", "？", "；", "，"]:
                pb = segment.rfind(punct)
                if pb > max_len // 3:
                    break_points.append(pb + 1)
            if break_points:
                split_at = max(break_points)
            else:
                # 没有任何标点，回退到空格或硬切
                space = segment.rfind(" ")
                split_at = space + 1 if space > max_len // 2 else max_len
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        return chunks

    # ============ 核心路由 ============

    async def route_to_decision_hub(
        self,
        content: str,
        user_id: str,
        user_name: str = "",
        message_type: str = "private",
        group_id: str = "",
        group_name: str = "",
        sender_role: str = "member",
        is_at_bot: bool = True,
        extra: Optional[Dict] = None,
        files: Optional[List[Any]] = None,
        images: Optional[List[Any]] = None,
    ) -> str:
        """
        将平台消息路由到 DecisionHub 并返回响应

        Args:
            content: 消息文本
            user_id: 用户ID
            user_name: 用户名
            message_type: 消息类型 (private/group/c2c/channel)
            group_id: 群组ID
            group_name: 群组名称
            sender_role: 发送者角色
            is_at_bot: 是否 @ 了机器人
            extra: 额外数据
            files: 文件上下文列表 (FileContext 或 dict)
            images: 图片上下文列表 (FileContext 或 dict)

        Returns:
            弥娅的响应文本
        """
        miya = self._miya_core
        if not miya:
            return "弥娅系统未就绪"

        from core.platform_context import set_current_platform_adapter

        set_current_platform_adapter(self)

        try:
            from mlink.message import Message

            group_id_int = 0
            if group_id:
                with contextlib.suppress(ValueError):
                    group_id_int = int(group_id)

            perception_data = {
                "content": content,
                "input": content,
                "sender_name": user_name or user_id,
                "user_id": user_id,
                "sender_id": user_id,
                "unified_user_id": f"{self.platform_id}_{user_id}",
                "message_type": message_type,
                "group_id": group_id_int,
                "group_name": group_name,
                "sender_role": sender_role,
                "platform": self.platform_id,
                "source": self.platform_id,
                "is_at_bot": is_at_bot,
                "reply_to_bot": False,
                "timestamp": datetime.now().isoformat(),
                "is_owner": False,
                "owner_name": "",
            }

            # 注入身份信息：检查发送者是否是超管/所有者
            try:
                from core.unified_permission import get_permission_engine

                engine = get_permission_engine()
                if engine.is_superadmin(str(user_id), platform=self.platform_id):
                    perception_data["is_owner"] = True
                    # 从 superadmins 配置中获取名字和规范ID
                    for _person, info in engine._config.get("superadmins", {}).items():
                        perception_data["owner_name"] = info.get("name", "")
                        # 获取规范用户ID（第一个有值的平台ID作为标准）
                        canonical_id = str(user_id)
                        ids = info.get("ids", {})
                        for _pid, raw_ids in ids.items():
                            if isinstance(raw_ids, list) and raw_ids:
                                canonical_id = str(raw_ids[0])
                                break
                            elif isinstance(raw_ids, str) and raw_ids:
                                canonical_id = str(raw_ids)
                                break
                        perception_data["canonical_user_id"] = canonical_id
                        perception_data["sender_name"] = info.get("name", "") or user_name or user_id
                        # 保留平台原始 ID 用于文件发送等场景
                        perception_data["platform_user_id"] = user_id
                        # 关键：统一 user_id 为规范ID，确保记忆存储在同一桶内
                        perception_data["user_id"] = canonical_id
                        break
            except Exception:
                pass

            if extra:
                perception_data.update(extra)

            # ── 文件/图片上下文注入 ──
            await _resolve_files_and_images(files, images, perception_data, content, user_id, self.platform_id)

            # v9.0: 记录到统一平台感知中心 (取代分散的多处追踪)
            # v8.1: 记录用户跨平台活跃度（主动消息路由精准分发用）
            try:
                from core.platform_awareness import get_platform_awareness

                awareness = get_platform_awareness()
                awareness.record_activity(str(user_id), self.platform_id)
            except Exception:
                pass

            mlink_msg = Message(
                msg_type="data",
                content=perception_data,
                source=self.platform_id,
            )

            if hasattr(miya, "decision_hub"):
                # ── 群聊命令守卫：群聊中未@且无触发关键词时不允许执行斜杠命令（超管豁免） ──
                if self._group_command_allowed(content, message_type, is_at_bot, perception_data):
                    # ── 统一斜杠命令系统（唯一命令入口） ──
                    cmd_response = await _dispatch_slash_command(self, content, user_id, group_id, message_type)
                    if cmd_response:
                        await _send_cmd_reply(self, cmd_response, user_id, group_id, message_type)
                        return

                # ── 内容自动检测管线（B站/arXiv/GitHub）──
                try:
                    from webnet.ToolNet.pipelines.content_pipeline import get_pipeline

                    pipeline = get_pipeline()
                    pipeline_results = await pipeline.detect_and_process(content)
                    if pipeline_results:
                        pipeline_texts = []
                        for pr in pipeline_results:
                            pipeline_texts.append(pr["content"])
                        pipeline_context = "\n\n".join(pipeline_texts)

                        # 注入到 perception_data，追加到 content 后（不干扰谛听前置匹配）
                        perception_data["content"] = f"{content}\n\n{pipeline_context}"
                        perception_data["pipeline_detections"] = pipeline_context
                        mlink_msg.content["content"] = perception_data["content"]
                        mlink_msg.content["pipeline_detections"] = pipeline_context
                        logger.info(f"[Pipeline] 检测到 {len(pipeline_results)} 个内容，已注入上下文")
                except Exception as e:
                    logger.debug(f"[Pipeline] 检测失败: {e}")

                # ── 统一路由：DecisionHub 处理所有消息 ──
                response = await miya.decision_hub.process_perception_cross_platform(mlink_msg)

                # === 通用后处理 ===
                if response:
                    response = self._filter_thinking(response)
                    response = self._filter_output(response)
                # TTS 本地播放 (fire-and-forget, 所有平台)
                if response and self._tts_should_local():
                    asyncio.ensure_future(self._tts_play_response(response))
                # 副作用 (fire-and-forget)
                asyncio.ensure_future(self._after_route(content, response or "", user_id))
                return response  # None → 不回复, 空字符串 → 平台自行兜底
            else:
                return "决策系统未就绪"

        except Exception as e:
            logger.error(f"[{self.platform_id}] 消息处理异常: {e}", exc_info=True)
            return f"处理消息时出错了: {e}"

    @staticmethod
    def _group_command_allowed(
        content: str, message_type: str, is_at_bot: bool, perception_data: Dict[str, Any]
    ) -> bool:
        """群聊命令守卫：群聊中执行斜杠命令需要 @bot 或触发关键词；私聊/超管豁免"""
        if message_type != "group" or is_at_bot:
            return True
        if perception_data.get("is_owner"):
            return True
        try:
            from core.text_loader import get_chatbot_keywords

            content_lower = (content or "").lower()
            return any(kw.lower() in content_lower for kw in get_chatbot_keywords())
        except Exception:
            return True

    # ============ 文件发送辅助 ============

    async def send_file_to_target(
        self,
        target: str,
        file_path: str = "",
        file_data: Optional[bytes] = None,
        file_name: str = "",
        caption: str = "",
        message_type: str = "private",
        **kwargs,
    ) -> bool:
        """发送文件到指定目标（委托给 BasePlatform.send_file）

        Args:
            target: 接收方ID (user_id / group_id / channel_id)
            file_path: 本地文件路径
            file_data: 文件二进制数据（与 file_path 二选一）
            file_name: 文件名
            caption: 附带文本
            message_type: private / group / channel

        Returns:
            True 表示发送成功
        """
        if hasattr(self, "send_file"):
            return await self.send_file(
                target=target,
                file_path=file_path,
                file_data=file_data,
                file_name=file_name,
                caption=caption,
                message_type=message_type,
                **kwargs,
            )
        logger.warning(f"[{self.platform_id}] send_file 未实现（MessageMixin 降级）")
        return False

    async def send_image_to_target(
        self,
        target: str,
        image_path: str = "",
        file_data: Optional[bytes] = None,
        file_name: str = "",
        caption: str = "",
        message_type: str = "private",
        **kwargs,
    ) -> bool:
        """发送图片到指定目标（委托给 BasePlatform.send_image）"""
        if hasattr(self, "send_image"):
            return await self.send_image(
                target=target,
                image_path=image_path,
                file_data=file_data,
                file_name=file_name,
                caption=caption,
                message_type=message_type,
                **kwargs,
            )
        return await self.send_file_to_target(
            target=target,
            file_path=image_path,
            file_data=file_data,
            file_name=file_name,
            caption=caption,
            message_type=message_type,
            **kwargs,
        )

    async def send_response_with_files(
        self,
        target: str,
        message_type: str,
        text: str = "",
        files: Optional[List[Any]] = None,
        images: Optional[List[Any]] = None,
    ) -> bool:
        """发送文本 + 可选附件到指定目标

        Args:
            target: 接收方ID
            message_type: private / group / channel
            text: 文本消息（可为空）
            files: OutboundFile 列表
            images: OutboundFile 列表

        Returns:
            True 表示所有文件发送成功（至少一个）
        """
        success = False

        for img in images or []:
            if hasattr(self, "send_image"):
                ok = await self.send_image(
                    target=target,
                    image_path=getattr(img, "file_path", ""),
                    file_data=getattr(img, "file_data", None),
                    file_name=getattr(img, "file_name", ""),
                    caption=getattr(img, "caption", text),
                    message_type=message_type,
                )
                if ok:
                    success = True
            elif hasattr(img, "file_path") and img.file_path:
                ok = await self.send_file_to_target(
                    target=target,
                    file_path=img.file_path,
                    file_name=getattr(img, "file_name", ""),
                    caption=getattr(img, "caption", text),
                    message_type=message_type,
                )
                if ok:
                    success = True

        for f in files or []:
            ok = await self.send_file_to_target(
                target=target,
                file_path=getattr(f, "file_path", ""),
                file_data=getattr(f, "file_data", None),
                file_name=getattr(f, "file_name", ""),
                caption=getattr(f, "caption", text),
                message_type=message_type,
            )
            if ok:
                success = True

        return success

    # ============ TTS 通用处理 ============

    _tts_cache: Dict[str, str] = {}  # text_hash → audio_path, 短 TTL 缓存

    def _tts_should_voice(self) -> bool:
        """是否应发送语音到平台（仅支持语音的平台）"""
        try:
            import json

            with open("config/tts_config.json", "r", encoding="utf-8") as f:
                c = json.load(f)
            return c.get("enabled", False) and c.get("qq_default_mode") == "voice"
        except Exception:
            return False

    def _tts_should_local(self) -> bool:
        """是否应本地电脑播放"""
        try:
            import json

            with open("config/tts_config.json", "r", encoding="utf-8") as f:
                c = json.load(f)
            return c.get("local_playback_enabled", False)
        except Exception:
            return False

    def _tts_platform_supports_voice(self) -> bool:
        """当前平台是否支持发送语音消息"""
        return self.platform_id in ("aiocqhttp", "qqofficial")

    async def _tts_process(self, text: str, **send_kwargs) -> tuple[str | None, bool]:
        """
        通用 TTS 处理：合成 + 可选发送语音 + 本地播放
        返回 (audio_path, sent_as_voice)
        平台发送端据此决定是否跳过文字发送

        send_kwargs 会透传给 _tts_send_voice（如 msg_type / target_id），
        便于平台覆写发送实现时拿到目标上下文。
        """
        should_voice = self._tts_should_voice() and self._tts_platform_supports_voice()
        should_local = self._tts_should_local()
        if not should_voice and not should_local:
            return None, False
        if not text or not text.strip():
            return None, False

        try:
            from core.tts.engine_router import synthesize

            audio_path = await synthesize(text)
        except Exception as e:
            logger.debug(f"[{self.platform_id}] TTS 合成失败: {e}")
            return None, False

        if not audio_path:
            return None, False

        sent = False
        if should_voice:
            try:
                sent = await self._tts_send_voice(audio_path, text, **send_kwargs)
            except Exception as e:
                logger.warning(f"[{self.platform_id}] TTS 语音发送失败: {e}")

        if should_local:
            _set_live2d_state("talking")
            try:
                await self._tts_play_local(audio_path)
            finally:
                _set_live2d_state("idle")

        return audio_path, sent

    async def _tts_send_voice(self, audio_path: str, text: str, **kwargs) -> bool:
        """发送语音到平台，子类可覆写"""
        return False

    async def _tts_play_local(self, audio_path: str):
        """本地电脑播放（子进程隔离，避免 simpleaudio 崩溃拖垮主进程）"""
        try:
            from core.audio_player import start_audio_subprocess

            proc = start_audio_subprocess(audio_path)
            if proc is not None:
                await asyncio.to_thread(proc.join)
        except ImportError:
            logger.debug("audio_player 不可用，跳过本地播放")
        except Exception as e:
            logger.debug(f"本地播放异常: {e}")

    async def _tts_play_response(self, text: str):
        """TTS 本地播放响应 (fire-and-forget, 所有平台共享)"""
        # 支持语音的平台自己处理本地播放（发送语音后直接播同一文件）
        if self._tts_should_voice() and self._tts_platform_supports_voice():
            return

        try:
            from core.tts.engine_router import synthesize

            logger.info(f"[{self.platform_id}] TTS 本地合成中... ({len(text)} chars)")
            audio_path = await synthesize(text)
            if audio_path:
                logger.info(f"[{self.platform_id}] TTS 本地播放中...")
                _set_live2d_state("talking")
                try:
                    await self._tts_play_local(audio_path)
                finally:
                    _set_live2d_state("idle")
                logger.info(f"[{self.platform_id}] TTS 本地播放完成")
            else:
                logger.warning(f"[{self.platform_id}] TTS 合成返回空路径")
        except Exception as e:
            logger.warning(f"[{self.platform_id}] TTS 本地播放失败: {e}")


async def _dispatch_slash_command(
    platform: Any, content: str, user_id: str, group_id: str, message_type: str
) -> str | None:
    """统一斜杠命令分发（唯一命令入口）"""
    try:
        from core.command_system import CommandContext, get_command_registry

        registry = get_command_registry()
        match = registry.match(content)
        if not match:
            return None

        command_name, subcommand, args = match

        # 构建上下文
        ctx = CommandContext(
            sender_id=int(user_id) if user_id.isdigit() else 0,
            user_id=user_id,
            group_id=int(group_id) if group_id and group_id.isdigit() else 0,
            scope="private" if message_type == "private" else "group",
        )

        # 注入平台能力
        ctx.onebot_client = getattr(platform, "_ws", None)

        async def send_group_msg(gid, text):
            if hasattr(platform, "_send_onebot_reply"):
                await platform._send_onebot_reply(str(gid), text, message_type="group", group_id=str(gid))

        async def send_private_msg(uid, text):
            if hasattr(platform, "_send_onebot_reply"):
                await platform._send_onebot_reply(str(uid), text, message_type="private", user_id=str(uid))

        ctx.send_group_message = send_group_msg
        ctx.send_private_message = send_private_msg

        # 注入系统组件
        try:
            from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

            ctx.knowledge_store = get_knowledge_store()
        except Exception:
            pass

        miya = getattr(platform, "_miya_core", None)
        if miya:
            ctx.ai_client = getattr(miya, "ai_client", None)
            ctx.cognitive_service = getattr(miya, "cognitive_service", None)

        # 权限信息 — 从 permissions.json 读取
        ctx.superadmin_qq = int(os.getenv("QQ_SUPERADMIN_QQ", "0"))
        ctx.bot_qq = int(os.getenv("QQ_BOT_QQ", "0"))
        try:
            from core.unified_permission import get_permission_engine

            engine = get_permission_engine()
            if engine.is_superadmin(str(ctx.sender_id), platform=getattr(platform, "platform_id", "aiocqhttp")):
                ctx.superadmin_qq = ctx.sender_id
        except Exception:
            pass

        # 检查权限
        cmd = registry._commands.get(command_name, {})
        required_permission = cmd.get("permission", "public")

        # 子命令权限
        if subcommand and cmd.get("subcommands", {}).get(subcommand, {}).get("permission"):
            required_permission = cmd["subcommands"][subcommand]["permission"]

        if not ctx.check_permission(required_permission):
            from config.config_utils import get_command_message

            return get_command_message("permission_denied", command=command_name, permission=required_permission)

        # 限流检查
        allowed, remaining = registry.check_rate_limit(command_name, user_id, required_permission)
        if not allowed:
            from config.config_utils import get_command_message

            return get_command_message("rate_limited", seconds=f"{remaining:.0f}")

        # 执行
        result = await registry.execute(command_name, subcommand, args, ctx)
        return result

    except Exception as e:
        logger.warning(f"[Commands] 分发失败: {e}", exc_info=True)
        return None


async def _send_cmd_reply(platform: Any, response: str, user_id: str, group_id: str, message_type: str) -> None:
    """根据消息来源发送命令回复到正确的会话"""
    try:
        import json as _json

        ws = getattr(platform, "_ws", None)
        if not ws:
            await _send_private(platform, response, user_id)
            return

        if message_type == "group" and group_id:
            payload = {
                "action": "send_group_msg",
                "params": {
                    "group_id": int(group_id),
                    "message": str(response),
                },
            }
        else:
            payload = {
                "action": "send_private_msg",
                "params": {
                    "user_id": int(user_id),
                    "message": str(response),
                },
            }
        await ws.send_str(_json.dumps(payload))
    except Exception as e:
        logger.warning(f"[Commands] 回复发送失败: {e}")
        await _send_private(platform, response, user_id)


async def _send_private(platform: Any, response: str, user_id: str) -> None:
    import inspect

    if hasattr(platform, "send_private_message"):
        result = platform.send_private_message(user_id, response)
        if inspect.isawaitable(result):
            await result


async def _resolve_files_and_images(
    files: Optional[List[Any]],
    images: Optional[List[Any]],
    perception_data: Dict[str, Any],
    content: str = "",
    user_id: str = "",
    platform_id: str = "",
) -> None:
    """将 files/images 列表解析并注入到 perception_data 中。

    持久化文件库策略：
    - 收到文件 → 立即存入 FileLibrary（存盘 + 索引），仅注入元数据摘要
    - 用户后续发问询消息 → 从 FileLibrary 取最近文件，触发 analyze_content，注入结果
    - 文件永久保存于 data/downloads/，跨会话可用

    图片视觉识别（跨平台统一下沉）：
    - 对当前消息附带的图片调用 MultiVisionAnalyzer 做视觉分析
    - 注入 perception_data["image_analysis"] + ["has_image"]，由决策层接管
    - 受 qq_config.yaml 的 image_recognition.cross_platform 开关控制
    """
    from core.file_context import FileContext
    from core.file_library import get_file_library

    library = get_file_library()
    platform = platform_id or str(perception_data.get("platform", ""))
    uid = user_id or str(perception_data.get("user_id", ""))

    # 当前消息如果有文件，存入文件库
    if files:
        for f in files:
            if isinstance(f, FileContext) and f.file_data:
                library.add_file(f, platform=platform, user_id=uid)

    # 构建要处理的文件列表：当前消息的文件 OR 文件库中的最近文件
    received_files = list(files or [])
    received_images = list(images or [])
    if not received_files and uid:
        recent = library.get_recent_files(user_id=uid, minutes=30, limit=10)
        if recent:
            received_files = [library.read_file(r.file_id) for r in recent]
            received_files = [fc for fc in received_files if fc is not None]

    if not received_files and not images:
        return

    # ── 跨平台统一图片视觉分析 ──
    # 使 Telegram/Discord/QQ官方/微信/飞书等所有走 images 参数的平台都能识别图片内容
    if received_images:
        await _analyze_platform_images(received_images, perception_data, platform=platform)

    # 判断是否来自当前消息（即时解析）还是文件库缓存（问询触发）
    is_current_files = bool(files)

    # 即时解析：当前消息附带的文件 → 始终解析；文件库缓存 → 问询触发
    if is_current_files:
        should_analyze = True
    else:
        from config.config_utils import get_text

        _QUERY_KEYWORDS = get_text("file_query", "query_keywords", default=[])
        _QUESTION_MARKERS = get_text("file_query", "question_markers", default=[])
        has_query_kw = any(kw in (content or "") for kw in _QUERY_KEYWORDS)
        is_question = any(m in (content or "") for m in _QUESTION_MARKERS)
        should_analyze = has_query_kw or is_question

    def _normalize(raw_list: Optional[List[Any]]) -> List[Dict[str, Any]]:
        if not raw_list:
            return []
        result = []
        for item in raw_list:
            if isinstance(item, FileContext):
                item_dict = item.to_dict()
                if should_analyze and item.file_data:
                    analysis = item.analyze_content()
                    if analysis:
                        item_dict["analysis_result"] = analysis
                result.append(item_dict)
            elif isinstance(item, dict):
                result.append(item)
        return result

    file_dicts = _normalize(received_files)
    image_dicts = _normalize(received_images)

    if file_dicts:
        perception_data["files"] = file_dicts
    if image_dicts:
        perception_data["images"] = image_dicts

    summaries = []
    for fd in image_dicts:
        name = fd.get("file_name", "")
        summaries.append(f"[图片: {name}]" if name else "[图片]")
    for fd in file_dicts:
        name = fd.get("file_name", "")
        ftype = fd.get("file_type", "unknown")
        size = fd.get("file_size", 0)
        size_str = ""
        if size > 0:
            if size < 1024:
                size_str = f" {size}B"
            elif size < 1024 * 1024:
                size_str = f" {size / 1024:.1f}KB"
            else:
                size_str = f" {size / (1024 * 1024):.1f}MB"
        status = " [已读取]" if fd.get("analysis_result") else ""
        summaries.append(f"[{ftype}: {name}{size_str}{status}]")

    if summaries:
        existing_content = perception_data.get("content", "")
        perception_data["content"] = f"{existing_content}\n{' '.join(summaries)}"

    # 如果有解析结果，注入到 content 末尾
    if should_analyze:
        analyzed = [fd.get("analysis_result") for fd in file_dicts if fd.get("analysis_result")]
        if analyzed:
            file_content = "\n---\n文件内容:\n" + "\n---\n".join(analyzed)
            # 截断过长内容，避免终端刷屏
            max_content_chars = 3000
            if len(file_content) > max_content_chars:
                file_content = file_content[:max_content_chars] + "\n...(文件内容已截断, 完整内容 AI 仍可见)"
            perception_data["content"] += file_content


def _cross_platform_vision_enabled(platform: str) -> bool:
    """跨平台图片识别总开关 + 按平台开关"""
    from config.config_utils import get_qq_config

    enabled = get_qq_config("qq", "image_recognition", "cross_platform", "enabled", default=True)
    if not enabled:
        return False
    platforms = get_qq_config("qq", "image_recognition", "cross_platform", "platforms", default={}) or {}
    default_on = platforms.get("default", True)
    return bool(platforms.get(platform, default_on))


def _cross_platform_vision_max_images() -> int:
    """单条消息最多分析的图片数"""
    from config.config_utils import get_qq_config

    try:
        return int(get_qq_config("qq", "image_recognition", "cross_platform", "max_images", default=2) or 2)
    except (TypeError, ValueError):
        return 2


async def _get_image_bytes(fc: Any, timeout: int = 30) -> Optional[bytes]:
    """从 FileContext 取图片字节（兼容 file_data / file_path / file_url 三种来源）"""
    if getattr(fc, "file_data", None):
        return fc.file_data
    file_path = getattr(fc, "file_path", None)
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except OSError as e:
            logger.debug(f"[MessageMixin] 读取本地图片失败: {e}")
            return None
    file_url = getattr(fc, "file_url", None)
    if file_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(file_url)
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            logger.debug(f"[MessageMixin] 下载图片失败: {e}")
    return None


async def _analyze_platform_images(
    images: List[Any],
    perception_data: Dict[str, Any],
    platform: str = "",
) -> None:
    """对平台图片做统一视觉分析，注入 image_analysis / has_image。

    仅当全局开关 + 平台开关开启时执行；失败静默回退（保留 [图片: 文件名] 摘要）。
    分析结果由决策层自动注入 AI 上下文（见 decision_hub 的 [图片描述] 处理）。
    """
    if not _cross_platform_vision_enabled(platform):
        return

    from core.file_context import FileContext

    try:
        from core.multi_vision_analyzer import get_vision_analyzer
    except Exception:
        return

    analyzer = None
    max_images = _cross_platform_vision_max_images()

    from config.config_utils import get_qq_config

    timeout = int(get_qq_config("qq", "image_recognition", "cross_platform", "timeout", default=30) or 30)

    for fc in images[:max_images]:
        if not isinstance(fc, FileContext):
            continue
        data = await _get_image_bytes(fc, timeout=timeout)
        if not data:
            continue
        try:
            if analyzer is None:
                analyzer = await get_vision_analyzer()
            result = await analyzer.analyze_image(data)
            if result.success:
                perception_data["image_analysis"] = result.to_context_dict()
                perception_data["has_image"] = True
                logger.info(f"[MessageMixin] {platform} 图片视觉分析完成: {result.description[:50]}")
                break
        except Exception as e:
            logger.debug(f"[MessageMixin] {platform} 图片视觉分析失败: {e}")
