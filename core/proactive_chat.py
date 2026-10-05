"""
弥娅主动聊天系统 v2.1 (完整版)
==========
支持：
- 关键词触发
- 时间触发（多时段问候）
- 上下文触发（行为期望跟进）
- 情绪感知触发
- 主动关怀
- AI触发

配置驱动，所有内容可自定义
"""

import asyncio
import contextlib
import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from pathlib import Path
from uuid import uuid4

from core.ai_client import AIMessage
from core.proactive_delivery import delivery_accepted

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """从 config/proactive_chat.yaml 加载主动聊天配置"""
    try:
        from pathlib import Path

        import yaml

        config_path = Path(__file__).parent.parent / "config" / "proactive_chat.yaml"

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            if raw_config and "proactive_chat" in raw_config:
                logger.info("[主动聊天] 从 config/proactive_chat.yaml 加载配置成功")
                return _normalize_config(raw_config["proactive_chat"])
            else:
                logger.warning("[主动聊天] config/proactive_chat.yaml 中无 proactive_chat 配置，使用默认配置")
                return get_default_config()
        else:
            logger.warning("[主动聊天] config/proactive_chat.yaml 不存在，使用默认配置")
            return get_default_config()
    except ImportError:
        logger.warning("[主动聊天] PyYAML 未安装，尝试从 _base.yaml 加载")
        try:
            from core.personality_loader import get_personality_loader

            loader = get_personality_loader()
            base_config = loader._load_base_config()
            raw_config = loader.get_proactive_chat_config(base_config)

            if raw_config:
                logger.info("[主动聊天] 从 _base.yaml 加载配置成功")
                return _normalize_config(raw_config)
            else:
                return get_default_config()
        except Exception as e:
            logger.warning(f"[主动聊天] 配置加载失败: {e}，使用默认配置")
            return get_default_config()
    except Exception as e:
        logger.warning(f"[主动聊天] 配置加载失败: {e}，使用默认配置")
        return get_default_config()


def _normalize_config(raw: dict) -> dict:
    """将 _base.yaml 的配置格式转换为代码期望的格式"""
    default = get_default_config()

    enabled = raw.get("enabled", default["enabled"])
    quiet_hours = raw.get("quiet_hours", default["limits"]["quiet_hours"])
    max_daily = raw.get("max_daily_messages", default["limits"]["max_daily_per_target"])
    # 这一段的三个限制以前被硬编码在下面，yaml 里怎么写都不生效（global_cooldown
    # 300 / duplicate_window 60 / quiet_hours_enabled True）。她是限频的最后一层，
    # 佳要能调，就必须真的读文件。
    limits_raw = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}

    # 上下文触发
    ctx_trigger = raw.get("context_trigger", {})
    expectations = {}
    raw_expectations = ctx_trigger.get("expectations", {})
    if raw_expectations:
        expectations["enabled"] = ctx_trigger.get("enabled", True)
        expectations["use_ai"] = ctx_trigger.get("use_ai", True)
        follow_responses = {}
        for key, responses in raw_expectations.items():
            follow_responses[key] = responses
        expectations["follow_responses"] = follow_responses
    else:
        expectations = default["triggers"]["context"]

    # 情绪感知
    emotion_perc = raw.get("emotion_perception", {})
    emotion_cfg = {
        "enabled": emotion_perc.get("enabled", default["triggers"]["emotion"]["enabled"]),
        "use_ai": emotion_perc.get("use_ai", True),
        "emotion_keywords": emotion_perc.get("emotion_keywords", {}),
        "emotion_responses": emotion_perc.get("emotion_responses", {}),
    }

    # 关键词触发
    kw_trigger = raw.get("keyword_trigger", {})
    keyword_cfg = {
        "enabled": kw_trigger.get("enabled", default["triggers"]["keyword"]["enabled"]),
        "use_ai": kw_trigger.get("use_ai", True),
        "keywords": kw_trigger.get("keywords", []),
        "responses": kw_trigger.get("responses", []),
    }

    # 主动关怀
    check_in = raw.get("check_in", {})
    check_in_cfg = {
        "enabled": check_in.get("enabled", default["triggers"]["check_in"]["enabled"]),
        "use_ai": check_in.get("use_ai", True),
        "check_interval": check_in.get("check_interval", 3600),
        "messages": check_in.get("messages", []),
    }

    # AI触发
    ai_trigger = raw.get("ai_trigger", {})
    ai_cfg = {
        "enabled": ai_trigger.get("enabled", default["triggers"]["ai"]["enabled"]),
        "cooldown": ai_trigger.get("cooldown", 300),
        "check_interval": ai_trigger.get("check_interval", 60),
        "max_per_hour": ai_trigger.get("max_per_hour", 3),
        "system_prompt": ai_trigger.get("system_prompt", ""),
    }

    # 时间感知
    time_aware = raw.get("time_awareness", {})
    greetings = {}
    if time_aware.get("enabled", True):
        time_slots = time_aware.get("time_slots", {})
        for slot_name, slot_data in time_slots.items():
            greetings[slot_name] = {
                "messages": [t for topic in slot_data.get("topics", []) for t in topic.get("templates", [])]
            }
    time_cfg = {
        "enabled": time_aware.get("enabled", default["triggers"]["time"]["enabled"]),
        "use_ai": time_aware.get("use_ai", True),
        "check_interval": raw.get("check_interval", 60),
        "greetings": greetings,
    }

    return {
        "enabled": enabled,
        "triggers": {
            "keyword": keyword_cfg,
            "time": time_cfg,
            "context": expectations,
            "emotion": emotion_cfg,
            "check_in": check_in_cfg,
            "ai": ai_cfg,
        },
        "limits": {
            "global_cooldown": limits_raw.get("global_cooldown", default["limits"]["global_cooldown"]),
            "max_daily_per_target": max_daily,
            "max_hourly_per_target": raw.get("max_hourly_messages", default["limits"]["max_hourly_per_target"]),
            "duplicate_window": limits_raw.get("duplicate_window", default["limits"]["duplicate_window"]),
            "quiet_hours": quiet_hours,
            "quiet_hours_enabled": limits_raw.get("quiet_hours_enabled", True),
        },
        "trigger_type_cooldown": raw.get("trigger_type_cooldown", {}),
        "user_message_cooldown": raw.get("user_message_cooldown", 5),
        "reply_cooldown": raw.get("reply_cooldown", 120),
        "check_interval": raw.get("check_interval", 45),
        "continuity_trigger": raw.get("continuity_trigger", {}),
        "scene": _normalize_scene_config(raw.get("scene_awareness", {})),
        "platform_routing": _normalize_platform_routing_config(raw.get("platform_routing", {})),
        "coordination": _normalize_coordination_config(raw.get("coordination", {})),
        # 感官触发：屏幕（弥娅之眼）与摄像头。以前这两段在这里被丢掉，
        # 导致 yaml 里的开关对运行中的系统完全无效。
        "screen_aware": _normalize_screen_aware_config(raw.get("screen_aware")),
        "camera_aware": _normalize_camera_aware_config(raw.get("camera_aware")),
    }


def _normalize_coordination_config(raw: dict) -> dict:
    """统一主动来源的总限频配置。

    这里必须把 yaml 里的键**原样带下去**。之前只重建了 5 个键，于是
    ``max_messages_per_source_per_hour``、``max_events_per_source_per_hour`` 和
    ``same_source_interval_seconds`` 被静默丢弃——配置里写了、注释里解释了为什么
    要这么设，协调器却一直用代码默认值（3/4/90）跑。三个默认值和 yaml 恰好接近，
    所以改 yaml 完全看不出没生效。
    """
    defaults = {
        "enabled": True,
        "max_messages_per_hour": 3,
        "max_messages_per_source_per_hour": 3,
        "max_events_per_source_per_hour": 4,
        "min_interval_seconds": 300,
        "same_source_interval_seconds": 90,
        "quiet_hours_enabled": True,
        "quiet_hours": [23, 0, 1, 2, 3, 4, 5, 6, 7],
    }
    merged = dict(defaults)
    for key in defaults:
        if key in raw and raw[key] is not None:
            merged[key] = raw[key]
    # Anything the coordinator learns to read should reach it without this
    # function needing to know about it first.
    for key, value in (raw or {}).items():
        merged.setdefault(key, value)
    return merged


def get_default_camera_aware_config() -> dict:
    """摄像头主动触发的默认配置（yaml 里缺项或整段缺失时使用）。

    与 ``config/proactive_chat.yaml`` 的 ``camera_aware`` 段一一对应，是唯一的
    默认值来源：``ProactiveChatSystem.__init__`` 与配置归一化共用它，避免两处
    各写一份默认值而慢慢走样。
    """
    return {
        "enabled": True,
        "min_interval": 90,
        "min_confidence": 0.62,
        "events": ["wave", "sit_down", "stand_up", "walk", "scene_change", "long_still"],
        # 在场判断：notify_on 支持 returned（刚回来）与 left（确认离开）
        # 这里**没有** min_interval：限频统一归协调器管（见 _check_presence_trigger
        # 的注释）。以前这里和 yaml 各留了一份 min_interval，两个值从头到尾没有
        # 任何代码读过——配置看起来在生效，其实只是装饰。
        "presence": {
            "enabled": True,
            "notify_on": ["returned"],
            "min_confidence": 0.5,
        },
        # 活动变化：notify_on 是声明性的，只说明"哪些变化算新闻"；真正决定要不要
        # 开口的是模型（_check_activity_trigger）。同样没有 min_interval。
        "activity": {
            "enabled": True,
            "notify_on": ["typing", "phone", "drink", "stretch", "walk", "sit_down", "stand_up", "lean_back"],
        },
        # 弥娅自主视觉：只决定"她攒下的话要不要投递"
        "agency": {
            "enabled": True,
            "max_age_seconds": 600,
        },
    }


def _normalize_camera_aware_config(raw: Any) -> dict:
    """把 yaml 的 camera_aware 段补全默认值后原样带下去。

    ``_normalize_config`` 以前用一张固定的键列表重建配置，把 ``camera_aware``
    （以及 ``screen_aware``）整段丢掉了：于是在 ``config/proactive_chat.yaml`` 里
    写的开关全部静默失效——presence / activity / agency 关不掉，
    ``agency.max_age_seconds`` 也改不动，一律落回代码里的硬编码默认值。
    """
    default = get_default_camera_aware_config()
    source = raw if isinstance(raw, dict) else {}
    merged = dict(default)
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            # 段内是部分配置时保留同段其余默认值，而不是整段覆盖
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _normalize_screen_aware_config(raw: Any) -> dict:
    """弥娅之眼（屏幕感知）开关与节奏。"""
    source = raw if isinstance(raw, dict) else {}
    return {
        "enabled": source.get("enabled", True),
        "min_interval": source.get("min_interval", 30),
        "max_daily_vision": source.get("max_daily_vision", 24),
    }


def _normalize_scene_config(raw: dict) -> dict:
    """归一化场景感知配置"""
    return {
        "enabled": raw.get("enabled", True),
        "platform_multipliers": raw.get("platform_multipliers", {}),
        "group_activity": raw.get("group_activity", {}),
        "mixed_strategy": raw.get("mixed_strategy", {}),
    }


def _normalize_platform_routing_config(raw: dict) -> dict:
    """归一化平台路由配置 (v8.1)"""
    return {
        "enabled": raw.get("enabled", True),
        "mode": raw.get("mode", "ai_aware"),
        "priority_ranking": raw.get("priority_ranking", {}),
        "ai_routing": {
            "enabled": raw.get("ai_routing", {}).get("enabled", True),
            "max_candidates": raw.get("ai_routing", {}).get("max_candidates", 5),
            "timeout_seconds": raw.get("ai_routing", {}).get("timeout_seconds", 3),
            "cache_ttl_seconds": raw.get("ai_routing", {}).get("cache_ttl_seconds", 30),
        },
    }


def get_default_config() -> dict:
    """默认配置（简化版）"""
    return {
        "enabled": True,
        "triggers": {
            "keyword": {
                "enabled": True,
                "use_ai": True,
                "keywords": [],
                "responses": [],
            },
            "time": {
                "enabled": True,
                "use_ai": True,
                "check_interval": 60,
                "greetings": {},
            },
            "context": {
                "enabled": True,
                "use_ai": True,
                "check_interval": 300,
                "expectations": {},
            },
            "emotion": {"enabled": True, "use_ai": True},
            "check_in": {"enabled": False, "use_ai": True},
            "ai": {"enabled": False},
        },
        "limits": {
            "global_cooldown": 300,
            "max_daily_per_target": 10,
            "max_hourly_per_target": 3,
            "duplicate_window": 60,
            "quiet_hours": [23, 0, 1, 2, 3, 4, 5, 6],
            "quiet_hours_enabled": True,
        },
        "trigger_type_cooldown": {
            "context": 60,
            "emotion": 120,
            "keyword": 30,
            "time": 300,
            "check_in": 1800,
            "ai": 180,
        },
        "user_message_cooldown": 5,
        "reply_cooldown": 120,
        "coordination": {
            "enabled": True,
            "max_messages_per_hour": 3,
            "min_interval_seconds": 300,
            "quiet_hours_enabled": True,
            "quiet_hours": [23, 0, 1, 2, 3, 4, 5, 6, 7],
        },
    }


@dataclass
class ChatContext:
    """聊天上下文"""

    chat_type: str
    target_id: int
    group_name: Optional[str] = None
    member_count: int = 0
    last_active: Optional[str] = None
    recent_topics: list = field(default_factory=list)
    message_count_today: int = 0
    # 用户行为状态
    user_expectation: Optional[str] = None  # 用户说"吃完"、"下班"等
    detected_emotion: Optional[str] = None  # 检测到的情绪
    # 场景感知字段
    platform: str = "terminal"
    platform_name: str = ""
    group_activity_level: float = 0.0
    last_group_msg_time: Optional[str] = None
    last_at_miya: Optional[str] = None
    is_reply_to_miya: bool = False
    # 谛听策略分析（来自主回复管线，供主动聊天复用）
    diting_intent: Optional[str] = None  # 用户意图: greeting/chat/question/share/complaint 等
    diting_style: Optional[str] = None  # 建议回复风格: normal/casual/gentle/playful 等
    diting_confidence: float = 0.0  # 谛听判断置信度
    # 主回复内容（避免主动聊天重复提问）
    last_miya_reply: Optional[str] = None  # 弥娅刚才对这条消息的回复


@dataclass
class SceneProfile:
    """场景画像 — 用于 Layer1 概率计算"""

    platform: str
    chat_type: str
    is_private: bool
    multiplier: float  # 平台衰减乘数
    group_activity: float  # 0=死水, 1=沸腾
    recently_engaged: bool  # 最近被@或互动
    recommended: bool  # 综合建议是否触发


@dataclass
class ProactiveResult:
    """主动消息结果"""

    should_respond: bool
    message: Optional[str]
    trigger_type: str
    context: Optional[ChatContext] = None
    # 触发层是否已经自己投递过这条消息（例如走统一协调器、且只有投递成功才取走她攒下的话）。
    # 后台轮询据此避免再发一次：全局冷却只是碰巧挡住了重复，不是设计。
    delivered: bool = False
    # 提案阶段为了去重而先记下的簿记，在**没发出去**时用它撤销。
    # 以前这些记账发生在提案时、且只在被拒时退掉每日/每小时额度，其余（"这类事件刚刚
    # 提过"、"这句话说过了"、"这个变化我消费了"）全部保留——于是一条被协调器拦下的
    # 消息，会静默地让同类消息在接下来几分钟到半小时内再也发不出来。
    rollback: Optional[Callable[[], None]] = None
    # 真正投递成功后才该做的收尾（例如把"这个变化我已经用过了"落定）。
    on_delivered: Optional[Callable[[], None]] = None
    delivery_id: str = field(default_factory=lambda: uuid4().hex)
    delivery_status: str = "pending"
    coordination_key: str = ""
    delivery_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def undo(self) -> None:
        """撤销提案阶段记下的账；重复调用是安全的。"""
        callback, self.rollback = self.rollback, None
        self.on_delivered = None
        if callback is None:
            return
        try:
            callback()
        except Exception:  # noqa: BLE001 - 撤销失败不该盖住"没发出去"这个事实
            logger.debug("[主动聊天] 回滚提案簿记失败", exc_info=True)

    def settle(self) -> None:
        """投递成功后的收尾；重复调用是安全的。"""
        callback, self.on_delivered = self.on_delivered, None
        self.rollback = None
        if callback is None:
            return
        try:
            callback()
        except Exception:  # noqa: BLE001
            logger.debug("[主动聊天] 投递后收尾失败", exc_info=True)


@dataclass
class IntentState:
    """弥娅未完成的主动意图"""

    intent_id: str
    target_id: int
    chat_type: str
    platform: str
    intent_type: str
    progression_type: str
    context_summary: str
    max_extra_turns: int
    turns_taken: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    last_continuation: datetime = field(default_factory=datetime.now)
    continuation_history: list = field(default_factory=list)
    original_response: str = ""
    paused: bool = False
    _task: Optional[Any] = None


class ProactiveChatSystem:
    """弥娅主动聊天系统 v2.1"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._config = load_config()
        self._config_path = Path(__file__).resolve().parent.parent / "config" / "proactive_chat.yaml"
        self._config_stamp = self._config_path.stat().st_mtime_ns if self._config_path.exists() else None
        self._checking_targets: set = set()
        self._proposals: dict = {}
        self._decision_timeout = 30.0

        # 核心开关
        self._enabled = self._config.get("enabled", True)

        # 触发器配置
        triggers = self._config.get("triggers", {})
        self._keyword_config = triggers.get("keyword", {})
        self._time_config = triggers.get("time", {})
        self._context_config = triggers.get("context", {})
        self._emotion_config = triggers.get("emotion", {})
        self._check_in_config = triggers.get("check_in", {})
        self._ai_config = triggers.get("ai", {})
        # 归一化后这两段一定存在；兜底只为防止 _config 被外部替换
        self._screen_aware_config = self._config.get(
            "screen_aware", _normalize_screen_aware_config(None)
        )
        self._camera_aware_config = self._config.get(
            "camera_aware", get_default_camera_aware_config()
        )

        # 限制配置
        limits = self._config.get("limits", {})
        self._global_cooldown = limits.get("global_cooldown", 300)
        self._max_daily = limits.get("max_daily_per_target", 10)
        self._max_hourly = limits.get("max_hourly_per_target", 3)
        self._duplicate_window = limits.get("duplicate_window", 60)
        self._quiet_hours = limits.get("quiet_hours", [23, 0, 1, 2, 3, 4, 5, 6])
        self._quiet_hours_enabled = limits.get("quiet_hours_enabled", True)

        # 调试设置
        debug = self._config.get("debug", {})
        self._verbose = debug.get("verbose", False)
        self._log_triggers = debug.get("log_triggers", True)

        # 运行状态
        self._last_trigger_time: dict[int, datetime] = {}
        self._context_cache: dict[int, ChatContext] = {}
        self._user_last_interaction: dict[int, datetime] = {}
        self._message_cache: dict[str, datetime] = {}
        self._daily_count: dict[int, dict] = {}
        self._hourly_count: dict[int, list] = {}

        # 最后检测的期望行为（用于上下文跟进）
        self._last_expectation: dict[int, str] = {}

        # 追踪每种触发类型的最后发送时间
        self._last_trigger_by_type: dict[int, dict[str, datetime]] = {}

        # 追踪弥娅最后一次回复时间（防止主动聊天紧跟正常回复）
        self._last_miya_reply_time: dict[int, datetime] = {}

        # 追踪已发送消息的内容，避免重复
        self._sent_messages_history: dict[int, list[tuple[str, datetime]]] = {}

        # 群聊消息时间戳（活跃度追踪）
        self._group_msg_timestamps: dict[int, list[datetime]] = {}

        # 从配置加载触发类型冷却时间
        cooldown_config = self._config.get("trigger_type_cooldown", {})
        self._trigger_type_cooldown = (
            cooldown_config
            if cooldown_config
            else {
                "context": 60,
                "emotion": 120,
                "keyword": 30,
                "time": 300,
                "check_in": 1800,
                "ai": 180,
                "ap_boredom": 300,
                "screen_aware": 120,
                "camera_aware": 180,
            }
        )

        # 用户发消息后的冷却时间
        self._user_message_cooldown = self._config.get("user_message_cooldown", 5)

        # 正常回复后的冷却时间（防止主动聊天紧跟插话）
        self._reply_cooldown = self._config.get("reply_cooldown", 120)

        # 后台轮询
        self._bg_task: Optional[asyncio.Task] = None
        self._poll_interval: int = self._config.get("check_interval", 45)
        self._send_callback: Optional[callable] = None

        # 记忆上下文提供者
        self._memory_context_provider: Optional[callable] = None

        # 深度上下文提供者（认知记忆 + 对话历史）
        self._rich_context_provider: Optional[callable] = None

        # prompt_manager
        self._prompt_manager = None

        # 场景感知配置
        scene = self._config.get("scene", {})
        self._scene_enabled = scene.get("enabled", True)
        self._platform_multipliers = scene.get("platform_multipliers", {})
        self._group_activity_cfg = scene.get("group_activity", {})
        self._mixed_strategy = scene.get("mixed_strategy", {})

        # Screen-Aware 实例（延迟注入）
        self._screen_aware: Optional[Any] = None
        self._last_screen_intent: Optional[Any] = None
        self._last_presence_key: str = ""
        self._last_presence_time: float = 0.0
        self._last_activity_time: float = 0.0

        # === 意图持续机制 ===
        self._pending_intents: dict[int, IntentState] = {}
        self._intent_id_counter: int = 0
        self._continuity_config = self._config.get("continuity_trigger", {})
        self._continuity_enabled = self._continuity_config.get("enabled", True)
        self._continuity_min_delay = self._continuity_config.get("min_delay_seconds", 2)
        self._continuity_max_delay = self._continuity_config.get("max_delay_seconds", 5)
        self._continuity_max_turns = self._continuity_config.get("max_extra_turns", 2)

        # 工具调用能力（行动型意图推进）
        self._tool_registry: Optional[callable] = None
        self._proactive_tool_context_provider: Optional[callable] = None

        # 从 text_config.json 缓存文本配置
        self._cache_text_configs()

    def apply_config(self, config: dict) -> None:
        """验证并热更新主动策略，保留运行中的状态和已用额度。"""
        import copy
        from core.proactive_coordinator import get_proactive_coordinator

        config = copy.deepcopy(config)
        limits = config.get("limits", {})
        coordination = config.get("coordination", {})
        numeric = {
            "check_interval": config.get("check_interval", 45),
            "global_cooldown": limits.get("global_cooldown", 300),
            "max_daily_per_target": limits.get("max_daily_per_target", 10),
            "max_hourly_per_target": limits.get("max_hourly_per_target", 3),
            "duplicate_window": limits.get("duplicate_window", 60),
            "user_message_cooldown": config.get("user_message_cooldown", 5),
            "reply_cooldown": config.get("reply_cooldown", 120),
            "send_timeout_seconds": coordination.get("send_timeout_seconds", 30),
            "decision_timeout_seconds": coordination.get("decision_timeout_seconds", 30),
        }
        import math

        for key, value in numeric.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"主动配置 {key} 必须是非负有限数值")
        if numeric["check_interval"] < 1 or min(numeric["send_timeout_seconds"], numeric["decision_timeout_seconds"]) <= 0:
            raise ValueError("轮询间隔至少 1 秒，超时必须大于 0")
        for hours in (limits.get("quiet_hours", []), coordination.get("quiet_hours", [])):
            if not isinstance(hours, list) or any(type(hour) is not int or not 0 <= hour <= 23 for hour in hours):
                raise ValueError("静默时段必须是 0 到 23 的整数列表")
        coordinator = get_proactive_coordinator()
        coordinator.configure(config={**coordination, "enabled": bool(config.get("enabled", True))
                                     and bool(coordination.get("enabled", True))})
        self._config = config
        self._enabled = bool(config.get("enabled", True))
        for trigger in ("keyword", "time", "context", "emotion", "check_in", "ai"):
            setattr(self, f"_{trigger}_config", config.get("triggers", {}).get(trigger, {}))
        self._screen_aware_config = config.get("screen_aware", _normalize_screen_aware_config(None))
        self._camera_aware_config = config.get("camera_aware", get_default_camera_aware_config())
        self._global_cooldown = numeric["global_cooldown"]
        self._max_daily = numeric["max_daily_per_target"]
        self._max_hourly = numeric["max_hourly_per_target"]
        self._duplicate_window = numeric["duplicate_window"]
        self._user_message_cooldown = numeric["user_message_cooldown"]
        self._reply_cooldown = numeric["reply_cooldown"]
        self._poll_interval = numeric["check_interval"]
        self._decision_timeout = numeric["decision_timeout_seconds"]
        self._quiet_hours = limits.get("quiet_hours", [])
        self._quiet_hours_enabled = limits.get("quiet_hours_enabled", True)
        self._trigger_type_cooldown = config.get("trigger_type_cooldown") or get_default_config()["trigger_type_cooldown"]
        scene = config.get("scene", {})
        self._scene_enabled = scene.get("enabled", True)
        self._platform_multipliers = scene.get("platform_multipliers", {})
        self._group_activity_cfg = scene.get("group_activity", {})
        self._mixed_strategy = scene.get("mixed_strategy", {})
        continuity = config.get("continuity_trigger", {})
        self._continuity_config = continuity
        self._continuity_enabled = continuity.get("enabled", True)
        self._continuity_min_delay = continuity.get("min_delay_seconds", 2)
        self._continuity_max_delay = continuity.get("max_delay_seconds", 5)
        self._continuity_max_turns = continuity.get("max_extra_turns", 2)
        self._cache_text_configs()

    def reload_config_if_changed(self, *, force: bool = False) -> bool:
        """仅接受完整合法的 YAML；错误配置不会替换当前策略。"""
        try:
            stamp = self._config_path.stat().st_mtime_ns
            if not force and stamp == self._config_stamp:
                return False
            import yaml

            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("proactive_chat"), dict):
                raise ValueError("缺少 proactive_chat 配置对象")
            self.apply_config(_normalize_config(raw["proactive_chat"]))
            self._config_stamp = stamp
            logger.info("[主动聊天] 配置已热更新")
            return True
        except Exception as exc:
            logger.warning("[主动聊天] 热更新失败，保留当前策略: %s", exc)
            return False

    def set_screen_aware(self, screen_aware) -> None:
        """注入 ScreenAwareProactive 实例，由 DecisionHub 调用"""
        self._screen_aware = screen_aware
        logger.info("[主动聊天] Screen-Aware 已接入")

    def _check_trigger_type_cooldown(self, target_id: int, trigger_type: str) -> bool:
        """检查同类型触发是否在冷却时间内"""
        min_interval = self._trigger_type_cooldown.get(trigger_type, 60)

        if target_id not in self._last_trigger_by_type:
            return True  # 没有记录，可以触发

        last_time = self._last_trigger_by_type[target_id].get(trigger_type)
        if not last_time:
            return True

        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed >= min_interval

    def _record_trigger_by_type(self, target_id: int, trigger_type: str):
        """记录某类型的触发时间"""
        if target_id not in self._last_trigger_by_type:
            self._last_trigger_by_type[target_id] = {}
        self._last_trigger_by_type[target_id][trigger_type] = datetime.now()

    def _check_message_content_duplicate(self, target_id: int, message: str) -> bool:
        """检查消息内容是否与最近发送的过于相似"""
        if target_id not in self._sent_messages_history:
            return False

        now = datetime.now()
        # 清理过期记录（保留30分钟内的）
        self._sent_messages_history[target_id] = [
            (msg, t) for msg, t in self._sent_messages_history[target_id] if (now - t).total_seconds() < 1800
        ]

        # 简化比对：检查前20个字符
        msg_prefix = message[:20] if len(message) > 20 else message

        for prev_msg, _ in self._sent_messages_history[target_id]:
            prev_prefix = prev_msg[:20] if len(prev_msg) > 20 else prev_msg
            # 如果前缀相同，认为是重复
            if msg_prefix == prev_prefix:
                return True

        return False

    def _record_sent_message(self, target_id: int, message: str):
        """记录已发送的消息"""
        if target_id not in self._sent_messages_history:
            self._sent_messages_history[target_id] = []
        self._sent_messages_history[target_id].append((message, datetime.now()))

    def set_ai_client(self, ai_client):
        self.ai_client = ai_client

    def set_personality(self, personality):
        self.personality = personality

    def set_prompt_manager(self, prompt_manager):
        """注入 prompt_manager 以构建系统 prompt"""
        self._prompt_manager = prompt_manager

    def record_miya_reply(self, target_id: int):
        """记录弥娅刚刚对 target 发送了正常回复"""
        self._last_miya_reply_time[target_id] = datetime.now()

    def _build_persona_context(self) -> str:
        """提取当前人设+形态的上下文，注入 AI prompt"""
        if not self.personality:
            return ""

        try:
            profile = self.personality.get_profile()
            form_info = profile.get("form_info", {})
            form_name = form_info.get("name", "常态")
            description = form_info.get("description", "")
            speaking = form_info.get("speaking", {})
            style = speaking.get("style", "")
            form_proactive = form_info.get("form_proactive", "")
            dominant = profile.get("dominant", "")
            core = profile.get("current_core_form", "")
            core_info = profile.get("core_form_info") or {}

            parts = [f"当前形态：{form_name}"]
            if description:
                parts.append(f"性格底色：{description}")
            if style:
                parts.append(f"说话风格：{style}")
            if form_proactive:
                parts.append(f"主动原则：{form_proactive}")
            if dominant:
                parts.append(f"核心心魂：{dominant}")
            if core and core_info:
                parts.append(f"{core_info.get('name', '')}显照·{core_info.get('description', '')}")

            form_casual = form_info.get("form_casual_chat", "")
            if form_casual:
                parts.append(f"闲聊模式：{form_casual}")

            return " | ".join(parts)
        except Exception:
            return ""

    def set_send_callback(self, callback):
        """设置消息发送回调函数
        callback(message, target_id, chat_type, platform, trigger_type=None)
        trigger_type: context/emotion/keyword/time/check_in/ai/ap_boredom/screen_aware (v8.1)
        """
        self._send_callback = callback

    def set_memory_context_provider(self, provider):
        """设置记忆上下文提供者 (func: target_id -> str)"""
        self._memory_context_provider = provider

    def set_rich_context_provider(self, provider):
        """设置深度上下文提供者 (async func: target_id -> str) — 认知记忆 + 对话历史"""
        self._rich_context_provider = provider

    def _build_memory_context(self, target_id: int) -> str:
        """从 ChatContext 构建当前对话上下文（轻量，不查持久记忆）"""
        ctx = self._context_cache.get(target_id)
        if not ctx:
            return ""

        parts = []
        last_active = ctx.last_active or ""
        if last_active:
            try:
                dt = datetime.fromisoformat(last_active)
                elapsed = (datetime.now() - dt).total_seconds()
                if elapsed < 60:
                    parts.append(f"用户刚刚活跃过（{int(elapsed)}秒前）")
                elif elapsed < 3600:
                    parts.append(f"用户{int(elapsed // 60)}分钟前活跃")
                else:
                    parts.append(f"用户{int(elapsed // 3600)}小时前活跃")
            except (ValueError, TypeError):
                pass

        if ctx.recent_topics:
            parts.append(f"最近话题: {', '.join(ctx.recent_topics)}")

        if ctx.chat_type == "group":
            parts.append(f"群活跃度: {ctx.group_activity_level:.2f}")
            if ctx.last_at_miya:
                parts.append(f"最近@弥娅: {ctx.last_at_miya}")

        if ctx.detected_emotion:
            parts.append(f"情绪: {ctx.detected_emotion}")

        return "\n".join(parts) if parts else ""

    async def _build_rich_context(self, target_id: int) -> str:
        """异步构建深度上下文（认知记忆 + 对话历史）"""
        if not self._rich_context_provider:
            return ""
        try:
            result = self._rich_context_provider(target_id)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result) if result else ""
        except Exception:
            return ""

    async def _generate_ai_message(self, trigger_type: str, context: dict, target_id: int = 0) -> Optional[str]:
        """统一 AI 消息生成器

        Args:
            trigger_type: context / emotion / keyword / time / check_in
            context: {"key": "value"} 用于填充 system_prompt 变量
            target_id: 用于查记忆上下文

        Returns:
            AI 生成的消息文本，或 None（表示 SKIP / 失败）
        """
        if not self.ai_client:
            return None

        system_prompt_paths = {
            "context": "context_trigger.system_prompt",
            "emotion": "emotion_perception.system_prompt",
            "keyword": "keyword_trigger.system_prompt",
            "time": "time_awareness.system_prompt",
            "check_in": "check_in.system_prompt",
        }

        from pathlib import Path

        import yaml

        config_path = Path(__file__).parent.parent / "config" / "proactive_chat.yaml"
        raw_config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}

        prompt_template = ""
        prompt_path = system_prompt_paths.get(trigger_type, "")
        parts = prompt_path.split(".")
        node = raw_config.get("proactive_chat", {})
        for part in parts:
            node = node.get(part, {})
        prompt_template = node if isinstance(node, str) else ""

        if not prompt_template:
            prompt_template = self._default_ai_prompt(trigger_type)

        persona = self._build_persona_context()
        memory_context = self._build_memory_context(target_id) if target_id else ""
        rich_context = await self._build_rich_context(target_id) if target_id else ""
        if rich_context:
            memory_context = "\n".join(part for part in (memory_context, rich_context) if part)

        context_with_persona = dict(context)
        context_with_persona["persona"] = persona
        context_with_persona["memory"] = memory_context

        try:
            prompt = prompt_template.format(**context_with_persona)
        except (KeyError, ValueError):
            prompt = prompt_template

        try:
            # 构建最终 prompt：记忆上下文 + 人设 + 触发上下文
            final_prompt = prompt
            if memory_context:
                final_prompt = f"【当前对话】\n{memory_context}\n\n{prompt}"

            # 【谛听传递】注入主回复管线的意图分析，避免主动聊天 AI 从零判断
            cached_ctx = self._context_cache.get(target_id) if target_id else None
            if cached_ctx and cached_ctx.diting_intent:
                diting_hint = f"\n\n【已分析的用户状态（来自主回复管线）】\n- 用户意图: {cached_ctx.diting_intent}\n"
                if cached_ctx.diting_style:
                    diting_hint += f"- 建议风格: {cached_ctx.diting_style}\n"
                diting_hint += f"- 分析置信度: {cached_ctx.diting_confidence:.0%}\n"
                diting_hint += "（以上信息供参考，请据此判断是否需要主动发言及发言内容）"
                final_prompt = final_prompt + diting_hint

            # 【主回复感知】让主动聊天 AI 知道弥娅刚才回了什么，避免重复提问
            if cached_ctx and cached_ctx.last_miya_reply:
                reply_awareness = (
                    f"\n\n【弥娅刚才已回复】\n{cached_ctx.last_miya_reply}\n"
                    "（不要重复问主回复已经问过的问题，也不要重复说已经说过的内容）"
                )
                final_prompt = final_prompt + reply_awareness

            use_tools = trigger_type == "ai"
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=final_prompt)],
                tools=[] if not use_tools else None,
                tool_choice="none" if not use_tools else "auto",
            )
            message = response.strip() if isinstance(response, str) else str(response).strip()
            if message.upper() == "SKIP" or not message:
                return None
            return message
        except Exception as e:
            logger.warning(f"[主动聊天] AI 生成失败 [{trigger_type}]: {e}")
            return None

    def _default_ai_prompt(self, trigger_type: str) -> str:
        """从 text_config.json 读取各触发类型默认 AI system prompt"""
        try:
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                prompts = cfg.get("proactive_chat", {}).get("default_prompts", {})
                return prompts.get(trigger_type, "")
        except Exception:
            pass
        return ""

    @staticmethod
    def _load_text_config(key: str, default: str = "") -> str:
        """从 text_config.json 读取文本配置"""
        try:
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                node = cfg.get("proactive_chat", {})
                for part in key.split("."):
                    node = node.get(part, {})
                return node if isinstance(node, str) else default
        except Exception:
            pass
        return default

    def _try_get_ai_message(self, trigger_type: str, context: dict) -> Optional[str]:
        """同步包装：尝试 AI 生成，失败返回 None —— 用于需要 await 的 async 方法中"""
        return None  # 覆盖在 async 调用中

    async def _generate_and_fallback(
        self,
        trigger_type: str,
        ai_context: dict,
        fallback_messages: list,
        target_id: int = 0,
    ) -> Optional[str]:
        """AI 优先 + 模板回退的消息生成

        Returns:
            生成的消息，或 None
        """
        use_ai = False
        if trigger_type == "context":
            use_ai = self._context_config.get("use_ai", True)
        elif trigger_type == "emotion":
            use_ai = self._emotion_config.get("use_ai", True)
        elif trigger_type == "keyword":
            use_ai = self._keyword_config.get("use_ai", True)
        elif trigger_type == "time":
            use_ai = self._time_config.get("use_ai", True)
        elif trigger_type == "check_in":
            use_ai = self._check_in_config.get("use_ai", True)

        if use_ai and self.ai_client:
            ai_msg = await self._generate_ai_message(trigger_type, ai_context, target_id)
            if ai_msg:
                return ai_msg

        if fallback_messages:
            return random.choice(fallback_messages)
        return None

    def get_active_targets(self) -> list[int]:
        """获取所有活跃的聊天目标 ID 列表"""
        return list(self._context_cache.keys())

    async def start_background_loop(self):
        """启动后台轮询循环，定期检查所有活跃上下文的触发条件"""
        if self._bg_task and not self._bg_task.done():
            logger.info("[主动聊天] 后台循环已在运行")
            return

        self._bg_task = asyncio.create_task(self._background_check_loop())
        logger.info(f"[主动聊天] 后台轮询已启动 (间隔 {self._poll_interval}s)")

    async def stop_background_loop(self):
        """停止后台轮询循环"""
        if self._bg_task:
            self._bg_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bg_task
            self._bg_task = None
            logger.info("[主动聊天] 后台轮询已停止")

    async def _background_check_loop(self):
        """后台轮询循环：定期检查所有活跃上下文"""
        poll_count = 0
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                self.reload_config_if_changed()
                poll_count += 1

                if not self._enabled or self._is_in_quiet_hours():
                    continue

                # Screen-Aware 观察：只有窗口标题+OCR，不调视觉模型
                if self.is_trigger_enabled("screen_aware") and self._screen_aware:
                    try:
                        if self._screen_aware.should_observe:
                            await self._screen_aware.observe(allow_vision=False)
                    except Exception as e:
                        logger.warning(f"[主动聊天] ScreenAware 观察异常: {e}")
                # 每4轮打印一次诊断（前2轮必打）
                if poll_count <= 2 or poll_count % 10 == 0:
                    sa_ok = self._screen_aware is not None
                    sa_should = self._screen_aware.should_observe if sa_ok else False
                    logger.info(
                        f"[主动聊天] 轮询 #{poll_count}: screen_aware={sa_ok}, "
                        f"should_observe={sa_should}, targets={len(self.get_active_targets())}"
                    )

                active_targets = self.get_active_targets()
                if not active_targets:
                    continue

                for target_id in active_targets:
                    try:
                        result = await self.check_and_respond(target_id)

                        if result and result.should_respond and result.message:
                            if result.delivered:
                                # 触发层已经自己投递过（只有投递成功才会返回这个结果），
                                # 再走一遍发送出口就是同一条消息发两遍。
                                logger.info(
                                    "[主动聊天] [后台] [%s] target=%s 已投递 -> %s",
                                    result.trigger_type, target_id, result.message[:30],
                                )
                                continue
                            await self._deliver_background_result(target_id, result)
                    except Exception as e:
                        logger.warning(f"[主动聊天] 后台检查 target={target_id} 失败: {e}")
                        continue

            except asyncio.CancelledError:
                logger.info("[主动聊天] 后台轮询循环已取消")
                break
            except Exception as e:
                logger.error(f"[主动聊天] 后台轮询异常: {e}")
                await asyncio.sleep(10)

    def is_enabled(self) -> bool:
        return self._enabled

    def is_trigger_enabled(self, trigger_type: str) -> bool:
        if trigger_type == "keyword":
            return self._keyword_config.get("enabled", True)
        elif trigger_type == "time":
            return self._time_config.get("enabled", True)
        elif trigger_type == "context":
            return self._context_config.get("enabled", True)
        elif trigger_type == "emotion":
            return self._emotion_config.get("enabled", True)
        elif trigger_type == "check_in":
            return self._check_in_config.get("enabled", False)
        elif trigger_type == "ai":
            return self._ai_config.get("enabled", False)
        elif trigger_type == "screen_aware":
            return self._screen_aware_config.get("enabled", True) and self._screen_aware is not None
        elif trigger_type == "camera_aware":
            return bool(self._camera_aware_config.get("enabled", True))
        elif trigger_type == "continuity":
            return self._continuity_enabled
        return False

    def update_context(self, target_id: int, context: ChatContext, platform: str = "terminal"):
        context.platform = platform
        self._context_cache[target_id] = context
        self._user_last_interaction[target_id] = datetime.now()

    async def record_message(
        self,
        target_id: int,
        chat_type: str,
        content: str = "",
        platform: str = "terminal",
    ):
        now = datetime.now()
        self._user_last_interaction[target_id] = now

        if target_id not in self._context_cache:
            self._context_cache[target_id] = ChatContext(
                chat_type=chat_type,
                target_id=target_id,
                platform=platform,
            )

        ctx = self._context_cache[target_id]
        ctx.chat_type = chat_type
        ctx.platform = platform
        ctx.last_active = now.isoformat()
        ctx.message_count_today += 1

        # 群聊活跃度追踪
        if chat_type == "group":
            active_window = self._group_activity_cfg.get("active_message_window", 120)
            self._group_msg_timestamps.setdefault(target_id, []).append(now)
            # 只保留窗口内的消息
            self._group_msg_timestamps[target_id] = [
                t for t in self._group_msg_timestamps[target_id] if (now - t).total_seconds() < active_window
            ]
            recent_count = len(self._group_msg_timestamps[target_id])
            ctx.group_activity_level = min(1.0, recent_count / 5.0)
            ctx.last_group_msg_time = now.isoformat()

        # 提取话题关键词
        if content:
            keywords = self._extract_keywords(content)
            if keywords:
                ctx.recent_topics = (ctx.recent_topics + keywords)[-5:]

        # 检测期望行为（用户说要做什么）
        expectation = await self._detect_expectation(content)
        if expectation:
            ctx.user_expectation = expectation
            self._last_expectation[target_id] = expectation
            logger.info(f"[主动聊天] 检测到期望行为: {expectation}")

        # 检测情绪
        emotion = self._detect_emotion(content)
        if emotion:
            ctx.detected_emotion = emotion
            logger.info(f"[主动聊天] 检测到情绪: {emotion}")

        # 重置每日计数
        if target_id not in self._daily_count or self._daily_count[target_id]["date"] != now.date():
            self._daily_count[target_id] = {"date": now.date(), "count": 0}

    def _extract_keywords(self, text: str) -> list:
        return [kw for kw in self._topic_keywords if kw in text]

    async def _detect_expectation(self, text: str) -> Optional[str]:
        """AI 判断用户消息中的期望行为（吃完、睡完、下班等）"""
        if not self.ai_client or not text:
            return None
        prompt = self._expectation_detect_prompt
        if not prompt:
            return None
        try:
            prompt = prompt.format(text=text)
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=prompt)],
                tools=[],
                tool_choice="none",
            )
            result = str(response).strip() if response else ""
            return result if result and result.upper() != "NONE" else None
        except Exception as e:
            logger.debug(f"[主动聊天] 期望行为检测失败: {e}")
            return None

    def _detect_emotion(self, text: str) -> Optional[str]:
        """检测用户情绪"""
        emotion_keywords = self._emotion_config.get("emotion_keywords", {})

        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return emotion
        return None

    def _is_in_quiet_hours(self) -> bool:
        """检查静默时段"""
        if not self._quiet_hours_enabled:
            return False
        return datetime.now().hour in self._quiet_hours

    def _check_cooldown(self, target_id: int) -> bool:
        """检查冷却时间"""
        last_time = self._last_trigger_time.get(target_id)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self._global_cooldown:
                return False
        return True

    def _check_rate_limits(self, target_id: int) -> bool:
        """检查速率限制"""
        now = datetime.now()
        today = now.date()

        # 每日限制
        if target_id in self._daily_count and self._daily_count[target_id]["date"] == today:
            if self._daily_count[target_id]["count"] >= self._max_daily:
                return False

        # 每小时限制
        if target_id in self._hourly_count:
            self._hourly_count[target_id] = [
                t for t in self._hourly_count[target_id] if (now - t).total_seconds() < 3600
            ]
            if len(self._hourly_count[target_id]) >= self._max_hourly:
                return False

        return True

    def _is_duplicate(self, target_id: int, message: str) -> bool:
        """检查重复消息，并把这次提案记进缓存。

        注意它**总会**写入 `_message_cache`，包括返回 False 的情况——那正是"这条我刚
        提过"的记忆。提案被下游拒绝时用 `_forget_message_proposal` 撤销，否则一句没能
        发出去的话会让她在 `_duplicate_window` 内再也不敢说同样的话。
        """
        if not message:
            return True

        msg_hash = hashlib.md5(f"{target_id}:{message[:50]}".encode()).hexdigest()

        if msg_hash in self._message_cache:
            last_time = self._message_cache[msg_hash]
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self._duplicate_window:
                logger.info(f"[主动聊天] 消息去重: {message[:30]}...")
                return True
            del self._message_cache[msg_hash]

        self._message_cache[msg_hash] = datetime.now()

        # 清理过期缓存
        now = datetime.now()
        self._message_cache = {
            k: v for k, v in self._message_cache.items() if (now - v).total_seconds() < self._duplicate_window * 2
        }

        return False

    def _forget_message_proposal(self, target_id: int, message: str, trigger_type: str = "camera_aware") -> None:
        """撤销一次没能投递出去的提案留下的记账。

        清掉内容去重记忆、`_message_cache` 里的指纹、同类触发的冷却时间戳，并退还
        每日/每小时额度。调用方随后可以重新提案同一件事。
        """
        if not message:
            return
        prefix = message[:20] if len(message) > 20 else message
        history = self._sent_messages_history.get(target_id)
        if history:
            self._sent_messages_history[target_id] = [
                (msg, stamp) for msg, stamp in history
                if (msg[:20] if len(msg) > 20 else msg) != prefix
            ]
        self._message_cache.pop(
            hashlib.md5(f"{target_id}:{message[:50]}".encode()).hexdigest(), None)
        by_type = self._last_trigger_by_type.get(target_id)
        if by_type:
            # The camera's own three sub-triggers share this one cooldown slot, so
            # a rejected line used to silence the next real event for 180 seconds.
            by_type.pop(trigger_type, None)

    def _remember_message(self, target_id: int, message: str) -> None:
        """记下"这句话真的说出去了"。

        与 `_forget_message_proposal` 对称：`_is_duplicate` 把"检查"和"记录"揉在
        一起，所以投递之前调用它就会给一句还没发出去的话打上"已说过"的戳。现在由
        投递成功的路径显式记录，检查那一侧保持只读。
        """
        if not message:
            return
        self._message_cache[
            hashlib.md5(f"{target_id}:{message[:50]}".encode()).hexdigest()
        ] = datetime.now()

    def _record_trigger(self, target_id: int):
        """记录触发"""
        now = datetime.now()
        today = now.date()

        self._last_trigger_time[target_id] = now

        if target_id not in self._daily_count or self._daily_count[target_id].get("date") != today:
            self._daily_count[target_id] = {"date": today, "count": 0}
        self._daily_count[target_id]["count"] += 1

        if target_id not in self._hourly_count:
            self._hourly_count[target_id] = []
        self._hourly_count[target_id].append(now)

    def _refund_trigger(self, target_id: int):
        """把一次"没能发出去"的提案还给她的额度。

        ``_record_trigger`` 记的是**提案**，而统一协调器拦下的提案根本没到佳那里。
        让它照样占额度，等于一条系统通知就能把她一小时的嘴堵上——日志里那 5 条被
        拦下的摄像头话语，就是这么变成"她什么也没想说"的。额度应该只统计真的
        送到他面前的句子。

        只退还小时/每日额度，``_last_trigger_time`` 不退：她确实想过一次，
        下一轮稍微退让一点是合理的节奏。
        """
        today = datetime.now().date()
        daily = self._daily_count.get(target_id)
        if daily and daily.get("date") == today:
            daily["count"] = max(0, int(daily.get("count", 0)) - 1)
        stamps = self._hourly_count.get(target_id)
        if stamps:
            stamps.pop()

    async def _deliver_background_result(self, target_id: int, result: ProactiveResult) -> bool:
        async with result.delivery_lock:
            return await self._deliver_background_result_locked(target_id, result)

    async def _deliver_background_result_locked(self, target_id: int, result: ProactiveResult) -> bool:
        """把一个后台提案交到发送出口，并如实记录它有没有真的出去。

        返回佳是否真的收到了。被统一协调器拦下的提案不花她任何额度——它根本没发出去，
        不该占这一小时的预算。以前这里无条件写"已发送"，于是日志说着"发了"，
        而她其实一个字都没到佳面前。
        """
        if result.delivered:
            return True
        if result.delivery_status != "pending" or not result.message:
            return False
        ctx = result.context
        chat_type = ctx.chat_type if ctx else "private"
        target = ctx.target_id if (ctx and chat_type == "group") else target_id
        platform = ctx.platform if ctx else "terminal"

        if not self._send_callback:
            self._reject_result(target_id, result)
            logger.info(
                "[主动聊天] [后台] [%s] target=%s 没有发送出口，未发送（额度已退还）",
                result.trigger_type, target_id,
            )
            return False
        try:
            import inspect

            parameters = inspect.signature(self._send_callback).parameters
            kwargs = {"key": result.coordination_key or result.delivery_id} if "key" in parameters else {}
            sent = await self._send_callback(
                result.message, target, chat_type, platform, result.trigger_type, **kwargs,
            )
        except asyncio.CancelledError:
            self._reject_result(target_id, result)
            raise
        except Exception as e:
            logger.error(f"[主动聊天] 发送回调失败: {e}")
            self._reject_result(target_id, result)
            return False
        # 发送出口返回 False 表示被统一协调器拦下（限频/静默/去重）。
        if not delivery_accepted(sent):
            self._reject_result(target_id, result)
            logger.info(
                "[主动聊天] [后台] [%s] target=%s 被协调器拦下，未发送（额度已退还）: %s",
                result.trigger_type, target_id, result.message[:30],
            )
            return False
        logger.info(
            "[主动聊天] [后台] [%s] target=%s -> %s",
            result.trigger_type, target_id, result.message[:30],
        )
        result.settle()
        result.delivered = True
        result.delivery_status = getattr(sent, "status", "sent")
        return True

    def _reject_result(self, target_id: int, result: ProactiveResult) -> None:
        if result.delivery_status != "pending":
            return
        result.delivery_status = "failed"
        self._refund_trigger(target_id)
        result.undo()
        self._forget_message_proposal(target_id, result.message, result.trigger_type)

    def _calculate_scene_profile(self, context: ChatContext) -> float:
        """Layer1 场景感知概率衰减 → 返回最终概率乘数 [0, 1]"""
        if not self._scene_enabled:
            return 1.0

        ms = self._mixed_strategy
        ga = self._group_activity_cfg

        platform = context.platform or "terminal"
        is_private = context.chat_type != "group"
        key = f"{platform}_{'private' if is_private else 'group'}"
        multiplier = self._platform_multipliers.get(key, 0.5)

        if not is_private:
            ga.get("active_message_window", 120)
            inactive_threshold = ga.get("inactive_threshold", 300)
            active_mult = ga.get("active_multiplier", 0.2)
            inactive_mult = ga.get("inactive_multiplier", 0.8)
            at_boost = ga.get("recent_at_boost", 0.6)

            if context.group_activity_level > 0.5:
                multiplier *= active_mult
            else:
                multiplier *= inactive_mult

            if context.last_at_miya:
                try:
                    at_time = datetime.fromisoformat(context.last_at_miya)
                    if (datetime.now() - at_time).total_seconds() < inactive_threshold:
                        multiplier = min(1.0, multiplier + at_boost)
                except (ValueError, TypeError):
                    pass

        min_prob = ms.get("layer1_min_probability", 0.3)
        if multiplier < min_prob:
            return -1.0

        if random.random() > multiplier:
            return -1.0

        return multiplier

    def _build_deep_context(self, context: ChatContext) -> str:
        """Layer2 深度上下文 — 供 AI 判决"""
        parts = []

        platform = context.platform or "terminal"
        parts.append(f"平台: {platform} ({'私聊' if context.chat_type != 'group' else '群聊'})")

        if context.chat_type == "group":
            parts.append(f"群活跃度: {context.group_activity_level:.2f} (0=死水, 1=沸腾)")
            if context.last_at_miya:
                parts.append(f"最近@弥娅: {context.last_at_miya}")
            if context.is_reply_to_miya:
                parts.append("上一轮对话: 用户在和弥娅互动")

        parts.append(f"上次互动: {context.last_active or '未知'}")

        try:
            from memory.context_assembler import ContextAssembler
            from memory.context_identity import ContextIdentity

            identity = ContextIdentity.resolve(
                "global" if context.chat_type == "group" else context.target_id,
                context.target_id if context.chat_type == "group" else "",
                platform,
            )
            screen_ctx, camera_ctx = ContextAssembler.senses(identity)
            parts.extend(part for part in (screen_ctx, camera_ctx) if part)
        except Exception:
            logger.debug("[主动聊天] 统一视觉上下文不可用", exc_info=True)

        return "\n".join(parts)

    def _build_screen_context(self) -> str:
        """构建弥娅的视觉感知上下文 — 原始感官卡片，让AI自己判断"""
        if not self._screen_aware:
            return ""

        try:
            card = self._screen_aware.build_timeline_card(max_entries=12)
            if card:
                return card
        except Exception:
            pass

        return ""

    async def check_and_respond(self, target_id: int, user_message: Optional[str] = None) -> Optional[ProactiveResult]:
        """同一目标只保留一个决策或待投递提案。"""
        self.reload_config_if_changed()
        if target_id in self._checking_targets or target_id in self._proposals:
            return None
        self._checking_targets.add(target_id)
        context = self._context_cache.get(target_id)
        old_expectation = context.user_expectation if context else None
        old_emotion = context.detected_emotion if context else None
        old_last_trigger = self._last_trigger_time.get(target_id)
        try:
            result = await asyncio.wait_for(
                self._check_and_respond_once(target_id, user_message), timeout=self._decision_timeout,
            )
            if result is None or result.delivered:
                return result
            rollback, settle = result.rollback, result.on_delivered
            proposal_expectation = context.user_expectation if context else None
            proposal_emotion = context.detected_emotion if context else None

            def undo_proposal():
                if rollback:
                    rollback()
                self._proposals.pop(target_id, None)
                self._forget_message_proposal(target_id, result.message, result.trigger_type)
                if old_last_trigger is None:
                    self._last_trigger_time.pop(target_id, None)
                else:
                    self._last_trigger_time[target_id] = old_last_trigger
                if context and context.user_expectation == proposal_expectation:
                    context.user_expectation = old_expectation
                    if old_expectation:
                        self._last_expectation.setdefault(target_id, old_expectation)
                if context and context.detected_emotion == proposal_emotion:
                    context.detected_emotion = old_emotion

            def settle_proposal():
                self._proposals.pop(target_id, None)
                if settle:
                    settle()

            result.rollback, result.on_delivered = undo_proposal, settle_proposal
            self._proposals[target_id] = result
            return result
        except asyncio.TimeoutError:
            logger.warning("[主动聊天] 主动决策超时 target=%s", target_id)
            return None
        finally:
            self._checking_targets.discard(target_id)

    async def _check_and_respond_once(self, target_id: int, user_message: Optional[str] = None) -> Optional[ProactiveResult]:
        """检查是否需要主动发言"""
        if not self._enabled:
            return None

        # 检查用户是否刚发送了消息
        last_user_msg_time = self._user_last_interaction.get(target_id)
        if last_user_msg_time:
            elapsed = (datetime.now() - last_user_msg_time).total_seconds()
            if elapsed < self._user_message_cooldown:
                return None

        # 检查弥娅是否刚刚回复过（防止主动聊天紧跟正常回复重复发送）
        last_miya_reply = self._last_miya_reply_time.get(target_id)
        if last_miya_reply:
            miya_elapsed = (datetime.now() - last_miya_reply).total_seconds()
            if miya_elapsed < self._reply_cooldown:
                return None

        if self._is_in_quiet_hours():
            return None

        if not self._check_cooldown(target_id):
            return None

        if not self._check_rate_limits(target_id):
            return None

        context = self._context_cache.get(target_id)
        if not context:
            return None

        # Layer1: 场景感知概率衰减（上下文触发不受限，其他触发器需通过）
        scene_mult = 1.0
        if self._scene_enabled:
            scene_mult = self._calculate_scene_profile(context)

        # 1. 上下文触发（行为期望跟进）- 最高优先级，不受场景过滤
        if self.is_trigger_enabled("context"):
            result = await self._check_context_trigger(target_id, context)
            if result:
                return result

        # 场景过滤：后续触发器需通过 Layer1
        if scene_mult < 0:
            return None

        # 2. 情绪感知触发
        if self.is_trigger_enabled("emotion") and context.detected_emotion:
            result = await self._check_emotion_trigger(target_id, context, user_message or "")
            if result:
                return result

        # 3. 关键词触发
        if self.is_trigger_enabled("keyword") and user_message:
            result = await self._check_keyword_trigger(target_id, context, user_message)
            if result:
                return result

        # 4. 时间触发
        if self.is_trigger_enabled("time"):
            result = await self._check_time_trigger(target_id, context)
            if result:
                return result

        # 5. 主动关怀
        if self.is_trigger_enabled("check_in"):
            result = await self._check_check_in_trigger(target_id, context)
            if result:
                return result

        # 6. 摄像头只消费弥娅在自主观察中已经决定要说的话。
        # 放在"再问一次该不该说"前面：她已经想过一遍的句子，优先于现场重新判断；
        # 否则每一次活动变化都会把它挤到下一轮，而它是有寿命的。
        if self.is_trigger_enabled("camera_aware"):
            result = await self._check_miya_vision_trigger(target_id, context)
            if result:
                return result

        # 7. AI触发
        if self.is_trigger_enabled("ai"):
            result = await self._check_ai_trigger(target_id, context)
            if result:
                return result

        # AI 判断本轮不需要主动发言，记录检查时间避免短时间重复评估
        self._last_trigger_time[target_id] = datetime.now()
        return None

    def _camera_persona_prompt(self, module_prompt: str) -> str:
        """Attach Miya's live form and mood to a camera-generated instruction.

        These camera triggers send a single *user* turn, and ``AIClient.chat``
        only ever injects the persona when the first message is a system one - so
        she used to speak about what she saw with no form and no mood at all,
        which is exactly the "she has no shape here" that Jia noticed. The bridge
        path gets this from the coordinator; this path has to ask for it.
        """
        prompt = module_prompt
        try:
            from core.persona_prompt import compose_persona_system_prompt

            personality = None
            try:
                from core.proactive_coordinator import get_proactive_coordinator

                personality = getattr(get_proactive_coordinator(), "_personality", None)
            except Exception:  # noqa: BLE001 - the persona alone is still worth having
                personality = None
            prompt = compose_persona_system_prompt(
                module_prompt, personality=personality, ai_client=self.ai_client,
            )
        except Exception:  # noqa: BLE001
            logger.debug("[主动聊天] 组合人格提示词失败，使用原始提示词", exc_info=True)
        try:
            # Her current form is not the same thing as her mood right now, and
            # this is the only place on this path that can supply the latter.
            from mcpserver.screen_vision.proactive import _mood_text, current_mood

            mood_text = _mood_text(current_mood())
            if mood_text:
                prompt = f"{prompt}\n\n【她此刻的状态】\n{mood_text}"
        except Exception:  # noqa: BLE001
            logger.debug("[主动聊天] 读取当前形态/情绪失败", exc_info=True)
        return prompt

    async def _check_presence_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """Greet a return or note a departure, driven by derived signals only.

        The tracker raises ``transition`` exactly once per real state change, so
        this path never repeats itself for a single arrival or departure.
        """
        try:
            from mcpserver.screen_vision.proactive import get_camera_bridge

            if get_camera_bridge().running:
                return None
        except Exception:
            pass
        config = self._camera_aware_config.get("presence") or {}
        if not config.get("enabled", True):
            return None
        notify_on = {str(item) for item in config.get("notify_on", ["returned"])}
        try:
            from core.camera_control import read_state
            from mcpserver.screen_vision.presence import get_presence_tracker

            camera_state = read_state()
            tracker = get_presence_tracker()
            snapshot = tracker.snapshot()
            # `snapshot.transition` is overwritten by the very next evaluation, so
            # a 45-second poll saw an arrival only if it happened to land inside
            # the same window - the log shows a handful of hits that were luck,
            # not mechanism. `last_transition()` keeps the change (and the moment
            # it happened) until the next real one.
            transition, transition_at = tracker.last_transition()
        except Exception:
            return None
        # Presence messages stay behind the same consent gate as camera events.
        if not camera_state.get("autonomous") or camera_state.get("mode") == "off":
            return None
        transition = str(transition or "")
        if transition not in notify_on or not transition_at:
            return None
        confidence = float(snapshot.confidence or 0)
        if confidence < float(config.get("min_confidence", 0.5)):
            return None
        # Keyed on *when* the change happened, not on how long ago a face was last
        # seen. `last_face_seconds` is small by construction whenever "returned" is
        # produced (a return means a face was just detected), so the key was always
        # "returned:0" - and because it was written before delivery, one rejected
        # greeting closed this path for the rest of the process.
        transition_key = f"{transition}:{round(float(transition_at), 3)}"
        if transition_key == getattr(self, "_last_presence_key", ""):
            return None
        # Throttling, quiet hours and de-duplication belong to the unified
        # coordinator, which every background source now passes through. Keeping a
        # second copy of those rules here is how the camera ended up governed by
        # limits nothing else obeyed.
        topic = "佳刚回到电脑前" if transition == "returned" else "佳暂时离开了电脑"
        prompt = (
            f"你是弥娅。摄像头判断：{snapshot.describe()}（依据：{'、'.join(snapshot.reasons) or '视觉线索'}）\n"
            f"请对佳说一句自然的话，围绕{topic}，不超过25字。"
            "如果不确定或此刻不适合说话，回复 SKIP。"
        )
        # What she remembers about him, so a greeting can land on something real
        # ("又熬夜了？") instead of being generated from the sensor line alone.
        # The bridge recalls memory for its presence events; this path, which is
        # the one that actually got a line out, did not.
        try:
            from mcpserver.screen_vision.proactive import recall_relevant

            memory_note = await recall_relevant(
                f"佳 {'回到' if transition == 'returned' else '离开'}电脑前 最近对话 兴趣 话题"
            )
            if memory_note:
                prompt = f"{prompt}\n\n{memory_note}"
        except Exception:  # noqa: BLE001 - memory is an enrichment, not a requirement
            logger.debug("[主动聊天] 在场事件召回记忆失败", exc_info=True)
        try:
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=self._camera_persona_prompt(prompt))],
                tools=[], tool_choice="none",
            )
            message = str(response or "").strip()
        except Exception:
            return None
        if message.upper().startswith("SKIP") or len(message) < 2:
            return None
        if self._check_message_content_duplicate(target_id, message) or self._is_duplicate(target_id, message):
            return None
        self._last_presence_key = transition_key
        self._record_trigger(target_id)
        self._record_trigger_by_type(target_id, "camera_aware")
        self._record_sent_message(target_id, message)
        # Bookkeeping for a message that may still be refused downstream. Without
        # this, one throttled greeting marked the arrival as already-greeted and
        # she stayed silent about it for the rest of the process.
        return ProactiveResult(True, message, "camera_aware", context,
                               rollback=lambda: self._forget_presence_proposal(target_id, transition_key, message),
                               coordination_key=f"camera:presence:{transition_key}")

    def _forget_presence_proposal(self, target_id: int, transition_key: str, message: str) -> None:
        """Undo the bookkeeping of a presence greeting that never went out."""
        if getattr(self, "_last_presence_key", "") == transition_key:
            self._last_presence_key = ""
        self._forget_message_proposal(target_id, message)

    async def _check_activity_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """React to a change in what Jia is doing, if the model judges it worth it.

        The activity tracker decides *what* changed; the model decides *whether*
        to speak - there is no duration threshold in the code, because "he has
        been typing for ninety minutes" is a judgement, not a rule. That makes
        this the single place Miya decides whether to talk about what he is
        doing: the camera bridge only remembers it.

        She decides with everything she perceives - presence, the accumulated
        activity, her own watching notes, the conversation, how she feels - not
        with the one line the tracker produced.
        """
        config = self._camera_aware_config.get("activity") or {}
        if not config.get("enabled", True):
            return None
        try:
            from core.camera_control import read_state
            from mcpserver.screen_vision.activity import activity_change_card

            camera_state = read_state()
        except Exception:
            return None
        if not camera_state.get("autonomous") or camera_state.get("mode") == "off":
            return None
        card = activity_change_card()
        if not card:
            return None
        # Throttling belongs to the unified coordinator now; the local interval and
        # trigger-type cooldown were a second, divergent set of rules.
        deep_context = self._build_deep_context(context)
        # Memory, for the same reason the reply path has it: deciding whether to
        # speak about a change is a judgement about a person, and it goes wrong
        # without anything to judge against. `_build_deep_context` carries the
        # senses; this carries what she remembers.
        try:
            from mcpserver.screen_vision.proactive import recall_relevant

            memory_note = await recall_relevant(str(card)[:120] or "佳 电脑前 活动")
            if memory_note:
                deep_context = f"{deep_context}\n{memory_note}"
        except Exception:  # noqa: BLE001
            logger.debug("[主动聊天] 活动事件召回记忆失败", exc_info=True)
        prompt = (
            "你是弥娅，正陪在佳身边。下面是近期背景，旧对话和记忆不是当前画面证据：\n"
            f"{deep_context}\n\n"
            f"{card}\n"
            "他刚刚的这个变化，你要不要开口？像一个人那样判断，而不是像告警器："
            "他在专心、他刚被打断、他明确说过累了或想休息、或者这句话现在说出来只是打扰——"
            "那就不说，只回复 SKIP。什么时候开口、说什么都由你定。"
            "要开口就用一句不超过 25 字的自然口语，语气贴合你当下的形态；"
            "不要把静坐、歪头、张嘴或看起来没动当成困倦、缺水或需要纠正坐姿；"
            "没有佳明确表达时，不要自动安排喝水、睡觉、吃饭或其他生活指导。"
            "不要说摄像头、识别、置信度这类字眼，也不要报流水账。"
        )
        try:
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=self._camera_persona_prompt(prompt))],
                tools=[], tool_choice="none",
            )
            message = str(response or "").strip()
        except Exception:
            return None
        if message.upper().startswith("SKIP") or len(message) < 2:
            # The model declined, but the change is still news for later context,
            # so it is deliberately not consumed here.
            return None
        if self._check_message_content_duplicate(target_id, message) or self._is_duplicate(target_id, message):
            return None
        self._record_trigger(target_id)
        self._record_trigger_by_type(target_id, "camera_aware")
        self._record_sent_message(target_id, message)
        return ProactiveResult(
            True, message, "camera_aware", context,
            rollback=lambda: self._forget_camera_proposal(target_id, message),
            # The change was only peeked at, so it is used up on the way out.
            on_delivered=self._consume_activity_change,
        )

    @staticmethod
    def _consume_activity_change() -> None:
        """Mark the peeked activity change as reported, once it really went out."""
        try:
            from mcpserver.screen_vision.activity import take_activity_change

            take_activity_change()
        except Exception:  # noqa: BLE001 - consuming is best effort
            logger.debug("[主动聊天] 取走活动变化失败", exc_info=True)

    def _forget_camera_proposal(self, target_id: int, message: str) -> None:
        """Undo the bookkeeping of a camera line that never went out.

        The activity change is consumed on the way out rather than on the way in:
        consuming it at proposal time destroyed the observation even when the
        coordinator refused the message, so a change nobody ever heard about could
        not be offered again.
        """
        self._forget_message_proposal(target_id, message)

    async def _check_miya_vision_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """Use what Miya herself decided was worth saying while watching.

        This is the end of the chain: Miya chose when to look, interpreted the
        frame with her own mind, judged it notable, and wrote the sentence. The
        code here only delivers it - it does not second-guess the wording.

        Delivery goes through the unified coordinator, which owns throttling,
        quiet hours and de-duplication. Her line is only removed from the queue
        once the coordinator has actually taken it, so a rejected message is not
        silently destroyed.
        """
        config = self._camera_aware_config.get("agency") or {}
        if not config.get("enabled", True):
            return None
        try:
            from core.camera_control import read_state
            from mcpserver.screen_vision.vision_agent import get_vision_agent

            camera_state = read_state()
        except Exception:
            return None
        if not camera_state.get("autonomous") or camera_state.get("mode") == "off":
            return None
        agent = get_vision_agent()
        pending = agent.peek_messages()
        if not pending:
            return None
        now = time.time()
        earliest = pending[0]
        if now - float(earliest.get("at", now)) > float(config.get("max_age_seconds", 600)):
            # Stale by the time she could say it; drop rather than blurt it out.
            agent.take_message()
            return None
        pending_faces = earliest.get("faces")
        if pending_faces is not None:
            pending_at = float(earliest.get("at") or 0.0)
            newer_presence: tuple[float, bool] | None = None
            try:
                from mcpserver.screen_vision.vision_stream import get_vision_stream

                latest = get_vision_stream().latest() or {}
                latest_at = float(latest.get("at") or 0.0)
                latest_faces = (latest.get("reading") or {}).get("faces")
                if latest_at > pending_at and latest_faces is not None:
                    newer_presence = (latest_at, bool(latest_faces))
            except Exception:
                logger.debug("[主动聊天] 复核视觉话术新鲜度失败", exc_info=True)
            try:
                from mcpserver.screen_vision.presence import get_presence_tracker

                snapshot = get_presence_tracker().snapshot()
                snapshot_at = float(getattr(snapshot, "updated_at", 0.0) or 0.0)
                state = str(getattr(snapshot, "state", "") or "")
                if snapshot_at > pending_at:
                    if state in {"present", "at_desk"}:
                        candidate = (snapshot_at, True)
                    elif state in {"away", "left"}:
                        candidate = (snapshot_at, False)
                    else:
                        candidate = None
                    if candidate and (newer_presence is None or candidate[0] >= newer_presence[0]):
                        newer_presence = candidate
            except Exception:
                logger.debug("[主动聊天] 读取在场状态失败", exc_info=True)
            if newer_presence is not None and newer_presence[1] != bool(pending_faces):
                agent.take_message()
                logger.info(
                    "[主动聊天] 丢弃过期视觉话术: faces=%s -> faces=%s",
                    pending_faces,
                    int(newer_presence[1]),
                )
                return None
        message = str(earliest.get("message") or "").strip()
        if len(message) < 2:
            agent.take_message()
            return None
        # Only the *read-only* history check here. `_is_duplicate` both checks and
        # records, so calling it before delivery meant a refused line was marked as
        # already-said; the next poll (45s later, inside its 90s window) then saw
        # it as a duplicate and destroyed it. Everything she decided to say died on
        # the first rejection, which is why the log filled with rising
        # `camera:voice:...:N` sequence numbers and not one delivered line.
        if self._check_message_content_duplicate(target_id, message):
            # This one really was said before, so dropping it is correct.
            agent.take_message()
            return None
        # Ask the one coordinator first; only then does her line leave the queue.
        delivered = await self._deliver_via_coordinator(
            target_id, message, context, fact_key=str(earliest.get("at") or "")
        )
        if not delivered:
            return None
        logger.info("[主动聊天] [弥娅自主视觉] target=%s: %s", target_id, message)
        # Already delivered above, through the one coordinator. Saying so keeps the
        # background loop from handing the same line to the send outlet a second
        # time and calling it sent when the coordinator refused it.
        return ProactiveResult(True, message, "camera_aware", context, delivered=True)

    async def _deliver_via_coordinator(
        self,
        target_id: int,
        message: str,
        context: ChatContext,
        *,
        fact_key: str = "",
    ) -> bool:
        """Send one already-decided line through the unified proactive coordinator.

        Falls back to the ordinary trigger bookkeeping when the coordinator is not
        wired up, so this never becomes a silent dead end.

        ``fact_key`` identifies *this line*; a retry of the same line must present
        the same key, or the coordinator's own cooldown cannot recognise it.
        """
        from core.proactive_coordinator import get_proactive_coordinator

        coordinator = get_proactive_coordinator()
        if coordinator is None:
            return False
        platform = getattr(context, "platform", "terminal") or "terminal"
        chat_type = getattr(context, "chat_type", "private") or "private"
        # One line, one stable key. A per-attempt counter used to make every retry
        # look like a fresh event, so whether it went out depended only on how much
        # of the hourly budget was left.
        identity = fact_key or str(int(time.time()))
        ok = await coordinator.submit_message(
            message,
            key=f"camera:voice:{target_id}:{identity}",
            target_id=str(target_id),
            chat_type=chat_type,
            platform=platform,
            trigger_type="camera_aware",
            # Grouped with the camera's own presence events rather than with
            # proactive_chat: they are both things Miya saw.
            source="camera",
            # A line she already decided to say is her voice, not a state change;
            # the two draw on separate budgets so her small talk cannot starve the
            # one event that actually matters.
            kind="voice",
        )
        if not ok:
            return False
        try:
            from mcpserver.screen_vision.vision_agent import get_vision_agent

            get_vision_agent().take_message()
        except Exception:
            logger.debug("[主动聊天] 取走已发送的观察消息失败", exc_info=True)
        self._record_trigger(target_id)
        self._record_trigger_by_type(target_id, "camera_aware")
        self._record_sent_message(target_id, message)
        # Now that it really went out, it is fair to remember it as said.
        self._remember_message(target_id, message)
        return True

    async def _check_context_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """上下文触发 - 行为期望跟进（AI 优先）"""
        expectations_config = self._context_config.get("expectations", self._context_config)
        if not expectations_config.get("enabled", True):
            return None

        user_expectation = context.user_expectation or self._last_expectation.get(target_id)
        if not user_expectation:
            return None

        follow_responses = expectations_config.get("follow_responses", {})
        fallback_msgs = follow_responses.get(user_expectation, follow_responses.get("default", []))

        if not self._check_trigger_type_cooldown(target_id, "context"):
            return None

        message = await self._generate_and_fallback(
            "context",
            {"expectation": user_expectation},
            fallback_msgs,
            target_id,
        )
        if not message:
            return None

        if self._check_message_content_duplicate(target_id, message):
            return None

        if not self._is_duplicate(target_id, message):
            self._record_trigger(target_id)
            self._record_trigger_by_type(target_id, "context")
            self._record_sent_message(target_id, message)

            if target_id in self._last_expectation:
                del self._last_expectation[target_id]
            context.user_expectation = None

            if self._log_triggers:
                logger.info(f"[主动聊天] [上下文触发] target={target_id}: {message}")

            return ProactiveResult(
                should_respond=True,
                message=message,
                trigger_type="context",
                context=context,
            )

        return None

    async def _check_emotion_trigger(
        self, target_id: int, context: ChatContext, user_message: str
    ) -> Optional[ProactiveResult]:
        """情绪感知触发（AI 优先）"""
        emotion = context.detected_emotion
        if not emotion:
            return None

        emotion_responses = self._emotion_config.get("emotion_responses", {})
        fallback_msgs = emotion_responses.get(emotion, [])

        if random.random() > 0.3:
            return None

        if not self._check_trigger_type_cooldown(target_id, "emotion"):
            return None

        message = await self._generate_and_fallback(
            "emotion",
            {"emotion": emotion},
            fallback_msgs,
            target_id,
        )
        if not message:
            return None

        if self._check_message_content_duplicate(target_id, message):
            return None

        if not self._is_duplicate(target_id, message):
            self._record_trigger(target_id)
            self._record_trigger_by_type(target_id, "emotion")
            self._record_sent_message(target_id, message)

            context.detected_emotion = None

            if self._log_triggers:
                logger.info(f"[主动聊天] [情绪触发] target={target_id}, emotion={emotion}: {message}")

            return ProactiveResult(
                should_respond=True,
                message=message,
                trigger_type="emotion",
                context=context,
            )

        return None

    async def _check_keyword_trigger(
        self, target_id: int, context: ChatContext, user_message: str
    ) -> Optional[ProactiveResult]:
        """关键词触发（AI 优先）"""
        keywords = self._keyword_config.get("keywords", [])
        matched = [kw for kw in keywords if kw in user_message]

        if not matched:
            return None

        if self._log_triggers:
            logger.info(f"[主动聊天] [关键词触发] target={target_id}, matched={matched}")

        fallback_msgs = self._keyword_config.get("responses", [])
        if not fallback_msgs:
            fallback_msgs = ["嗯呢，收到啦~"]

        if not self._check_trigger_type_cooldown(target_id, "keyword"):
            return None

        message = await self._generate_and_fallback(
            "keyword",
            {"keywords": ", ".join(matched)},
            fallback_msgs,
            target_id,
        )
        if not message:
            return None

        if self._check_message_content_duplicate(target_id, message):
            return None

        if not self._is_duplicate(target_id, message):
            self._record_trigger(target_id)
            self._record_trigger_by_type(target_id, "keyword")
            self._record_sent_message(target_id, message)
            return ProactiveResult(
                should_respond=True,
                message=message,
                trigger_type="keyword",
                context=context,
            )

        return None

    async def _check_time_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """时间触发 - 多时段问候（AI 优先）"""
        now = datetime.now()
        hour = now.hour

        greetings = self._time_config.get("greetings", {})

        messages = []
        time_period = "深夜"

        if 6 <= hour < 12:
            messages = greetings.get("morning", {}).get("messages", [])
            time_period = "早上"
        elif 12 <= hour < 14:
            messages = greetings.get("noon", {}).get("messages", [])
            if not messages:
                messages = greetings.get("afternoon", {}).get("messages", [])
            time_period = "中午"
        elif 14 <= hour < 18:
            messages = greetings.get("afternoon", {}).get("messages", [])
            time_period = "下午"
        elif 18 <= hour < 22:
            messages = greetings.get("evening", {}).get("messages", [])
            time_period = "傍晚"

        if not self._check_trigger_type_cooldown(target_id, "time"):
            return None

        message = await self._generate_and_fallback(
            "time",
            {"time_period": time_period},
            messages,
            target_id,
        )
        if not message:
            return None

        if self._check_message_content_duplicate(target_id, message):
            return None

        if not self._is_duplicate(target_id, message):
            self._record_trigger(target_id)
            self._record_trigger_by_type(target_id, "time")
            self._record_sent_message(target_id, message)

            if self._log_triggers:
                logger.info(f"[主动聊天] [时间触发] target={target_id}: {message}")

            return ProactiveResult(
                should_respond=True,
                message=message,
                trigger_type="time",
                context=context,
            )

        return None

    async def _check_check_in_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """主动关怀触发（AI 优先）"""
        check_in_config = self._check_in_config
        check_interval = check_in_config.get("check_interval", 3600)

        last_interaction = self._user_last_interaction.get(target_id)
        idle_seconds = 0
        idle_duration = "一段时间"
        if last_interaction:
            idle_seconds = (datetime.now() - last_interaction).total_seconds()
            if idle_seconds < check_interval:
                return None
            if idle_seconds < 3600:
                idle_duration = f"{int(idle_seconds // 60)}分钟"
            else:
                idle_duration = f"{int(idle_seconds // 3600)}小时"

        if random.random() > 0.2:
            return None

        fallback_msgs = check_in_config.get("messages", [])

        if not self._check_trigger_type_cooldown(target_id, "check_in"):
            return None

        message = await self._generate_and_fallback(
            "check_in",
            {"idle_duration": idle_duration},
            fallback_msgs,
            target_id,
        )
        if not message:
            return None

        if self._check_message_content_duplicate(target_id, message):
            return None

        if not self._is_duplicate(target_id, message):
            self._record_trigger(target_id)
            self._record_trigger_by_type(target_id, "check_in")
            self._record_sent_message(target_id, message)

            if self._log_triggers:
                logger.info(f"[主动聊天] [关怀触发] target={target_id}: {message}")

            return ProactiveResult(
                should_respond=True,
                message=message,
                trigger_type="check_in",
                context=context,
            )

        return None

    async def _check_ai_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """AI触发"""
        if not self.ai_client:
            return None

        ai_config = self._ai_config
        cooldown = ai_config.get("cooldown", 300)

        last_time = self._last_trigger_time.get(target_id)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < cooldown:
                return None

        try:
            chat_type = "群聊" if context.chat_type == "group" else "私聊"
            group_name = context.group_name or "未知群"
            member_count = context.member_count
            last_active = context.last_active or "未知"
            recent_topics = ", ".join(context.recent_topics) if context.recent_topics else "无"

            persona = self._build_persona_context()
            memory_context = self._build_memory_context(target_id)
            rich_context = await self._build_rich_context(target_id)
            scene_context = self._build_deep_context(context) if self._scene_enabled else ""
            screen_ctx = self._build_screen_context() or ""
            if screen_ctx:
                logger.info(f"[主动聊天] AI决策包含弥娅之眼: {screen_ctx[:120]}...")

            memory_empty = self._load_text_config("scene.memory_empty", "（无近期对话记录）")
            group_warning = (
                self._load_text_config("scene.group_warning", "")
                if context.chat_type == "group" and self._scene_enabled
                else ""
            )

            # 构建系统 prompt
            system_prompt = ""
            if self._prompt_manager:
                system_prompt = self._prompt_manager.get_system_prompt() or ""
            if self.personality:
                status = self.personality.get_status_for_prompt()
                if status:
                    system_prompt = status + "\n\n" + system_prompt

            # 注入弥娅刚才的回复，让 AI 知道已经回应过了，避免重复
            last_reply_hint = ""
            if context.last_miya_reply:
                last_reply_short = context.last_miya_reply[:100]
                last_reply_hint = f"\n弥娅刚刚回复了用户（内容摘要: {last_reply_short}），不需要再回复相同话题。\n"

            now = datetime.now()
            current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            hour = now.hour
            if 5 <= hour < 12:
                period_str = "上午"
            elif 12 <= hour < 14:
                period_str = "中午"
            elif 14 <= hour < 18:
                period_str = "下午"
            elif 18 <= hour < 22:
                period_str = "晚上"
            else:
                period_str = "深夜"

            last_active_readable = "未知"
            if last_active and last_active != "未知":
                try:
                    last_dt = datetime.fromisoformat(last_active)
                    elapsed = (now - last_dt).total_seconds()
                    if elapsed < 60:
                        last_active_readable = f"{int(elapsed)}秒前"
                    elif elapsed < 3600:
                        last_active_readable = f"{int(elapsed // 60)}分钟前"
                    elif elapsed < 86400:
                        last_active_readable = f"{int(elapsed // 3600)}小时前"
                    else:
                        last_active_readable = f"{int(elapsed // 86400)}天前"
                except (ValueError, TypeError):
                    last_active_readable = str(last_active)[:19]

            prompt = f"""判断是否应该主动和用户聊天。
【当前时间: {current_time_str} ({period_str})】
【形态: {persona}】

{screen_ctx}————— 以上是弥娅刚才在屏幕上看到的内容，请参考这些信息理解用户的状态 —————

智能记忆检索：
{rich_context or "（无相关记忆）"}

当前对话状态：
{memory_context or memory_empty}

场景信息：
{scene_context}

聊天信息：
- 类型: {chat_type}
- 群名称: {group_name}
- 成员数: {member_count}
- 用户最后活跃: {last_active_readable}
- 最近话题: {recent_topics}
{last_reply_hint}
{group_warning}如果需要回复，请以符合上述人设质感生成一句简短温暖的话（不超过20字）。
如果不需要回复，请回复"SKIP"。"""

            messages = []
            if system_prompt:
                messages.append(AIMessage(role="system", content=system_prompt))
            messages.append(AIMessage(role="user", content=prompt))

            response = await self.ai_client.chat(
                messages=messages,
                tool_choice="none",
            )

            # response 直接是字符串，不需要 .get() 解析
            message = response.strip() if isinstance(response, str) else str(response).strip()

            if message.upper() == "SKIP" or not message:
                return None

            # 检查同类型触发冷却
            if not self._check_trigger_type_cooldown(target_id, "ai"):
                return None

            # 检查消息内容是否重复
            if self._check_message_content_duplicate(target_id, message):
                return None

            if not self._is_duplicate(target_id, message):
                self._record_trigger(target_id)
                self._record_trigger_by_type(target_id, "ai")
                self._record_sent_message(target_id, message)

                if self._log_triggers:
                    logger.info(f"[主动聊天] [AI触发] target={target_id}: {message}")

                return ProactiveResult(
                    should_respond=True,
                    message=message,
                    trigger_type="ai",
                    context=context,
                )

        except Exception as e:
            logger.warning(f"[主动聊天] AI触发失败: {e}")

        return None

    # ============================================================
    # 意图持续机制
    # ============================================================

    def _cache_text_configs(self) -> None:
        try:
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            pc = cfg.get("proactive_chat", {})

            self._topic_keywords = pc.get("topic_keywords", [])
            expectation_cfg = pc.get("expectation", {})
            self._expectation_detect_prompt = expectation_cfg.get("detect_prompt", "")
            continuity = pc.get("continuity", {})
            self._intent_summaries = continuity.get("intent_summaries", {})
            self._continuity_default_prompt = continuity.get("default_prompt", "")
            self._continuity_classify_prompt = continuity.get("classify_prompt", "")
            self._verbal_fallback_prompt = continuity.get("verbal_fallback_prompt", "")
            self._actional_fallback_prompt = continuity.get("actional_fallback_prompt", "")
            screen_aware = pc.get("screen_aware", {})
            self._screen_aware_judge_prompt = screen_aware.get("judge_prompt", "")
            self._screen_aware_gen_prompt = screen_aware.get("gen_prompt", "")
        except Exception as e:
            logger.debug(f"[主动聊天] text_config 缓存失败: {e}")
            self._topic_keywords = []
            self._expectation_detect_prompt = ""
            self._intent_summaries = {}
            self._continuity_default_prompt = ""
            self._continuity_classify_prompt = ""
            self._verbal_fallback_prompt = ""
            self._actional_fallback_prompt = ""
            self._screen_aware_judge_prompt = ""
            self._screen_aware_gen_prompt = ""

    def set_tool_registry(self, registry_callback: callable) -> None:
        self._tool_registry = registry_callback
        logger.info("[主动聊天] ToolRegistry 已注入")

    def set_proactive_tool_context(self, context_provider: callable) -> None:
        self._proactive_tool_context_provider = context_provider

    async def _detect_pending_intent(self, response: str, user_message: str = "") -> Optional[dict]:
        if not response or len(response.strip()) < 2:
            return None
        return await self._ai_classify_intent(response, user_message)

    async def _ai_classify_intent(self, response: str, user_message: str = "") -> Optional[dict]:
        if not self.ai_client:
            return None
        prompt_template = self._continuity_classify_prompt
        if not prompt_template:
            logger.info("[意图检测] classify_prompt 为空，跳过")
            return None
        try:
            prompt = prompt_template.format(response=response, user_message=user_message)
            response_text = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=prompt)],
                tools=[],
                tool_choice="none",
            )
            if not response_text:
                return None
            import json

            text = str(response_text).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(text)
            if result.get("has_pending"):
                return {
                    "intent_type": result.get("intent_type", "casual"),
                    "progression_type": result.get("progression_type", "verbal"),
                }
        except Exception as e:
            logger.debug(f"[意图检测] AI 分类失败: {e}")
        return None

    async def detect_and_register_intent(
        self, target_id: int, chat_type: str, platform: str, miya_response: str, user_message: str = ""
    ) -> bool:
        if not self._continuity_enabled or not miya_response:
            logger.info(f"[意图持续] 跳过: enabled={self._continuity_enabled} resp_len={len(miya_response or '')}")
            return False
        if target_id in self._pending_intents:
            logger.info(f"[意图持续] 跳过: 已有 pending intent target={target_id}")
            return False
        logger.info(f"[意图持续] 开始检测 intent target={target_id} resp={miya_response[:40]}...")
        intent_info = await self._detect_pending_intent(miya_response, user_message)
        if not intent_info:
            logger.info(f"[意图持续] AI 判断无 pending intent: target={target_id}")
            return False
        context_summary = self._build_intent_summary(intent_info["intent_type"], miya_response)
        self._intent_id_counter += 1
        intent = IntentState(
            intent_id=f"continuity_{self._intent_id_counter}",
            target_id=target_id,
            chat_type=chat_type,
            platform=platform,
            intent_type=intent_info["intent_type"],
            progression_type=intent_info["progression_type"],
            context_summary=context_summary,
            max_extra_turns=self._continuity_max_turns,
            original_response=miya_response,
        )
        self._pending_intents[target_id] = intent
        logger.info(
            f"[意图持续] 注册: {intent.intent_type}/{intent.progression_type} "
            f'target={target_id} max_turns={intent.max_extra_turns} resp="{miya_response[:30]}..."'
        )
        intent._task = asyncio.create_task(self._run_continuity_loop(intent))
        logger.info(f"[意图持续] 定时器已启动: {intent.intent_id}")
        return True

    async def _run_continuity_loop(self, intent: IntentState) -> None:
        try:
            while intent.turns_taken < intent.max_extra_turns:
                delay = random.uniform(self._continuity_min_delay, self._continuity_max_delay)
                await asyncio.sleep(delay)
                if intent.paused:
                    continue
                if intent.turns_taken >= intent.max_extra_turns:
                    break
                if not self._enabled or not self._continuity_enabled or self._is_in_quiet_hours():
                    continue
                message = await self._execute_continuation(intent)
                if not message:
                    logger.info(f"[意图持续] AI返回SKIP: {intent.intent_id}")
                    break
                if self._send_callback:
                    try:
                        sent = await self._send_callback(
                            message,
                            intent.target_id,
                            intent.chat_type,
                            intent.platform,
                            intent.intent_type,  # intent_type = comfort/task/reminder...
                        )
                        if not delivery_accepted(sent):
                            logger.info("[意图持续] 投递未接受: %s", intent.intent_id)
                            break
                        intent.turns_taken += 1
                        intent.last_continuation = datetime.now()
                        intent.continuation_history.append(message)
                        logger.info(
                            f"[意图持续] [{intent.intent_type}/{intent.progression_type}] "
                            f"推进 #{intent.turns_taken}: {message[:50]}"
                        )
                    except Exception as e:
                        logger.error(f"[意图持续] 发送回调失败: {e}")
                        break
                else:
                    logger.warning(f"[意图持续] 无发送回调: {message[:50]}")
                    break
            logger.info(
                f"[意图持续] 循环结束: {intent.intent_id} "
                f"({intent.intent_type}/{intent.progression_type}, {intent.turns_taken}/{intent.max_extra_turns} 轮)"
            )
        except asyncio.CancelledError:
            logger.info(f"[意图持续] 循环已取消: {intent.intent_id}")
        finally:
            if intent.target_id in self._pending_intents:
                self._pending_intents.pop(intent.target_id, None)

    async def _execute_continuation(self, intent: IntentState) -> Optional[str]:
        if intent.progression_type == "actional":
            return await self._execute_actional_continuation(intent)
        else:
            return await self._execute_verbal_continuation(intent)

    async def _execute_verbal_continuation(self, intent: IntentState) -> Optional[str]:
        if not self.ai_client:
            return None
        prompt_template = self._continuity_config.get("system_prompt", self._default_continuity_prompt())
        persona = self._build_persona_context()
        meta = self._build_memory_context(intent.target_id)
        rich = await self._build_rich_context(intent.target_id)
        memory = f"{rich}\n{meta}".strip() if rich else meta

        cached_ctx = self._context_cache.get(intent.target_id)
        user_last_msg = ""
        if cached_ctx and cached_ctx.recent_topics:
            user_last_msg = ", ".join(cached_ctx.recent_topics)

        ctx = {
            "persona": persona,
            "memory": memory,
            "original_response": intent.original_response,
            "context_summary": intent.context_summary,
            "intent_type": intent.intent_type,
            "turn_number": intent.turns_taken + 1,
            "max_turns": intent.max_extra_turns,
        }
        try:
            prompt = prompt_template.format(**ctx)
        except (KeyError, ValueError):
            prompt = self._verbal_fallback_prompt.format(**ctx) if self._verbal_fallback_prompt else ""
        final_prompt = prompt
        if not final_prompt:
            return None
        if memory:
            final_prompt = f"【当前对话】\n{memory}\n\n{prompt}"
        if intent.continuation_history:
            history_text = "\n".join(f"- 弥娅: {h[:60]}" for h in intent.continuation_history)
            final_prompt += f"\n\n【已发送的持续推进消息】\n{history_text}\n（不要重复）"
        if user_last_msg:
            final_prompt += (
                f"\n\n【提醒】用户当前只是在进行日常闲聊。他最后一句话的话题是：{user_last_msg}。"
                f"不要带上之前对话的旧情绪。保持日常温柔的语气，不要过度解读用户的意图。"
            )
        try:
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=final_prompt)],
                tools=[],
                tool_choice="none",
            )
            message = str(response).strip() if response else ""
            if message.upper() == "SKIP" or not message:
                return None
            return message
        except Exception as e:
            logger.warning(f"[意图持续] 语言推进失败: {e}")
            return None

    async def _execute_actional_continuation(self, intent: IntentState) -> Optional[str]:
        if not self.ai_client:
            return None
        meta = self._build_memory_context(intent.target_id)
        rich = await self._build_rich_context(intent.target_id)
        memory = f"{rich}\n{meta}".strip() if rich else meta
        persona = self._build_persona_context()
        fallback = self._actional_fallback_prompt
        if not fallback:
            return None
        fallback = fallback.format(
            original_response=intent.original_response,
            context_summary=intent.context_summary,
            turn_number=intent.turns_taken + 1,
            max_turns=intent.max_extra_turns,
        )
        parts = []
        if persona:
            parts.append(f"【当前人设】\n{persona}\n")
        parts.append(fallback)
        if intent.continuation_history:
            parts.append("")
            parts.append("【已发送的持续推进消息】")
            for h in intent.continuation_history:
                parts.append(f"- 弥娅: {h[:60]}")
            parts.append("（不要重复）")
        final_prompt = "\n".join(parts)
        if memory:
            final_prompt = f"【当前对话】\n{memory}\n\n{final_prompt}"
        if self._proactive_tool_context_provider:
            try:
                ctx = self._proactive_tool_context_provider(intent.target_id)
                if ctx:
                    self.ai_client.set_tool_context(ctx)
            except Exception as e:
                logger.debug(f"[意图持续] 工具上下文设置失败: {e}")
        if self._tool_registry:
            self.ai_client.set_tool_registry(self._tool_registry)
        try:
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=final_prompt)],
                tools=None,
                tool_choice="auto",
            )
            message = str(response).strip() if response else ""
            self.ai_client.set_tool_registry(lambda: [])
            self.ai_client.set_tool_context({})
            if message.upper() == "SKIP" or not message:
                return None
            return message
        except Exception as e:
            logger.warning(f"[意图持续] 行动推进失败: {e}")
            try:
                self.ai_client.set_tool_registry(lambda: [])
                self.ai_client.set_tool_context({})
            except Exception:
                pass
            return None

    def _build_intent_summary(self, intent_type: str, response: str) -> str:
        base = self._intent_summaries.get(intent_type, intent_type) if self._intent_summaries else intent_type
        return f"{base}（回复: {response[:50]}）"

    def _default_continuity_prompt(self) -> str:
        return self._continuity_default_prompt or ""

    def pause_intent(self, target_id: int) -> None:
        intent = self._pending_intents.get(target_id)
        if intent:
            intent.paused = True
            logger.info(f"[意图持续] 暂停: {intent.intent_id}")

    def resume_intent(self, target_id: int) -> None:
        intent = self._pending_intents.get(target_id)
        if intent:
            intent.paused = False
            logger.info(f"[意图持续] 恢复: {intent.intent_id}")

    def clear_intent(self, target_id: int) -> None:
        if target_id in self._pending_intents:
            intent = self._pending_intents.pop(target_id)
            if intent._task and not intent._task.done():
                intent._task.cancel()
            logger.info(f"[意图持续] 清除: {intent.intent_id}")

    async def _check_screen_aware_trigger(self, target_id: int, context: ChatContext) -> Optional[ProactiveResult]:
        """屏幕感知触发 — 让弥娅的 AI 自己判断是否开口

        不再用死阈值。把看到的内容注入 AI prompt，让弥娅综合判断。
        """
        if not self.is_trigger_enabled("screen_aware"):
            return None
        intent = self._last_screen_intent
        if intent is None:
            return None

        # 活动没变化且上次 AI 判断不建议开口 → 跳过
        if intent.priority < 0.20 and intent.trigger_type != "activity_change":
            return None

        if not self._check_trigger_type_cooldown(target_id, "screen_aware"):
            return None

        try:
            screen_ctx = self._build_screen_context()
            if not screen_ctx:
                return None

            deep_ctx = self._build_deep_context(context)

            judge_prompt_template = self._screen_aware_judge_prompt or (
                "你是弥娅，一个温柔体贴的 AI 虚拟化身。佳是你最重要的人。\n\n"
                "当前情况：\n{deep_ctx}\n\n"
                "请判断是否应该主动和佳说话。考虑以下因素：\n"
                "- 佳正在做什么？现在适合打扰他吗？\n"
                "- 距离上次互动有多久了？\n"
                "- 佳的状态如何？需要关心吗？\n"
                "- 有没有什么值得评论或关心的事情（比如佳刚切换了活动、连续工作了很久等）？\n\n"
                '请用 JSON 回复：{{"should_speak": true/false, '
                '"reason": "简短理由(10字内)", "mood": "温柔/兴奋/关心/好奇/安静"}}\n'
                "只返回JSON，不要其他内容。"
            )
            judge_prompt = judge_prompt_template.replace("{deep_ctx}", deep_ctx)

            judge_result = await self._ai_judge(judge_prompt)
            if not judge_result or not judge_result.get("should_speak", False):
                return None

            # AI 判定要说话 → 生成消息
            mood = judge_result.get("mood", "casual")
            reason = judge_result.get("reason", "")

            screen_desc = screen_ctx.replace("[弥娅的视觉感知]\n", "")
            gen_prompt_template = self._screen_aware_gen_prompt or (
                "你是弥娅。你用{mood}的语气，对佳说一句话。\n\n"
                "你看到的情况：\n{screen_desc}\n\n"
                "你想表达的情绪: {mood}\n"
                "想说的原因: {reason}\n\n"
                "要求：简短自然（不超过30字），像真实的伴侣一样说话。只回复一句话。"
            )
            gen_prompt = (
                gen_prompt_template.replace("{mood}", mood)
                .replace("{screen_desc}", screen_desc)
                .replace("{reason}", reason)
            )

            # 直接用 AI 生成消息
            gen_response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=gen_prompt)],
                tools=[],
                tool_choice="none",
            )
            message = str(gen_response).strip() if gen_response else ""
            if not message or len(message) < 2:
                return None

            if self._check_message_content_duplicate(target_id, message):
                return None

            if not self._is_duplicate(target_id, message):
                self._record_trigger(target_id)
                self._record_trigger_by_type(target_id, "screen_aware")
                self._record_sent_message(target_id, message)

                logger.info(f"[主动聊天] 💬 [弥娅看见] {reason} | {message[:40]}")
                return ProactiveResult(
                    should_respond=True,
                    message=message,
                    trigger_type="screen_aware",
                    context=context,
                )
        except Exception as e:
            logger.debug(f"[主动聊天] Screen-Aware AI触发跳过: {e}")

        return None

    async def _ai_judge(self, prompt: str) -> dict | None:
        """让 AI 做一个简单判断，返回解析后的 JSON"""
        import json

        try:
            response = await self.ai_client.chat(
                messages=[AIMessage(role="user", content=prompt)],
                tools=[],
                tool_choice="none",
            )
            if not response:
                return None

            text = str(response).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except Exception:
            return None


# 全局实例
_proactive_system: Optional[ProactiveChatSystem] = None


def get_proactive_chat_system() -> ProactiveChatSystem:
    """获取主动聊天系统实例"""
    global _proactive_system
    if _proactive_system is None:
        _proactive_system = ProactiveChatSystem()
    return _proactive_system
