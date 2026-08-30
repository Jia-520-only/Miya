"""
记忆管理器 (Memory Manager)

职责：
1. 用户消息存储
2. AI响应存储
3. 统一跨平台记忆存储
4. 对话历史管理
5. 记忆压缩
"""

import contextlib
import logging
import re
from typing import Any, Dict, List, Optional

from config.config_utils import get_text
from core.token_utils import count_message_tokens
from memory import MemoryLevel, get_memory_bus, load_memory_config
from memory.historian import get_historian

logger = logging.getLogger(__name__)

_MEM_CONFIG = load_memory_config()
_AUTO_DETECT_PATTERNS = [
    (p[0], p[1], p[2]) for p in _MEM_CONFIG.get("classification", {}).get("auto_detect_regex_patterns", [])
]
_RECALL_PATTERNS = get_text(
    "conversation_context",
    "recall_patterns",
    default=_MEM_CONFIG.get("classification", {}).get("recall_detection_patterns", []),
)


class MemoryManager:
    """
    记忆管理器

    单一职责：处理所有与记忆存储和管理相关的逻辑
    """

    def __init__(
        self,
        memory_net: Optional[Any] = None,
        memory_engine: Optional[Any] = None,
    ):
        self.memory_net = memory_net
        self.memory_engine = memory_engine
        self._bus = None  # MemoryBus lazy init
        self.historian = get_historian()
        # 【时间对照】初始化时间追踪器
        try:
            from memory.time_tracker import get_time_tracker

            self.time_tracker = get_time_tracker()
        except Exception:
            self.time_tracker = None
        logger.info("[记忆管理器] 初始化完成 (MemoryBus V4.0)")

    async def _get_bus(self):
        if self._bus is None:
            self._bus = await get_memory_bus()
        return self._bus

    @staticmethod
    def _build_session_id(platform: str, user_id: str, group_id: str, message_type: str) -> str:
        """构建统一会话ID（不含平台前缀，platform 仅作元数据标签）"""
        if message_type == "group" and group_id:
            return f"group_{group_id}_{user_id}"
        return f"user_{user_id}"

    async def store_user_message(self, perception: Dict) -> None:
        """
        存储用户消息到记忆系统

        Args:
            perception: 感知数据
        """
        try:
            content = perception.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        item_data = item.get("data", {})
                        if item_type == "text":
                            text_parts.append(item_data.get("text", ""))
                        elif item_type == "image":
                            text_parts.append("[图片]")
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = " ".join(text_parts) if text_parts else ""

            user_id = str(perception.get("user_id", "unknown"))
            group_id = str(perception.get("group_id", ""))
            platform = perception.get("platform", "qq")
            sender_name = perception.get("sender_name", "用户")
            message_type = perception.get("message_type", "")
            session_id = self._build_session_id(platform, user_id, group_id, message_type)

            logger.info(f"[记忆管理器] 收到消息: {content[:50]}...")

            # 【时间对照】记录交互时间戳
            if self.time_tracker:
                try:
                    self.time_tracker.record_interaction(
                        user_id=user_id,
                        platform=platform,
                        role="user",
                        session_start=False,
                        message_preview=content[:50],
                    )
                except Exception:
                    pass

            # 自动检测重要信息（从 memory_config.json 加载模式）
            detected_importance = 0.0
            detected_info_type = None
            for pattern, info_type, priority in _AUTO_DETECT_PATTERNS:
                if re.search(pattern, content):
                    detected_importance = priority
                    detected_info_type = info_type
                    break

            # 存储到 MemoryNet 对话历史
            if self.memory_net and self.memory_net.conversation_history:
                metadata = {
                    "user_id": user_id,
                    "group_id": group_id,
                    "message_type": message_type,
                    "sender": sender_name,
                    "chat_label": f"群聊_{group_id}" if message_type == "group" and group_id else "私聊",
                }
                if detected_importance > 0:
                    metadata["importance"] = detected_importance
                    metadata["importance_tags"] = [detected_info_type] if detected_info_type else []
                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role="user",
                    content=content,
                    metadata=metadata,
                )

                # 每 3 条消息强制 flush 到磁盘
                self._conv_save_counter = getattr(self, "_conv_save_counter", 0) + 1
                if self._conv_save_counter % 3 == 0:
                    with contextlib.suppress(Exception):
                        await self.memory_net.conversation_history.flush()

            # 存储到统一记忆系统 (新版 API) — V4.1.11: 复用 bus
            bus = await self._get_bus()
            await bus.store_dialogue(
                content=content,
                role="user",
                user_id=user_id,
                session_id=session_id,
                platform=platform,
                metadata={
                    "sender_name": sender_name,
                    "message_type": message_type,
                    "group_id": group_id,
                },
            )

            if detected_importance > 0 and detected_info_type:
                # V4.1.11: 去重检查（内容 hash 比对，避免子串误匹配）
                import hashlib

                content_hash = hashlib.md5(content[:200].encode()).hexdigest()
                existing = await bus.get_user_memories(user_id=user_id, level=MemoryLevel.LONG_TERM, limit=20)
                is_duplicate = False
                for e in existing or []:
                    e_hash = hashlib.md5((e.content or "")[:200].encode()).hexdigest()
                    if e_hash == content_hash and e.tags and detected_info_type in e.tags:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    await bus.store_important(
                        content=content,
                        user_id=user_id,
                        tags=[detected_info_type],
                        priority=detected_importance,
                        metadata={
                            "source": "auto_extract",
                            "info_type": detected_info_type,
                        },
                    )
                    logger.info(f"[记忆管理器] 已自动存储重要信息: {detected_info_type}")
                else:
                    logger.debug(f"[记忆管理器] 跳过重复重要信息: {detected_info_type}")

        except Exception as e:
            logger.error(f"[记忆管理器] 存储用户消息失败: {e}", exc_info=True)

    async def store_assistant_response(self, perception: Dict, response: str) -> None:
        """
        存储 AI 响应到记忆系统（V4.1.11: 精简链路 + 去重）

        优化：
        - 合并冗余的存储操作，消除重复写入
        - 星璇自记忆 → store_dialogue 后批量处理，降低异步调度开销
        - Historian / LifeBook / 每日摘要 延迟到后台执行（不阻塞响应返回）

        Args:
            perception: 感知数据
            response: AI 响应内容
        """
        try:
            user_id = str(perception.get("user_id", "unknown"))
            group_id = str(perception.get("group_id", ""))
            message_type = perception.get("message_type", "")
            platform = perception.get("platform", "qq")
            session_id = self._build_session_id(platform, user_id, group_id, message_type)

            if self.time_tracker:
                try:
                    self.time_tracker.record_interaction(
                        user_id=user_id,
                        platform=platform,
                        role="assistant",
                        session_start=False,
                        message_preview=response[:50],
                    )
                except Exception:
                    pass

            # 步骤1: 核心存储 — 对话历史（MemoryBus store_dialogue）
            assistant_importance = self._calc_assistant_importance(response)
            bus = await self._get_bus()

            await bus.store_dialogue(
                content=response,
                role="assistant",
                user_id=user_id,
                session_id=session_id,
                platform=platform,
                metadata={
                    "sender_name": "弥娅",
                    "message_type": message_type,
                    "group_id": group_id,
                },
            )

            # 步骤2: 星璇自记忆检测（复用 bus 引用，不额外创建）
            user_content = perception.get("content", "")
            if user_content:
                try:
                    await self._analyze_and_upgrade_assistant_memory(
                        user_input=user_content,
                        ai_response=response,
                        user_id=user_id,
                        group_id=group_id,
                        message_type=message_type,
                    )
                except Exception as e:
                    logger.debug(f"[记忆管理器] 弥娅自记忆分析失败: {e}")

            # 步骤3: MemoryNet 对话历史（仅在可用时写入）
            if self.memory_net and self.memory_net.conversation_history:
                try:
                    metadata = {
                        "user_id": user_id,
                        "group_id": group_id,
                        "message_type": message_type,
                        "sender": "弥娅",
                        "chat_label": f"群聊_{group_id}" if message_type == "group" and group_id else "私聊",
                    }
                    if assistant_importance > 0:
                        metadata["importance"] = assistant_importance
                    await self.memory_net.conversation_history.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=response,
                        metadata=metadata,
                    )
                except Exception:
                    pass

            # 步骤4: Historian / LifeBook / 每日摘要 → 后台延迟执行（V4.1.11: 不阻塞响应路径）
            import asyncio as _asyncio

            _asyncio.ensure_future(
                self._background_memory_enrichment(
                    user_input=user_content,
                    ai_response=response,
                    user_id=user_id,
                    group_id=group_id,
                    message_type=message_type,
                    platform=platform,
                    session_id=session_id,
                    perception_emotion=str(perception.get("emotion", "平静")),
                )
            )

        except Exception as e:
            logger.error(f"[记忆管理器] 存储 AI 响应失败: {e}")

    async def _background_memory_enrichment(
        self,
        user_input: str,
        ai_response: str,
        user_id: str,
        group_id: str,
        message_type: str,
        platform: str,
        session_id: str,
        perception_emotion: str,
    ) -> None:
        """后台记忆增强：Historian + 每日摘要（V4.1.11 并行调度）"""
        try:
            import asyncio as _asyncio

            async def _run_historian():
                try:
                    await self.historian.process_conversation(
                        user_input=user_input,
                        ai_response=ai_response,
                        user_id=user_id,
                        group_id=group_id,
                        message_type=message_type,
                    )
                except Exception as e:
                    logger.debug(f"[后台] Historian 失败: {e}")

            async def _run_daily_summary():
                try:
                    from datetime import datetime as dt
                    from datetime import timedelta

                    today = dt.now().strftime("%Y-%m-%d")
                    self._last_summary_date = getattr(self, "_last_summary_date", "")
                    if self._last_summary_date and self._last_summary_date != today:
                        bus = await self._get_bus()
                        yesterday = (dt.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                        daily = await bus.core.get_daily_dialogues(yesterday)
                        if daily and len(daily) >= 3:
                            lines = [
                                f"- {m.content[:80]}..." if len(m.content) > 80 else f"- {m.content}"
                                for m in daily[:20]
                            ]
                            summary_text = "\n".join(lines)
                            await bus.core.store_daily_summary(
                                date_key=yesterday,
                                summary=summary_text,
                                user_id="global",
                                dialogue_count=len(daily),
                            )
                            logger.info(f"[记忆管理器] 已生成 {yesterday} 每日摘要 ({len(daily)} 条对话)")
                    self._last_summary_date = today
                except Exception as e:
                    logger.debug(f"[后台] 每日摘要跳过: {e}")

            # V4.1.11: 并行执行独立子任务
            await _asyncio.gather(
                _run_historian(),
                _run_daily_summary(),
                return_exceptions=True,
            )

            # 对话压缩（依赖 historian 完成后再执行，顺序执行）
            try:
                if self.memory_net and self.memory_net.conversation_history:
                    messages = await self.memory_net.conversation_history.get_history(session_id, limit=100)
                    if len(messages) > 50:
                        if hasattr(self.memory_net, "compress_conversation_to_tide"):
                            await self.memory_net.compress_conversation_to_tide(session_id=session_id, recent_count=30)
                            logger.info(f"[后台] 已触发对话压缩: {session_id}")
            except Exception as e:
                logger.debug(f"[后台] 对话压缩失败: {e}")
        except Exception as e:
            logger.debug(f"[后台] 记忆增强整体失败: {e}")

    async def _analyze_and_upgrade_assistant_memory(
        self,
        user_input: str,
        ai_response: str,
        user_id: str,
        group_id: str,
        message_type: str,
    ) -> None:
        """
        【星璇增强】分析弥娅回复，自动识别并升级重要自记忆

        模式从 text_config.json 的 assistant_self.patterns 加载
        """
        import re

        # 从配置文件加载模式（通过 config_utils）
        self_config = get_text("assistant_self", default={})
        patterns = self_config.get("patterns", {})
        base_importance = self_config.get("base_importance", {})

        if not patterns:
            return

        type_label_map = {
            "commitment": "承诺",
            "opinion": "观点",
            "emotion": "情感",
            "knowledge": "知识",
            "self_awareness": "自我认知",
        }

        assistant_patterns = []
        for category, pattern_list in patterns.items():
            importance = base_importance.get(category, 0.5)
            mem_type = type_label_map.get(category, category)
            for item in pattern_list:
                if isinstance(item, list) and len(item) >= 2:
                    assistant_patterns.append((item[0], mem_type, importance, [item[1]]))

        if not assistant_patterns:
            logger.debug("[记忆管理器] 自记忆配置为空，跳过分析")
            return

        for pattern, mem_type, base_importance, tags in assistant_patterns:
            match = re.search(pattern, ai_response)
            if match:
                content = match.group(0).strip()
                if len(content) < 5:
                    continue

                # 构建记忆内容
                memory_content = f"[弥娅{mem_type}] {content}"

                # 存储为 LONG_TERM（自动升级）
                try:
                    await (await self._get_bus()).store_important(
                        content=memory_content,
                        user_id=user_id,
                        tags=tags + ["星璇自记忆", f"类型_{mem_type}"],
                        priority=min(1.0, base_importance),
                        metadata={
                            "source": "assistant_self",
                            "memory_type": mem_type,
                            "role": "assistant",
                            "group_id": group_id,
                            "message_type": message_type,
                            "original_context": user_input[:100] if user_input else "",
                        },
                    )
                    logger.info(f"[星璇·自记忆升级] {mem_type}: {content[:30]}... (priority={base_importance})")
                except Exception as e:
                    logger.debug(f"[星璇·自记忆升级] 存储失败: {e}")

                # 每个回复只记录一条最重要的，避免刷屏
                break

    async def store_unified_memory(self, perception: Dict, role: str = "user") -> None:
        """
        存储统一记忆（跨平台）

        【星璇增强】当 role="assistant" 时，自动分析弥娅回复中的
        承诺、观点、建议等重要内容，升级为 LONG_TERM 自记忆

        Args:
            perception: 感知数据
            role: 角色 ('user' 或 'assistant')
        """
        try:
            platform = perception.get("platform", "terminal")
            user_id = str(perception.get("user_id", "unknown"))
            group_id = str(perception.get("group_id", ""))
            message_type = perception.get("message_type", "")

            if role == "user":
                content = perception.get("content", "") or perception.get("input", "")
                sender_name = perception.get("sender_name", "用户")
            else:
                content = perception.get("response", "")
                sender_name = "弥娅"

            session_id = self._build_session_id(platform, user_id, group_id, message_type)

            extra_meta = perception.get("_meta", {}) if isinstance(perception.get("_meta"), dict) else {}

            # 存储到统一记忆系统
            await (await self._get_bus()).store_dialogue(
                content=content,
                role=role,
                user_id=user_id,
                session_id=session_id,
                platform=platform,
                metadata={
                    "sender_name": sender_name,
                    "group_id": perception.get("group_id", ""),
                    "message_type": perception.get("message_type", ""),
                    **extra_meta,
                },
            )

            # 存储到 MemoryNet
            if self.memory_net and self.memory_net.conversation_history:
                await self.memory_net.conversation_history.add_message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    metadata={
                        "platform": platform,
                        "user_id": user_id,
                        "sender_name": sender_name,
                        **extra_meta,
                    },
                )

            # 【星璇增强】弥娅回复时，自动分析并升级重要自记忆
            if role == "assistant" and content and len(content.strip()) >= 5:
                user_input = perception.get("content", "") or perception.get("input", "")
                group_id = perception.get("group_id", "")
                message_type = perception.get("message_type", "")
                try:
                    await self._analyze_and_upgrade_assistant_memory(
                        user_input=user_input,
                        ai_response=content,
                        user_id=user_id,
                        group_id=group_id,
                        message_type=message_type,
                    )
                except Exception as e:
                    logger.debug(f"[记忆管理器] 弥娅自记忆分析失败: {e}")

        except Exception as e:
            logger.error(f"[记忆管理器] 存储统一记忆失败: {e}")

    async def get_conversation_history(
        self, session_id: str, user_id: str = "", current_input: str = "", max_tokens: int = 2000
    ) -> List[Dict]:
        """
        获取对话历史上下文（统一检索：按 user_id 跨平台聚合）

        Args:
            session_id: 会话ID（辅助定位）
            user_id: 用户ID（主检索键，跨平台统一）
            current_input: 当前用户输入
            max_tokens: 最大token数

        Returns:
            对话历史列表
        """
        if not self.memory_net or not self.memory_net.conversation_history:
            return []

        needs_recall = self._check_needs_recall(current_input)
        max_messages = 30 if needs_recall else 8

        try:
            messages = await self.memory_net.conversation_history.get_history(session_id, limit=max_messages)

            if not messages and user_id:
                bus = await self._get_bus()
                unified_memories = await bus.get_user_dialogue(user_id=user_id, limit=max_messages)
                if unified_memories:
                    context = []
                    total_tokens = 0
                    for m in unified_memories:
                        token_estimate = count_message_tokens(m.content)
                        if total_tokens + token_estimate > max_tokens:
                            break
                        context.append(
                            {
                                "role": m.role,
                                "content": m.content,
                                "timestamp": m.created_at if hasattr(m, "created_at") else "",
                            }
                        )
                        total_tokens += token_estimate
                    return context
                return []

            if not messages:
                return []

            recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages

            context = []
            total_tokens = 0

            for msg in recent_messages:
                token_estimate = count_message_tokens(msg.content)
                if total_tokens + token_estimate > max_tokens:
                    break

                context.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp if hasattr(msg, "timestamp") else "",
                    }
                )
                total_tokens += token_estimate

            return context

        except Exception as e:
            logger.error(f"[记忆管理器] 获取对话历史失败: {e}")
            return []

    def _calc_assistant_importance(self, response: str) -> float:
        import re

        try:
            self_config = get_text("assistant_self", default={})
            patterns = self_config.get("patterns", {})
            base_importance = self_config.get("base_importance", {})
            for category, pattern_list in patterns.items():
                imp = base_importance.get(category, 0.5)
                for item in pattern_list:
                    pattern_regex = item[0] if isinstance(item, list) and len(item) >= 2 else item
                    if isinstance(pattern_regex, str) and re.search(pattern_regex, response):
                        return imp
        except Exception:
            pass
        return 0.0

    def _check_needs_recall(self, user_input: str) -> bool:
        """检测用户是否在问关于过去的问题（模式从配置加载）"""
        if not user_input:
            return False

        for pattern in _RECALL_PATTERNS:
            if re.search(pattern, user_input):
                logger.info(f"[记忆管理器] 检测到回忆请求: {user_input[:30]}")
                return True

        return False

    async def get_memory_stats(self) -> Dict:
        """获取记忆统计信息"""
        try:
            bus = await self._get_bus()
            return await bus.stats()
        except Exception as e:
            logger.error(f"[记忆管理器] 获取统计失败: {e}")
            return {}
