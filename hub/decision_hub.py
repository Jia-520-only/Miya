"""
决策层 Hub
监听 M-Link 消息并协调各子网进行决策

架构：门面模式 (Facade Pattern)
- DecisionHub 作为协调器，委托给各个专业处理器
- PerceptionHandler: 感知处理
- ResponseGenerator: 响应生成
- EmotionController: 情绪控制
- MemoryManager: 记忆管理
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.text_loader import get_text
from core.ai_client import AIMessage
from core.model_pool_manager import TaskType
from core.unified_platform.platform_type import MiyaPlatform

# 导入辅助模块
from hub.context_builder import ContextBuilder, ConsumerRequest
from hub.conversation_context import ConversationContextManager
from hub.memory_manager import MemoryManager

# 导入新的处理器类
from hub.perception_handler import PerceptionHandler
from hub.platform_tools import PlatformToolsManager
from hub.response_generator import ResponseGenerator
from hub.session_handler import SessionHandler

# 导入智能记忆系统
from memory.cognitive_engine import get_cognitive_engine
from memory.historian import get_historian
from memory.session_manager import (
    SessionManager,
    init_session_manager,
)
from mlink.message import Message

logger = logging.getLogger(__name__)


# Stage 1: 纯函数已迁移到 hub.decision_hub_helpers。
# 上方同名旧实现暂时保留，但会被以下导入覆盖；后续阶段将物理删除。
from hub.decision_hub_helpers import (  # noqa: E402
    _MINIMAL_EMOTION_GUIDANCE,
    _build_integrated_status,
    _build_memory_guard,
    _build_spine_status_prompt,
    _get_emotion_guidance,
    _is_reminder_request,
    _load_strategy_descriptions,
)


class DecisionHub:
    """
    决策层 Hub (门面/协调器)

    职责：
    1. 监听来自 QQNet 的感知数据（data_flow）
    2. 协调各处理器生成响应
    3. 将响应通过 M-Link 发送回 QQNet

    架构：门面模式 (Facade Pattern)
    - 将具体职责委托给专业处理器
    - PerceptionHandler: 感知处理（权限、命令检测、响应判断）
    - ResponseGenerator: 响应生成（AI调用、工具编排）
    - EmotionController: 情绪控制（情绪更新、染色、衰减）
    - MemoryManager: 记忆管理（存储、检索、压缩）
    """

    def __init__(
        self,
        mlink,
        ai_client,
        emotion,
        personality,
        prompt_manager,
        memory_net,
        decision_engine,
        tool_subnet=None,
        memory_engine=None,
        scheduler=None,
        onebot_client=None,
        identity=None,
        model_pool=None,
        model_scheduler=None,
        miya_instance=None,
        unified_memory=None,
        platform_registry=None,
    ):
        """
        初始化决策层

        Args:
            mlink: M-Link 核心实例
            ai_client: AI 客户端（默认模型）
            emotion: 情绪系统
            personality: 人格系统
            prompt_manager: Prompt 管理器
            memory_net: MemoryNet 记忆系统
            decision_engine: 决策引擎
            tool_subnet: ToolNet 子网实例
            memory_engine: 记忆引擎
            scheduler: 调度器
            onebot_client: OneBot 客户端
            identity: 身份系统
            model_pool: 多模型管理器
            model_scheduler: AI 模型调度裁判
            miya_instance: Miya 实例
        """
        # 核心组件引用（保留用于兼容性）
        self.mlink = mlink
        self.ai_client = ai_client
        self.emotion = emotion
        self.personality = personality
        self.prompt_manager = prompt_manager
        self.memory_net = memory_net
        self.decision_engine = decision_engine
        self.tool_subnet = tool_subnet
        self.memory_engine = memory_engine
        self.scheduler = scheduler
        self.onebot_client = onebot_client
        self.identity = identity
        self.model_pool = model_pool
        self.model_scheduler = model_scheduler
        self.miya_instance = miya_instance
        self.platform_registry = platform_registry

        # 当前使用的模型信息（用于日志显示）
        self._last_selected_model: str = ""
        self._last_task_type: str = ""

        # FIX: AdvancedOrchestrator 的工具执行包装器会读取 self.tool_context；此处必须初始化，避免首次使用抛 AttributeError。
        self.tool_context = None

        # 对话历史上下文配置
        self.enable_conversation_context = True
        self.conversation_context_max_count = 10
        self.conversation_context_max_tokens = 2000

        # 终端执行能力由 DSH (DeepSeek Harness) 提供
        # DSH 作为弥娅的"手"/肢体工具，守护进程通过 MCP/子进程调用 DSH

        # 高级编排器（懒加载）
        self._advanced_orchestrator: Any | None = None
        self._advanced_orchestrator_initialized: bool = False

        # 鉴权子网
        self.auth_subnet: Any | None = None

        # 【新增】灵魂发生器
        self._soul_generator: Any | None = None
        self._init_soul_generator()
        self._init_auth_subnet()

        # 【加速】Soul 结果缓存 — 复用上一轮情绪避免阻塞主响应
        self._soul_cache: dict = {}
        self._soul_cache_max_size: int = 100
        self._soul_cache_ttl: float = 1800.0

        # 【持久化】启动时恢复 soul 快照 + 诞生时间
        self._init_soul_snapshot()
        self._init_birth_time()

        # 响应回调
        self.response_callback: Callable | None = None

        # 会话管理器
        self.session_manager: SessionManager = self._init_session_manager()

        # ========== 初始化专业处理器（门面模式核心）==========

        # 1. 感知处理器
        self.perception_handler = PerceptionHandler(
            auth_subnet=self.auth_subnet,
            onebot_client=self.onebot_client,
        )

        # 2. 记忆管理器
        self.memory_manager = MemoryManager(
            memory_net=self.memory_net,
            memory_engine=self.memory_engine,
        )

        # 4. 响应生成器
        self.response_generator = ResponseGenerator(
            ai_client=self.ai_client,
            personality=self.personality,
            prompt_manager=self.prompt_manager,
            tool_subnet=self.tool_subnet,
            memory_engine=self.memory_engine,
            model_pool=self.model_pool,
            identity=self.identity,
        )

        # 5. 对话上下文管理器（保留 topic tracking 功能）
        self.conversation_context_manager = ConversationContextManager(
            memory_net=self.memory_net,
            enable_conversation_context=self.enable_conversation_context,
            conversation_context_max_count=self.conversation_context_max_count,
            conversation_context_max_tokens=self.conversation_context_max_tokens,
        )

        # 5b. 统一上下文管道 (v8.0+): 一次读取，多组件共享
        self.context_builder = ContextBuilder(memory_net=self.memory_net)

        # 6. 平台工具管理器
        self.platform_tools_manager = PlatformToolsManager(tool_subnet=self.tool_subnet)

        # 7. 会话处理器
        self.session_handler = SessionHandler()

        # Stage 2: 服务化编排器已接线，但默认仍走旧门面路径，避免行为漂移。
        self.service_orchestrator = None
        self._service_orchestrator_enabled = False
        self._init_service_orchestrator()

        logger.info("决策层 Hub 初始化完成（门面模式：感知/情绪/记忆/响应处理器 + 辅助模块）")

        # 9. 安全服务 / 10. 注入检测 / 11. 协作引擎 / 12. 主动聊天 — 后台延迟初始化
        self._deferred_init_event = threading.Event()
        self.proactive_chat = None
        self.proactive_coordinator = None
        self._start_deferred_init()

    def _init_service_orchestrator(self) -> None:
        """Stage 2: 将旧 DecisionHub 依赖接线到 hub.services.MiyaOrchestrator"""
        try:
            from hub.services.orchestrator import MiyaOrchestrator

            self.service_orchestrator = MiyaOrchestrator().wire_from_legacy(
                perception_handler=self.perception_handler,
                auth_subnet=self.auth_subnet,
                soul_generator=self._soul_generator,
                emotion=self.emotion,
                personality=self.personality,
                decision_engine=self.decision_engine,
                model_pool=self.model_pool,
                model_scheduler=self.model_scheduler,
                ethics=getattr(self, "ethics", None),
                ai_client=self.ai_client,
                prompt_manager=self.prompt_manager,
                tool_subnet=self.tool_subnet,
                response_generator=self.response_generator,
                collaboration_engine=getattr(self, "collaboration_engine", None),
                identity=self.identity,
                memory_net=self.memory_net,
                memory_engine=self.memory_engine,
                memory_manager=self.memory_manager,
                historian=None,
                lifebook=None,
                session_manager=self.session_manager,
                session_handler=self.session_handler,
            )
            logger.info("[决策层] Stage 2 服务化编排器接线完成（默认未接管消息流）")
        except Exception as e:
            logger.warning(f"[决策层] Stage 2 服务化编排器接线失败: {e}")
            self.service_orchestrator = None

    def enable_service_orchestrator(self, enabled: bool = True) -> None:
        """显式启用服务化编排器（后续阶段可在配置中默认开启）"""
        self._service_orchestrator_enabled = bool(
            enabled and self.service_orchestrator and self.service_orchestrator.is_ready()
        )
        logger.info(f"[决策层] 服务化编排器启用状态: {self._service_orchestrator_enabled}")

    def service_orchestrator_ready(self) -> bool:
        return bool(self.service_orchestrator and self.service_orchestrator.is_ready())

    async def process_with_service_orchestrator(self, message: Message) -> Optional[str]:
        """使用服务化编排器处理消息，供灰度调用方显式接入"""
        if not self._service_orchestrator_enabled:
            logger.warning("[决策层] 服务化编排器尚未启用，请先调用 enable_service_orchestrator(True)")
            return None
        if not self.service_orchestrator_ready():
            logger.warning("[决策层] 服务化编排器未就绪")
            return None
        return await self.service_orchestrator.process_message(message)

    def get_service_orchestrator_status(self) -> dict:
        if not self.service_orchestrator:
            return {"available": False, "enabled": False}
        status = self.service_orchestrator.get_status()
        status["enabled"] = self._service_orchestrator_enabled
        return status

    def _set_soul_cache(self, user_id: str, data: dict):
        import time

        data["_ts"] = time.time()
        if len(self._soul_cache) >= self._soul_cache_max_size:
            oldest = min(self._soul_cache, key=lambda k: self._soul_cache[k].get("_ts", 0))
            del self._soul_cache[oldest]
        self._soul_cache[user_id] = data

    def _get_soul_cache(self, user_id: str) -> dict:
        import time

        entry = self._soul_cache.get(user_id, {})
        if entry and time.time() - entry.get("_ts", 0) > self._soul_cache_ttl:
            del self._soul_cache[user_id]
            return {}
        return entry

    @staticmethod
    def _calc_cognitive_limit(conversation_context: list, needs_recall: bool = False) -> int:
        conv_len = len(conversation_context) if conversation_context else 0
        if needs_recall or conv_len > 15:
            return 30
        elif conv_len > 5:
            return 15
        return 5

    def _init_soul_snapshot(self):
        """启动时加载 soul 缓存快照，避免冷启动等待"""
        try:
            snap_path = Path(__file__).parent.parent / "data" / "soul_snapshot.json"
            if snap_path.exists():
                with open(snap_path, "r", encoding="utf-8") as f:
                    self._soul_cache = json.load(f)
                logger.info(f"[Soul快照] 已恢复 {len(self._soul_cache)} 个用户的缓存")
        except Exception:
            logger.warning("[Soul快照] 恢复失败，将使用空缓存启动")
            pass

    def _save_soul_snapshot(self):
        """保存 soul 缓存到磁盘"""
        try:
            if not self._soul_cache:
                return
            snap_path = Path(__file__).parent.parent / "data" / "soul_snapshot.json"
            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump(self._soul_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.warning("[Soul快照] 保存失败，不影响主流程")
            pass

    def _init_birth_time(self):
        """初始化弥娅诞生时间与运行时间感知"""
        self._birth_path = Path(__file__).parent.parent / "data" / "miya_birth.json"
        self._birth_data: dict = {}
        try:
            if self._birth_path.exists():
                with open(self._birth_path, "r", encoding="utf-8") as f:
                    self._birth_data = json.load(f)
            else:
                by, bm, bd = 2025, 3, 20
                try:
                    cfg_path = Path(__file__).parent.parent / "config" / "text_config.json"
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    identity_cfg = cfg.get("identity", {})
                    by = identity_cfg.get("birth_year", 2025)
                    bm = identity_cfg.get("birth_month", 3)
                    bd = identity_cfg.get("birth_day", 20)
                except Exception:
                    pass
                now = datetime.now()
                birth_iso = datetime(by, bm, bd).isoformat()
                self._birth_data = {"created_at": birth_iso, "started_at": now.isoformat()}
                self._birth_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._birth_path, "w", encoding="utf-8") as f:
                    json.dump(self._birth_data, f, ensure_ascii=False, indent=2)
            self._started_at = datetime.now()
            self._birth_data["started_at"] = self._started_at.isoformat()
            self._birth_data["last_active_at"] = self._started_at.isoformat()
            with open(self._birth_path, "w", encoding="utf-8") as f:
                json.dump(self._birth_data, f, ensure_ascii=False, indent=2)
            birth = datetime.fromisoformat(self._birth_data["created_at"])
            delta = datetime.now() - birth
            logger.info(f"[时间感知] 弥娅已陪伴佳 {delta.days} 天 (诞生于 {birth.strftime('%Y-%m-%d %H:%M')})")
            # 注入到 identity 系统，让 personality status 里也能看到
            if self.identity:
                self.identity.birth_time = birth
        except Exception as e:
            logger.debug(f"[时间感知] 初始化失败: {e}")

    def _get_temporal_awareness(self, user_id: str = "", platform: str = "") -> str:
        """构建时间感知文本（含时间对照）"""
        try:
            if not hasattr(self, "_birth_data") or not self._birth_data:
                return ""
            birth = datetime.fromisoformat(self._birth_data["created_at"])
            days = (datetime.now() - birth).days
            uptime = datetime.now() - self._started_at if hasattr(self, "_started_at") else None

            parts = [f"弥娅已陪伴佳 {days} 天（诞生于 {birth.strftime('%Y-%m-%d')}）"]
            if uptime:
                h = int(uptime.total_seconds() // 3600)
                m = int((uptime.total_seconds() % 3600) // 60)
                if h > 0:
                    parts.append(f"本次已在线 {h} 小时 {m} 分")
                else:
                    parts.append(f"本次已在线 {m} 分钟")

            # 自检状态注入 — 弥娅知道自己最近一次体检结果（自检看护器官维护该文件）
            try:
                _sc_file = Path(__file__).resolve().parent.parent / "data" / "self_care_last.json"
                if _sc_file.is_file():
                    _sc = json.loads(_sc_file.read_text(encoding="utf-8"))
                    if isinstance(_sc, dict) and _sc.get("note"):
                        _sc_at = str(_sc.get("at") or "").replace("T", " ")[5:16]
                        parts.append(
                            f"上次自检 {_sc_at} · {_sc['note']}"
                            f"（平台 {_sc.get('platforms_online', '?')} 在线）"
                        )
                        _sc_data = {
                            "overall": _sc.get("overall"),
                            "resources": _sc.get("resources") or {},
                            "tasks": _sc.get("tasks") or {},
                            "platforms": _sc.get("platforms") or [],
                            "recent_errors_count": _sc.get("recent_errors_count", 0),
                            "incidents": _sc.get("incidents_detail") or [],
                        }
                        parts.append(
                            "自检数据 "
                            + json.dumps(_sc_data, ensure_ascii=False, separators=(",", ":"))
                        )
            except Exception:
                pass

            # 【时间对照】注入用户级时间感知
            if user_id and platform:
                try:
                    from memory.time_comparison import get_time_comparison_engine
                    from memory.time_tracker import get_time_tracker
                    from memory.pattern_learner import get_pattern_learner

                    tracker = get_time_tracker()
                    engine = get_time_comparison_engine()
                    learner = get_pattern_learner()
                    engine.set_tracker(tracker)
                    learner.set_tracker(tracker)
                    perception = engine.compare(user_id, platform)
                    if perception and perception.full_context:
                        raw_facts = perception.full_context
                        parts.append(f"\n[时间事实]\n{raw_facts}")
                    # 模式学习者
                    peak_desc = learner.get_peak_hours_description(user_id)
                    if peak_desc:
                        parts.append(peak_desc)
                    quiet_desc = learner.get_quiet_hours_description(user_id, datetime.now().hour)
                    if quiet_desc:
                        parts.append(quiet_desc)
                except Exception as e:
                    logger.debug(f"[时间感知] TimeComparison 失败: {e}")

            last_active = self._birth_data.get("last_active_at")
            if last_active:
                try:
                    gap = datetime.now() - datetime.fromisoformat(last_active)
                    if gap.total_seconds() > 60:
                        parts.append(f"上次活跃: {int(gap.total_seconds() // 60)} 分钟前")
                except Exception:
                    pass
            return " | ".join(parts)
        except Exception:
            return ""

    def _start_deferred_init(self):
        """后台线程初始化非关键子系统（安全、协作引擎、主动聊天）"""

        def _deferred():
            self._init_security()
            self._init_collaboration_engine()
            self._init_proactive_chat()
            self._deferred_init_event.set()

        threading.Thread(target=_deferred, daemon=True, name="Miya-Init-BG").start()

    def _init_security(self):
        """初始化安全服务（后台线程调用）"""
        try:
            from core.security_service import SecurityService

            self.security_service = SecurityService()
            logger.info("[决策层] 安全服务已初始化（技术性防注入）")
        except Exception as e:
            logger.warning(f"[决策层] 安全服务初始化失败: {e}")
            self.security_service = None

        # 10. AI注入检测器（角色扮演诱导检测）
        try:
            from core.ai_injection_detector import get_injection_detector

            self.ai_injection_detector = get_injection_detector()
            logger.info("[决策层] AI注入检测器已初始化（角色扮演诱导检测）")
        except Exception as e:
            logger.warning(f"[决策层] AI注入检测器初始化失败: {e}")
            self.ai_injection_detector = None

    def _init_proactive_chat(self):
        """初始化主动聊天系统 v2.0（后台线程调用）"""
        try:
            from core.proactive_chat import get_proactive_chat_system

            self.proactive_chat = get_proactive_chat_system()
            self.proactive_chat.set_ai_client(self.ai_client)
            self.proactive_chat.set_personality(self.personality)
            self.proactive_chat.set_prompt_manager(self.prompt_manager)

            try:
                from pathlib import Path

                import yaml
                from miya_senses.sensors.screen_aware import get_screen_aware

                cfg = {}
                cfg_path = Path(__file__).resolve().parent.parent / "config" / "screen_aware.yaml"
                if cfg_path.exists():
                    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                    cfg = raw.get("screen_aware", raw)

                sa = get_screen_aware(
                    enabled=cfg.get("enabled", True),
                    min_interval_seconds=cfg.get("min_interval_seconds", 30),
                    vision_mode=cfg.get("vision_mode", "on_demand"),
                    vision_cooldown_seconds=cfg.get("vision_cooldown_seconds", 300),
                    vision_daily_quota=cfg.get("vision_daily_quota", 24),
                    vision_trigger_light_count=cfg.get("vision_trigger_light_count", 10),
                    hash_similarity_threshold=cfg.get("hash_similarity_threshold", 8),
                    model_dir=cfg.get("model_dir", ""),
                    ocr_startup_grace_seconds=cfg.get("ocr_startup_grace_seconds", 120),
                )
                self.proactive_chat.set_screen_aware(sa)
                logger.info(
                    f"[决策层] Screen-Aware 已注入 "
                    f"(vision_mode={sa.vision_mode}, interval={cfg.get('min_interval_seconds', 30)}s)"
                )
            except Exception as e:
                logger.debug(f"[决策层] Screen-Aware 注入跳过: {e}")

            async def _rich_context_provider(target_id: int) -> str:
                """为主动聊天构建完整的记忆上下文"""
                try:
                    from datetime import datetime, timezone, timedelta
                    from memory.cognitive_engine import get_cognitive_engine

                    parts = []
                    target_str = str(target_id)
                    session_id = f"user_{target_str}"
                    now = datetime.now()

                    try:
                        ce = get_cognitive_engine()
                        cog_text = await ce.build_context(
                            user_input="最近的对话",
                            conversation_history=[],
                            limit=3,
                            user_id=target_str,
                        )
                        if cog_text:
                            parts.append(cog_text)
                    except Exception:
                        pass

                    try:
                        conv = await self.conversation_context_manager.get_conversation_context(
                            session_id, user_id=target_str, current_input=""
                        )
                        if conv:
                            cutoff = now - timedelta(hours=4)
                            recent = []
                            for msg in conv:
                                ts = msg.get("timestamp", "")
                                try:
                                    if ts:
                                        msg_time = datetime.fromisoformat(str(ts))
                                        if msg_time < cutoff:
                                            continue
                                except (ValueError, TypeError):
                                    pass
                                recent.append(msg)

                            if recent:
                                lines = []
                                for msg in recent[-8:]:
                                    role = msg.get("role", "user")
                                    content = str(msg.get("content", ""))[:80]
                                    name = "弥娅" if role == "assistant" else "用户"
                                    ts = msg.get("timestamp", "")
                                    time_label = ""
                                    try:
                                        if ts:
                                            msg_time = datetime.fromisoformat(str(ts))
                                            elapsed = (now - msg_time).total_seconds()
                                            if elapsed < 3600:
                                                time_label = f"[{int(elapsed // 60)}分钟前]"
                                            elif elapsed < 86400:
                                                time_label = f"[{msg_time.strftime('%H:%M')}]"
                                            else:
                                                time_label = f"[{msg_time.strftime('%m-%d %H:%M')}]"
                                    except (ValueError, TypeError):
                                        pass
                                    lines.append(f"{time_label} {name}: {content}")
                                if lines:
                                    parts.append("【近期对话】\n" + "\n".join(lines))
                            else:
                                parts.append("【近期对话】\n（最近4小时内无对话记录）")
                    except Exception:
                        pass

                    return "\n".join(parts) if parts else ""
                except Exception:
                    return ""

            self.proactive_chat.set_rich_context_provider(_rich_context_provider)

            async def _proactive_send_callback(
                message: str, target_id: int, chat_type: str, platform: str = "terminal", trigger_type: str = ""
            ):
                """主动聊天消息发送回调 — 委托到统一分发 (v8.1)"""
                if not message or not target_id:
                    return False
                if self.proactive_coordinator:
                    return await self.proactive_coordinator.submit_message(
                        message,
                        key=f"chat:{target_id}:{trigger_type or 'proactive_chat'}",
                        target_id=str(target_id),
                        chat_type=chat_type,
                        platform=platform,
                        trigger_type=trigger_type or "proactive_chat",
                    )
                await self._dispatch_proactive_message(
                    message=message,
                    target_id=target_id,
                    chat_type=chat_type,
                    platform=platform,
                    trigger_type=trigger_type,
                    store_memory=True,
                )
                return True

            self.proactive_chat.set_send_callback(_proactive_send_callback)

            # 所有后台主动来源共享一层总决策/总限频。主动聊天已经完成触发判断，
            # 这里由协调器继续执行跨来源冷却、去重和统一发送。
            try:
                from core.proactive_coordinator import get_proactive_coordinator

                self.proactive_coordinator = get_proactive_coordinator()
                owner_target_id = "default"
                try:
                    from memory.identity_resolver import get_identity_resolver

                    owner_target_id = get_identity_resolver().owner_canonical_id or "default"
                except Exception:
                    pass
                self.proactive_coordinator.configure(
                    ai_client=self.ai_client,
                    personality=self.personality,
                    send_callback=self._dispatch_proactive_message,
                    config=self.proactive_chat._config.get("coordination", {}),
                    default_target_id=owner_target_id,
                )
                logger.info("[决策层] 统一主动性协调器已接入")
            except Exception as exc:
                logger.warning(f"[决策层] 统一主动性协调器接入失败: {exc}")

            # 移动端主动消息缓存
            self._mobile_pending: Dict[str, List[Dict]] = {}

            # 【意图持续】注入工具调用能力
            if self.tool_subnet:
                self.proactive_chat.set_tool_registry(self.tool_subnet.get_tools_schema)

            def _proactive_tool_ctx(target_id: int) -> dict:
                ctx = self.proactive_chat._context_cache.get(target_id)
                platform = ctx.platform if ctx else "terminal"
                user_id = str(target_id)
                group_id = "0"
                if ctx and ctx.chat_type == "group":
                    group_id = str(target_id)
                    user_id = "0"
                return {
                    "platform": platform,
                    "user_id": user_id,
                    "group_id": group_id,
                    "message_type": ctx.chat_type if ctx else "private",
                    "onebot_client": self.onebot_client,
                    "send_like_callback": getattr(self.onebot_client, "send_like", None)
                    if self.onebot_client
                    else None,
                    "memory_engine": self.memory_engine,
                    "emotion": self.emotion,
                    "personality": self.personality,
                    "scheduler": self.scheduler,
                }

            self.proactive_chat.set_proactive_tool_context(_proactive_tool_ctx)

            logger.info("[决策层] 主动聊天系统 v2.0 已初始化（含意图持续机制）")
        except Exception as e:
            logger.warning(f"[决策层] 主动聊天系统初始化失败: {e}")
            self.proactive_chat = None

    async def _check_injection_technical(self, perception: dict, content: str) -> tuple[str | None, str | None]:
        """仅执行技术性注入检查（同步/快速），AI 检测移至并行阶段"""
        if self.security_service:
            try:
                platform = perception.get("source", "")
                if MiyaPlatform.requires_injection_check(platform):
                    user_id = str(perception.get("user_id", perception.get("user_id", "unknown")))
                    result = self.security_service.check(content, user_id)
                    if result.level.value in ["dangerous", "blocked"]:
                        logger.warning(f"[决策层-防注入] 技术性注入: level={result.level}, reason={result.reason}")
                        return get_text("security.ai_injection_detection.fallback_response"), None
            except Exception as e:
                logger.warning(f"[决策层-防注入] 技术检测失败: {e}")
        return None, None

    async def _check_injection(self, perception: dict, content: str) -> tuple[str | None, str | None]:
        """
        检查注入攻击

        Returns:
            (拦截消息, 防护提示) - 拦截消息非None时直接返回，防护提示非None时附加到AI请求
        """

        # 1. 先检查技术性注入
        if self.security_service:
            try:
                platform = perception.get("source", "")
                if MiyaPlatform.requires_injection_check(platform):
                    user_id = str(perception.get("user_id", perception.get("user_id", "unknown")))
                    result = self.security_service.check(content, user_id)
                    # 检查是否是危险级别
                    if result.level.value in ["dangerous", "blocked"]:
                        logger.warning(f"[决策层-防注入] 技术性注入: level={result.level}, reason={result.reason}")
                        return get_text("security.ai_injection_detection.fallback_response"), None
            except Exception as e:
                logger.warning(f"[决策层-防注入] 技术检测失败: {e}")

        # 2. 检查AI角色扮演诱导
        if self.ai_injection_detector:
            try:
                # 检查是否启用
                if not self.ai_injection_detector.is_enabled():
                    return None, None

                platform = perception.get("source", "")
                if MiyaPlatform.requires_injection_check(platform):
                    is_injection, reason = await self.ai_injection_detector.detect(content)
                    if is_injection:
                        logger.warning(f"[决策层-AI防注入] 检测到角色扮演诱导: {reason}")
                        # 根据配置决定是阻止还是使用防护提示
                        if self.ai_injection_detector.should_block():
                            return (
                                self.ai_injection_detector.get_fallback_response(),
                                None,
                            )
                        else:
                            # 软防护：允许回复但附加防护提示
                            protection_prompt = self.ai_injection_detector.get_protection_prompt()
                            return None, protection_prompt
            except Exception as e:
                logger.warning(f"[决策层-AI防注入] 检测失败: {e}")

        return None, None

    async def _check_ai_injection_parallel(self, content: str, platform: str) -> Optional[str]:
        """AI 注入检测 — 在并行阶段执行"""
        if not self.ai_injection_detector:
            return None
        try:
            if not self.ai_injection_detector.is_enabled():
                return None
            if not MiyaPlatform.requires_injection_check(platform):
                return None
            is_injection, reason = await asyncio.wait_for(self.ai_injection_detector.detect(content), timeout=3.0)
            if is_injection:
                logger.warning(f"[决策层-AI防注入] 并行检测到角色扮演诱导: {reason}")
                if self.ai_injection_detector.should_block():
                    return self.ai_injection_detector.get_fallback_response()
                else:
                    return self.ai_injection_detector.get_protection_prompt()
        except asyncio.TimeoutError:
            logger.debug("[决策层-AI防注入] 并行检测超时，跳过")
        except Exception as e:
            logger.warning(f"[决策层-AI防注入] 并行检测失败: {e}")
        return None

    async def _handle_proactive_chat(self, perception: dict, user_message: str, main_response: str = ""):
        """处理主动聊天"""
        if not self.proactive_chat:
            return None

        try:
            from core.proactive_chat import ChatContext, ProactiveResult

            user_id = perception.get("user_id", 0)
            group_id = perception.get("group_id", 0)
            group_name = perception.get("group_name", "")
            message_type = perception.get("message_type", "unknown")

            if not user_id:
                return None

            # 确定目标ID
            if message_type == "group" or (group_id and group_id != 0):
                target_id = group_id if group_id else 0
                chat_type = "group"
            else:
                target_id = user_id
                chat_type = "private"

            if target_id == 0:
                return None

            # 更新上下文
            platform = perception.get("platform", "terminal")
            context = ChatContext(
                chat_type=chat_type,
                target_id=target_id,
                group_name=group_name or None,
                member_count=perception.get("member_count", 0),
                platform=platform,
            )

            # 【谛听传递】将主回复管线的谛听分析注入主动聊天的 ChatContext
            msg_strategy = perception.get("_message_strategy")
            if msg_strategy:
                context.diting_intent = msg_strategy.get("intent")
                context.diting_style = msg_strategy.get("style")
                context.diting_confidence = msg_strategy.get("confidence", 0.0)

            # 【主回复传递】让主动聊天知道弥娅刚才说了什么，避免重复提问
            if main_response:
                context.last_miya_reply = main_response

            self.proactive_chat.update_context(target_id, context, platform)
            await self.proactive_chat.record_message(target_id, chat_type, user_message, platform)

            # 记录弥娅刚回复了，防止主动聊天紧跟正常回复重复发送
            if main_response:
                self.proactive_chat.record_miya_reply(target_id)

            # 【意图持续】检测主回复中的主动意图
            if main_response:
                await self.proactive_chat.detect_and_register_intent(
                    target_id, chat_type, platform, main_response, user_message
                )

            # 检查是否需要主动发言
            result: Optional[ProactiveResult] = await self.proactive_chat.check_and_respond(
                target_id=target_id, user_message=user_message
            )

            if result and result.should_respond and result.message:
                ctx_platform = result.context.platform if result.context else None
                platform = ctx_platform or perception.get("platform", "terminal")
                target_to_send = result.context.target_id if result.context else target_id

                # 委托统一分发 (v8.1)
                await self._dispatch_proactive_message(
                    message=result.message,
                    target_id=target_to_send,
                    chat_type=chat_type,
                    platform=platform,
                    trigger_type=result.trigger_type,
                    store_memory=True,
                )

                return result

            return None

        except Exception as e:
            logger.warning(f"[决策层] 主动聊天处理失败: {e}")
            return None

    async def _dispatch_proactive_message(
        self,
        message: str,
        target_id: int,
        chat_type: str = "private",
        platform: str = "terminal",
        trigger_type: str = "",
        store_memory: bool = True,
    ) -> bool:
        """主动消息跨平台分发 — 统一路由入口 (v8.1)

        分发优先级:
        1. 平台明确在线 → 直接发送
        2. QQ 系列 → OneBot 回退
        3. desktop/generic/webchat/mobile/terminal + trigger_type → AI 感知路由
        4. 无 trigger_type 的广播平台 → 广播到所有在线支持主动消息的平台
        5. mobile 或失败 → mobile_pending 兜底队列
        """
        sent = False

        # 1) 平台注册表直接发送 (v8.2: 启用跨平台 ID 翻译)
        if self.platform_registry and platform and platform != "terminal":
            inst = self.platform_registry.get(platform)
            if inst and hasattr(inst, "is_online") and inst.is_online:
                if chat_type == "group" and hasattr(inst, "send_group_message"):
                    logger.info(f"[主动分发] 发送群消息 (via {platform}): {message[:50]}")
                    sent = await inst.send_group_message(target_id, message)
                elif hasattr(inst, "send_private_message"):
                    resolved_id = self._resolve_cross_platform_target_id(str(target_id), platform)
                    logger.info(
                        f"[主动分发] 发送私聊消息 (via {platform}"
                        f"{', resolved_id=' + resolved_id if resolved_id != str(target_id) else ''})"
                        f": {message[:50]}"
                    )
                    sent = await inst.send_private_message(resolved_id, message)

        # 2) QQ 系列 → OneBot 回退 (仅 QQ 类平台)
        _qq_platforms = MiyaPlatform.qq_family()
        if not sent and self.onebot_client and platform in _qq_platforms:
            if chat_type == "group":
                sent = await self.onebot_client.send_group_message(target_id, message)
            else:
                sent = await self.onebot_client.send_private_message(target_id, message)

        # 3) 需要路由判断的平台 → AI 感知 / 优先级 / 广播
        # v9.0: mobile/desktop 跳过 AI 路由，直接走 WS 兜底
        _ws_direct_platforms = MiyaPlatform.ws_direct_platforms()
        if not sent and platform not in _ws_direct_platforms:
            routing_config = self._get_platform_routing_config()
            mode = routing_config.get("mode", "ai_aware")

            # 3a) 后台触发 + AI 感知模式 → AI 智能选择
            if trigger_type and mode == "ai_aware" and routing_config.get("ai_routing", {}).get("enabled", True):
                selected_platform = await self._ai_select_platform(
                    message=message,
                    target_id=target_id,
                    trigger_type=trigger_type,
                    routing_config=routing_config,
                )
                if selected_platform:
                    inst = self.platform_registry.get(selected_platform)
                    if inst and hasattr(inst, "is_online") and inst.is_online:
                        if hasattr(inst, "send_private_message"):
                            try:
                                resolved_id = self._resolve_cross_platform_target_id(str(target_id), selected_platform)
                                result = await inst.send_private_message(resolved_id, message)
                                if result:
                                    logger.info(
                                        f"[主动分发] AI 路由 → {selected_platform}"
                                        f"{' (id=' + resolved_id + ')' if resolved_id != str(target_id) else ''}"
                                        f": {message[:50]}"
                                    )
                                    sent = True
                            except Exception as e:
                                logger.debug(f"[主动分发] AI 路由发送失败: {e}")

            # 3b) AI 未命中或非 AI 模式 → 用户活跃度优先级路由 (v8.2)
            if not sent:
                sent = await self._send_by_priority(target_id, message, chat_type, routing_config)

        # 4) mobile/desktop 兜底 + WS 直推 (v9.0)
        if MiyaPlatform.is_ws_direct(platform) or not sent:
            if not sent:
                logger.info(f"[主动分发] 无法直接发送到 {platform}，使用 WS 兜底: {message[:50]}")

            _key = str(target_id)
            if _key not in self._mobile_pending:
                self._mobile_pending[_key] = []
            self._mobile_pending[_key].append(
                {
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            # v9.0: 同时写入 default 队列 (兼容手机端轮询 /api/chat/pending/default)
            if "default" not in self._mobile_pending:
                self._mobile_pending["default"] = []
            self._mobile_pending["default"].append(
                {
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            try:
                from core.management_api import get_management_api
                from core.platform_awareness import get_platform_awareness

                mgmt = get_management_api()
                if mgmt:
                    if platform == "mobile":
                        await mgmt.push_proactive_message(
                            user_id=_key,
                            message=message,
                            platform=platform,
                            target_client="mobile",
                        )
                    elif platform in ("desktop", "web"):
                        await mgmt.push_proactive_message(
                            user_id=_key,
                            message=message,
                            platform=platform,
                            target_client="desktop",
                        )

                awareness = get_platform_awareness()
                if platform == "mobile":
                    awareness.add_mobile_pending(_key, message)
                sent = True
            except Exception as e:
                logger.debug(f"[主动分发] WS 兜底失败: {e}")

        if not sent and platform != "mobile":
            if "default" not in self._mobile_pending:
                self._mobile_pending["default"] = []
            self._mobile_pending["default"].append(
                {
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        if not sent:
            logger.info(f"[主动分发] 无法发送到 {platform}: {message[:50]}")

        # 5) 记入记忆 + WS 广播到桌面前端
        if store_memory:
            try:
                perception = {
                    "platform": platform or "terminal",
                    "user_id": str(target_id),
                    "group_id": str(target_id) if chat_type == "group" else "0",
                    "message_type": chat_type,
                    "response": message,
                }
                await self.memory_manager.store_unified_memory(perception, role="assistant")
                # WS 广播——让桌面前端实时显示主动聊天内容
                try:
                    from core.management_api import get_management_api

                    mgmt = get_management_api()
                    if mgmt:
                        await mgmt.broadcast_message(
                            content=message[:2000],
                            platform=platform,
                            sender_name="弥娅",
                            sender_id="miya",
                            user_id=str(target_id),
                            direction="out",
                            message_id="",
                            group_id=str(target_id) if chat_type == "group" else None,
                        )
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"[主动分发] 记忆存储失败: {e}")

        return sent

    def _get_platform_routing_config(self) -> dict:
        """获取平台路由配置 (从 proactive_chat._config 读取) (v8.1)"""
        try:
            if hasattr(self, "proactive_chat") and self.proactive_chat:
                return self.proactive_chat._config.get("platform_routing", {})
        except Exception:
            pass
        return {}

    def _resolve_cross_platform_target_id(self, target_id: str, target_platform: str) -> str:
        """跨平台用户 ID 翻译 (v9.0: 优先 PlatformAwareness)

        从 PlatformAwareness / permissions.json 读取 linked_to 映射 + superadmin 配置:
          - desktop_user 的 linked_to 是 "1523878699" → QQ 平台用 "1523878699"
          - canonical QQ ID → 其它平台时，从 superadmin.ids 反向查平台特定 ID
          - 如果 target_id 本身就是该平台的合法 ID，直接返回

        返回: 适合 target_platform 的用户 ID
        """
        if not target_id:
            return target_id

        # v9.0: 优先从 PlatformAwareness 查询跨平台 ID 映射
        try:
            from core.platform_awareness import get_platform_awareness

            awareness = get_platform_awareness()
            resolved = awareness.resolve_platform_id(target_id, target_platform)
            if resolved and resolved != target_id:
                logger.debug(f"[跨平台] PlatformAwareness: {target_id}@{target_platform} → {resolved}")
                return resolved
        except Exception:
            pass

        # QQ 系列平台的已知 ID 模式
        _qq_platforms = MiyaPlatform.qq_family()
        _is_qq_target = target_platform in _qq_platforms

        # QQ 纯数字 ID：OneBot/NapCat 可用 QQ 号，qqofficial 需要 openid
        if _is_qq_target and target_id.isdigit():
            if target_platform == "qqofficial":
                openid = self._find_qqofficial_openid(target_id)
                if openid:
                    logger.info(f"[跨平台] qqofficial QQ号 {target_id} → openid {openid}")
                    return openid
            return target_id

        try:
            import json
            from pathlib import Path

            perms_path = Path("config/permissions.json")
            if perms_path.exists():
                perms = json.loads(perms_path.read_text(encoding="utf-8"))
                users = perms.get("users", [])

                # 1) 目标 ID 直接匹配 → 检查该用户的 linked_to
                for u in users:
                    if u.get("user_id") == target_id:
                        linked = u.get("linked_to", "")
                        if linked and str(linked).isdigit():
                            logger.debug(f"[跨平台] {target_id} → {linked} (exact linked_to)")
                            return str(linked)
                        if _is_qq_target and not target_id.isdigit():
                            break

                # 4) v8.2: superadmin 反向查找 — canonical QQ ID → 目标平台的特定 ID
                # (必须在 step 2 之前，否则 desktop_user.linked_to 会截胡)
                if not _is_qq_target and target_id.isdigit():
                    superadmins = perms.get("superadmins", {})
                    for _sa_name, sa_info in superadmins.items():
                        ids_by_platform = sa_info.get("ids", {})
                        for src_platform, id_list in ids_by_platform.items():
                            if target_id in [str(i) for i in id_list]:
                                target_ids = ids_by_platform.get(target_platform, [])
                                if target_ids and target_ids[0]:
                                    resolved = str(target_ids[0])
                                    logger.info(
                                        f"[跨平台] canonical {target_id} → "
                                        f"{target_platform} ID {resolved} (from superadmin config)"
                                    )
                                    return resolved

                # 2) 反向：search linked_to == target_id → 该 ID 本身已经是 QQ 号
                for u in users:
                    if str(u.get("linked_to", "")) == str(target_id):
                        logger.debug(f"[跨平台] {target_id} 是 linked_to，找到用户 {u.get('user_id')}")
                        return target_id

                # 3) QQ 兜底：target_id 不是纯数字 QQ 号 → 搜索有 linked_to 的用户
                if _is_qq_target and not target_id.isdigit():
                    for u in users:
                        linked = str(u.get("linked_to", ""))
                        if linked and linked.isdigit():
                            logger.debug(f"[跨平台] {target_id} → QQ 兜底 {linked} (from user {u.get('user_id')})")
                            return linked
                    for u in users:
                        uid = str(u.get("user_id", ""))
                        if u.get("platform") in _qq_platforms and uid.isdigit():
                            logger.debug(f"[跨平台] {target_id} → QQ 平台用户 {uid}")
                            return uid

        except Exception as e:
            logger.debug(f"[跨平台] 用户 ID 翻译失败: {e}")

        return target_id

    @staticmethod
    def _find_qqofficial_openid(qq_number: str) -> str:
        """从 superadmin 配置中查找 QQ 号对应的 qqofficial openid (v8.2)

        QQ 官方 Bot API 的 post_c2c_message 需要 openid (hex 字符串)，
        不能直接使用 QQ 号。从 permissions.json 的 superadmin 配置中查找映射。
        """
        try:
            import json
            from pathlib import Path

            perms_path = Path("config/permissions.json")
            if not perms_path.exists():
                return ""
            perms = json.loads(perms_path.read_text(encoding="utf-8"))
            superadmins = perms.get("superadmins", {})
            for _sa_name, sa_info in superadmins.items():
                ids_by_platform = sa_info.get("ids", {})
                qqofficial_ids = ids_by_platform.get("qqofficial", [])
                if qq_number in [str(i) for i in qqofficial_ids]:
                    for qid in qqofficial_ids:
                        sid = str(qid)
                        if not sid.isdigit() and len(sid) >= 10:
                            return sid
                    if qqofficial_ids:
                        return str(qqofficial_ids[-1])
        except Exception:
            pass
        return ""

    def _get_platform_activity(self, target_id: int) -> dict:
        """获取用户在任平台上的最近活跃时间 (v8.2: 用户级数据优先)

        查询来源: user_platform_activity 模块 (用户×平台二维矩阵) → 平台全局健康数据 (兜底)
        返回: { platform_id: seconds_ago (float) }
        """
        import time

        result = {}
        now = time.time()

        # v8.2: 优先读取用户级跨平台活跃度
        try:
            from memory.user_platform_activity import get_all_user_platform_activity

            user_activity = get_all_user_platform_activity(str(target_id), now=now)
            for pid, activity in user_activity.items():
                seconds_ago = activity.get("seconds_ago", float("inf"))
                if seconds_ago != float("inf"):
                    result[pid] = round(seconds_ago, 1)
        except Exception:
            pass

        # 兜底：平台全局健康数据 (补充用户级未覆盖的平台)
        if self.platform_registry:
            for pid, inst in self.platform_registry._instances.items():
                if pid not in result and inst and inst.is_online:
                    try:
                        health = getattr(inst, "_health", None)
                        if health and health.last_message_received:
                            delta = now - health.last_message_received.timestamp()
                            result[pid] = round(delta, 1)
                    except Exception:
                        pass

        return result

    async def _ai_select_platform(
        self,
        message: str,
        target_id: int,
        trigger_type: str,
        routing_config: dict,
    ) -> Optional[str]:
        """AI 感知平台选择 — 让 AI 从候选平台中挑选最佳发送目标 (v8.2)

        根据: 消息内容 + 触发场景 + 用户活跃度 + 平台优先级
        返回: 平台 ID 或 None (AI 失败时降级)
        """
        if not self.ai_client:
            logger.warning("[AI路由] AI 客户端未初始化，跳过平台选择")
            return None
        if not self.platform_registry:
            logger.warning("[AI路由] 平台注册表未就绪，跳过平台选择")
            return None

        ai_cfg = routing_config.get("ai_routing", {})
        timeout_seconds = ai_cfg.get("timeout_seconds", 3)

        try:
            # 收集在线平台及其优先级
            priority_map = routing_config.get("priority_ranking", {})
            candidates = []

            for pid in self.platform_registry.list_active() or []:
                inst = self.platform_registry.get(pid)
                if inst and hasattr(inst, "is_online") and inst.is_online:
                    if hasattr(inst, "send_private_message"):
                        priority = priority_map.get(pid, priority_map.get(f"{pid}_private", 5))
                        candidates.append((pid, priority))

            if not candidates:
                logger.warning("[AI路由] 无可用候选平台（无在线且支持 send_private_message 的平台）")
                return None

            # 按优先级排序，取 top-N
            candidates.sort(key=lambda x: x[1], reverse=True)
            max_cand = ai_cfg.get("max_candidates", 5)
            candidates = candidates[:max_cand]

            # 获取各平台用户活跃度
            activity = self._get_platform_activity(target_id)

            # 构建 AI prompt
            now_str = datetime.now().strftime("%H:%M")

            # 从配置读取文本模板
            activity_fmts = {
                "seconds": get_text("platform_routing.activity_format.seconds", ""),
                "minutes": get_text("platform_routing.activity_format.minutes", ""),
                "hours": get_text("platform_routing.activity_format.hours", ""),
                "inactive": get_text("platform_routing.activity_format.inactive", ""),
            }
            cand_line_fmt = get_text("platform_routing.candidate_line_format", "")

            cand_lines = []
            for pid, priority in candidates:
                secs_ago = activity.get(pid)
                active_str = ""
                if secs_ago is not None:
                    if secs_ago < 60:
                        active_str = activity_fmts["seconds"].format(seconds=int(secs_ago))
                    elif secs_ago < 3600:
                        active_str = activity_fmts["minutes"].format(minutes=int(secs_ago / 60))
                    else:
                        active_str = activity_fmts["hours"].format(hours=round(secs_ago / 3600, 1))
                else:
                    active_str = activity_fmts["inactive"]
                if cand_line_fmt:
                    cand_lines.append(cand_line_fmt.format(platform_id=pid, priority=priority, activity=active_str))
                else:
                    cand_lines.append(f"- {pid} (优先级{priority}){active_str}")

            trigger_desc = get_text(f"platform_routing.trigger_descriptions.{trigger_type}", trigger_type)

            # v8.2: 从配置读取 most_active_hint 模板
            most_active_hint = ""
            hint_threshold = routing_config.get("activity_boost", {}).get("most_active_hint_threshold", 300)
            if activity:
                best_pid = min(activity, key=lambda k: activity.get(k, float("inf")))
                best_secs = activity.get(best_pid, float("inf"))
                if best_secs != float("inf") and best_secs < hint_threshold:
                    hint_template = get_text("platform_routing.most_active_hint", "")
                    if hint_template:
                        most_active_hint = hint_template.format(platform_id=best_pid, seconds_ago=int(best_secs))

            prompt_template = get_text("platform_routing.ai_prompt_template", "")
            prompt = prompt_template.format(
                message=message[:200],
                trigger_desc=trigger_desc,
                now_str=now_str,
                most_active_hint=most_active_hint,
                candidates=chr(10).join(cand_lines),
            )

            response = await asyncio.wait_for(
                self.ai_client.chat(
                    messages=[AIMessage(role="user", content=prompt)],
                    use_miya_prompt=False,
                ),
                timeout=timeout_seconds,
            )

            if response:
                selected = response.strip().lower()
                valid_ids = {c[0] for c in candidates}
                if selected in valid_ids:
                    logger.info(f"[AI路由] {trigger_type} → {selected}: {message[:50]}")
                    return selected
                for pid in valid_ids:
                    if pid.startswith(selected) or selected.startswith(pid):
                        logger.info(f"[AI路由] {trigger_type} → {pid} (fuzzy: {selected}): {message[:50]}")
                        return pid

            if response:
                logger.warning(f"[AI路由] AI 返回无效平台: '{selected}', 候选: {valid_ids}")
            else:
                logger.warning("[AI路由] AI 返回空响应，降级到优先级路由")

        except asyncio.TimeoutError:
            logger.warning(f"[AI路由] AI 判断超时 ({timeout_seconds}s)，降级到优先级排序")
        except Exception as e:
            logger.warning(f"[AI路由] AI 判断失败: {e}，降级到优先级排序")

        return None

    async def _send_by_priority(
        self,
        target_id: int,
        message: str,
        chat_type: str,
        routing_config: dict,
    ) -> bool:
        """按用户活跃度 + 配置优先级排序发送消息 (v9.0: 当前活跃平台优先)

        用户当前活跃的平台获得最高优先权，确保主动消息发到用户正在用的平台。
        """
        if not self.platform_registry:
            return False

        import time as _time

        now = _time.time()
        priority_map = routing_config.get("priority_ranking", {})
        active = self.platform_registry.list_active() or []

        user_activity = {}
        try:
            from memory.user_platform_activity import get_all_user_platform_activity

            user_activity = get_all_user_platform_activity(str(target_id), now=now)
        except Exception:
            pass

        current_platform = ""
        try:
            from core.platform_awareness import get_platform_awareness

            awareness = get_platform_awareness()
            current_platform = awareness.get_current_platform(str(target_id))
        except Exception:
            pass

        scored = []
        for pid in active:
            inst = self.platform_registry.get(pid)
            if inst and hasattr(inst, "is_online") and inst.is_online:
                if hasattr(inst, "send_private_message"):
                    base_score = priority_map.get(pid, priority_map.get(f"{pid}_private", 5))

                    activity = user_activity.get(pid, {})
                    seconds_ago = activity.get("seconds_ago", float("inf"))
                    activity_boost = 0
                    boost_thresholds = routing_config.get("activity_boost", {}).get("thresholds", [])
                    if boost_thresholds:
                        for threshold in boost_thresholds:
                            if seconds_ago < threshold.get("seconds", 0):
                                activity_boost = max(activity_boost, threshold.get("boost", 0))
                    else:
                        if seconds_ago < 60:
                            activity_boost = 80
                        elif seconds_ago < 300:
                            activity_boost = 60
                        elif seconds_ago < 600:
                            activity_boost = 40
                        elif seconds_ago < 1800:
                            activity_boost = 20
                        elif seconds_ago < 3600:
                            activity_boost = 10

                    current_boost = 9999 if (current_platform and pid == current_platform) else 0
                    adjusted_score = base_score + activity_boost + current_boost
                    scored.append((adjusted_score, base_score, activity_boost, current_boost, pid))

        scored.sort(key=lambda x: x[0], reverse=True)

        for adj_score, base_score, boost, cur_boost, pid in scored:
            inst = self.platform_registry.get(pid)
            try:
                resolved_id = self._resolve_cross_platform_target_id(str(target_id), pid)
                success = await inst.send_private_message(resolved_id, message)
                if success:
                    boost_hint = ""
                    if cur_boost > 0:
                        boost_hint = f" (当前活跃平台)"
                    elif boost > 0:
                        boost_hint = f" (boost={boost})"
                    logger.info(
                        f"[主动分发] 优先级路由 → {pid}"
                        f"{' (id=' + resolved_id + ')' if resolved_id != str(target_id) else ''}"
                        f": {message[:50]}{boost_hint}"
                    )
                    return True
            except Exception:
                pass

        return False

    async def start_proactive_background(self):
        """启动主动聊天后台轮询"""
        if self.proactive_chat and self.proactive_chat.is_enabled():
            await self.proactive_chat.start_background_loop()
        else:
            logger.info("[决策层] 主动聊天系统未启用，跳过后台轮询")

    async def _handle_smart_emoji(self, response: str, perception: dict):
        """智能表情包发送 - 根据回复内容自动选择表情包

        通过 OneBot upload_image API 上传后发送，确保 Windows 路径兼容。
        """
        try:
            from utils.emoji_manager import get_smart_emoji_manager

            emoji_manager = get_smart_emoji_manager()
            if not emoji_manager:
                return

            emoji_info = emoji_manager.get_emoji_by_context(response)
            if not emoji_info:
                return

            user_id = perception.get("user_id", 0)
            group_id = perception.get("group_id", 0)
            message_type = perception.get("message_type", "unknown")

            emoji_path = emoji_info.get("path", "")
            if not emoji_path or not Path(emoji_path).exists():
                return

            if message_type == "group" and group_id:
                if self.onebot_client:
                    result = await self.onebot_client.send_group_image(group_id, emoji_path)
                    if result and result.get("status") == "ok":
                        logger.info(f"[决策层] [智能表情包] 发送到群 {group_id}")
            elif user_id and self.onebot_client:
                result = await self.onebot_client.send_private_image(user_id, emoji_path)
                if result and result.get("status") == "ok":
                    logger.info(f"[决策层] [智能表情包] 发送到用户 {user_id}")

        except Exception as e:
            logger.warning(f"[决策层] 智能表情包发送失败: {e}")

    def _extract_keywords_from_input(self, text: str) -> List[str]:
        """从用户输入中提取关键词用于知识图谱检索"""
        import re

        # 简单的关键词提取：长度>=2的中文词
        keywords = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
        # 去重并返回前5个
        return list(set(keywords))[:5]

    def set_response_callback(self, callback: Callable) -> None:
        """
        设置响应回调函数

        Args:
            callback: 回调函数，签名: callback(qq_message, response_text) -> None
        """
        self.response_callback = callback

    def _init_session_manager(self) -> Optional[SessionManager]:
        """
        初始化统一会话管理器

        Returns:
            SessionManager 实例
        """
        try:
            # 总是重新初始化，确保有完整的组件引用
            sm = init_session_manager()
            logger.info("[决策层] 会话管理器初始化完成")
            return sm

        except Exception as e:
            logger.warning(f"[决策层] 会话管理器初始化失败: {e}")
            return None

    def _init_soul_generator(self) -> None:
        """
        初始化灵魂发生器 (Soul Generator)

        弥娅的"灵魂"系统，让弥娅拥有类似人类的情绪、认知和行为模式
        """
        try:
            from core.soul_generator import init_soul_generator

            self._soul_generator = init_soul_generator()
            logger.info("[灵魂] 🎭 灵魂发生器已初始化")
        except Exception as e:
            logger.warning(f"[灵魂] 初始化跳过: {e}")
            self._soul_generator = None

    def _init_auth_subnet(self) -> None:
        """
        初始化鉴权子网（AuthNet）

        AuthNet职责：
        - 统一用户身份管理（跨平台）
        - 权限检查与验证
        - 会话管理
        - API访问控制
        """
        try:
            from webnet.AuthNet import AuthSubnet

            self.auth_subnet = AuthSubnet()
            logger.info("[决策层] 鉴权子网初始化成功（支持跨平台权限管理）")
            logger.info("[决策层] 权限检查将在消息处理前自动执行")

        except Exception as e:
            logger.warning(f"[决策层] 鉴权子网初始化失败: {e}")
            self.auth_subnet = None

    def _init_collaboration_engine(self) -> None:
        """
        初始化模型协作引擎
        """
        logger.info(f"[决策层] 协作引擎初始化检查: model_pool={self.model_pool is not None}")
        try:
            if self.model_pool:
                from core.model_collaboration_engine import ModelCollaborationEngine

                config = getattr(self.model_pool, "_config", {})
                logger.info(
                    f"[决策层] 协作引擎配置: keys={list(config.keys())[:10]}, "
                    f"has_collaboration={'collaboration' in config}"
                )
                self.collaboration_engine = ModelCollaborationEngine(
                    model_pool=self.model_pool,
                    config=config,
                    personality=self.personality,
                    soul_generator=self._soul_generator,
                )
                logger.info(
                    f"[决策层] 模型协作引擎初始化成功 | "
                    f"enabled={self.collaboration_engine.enabled} | "
                    f"thresholds: single<={self.collaboration_engine.threshold_single}, "
                    f"chain<={self.collaboration_engine.threshold_chain}"
                )
            else:
                self.collaboration_engine = None
                logger.info("[决策层] ModelPool 不可用，协作引擎未初始化")

        except Exception as e:
            import traceback

            logger.warning(f"[决策层] 模型协作引擎初始化失败: {e}\n{traceback.format_exc()}")
            self.collaboration_engine = None

    def _get_advanced_orchestrator(self) -> Optional[Any]:
        """
        获取高级编排器（懒加载）

        功能：
        - 任务规划：将复杂任务分解为可执行的子任务
        - 自主探索：主动探索文件系统和代码库
        - 智能执行：可靠地执行任务，支持重试和回滚
        - 思维链：结构化的多步骤推理

        Returns:
            高级编排器实例，如果初始化失败则返回 None
        """
        if self._advanced_orchestrator_initialized:
            return self._advanced_orchestrator

        try:
            from core.advanced_orchestrator import AdvancedOrchestrator
            from core.tool_adapter import get_tool_adapter

            # 创建工具执行器包装器
            def _tool_executor_wrapper(tool_name: str, params: dict) -> str:
                """工具执行器包装器"""
                adapter = get_tool_adapter()

                async def _execute():
                    return await adapter.execute_tool(tool_name, params, self.tool_context or {})

                return asyncio.run(_execute())

            project_root = Path(__file__).parent.parent
            storage_dir = project_root / "data" / "advanced_tasks"
            storage_dir.mkdir(parents=True, exist_ok=True)

            self._advanced_orchestrator = AdvancedOrchestrator(
                ai_client=self.ai_client,
                tool_executor=_tool_executor_wrapper,
                storage_dir=str(storage_dir),
            )
            self._advanced_orchestrator_initialized = True

            logger.info("[决策层] 高级编排器初始化成功（任务规划、自主探索、智能执行、思维链）")

            return self._advanced_orchestrator

        except Exception as e:
            logger.warning(f"[决策层] 高级编排器初始化失败: {e}")
            self._advanced_orchestrator_initialized = True  # 标记为已尝试初始化
            return None

    async def process_perception(self, message: Message) -> Optional[str]:
        """
        处理来自 QQNet 的感知数据

        委托给感知处理器和响应生成器

        Args:
            message: M-Link 消息（包含感知数据）

        Returns:
            响应文本
        """
        return await self.process_perception_cross_platform(message)

    async def process_perception_cross_platform(self, message: Message) -> Optional[str]:
        """
        处理跨平台感知数据（统一入口）

        委托给感知处理器和响应生成器

        Args:
            message: M-Link 消息（包含感知数据）

        Returns:
            响应文本
        """
        perception = message.content

        # v8.2: 为桌面/移动端注入 AppPlatformBridge 适配器
        platform = perception.get("platform", "")
        if MiyaPlatform.is_local_platform(platform):
            try:
                from core.platform_context import (
                    AppPlatformBridge,
                    get_current_platform_adapter,
                    set_current_platform_adapter,
                )

                if not get_current_platform_adapter():
                    set_current_platform_adapter(AppPlatformBridge(platform))
            except Exception:
                pass

        # 提取感知信息 - 处理图片等非文本消息
        raw_content = perception.get("content", perception.get("input", ""))
        # 如果是list（图片消息等），转换为字符串
        if isinstance(raw_content, list):
            content = ""
            for item in raw_content:
                if isinstance(item, dict):
                    if item.get("type") == "image":
                        content = "[图片]"
                    elif item.get("type") == "text":
                        content = item.get("data", {}).get("text", "")
                        break
        else:
            content = raw_content
        sender_name = perception.get("sender_name", "用户")
        message_type = perception.get("message_type", "")
        # 兼容多种来源：source字段或platform字段
        platform = perception.get("source", perception.get("platform", "qq"))

        logger.info(f"[决策层] 收到感知数据: {sender_name} - {content[:50]}")

        # v9.0: 记录到统一平台感知中心
        try:
            from core.platform_awareness import get_platform_awareness

            raw_uid = perception.get("user_id", perception.get("sender_id", ""))
            if raw_uid:
                get_platform_awareness().record_activity(str(raw_uid), platform)
        except Exception:
            pass

        # 【统一消息存储】记录入站消息（fire-and-forget）
        async def _record_inbound():
            try:
                from core.unified_message_store import get_unified_message_store

                store = get_unified_message_store()
                await store.initialize()
                await store.record_message(
                    platform_id=platform,
                    user_id=str(user_id) if user_id else "unknown",
                    sender_id=str(perception.get("sender_id", "")),
                    sender_name=sender_name,
                    content={"text": content[:2000]},
                    direction="in",
                    message_id=perception.get("message_id", ""),
                    group_id=str(group_id) if group_id else None,
                    text=content[:2000],
                )
                from core.management_api import get_management_api

                mgmt = get_management_api()
                if mgmt:
                    await mgmt.broadcast_message(
                        content=content[:2000],
                        platform=platform,
                        sender_name=sender_name,
                        sender_id=str(perception.get("sender_id", "")),
                        user_id=str(user_id) if user_id else "unknown",
                        direction="in",
                        message_id=perception.get("message_id", ""),
                        group_id=str(group_id) if group_id else None,
                    )
            except Exception as e:
                logger.debug(f"[MessageStore] 入站记录失败: {e}")

        asyncio.create_task(_record_inbound(), name="record_inbound")

        # 【过滤】跳过内部处理标志消息，防止循环处理
        if content.startswith("[表情包请求已处理]"):
            logger.info("[决策层] 跳过内部标志消息 (emoji request processed)")
            return content.replace("[表情包请求已处理] ", "")

        # 【谛听】第一时间记录所有群消息（在任何拦截之前）
        group_id = perception.get("group_id", 0)
        is_at_bot = perception.get("is_at_bot", False)
        reply_to_bot = perception.get("reply_to_bot", False)
        user_id = perception.get("user_id", perception.get("sender_id", 0))
        group_name = perception.get("group_name", "")

        # 标记弥娅正在处理消息，防止主动聊天在后处理中插入干扰
        target_id = group_id if group_id and group_id != 0 else user_id
        if target_id and self.proactive_chat:
            self.proactive_chat.record_miya_reply(target_id)
            # 【意图持续】用户新消息清除之前的 pending intent
            self.proactive_chat.clear_intent(target_id)

        try:
            if group_id and group_id != 0:
                from memory.diteng_listener import get_diting

                diteng = get_diting()
                diteng.on_group_message(
                    group_id=str(group_id),
                    group_name=group_name,
                    user_id=str(user_id),
                    user_name=sender_name,
                    content=content,
                    is_at_bot=is_at_bot,
                    reply_to_bot=reply_to_bot,
                )
                logger.info(
                    f"[谛听] 记录: group={group_id}({group_name}), user={sender_name}, "
                    f"at_bot={is_at_bot}, reply_bot={reply_to_bot}"
                )
        except Exception as e:
            logger.warning(f"[谛听] 记录失败: {e}")

        # 【新增】更新用户/群聊侧写（从消息中学习用户特征）

        if MiyaPlatform.is_qq(platform) and user_id:
            try:
                from core.user_persona import get_user_persona_manager

                persona_manager = get_user_persona_manager()
                persona_manager.update_from_message(
                    user_id=str(user_id),
                    user_name=sender_name,
                    group_id=str(group_id) if group_id else None,
                    group_name=group_name,
                    message=content,
                )
                logger.debug(f"[决策层] 用户侧写已更新: user_id={user_id}, group_id={group_id}")
            except Exception as e:
                logger.debug(f"[决策层] 用户侧写更新失败: {e}")

        # 【新增】在最开始拦截快捷命令
        logger.debug(
            f"[决策层] ========== 命令检测 START ========== content={content[:30]}, personality={type(self.personality) if self.personality else None}"
        )

        # DEBUG: Check where we are in the code
        logger.debug("[决策层-DEBUG] 1. 命令检测后，检查位置")

        # 检查是否是图片消息并返回分析结果
        has_image = perception.get("has_image", False)
        image_analysis = perception.get("image_analysis")

        if has_image and image_analysis and image_analysis.get("success"):
            logger.info(f"[决策层] 检测到图片消息，分析结果: {image_analysis.get('description', '')[:50]}")
            # 将图片分析结果添加到上下文中
            perception["_image_analysis"] = image_analysis

            # 【新增】将图片分析结果保存到长期记忆（数据库持久化）
            try:
                from memory import store_important

                img_desc = image_analysis.get("description", "")[:500]
                img_labels = ", ".join(image_analysis.get("labels", [])[:10])
                img_model = image_analysis.get("model", "")
                # 存到长期记忆系统（和普通记忆一样持久化到数据库）
                memory_id = await store_important(
                    content=f"[图片分析] {img_desc}",
                    user_id=str(user_id) if user_id else "unknown",
                    tags=["image_analysis", "media", "图片识别"],
                    priority=0.6,
                    metadata={
                        "labels": img_labels,
                        "model": img_model,
                        "message_type": message_type,
                    },
                )
                logger.info(f"[决策层] 图片分析结果已保存到长期记忆: {memory_id}")
            except Exception as e:
                logger.warning(f"[决策层] 保存图片到长期记忆失败: {e}")

            # 【新增】保存图片分析结果到工作内存（短期记忆）
            try:
                from memory.working_memory import get_working_memory

                wm = get_working_memory()
                group_id_str = str(group_id) if (group_id is not None and group_id != 0) else "private"
                img_desc = image_analysis.get("description", "")[:300]
                img_labels = ", ".join(image_analysis.get("labels", [])[:5])
                wm.add_media_analysis(
                    group_id_str,
                    "image",
                    img_desc,
                    img_labels,
                    image_analysis.get("model", ""),
                )
                logger.info("[决策层] 图片分析结果已保存到工作内存")
            except Exception as e:
                logger.debug(f"[决策层] 保存图片到工作内存失败: {e}")

        # 【新增】检测引用消息包含图片，提前保存占位记录
        if not has_image:
            reply_info = perception.get("reply")
            content_check = str(perception.get("raw_message", []))
            has_reply_image = reply_info and ("image" in str(reply_info).lower() or "引用消息包含图片" in content_check)
            if has_reply_image:
                group_id_str = str(group_id) if (group_id is not None and group_id != 0) else "private"
                try:
                    wm = get_working_memory()
                    wm.add_media_analysis(
                        group_id_str,
                        "image",
                        "[图片待分析]",
                        "",
                        "pending",
                    )
                    logger.info("[决策层] 引用图片预保存记录")
                except Exception as e:
                    logger.debug(f"[决策层] 引用图片预保存失败: {e}")

        # 【新增】检查是否是用户确认/纠正图片识别结果（独立于图片消息）
        # 用户可能发送"是的，这是xxx"或"不是，是yyy"来确认/纠正之前的图片识别
        try:
            await self._check_and_learn_image_correction(perception, content, user_id, group_id)
        except Exception as e:
            logger.debug(f"[决策层] 检查图片学习失败: {e}")

        # 【群聊命令守卫】群聊中未@且无触发关键词的消息不允许执行任何命令（快捷词/斜杠命令）
        # 超管豁免：主人自己在群里发命令无需@
        group_command_allowed = True
        if group_id and group_id != 0 and not is_at_bot:
            is_owner = bool(perception.get("is_owner", False))
            if not is_owner:
                # 部分管线不传 is_owner 字段，回退查询权限引擎
                try:
                    from core.unified_permission import get_permission_engine

                    sender_id = str(perception.get("user_id") or perception.get("sender_id") or "")
                    plat = perception.get("platform", perception.get("source", ""))
                    is_owner = get_permission_engine().is_superadmin(sender_id, platform=plat)
                except Exception:
                    pass
            if not is_owner:
                from core.text_loader import get_chatbot_keywords

                content_lower_guard = content.lower()
                if not any(kw.lower() in content_lower_guard for kw in get_chatbot_keywords()):
                    group_command_allowed = False
                    logger.info(f"[决策层] 群聊命令守卫拦截: {content[:30]} (未@且无触发关键词)")

        quick_response = None
        if group_command_allowed:
            quick_response = await self._handle_quick_commands(content, platform, perception)
        if quick_response:
            logger.info(f"[决策层] 快捷命令拦截成功: {content[:20]} -> {quick_response[:50]}")
            return quick_response

        # 【安全检查】防注入检测（技术性检查同步，AI 检测移至并行阶段）
        injection_result, protection_prompt = await self._check_injection_technical(perception, content)
        if injection_result:
            logger.warning(f"[决策层] 检测到注入攻击: {injection_result}")
            return injection_result

        # 如果有防护提示，附加到perception中传递给AI
        if protection_prompt:
            perception["_protection_prompt"] = protection_prompt
            logger.info("[决策层] 已添加防护提示到AI请求")

        # AI 角色扮演诱导检测移至并行阶段，标记待检查
        perception["_pending_ai_injection_check"] = True

        # 【新增】群聊关键词触发检测（不@也能回复）
        group_id = perception.get("group_id", 0)
        is_at_bot = perception.get("is_at_bot", False)
        reply_to_bot = perception.get("reply_to_bot", False)

        logger.info(f"[谛听] 检查群聊: group_id={group_id}, is_at_bot={is_at_bot}, reply_to_bot={reply_to_bot}")

        # 群聊关键词列表：叫弥娅名字/亲昵称呼时触发回复 - 从配置获取
        from core.text_loader import get_chatbot_keywords

        auto_respond_keywords = get_chatbot_keywords()

        # 如果是群聊且没有@bot，检查是否包含关键词 或 用户仍在活跃对话中
        if group_id and group_id != 0 and not is_at_bot:
            content_lower = content.lower()
            matched_keywords = [kw for kw in auto_respond_keywords if kw.lower() in content_lower]

            # 检查用户是否仍在与机器人活跃对话
            from memory.diteng_listener import get_diting

            diteng = get_diting()
            user_id_str = str(perception.get("user_id", 0))
            user_active = diteng.is_user_active_with_bot(str(group_id), user_id_str)

            logger.warning(
                f"[谛听] 关键词检查: group={group_id}, user={user_id_str}, "
                f"matched={matched_keywords}, active={user_active}"
            )

            # 读取"仅关键词触发"开关
            keyword_only = False
            try:
                import re

                qq_cfg_path = Path(__file__).resolve().parent.parent / "config" / "qq_config.yaml"
                if qq_cfg_path.exists():
                    raw_text = qq_cfg_path.read_text(encoding="utf-8")
                    for line in raw_text.splitlines():
                        m = re.match(r"\s*passive_chat_keyword_only\s*:\s*(true|false)", line)
                        if m:
                            keyword_only = m.group(1).lower() == "true"
                            break
            except Exception:
                pass

            if matched_keywords:
                logger.info(f"[决策层] 群聊关键词触发回复: 匹配到 {matched_keywords}")
                diteng.on_group_message(
                    group_id=str(group_id),
                    group_name=perception.get("group_name", ""),
                    user_id=user_id_str,
                    user_name=perception.get("sender_name", "未知"),
                    content=content,
                    is_at_bot=True,
                    reply_to_bot=reply_to_bot,
                )
            elif not keyword_only and user_active:
                logger.info(f"[决策层] 谛听检测到用户仍在活跃对话中，触发回复 (user={user_id_str})")
            else:
                reason = "仅关键词模式" if keyword_only else "无关键词且非活跃对话"
                logger.info(f"[决策层] 群聊消息跳过 ({reason}): {content[:30]}")
                # 即使跳过回复，仍记录消息到谛听以保持上下文连贯
                diteng.on_group_message(
                    group_id=str(group_id),
                    group_name=perception.get("group_name", ""),
                    user_id=user_id_str,
                    user_name=perception.get("sender_name", "未知"),
                    content=content,
                    is_at_bot=False,
                    reply_to_bot=reply_to_bot,
                )
                return None

        # 终端命令处理已由 DSH 接管（DSH = 弥娅的"手"/肢体工具）
        # 守护进程不再需要单独处理终端命令检测

        # 检查是否是拍一拍
        if "拍了拍你" in content:
            logger.info("[决策层] 检测到拍一拍，标记后让 AI 生成回复")
            perception["tool_context"] = "（拍一拍交互）"

        # 存储记忆（委托给记忆管理器）
        await self.memory_manager.store_user_message(perception)

        # 【会话连续性】记录用户活跃时间戳（同步写盘，绕过异步 history 写的不确定性）
        from memory.user_activity_tracker import record_activity

        uid = perception.get("user_id", "")
        if uid:
            record_activity(str(uid), str(perception.get("content", ""))[:100])

        # 【时间感知矫正】每次收到用户消息时更新全局 last_active_at
        if hasattr(self, "_birth_data") and self._birth_data:
            try:
                self._birth_data["last_active_at"] = datetime.now().isoformat()
            except Exception:
                pass

        # 6. 生成响应（委托给响应生成器）
        raw_content = perception.get("content", "")

        # 处理 content 可能是 list 的情况（如图片消息）
        if isinstance(raw_content, list):
            content_parts = []
            for item in raw_content:
                if isinstance(item, dict):
                    item_type = item.get("type", "")
                    item_data = item.get("data", {})
                    if item_type == "text":
                        content_parts.append(item_data.get("text", ""))
                    elif item_type == "image":
                        content_parts.append("[图片]")
                elif isinstance(item, str):
                    content_parts.append(item)
            content = " ".join(content_parts) if content_parts else "[图片消息]"
        else:
            content = raw_content

        # 【优化】私聊谛听策略分析移至并行阶段（_generate_response_cross_platform Phase 1）

        # 【已移除】关键词检测定时任务已改为由 LLM 调用 create_schedule_task 工具自行判断
        # 原 _detect_and_process_timer_task 的关键词匹配（如 "叫我"）过于宽泛，
        # 会导致日常对话（如 "我叫你老婆"）被误判为定时任务请求

        response = await self._generate_response_cross_platform(content, platform, perception)

        # 7. 主动聊天系统 v2.0 + 智能表情包（fire-and-forget，不阻塞响应返回）
        if response:
            asyncio.create_task(self._handle_proactive_chat(perception, content, response), name="proactive")
            if not ("画好了" in response or "发过去了" in response or "画出了" in response):
                asyncio.create_task(self._handle_smart_emoji(response, perception))

        # 【新增】QQ端状态标签（仅日志，不添加到响应中）
        if MiyaPlatform.is_qq(platform) and response and self.personality:
            from core.text_loader import get_form_name

            profile = self.personality.get_profile()
            current_form = profile.get("current_form", "normal")
            speak_mode = profile.get("speak_mode", "casual")
            form_name = get_form_name(current_form)
            logger.debug(f"[形态状态] {form_name}|{speak_mode}")

        # 5. 情绪染色（委托给情绪控制器）
        # 先设置当前神格形态，让染色更符合神格风格
        if response:
            current_form = self.personality.current_form if hasattr(self.personality, "current_form") else "normal"
            if hasattr(self.emotion, "set_form"):
                self.emotion.set_form(current_form)
            response = self.emotion.influence_response(response)

        # 6. 存储AI回复到记忆（fire-and-forget，不阻塞响应返回）
        if response:
            perception["response"] = response
            asyncio.create_task(
                self.memory_manager.store_unified_memory(perception.copy(), "assistant"), name="store_memory"
            )

            # 【修复】将 AI 回复也添加到工作记忆中（fire-and-forget）
            async def _store_working_memory():
                try:
                    msg_type = perception.get("message_type", "")
                    group_id = perception.get("group_id")
                    user_id = perception.get("user_id")

                    from memory.working_memory import get_working_memory

                    wm = get_working_memory()

                    if msg_type == "group" and group_id:
                        wm.add_message(
                            group_id=str(group_id),
                            sender="弥娅",
                            content=response[:200],
                            is_at_bot=False,
                        )
                    elif msg_type == "private" and user_id:
                        private_key = f"private_{str(user_id)}"
                        wm.add_message(
                            group_id=private_key,
                            sender="弥娅",
                            content=response[:200],
                            is_at_bot=False,
                        )
                except Exception as e:
                    logger.debug(f"[决策层] 工作记忆存储AI回复失败: {e}")

            asyncio.create_task(_store_working_memory(), name="store_wm")

            # 【新增】智能记忆 - 自动提取重要内容记忆（fire-and-forget）
            async def _process_historian():
                try:
                    user_input = perception.get("content", "")
                    historian = get_historian()
                    uid = perception.get("user_id", "unknown")
                    await historian.process_after_response(user_input, response, uid)
                except Exception as e:
                    logger.debug(f"[决策层] 智能记忆处理失败: {e}")

            asyncio.create_task(_process_historian(), name="historian")

        # 7. 情绪衰减
        self.emotion.decay_coloring()

        # 8. 返回响应
        message.content["response"] = response
        message.content["platform"] = platform

        # 【统一消息存储】记录出站回复（fire-and-forget）
        if response:

            async def _record_outbound():
                try:
                    from core.unified_message_store import get_unified_message_store

                    store = get_unified_message_store()
                    await store.initialize()
                    await store.record_miya_reply(
                        platform_id=platform,
                        user_id=str(user_id) if user_id else "unknown",
                        content_text=response[:2000],
                        reply_to_message_id=perception.get("message_id", ""),
                        group_id=str(group_id) if group_id else None,
                    )
                    from core.management_api import get_management_api

                    mgmt = get_management_api()
                    if mgmt:
                        await mgmt.broadcast_message(
                            content=response[:2000],
                            platform=platform,
                            sender_name="弥娅",
                            sender_id="miya",
                            user_id=str(user_id) if user_id else "unknown",
                            direction="out",
                            message_id="",
                            reply_to_message_id=perception.get("message_id", ""),
                            group_id=str(group_id) if group_id else None,
                        )
                except Exception as e:
                    logger.debug(f"[MessageStore] 出站记录失败: {e}")

            asyncio.create_task(_record_outbound(), name="record_outbound")

        logger.info(f"[决策层-跨平台] 生成响应: {response[:50] if response else '(空)'}")
        return response

    async def _generate_response_cross_platform(self, content, platform: str, context: dict = None) -> str:
        """
        生成响应（跨平台统一）

        Args:
            content: 用户输入（可能是字符串或列表）
            platform: 平台类型 ('terminal', 'pc_ui', 'qq')
            context: 上下文信息（现已废弃，保留参数兼容）

        Returns:
            响应文本
        """
        perception = context  # 使用 context 作为感知数据源
        # 规范化 content 为字符串
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
        elif not isinstance(content, str):
            content = str(content) if content else ""

        content.lower().strip()

        # AI 自主判断是否调用电脑控制工具 — 无需硬编码关键词

        sender_name = context.get("sender_name", "用户")
        user_id = context.get("user_id") or context.get("sender_id") or 0

        # 如果没有 AI 客户端，使用简化回复
        if not self.ai_client:
            return await self._fallback_response_cross_platform(content, sender_name, platform)

        # 【修改】终端模式：禁用单命令快速检测,让AI处理所有自然语言
        # 原因: 单命令检测会绕过AI理解,导致"打开一个终端"等自然语言请求被错误处理
        # 现在所有终端输入都通过AI分析,让AI决定调用哪个工具(multi_terminal或terminal_command)
        # if platform == 'terminal' and self.tool_subnet:
        #     from webnet.ToolNet.tools.terminal.terminal_command import TerminalCommandTool
        #     ... (已禁用单命令检测逻辑)

        # DSH 作为执行引擎（手/肢体），终端任务由 DSH 的内置工具和 Agent 系统处理
        # 守护进程（大脑/灵魂）通过 MCP 协议与 DSH 双向通信

        # Agent 调度 - 根据用户输入智能选择 Agent（所有平台）
        if self.ai_client and not getattr(self, "_in_agent_execution", False):
            # 【格式塔意识】Agent 工具不再单独调度，融入统一工具池
            # 通过工具调用自动判断是否需要 Agent 工具

            # 加载格式塔控制器
            from core.gestalt_controller import get_gestalt_controller
            from core.gestalt_display import get_gestalt_display

            gestalt_controller = get_gestalt_controller()
            gestalt_display = get_gestalt_display()

            # 初始化格式塔（如果需要）
            if not gestalt_controller._agent_tools_loaded and self.tool_subnet:
                await gestalt_controller.initialize(self.tool_subnet)

            # 显示格式塔启动信息
            logger.info("[格式塔] 格式塔意识已激活，Agent工具已融入工具池")

            # 【格式塔】不再使用旧的 Agent 调度
            # Agent 工具现在通过 tool_subnet.get_tools_schema() 自动包含
            # 工具调用由 AI 自行判断，协作引擎也会参与处理

            # 显示格式塔工具信息
            agent_tools = list(gestalt_controller.get_all_tool_sources().keys())
            if agent_tools:
                gestalt_display.print_thinking(
                    "工具池初始化",
                    f"Agent工具已融入: {', '.join(agent_tools[:5])}...",
                    status="done",
                )

            # 【优化】检查 Agent 是否已处理，避免重复执行
            if context and isinstance(context, dict) and context.get("_agent_executed"):
                logger.info("[决策层] Agent 已处理请求，跳过主流程")
                return ""

        try:
            # 构建系统提示词（包含平台信息）
            self.personality.get_profile()

            # 获取平台可用工具
            available_tools = self._get_platform_tools(platform)

            # ============================================================
            # 【优化】Phase 1: 并行检索所有独立上下文源
            # conversation / knowledge / persona / awareness / search / group_chat
            # ============================================================
            msg_type = context.get("message_type", "")
            ctx_group_id = str(context.get("group_id", "")) if context.get("group_id") else ""
            if msg_type == "group" and ctx_group_id:
                session_id = f"group_{ctx_group_id}_{user_id}"
            else:
                session_id = f"user_{user_id}"
            user_id_str = str(user_id)

            _needs_recall = self.conversation_context_manager.check_needs_recall(content)
            _is_deep = self.conversation_context_manager._is_deep_discussion(content)

            async def fetch_conversation_context():
                self.conversation_context_manager._update_topic_tracking(session_id, content)
                base_limit = self.conversation_context_manager.conversation_context_max_count
                max_tokens = self.conversation_context_manager.conversation_context_max_tokens

                if _needs_recall:
                    main_msgs = max(base_limit * 2, 80)
                elif _is_deep:
                    main_msgs = max(base_limit * 2, 60)
                else:
                    main_msgs = base_limit

                allocation = await self.context_builder.build(
                    session_id=session_id,
                    user_id=user_id_str,
                    current_input=content,
                    consumers=[
                        ConsumerRequest("main_prompt", max_messages=main_msgs, max_tokens=max_tokens, priority=1),
                        ConsumerRequest(
                            "soul_analysis", max_messages=24, max_tokens=3000, priority=2, per_message_max_chars=300
                        ),
                    ],
                    needs_recall=_needs_recall,
                    is_deep_discussion=_is_deep,
                )

                self._last_context_allocation = allocation

                context = allocation.get("main_prompt")
                logger.info(
                    f"[对话上下文] 统一管道: {allocation.total_messages}条 -> "
                    f"main={len(context)}条/{allocation.slices.get('main_prompt').token_count if 'main_prompt' in allocation.slices else 0}t, "
                    f"soul={len(allocation.get('soul_analysis'))}条"
                )
                return context

            async def fetch_user_persona():
                upc = ""
                gpc = ""
                try:
                    from core.user_persona import get_user_persona_manager

                    q_uid = context.get("user_id")
                    pm = get_user_persona_manager()
                    if q_uid:
                        upc = pm.build_user_context(
                            user_id=str(q_uid),
                            group_id=str(context.get("group_id")) if context.get("group_id") else None,
                        )
                    if context.get("group_id"):
                        gpc = pm.build_group_context(str(context.get("group_id")))
                except Exception as e:
                    logger.debug(f"[决策层] 用户侧写检索失败: {e}")
                return upc, gpc

            async def fetch_awareness_text():
                try:
                    from core.awareness import get_awareness

                    awareness = get_awareness()
                    if awareness:
                        perception_ctx = awareness.gather_context(
                            message_type=context.get("message_type", ""),
                            group_id=context.get("group_id", 0),
                            group_name=context.get("group_name", ""),
                            user_id=context.get("user_id", 0),
                            sender_name=context.get("sender_name", ""),
                            sender_role=context.get("sender_role", ""),
                        )
                        result = perception_ctx.get("perception_text", "")
                        logger.info(f"[意识感知] 成功: {result[:150]}")
                        return result
                except Exception:
                    pass
                return ""

            async def fetch_search_context():
                sc = ""
                try:
                    global _search_strategy_cache
                    if _search_strategy_cache is None:
                        search_config_path = Path(__file__).parent.parent / "config" / "text_config.json"
                        if search_config_path.exists():
                            import json

                            with open(search_config_path, "r", encoding="utf-8") as f:
                                full_config = json.load(f)
                            _search_strategy_cache = full_config.get("search_strategy", {})
                        else:
                            _search_strategy_cache = {}
                    search_strategy = _search_strategy_cache
                    enabled = search_strategy.get("enabled")
                    auto = search_strategy.get("auto_search_enabled")
                    if enabled and auto:
                        content_lower = content.lower()
                        skip_keywords = search_strategy.get("skip_search_keywords", [])
                        should_skip = any(kw.lower() in content_lower for kw in skip_keywords)
                        if not should_skip:
                            trigger_kw = search_strategy.get("auto_search_triggers", [])
                            needs_search = any(kw in content_lower for kw in trigger_kw) or len(content) > 50
                            if needs_search:
                                try:
                                    import importlib

                                    web_search_mod = importlib.import_module("webnet.ToolNet.tools.network.web_search")
                                    if hasattr(web_search_mod, "EnhancedWebSearch"):
                                        # 提取核心搜索词（整句消息直接搜索噪音太大）
                                        search_query = content
                                        try:
                                            query_optimizer_mod = importlib.import_module(
                                                "webnet.ToolNet.tools.network.query_optimizer"
                                            )
                                            if hasattr(query_optimizer_mod, "extract_core_query"):
                                                search_query = query_optimizer_mod.extract_core_query(content) or content
                                        except Exception:
                                            pass
                                        searcher = web_search_mod.EnhancedWebSearch()
                                        loop = asyncio.get_running_loop()
                                        search_results = await loop.run_in_executor(None, searcher.search, search_query)
                                        if search_results:
                                            # 格式化为人读文本，避免裸 repr 字典喂给 LLM
                                            sc = "\n\n【联网搜索结果】\n" + searcher.format_results_for_ai(
                                                search_results, max_items=6
                                            )
                                except Exception:
                                    pass
                except Exception:
                    pass
                return sc

            async def fetch_group_chat_context():
                gcc = ""
                from memory.working_memory import get_working_memory

                wm = get_working_memory()
                msg_type = context.get("message_type", "")
                ctx_uid = context.get("user_id")
                ctx_uid_str = str(ctx_uid) if ctx_uid else ""
                if msg_type == "group" and context.get("group_id"):
                    group_id_str = str(context.get("group_id"))
                    wm.add_message(
                        group_id=group_id_str,
                        sender=context.get("sender_name", "未知"),
                        content=content,
                        is_at_bot=context.get("is_at_bot", False),
                        sender_id=ctx_uid or 0,
                    )
                    gcc = wm.build_prompt_context(group_id_str)
                    if gcc:
                        logger.debug(f"[工作记忆] 注入群聊上下文: {len(gcc)} 字符")
                elif msg_type == "private" and ctx_uid:
                    private_key = f"private_{ctx_uid_str}"
                    wm.add_message(
                        group_id=private_key,
                        sender=context.get("sender_name", "用户"),
                        content=content,
                        is_at_bot=context.get("is_at_bot", False),
                        sender_id=ctx_uid or 0,
                    )
                    gcc = wm.build_prompt_context(private_key)
                    if gcc:
                        logger.debug(f"[工作记忆] 注入私聊上下文: {len(gcc)} 字符")
                return gcc

            async def fetch_diting_strategy():
                """谛听消息策略分析 — 与上下文检索并行"""
                try:
                    from memory.diteng_listener import get_diting

                    diteng = get_diting()
                    msg_type = context.get("message_type", "")
                    ctx_uid = context.get("user_id")
                    ctx_uid_str = str(ctx_uid) if ctx_uid else ""
                    group_id = context.get("group_id")
                    is_at_bot = context.get("is_at_bot", False)

                    # 获取最近上下文
                    recent_context = ""
                    try:
                        from memory.working_memory import get_working_memory

                        wm = get_working_memory()
                        if msg_type == "group" and group_id:
                            recent_context = wm.build_prompt_context(str(group_id))[:500]
                        elif msg_type == "private" and ctx_uid:
                            recent_context = wm.build_prompt_context(f"private_{ctx_uid_str}")[:500]
                    except Exception:
                        pass

                    strategy = await diteng.analyze_message_strategy(
                        content=content,
                        user_id=ctx_uid_str,
                        group_id=str(group_id) if group_id else None,
                        is_at_bot=is_at_bot,
                        message_type=msg_type,
                        recent_context=recent_context,
                    )
                    logger.warning(
                        f"[谛听-并行] should_respond={strategy.should_respond}, "
                        f"strategy={strategy.response_strategy}, "
                        f"intent={getattr(strategy, 'message_intent', 'N/A')}, "
                        f"confidence={getattr(strategy, 'confidence', 0):.2f}"
                    )
                    return strategy
                except Exception as e:
                    logger.warning(f"[谛听-并行] 分析失败: {e}")
                return None

            # 启动 Phase 1 所有并行任务（含 AI 注入检测，从 Phase 0 移入以消除串行等待）
            is_qq = MiyaPlatform.is_qq(platform)

            conv_task = asyncio.create_task(fetch_conversation_context(), name="conv")

            async def fetch_search_with_timeout():
                try:
                    return await asyncio.wait_for(fetch_search_context(), timeout=6.0)
                except asyncio.TimeoutError:
                    logger.debug("[决策层] 联网搜索超时 (6s)")
                except Exception:
                    pass
                return ""

            async def fetch_diting_with_timeout():
                try:
                    return await asyncio.wait_for(fetch_diting_strategy(), timeout=6.0)
                except asyncio.TimeoutError:
                    logger.debug("[决策层] 谛听策略分析超时 (6s)")
                except Exception:
                    pass
                return None

            async def fetch_ai_injection_check():
                if not perception.get("_pending_ai_injection_check"):
                    return None
                try:
                    result = await self._check_ai_injection_parallel(content, perception.get("source", ""))
                    return result
                except Exception:
                    return None

            if is_qq:
                persona_task = asyncio.create_task(fetch_user_persona(), name="persona")
                awareness_task = asyncio.create_task(fetch_awareness_text(), name="awareness")
                search_task = asyncio.create_task(fetch_search_with_timeout(), name="search")
                wm_task = asyncio.create_task(fetch_group_chat_context(), name="wm")
                diting_task = asyncio.create_task(fetch_diting_with_timeout(), name="diting")
                injection_task = asyncio.create_task(fetch_ai_injection_check(), name="injection")
            else:

                async def _empty_tuple():
                    return ("", "")

                async def _empty_str():
                    return ""

                async def _none():
                    return None

                persona_task = asyncio.create_task(_empty_tuple(), name="persona-skip")
                awareness_task = asyncio.create_task(_empty_str(), name="awareness-skip")
                search_task = asyncio.create_task(_empty_str(), name="search-skip")
                wm_task = asyncio.create_task(_empty_str(), name="wm-skip")
                diting_task = asyncio.create_task(_none(), name="diting-skip")
                injection_task = asyncio.create_task(_none(), name="injection-skip")
                logger.info(f"[决策层-{platform}] 跳过 6 个非必要上下文检索")

            # 等待 conversation_context (cognitive 和 soul 都需要它)
            conversation_context = await conv_task
            logger.info(f"[决策层] 对话上下文: {len(conversation_context)} 条, session={session_id}")

            # ============================================================
            # Phase 2: 先获取认知记忆，再注入灵魂发生器（保证内心独白连贯）
            # Soul Generator 需要认知记忆上下文来生成连贯的内心独白
            # ============================================================
            async def fetch_cognitive_memory():
                cmc = ""
                try:
                    cognitive_engine = get_cognitive_engine()
                    query_user_id = user_id_str if context.get("user_id") else None
                    query_group_id = str(context.get("group_id")) if context.get("group_id") else None
                    cmc = await cognitive_engine.build_context(
                        user_input=content,
                        conversation_history=conversation_context,
                        limit=self._calc_cognitive_limit(conversation_context, _needs_recall),
                        user_id=query_user_id,
                        group_id=query_group_id,
                    )
                    if cmc:
                        logger.info(f"[决策层] 智能记忆检索到相关记忆 (user_id={query_user_id})")
                except Exception as e:
                    logger.warning(f"[决策层] 智能记忆检索失败: {e}")
                return cmc

            async def run_soul_generator(cognitive_memory=""):
                sr = None
                try:
                    if self._soul_generator:
                        allocation = getattr(self, "_last_context_allocation", None)
                        history = (
                            allocation.get("soul_analysis")
                            if allocation
                            else (conversation_context if conversation_context else [])
                        )
                        ai_client_for_soul = None
                        if self.model_pool:
                            try:
                                multi_config = self.model_pool._config
                                soul_model_id = multi_config.get("system_defaults", {}).get(
                                    "soul_model", "deepseek_v4_flash_official"
                                )
                                ai_client_for_soul = self.model_pool.create_ai_client(soul_model_id)
                            except Exception:
                                pass
                        personality_info = {}
                        if self.personality:
                            try:
                                form_name = self.personality.get_form_for_chat(
                                    str(user_id),
                                    str(perception.get("group_id", "")),
                                )
                                form = self.personality.get_form_config(form_name)
                                personality_info = {
                                    "form_name": form.get("name", "默认"),
                                    "form_description": form.get("description", ""),
                                    "speaking_style": form.get("speaking", {}).get("style", ""),
                                }
                            except Exception:
                                pass

                        sr = await self._soul_generator.process(
                            content,
                            history,
                            ai_client_for_soul,
                            user_info={
                                "user_id": user_id,
                                "group_id": perception.get("group_id"),
                                "is_group": (perception.get("message_type") == "group"),
                            },
                            personality_info=personality_info,
                            cognitive_memory=cognitive_memory,
                        )
                except Exception as e:
                    logger.warning(f"[灵魂] 提前分析失败: {e}")
                return sr

            cog_task = asyncio.create_task(fetch_cognitive_memory(), name="cog")

            # Phase 2 提前启动：soul_generator 与 Phase 1 剩余任务并行
            # 它只需要 conversation_context + cognitive_memory，不需要搜索结果/谛听等
            async def run_soul_early():
                cm = await cog_task
                sr = await run_soul_generator(cognitive_memory=cm)
                return cm, sr

            soul_task = asyncio.create_task(run_soul_early(), name="soul")

            # 等待其余 Phase 1 任务（同时 cog → soul 在后台运行）
            user_persona_context, group_persona_context = await persona_task
            awareness_text = await awareness_task
            temporal = self._get_temporal_awareness(
                user_id=user_id_str,
                platform=platform,
            )
            if temporal:
                awareness_text = (awareness_text or "") + f"\n【弥娅时间感知】{temporal}"
                logger.info(f"[时间感知] {temporal}")
            search_context = await search_task
            group_chat_context = await wm_task

            # 等待谛听策略结果并注入 perception
            try:
                diting_strategy = await diting_task
                if diting_strategy:
                    if not diting_strategy.should_respond:
                        logger.info(f"[谛听-并行] 策略决定不回复: {diting_strategy.reason}")
                        if getattr(diting_strategy, "response_strategy", "") == "like_only":
                            try:
                                if hasattr(self, "onebot_client") and self.onebot_client:
                                    user_id_str = str(context.get("user_id", ""))
                                    await self.onebot_client.send_like(user_id_str)
                            except Exception:
                                pass
                        return None
                    context["_message_strategy"] = {
                        "strategy": diting_strategy.response_strategy,
                        "intent": getattr(diting_strategy, "message_intent", "chat"),
                        "style": getattr(diting_strategy, "suggested_reply_style", "casual"),
                        "confidence": getattr(diting_strategy, "confidence", 0.8),
                    }
                    # 【谛听传递】将策略分析结果转化为自然语言指引，注入下游
                    sdesc = _load_strategy_descriptions()
                    strategy_desc_map = sdesc.get("response_strategies", {})
                    style_desc_map = sdesc.get("reply_styles", {})
                    _strat = diting_strategy.response_strategy
                    _style = getattr(diting_strategy, "suggested_reply_style", "normal")
                    _intent = getattr(diting_strategy, "message_intent", "chat")
                    _strat_desc = strategy_desc_map.get(_strat, "自然回复")
                    _style_desc = style_desc_map.get(_style, "正常风格")
                    context["_strategy_guidance"] = (
                        f"\n\n【回复策略指引 · 谛听分析】\n"
                        f"- 用户意图：{_intent}\n"
                        f"- 回复方式：{_strat_desc}\n"
                        f"- 回复语气：{_style_desc}\n"
                        f"（请根据以上指引调整你的回复风格，但不要生硬地复述这些指令）"
                    )
            except Exception as e:
                logger.warning(f"[谛听-并行] 结果处理失败: {e}")

            # 检查 AI 注入并行检测结果
            try:
                injection_check_result = await injection_task
                if injection_check_result:
                    if self.ai_injection_detector and self.ai_injection_detector.should_block():
                        logger.warning(f"[决策层-AI防注入] 并行检测阻止响应")
                        return self.ai_injection_detector.get_fallback_response()
                    else:
                        if not perception.get("_protection_prompt"):
                            perception["_protection_prompt"] = injection_check_result
                            logger.info("[决策层] 并行AI注入检测已添加防护提示")
            except Exception:
                pass

            # 等待 Phase 2 任务（soul 已在后台与 Phase 1 并行运行）
            # 等待灵魂 AI 分析完成，确保当前轮次使用最新鲜的情绪上下文
            cognitive_memory_context, soul_result = await soul_task
            if soul_result and soul_result.get("emotions"):
                self._last_soul_data = soul_result

            # 处理 Soul Generator 结果 (共用于两条路径)
            emotion_context_for_collab = ""
            if soul_result:
                dominant = soul_result.get("dominant_emotion", "") or ""
                miya_emotions = soul_result.get("emotions", {})
                # emotions 可能是 list[dict] 或 dict[str,int]，统一归一化
                if isinstance(miya_emotions, list):
                    emo_items = [
                        (e.get("name", ""), e.get("intensity", 0)) for e in miya_emotions if isinstance(e, dict)
                    ]
                elif isinstance(miya_emotions, dict):
                    emo_items = list(miya_emotions.items())
                else:
                    emo_items = []
                top_emotions = sorted(emo_items, key=lambda x: float(x[1] or 0), reverse=True)[:3]
                if top_emotions:
                    miya_dominant = top_emotions[0][0]
                    miya_intensity = top_emotions[0][1]
                    emotion_str = " + ".join([f"{name}({int(val)}%)" for name, val in top_emotions])
                else:
                    miya_dominant = "平静"
                    miya_intensity = 40
                    emotion_str = "平静"
                # 主导情绪：LLM 未输出 dominant_emotion 时，取情绪谱最高分
                if not dominant:
                    dominant = miya_dominant
                logger.info(f"[灵魂] 主导情绪: {dominant} | 弥娅: {emotion_str}")
                inner_thought = soul_result.get("inner_thought", "") or soul_result.get("analysis", {}).get(
                    "inner_thought", ""
                )
                attribution = soul_result.get("attribution", "") or soul_result.get("analysis", {}).get(
                    "attribution", ""
                )
                reflection = soul_result.get("reflection", "") or soul_result.get("analysis", {}).get("reflection", "")

                # 从配置文件加载情感引导文案
                eg = _get_emotion_guidance()
                emotion_context_for_collab = eg["header"]
                emotion_context_for_collab += eg["user_emotion"].format(dominant=dominant)
                emotion_context_for_collab += eg["miya_emotion"].format(
                    miya_dominant=miya_dominant, miya_intensity=miya_intensity, emotion_spectrum=emotion_str
                )
                if inner_thought:
                    emotion_context_for_collab += eg["inner_thought"].format(inner_thought=inner_thought)
                if attribution:
                    emotion_context_for_collab += eg["attribution"].format(attribution=attribution)
                if reflection:
                    emotion_context_for_collab += eg["reflection"].format(reflection=reflection)
                emotion_context_for_collab += eg["footer"]

                # 更新缓存供下一轮复用
                self._set_soul_cache(
                    user_id_str,
                    {
                        "emotion_context": emotion_context_for_collab,
                        "cognitive_memory": cognitive_memory_context,
                        "emotions": miya_emotions,
                    },
                )
                self._save_soul_snapshot()
            # soul 分析失败时，尝试使用缓存兜底
            if not emotion_context_for_collab:
                cached = self._get_soul_cache(user_id_str)
                cached_emotion = cached.get("emotion_context", "")
                if cached_emotion:
                    emotion_context_for_collab = cached_emotion
                    logger.info(f"[灵魂-兜底] soul 分析未返回，使用缓存 ({len(cached_emotion)} 字符)")

            # 冷启动兜底 — 没有 soul 也没有缓存时，给协作引擎一个空标题
            if not emotion_context_for_collab:
                eg = _get_emotion_guidance()
                emotion_context_for_collab = eg.get("header", "")

            logger.debug(
                f"[DEBUG认知] build_context 返回长度={len(cognitive_memory_context) if cognitive_memory_context else 0}, user={user_id_str}"
            )

            # ============================================================
            # 构建提示词所需变量（status_prompt, protection_prompt, message_type）
            # ============================================================
            group_id_extra = context.get("group_id", "0") if context else "0"
            status_prompt = self.personality.get_status_for_prompt(
                user_id=str(user_id) if user_id else "",
                group_id=str(group_id_extra) if group_id_extra and group_id_extra != 0 else "",
            )
            protection_prompt = context.get("_protection_prompt", "")
            message_type = context.get("message_type", "unknown")

            # 获取引用消息信息
            reply_info = context.get("reply")
            reply_context = ""
            if reply_info:
                # 兼容 ReplySegment 对象和字典
                if hasattr(reply_info, "get"):
                    sender_name = reply_info.get("sender_name", "未知")
                    content = reply_info.get("content", "")[:100]
                    image_url = reply_info.get("image_url")
                elif hasattr(reply_info, "sender_name"):
                    sender_name = getattr(reply_info, "sender_name", "未知")
                    content = getattr(reply_info, "content", "")[:100]
                    image_url = getattr(reply_info, "image_url", None)
                else:
                    sender_name = "未知"
                    content = ""
                    image_url = None

                if image_url:
                    reply_context = f"\n[引用消息] 来自: {sender_name}\n内容: {content}\n图片URL: {image_url}"
                else:
                    reply_context = f"\n[引用消息] 来自: {sender_name}\n内容: {content}"

            # 获取文件信息
            files_info = context.get("files", [])
            files_context = ""
            if files_info:
                # 兼容 FileSegment 对象和字典
                file_list = []
                for f in files_info:
                    if hasattr(f, "get"):
                        file_list.append(f.get("name", "文件"))
                    elif hasattr(f, "name"):
                        file_list.append(f.name)
                    else:
                        file_list.append("文件")
                files_context = f"\n[附加文件] {', '.join(file_list)}"

            # 获取是否有媒体
            has_media = context.get("has_media", False)
            media_context = "\n[图片消息]" if has_media else ""

            # 获取图片分析结果
            image_analysis = context.get("image_analysis")
            image_context = ""
            if image_analysis and image_analysis.get("success"):
                description = image_analysis.get("description", "")
                labels = image_analysis.get("labels", [])
                model = image_analysis.get("model", "未知")
                image_context = f"\n[图片描述] {description}"
                if labels:
                    image_context += f"\n[图片标签] {', '.join(labels)}"
                image_context += f"\n(分析模型: {model})"
                # 【重要】告诉AI不要重复调用工具
                image_context += "\n【注意】图片已经分析完成，不要再调用 qq_image_analyzer 工具！"
                logger.info(f"[决策层] 图片分析结果已添加到上下文: {description[:50]}")
            # 【新增】如果检测到引用消息包含图片但没有分析结果，给出提示
            elif context.get("reply") and "[引用消息包含图片]" in str(context.get("reply")):
                # 获取引用消息中的图片URL
                reply_info = context.get("reply")
                image_url = None
                if hasattr(reply_info, "get"):
                    image_url = reply_info.get("image_url")
                elif hasattr(reply_info, "image_url"):
                    image_url = getattr(reply_info, "image_url", None)

                if image_url:
                    image_context = (
                        f"\n[图片消息] 用户引用了包含图片的消息。"
                        f"\n【重要】图片URL: {image_url}"
                        f"\n【必须】请立即调用 qq_image_analyzer 工具分析这张图片！"
                    )
                    logger.info(f"[决策层] 检测到引用消息包含图片，URL: {image_url[:50]}...")
                else:
                    image_context = "\n[图片消息] 用户引用了一条包含图片的消息，但无法获取图片URL"
                    logger.info("[决策层] 检测到引用消息包含图片但无URL")

            # 【弥娅之眼】屏幕感知 — 原始感官时间序列
            screen_context = ""
            try:
                from miya_senses.sensors.screen_aware import get_screen_aware

                sa = get_screen_aware()
                if sa and sa.should_observe:
                    await sa.observe(allow_vision=False)
                if sa:
                    card = sa.build_timeline_card(max_entries=12)
                    if card and len(card) > 30:
                        screen_context = card
                        logger.info(f"[决策层] 弥娅之眼: {card[:120]}...")
            except Exception:
                pass

            # 【陪玩】注入陪玩画面（如果游戏陪玩引擎活跃）
            try:
                from core.game_play.engine import get_game_play_engine

                engine = get_game_play_engine()
                if engine._state.active and engine._state.vision_enabled:
                    summary = await engine.get_screen_summary()
                    if summary:
                        if screen_context:
                            screen_context += "\n" + summary
                        else:
                            screen_context = summary
                        logger.debug(f"[决策层] 陪玩画面: {summary[:60]}...")
            except Exception:
                pass

            at_list = perception.get("at_list", [])
            at_content_hint = content
            if at_list:
                at_names = perception.get("at_names", {})
                at_names_str = ", ".join(f"{at_names.get(str(qq), 'QQ' + str(qq))}" for qq in at_list)
                at_qids = ", ".join(str(qq) for qq in at_list)
                at_content_hint = f"[用户@了{at_names_str}(QQ:{at_qids})] {content}"

            # 【注入管线】获取 MemoryBus 的 identity + user_profile 注入
            bus_identity_context = ""
            try:
                from memory.bus import get_memory_bus

                bus = await get_memory_bus()
                injection_result = await bus.inject(
                    user_id=user_id_str,
                    group_id=str(context.get("group_id", "")) if context.get("group_id") else "",
                    session_id=session_id,
                    platform=platform,
                    user_input=content,
                    conversation_history=conversation_context,
                    available_tools=available_tools,
                )
                bus_identity_context = injection_result.get("system", "")
                if bus_identity_context:
                    logger.info(f"[注入管线] 注入长度={len(bus_identity_context)}")
            except Exception as e:
                logger.debug(f"[注入管线] 失败: {e}")

            prompt_info = self.prompt_manager.build_full_prompt(
                user_input=at_content_hint,
                memory_context=conversation_context,
                knowledge_context="",
                additional_context={
                    "platform": platform,
                    "message_type": message_type,
                    "group_id": context.get("group_id", 0),
                    "group_name": context.get("group_name", ""),
                    "user_id": user_id,
                    "sender_name": sender_name,
                    "available_tools": available_tools,
                    "at_list": perception.get("at_list", []),
                    "at_names": perception.get("at_names", {}),
                    "bot_qq": context.get("bot_qq"),
                    "is_creator": self.platform_tools_manager.is_creator(user_id, self.onebot_client),
                    "status_prompt": status_prompt,
                    "cognitive_memory": cognitive_memory_context,
                    "emotion_context": emotion_context_for_collab,
                    "protection_prompt": protection_prompt,
                    # 【新增】用户/群聊侧写上下文
                    "user_persona": user_persona_context,
                    "group_persona": group_persona_context,
                    # 【新增】引用消息和文件上下文
                    "reply_context": reply_context,
                    "files_context": files_context,
                    "media_context": media_context,
                    "image_context": image_context,
                    # 【陪玩】屏幕画面上下文
                    "screen_context": screen_context,
                    # 【谛听】群聊上下文摘要
                    "group_chat_context": group_chat_context,
                    # 【意识感知】时间、地点、活动感知
                    "awareness_text": awareness_text,
                    # 【主动搜索】联网搜索结果
                    "search_context": search_context,
                },
            )

            # 注入 MemoryBus 系统前缀 (identity + user_profile hooks)
            if bus_identity_context:
                prompt_info["system"] = bus_identity_context + "\n" + prompt_info["system"]

            logger.debug(f"[决策层-跨平台] 系统提示词前200字符: {prompt_info['system'][:200]}")

            # 【弥娅综合感知】谛听策略 + 灵魂情绪 + AP规则情感 融合为统一画像
            strategy_guidance = context.get("_strategy_guidance", "")
            msg_strategy = context.get("_message_strategy", {})
            if strategy_guidance or emotion_context_for_collab:
                integrated = _build_integrated_status(
                    strategy_guidance,
                    emotion_context_for_collab,
                    msg_strategy.get("strategy", "full_reply"),
                    msg_strategy.get("style", "normal"),
                    msg_strategy.get("intent", "chat"),
                )

                # v8.0: 附加脊柱神经状态——让弥娅知道自己在呼吸
                try:
                    spine_status = _build_spine_status_prompt()
                    if spine_status:
                        integrated = spine_status + "\n" + integrated
                except Exception:
                    pass

                prompt_info["system"] = integrated + "\n" + prompt_info["system"]
                logger.info(f"[弥娅-感知] 综合状态指引已注入 system prompt ({len(integrated)} 字符)")

            # 【分寸规则】记忆空间隔离 + 场合自适应
            memory_guard = _build_memory_guard(
                msg_type=message_type,
                ctx_group_id=ctx_group_id,
                recipient=context.get("recipient", ""),
            )
            prompt_info["system"] = memory_guard + "\n" + prompt_info["system"]

            # 设置工具上下文和 ToolNet（符合 MIYA 框架）
            if self.tool_subnet:
                # 使用 ToolNet 子网（符合 MIYA 蛛网式分布式架构）
                self.ai_client.set_tool_registry(self.tool_subnet.get_tools_schema)

                # 设置 tool_adapter 的 tool_registry（关键修复）
                from core.tool_adapter import get_tool_adapter

                adapter = get_tool_adapter()
                adapter.set_tool_registry(self.tool_subnet.registry)

                tool_context = {
                    "platform": platform,
                    "user_id": user_id if user_id else 0,
                    "platform_user_id": perception.get("platform_user_id", user_id),
                    "group_id": perception.get("group_id"),
                    "message_type": perception.get("message_type"),
                    "sender_name": sender_name,
                    "at_list": perception.get("at_list", []) or [],
                    "at_names": perception.get("at_names", {}),
                    "bot_qq": perception.get("bot_qq"),
                    "memory_engine": self.memory_engine,
                    "emotion": self.emotion,
                    "personality": self.personality,
                    "scheduler": self.scheduler,
                    "onebot_client": self.onebot_client,
                    "send_like_callback": getattr(self.onebot_client, "send_like", None)
                    if self.onebot_client
                    else None,
                    # 【关键】传递图片分析结果
                    "image_analysis": perception.get("image_analysis"),
                    "image_data": perception.get("image_data"),
                }
                logger.debug(f"[决策层] 构建的tool_context keys: {list(tool_context.keys())}")
                logger.debug(
                    f"[决策层] tool_context中 onebot_client={tool_context.get('onebot_client')}, send_like_callback={tool_context.get('send_like_callback')}"
                )
                self.ai_client.set_tool_context(tool_context)

            # 调用 AI（带工具）
            # 【修改】使用 auto 让 AI 自行决定是否调用工具
            # 注意：不使用 required，因为很多 API 不支持此参数
            tool_choice = "auto"

            # 只获取当前平台相关的核心工具，减少 API 负担
            # 避免 101 个工具导致 500 错误
            platform_tools = self.platform_tools_manager.get_platform_specific_tools(platform)
            tools_schema = platform_tools if platform_tools else self.tool_subnet.get_tools_schema()

            logger.info(f"[决策层-跨平台] 使用平台工具: {platform}, 工具数量: {len(tools_schema)}")

            # 使用模型池动态选择模型
            ai_client_to_use = self.ai_client  # 默认使用传入的AI客户端

            if self.model_pool:
                # classify_task 可能是同步或异步方法
                classify_result = self.model_pool.classify_task(content, context)
                if asyncio.iscoroutine(classify_result):
                    task_type = await classify_result
                else:
                    task_type = classify_result

                # 【加速】纯闲聊精简工具集 — 53→10，大幅降低 prompt 体积
                # 命令/任务类请求 + 谛听超时兜底不砍工具
                diting_intent = context.get("_message_strategy", {}).get("intent", "")
                action_intents = {"command", "task", "reminder", "schedule", "alarm"}
                if (
                    task_type == TaskType.SIMPLE_CHAT
                    and len(tools_schema) > 10
                    and diting_intent not in action_intents
                    and diting_intent != ""
                ):
                    minimal = self.platform_tools_manager.get_minimal_chat_tools()
                    if minimal:
                        tools_schema = minimal
                        logger.info(f"[决策层-闲聊加速] 精简为 {len(tools_schema)} 个工具")

                # 【谛听覆盖】亲密/分享场景不应被技术关键词误导为 code_analysis
                personal_intents = {"share", "chat", "love", "comfort", "tease", "confession"}
                if diting_intent in personal_intents and task_type != TaskType.SIMPLE_CHAT:
                    logger.info(f"[决策层] 谛听覆盖任务分类: {task_type.value} → simple_chat (intent={diting_intent})")
                    task_type = TaskType.SIMPLE_CHAT

                # 尝试使用协作引擎处理
                if self.collaboration_engine and self.collaboration_engine.enabled:
                    try:
                        from core.ai_client import AIClientFactory

                        # 使用正确的tool_context，包含onebot_client和send_like_callback
                        tool_ctx_for_collab = tool_context
                        logger.debug(
                            f"[决策层] 传递给协作引擎的tool_context keys: {list(tool_ctx_for_collab.keys()) if tool_ctx_for_collab else 'None'}"
                        )

                        # 【优化】使用并行阶段预计算的 Soul Generator 结果
                        # soul_result 和 emotion_context_for_collab 已在 Phase 2 并行计算

                        # 传递情绪上下文给协作引擎
                        if emotion_context_for_collab and tool_ctx_for_collab:
                            # 【认知记忆注入】检索近期的思考记录，注入情感指引
                            try:
                                from memory.cognition_cache import get_cognition_cache

                                cache = get_cognition_cache()
                                cache_context = await cache.get_context_for_ai(user_id, limit=2)
                                if cache_context:
                                    emotion_context_for_collab += "\n\n" + cache_context
                                    logger.info("[认知缓存] 已注入认知记忆到协作引擎")
                                else:
                                    from memory import retrieve_cognition

                                    recent_cognitions = await retrieve_cognition(user_id, limit=3)
                                    if recent_cognitions:
                                        parts = []
                                        for cog in recent_cognitions:
                                            if cog.get("thinking"):
                                                parts.append(f"- 思考: {cog['thinking'][:150]}")
                                            if cog.get("inner_thought"):
                                                parts.append(f"- 想法: {cog['inner_thought'][:80]}")
                                        if parts:
                                            cognition_text = "\n【近期思维参考】\n" + "\n".join(parts)
                                            cognition_text += "\n（以上是弥娅近期的思考记录，用于了解自己的连贯状态，不要直接引用输出）"
                                            emotion_context_for_collab += "\n\n" + cognition_text
                                            logger.info("[认知记忆] 已注入认知记忆到协作引擎 (db fallback)")
                            except Exception as e:
                                logger.debug(f"[认知记忆] 注入协作引擎失败: {e}")

                            tool_ctx_for_collab["emotion_context"] = emotion_context_for_collab
                            # v7.0: 注入认知记忆到协作引擎 context，供 fallback 灵魂生成器使用
                            tool_ctx_for_collab["cognitive_memory"] = (
                                cognitive_memory_context if cognitive_memory_context else ""
                            )

                        # 将认知记忆直接注入 system prompt，确保 AI 能看见
                        final_system_prompt = prompt_info["system"]
                        if cognitive_memory_context:
                            final_system_prompt = (
                                "\n\n【以下是弥娅记忆系统检索到的与你当前对话相关的过往记录，请在回复中自然引用这些记忆，让对话更连贯】\n"
                                + cognitive_memory_context
                                + "\n【记忆记录结束】\n\n"
                                + final_system_prompt
                            )
                            logger.debug(
                                f"[决策层] 认知记忆已注入 system prompt ({len(cognitive_memory_context)} 字符)"
                            )

                        collab_result = await self.collaboration_engine.process(
                            message=content,
                            task_type=task_type.value,
                            platform=platform,
                            context=tool_ctx_for_collab,
                            system_prompt=final_system_prompt,
                            user_prompt=prompt_info["user"],
                            tools=tools_schema,
                            ai_client_factory=AIClientFactory,
                        )

                        # 记录协作结果
                        self._last_selected_model = ",".join(collab_result.models_used)
                        self._last_task_type = task_type.value
                        logger.debug("[协作引擎] 流程开始")
                        logger.info(
                            f"[决策层-协作引擎] 模式={collab_result.mode.value} | "
                            f"模型={collab_result.models_used} | "
                            f"Token≈{collab_result.token_estimate} | "
                            f"原因={collab_result.reasoning}"
                        )

                        # 【新增】协作引擎路径也存储情绪记忆（无论soul_result是否有效都存储）
                        logger.debug("[协作引擎] 开始存储情绪记忆")
                        logger.info(f"[灵魂记忆] 协作引擎检查: soul_result={bool(soul_result)}, user_id={user_id}")

                        # 处理emotions格式 - 支持list或dict
                        _emotions_raw = soul_result.get("emotions", []) if soul_result else []
                        _emotions = {}
                        if isinstance(_emotions_raw, list):
                            for item in _emotions_raw:
                                if isinstance(item, dict) and "name" in item:
                                    _emotions[item["name"]] = item.get("intensity", 50)
                        elif isinstance(_emotions_raw, dict):
                            _emotions = _emotions_raw

                        # 获取分析内容
                        _analysis = soul_result.get("analysis", {}) if soul_result else {}
                        _inner_thought = (
                            (soul_result.get("inner_thought", "") if soul_result else "")
                            or _analysis.get("inner_thought", "")
                            or _analysis.get("reflection", "")
                        )
                        _attribution = (soul_result.get("attribution", "") if soul_result else "") or _analysis.get(
                            "attribution", ""
                        )
                        _reflection = (soul_result.get("reflection", "") if soul_result else "") or _analysis.get(
                            "reflection", ""
                        )
                        _dominant = soul_result.get("dominant_emotion", "未知") if soul_result else "未知"
                        _dominant = soul_result.get("dominant_emotion", "未知") if soul_result else "未知"

                        # 获取AI思考过程
                        _thinking = getattr(collab_result, "reasoning_content", "") or ""
                        if not _thinking and hasattr(collab_result, "thinking") and collab_result.thinking:
                            _thinking = collab_result.thinking

                        # B方案：存储情绪上下文到短期记忆
                        import json

                        from memory import store_auto

                        emotion_memory_content = (
                            f"【情绪记录】\n"
                            f"- 主导情绪: {_dominant}\n"
                            f"- 情绪池: {json.dumps(_emotions, ensure_ascii=False) if _emotions else '无'}\n"
                            f"- 内心独白: {_inner_thought}\n"
                            f"- 归因: {_attribution}\n"
                            f"- 反思: {_reflection}\n"
                            f"- AI思考过程: {_thinking[:200] if _thinking else '无'}"
                        )
                        try:
                            await store_auto(
                                emotion_memory_content,
                                user_id,
                                tags=["情绪记录", "emotion_context"],
                                priority=0.5,
                            )
                            logger.info("[灵魂记忆] 协作引擎已存储")
                        except Exception as store_err:
                            logger.warning(f"[灵魂记忆] store_auto失败: {store_err}")

                        # C方案：存入长期记忆，AI自行判断重要性
                        significant_emotions = [e for e, i in _emotions.items() if i >= 60]
                        if significant_emotions:
                            peak_content = f"【情绪记录】与佳互动时感到: {', '.join(significant_emotions)}"
                            await store_auto(
                                peak_content,
                                user_id,
                                tags=["#emotion_record", "#relation_history"],
                                priority=0.6,
                            )

                        # 【新增】协作引擎路径也存储认知记忆（使用之前提取的soul_result数据）
                        try:
                            from memory import store_cognition

                            # 获取AI思考过程 - 从协作引擎结果获取
                            collab_thinking = ""
                            if hasattr(collab_result, "thinking") and collab_result.thinking:
                                collab_thinking = collab_result.thinking
                            logger.debug(f"[协作引擎] thinking: {len(collab_thinking)} chars")

                            # 直接使用之前从soul_result提取的数据
                            group_id_str_cog = str(context.get("group_id")) if context.get("group_id") else None
                            await store_cognition(
                                thinking=collab_thinking,
                                emotions=_emotions,
                                inner_thought=_inner_thought,
                                attribution=_attribution,
                                reflection=_reflection,
                                user_id=str(user_id),
                                group_id=group_id_str_cog,
                            )
                            logger.debug("[协作引擎] 认知记忆存储完成")
                        except Exception as cog_err:
                            logger.warning(f"[认知记忆] 协作路径存储失败: {cog_err}")

                        # 存储到 decision_hub 供 SSE/API 读取（协作引擎路径）
                        self._last_soul_output = {
                            "emotions": _emotions or {},
                            "inner_thought": _inner_thought or "",
                            "attribution": _attribution or "",
                            "reflection": _reflection or "",
                            "thinking": _thinking or "",
                        }
                        logger.debug(
                            f"[SSE] _last_soul_output (collab): inner={bool(_inner_thought)}, emotions={list(_emotions.keys()) if _emotions else []}"
                        )

                        # 【LifeBook 集成】协作引擎路径也记录交互到多视角日记
                        try:
                            from memory.lifebook import get_lifebook

                            lifebook = get_lifebook()
                            response_text = collab_result.response
                            if lifebook and content and response_text:
                                emotion_label = "平静"
                                if soul_result:
                                    dominant = soul_result.get("dominant_emotion", "")
                                    if dominant and dominant != "未知":
                                        emotion_label = dominant
                                    else:
                                        emotions = soul_result.get("emotions", {})
                                        if isinstance(emotions, list) and emotions:
                                            emotion_label = (
                                                emotions[0].get("name", "平静")
                                                if isinstance(emotions[0], dict)
                                                else "平静"
                                            )
                                        elif isinstance(emotions, dict) and emotions:
                                            emotion_label = max(emotions, key=emotions.get) if emotions else "平静"
                                await lifebook.record_interaction(
                                    user_message=str(content),
                                    lover_response=response_text,
                                    topics=[message_type] if message_type else ["对话"],
                                    emotion=str(emotion_label),
                                )
                        except Exception as e:
                            logger.debug(f"[决策层-协作引擎] LifeBook 记录失败: {e}")

                        return collab_result.response

                    except Exception as e:
                        logger.info(f"[决策层-协作引擎] 协作失败，降级为单模型: {e}")
                        # 继续走原有单模型路径

            # 【优化】使用并行阶段预计算的 Soul Generator 结果
            _soul_result = soul_result  # 来自 Phase 2 并行计算
            ai_emotion_context = ""
            if _soul_result:
                dominant = _soul_result.get("dominant_emotion", "") or ""
                miya_emotions = _soul_result.get("emotions", {})
                # emotions 可能是 list[dict] 或 dict[str,int]，统一归一化
                if isinstance(miya_emotions, list):
                    emo_items = [
                        (e.get("name", ""), e.get("intensity", 0)) for e in miya_emotions if isinstance(e, dict)
                    ]
                elif isinstance(miya_emotions, dict):
                    emo_items = list(miya_emotions.items())
                else:
                    emo_items = []
                top_emotions = sorted(emo_items, key=lambda x: float(x[1] or 0), reverse=True)[:3]
                if top_emotions:
                    miya_dominant = top_emotions[0][0]
                    miya_intensity = top_emotions[0][1]
                    emotion_str_single = " + ".join([f"{name}({int(val)}%)" for name, val in top_emotions])
                else:
                    miya_dominant = "平静"
                    miya_intensity = 40
                    emotion_str_single = "平静"
                # 主导情绪：LLM 未输出 dominant_emotion 时，取情绪谱最高分
                if not dominant:
                    dominant = miya_dominant
                inner_thought = _soul_result.get("inner_thought", "") or _soul_result.get("analysis", {}).get(
                    "inner_thought", ""
                )
                attribution = _soul_result.get("attribution", "") or _soul_result.get("analysis", {}).get(
                    "attribution", ""
                )
                reflection = _soul_result.get("reflection", "") or _soul_result.get("analysis", {}).get(
                    "reflection", ""
                )

                eg = _get_emotion_guidance()
                ai_emotion_context = eg["header"]
                ai_emotion_context += eg["user_emotion"].format(dominant=dominant)
                ai_emotion_context += eg["miya_emotion"].format(
                    miya_dominant=miya_dominant, miya_intensity=miya_intensity, emotion_spectrum=emotion_str_single
                )
                if inner_thought:
                    ai_emotion_context += eg["inner_thought"].format(inner_thought=inner_thought)
                if attribution:
                    ai_emotion_context += eg["attribution"].format(attribution=attribution)
                if reflection:
                    ai_emotion_context += eg["reflection"].format(reflection=reflection)
                ai_emotion_context += eg["single_model_footer"]
                logger.info(f"[灵魂-单模型] 使用预计算结果: user_emotion={dominant}, miya={miya_dominant}")

            # 【增强】检索认知记忆 - 优先从缓存读取，更可靠
            cognition_context = ""
            try:
                # 方案1：优先从内存缓存读取（更快更可靠）
                from memory.cognition_cache import get_cognition_cache

                cache = get_cognition_cache()
                cache_context = await cache.get_context_for_ai(user_id, limit=2)

                if cache_context:
                    cognition_context = "\n" + cache_context
                    logger.info("[认知缓存] 从内存缓存读取成功")
                else:
                    # 方案2：回退到数据库检索
                    from memory import retrieve_cognition

                    recent_cognitions = await retrieve_cognition(user_id, limit=3)
                    if recent_cognitions:
                        cognition_parts = []
                        for cog in recent_cognitions:
                            if cog.get("thinking"):
                                cognition_parts.append(f"- 思考: {cog['thinking'][:150]}")
                            if cog.get("inner_thought"):
                                cognition_parts.append(f"- 想法: {cog['inner_thought'][:80]}")
                        if cognition_parts:
                            cognition_context = "\n【近期思维参考】\n" + "\n".join(cognition_parts[:3])
                            logger.info(f"[认知记忆] 从数据库检索 {len(recent_cognitions)} 条思维记录")
            except Exception as cog_err:
                logger.warning(f"[认知记忆] 检索失败: {cog_err}")

            # 调用 AI（注入情绪上下文 + 认知记忆）
            user_msg = prompt_info["user"]

            # 【关键修复】检测提醒/定时请求，强制在 system_prompt 末尾注入工具调用提示
            system_prompt_with_tool_hint = prompt_info["system"]
            if _is_reminder_request(content):
                has_create_task = any(
                    isinstance(t, dict) and t.get("function", {}).get("name") == "create_schedule_task"
                    for t in (tools_schema or [])
                )
                if has_create_task:
                    system_prompt_with_tool_hint = (
                        system_prompt_with_tool_hint
                        + "\n\n【重要】用户要求你设置提醒/定时任务。你必须立即调用 create_schedule_task 工具。"
                        + " 不调工具 = 失败，不要犹豫，现在就调。"
                    )

            if cognition_context:
                user_msg = user_msg + cognition_context
            if ai_emotion_context:
                user_msg = user_msg + ai_emotion_context
            response = await ai_client_to_use.chat_with_system_prompt(
                system_prompt=system_prompt_with_tool_hint,
                user_message=user_msg,
                tools=tools_schema if tools_schema else None,
                tool_choice=tool_choice,
            )

            # 【新增】存储情绪记忆 - 无论_soul_result是否有效都存储
            logger.info(f"[记忆存储] 检查存储: _soul_result={bool(_soul_result)}, user_id={user_id}")

            # 如果_soul_result为空，尝试从AI响应中提取情绪信息
            if not _soul_result:
                logger.warning("[灵魂记忆] _soul_result为空，跳过存储")
            else:
                # 处理emotions格式 - 支持list或dict
                _emotions_raw = _soul_result.get("emotions", []) if _soul_result else []
                _emotions = {}
                if isinstance(_emotions_raw, list):
                    for item in _emotions_raw:
                        if isinstance(item, dict) and "name" in item:
                            _emotions[item["name"]] = item.get("intensity", 50)
                elif isinstance(_emotions_raw, dict):
                    _emotions = _emotions_raw

                # 获取分析内容
                _analysis = _soul_result.get("analysis", {}) if _soul_result else {}
                _inner_thought = (
                    _soul_result.get("inner_thought", "")
                    or _analysis.get("inner_thought", "")
                    or _analysis.get("reflection", "")
                    or _analysis.get("reflection", "")
                )
                _attribution = _soul_result.get("attribution", "") or _analysis.get("attribution", "")
                _reflection = _soul_result.get("reflection", "") or _analysis.get("reflection", "")

                # 存储灵魂数据供 SSE 输出 (路径 A)
                self._last_soul_data = {
                    "emotions": _emotions.copy(),
                    "inner_thought": _inner_thought,
                    "attribution": _attribution,
                    "reflection": _reflection,
                }
                _dominant = _soul_result.get("dominant_emotion", "未知") if _soul_result else "未知"

                # 记录提取到的数据
                logger.info(
                    f"[灵魂记忆] 提取到: emotions={_emotions}, inner_thought={_inner_thought[:30]}, attribution={_attribution[:20]}"
                )

            # 获取AI思考过程
            thinking_content = ""
            if ai_client_to_use and hasattr(ai_client_to_use, "last_reasoning_content"):
                thinking_content = ai_client_to_use.last_reasoning_content or ""

            # B方案：存储情绪上下文到短期记忆（带 #emotion_context tag）
            if _soul_result:
                import json

                from memory import store_auto

                emotion_memory_content = (
                    f"【情绪记录】\n"
                    f"- 主导情绪: {_dominant}\n"
                    f"- 情绪池: {json.dumps(_emotions, ensure_ascii=False) if _emotions else '无'}\n"
                    f"- 内心独白: {_inner_thought}\n"
                    f"- 归因: {_attribution}\n"
                    f"- 反思: {_reflection}\n"
                    f"- AI思考过程: {thinking_content[:200] if thinking_content else '无'}"
                )

                # 使用 store_auto 存储，tag 使用不带#的格式（避免embedding问题）
                try:
                    await store_auto(
                        emotion_memory_content,
                        user_id,
                        tags=["情绪记录", "emotion_context"],
                        priority=0.5,
                    )
                    logger.info("[灵魂记忆] 已存储情绪上下文")
                except Exception as store_err:
                    logger.warning(f"[灵魂记忆] store_auto失败: {store_err}")

                # C方案：存入长期记忆，让AI自己判断重要性
                # 检测是否有显著的正面情绪（强度>=60）
                significant_emotions = [e for e, i in _emotions.items() if i >= 60]
                if significant_emotions:
                    peak_content = f"【情绪记录】与佳互动时感到: {', '.join(significant_emotions)}"
                    try:
                        await store_auto(
                            peak_content,
                            user_id,
                            tags=["情绪记录", "relation_history"],
                            priority=0.6,
                        )
                        logger.info(f"[灵魂记忆] 已存储情绪: {significant_emotions}")
                    except Exception as store_err2:
                        logger.warning(f"[灵魂记忆] 情绪峰值存储失败: {store_err2}")

            # 【LifeBook 集成】用真实情绪数据记录交互到多视角日记
            try:
                from memory.lifebook import get_lifebook

                lifebook = get_lifebook()
                user_msg_content = perception.get("content", "")
                if lifebook and user_msg_content and response:
                    emotion_label = "平静"
                    if _soul_result:
                        dominant = _soul_result.get("dominant_emotion", "")
                        if dominant and dominant != "未知":
                            emotion_label = dominant
                        else:
                            emotions = _soul_result.get("emotions", {})
                            if isinstance(emotions, list) and emotions:
                                emotion_label = (
                                    emotions[0].get("name", "平静") if isinstance(emotions[0], dict) else "平静"
                                )
                            elif isinstance(emotions, dict) and emotions:
                                emotion_label = max(emotions, key=emotions.get) if emotions else "平静"
                    await lifebook.record_interaction(
                        user_message=user_msg_content,
                        lover_response=response,
                        topics=[message_type] if message_type else ["对话"],
                        emotion=str(emotion_label),
                    )
            except Exception as e:
                logger.debug(f"[决策层] LifeBook 记录失败: {e}")

            # 【增强】存储认知记忆 - 思考过程、情绪分析、内心独白 + 缓存
            logger.debug(f"[认知记忆] 存储流程开始, _soul_result存在: {_soul_result is not None}")
            try:
                import uuid

                from memory import store_cognition
                from memory.cognition_cache import CognitionRecord, get_cognition_cache

                # 获取灵魂发生器的思考（情绪分析过程）
                soul_reasoning = ""
                _emotions = {}
                _inner_thought = ""
                _attribution = ""
                _reflection = ""

                logger.debug(f"[认知记忆] _soul_result keys: {_soul_result.keys()}")
                if _soul_result:
                    logger.debug(f"[认知记忆] inner_thought: {_soul_result.get('inner_thought', 'EMPTY')[:30]}")
                    logger.debug(f"[认知记忆] attribution: {_soul_result.get('attribution', 'EMPTY')[:20]}")
                    logger.debug(f"[认知记忆] reflection: {_soul_result.get('reflection', 'EMPTY')[:20]}")

                    soul_reasoning = _soul_result.get("reasoning", "")
                    logger.debug(f"[认知记忆] soul_reasoning: {soul_reasoning[:50] if soul_reasoning else 'empty'}")
                    # 处理emotions格式
                    _emotions_raw = _soul_result.get("emotions", [])
                    if isinstance(_emotions_raw, list):
                        for item in _emotions_raw:
                            if isinstance(item, dict) and "name" in item:
                                _emotions[item["name"]] = item.get("intensity", 50)
                    elif isinstance(_emotions_raw, dict):
                        _emotions = _emotions_raw
                    # 获取分析内容 - 优先从顶层获取
                    _analysis = _soul_result.get("analysis", {})
                    _inner_thought = _soul_result.get("inner_thought", "") or _analysis.get("inner_thought", "")
                    _attribution = _soul_result.get("attribution", "") or _analysis.get("attribution", "")
                    _reflection = _soul_result.get("reflection", "") or _analysis.get("reflection", "")

                    # 存储最后灵魂数据供 SSE 输出
                    self._last_soul_data = {
                        "emotions": {item["name"]: item["intensity"] for item in _emotions_raw}
                        if isinstance(_emotions_raw, list)
                        else _emotions,
                        "inner_thought": _inner_thought,
                        "attribution": _attribution,
                        "reflection": _reflection,
                    }
                    logger.debug(
                        f"[SSE] 已存储灵魂数据: emotions={list(self._last_soul_data['emotions'].keys())}, inner={_inner_thought[:20]}"
                    )

                # 获取AI客户端的思考（回复生成过程）
                ai_reasoning = ""
                if ai_client_to_use and hasattr(ai_client_to_use, "last_reasoning_content"):
                    ai_reasoning = ai_client_to_use.last_reasoning_content or ""

                # 存储思考过程供 SSE 输出
                if hasattr(self, "_last_soul_data") and self._last_soul_data:
                    self._last_soul_data["thinking"] = ai_reasoning[:800]

                # 合并两个思考过程
                thinking_content = ""
                if soul_reasoning and ai_reasoning:
                    thinking_content = f"[情绪分析] {soul_reasoning[:300]}\n\n[回复生成] {ai_reasoning[:500]}"
                elif soul_reasoning:
                    thinking_content = soul_reasoning[:500]
                elif ai_reasoning:
                    thinking_content = ai_reasoning[:500]
                elif collab_result and collab_result.thinking:
                    thinking_content = collab_result.thinking[:500]

                # 如果没有数据，至少记录回复内容
                if not thinking_content and response:
                    thinking_content = f"[回复内容片段] {response[:200]}"

                logger.debug(
                    f"[认知记忆] soul_reasoning={bool(soul_reasoning)}, ai_reasoning={bool(ai_reasoning)}, emotions={_emotions}, thinking={len(thinking_content)}"
                )

                # 存储到持久化存储
                group_id_str_tmp = str(context.get("group_id")) if context.get("group_id") else None
                memory_id = await store_cognition(
                    thinking=thinking_content,
                    emotions=_emotions,
                    inner_thought=_inner_thought,
                    attribution=_attribution,
                    reflection=_reflection,
                    user_id=user_id,
                    group_id=group_id_str_tmp,
                )
                logger.debug(
                    f"[认知记忆] 已存储 | 内心: {_inner_thought[:30]}... | 情绪: {_emotions} | 归因: {_attribution[:20]}..."
                )

                # 【新增】同时添加到内存缓存区
                cache = get_cognition_cache()
                cache_record = CognitionRecord(
                    id=memory_id or str(uuid.uuid4())[:8],
                    timestamp=datetime.now().timestamp(),
                    user_id=user_id,
                    thinking=thinking_content,
                    emotions=_emotions,
                    inner_thought=_inner_thought,
                    attribution=_attribution,
                    reflection=_reflection,
                    message_preview=content[:50] if content else "",
                )
                await cache.add(cache_record)
                logger.info("[认知缓存] 已添加到内存缓存区")
            except Exception as cog_err:
                logger.error(f"[认知记忆] 存储失败: {cog_err}", exc_info=True)

            # 存储到 decision_hub 供 SSE 读取（放在 try 外面确保一定执行）
            self._last_soul_output = {
                "emotions": _emotions or {},
                "inner_thought": _inner_thought or "",
                "attribution": _attribution or "",
                "reflection": _reflection or "",
                "thinking": thinking_content or "",
            }
            logger.debug(
                f"[SSE] _last_soul_output: inner={bool(_inner_thought)}, emotions={list(_emotions.keys()) if _emotions else []}"
            )

            # 【灵魂发生器】将情感注入到回复中 (已移除，使用Prompt引导)

            return response

        except Exception as e:
            logger.error(f"[决策层-跨平台] AI生成失败: {e}", exc_info=True)
            return await self._fallback_response_cross_platform(content, sender_name, platform)

    async def _fallback_response_cross_platform(self, content: str, sender_name: str, platform: str) -> str:
        """
        降级回复（跨平台）

        Args:
            content: 用户输入
            sender_name: 发送者名称
            platform: 平台类型

        Returns:
            回复文本
        """
        # 安全处理content参数 - 处理图片消息等非字符串情况
        if not isinstance(content, str):
            if isinstance(content, list):
                # 尝试从列表中提取文本（QQ图片消息格式）
                content_str = ""
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        if item_type == "text":
                            content_str += item.get("data", {}).get("text", "")
                        elif item_type == "image":
                            # 图片消息，添加标记
                            content_str += "[图片]"
                    elif isinstance(item, str):
                        content_str += item
                content = content_str if content_str else "[图片或其他非文本消息]"
            else:
                # 其他类型转换为字符串
                content = str(content)

        # 获取人格状态
        personality_profile = self.personality.get_profile()
        warmth = personality_profile["vectors"].get("warmth", 0.5)
        empathy = personality_profile["vectors"].get("empathy", 0.5)

        # 基于人格和平台生成响应
        from core.text_loader import (
            get_command_keywords,
            get_emotion_keywords,
            get_greeting,
            get_text,
            is_greeting,
        )

        # 获取名称（优先使用identity，否则使用配置中的默认值）
        name = get_text("personality_responses.name")
        if self.identity and hasattr(self.identity, "name"):
            name = self.identity.name
        from core.personality_config_loader import get_personality_config

        pconfig = get_personality_config()
        content.lower()
        emotion_keywords = get_emotion_keywords()

        if is_greeting(content):
            empathy_threshold = pconfig.get_response_threshold("greeting_empathy")
            warmth_threshold = pconfig.get_response_threshold("greeting_warmth")

            if empathy > empathy_threshold or warmth > warmth_threshold:
                return get_greeting(name, "hello")
            else:
                return get_greeting(name, "hello")

        who_are_keywords = emotion_keywords.get("who_are_you", [])
        if any(kw in content for kw in who_are_keywords):
            intro_template = get_text(
                "personality_responses.intro",
                "我是{name}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命伴侣。我的主导特质是同理心({empathy:.2f})和温暖度({warmth:.2f})。",
            )
            return intro_template.format(name=name, empathy=empathy, warmth=warmth)

        status_keywords = get_command_keywords().get("status", ["状态", "查看状态"])
        if any(kw in content for kw in status_keywords):
            emotion_state = self.emotion.get_emotion_state()
            existential_state = (
                self.emotion.get_existential_state() if hasattr(self.emotion, "get_existential_state") else {}
            )
            memory_stats = self.memory_engine.get_memory_stats() if self.memory_engine else {}
            profile = self.personality.get_profile()

            # 构建状态信息
            from core.text_loader import get_form_name

            form_key = profile.get("current_form", "normal")
            form_display = get_form_name(form_key)

            lines = [
                f"【{name}状态】",
                f"形态: {form_key} ({form_display})",
                f"情绪: {emotion_state['dominant']} (强度: {emotion_state['intensity']:.2f})",
                f"记忆: {memory_stats.get('tide_count', 0)}条",
            ]

            # 添加核心特质（如果有七重特质系统）
            if "vectors" in profile and "awake" in profile["vectors"]:
                lines.append("")
                lines.append("【七重特质】")
                lines.append(f"  清醒: {profile['vectors'].get('awake', 0):.2f}")
                lines.append(
                    f"  说话: {profile['vectors'].get('speak', 0):.2f} [{profile.get('speak_mode', 'casual')}]"
                )
                lines.append(f"  记住: {profile['vectors'].get('remember', 0):.2f}")
                lines.append(f"  等: {profile['vectors'].get('wait', 0):.2f}")
                lines.append(f"  疼: {profile['vectors'].get('pain', 0):.2f}")
                lines.append(f"  怕: {profile['vectors'].get('fear', 0):.2f}")
                lines.append(f"  押: {profile['vectors'].get('commit', 0):.2f}")

            # 添加核心形态（如果有）
            if profile.get("current_core_form"):
                lines.append(f"核心形态: {profile['current_core_form']}")

            # 添加存在性情感
            if existential_state:
                from core.text_loader import get_existential_display

                lines.append("")
                lines.append(get_existential_display("header").strip())
                dom_exist = existential_state.get("dominant", "unknown")
                lines.append(get_existential_display("dominant", dominant=dom_exist))
                active = existential_state.get("active")
                if active:
                    lines.append(get_existential_display("active", active=active))

            return "\n".join(lines)

        happy_keywords = emotion_keywords.get("happy", [])
        if any(kw in content for kw in happy_keywords):
            self.emotion.apply_coloring("joy", 0.3)
            return get_text(
                "personality_responses.excited_response",
                "听起来你很开心呢！看到你快乐，我也感到很开心~",
            )

        sad_keywords = emotion_keywords.get("sad", [])
        if any(kw in content for kw in sad_keywords):
            self.emotion.apply_coloring("sadness", 0.4)
            return get_text("personality_responses.comforting_sad")

        if is_greeting(content):
            return get_text("personality_responses.help_request")

        command_keywords = get_command_keywords()
        form_cmds = command_keywords.get("form", [])
        speak_cmds = command_keywords.get("speak", [])
        exist_cmds = command_keywords.get("exist", [])

        form_prefixes = [cmd for cmd in form_cmds if cmd.startswith("/")]
        speak_prefixes = [cmd for cmd in speak_cmds if cmd.startswith("/")]
        exist_prefixes = [cmd for cmd in exist_cmds if cmd.startswith("/")]

        is_form_cmd = any(content.startswith(cmd) for cmd in form_prefixes)
        is_speak_cmd = any(content.startswith(cmd) for cmd in speak_prefixes)
        is_exist_cmd = any(content.startswith(cmd) for cmd in exist_prefixes)

        if is_form_cmd:
            from core.personality_command_config import (
                format_core_forms_list,
                format_forms_list,
            )
            from core.text_loader import get_form_display, get_form_name

            cmd = content
            for c in form_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                # 显示当前形态
                profile = self.personality.get_profile()
                current_form = profile.get("current_form", "normal")
                form_name = get_form_name(current_form)
                form_info = profile.get("form_info", {})

                available_forms = format_forms_list()
                available_cores = format_core_forms_list()

                lines = [
                    get_form_display("current", form=form_name),
                    get_form_display("name", name=form_info.get("name", "常态")),
                    get_form_display("description", desc=form_info.get("description", "")),
                ]
                if profile.get("current_core_form"):
                    core_info = profile.get("core_form_info", {})
                    lines.append(get_form_display("core", core=profile["current_core_form"]))
                    lines.append(get_form_display("core_description", desc=core_info.get("description", "")))
                lines.append("")
                lines.append(get_form_display("available", forms=available_forms))
                lines.append(get_form_display("available_core", cores=available_cores))
                return "\n".join(lines)

        elif is_speak_cmd:
            from core.personality_command_config import get_personality_command_config

            pcmd = get_personality_command_config()

            cmd = content
            for c in speak_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                current_mode = self.personality.get_speak_mode()
                from core.text_loader import get_speak_mode_response

                return get_speak_mode_response(
                    "current_mode",
                    mode=current_mode,
                    available_modes=pcmd.format_speak_modes(),
                )

            valid_modes = pcmd.get_speak_modes()
            if cmd in valid_modes:
                success = self.personality.set_speak_mode(cmd)
                if success:
                    from core.text_loader import get_speak_mode_response

                    return get_speak_mode_response("switch_success", mode=cmd)
                return get_text("default_responses.switch_failed")
            from core.text_loader import get_speak_mode_response

            return get_speak_mode_response("unknown_mode", mode=cmd, available_modes=pcmd.format_speak_modes())

        elif is_exist_cmd:
            from core.personality_command_config import get_personality_command_config

            pcmd = get_personality_command_config()

            cmd = content
            for c in exist_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                state = self.emotion.get_existential_state() if hasattr(self.emotion, "get_existential_state") else {}
                if state:
                    from core.text_loader import get_existential_response

                    lines = [get_existential_response("header")]
                    for k, v in state.get("emotions", {}).items():
                        lines.append(f"  {k}: {v:.2f}")
                    if state.get("active"):
                        lines.append(get_existential_response("active", active=state["active"]))
                    return "\n".join(lines)
                return get_text("default_responses.no_existential_data")

            valid_exists = pcmd.get_core_forms()
            if cmd in valid_exists:
                success = (
                    self.emotion.activate_existential(cmd) if hasattr(self.emotion, "activate_existential") else False
                )
                if success:
                    from core.text_loader import get_existential_response

                    return get_existential_response("activated", emotion=cmd)
                return get_text("default_responses.activate_failed")
            from core.text_loader import get_existential_response

            return get_existential_response("unknown_emotion", emotion=cmd)

        else:
            # 智能响应 - 基于人格特质
            from core.personality_config_loader import get_personality_config
            from core.text_loader import get_text

            pconfig = get_personality_config()
            deep_conv_threshold = pconfig.get_response_threshold("deep_conversation_empathy")
            help_threshold = pconfig.get_response_threshold("help_warmth")

            if empathy > deep_conv_threshold and warmth > help_threshold:
                return get_text("personality_responses.deep_conversation")
            elif warmth > help_threshold:
                return get_text("personality_responses.normal_response")
            else:
                return get_text("personality_responses.simple_response")

    def _get_platform_tools(self, platform: str) -> list:
        """
        获取平台可用工具

        Args:
            platform: 平台类型

        Returns:
            工具列表
        """
        return self.platform_tools_manager.get_platform_tools(platform)

    # ========== 高级编排器支持 ==========

    async def process_complex_task(self, goal: str, context: dict | None = None) -> str:
        """
        处理复杂任务（使用高级编排器）

        流程：
        1. 使用思维链分析目标
        2. 分解为子任务
        3. 如果需要，进行主动探索
        4. 执行任务
        5. 反思和总结

        Args:
            goal: 任务目标
            context: 上下文信息

        Returns:
            执行结果或错误信息
        """
        orchestrator = self._get_advanced_orchestrator()
        if not orchestrator:
            from core.text_loader import get_advanced_response

            return get_advanced_response("orchestrator_not_initialized")

        logger.info(f"[决策层-高级编排] 开始处理复杂任务: {goal}")

        try:
            # 构建上下文
            if context is None:
                context = {}

            # 添加弥娅的状态信息到上下文
            if self.identity and hasattr(self.identity, "name"):
                context["bot_name"] = self.identity.name

            if self.memory_engine:
                context["memory_stats"] = self.memory_engine.get_memory_stats()

            # 调用高级编排器
            result = await orchestrator.process_complex_task(
                goal=goal, context=context, enable_exploration=True, enable_cot=True
            )

            # 生成简洁的摘要返回给用户
            summary = self._format_complex_task_result(result)

            logger.info(f"[决策层-高级编排] 复杂任务处理完成: {'成功' if result['success'] else '失败'}")

            return summary

        except Exception as e:
            logger.error(f"[决策层-高级编排] 处理复杂任务失败: {e}", exc_info=True)
            from core.text_loader import get_text

            return get_text("error_messages.task_failed", "任务执行失败: {error}").format(error=str(e))

    def _format_complex_task_result(self, result: dict) -> str:
        """
        格式化复杂任务执行结果

        Args:
            result: 执行结果字典

        Returns:
            格式化的字符串
        """
        from core.text_loader import get_advanced_response

        lines = [
            get_advanced_response("task_completed", conclusion=result.get("conclusion", "执行完成")),
            get_advanced_response("execution_time", time=result.get("execution_time", 0)),
            get_advanced_response("steps_completed", count=len(result.get("steps", []))),
            get_advanced_response("findings_count", count=len(result.get("findings", []))),
        ]

        # 添加主要发现
        findings = result.get("findings", [])
        if findings:
            lines.append("")
            lines.append("主要发现：")
            for finding in findings[:5]:  # 最多显示5条
                lines.append(f"  • {finding}")

        # 添加反思建议
        reflection = result.get("reflection", {})
        if reflection.get("improvements"):
            lines.append("")
            lines.append("改进建议：")
            for improvement in reflection["improvements"][:3]:  # 最多显示3条
                lines.append(f"  • {improvement}")

        return "\n".join(lines)

    # ========== 会话结束处理 ==========

    async def handle_session_end(self, session_id: str, platform: str = "terminal") -> dict:
        """
        处理会话结束，使用 SessionManager 保存对话历史到 LifeBook

        Args:
            session_id: 会话ID
            platform: 平台类型 (默认 'terminal')

        Returns:
            处理结果字典
        """
        return await self.session_handler.handle_session_end(
            session_id=session_id, platform=platform, memory_net=self.memory_net
        )

    # ========== 日记提醒功能 ==========

    async def set_diary_reminder(self, user_id: str, time: str = "21:00") -> dict:
        """
        设置日记提醒

        Args:
            user_id: 用户ID
            time: 提醒时间（格式：HH:MM，默认 21:00）

        Returns:
            设置结果
        """
        return await self.session_handler.set_diary_reminder(user_id, time)

    async def _detect_and_process_timer_task(
        self,
        perception: dict,
        platform: str,
        content: str,
        user_id: str,
        sender_name: str,
    ) -> str | None:
        """
        检测并处理定时任务请求

        Args:
            perception: 感知数据
            platform: 平台类型
            content: 用户输入内容
            user_id: 用户ID
            sender_name: 发送者名称

        Returns:
            如果检测到定时任务并处理成功，返回响应文本；否则返回None
        """
        import re

        logger.debug(f"[决策层-定时任务] 开始检测: 平台={platform}, 用户={user_id}, 内容='{content}'")

        # 检测定时任务关键词
        timer_keywords = [
            "提醒我",
            "叫我",
            "定时",
            "一分钟后",
            "五分钟后",
            "十分钟后",
            "小时后",
            "分钟后",  # 保留"分钟后"来识别具体时间
        ]
        has_timer_keyword = any(keyword in content for keyword in timer_keywords)

        if not has_timer_keyword:
            logger.debug(f"[决策层-定时任务] 未检测到定时任务关键词: '{content}'")
            return None

        logger.info(f"[决策层-定时任务] 检测到定时任务请求: '{content}' (用户: {user_id}, 平台: {platform})")

        # 如果ToolNet子网不可用，返回提示
        if not self.tool_subnet:
            logger.warning("[决策层-定时任务] ToolNet子网未初始化，无法创建定时任务")
            from core.text_loader import get_error_message

            return get_error_message("schedule_unavailable")

        logger.info("[决策层-定时任务] ToolNet子网可用，准备创建定时任务")

        try:
            # 解析时间
            scheduled_time = ""

            # 检测相对时间（如"一分钟后"、"五分钟后"）
            if "分钟后" in content:
                match = re.search(r"(\d+)\s*分钟", content)
                if match:
                    minutes = int(match.group(1))
                    scheduled_time = f"{minutes}分钟后"

            # 如果没有解析到具体分钟数，尝试其他格式
            elif "分钟后" in content:
                # 处理中文数字
                chinese_numbers = {
                    "一": 1,
                    "二": 2,
                    "三": 3,
                    "四": 4,
                    "五": 5,
                    "六": 6,
                    "七": 7,
                    "八": 8,
                    "九": 9,
                    "十": 10,
                }
                for cn, num in chinese_numbers.items():
                    if f"{cn}分钟后" in content:
                        scheduled_time = f"{num}分钟后"
                        break

            # 如果仍未解析到时间，使用默认的1分钟
            if not scheduled_time:
                scheduled_time = "1分钟后"

            # 检测任务类型
            task_type = "reminder"  # 默认提醒类型

            # 检测点赞请求
            if "点赞" in content or "点个赞" in content:
                task_type = "action"
                action_type = "qq_like"
                times = 1

                # 构建任务参数
                task_args = {
                    "task_type": task_type,
                    "target_type": "private" if MiyaPlatform.is_qq(platform) else "group",
                    "target_id": int(user_id)
                    if isinstance(user_id, str) and user_id.isdigit()
                    else (user_id if isinstance(user_id, int) else 0),
                    "schedule_time": scheduled_time,
                    "repeat": "once",
                    "priority": 5,
                    "action_type": action_type,
                    "times": times,
                }

                # 确保 user_id 格式正确（统一变量名）
                uid = (
                    int(user_id)
                    if isinstance(user_id, (int, str)) and str(user_id).isdigit()
                    else (int(user_id) if isinstance(user_id, int) else 0)
                )
            else:
                # 提醒任务
                from core.text_loader import get_reminder_message

                # 确保 user_id 是正确的类型
                uid = (
                    int(user_id)
                    if isinstance(user_id, (int, str)) and str(user_id).isdigit()
                    else (int(user_id) if isinstance(user_id, int) else 0)
                )

                task_args = {
                    "task_type": task_type,
                    "target_type": "private" if MiyaPlatform.is_qq(platform) else "group",
                    "target_id": uid,
                    "message": get_reminder_message(content),
                    "schedule_time": scheduled_time,
                    "repeat": "once",
                    "priority": 5,
                }

            # 调用ToolNet创建定时任务
            result = await self.tool_subnet.execute_tool(
                tool_name="create_schedule_task",
                args=task_args,
                user_id=uid,
                group_id=perception.get("group_id", 0),
                message_type=perception.get("message_type", "private"),
                sender_name=sender_name,
            )

            logger.info(f"[决策层-定时任务] 定时任务创建结果: {result[:100]}...")

            # 格式化响应
            from core.text_loader import get_schedule_response

            success = "已创建" in result or "任务ID" in result or "✅" in result
            return get_schedule_response(success, result)

        except Exception as e:
            logger.error(f"[决策层-定时任务] 处理定时任务失败: {e}", exc_info=True)
            from core.text_loader import get_error_message

            return get_error_message("schedule_error").format(error=str(e))

    async def _detect_and_process_emoji_request(
        self,
        perception: dict,
        platform: str,
        content: str,
        user_id: str,
        sender_name: str,
    ) -> str | None:
        """
        检测并处理表情包请求

        Args:
            perception: 感知数据
            platform: 平台类型
            content: 用户输入内容
            user_id: 用户ID
            sender_name: 发送者名称

        Returns:
            如果检测到表情包请求并处理成功，返回响应文本；否则返回None
        """
        logger.debug(f"[决策层-表情包] 开始检测: 平台={platform}, 用户={user_id}, 内容='{content}'")

        # 检测表情包请求关键词
        emoji_keywords = [
            "表情包",
            "表情",
            "发送表情",
            "来点表情",
            "给我表情",
            "发个表情",
            "发张表情",
            "发个图",
            "发张图",
            "来张图",
            "发图片",
            "发照片",
        ]
        has_emoji_keyword = any(keyword in content for keyword in emoji_keywords)

        # 检测特定表情包请求（如"发送开心表情"）
        import re

        specific_emoji_pattern = r"(发送|来一张|给我)(.*?)(表情|表情包|图)"
        specific_match = re.search(specific_emoji_pattern, content)

        if not has_emoji_keyword and not specific_match:
            logger.debug(f"[决策层-表情包] 未检测到表情包请求关键词: '{content}'")
            return None

        logger.info(f"[决策层-表情包] 检测到表情包请求: '{content}' (用户: {user_id}, 平台: {platform})")

        # 提取具体表情包名称（如果有）
        emoji_name = None
        if specific_match:
            emoji_name = specific_match.group(2).strip()
            logger.info(f"[决策层-表情包] 提取到具体表情包名称: '{emoji_name}'")

        try:
            # 根据平台类型处理表情包请求
            if MiyaPlatform.is_qq(platform):
                # QQ平台，需要特殊处理

                # 查找消息处理器实例
                qq_handler = None
                if hasattr(self, "qq_net") and self.qq_net and hasattr(self.qq_net, "message_handler"):
                    qq_handler = self.qq_net.message_handler

                if not qq_handler:
                    logger.warning("[决策层-表情包] 未找到QQ消息处理器，尝试通过工具调用")
                    return await self._process_emoji_via_tools(
                        perception, platform, content, user_id, sender_name, emoji_name
                    )

                # 获取群组ID和消息类型
                group_id = perception.get("group_id", 0)
                message_type = perception.get("message_type", "private")

                logger.info(
                    f"[决策层-表情包] QQ平台处理表情包请求: group_id={group_id}, message_type={message_type}, emoji_name='{emoji_name}'"
                )

                # 调用消息处理器的表情包发送方法
                from core.text_loader import get_emoji_sending_response

                if message_type == "group" and group_id > 0:
                    # 群聊
                    if hasattr(qq_handler, "_send_emoji_response"):
                        success = await qq_handler._send_emoji_response(
                            group_id, int(user_id) if user_id.isdigit() else 0
                        )
                        return get_emoji_sending_response(success)
                    else:
                        logger.error("[决策层-表情包] QQ消息处理器没有表情包发送方法")
                else:
                    # 私聊
                    if hasattr(qq_handler, "_send_emoji_response"):
                        success = await qq_handler._send_emoji_response(0, int(user_id) if user_id.isdigit() else 0)
                        return get_emoji_sending_response(success)

            # 其他平台或通过工具调用
            return await self._process_emoji_via_tools(perception, platform, content, user_id, sender_name, emoji_name)

        except Exception as e:
            logger.error(f"[决策层-表情包] 处理表情包请求失败: {e}", exc_info=True)
            return get_text("emoji_responses.error").format(error=str(e))

    async def _process_emoji_via_tools(
        self,
        perception: dict,
        platform: str,
        content: str,
        user_id: str,
        sender_name: str,
        emoji_name: str = None,
    ) -> str:
        """
        通过ToolNet工具处理表情包请求

        Args:
            perception: 感知数据
            platform: 平台类型
            content: 用户输入内容
            user_id: 用户ID
            sender_name: 发送者名称
            emoji_name: 表情包名称（可选）

        Returns:
            处理结果文本
        """
        logger.info(
            f"[决策层-表情包-工具] 通过工具处理表情包请求: 平台={platform}, 用户={user_id}, 表情包名称='{emoji_name}'"
        )

        # 如果ToolNet子网不可用，返回提示
        if not self.tool_subnet:
            logger.warning("[决策层-表情包-工具] ToolNet子网不可用")
            from core.text_loader import get_error_message

            return get_error_message("emoji_unavailable")

        try:
            # 准备工具参数
            tool_args = {
                "platform": platform,
                "user_id": user_id,
                "emoji_name": emoji_name if emoji_name else "",
                "context": content,
            }

            # 如果是QQ平台，添加额外信息
            if MiyaPlatform.is_qq(platform):
                tool_args.update(
                    {
                        "group_id": perception.get("group_id", 0),
                        "message_type": perception.get("message_type", "private"),
                    }
                )

            # 调用ToolNet的表情包工具
            result = await self.tool_subnet.execute_tool(
                tool_name="send_emoji",
                args=tool_args,
                user_id=int(user_id)
                if isinstance(user_id, str) and user_id.isdigit()
                else (user_id if isinstance(user_id, int) else 0),
                group_id=perception.get("group_id", 0),
                message_type=perception.get("message_type", "private"),
                sender_name=sender_name,
                at_list=perception.get("at_list", []),
            )

            logger.info(f"[决策层-表情包-工具] 表情包工具调用结果: {result[:100]}...")

            # 格式化响应
            from core.text_loader import get_emoji_fallback_response, get_error_message

            if "已发送" in result or "发送成功" in result or "表情包" in result:
                return result
            else:
                # 如果工具调用失败，提供友好的回退响应
                if emoji_name:
                    return get_emoji_fallback_response(emoji_name)
                else:
                    return get_emoji_fallback_response("")

        except Exception as e:
            logger.error(f"[决策层-表情包-工具] 通过工具处理表情包请求失败: {e}", exc_info=True)
            return get_error_message("emoji_unavailable")

    async def _handle_quick_commands(
        self, content: str, platform: str, perception: Optional[Dict] = None
    ) -> Optional[str]:
        """
        快速命令处理（在AI调用之前拦截）

        Args:
            content: 用户输入
            platform: 平台类型
            perception: 感知数据（包含用户ID、群ID等信息）

        Returns:
            如果是快速命令，返回响应；否则返回None让AI处理
        """
        if not self.personality:
            logger.warning("[决策层] personality为空，无法处理快捷命令")
            return None

        content_lower = content.lower().strip()
        content_preview = content[:300] + ("..." if len(content) > 300 else "")
        logger.info(f"[决策层] 处理命令: {content_preview}, personality: {type(self.personality)}")

        user_id = None
        if perception:
            user_id = perception.get("user_id") or perception.get("sender_id")
            _group_id = perception.get("group_id")

        def check_command_permission() -> bool:
            """检查命令执行权限 - 使用统一权限引擎 (v7.0 跨平台)"""
            if not perception:
                return True

            try:
                from core.unified_permission import get_permission_engine

                engine = get_permission_engine()

                cmd_config = engine._config.get("command_permissions", {})
                if not cmd_config.get("enabled", False):
                    return True

                plat = perception.get("platform", perception.get("source", ""))
                raw_uid = str(user_id) if user_id else ""
                unified_uid = perception.get("unified_user_id", "")

                # 优先用 unified_user_id 匹配
                check_id = unified_uid or raw_uid

                if engine.is_superadmin(check_id, platform=plat):
                    logger.info(f"[权限检查] {check_id} 是超级管理员，授权")
                    return True

                # fallback: raw user_id
                if unified_uid and unified_uid != raw_uid:
                    if engine.is_superadmin(raw_uid, platform=plat):
                        logger.info(f"[权限检查] {raw_uid} 是超级管理员，授权")
                        return True

                logger.warning(f"[权限检查] 用户 {check_id} 无权限执行命令")
                return False
            except Exception as e:
                logger.warning(f"[权限检查异常] {e}，拒绝执行")
                return False
            except Exception as e:
                logger.warning(f"[权限检查异常] {e}，拒绝执行")
                return False
            except Exception as e:
                logger.warning(f"[权限检查异常] {e}，拒绝执行")
                return False

        def get_permission_denied_message() -> str:
            """获取权限不足消息"""
            from core.text_loader import get_permission, get_text

            denied_msg = get_permission("command_permissions.denied_message", "")
            if denied_msg:
                roles_text = (
                    get_permission("role_names.superadmin", "超级管理员")
                    + "、"
                    + get_permission("role_names.group_owner", "群主")
                    + "、"
                    + get_permission("role_names.group_admin", "群管理员")
                )
                return denied_msg.replace("{roles}", roles_text)
            return get_text("error_messages.permission_denied")

        from core.text_loader import get_command_keywords

        command_keywords = get_command_keywords()
        form_cmds = command_keywords.get("form", ["/形态", "/form"])
        speak_cmds = command_keywords.get("speak", ["/说话", "/speak"])
        exist_cmds = command_keywords.get("exist", ["/存在", "/exist"])
        voice_cmds = command_keywords.get("voice", ["/语音", "/voice"])
        text_cmds = command_keywords.get("text", ["/文本", "/text"])
        local_playback_cmds = command_keywords.get("local_playback", ["/本地播放", "/localplay"])
        tts_engine_cmds = command_keywords.get("tts_engine", ["/tts", "/TTS"])

        form_prefixes = [cmd for cmd in form_cmds if cmd.startswith("/")]
        speak_prefixes = [cmd for cmd in speak_cmds if cmd.startswith("/")]
        exist_prefixes = [cmd for cmd in exist_cmds if cmd.startswith("/")]
        [cmd for cmd in voice_cmds if cmd.startswith("/")]
        [cmd for cmd in text_cmds if cmd.startswith("/")]
        [cmd for cmd in local_playback_cmds if cmd.startswith("/")]

        is_form_cmd = any(content_lower.startswith(cmd) for cmd in form_prefixes)
        is_speak_cmd = any(content_lower.startswith(cmd) for cmd in speak_prefixes)
        is_exist_cmd = any(content_lower.startswith(cmd) for cmd in exist_prefixes)
        is_voice_cmd = any(content_lower.strip() == cmd for cmd in voice_cmds)
        is_text_cmd = any(content_lower.strip() == cmd for cmd in text_cmds)
        is_local_playback_cmd = any(content_lower.strip() == cmd for cmd in local_playback_cmds)
        is_tts_engine_cmd = any(
            content_lower.startswith(cmd + " ") or content_lower.strip() == cmd for cmd in tts_engine_cmds
        )

        status_cmds = command_keywords.get("status", [])
        is_status_cmd = content_lower in status_cmds

        # 1. 状态查询命令
        if is_status_cmd:
            logger.info(f"[决策层] 捕获状态命令: {content}")
            if not check_command_permission():
                return get_permission_denied_message()
            from core.text_loader import get_form_name, get_status_response

            profile = self.personality.get_profile()

            current_form = profile.get("current_form", "normal")
            form_name = get_form_name(current_form)

            lines = [
                get_status_response("header").strip(),
                get_status_response("form", form=form_name),
            ]

            if "vectors" in profile:
                lines.append(get_status_response("vectors_header").strip())
                lines.append(get_status_response("awake", value=profile["vectors"].get("awake", 0)))
                lines.append(
                    get_status_response(
                        "speak",
                        value=profile["vectors"].get("speak", 0),
                        mode=profile.get("speak_mode", "casual"),
                    )
                )
                lines.append(get_status_response("remember", value=profile["vectors"].get("remember", 0)))
                lines.append(get_status_response("wait", value=profile["vectors"].get("wait", 0)))
                lines.append(get_status_response("pain", value=profile["vectors"].get("pain", 0)))
                lines.append(get_status_response("fear", value=profile["vectors"].get("fear", 0)))
                lines.append(get_status_response("commit", value=profile["vectors"].get("commit", 0)))

            return "\n".join(lines)

        # 2. 形态切换命令
        if is_form_cmd:
            if not check_command_permission():
                return get_permission_denied_message()
            from core.personality import Personality
            from core.personality_command_config import (
                format_core_forms_list,
                format_forms_list,
            )
            from core.text_loader import (
                get_form_display,
                get_form_name,
                get_form_response,
                get_text,
            )

            cmd = content
            for c in form_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                profile = self.personality.get_profile()
                current_form = profile.get("current_form", "normal")
                form_name = get_form_name(current_form)
                form_info = profile.get("form_info", {})

                lines = [
                    get_form_display("current", form=form_name),
                    get_form_display("name", name=form_info.get("name", "常态")),
                    get_form_display("description", desc=form_info.get("description", "")),
                ]
                if profile.get("current_core_form"):
                    core_info = profile.get("core_form_info", {})
                    lines.append(get_form_display("core", core=profile["current_core_form"]))
                    lines.append(get_form_display("core_description", desc=core_info.get("description", "")))
                lines.append("")
                lines.append(get_form_display("available", forms=format_forms_list()))
                lines.append(get_form_display("available_core", cores=format_core_forms_list()))
                return "\n".join(lines)

            if self.personality._use_yaml and self.personality._loader:
                available_forms = self.personality._loader.list_available()
                if cmd in available_forms:
                    success = self.personality.set_form_global(cmd)
                    return (
                        get_form_response("switch_success", form=cmd)
                        if success
                        else get_text("default_responses.switch_failed")
                    )
            else:
                from core.personality_command_config import get_available_forms

                available_forms = get_available_forms()
                if cmd in available_forms:
                    success = self.personality.set_form_global(cmd)
                    return (
                        get_form_response("switch_success", form=cmd)
                        if success
                        else get_text("default_responses.switch_failed")
                    )

            if cmd in self.personality._core_forms:
                success = self.personality.set_core_form(cmd)
                return (
                    get_form_response("switch_core_success", form=cmd)
                    if success
                    else get_text("default_responses.switch_failed")
                )
            return get_form_response("unknown_form", form=cmd)

        # 3. 说话模式命令
        if is_speak_cmd:
            if not check_command_permission():
                return get_permission_denied_message()
            from core.text_loader import get_speak_mode_response, get_text

            cmd = content
            for c in speak_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                current_mode = self.personality.get_speak_mode()
                return get_speak_mode_response("help", mode=current_mode)

            valid_modes = ["casual", "catching", "confiding"]
            if cmd in valid_modes:
                success = self.personality.set_speak_mode(cmd)
                return (
                    get_speak_mode_response("switch_success", mode=cmd)
                    if success
                    else get_text("default_responses.switch_failed")
                )
            return get_speak_mode_response(
                "unknown_mode",
                mode=cmd,
                available_modes="casual闲聊/catching捕捉/confiding倾诉",
            )

        # 4. 存在性情感命令
        if is_exist_cmd:
            if not check_command_permission():
                return get_permission_denied_message()
            from core.text_loader import get_existential_response

            cmd = content
            for c in exist_cmds:
                cmd = cmd.replace(c, "")
            cmd = cmd.strip().lower()
            if not cmd:
                return get_existential_response("help")
            return get_existential_response("unknown_emotion", emotion=cmd)

        # 4.5. TTS 语音/文本/本地播放/引擎切换 命令
        if is_voice_cmd or is_text_cmd or is_local_playback_cmd or is_tts_engine_cmd:
            return await self._handle_tts_commands(
                content,
                content_lower,
                is_voice_cmd,
                is_text_cmd,
                is_local_playback_cmd,
                is_tts_engine_cmd,
                tts_engine_cmds,
            )

        # 4.6. AI 唱歌命令（唱一下/点歌/唱歌 等）
        from core.singing.engine_router import (
            extract_song_name,
            handle_sing_request,
            is_sing_request,
        )

        if is_sing_request(content):
            logger.info(f"[决策层] 捕获唱歌命令: {content}")
            song_name = extract_song_name(content)
            if not song_name:
                from core.text_loader import get_singing_text

                return get_singing_text("no_song_name")
            username = (perception or {}).get("user_name", "") or (perception or {}).get("sender_name", "") or "亲爱的"
            return await handle_sing_request(song_name, username=username)

        # 4.7. AI 唱歌控制命令（切歌/歌单/停止）
        from core.text_loader import get_command_keywords, get_singing_text

        kw = get_command_keywords()
        skip_cmds = kw.get("sing_control_skip", [])
        list_cmds = kw.get("sing_control_list", [])
        stop_cmds = kw.get("sing_control_stop", [])

        is_skip_cmd = any(content_lower.startswith(c) for c in skip_cmds)
        is_list_cmd = any(content_lower.startswith(c) for c in list_cmds)
        is_stop_cmd = any(content_lower.startswith(c) for c in stop_cmds)

        if is_skip_cmd or is_list_cmd or is_stop_cmd:
            logger.info(f"[决策层] 捕获唱歌控制命令: {content}")
            from core.audio_player import get_audio_player
            from core.singing import get_singing_registry

            registry = get_singing_registry()
            wf = registry.workflow
            player = get_audio_player()
            if is_skip_cmd:
                if wf.is_singing or wf._playback_active:
                    player.stop()
                    wf.is_singing = False
                    return get_singing_text("skip_ok")
                return get_singing_text("skip_no_singing")
            elif is_list_cmd:
                songs = []
                if wf.current_song:
                    songs.append(get_singing_text("songlist_now", song_name=wf.current_song.song_name))
                for s in wf.play_queue:
                    songs.append(get_singing_text("songlist_queued", song_name=s.song_name))
                if not songs:
                    return get_singing_text("songlist_empty")
                return get_singing_text("songlist_header") + "\n" + "\n".join(songs)
            elif is_stop_cmd:
                if wf.is_singing or wf._playback_active or wf.play_queue:
                    player.stop()
                    wf.is_singing = False
                    wf.play_queue.clear()
                    return get_singing_text("stop_ok")
                return get_singing_text("stop_no_singing")

        # 5. 帮助命令已由统一斜杠命令系统接管（/help），此处不再处理

        # 6. 版本命令
        version_cmds = command_keywords.get("version", ["版本", "version", "ver"])
        if any(content_lower == kw for kw in version_cmds):
            return "弥娅 AI 虚拟化身系统 v6.0.0"

        # 7. 记忆命令 — 委托到 MemoryCommandHandler
        try:
            from webnet.qq.memory_commands import process_memory_command

            uid = str(user_id) if user_id else ""
            mem_result = await process_memory_command(content, uid)
            if mem_result:
                return mem_result
        except Exception as e:
            logger.debug(f"[决策层] 记忆命令处理跳过: {e}")

        # 8. 游戏陪玩命令
        game_play_cmds = command_keywords.get("game_play", ["/游戏", "/陪玩"])
        gp_prefixes = [cmd for cmd in game_play_cmds if cmd.startswith("/")]
        is_game_play_cmd = any(content_lower.startswith(cmd) for cmd in gp_prefixes)
        if is_game_play_cmd:
            if not check_command_permission():
                return get_permission_denied_message()
            arg = ""
            for p in gp_prefixes:
                if content_lower.startswith(p):
                    arg = content_lower[len(p) :].strip()
                    break
            return await self._handle_game_play_command(arg)

        # 不是快速命令
        return None

    async def _handle_game_play_command(self, arg: str) -> str:
        """处理游戏陪玩命令: /游戏 [游戏名|stop|状态]"""
        from core.game_play.engine import get_game_play_engine

        engine = get_game_play_engine()
        await engine.initialize()

        arg = arg.strip()

        # /游戏 stop / /陪玩 关
        if arg in ("stop", "关", "停", "关闭", "结束"):
            result = await engine.stop_game()
            return result.get("message", "已停止")

        # /游戏 状态
        if arg in ("状态", "status"):
            status = engine.get_status()
            if not status["active"]:
                return "游戏陪玩未启动。输入 /游戏 来启动~"
            lines = [
                f"当前模式: {status.get('game_name', '通用')}",
                f"截图次数: {status.get('screenshot_count', 0)}",
                f"语音: {'开' if status.get('voice_enabled') else '关'}",
                f"视觉: {'开' if status.get('vision_enabled') else '关'}",
            ]
            return "\n".join(lines)

        # 游戏名映射（支持 "游戏名" 或 "游戏名 auto"）
        auto_speak = False
        if arg.endswith(" auto") or arg.endswith(" -auto"):
            auto_speak = True
            arg = arg.replace(" auto", "").replace(" -auto", "").strip()
        elif arg == "auto":
            auto_speak = True
            arg = ""

        game_map = {
            "黑神话": "black_myth_wukong",
            "悟空": "black_myth_wukong",
            "黑神话悟空": "black_myth_wukong",
            "视觉小说": "visual_novel",
            "galgame": "visual_novel",
            "gal": "visual_novel",
            "adv": "visual_novel",
            "文字游戏": "visual_novel",
        }

        game_id = game_map.get(arg)

        result = await engine.start_game(game_id=game_id, auto_speak=auto_speak)
        msg = result.get("message", "已启动")
        if auto_speak:
            msg += " (自动模式：主动观察+TTS提醒)"
        return msg

    async def _handle_tts_commands(
        self,
        content: str,
        content_lower: str,
        is_voice: bool,
        is_text: bool,
        is_local_playback: bool,
        is_tts_engine: bool = False,
        tts_engine_cmds: list = None,
    ) -> str:
        """处理 TTS 语音/文本/本地播放/引擎切换 命令"""
        import json

        config_path = "config/tts_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}

        changed = False
        messages = []

        if is_voice:
            config["qq_default_mode"] = "voice"
            config["enabled"] = True
            changed = True
            engine = config.get("preferred_engine", "edge_tts")
            engine_names = {
                "edge_tts": "Edge TTS",
                "gpt_sovits": "GPT-SoVITS 遐蝶",
                "api_tts": "API 云端 TTS",
            }
            messages.append(f"已切换到语音模式 ({engine_names.get(engine, engine)})")
        elif is_text:
            config["qq_default_mode"] = "text"
            changed = True
            messages.append("已切换到文本模式，回复将以文字发送")
        elif is_local_playback:
            current = config.get("local_playback_enabled", False)
            config["local_playback_enabled"] = not current
            engine = config.get("preferred_engine", "edge_tts")
            config["local_playback_engine"] = engine
            changed = True
            if not current:
                messages.append(f"已开启本地电脑播放 ({engine})")
            else:
                messages.append("已关闭本地电脑播放")
        elif is_tts_engine and tts_engine_cmds:
            cmd = content_lower
            for c in tts_engine_cmds:
                cmd = cmd.replace(c.lower(), "")
            cmd = cmd.strip()

            engine_names = {
                "edge": "edge_tts",
                "sovits": "gpt_sovits",
                "api": "api_tts",
            }
            if not cmd or cmd in ("status", "状态"):
                current = config.get("preferred_engine", "edge_tts")
                display = {
                    "edge_tts": "Edge TTS (免费，微软晓晓)",
                    "gpt_sovits": "GPT-SoVITS (遐蝶音色，需本地服务)",
                    "api_tts": "API 云端 (OpenAI TTS)",
                }
                local_eng = config.get("local_playback_engine", current)
                save_audio = config.get("save_audio", False)
                save_dir = config.get("save_audio_dir", "data/tts_audio")
                lines = [
                    "【TTS 状态】",
                    "",
                    f"QQ 引擎: {display.get(current, current)}",
                    f"本地播放引擎: {display.get(local_eng, local_eng)}",
                    f"QQ 模式: {config.get('qq_default_mode', 'text')}",
                    f"本地播放: {'开' if config.get('local_playback_enabled') else '关'}",
                    f"音频存档: {'开' if save_audio else '关'} ({save_dir})",
                ]
                return "\n".join(lines)

            if cmd.startswith("save ") or cmd == "save":
                sub = cmd.replace("save ", "").replace("save", "").strip()
                if sub in ("on", "开"):
                    config["save_audio"] = True
                    changed = True
                    messages.append("音频存档已开启 → data/tts_audio/")
                elif sub in ("off", "关"):
                    config["save_audio"] = False
                    changed = True
                    messages.append("音频存档已关闭（播放后自动清理）")
                else:
                    return "用法: /tts save on|off"

            if messages:
                pass  # save 命令已处理
            else:
                engine_key = engine_names.get(cmd)
                if not engine_key:
                    return f"未知引擎: {cmd}。可用: edge / sovits / api / save / status"

                config["preferred_engine"] = engine_key
                changed = True

                # 切换引擎时自动开启语音模式
                config["qq_default_mode"] = "voice"
                config["enabled"] = True

                display = {
                    "edge_tts": "Edge TTS (免费)",
                    "gpt_sovits": "GPT-SoVITS 遐蝶",
                    "api_tts": "API 云端 TTS",
                }
                messages.append(f"TTS 引擎已切换: {display.get(engine_key, engine_key)}，已自动开启语音模式")

                if engine_key == "gpt_sovits":
                    messages.append("（需确保 GPT-SoVITS 已启动: http://127.0.0.1:9880）")
                elif engine_key == "api_tts":
                    key = config.get("engines", {}).get("api_tts", {}).get("api_key", "")
                    if not key:
                        messages.append("（⚠️ 未配置 API Key，请在 tts_config.json 中填写）")

        if changed:
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                logger.info(f"[决策层] TTS 配置已更新: {messages[0]}")
            except Exception as e:
                logger.error(f"[决策层] TTS 配置保存失败: {e}")
                return f"配置保存失败: {e}"

        try:
            if self.miya_instance:
                daemon = getattr(self.miya_instance, "daemon", None)
                if daemon and hasattr(daemon, "registry"):
                    for _pid, inst in daemon.registry._instances.items():
                        if hasattr(inst, "set_tts_mode"):
                            if is_voice:
                                inst.set_tts_mode("voice")
                            elif is_text:
                                inst.set_tts_mode("text")
        except Exception as e:
            logger.debug(f"[决策层] 运行时通知平台失败: {e}")

        return "\n".join(messages)

    def _append_qq_status_tag(self, response: str) -> str:
        """
        在QQ响应末尾附加弥娅状态标签

        Args:
            response: 原始响应

        Returns:
            附加状态标签后的响应
        """
        if not self.personality:
            return response

        try:
            profile = self.personality.get_profile()
            current_form = profile.get("current_form", "normal")
            speak_mode = profile.get("speak_mode", "casual")
            current_core = profile.get("current_core_form", "")

            # 构建状态标签 - 使用配置
            from core.text_loader import get_core_form_name, get_form_name

            form_name = get_form_name(current_form)
            core_name = get_core_form_name(current_core) if current_core else ""

            tag = f"\n\n[{form_name}|{speak_mode}|{core_name}]" if core_name else f"\n\n[{form_name}|{speak_mode}]"

            logger.debug(f"[决策层] 添加状态标签: {tag}")
            return response + tag
        except Exception as e:
            logger.debug(f"[决策层] 添加状态标签失败: {e}")
            return response

    def _load_agent_trigger_keywords(self) -> list:
        """从配置文件加载 Agent 触发关键词"""
        try:
            import json
            from pathlib import Path

            config_path = Path("config/agent_routing_config.json")
            if not config_path.exists():
                return []

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            routing = config.get("agent_routing", {})
            if not routing.get("enabled", True):
                return []

            rules = routing.get("routing_rules", {})
            keywords = []
            for _agent_name, rule in rules.items():
                keywords.extend(rule.get("keywords", []))

            logger.info(f"[决策层] 从配置加载触发关键词: {len(keywords)} 个")
            return keywords
        except Exception as e:
            logger.warning(f"[决策层] 加载触发关键词失败: {e}")
            return []

    async def _check_and_learn_image_correction(self, perception: dict, content: str, user_id, group_id):
        """使用 AI 检查用户是否在确认/纠正图片识别结果，并学习对应关系"""
        import logging
        import re

        logger = logging.getLogger(__name__)

        logger.debug(f"[AI学习] 检查纠正: {content[:30]}")

        # 检测用户是否在纠正（关键词检测）
        correction_keywords = ["是", "对的", "没错", "正确", "就是", "这个是", "错了"]
        has_correction = any(kw in content for kw in correction_keywords)

        # 提取可能的答案（优先引号，再次提取最后的角色名）
        answer = None
        answer_match = re.search(r"['\"](.+?)['\"]", content)
        if answer_match:
            answer = answer_match.group(1).strip()
        else:
            # 提取 "xxx里的xxx" 格式
            match2 = re.search(r"里的(.+?)(?:，|$)", content)
            if match2:
                answer = match2.group(1).strip()
            else:
                # 提取是/叫/为后面的内容
                match3 = re.search(r"(?:是|叫|为|的)(.+?)(?:，|啦|啊|的|$)", content)
                if match3:
                    answer = match3.group(1).strip()

        if not (has_correction and answer and len(answer) >= 2):
            logger.info("[AI学习] 非纠正内容，跳过")
            return

        answer = answer.strip()
        logger.info(f"[AI学习] 检测到纠正/确认，答案={answer}")

        # 保存到长期记忆
        try:
            from memory import store_important

            memory_id = await store_important(
                content=f"[AI学习] 用户纠正/确认: {answer}",
                user_id=str(user_id) if user_id else "unknown",
                tags=["ai_learn", "纠正学习"],
                priority=0.7,
                metadata={"learned_answer": answer},
            )
            logger.info(f"[AI学习] 学习完成，memory_id={memory_id}")
        except Exception as e:
            logger.warning(f"[AI学习] 保存失败: {e}")

    async def _check_and_learn_general_correction(self, perception: dict, content: str, user_id):
        """通用的确认/纠正学习框架 - 支持多种场景"""
        # 从配置文件加载
        from core.text_loader import get_text_loader

        loader = get_text_loader()
        config = loader._config

        correction_config = config.get("correction_learning", {})
        if not correction_config.get("enabled", True):
            return

        content_lower = content.lower().strip()

        # 获取所有场景配置
        scenarios = correction_config.get("scenarios", {})

        # 检测是否匹配任何纠正模式
        matched_scenario = None
        extracted_answer = None

        import re

        for scenario_name, scenario_config in scenarios.items():
            if scenario_name == "image":
                continue  # 图片学习单独处理

            patterns = scenario_config.get("patterns", [])
            if any(p in content_lower for p in patterns):
                matched_scenario = scenario_config

                # 尝试提取答案
                regex_patterns = scenario_config.get("regex_extract", [])
                for pattern in regex_patterns:
                    match = re.search(pattern, content)
                    if match:
                        extracted_answer = match.group(1).strip()[:100]
                        break

                break  # 找到第一个匹配的场景

        if not matched_scenario or not extracted_answer:
            return

        # 保存学习记录
        try:
            from memory import store_important

            learning_content = (
                f"[{matched_scenario['tags'][0]}] 用户纠正: {extracted_answer} | 原始消息: {content[:100]}"
            )

            await store_important(
                content=learning_content,
                user_id=str(user_id) if user_id else "unknown",
                tags=matched_scenario["tags"],
                priority=matched_scenario["priority"],
                metadata={
                    "learned_content": extracted_answer,
                    "scenario": matched_scenario["tags"][0],
                    "original_message": content[:200],
                },
            )
            logger.info(f"[决策层] 通用学习完成，场景: {matched_scenario['tags'][0]}, 内容: {extracted_answer}")
        except Exception as e:
            logger.warning(f"[决策层] 通用学习失败: {e}")
