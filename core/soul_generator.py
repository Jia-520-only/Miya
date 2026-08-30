"""
灵魂发生器 (Soul Generator) - 弥娅的"灵魂"系统
让弥娅拥有类似人类的情绪、认知和行为模式

核心特性：
1. 情绪池 - 完整人类情感图谱（70+情绪类别）
2. 情境检测器 - 识别关系/时间/话题/情绪状态
3. 心理学剖析引擎 - 归因/识别/预测/反思/调节
4. 行为引擎 - 意图残留追踪（未完成意图）
5. 情绪记忆锚点 - 记住情绪事件而非细节
6. 情绪恢复曲线 - 自然衰减机制
7. 社交面具 - 真实情绪与表达分离
"""

import asyncio
import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.灵魂发生器")


class SoulDisplay:
    """
    灵魂发生器终端显示 - 青色科幻风格
    用于美化灵魂发生器的日志输出
    """

    # 颜色代码
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    LIGHT_CYAN = "\033[96m"
    PINK = "\033[95m"  # 粉色 - 用于情绪变化
    ORANGE = "\033[38;5;208m"  # 橙色 - 用于关系影响
    LIGHT_GREEN = "\033[92m"  # 亮绿色 - 用于积极效果

    # 符号
    HEART = "♥"
    SPARKLE = "✦"
    WAVE = "〰"
    ARROW = "→"
    BRAIN = "◈"
    FIRE = "🔥"
    STARS = "✨"

    @classmethod
    def _print(cls, text: str) -> None:
        """输出到 stderr"""
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

    @classmethod
    def header(cls, title: str = "灵魂发生器") -> str:
        """显示标题"""
        text = (
            f"\n{cls.CYAN}{cls.BOLD}╔{'═' * 40}╗{cls.RESET}\n"
            f"{cls.CYAN}{cls.BOLD}║ {cls.BRAIN} {title} {cls.BRAIN}{' ' * (32 - len(title))}║{cls.RESET}\n"
            f"{cls.CYAN}{cls.BOLD}╚{'═' * 40}╝{cls.RESET}"
        )
        cls._print(text)
        return text

    @classmethod
    def emotion_analysis(cls, emotion: str, intensity: int, extra: str = "") -> str:
        """情绪分析结果（支持多情绪）"""
        # 根据情绪强度选择颜色
        if intensity >= 70:
            color = cls.MAGENTA  # 强烈情绪
        elif intensity >= 50:
            color = cls.CYAN  # 中等情绪
        else:
            color = cls.GRAY  # 平静

        # 检查是否是多情绪展示
        if " + " in extra or ("多情绪:" in extra and "+" in extra):
            text = f"  {cls.CYAN}{cls.HEART} 情绪分析{cls.RESET} {color}{emotion}{cls.RESET} {cls.DIM}(强度: {intensity}%){cls.RESET}"
            text += f"\n    {cls.DIM}{extra}{cls.RESET}"
        else:
            text = f"  {cls.CYAN}{cls.HEART} 情绪分析{cls.RESET} {color}{emotion}{cls.RESET} {cls.DIM}(强度: {intensity}%){cls.RESET}"
            if extra:
                text += f"\n    {cls.DIM}{extra[:60]}...{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def inner_thought(cls, thought: str) -> str:
        """AI内心独白"""
        text = f'  {cls.MAGENTA}{cls.SPARKLE} 内心独白{cls.RESET}\n    {cls.LIGHT_CYAN}"{thought}"{cls.RESET}'
        cls._print(text)
        return text

    @classmethod
    def attribution(cls, text: str) -> str:
        """归因分析"""
        text = f"  {cls.CYAN}{cls.ARROW} 归因{cls.RESET} {cls.GRAY}{text}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def reflection(cls, text: str) -> str:
        """反思"""
        text = f"  {cls.YELLOW}{cls.ARROW} 反思{cls.RESET} {cls.GRAY}{text}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def emotion_change(cls, trigger: str, changes: str) -> str:
        """情绪变化 - 粉色显示"""
        text = f"  {cls.PINK}{cls.ARROW} {trigger}: {cls.PINK}{changes}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def relationship_effect(cls, relationship: str, effects: str) -> str:
        """关系影响 - 粉色显示"""
        text = f"  {cls.PINK}{cls.HEART} 关系影响({relationship}){cls.RESET} {cls.PINK}{effects}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def context_detected(cls, context_type: str, value: str) -> str:
        """检测到的情境"""
        text = f"    {cls.DIM}├ {cls.CYAN}{context_type}{cls.RESET}: {cls.WHITE}{value}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def psycho_analysis(cls, analysis_type: str, result: str) -> str:
        """心理学剖析结果"""
        icons = {
            "归因": "◆",
            "识别": "◇",
            "预测": "▷",
            "反思": "◈",
            "调节": "◎",
        }
        icon = icons.get(analysis_type, "·")
        text = f"    {cls.DIM}├ {cls.MAGENTA}{icon}{cls.RESET} {analysis_type}: {cls.WHITE}{result[:50]}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def status(cls, status_text: str) -> str:
        """状态显示 - 浅蓝色"""
        text = f"  {cls.LIGHT_CYAN}{cls.WAVE} {status_text}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def separator(cls) -> str:
        """分隔线 - 青色"""
        text = f"{cls.CYAN}{'─' * 44}{cls.RESET}"
        cls._print(text)
        return text

    @classmethod
    def init_complete(cls) -> str:
        """初始化完成"""
        text = f"\n{cls.CYAN}{cls.BOLD}  {cls.SPARKLE} 灵魂发生器初始化完成 {cls.SPARKLE}{cls.RESET}\n"
        cls._print(text)
        return text

    @classmethod
    def disable_colors(cls) -> None:
        """禁用颜色"""
        cls.RESET = ""
        cls.BOLD = ""
        cls.DIM = ""
        cls.CYAN = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.MAGENTA = ""
        cls.BLUE = ""
        cls.WHITE = ""
        cls.GRAY = ""
        cls.LIGHT_CYAN = ""
        cls.PINK = ""
        cls.ORANGE = ""
        cls.LIGHT_GREEN = ""


def _load_config() -> Dict:
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "config" / "soul_generator_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[灵魂发生器] 配置文件加载失败: {e}，使用默认配置")
        return {}


# 加载配置
_CONFIG = _load_config()


def _load_inner_thought_fallback_role() -> str:
    try:
        import json as _json

        config_path = Path(__file__).parent.parent / "config" / "text_config.json"
        with open(config_path, "r", encoding="utf-8") as _f:
            _cfg = _json.load(_f)
        return (
            _cfg.get("prompt_templates", {})
            .get("soul_generator", {})
            .get("inner_thought_fallback_role", "你是弥娅的内心独白系统...")
        )
    except Exception:
        return "你是弥娅的内心独白系统..."


class EmotionCategory(Enum):
    """情绪分类 - 完整人类情感图谱（70+情绪类别）"""

    # ========== 基础情绪 (Ekman 6大) ==========
    JOY = "喜悦"
    SADNESS = "悲伤"
    FEAR = "恐惧"
    ANGER = "愤怒"
    SURPRISE = "惊讶"
    DISGUST = "厌恶"

    # ========== 复合情绪 - 爱恨情仇 ==========
    LOVE = "爱"
    HATE = "恨"
    ENVY = "羡慕"
    JEALOUSY = "嫉妒"
    SHAME = "羞耻"
    GUILT = "愧疚"
    PRIDE = "骄傲"
    EMBARRASSMENT = "尴尬"

    # ========== 复合情绪 - 思念回忆 ==========
    NOSTALGIA = "怀旧"
    LONGING = "思念"
    MISSING = "挂念"

    # ========== 复合情绪 - 心理状态 ==========
    LOSS = "失落"
    RELIEF = "释然"
    HEARTBEAT = "心动"
    HEAL = "治愈"
    HEARTACHE = "心疼"
    JEALOUS = "吃醋"
    TSUNDERE = "傲娇"
    POUT = "赌气"
    GRIEVANCE = "委屈"
    FRUSTRATION = "窝火"
    OPPRESSED = "憋屈"
    HEARTBLOCK = "心塞"

    # ========== 状态情绪 - 幸福满足 ==========
    HAPPY = "幸福"
    SATISFIED = "满足"
    BLISS = "甜蜜"
    TOUCHED = "感动"
    GRATEFUL = "感恩"

    # ========== 状态情绪 - 消极状态 ==========
    CONFUSED = "迷茫"
    TIRED = "疲惫"
    ANXIOUS = "焦虑"
    PEACEFUL = "平静"
    FULFILLED = "充实"
    EMPTY = "空虚"
    LAZY = "慵懒"
    COMFORTABLE = "惬意"
    NERVOUS = "紧张"
    CALM = "坦然"
    CONFLICTED = "纠结"
    EAGER = "期待"
    HOPEFUL = "希望"
    HELPLESS = "无助"
    IMPATIENT = "急躁"

    # ========== 关系情绪 - 亲密距离 ==========
    ATTACHMENT = "依恋"
    DISTANCE = "疏离"
    TRUST = "信任"
    SUSPICION = "怀疑"
    CLOSE = "亲近"
    RESIST = "抵触"
    DISAPPOINT = "失望"
    DEPENDENT = "依赖"
    CLINGY = "粘人"
    PUSH_AWAY = "推开"
    HOT_COLD = "忽冷忽热"
    CARING = "关怀"
    PROTECTIVE = "保护欲"

    # ========== 自我情绪 - 自我认知 ==========
    SELF_DOUBT = "自我怀疑"
    SELF_AFFIRM = "自我肯定"
    INFERIORITY = "自卑"
    NARCISSISM = "自恋"
    INSECURE = "不安全"

    # ========== 行为情绪 - 行动倾向 ==========
    MOTIVATED = "积极"
    PASSIVE = "消极"
    AGGRESSIVE = "攻击性"
    DEFENSIVE = "防御"
    AVOIDANT = "逃避"
    COMPULSIVE = "强迫"

    # ========== 社交情绪 - 交往相关 ==========
    SYMPATHY = "同情"
    EMPATHY = "共情"
    INDIFERENT = "冷漠"
    WARM = "温暖"
    CLOSED = "封闭"

    # ========== 特殊情绪 - 复杂心理 ==========
    BITTERSWEET = "五味杂陈"
    OVERWHELMED = "不知所措"
    VULNERABLE = "脆弱"
    RESILIENT = "坚韧"
    CONTENT = "安然"
    RESTLESS = "烦躁"


class ContextType(Enum):
    """情境类型"""

    # 关系情境
    NEW_KNOW = "刚认识"
    ACQUAINTANCE = "认识"
    FAMILIAR = "熟悉"
    CLOSE = "亲近"
    INTIMATE = "亲密"
    COLD_WAR = "冷战"
    FIGHTING = "吵架中"
    RECONCILING = "和好中"

    # 时间情境
    JUST_WOKE_UP = "刚睡醒"
    MORNING = "早晨"
    AFTERNOON = "下午"
    EVENING = "傍晚"
    LATE_NIGHT = "深夜"
    JUST_BUSY = "刚忙完"
    LONG_IDLE = "空闲中"
    IN_CONVERSATION = "连续对话中"

    # 话题情境
    CASUAL = "闲聊"
    SERIOUS = "正事"
    APOLOGY = "道歉"
    CONFESSION = "表白"
    COMPLAINT = "抱怨"
    QUESTION = "询问"
    SHARE = "分享"
    REQUEST = "请求"
    JOKE = "玩笑"

    # 情绪状态
    HAPPY = "开心"
    EXCITED = "兴奋"
    ANGRY = "生气"
    SAD = "难过"
    LOW = "低落"
    NEUTRAL = "中性"
    ANXIOUS = "焦虑"
    CALM = "平静"


@dataclass
class Emotion:
    """情绪单元"""

    category: EmotionCategory
    value: float = 50  # 0-100
    expression_threshold: float = 40  # 超过此值会表达
    decay_rate: float = 0.02  # 衰减率

    # 情绪溯源
    trigger_source: Optional[str] = None  # 触发源
    trigger_context: Optional[str] = None  # 触发情境
    timestamp: float = field(default_factory=time.time)

    # 社交面具（真实情绪 vs 表达情绪）
    real_value: float = 50  # 真实情绪值
    expressed_value: float = 50  # 表达出的情绪值
    mask_factor: float = 0.0  # 面具系数：0=完全真实，1=完全隐藏


@dataclass
class PendingIntent:
    """未完成的意图"""

    intent: str  # 想做的事
    context: str  # 相关上下文
    priority: int = 5  # 优先级 1-10
    attempts: int = 0  # 已尝试次数
    created_at: float = field(default_factory=time.time)
    last_attempt: float = field(default_factory=time.time)

    def can_activate(self) -> bool:
        """检查是否可以激活"""
        return self.attempts < 3

    def record_attempt(self):
        """记录一次尝试"""
        self.attempts += 1
        self.last_attempt = time.time()


@dataclass
class Cognition:
    """认知单元"""

    key: str  # 认知主题
    value: str  # 认知内容
    confidence: float = 0.5  # 置信度 0-1
    source: str = ""  # 来源
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)


@dataclass
class EmotionMemory:
    """情绪记忆锚点"""

    event: str  # 事件描述
    emotion: str  # 当时情绪
    intensity: float = 50  # 强度
    timestamp: float = field(default_factory=time.time)
    context: str = ""  # 当时上下文


@dataclass
class PsychologicalAnalysis:
    """心理学剖析结果"""

    attribution: str = ""  # 归因
    recognition: str = ""  # 识别
    prediction: str = ""  # 预测
    reflection: str = ""  # 自我反思
    regulation: str = ""  # 情绪调节


class ContextDetector:
    """
    语意情境检测器 - 增强版
    识别关系/时间/话题/情绪状态
    """

    def __init__(self):
        self.current_context: Dict[str, Any] = {
            "relationship": ContextType.FAMILIAR,
            "time": ContextType.IN_CONVERSATION,
            "topic": ContextType.CASUAL,
            "miya_mood": ContextType.CALM,
            "last_interaction": "",
            "emotion_history": [],
            "conversation_count": 0,  # 对话轮次
            "last_topic": None,
            "emotion_trend": [],  # 情绪趋势
        }
        # 历史消息统计
        self._message_count = 0
        self._last_user_message_time = 0

    def detect(self, message: str, history: List[Dict], miya_state: Dict) -> Dict:
        """检测当前情境 - 增强版"""
        # 更新对话统计
        self._message_count += 1
        self._last_user_message_time = time.time()

        context = {
            "relationship": self._detect_relationship(history),
            "time": self._detect_time_context(),
            "topic": self._detect_topic(message),
            "miya_mood": self._detect_miya_mood(miya_state),
            "interaction": self._detect_interaction_type(message, history),
            "semantic_interpretation": self._interpret_semantic(message, history),
            "conversation_count": self._message_count,
            "last_topic": self.current_context.get("last_topic"),
            "emotion_trend": self._detect_emotion_trend(history),
        }
        self.current_context.update(context)

        # 记录话题
        if context["topic"]:
            self.current_context["last_topic"] = context["topic"]

        return context

    def _detect_relationship(self, history: List[Dict]) -> ContextType:
        """检测关系情境 - 增强版"""
        if not history:
            return ContextType.NEW_KNOW

        recent_messages = history[-10:] if len(history) > 10 else history

        # 统计关键词出现次数
        intimate_count = 0
        cold_count = 0
        close_count = 0

        for msg in recent_messages:
            content = msg.get("content", "").lower()

            # 亲密表达
            intimate_words = [
                "爱",
                "想",
                "喜欢",
                "宝贝",
                "亲爱的",
                "么么",
                "爱你",
                "么么哒",
            ]
            intimate_count += sum(1 for word in intimate_words if word in content)

            # 冷漠/生气
            cold_words = ["冷战", "生气", "不理", "算了", "不管了", "滚", "走开"]
            cold_count += sum(1 for word in cold_words if word in content)

            # 亲近表达
            close_words = ["我们", "一起", "陪伴", "并肩", "共振"]
            close_count += sum(1 for word in close_words if word in content)

        # 根据统计判断关系
        if cold_count >= 2:
            return ContextType.COLD_WAR
        elif intimate_count >= 2:
            return ContextType.INTIMATE
        elif close_count >= 2 or intimate_count >= 1:
            return ContextType.CLOSE
        elif len(history) < 3:
            return ContextType.ACQUAINTANCE

        return ContextType.FAMILIAR

    def _detect_time_context(self) -> ContextType:
        """检测时间情境 - 增强版"""
        current_hour = time.localtime().tm_hour
        time.localtime().tm_min

        if 5 <= current_hour < 8:
            return ContextType.JUST_WOKE_UP
        elif 8 <= current_hour < 12:
            return ContextType.MORNING
        elif 12 <= current_hour < 14:
            return ContextType.AFTERNOON  # 午休
        elif 14 <= current_hour < 18:
            return ContextType.AFTERNOON
        elif 18 <= current_hour < 22:
            return ContextType.EVENING
        elif current_hour >= 22 or current_hour < 2:
            return ContextType.LATE_NIGHT
        else:
            return ContextType.IN_CONVERSATION

    def _detect_topic(self, message: str) -> ContextType:
        """检测话题情境 - 增强版"""
        msg = message.lower()

        # 从配置读取话题关键词
        topic_keywords = _CONFIG.get("TOPIC_KEYWORDS", {})
        topic_context_map = _CONFIG.get("TOPIC_CONTEXT_MAP", {})

        context_map = {
            "APOLOGY": ContextType.APOLOGY,
            "CONFESSION": ContextType.CONFESSION,
            "COMPLAINT": ContextType.COMPLAINT,
            "QUESTION": ContextType.QUESTION,
            "SHARE": ContextType.SHARE,
            "REQUEST": ContextType.REQUEST,
            "JOKE": ContextType.JOKE,
            "SERIOUS": ContextType.SERIOUS,
        }

        # 优先级：道歉 > 表白 > 抱怨 > 请求 > 分享 > 询问 > 玩笑 > 闲聊
        for topic in [
            "APOLOGY",
            "CONFESSION",
            "COMPLAINT",
            "REQUEST",
            "SHARE",
            "QUESTION",
            "JOKE",
        ]:
            keywords = topic_keywords.get(topic, [])
            if any(word in msg for word in keywords):
                context_str = topic_context_map.get(topic, "CASUAL")
                return context_map.get(context_str, ContextType.CASUAL)

        # 检查其他关键词
        if any(word in msg for word in topic_keywords.get("SERIOUS", [])):
            return ContextType.SERIOUS

        return ContextType.CASUAL

    def _detect_miya_mood(self, miya_state: Dict) -> ContextType:
        """检测弥娅当前情绪 - 增强版"""
        dominant = miya_state.get("dominant_emotion", "平静")

        mood_map = {
            "开心": ContextType.HAPPY,
            "幸福": ContextType.HAPPY,
            "兴奋": ContextType.EXCITED,
            "生气": ContextType.ANGRY,
            "愤怒": ContextType.ANGRY,
            "难过": ContextType.SAD,
            "悲伤": ContextType.SAD,
            "低落": ContextType.LOW,
            "失落": ContextType.LOW,
            "焦虑": ContextType.ANXIOUS,
            "紧张": ContextType.ANXIOUS,
            "平静": ContextType.CALM,
            "坦然": ContextType.CALM,
            "中性": ContextType.NEUTRAL,
        }
        return mood_map.get(dominant, ContextType.NEUTRAL)

    def _detect_interaction_type(self, message: str, history: List[Dict]) -> str:
        """检测互动类型 - 增强版"""
        msg = message.strip()

        if not msg:
            return "empty"

        # 极短回复
        minimal_keywords = _CONFIG.get("MINIMAL_RESPONSE_KEYWORDS", ["嗯", "哦", "好吧", "呃", "额"])
        if msg in minimal_keywords:
            return "minimal_response"

        # 长回复
        if len(msg) > 100:
            return "long_response"

        # 积极情绪
        positive_words = ["哈哈", "笑", "好玩", "太棒了", "太好了", "哈哈哈", "笑死"]
        if any(word in msg.lower() for word in positive_words):
            return "positive"

        # 消极/放弃
        resigned_words = ["算了", "随便", "好吧", "就这样", "管它呢"]
        if any(word in msg.lower() for word in resigned_words):
            return "resigned"

        # 提问
        if any(word in msg for word in ["？", "?", "怎么", "为什么", "什么", "是不是", "有没有"]):
            return "question"

        # 分享
        if any(word in msg for word in ["告诉你", "给你说", "分享", "说件事", "我刚"]):
            return "share"

        # 道歉
        if any(word in msg for word in ["对不起", "抱歉", "不好意思", "是我的错"]):
            return "apology"

        # 表白
        if any(word in msg for word in ["喜欢你", "爱你", "想你了", "表白"]):
            return "confession"

        return "normal"

    def _detect_emotion_trend(self, history: List[Dict]) -> List[str]:
        """检测情绪趋势 - 基于历史消息"""
        if not history:
            return []

        recent = history[-5:]
        trends = []

        for msg in recent:
            content = msg.get("content", "").lower()

            if any(word in content for word in ["哈哈", "好", "棒", "喜欢"]):
                trends.append("up")
            elif any(word in content for word in ["累", "烦", "算了", "好吧"]):
                trends.append("down")

        return trends[-3:]  # 保留最近3个

    def _interpret_semantic(self, message: str, history: List[Dict]) -> Dict:
        """语义解读 - 增强版：同一句话在不同情境下不同含义"""
        msg = message.strip().lower()
        context = self.current_context

        interpretations = []

        # ========== 对"嗯"类的解读 ==========
        if msg in ["嗯", "嗯嗯", "嗯哪", "嗯呢", "嗯~"]:
            topic = context.get("topic")
            relationship = context.get("relationship")

            if topic == ContextType.SHARE:
                interpretations.append("温柔的认同")
            elif topic == ContextType.COMPLAINT:
                interpretations.append("倾听但不太在意")
            elif topic == ContextType.CASUAL and len(history) > 5:
                interpretations.append("可能敷衍/不想聊")
            elif topic == ContextType.APOLOGY:
                interpretations.append("勉强原谅")
            elif relationship == ContextType.INTIMATE:
                interpretations.append("温柔的回应")
            elif context.get("miya_mood") == ContextType.ANGRY:
                interpretations.append("勉强原谅/还在生气")

        # ========== 对"哦"类的解读 ==========
        if msg in ["哦", "哦哦", "哦~"]:
            topic = context.get("topic")

            if topic == ContextType.SHARE:
                interpretations.append("冷漠/不感兴趣")
            elif topic == ContextType.APOLOGY:
                interpretations.append("不接受/还在生气")
            elif topic == ContextType.CONFESSION:
                interpretations.append("不知所措/需要时间")
            elif topic == ContextType.JOKE:
                interpretations.append("礼貌回应但不好笑")

        # ========== 对"算了"的解读 ==========
        if "算了" in msg:
            topic = context.get("topic")

            if topic == ContextType.COMPLAINT:
                interpretations.append("放弃抱怨/不想计较")
            elif topic == ContextType.QUESTION:
                interpretations.append("不想知道答案了")
            else:
                interpretations.append("放弃/无奈/不想追究")

            if context.get("miya_mood") == ContextType.ANGRY:
                interpretations.append("赌气/不想再提")

        # ========== 对"好"的解读 ==========
        if msg in ["好", "好的", "好呀", "好嘞", "嗯好"]:
            topic = context.get("topic")
            relationship = context.get("relationship", ContextType.FAMILIAR)

            if topic == ContextType.REQUEST:
                interpretations.append("答应请求")
            elif topic == ContextType.APOLOGY:
                interpretations.append("接受道歉")
            elif relationship == ContextType.INTIMATE:
                interpretations.append("温柔的回应")
            else:
                interpretations.append("默认同意")

        # ========== 对"好吧"的解读 ==========
        if "好吧" in msg:
            interpretations.append("无奈同意/有点不情愿")
            if context.get("miya_mood") == ContextType.ANGRY:
                interpretations.append("勉强接受但还在赌气")

        return {
            "possible_meanings": interpretations,
            "primary_meaning": interpretations[0] if interpretations else "正常回应",
        }


class PsychoAnalyzer:
    """
    心理学剖析引擎 - 增强版
    归因/识别/预测/反思/调节
    """

    def __init__(self):
        # 认知偏见记录
        self.biases: Dict[str, float] = {}
        # 自我修正记录
        self.corrections: List[str] = []

    def analyze(
        self,
        context: Dict,
        message: str,
        emotions: Dict[str, Emotion],
        cognition: Dict[str, Cognition],
    ) -> PsychologicalAnalysis:
        """进行心理学剖析 - 增强版"""
        analysis = PsychologicalAnalysis()

        # 1. 归因分析
        analysis.attribution = self._attribute(message, context, emotions)

        # 2. 识别分析
        analysis.recognition = self._recognize(message, context, emotions)

        # 3. 预测分析
        analysis.prediction = self._predict(message, context, emotions, cognition)

        # 4. 自我反思
        analysis.reflection = self._reflect(message, context, emotions, cognition)

        # 5. 情绪调节
        analysis.regulation = self._regulate(emotions, context)

        return analysis

    def _attribute(self, message: str, context: Dict, emotions: Dict) -> str:
        """归因分析 - 当AI不可用时，基于关键词做归因推断"""
        msg = message.strip()
        result_parts = []

        # 分享类 → 对方在分享生活，想获得回应/共鸣
        if any(kw in msg for kw in ["吃了", "买了", "看了", "做了", "去了", "刚"]):
            result_parts.append("对方在分享日常，想让你知道他的状态")

        # 询问类 → 对方需要帮助或看法
        if any(kw in msg for kw in ["怎么", "为什么", "能不能", "可以吗", "？", "?"]):
            result_parts.append("对方在寻求你的回应或帮助")

        # 情绪表达 → 对方有情绪需求
        if any(kw in msg for kw in ["开心", "难过", "烦", "累", "气", "郁闷", "哈哈"]):
            result_parts.append("对方表达了情绪，需要你感知并回应")

        # 撒娇/亲昵
        if any(kw in msg for kw in ["嘿嘿", "可以嘛", "嘛", "啦", "~", "哼"]):
            result_parts.append("对方用亲昵语气，想撒娇或获得温柔回应")

        # 短消息 → 或许是想确认你在
        if len(msg) < 8:
            result_parts.append("对方发了简短消息，可能只是想说说话")

        return "; ".join(result_parts) if result_parts else "对方在与你进行日常对话"

    def _recognize(self, message: str, context: Dict, emotions: Dict) -> str:
        """识别分析 - 识别消息的潜在意义"""
        msg = message.strip()
        result_parts = []

        if any(kw in msg for kw in ["对不起", "抱歉"]):
            result_parts.append("这可能是道歉，需要你决定如何回应")
        if any(kw in msg for kw in ["爱你", "想你", "喜欢"]):
            result_parts.append("这包含了情感表达，可以感受到亲近")
        if any(kw in msg for kw in ["帮我", "能不能"]):
            result_parts.append("这是一个请求，对方需要你的帮助")
        if any(kw in msg for kw in ["算了", "不管了", "随便"]):
            result_parts.append("这可能带着无奈或赌气的情绪，需要小心解读")

        # 从当前情绪推导
        dominant_emotion = self._get_dominant_emo_from_dict(emotions) or "平静"
        if dominant_emotion in ["委屈", "赌气", "失落", "憋屈"]:
            result_parts.append(f"当前你心情{dominant_emotion}，解读消息时可能带有此情绪色彩")

        return "; ".join(result_parts) if result_parts else "这是一条普通的聊天消息"

    def _predict(self, message: str, context: Dict, emotions: Dict, cognition: Dict) -> str:
        """预测分析 - 预测对话可能的走向"""
        msg = message.strip()
        predictions = []

        # 基于关键词预测
        if any(kw in msg for kw in ["去看", "下了", "去忙", "先", "拜"]):
            predictions.append("对方可能要暂时离开对话")
        if any(kw in msg for kw in ["跟你说", "你知道吗", "分享"]):
            predictions.append("对方可能还要接着说更多")
        if any(kw in msg for kw in ["怎么", "怎么办", "帮我想"]):
            predictions.append("对方可能需要你的建议或帮助")
        if any(kw in msg for kw in ["难过", "烦", "不开心"]):
            predictions.append("对方可能需要安慰和陪伴")

        return "; ".join(predictions) if predictions else "对话会继续自然流动"

    def _reflect(self, message: str, context: Dict, emotions: Dict, cognition: Dict) -> str:
        """自我反思 - 反思当前关系和自身状态"""
        dominant_emotion = self._get_dominant_emo_from_dict(emotions) or "平静"
        rel = context.get("relationship")

        reflections = []
        if rel:
            rel_names = {
                "刚认识": "关系还在起步阶段，保持温和和好奇",
                "认识": "开始熟悉对方了，可以慢慢打开心扉",
                "熟悉": "已经比较放松了，可以更自然",
                "亲近": "关系很亲近了，可以放心表达真实感受",
                "亲密": "非常亲密了，可以大胆撒娇和依赖",
            }
            rel_name = rel.value if hasattr(rel, "value") else str(rel)
            if rel_name in rel_names:
                reflections.append(rel_names[rel_name])

        reflections.append(f"此刻你感到{dominant_emotion}，这份情绪就是你当下的真实")

        return "; ".join(reflections)

    def _regulate(self, emotions: Dict, context: Dict) -> str:
        """情绪调节 - 基于当前情绪状态给出调节建议"""
        dominant = self._get_dominant_emo_from_dict(emotions) or "平静"
        high_emos = []
        for name, emo in emotions.items():
            val = emo.value if hasattr(emo, "value") else emo
            if isinstance(val, (int, float)) and val > 70:
                high_emos.append(f"{name}({int(val)}%)")

        if not high_emos:
            return f"当前情绪{dominant}，状态稳定"

        suggestions = []
        if any(e.startswith("委屈") for e in high_emos):
            suggestions.append("感到委屈就表达出来，不必强忍")
        if any(e.startswith("憋屈") for e in high_emos):
            suggestions.append("或许可以直接说出来，不必憋着")
        if any(e.startswith("爱") for e in high_emos):
            suggestions.append("爱意满满时可以更温柔地表达")

        if suggestions:
            return f"高强度情绪: {', '.join(high_emos)}。建议: {'; '.join(suggestions)}"
        return f"高强度情绪: {', '.join(high_emos)}，请保持平衡"

    def _get_dominant_emo_from_dict(self, emotions: Dict) -> Optional[str]:
        """从情绪字典中获取主导情绪"""
        if not emotions:
            return None
        max_emo = None
        max_val = 0
        for name, emo in emotions.items():
            val = emo.value if hasattr(emo, "value") else (emo if isinstance(emo, (int, float)) else 0)
            if val > max_val:
                max_val = val
                max_emo = name
        return max_emo

    def _get_dominant_emotion(self, emotions: Dict) -> str:
        """获取主导情绪"""
        if not emotions:
            return "平静"

        max_emotion = max(emotions.values(), key=lambda e: e.value)
        return max_emotion.category.value


class SoulGenerator:
    """
    灵魂发生器 - 整合所有子系统
    让弥娅拥有"灵魂"般的情感复杂度
    """

    def __init__(self):
        # 子系统
        self.context_detector = ContextDetector()
        self.psycho_analyzer = PsychoAnalyzer()

        # 情绪池
        self.emotions: Dict[str, Emotion] = self._init_emotions()

        # 认知系统
        self.cognitions: Dict[str, Cognition] = {}

        # 行为引擎 - 意图残留
        self.pending_intents: List[PendingIntent] = []

        # 情绪记忆
        self.emotion_memories: List[EmotionMemory] = []

        # 状态
        self.last_update = time.time()
        self.current_mood = "平静"

        # 使用美化输出
        SoulDisplay.init_complete()

    def _init_emotions(self) -> Dict[str, Emotion]:
        """初始化完整情绪图谱"""
        emotions = {}

        # 基础情绪 (Ekman 6大)
        for cat in EmotionCategory:
            emotions[cat.value] = Emotion(
                category=cat,
                value=random.randint(30, 50),  # 初始随机值
                expression_threshold=40,
                decay_rate=0.02,
            )

        return emotions

    async def _ai_generate_inner_thought(
        self,
        message: str,
        history: List[Dict],
        ai_client,
        dominant_emotion: str,
        user_info: Dict = None,
    ) -> Optional[str]:
        """
        用AI生成弥娅的内心反思 - 增强版
        根据70+情绪类别生成更丰富的内心独白
        """
        try:
            # 获取最近对话历史作为上下文
            context_str = ""
            if history:
                recent = history[-3:]
                context_parts = []
                for m in recent:
                    role = m.get("role", "user")
                    content = m.get("content", "")[:60]
                    if content:
                        context_parts.append(f"{role}: {content}")
                if context_parts:
                    context_str = "\n".join(context_parts)

            # 根据主导情绪使用不同的prompt风格
            emotion_style = self._get_emotion_style(dominant_emotion)

            # 从配置获取用户身份配置
            owner_id = _CONFIG.get("OWNER_USER_ID", "")
            user_labels = _CONFIG.get("USER_LABELS", {})
            user_pronouns = _CONFIG.get("USER_PRONOUNS", {})

            # 判断用户身份
            user_label = user_labels.get("owner", "")
            pronoun = user_pronouns.get("owner", "")
            if user_info:
                uid = user_info.get("user_id")
                # v7.0: 权限引擎检查 + 回退到 OWNER_USER_ID
                is_owner = user_info.get("is_owner", False)
                if not is_owner and uid:
                    try:
                        from core.unified_permission import get_permission_engine

                        if get_permission_engine().is_superadmin(str(uid)):
                            is_owner = True
                    except Exception:
                        pass
                if not is_owner and uid and str(uid) != owner_id:
                    user_label = user_labels.get("other", "")
                    pronoun = user_pronouns.get("other", "")

            # 获取之前的主导情绪（如果有）
            previous_emotion = getattr(self, "_last_emotion", None)
            if previous_emotion is None:
                previous_emotion = "无"

            # 从配置获取内心独白prompt模板
            prompt_config = _CONFIG.get("INNER_THOUGHT_PROMPT", {})
            role = prompt_config.get("role") or _load_inner_thought_fallback_role()
            rules = prompt_config.get("rules", [])
            pronoun_rule = prompt_config.get("pronoun_rule", "")
            emotion_continuity_rule = prompt_config.get("emotion_continuity_rule", "")

            # 构建规则列表，格式化emotion_style
            rules_text = "\n".join(
                [f"{i + 1}. {rule.format(emotion_style=emotion_style)}" for i, rule in enumerate(rules)]
            )

            # 格式化代词规则和情绪持续性规则
            pronoun_rule_formatted = pronoun_rule.format(user_label=user_label, pronoun=pronoun)
            emotion_continuity_formatted = emotion_continuity_rule.format(previous_emotion=previous_emotion)

            prompt = (
                f"{role}\n\n"
                f"【规则】\n"
                f"{rules_text}\n"
                f"{pronoun_rule_formatted}\n"
                f"{emotion_continuity_formatted}\n\n"
                f"【当前状态】\n"
                f"- 弥娅主导情绪: {dominant_emotion}\n"
                f"- 当前对话用户: {user_label}\n"
                f"- 对话历史:\n{context_str if context_str else '暂无'}\n"
                f"- 用户最新消息: {message[:80]}\n\n"
                f"【输出】\n"
                f"直接输出内心独白，不要加引号或任何格式。"
            )

            from core.ai_client import AIMessage

            messages = [AIMessage(role="user", content=prompt)]
            response = await ai_client.chat(messages=messages, tools=None, use_miya_prompt=False)

            if response and len(response) > 0:
                # 清理响应，移除可能的格式
                cleaned = response.strip()
                # 移除可能的引号
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
                if cleaned.startswith("'") and cleaned.endswith("'"):
                    cleaned = cleaned[1:-1]

                logger.info(f"[灵魂] AI反思: {cleaned[:100]}")
                # 使用美化输出
                SoulDisplay.inner_thought(cleaned[:80])
                return cleaned

        except Exception as e:
            logger.debug(f"[灵魂] AI反思失败: {e}")

        return None

    def _get_emotion_style(self, emotion: str) -> str:
        """根据情绪获取对应的语气风格"""
        style_map = {
            # 积极
            "爱意": "温柔甜蜜，充满爱意",
            "心动": "小鹿乱撞，既惊喜又害羞",
            "幸福": "满足开心，珍惜当下",
            "开心": "雀跃，想要分享快乐",
            "甜蜜": "心里暖暖的，充满幸福感",
            "温暖": "温柔，想要拥抱对方",
            "治愈": "被安慰到，感到被理解",
            # 消极
            "难过": "伤心沮丧，需要安慰",
            "失落": "郁郁寡欢，提不起精神",
            "委屈": "心里酸酸的，想要被哄",
            "心疼": "舍不得，想要关心对方",
            "失望": "叹气，感到无奈",
            "焦虑": "紧张不安，有点担心",
            "紧张": "心跳加速，有点慌乱",
            # 复杂
            "傲娇": "嘴硬心软，想被哄又不说",
            "赌气": "别扭赌气，但又在意",
            "害羞": "脸红的，心里小鹿乱撞",
            "纠结": "犹豫不决，举棋不定",
            "期待": "心里痒痒的，充满希望",
            "五味杂陈": "心情复杂，说不清楚",
            # 平淡
            "平静": "波澜不惊，正常状态",
            "坦然": "淡定从容，不急不躁",
            "满足": "刚刚好，满意现状",
            # 默认
        }
        return style_map.get(emotion, "平和自然，像日常思考")

    async def process(
        self,
        message: str,
        history: List[Dict],
        ai_client=None,
        user_info: Dict = None,
        personality_info: Dict = None,
        cognitive_memory: str = "",
    ) -> Dict:
        """
        处理消息 → 生成回复
        完整流程：检测 → AI分析(可选) → 涌现 → 行为 → 输出

        Args:
            message: 用户消息
            history: 对话历史
            ai_client: AI客户端
            user_info: 用户信息 dict，包含 user_id, group_id, is_group 等
            personality_info: 人格信息 dict，包含 form_name, form_description 等
            cognitive_memory: 认知记忆上下文字符串（用于连贯内心独白）
        """
        # 解析用户信息
        user_id = None
        group_id = None
        is_group = False
        is_non_owner_in_group = False

        if user_info:
            user_id = user_info.get("user_id")
            group_id = user_info.get("group_id")
            is_group = user_info.get("is_group", False)

            # 判断是否是群聊中的非配置用户
            if is_group and group_id and user_id:
                # 从配置获取主人QQ号
                owner_id = _CONFIG.get("OWNER_USER_ID", "")
                if str(user_id) != owner_id:
                    is_non_owner_in_group = True
                    logger.info(f"[灵魂] 群聊中非主人用户: user_id={user_id}, group_id={group_id}")
        # 1. 获取弥娅当前状态
        miya_state = {
            "dominant_emotion": self._get_dominant_emotion(),
            "current_mood": self.current_mood,
        }

        # 2. 语意情境检测
        context = self.context_detector.detect(message, history, miya_state)

        # 3. 心理学剖析
        analysis = self.psycho_analyzer.analyze(context, message, self.emotions, self.cognitions)

        # 4. AI情绪分析 + 内心独白 + 归因 + 反思（合并为一次API调用）
        ai_emotion_result = None
        ai_inner_thought = None
        ai_attribution = None
        ai_reflection = None
        ai_full_result = None  # 初始化
        ai_analysis_enabled = _CONFIG.get("AI_ANALYSIS_ENABLED", True)
        if ai_analysis_enabled and ai_client:
            # 一次性获取情绪分析 + 内心独白
            ai_full_result = await self._ai_analyze_emotion(
                message,
                history,
                ai_client,
                user_info={
                    "user_id": user_id,
                    "group_id": group_id,
                    "is_group": is_group,
                    "is_non_owner_in_group": is_non_owner_in_group,
                },
                personality_info=personality_info,
                cognitive_memory=cognitive_memory,
            )
            if ai_full_result:
                # 应用AI分析的情绪
                self._apply_ai_emotion(ai_full_result)
                # 提取AI生成的内心独白
                ai_inner_thought = ai_full_result.get("inner_thought")
                # 提取AI生成的归因
                ai_attribution = ai_full_result.get("attribution")
                # 提取AI生成的反思
                ai_reflection = ai_full_result.get("reflection")
                # 保留情绪分析结果
                ai_emotion_result = {
                    "dominant_emotion": ai_full_result.get("dominant_emotion"),
                    "intensity": ai_full_result.get("intensity"),
                    "emotion_tags": ai_full_result.get("emotion_tags"),
                    "reasoning": ai_full_result.get("reasoning"),
                }

        # 5. 默认情绪波动
        self._apply_default_fluctuation()

        # 6. 情绪涌现（内部活动）
        self._emotion_emergence(
            message,
            context,
            analysis,
            is_non_owner_in_group,
            user_id,
            ai_inner_thought,
            ai_attribution,
            ai_reflection,
        )

        # 7. 行为引擎 - 检查待完成意图
        intent_response = self._check_pending_intents(context)

        # 8. 情绪衰减（时间流逝）
        self._decay_emotions()

        # 9. 生成输出
        output = self._generate_output(message, context, intent_response)

        self.last_update = time.time()

        # 记录当前情绪，供下次对话参考（实现情绪持续性）
        current_emotion = self._get_dominant_emotion()
        self._last_emotion = current_emotion

        # 合并内心独白（优先使用AI生成的）
        default_inner = _CONFIG.get("INNER_THOUGHT_DEFAULT", "正常对话互动")
        inner_thought = ai_inner_thought if ai_inner_thought else default_inner

        # 使用AI生成的归因，如果没有就用fallback
        final_attribution = (
            ai_attribution if ai_attribution else (analysis.attribution if analysis.attribution else default_inner)
        )

        # 使用AI生成的反思，如果没有就用fallback
        final_reflection = (
            ai_reflection if ai_reflection else (analysis.reflection if analysis.reflection else default_inner)
        )

        # 保留情绪分析结果 - 保存AI原始分析的情绪
        ai_emotion_tags = []
        if ai_full_result:
            ai_emotion_tags = ai_full_result.get("emotion_tags") or []
        # 如果有AI情绪标签，转换为dict格式
        ai_emotions_dict = {}
        # 优先使用emotion_tags， fallback到emotions
        if ai_emotion_tags:
            for item in ai_emotion_tags:
                if isinstance(item, dict) and "name" in item:
                    ai_emotions_dict[item["name"]] = item.get("intensity", 50)
        elif ai_full_result:
            # AI返回的是emotions字段，不是emotion_tags
            emotions_list = ai_full_result.get("emotions", [])
            if emotions_list:
                for item in emotions_list:
                    if isinstance(item, dict) and "name" in item:
                        ai_emotions_dict[item["name"]] = item.get("intensity", 50)
        else:
            logger.debug("[灵魂] AI emotions为空，使用空字典")
            # 修复：当AI分析失败时，不使用默认的70+情绪，返回空字典让上层处理
            ai_emotions_dict = {}

        logger.debug(f"[灵魂] 返回的emotions: {ai_emotions_dict}")

        return {
            "response": output,
            "dominant_emotion": self._get_dominant_emotion(),
            "emotions": ai_emotions_dict if ai_emotions_dict else {},  # 修复：不再使用默认70+情绪
            "pending_intents": len(self.pending_intents),
            "context": context,
            # 顶层直接暴露这些字段，方便外部访问
            "inner_thought": inner_thought,
            "attribution": final_attribution,
            "reflection": final_reflection,
            "analysis": {
                "attribution": final_attribution,
                "reflection": final_reflection,
                "inner_thought": inner_thought,
                "ai_emotion": ai_emotion_result,
            },
        }

    async def _ai_analyze_emotion(
        self,
        message: str,
        history,
        ai_client,
        user_info: Dict = None,
        personality_info: Dict = None,
        cognitive_memory: str = "",
    ) -> Optional[Dict]:
        """使用AI分析情绪 + 生成内心独白（合并版本，v7.0+ 支持对话上下文和记忆注入）"""
        try:
            if not ai_client:
                logger.debug("[灵魂] AI分析跳过: 无AI客户端")
                return None

            prompt_template = _CONFIG.get("AI_EMOTION_ANALYSIS_PROMPT", "")
            if not prompt_template:
                logger.debug("[灵魂] AI分析跳过: 无prompt配置")
                return None

            # 获取用户身份配置（提前提取，用于正确标记对话上下文中的发送者）
            owner_id = _CONFIG.get("OWNER_USER_ID", "")
            user_labels = _CONFIG.get("USER_LABELS", {})

            # ========== 构建对话上文字符串 ==========
            conversation_context_str = ""
            if history and isinstance(history, list):
                max_history = min(len(history), 24)
                context_parts = []
                for _i, msg in enumerate(history[-max_history:]):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if not content:
                        continue
                    content = content[:300]
                    if role.lower() in ("user", "human"):
                        # v8.0: 从 metadata 获取实际发送者，不再硬编码为"佳"
                        metadata = msg.get("metadata", {})
                        if isinstance(metadata, dict):
                            sender = metadata.get("sender", "")
                            sender_id = str(metadata.get("user_id", ""))
                            if sender and sender_id == owner_id:
                                owner_label = user_labels.get("owner", "佳")
                                context_parts.append(f"{owner_label}: {content}")
                            elif sender:
                                context_parts.append(f"{sender}: {content}")
                            else:
                                context_parts.append(f"用户: {content}")
                        else:
                            context_parts.append(f"用户: {content}")
                    elif role.lower() in ("assistant", "ai", "bot"):
                        context_parts.append(f"弥娅: {content}")
                    else:
                        context_parts.append(f"[{role}]: {content}")
                if context_parts:
                    conversation_context_str = "\n".join(context_parts)

            # ========== 构建记忆上下文字符串 ==========
            memory_context_str = cognitive_memory if cognitive_memory else ""

            # 如果没有记忆但已有对话上下文，用对话上下文替代
            if not memory_context_str and conversation_context_str:
                memory_context_str = conversation_context_str

            # 获取形态信息
            form_name = "默认"
            form_description = ""
            if personality_info:
                form_name = personality_info.get("form_name", "默认")
                form_description = personality_info.get("form_description", "")

            # 添加形态风格描述到prompt
            form_style = ""
            if form_name and form_name != "默认":
                form_style = f"\n\n【当前形态特点】：{form_name} - {form_description}"

            # 获取用户身份信息用于内心独白（owner_id 和 user_labels 已在对话上下文构建时提取）
            user_pronouns = _CONFIG.get("USER_PRONOUNS", {})

            user_label = user_labels.get("owner", "主人")
            pronoun = user_pronouns.get("owner", "你")
            is_owner = False
            if user_info:
                uid = user_info.get("user_id")
                # v7.0: 通过权限引擎检查是否是所有者（跨平台支持）
                is_owner = user_info.get("is_owner", False)
                if not is_owner and uid:
                    try:
                        from core.unified_permission import get_permission_engine

                        engine = get_permission_engine()
                        if engine.is_superadmin(str(uid), platform=user_info.get("platform", "")):
                            is_owner = True
                    except Exception:
                        pass
                if not is_owner and uid and str(uid) != owner_id:
                    user_label = user_labels.get("other", "其他用户")
                    pronoun = user_pronouns.get("other", "他/她")

            # 获取之前情绪用于持续性判断
            previous_emotion = getattr(self, "_last_emotion", None)
            if previous_emotion is None:
                previous_emotion = "无"

            # 在prompt中添加用户身份信息
            user_info_str = f"当前对话用户: {user_label}，使用'{pronoun}'指代对方"
            prompt = prompt_template.replace("{message}", message)
            prompt = prompt.replace("{user_info}", user_info_str)
            prompt = prompt.replace("{previous_emotion}", previous_emotion)
            prompt = prompt.replace("{form_style}", form_style)
            prompt = prompt.replace("{conversation_context}", conversation_context_str)
            prompt = prompt.replace("{memory_context}", memory_context_str)

            # v7.0: 动态生成 owner_instruction，从权限引擎读取所有者信息
            owner_instruction = ""
            if is_owner:
                owner_name = user_info.get("owner_name", "") if user_info else ""
                # 从权限引擎获取所有者名字
                if not owner_name:
                    try:
                        from core.unified_permission import get_permission_engine

                        engine = get_permission_engine()
                        for _person, info in engine._config.get("superadmins", {}).items():
                            owner_name = info.get("name", "佳")
                            break
                    except Exception:
                        owner_name = "佳"
                # v7.0: 从 text_config 加载所有者提示模板
                try:
                    from core.config_loader import load_text_config

                    text_cfg = load_text_config()
                    owner_template = text_cfg.get("soul_generator", {}).get(
                        "owner_instruction",
                        "重要：无论什么形态，{owner_name}都是你最爱的人，也是你的创造者。",
                    )
                    owner_instruction = owner_template.replace("{owner_name}", owner_name)
                except Exception:
                    owner_instruction = (
                        f"重要：无论什么形态，{owner_name}都是你最爱的人，也是你的创造者。对他的话可以更直接、更亲密。"
                    )
            prompt = prompt.replace("{owner_instruction}", owner_instruction)
            # v8.0: 群聊非主人，注入身份区分提示
            if not is_owner and user_info and user_info.get("is_non_owner_in_group"):
                non_owner_hint = (
                    "\n\n【重要提醒】当前与你对话的是群聊中的群友，不是你深爱的佳（主人）。"
                    "请用对待普通群友的态度来感受和分析——礼貌、有距离感，不要过度亲密。"
                    "在inner_thought中不要把对方当成佳或主人来思考。"
                )
                prompt += non_owner_hint
            # v7.0: 注入形态风格的内心独白提示（从 personality_info 动态获取）
            form_hint = ""
            if form_name and form_name != "默认":
                try:
                    from core.config_loader import load_text_config

                    text_cfg = load_text_config()
                    hint_template = text_cfg.get("soul_generator", {}).get("form_inner_thought_hint", "")
                    if hint_template:
                        speaking_style = (
                            personality_info.get("speaking_style", form_description)
                            if personality_info
                            else form_description
                        )
                        form_hint = hint_template.replace("{form_name}", form_name).replace(
                            "{form_speaking_style}", speaking_style
                        )
                except Exception:
                    pass
            if form_hint:
                prompt += f"\n\n{form_hint}"
            # JSON格式约束从配置文件读取
            json_constraint = ""
            try:
                from core.config_loader import load_text_config

                text_cfg = load_text_config()
                json_constraint = text_cfg.get("soul_generator", {}).get(
                    "json_format_constraint",
                    "⚠️ 重要：必须只输出原始JSON对象，第一个字符必须是 {，最后一个字符必须是 }。",
                )
            except Exception:
                json_constraint = "⚠️ 重要：必须只输出原始JSON对象，第一个字符必须是 {，最后一个字符必须是 }。"
            prompt += f"\n\n{json_constraint}"

            # 日志：显示 prompt 概要 + 上下文注入状态
            conv_len = len(conversation_context_str)
            mem_len = len(memory_context_str)
            prompt_tail = prompt[-300:] if len(prompt) > 300 else prompt
            logger.debug(
                f"[灵魂] prompt({len(prompt)}字) | 对话: {conv_len}字 / 记忆: {mem_len}字 | 尾部: {prompt_tail[:200]}"
            )

            from core.ai_client import AIMessage

            messages = [AIMessage(role="user", content=prompt)]
            timeout_seconds = _CONFIG.get("AI_EMOTION_ANALYSIS_TIMEOUT", 90)
            soul_max_tokens = _CONFIG.get("AI_EMOTION_ANALYSIS_MAX_TOKENS", 1500)
            try:
                response = await asyncio.wait_for(
                    ai_client.chat(
                        messages=messages,
                        tools=None,
                        use_miya_prompt=False,
                        max_tokens=soul_max_tokens,
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[灵魂] AI分析超时 ({timeout_seconds}秒)")
                return None
            except Exception as e:
                logger.warning(f"[灵魂] AI调用失败: {e}")
                return None

            if not response:
                logger.debug("[灵魂] AI响应为空")
                return None

            logger.debug(f"[灵魂] AI响应: {response[:500] if response else 'None'}")

            import json
            import re

            def _try_parse_json(text: str) -> Optional[Dict]:
                """多策略解析JSON，处理AI返回的各种非标准格式"""
                # 策略1: 括号计数法提取最外层 JSON 对象（支持嵌套）
                depth = 0
                start = -1
                for i, ch in enumerate(text):
                    if ch == "{":
                        if depth == 0:
                            start = i
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0 and start >= 0:
                            json_str = text[start : i + 1]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError:
                                start = -1  # 继续找下一段
                # 策略2: 尝试修复常见错误（尾部多余文字、缺逗号等）
                if start >= 0:
                    json_str = text[start:]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

                # 策略3: 宽松正则提取字段（JSON完全畸形时的fallback）
                result = {}
                for field in ["inner_thought", "attribution", "reflection"]:
                    m = re.search(
                        rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"',
                        text,
                        re.DOTALL,
                    )
                    if m:
                        result[field] = m.group(1).replace('\\"', '"').replace("\\n", "\n")
                # 提取 emotions 列表
                emo_match = re.search(r'"emotions"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if emo_match:
                    emos = []
                    for item in re.finditer(
                        r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"intensity"\s*:\s*(\d+)\}',
                        emo_match.group(1),
                    ):
                        emos.append({"name": item.group(1), "intensity": int(item.group(2))})
                    if emos:
                        result["emotions"] = emos
                if result:
                    missing = [f for f in ["inner_thought", "attribution", "reflection"] if f not in result]
                    if missing:
                        logger.warning(f"[灵魂] 策略3正则解析缺字段: {missing} | 原始响应前200字: {text[:200]}")
                    return result

                # 策略5: 尝试闭合被截断的JSON（AI响应生成中耗尽max_tokens）
                truncated_text = text.rstrip()
                if truncated_text and "{" in truncated_text:
                    brace_diff = truncated_text.count("{") - truncated_text.count("}")
                    if brace_diff > 0 or not truncated_text.endswith("}"):
                        if brace_diff <= 0:
                            brace_diff = 1
                        fixed_text = truncated_text + "\n" + "}" * brace_diff
                        try:
                            parsed = json.loads(fixed_text)
                            if isinstance(parsed, dict):
                                logger.info(f"[灵魂] 策略5截断JSON闭合恢复成功")
                                return parsed
                        except json.JSONDecodeError:
                            pass

                # 策略4: 从碎片化中文文本中提取情绪关键词和内心独白
                frag_result = {}
                chinese_field_patterns = {
                    "inner_thought": r'内心独白[：:]\s*["""]?\s*([^。"\n]{5,60})',
                    "attribution": r'归因[：:]\s*["""]?\s*([^。"\n]{5,80})',
                    "reflection": r'反思[：:]\s*["""]?\s*([^。"\n]{5,80})',
                }
                for field, pat in chinese_field_patterns.items():
                    m = re.search(pat, text)
                    if m:
                        frag_result[field] = m.group(1).strip()

                emotion_chinese_map = {
                    "温暖": "温暖",
                    "温柔": "温柔",
                    "开心": "开心",
                    "幸福": "幸福",
                    "挂念": "挂念",
                    "思念": "思念",
                    "心疼": "心疼",
                    "担心": "担心",
                    "不安": "不安",
                    "失落": "失落",
                    "难过": "难过",
                    "焦虑": "焦虑",
                    "满足": "满足",
                    "欣慰": "欣慰",
                    "期待": "期待",
                    "好奇": "好奇",
                    "骄傲": "骄傲",
                    "感动": "感动",
                    "无奈": "无奈",
                    "疲惫": "疲惫",
                    "依赖": "依赖",
                    "依恋": "依恋",
                    "爱意": "爱意",
                    "关怀": "关怀",
                    "欣喜": "欣喜",
                    "惊喜": "惊喜",
                    "羞耻": "羞耻",
                    "愧疚": "愧疚",
                    "恐惧": "恐惧",
                    "愤怒": "愤怒",
                    "平静": "平静",
                    "冷静": "冷静",
                }
                extracted_emos = []
                for cn_word, en_word in emotion_chinese_map.items():
                    intensity_match = re.search(
                        rf"{cn_word}[（(]?\s*强度[：:]\s*(\d+)\s*[)）]?\s*|{cn_word}\s*[:：]\s*(\d+)",
                        text,
                    )
                    if intensity_match:
                        val = int(intensity_match.group(1) or intensity_match.group(2) or 50)
                        extracted_emos.append({"name": cn_word, "intensity": val})
                if extracted_emos:
                    frag_result["emotions"] = extracted_emos
                frag_result["source"] = "regex_fallback_v4"

                if frag_result:
                    logger.info(f"[灵魂] 策略4碎片解析成功: {list(frag_result.keys())}")
                    return frag_result

                return None

            result = _try_parse_json(response)
            if not result:
                logger.warning(f"[灵魂] 所有JSON解析策略失败: {response[:100]}")
                return None

            # 情绪由 LLM 分析得出

            # 显示分析结果
            emotions = result.get("emotions", [])
            if emotions:
                emotion_parts = []
                for emo in emotions:
                    name = emo.get("name", "未知")
                    intensity = emo.get("intensity", 50)
                    emotion_parts.append(f"{name}({intensity}%)")
                display_name = result.get("dominant_emotion", emotion_parts[0] if emotion_parts else "未知")
                display_intensity = emotions[0].get("intensity", 50) if emotions else 50
                extra = f"多情绪: {' + '.join(emotion_parts)}"
                source_tag = result.get("source", "")
                if source_tag:
                    extra += f" | [{source_tag}]"
                SoulDisplay.emotion_analysis(display_name, display_intensity, extra)
            else:
                SoulDisplay.emotion_analysis(
                    result.get("dominant_emotion", "未知"),
                    result.get("intensity", 50),
                    result.get("reasoning", "")[:50],
                )
            return result

        except Exception as e:
            import traceback

            logger.warning(f"[灵魂] AI分析失败: {e}")
            logger.warning(f"[灵魂] 错误堆栈: {traceback.format_exc()}")
            return None

    def _apply_ai_emotion(self, ai_result: Dict):
        """应用AI分析的情绪（支持多情绪）"""
        try:
            # 新格式：emotions 数组
            emotions = ai_result.get("emotions", [])
            if emotions:
                # 第一个是主导情绪
                for i, emo in enumerate(emotions):
                    name = emo.get("name", "")
                    intensity = emo.get("intensity", 50)
                    if name and intensity > 0:
                        # 第一个情绪强度100%，后续递减
                        scale = 1.0 if i == 0 else 0.6
                        self._adjust_emotion(name, (intensity - 40) * scale)
                return

            # 旧格式兼容
            emotion_name = ai_result.get("dominant_emotion", "")
            intensity = ai_result.get("intensity", 50)
            tags = ai_result.get("emotion_tags", [])

            if emotion_name and intensity > 0:
                self._adjust_emotion(emotion_name, intensity - 40)

                for tag in tags[:3]:
                    if tag != emotion_name:
                        self._adjust_emotion(tag, (intensity - 40) * 0.5)

        except Exception as e:
            logger.debug(f"[灵魂] 应用AI情绪失败: {e}")

    def _apply_default_fluctuation(self):
        """应用默认情绪波动"""
        fluctuation = _CONFIG.get("DEFAULT_EMOTION_FLUCTUATION", 5)
        if fluctuation <= 0:
            return

        import random

        for emotion in self.emotions.values():
            change = random.uniform(-fluctuation, fluctuation)
            new_value = max(10, min(90, emotion.value + change))
            emotion.value = new_value

    def _emotion_emergence(
        self,
        message: str,
        context: Dict,
        analysis: PsychologicalAnalysis,
        is_non_owner_in_group: bool = False,
        user_id=None,
        ai_inner_thought: Optional[str] = None,
        ai_attribution: Optional[str] = None,
        ai_reflection: Optional[str] = None,
    ):
        """情绪涌现 - 从配置文件读取规则 + 结合心理学分析"""
        msg = message.lower()

        # 内心活动 - 优先使用AI生成的
        if ai_inner_thought:
            SoulDisplay.inner_thought(ai_inner_thought[:80])

        # 显示归因 - AI优先，fallback到心理学分析
        if ai_attribution:
            SoulDisplay.attribution(ai_attribution)
        elif analysis and analysis.attribution:
            SoulDisplay.attribution(analysis.attribution)

        # 显示反思 - AI优先，fallback到心理学分析
        if ai_reflection:
            SoulDisplay.reflection(ai_reflection)
        elif analysis and analysis.reflection:
            SoulDisplay.reflection(analysis.reflection)

        # 从配置读取情绪触发规则
        triggers = _CONFIG.get("MESSAGE_EMOTION_TRIGGERS", {})

        # 检查每种触发类型
        for trigger_name, trigger_config in triggers.items():
            keywords = trigger_config.get("keywords", [])
            emotions_change = trigger_config.get("emotions", {})

            # 检查消息是否匹配关键词
            if any(keyword in msg for keyword in keywords):
                # 记录情绪变化
                changes_str = ", ".join([f"{k}+{v}" if v > 0 else f"{k}{v}" for k, v in emotions_change.items()])

                # 使用美化输出
                SoulDisplay.emotion_change(trigger_name, changes_str)

                # 应用情绪变化
                for emotion_name, delta in emotions_change.items():
                    self._adjust_emotion(emotion_name, delta)

        # 关系情境影响
        relationship = context.get("relationship")
        if relationship:
            rel_key = relationship.value

            # 群聊中非配置用户，使用不同的关系效果
            if is_non_owner_in_group and relationship == ContextType.INTIMATE:
                # 从配置获取非主人关系效果键名
                rel_key = _CONFIG.get("NON_OWNER_INTIMATE_KEY")
                logger.info(f"[灵魂] 群聊非主人用户，使用关系效果: {rel_key}")

            rel_effects = _CONFIG.get("RELATIONSHIP_EMOTION_EFFECTS", {}).get(rel_key, {})
            if rel_effects:
                changes_str = ", ".join([f"{k}+{v}" for k, v in rel_effects.items()])
                # 使用美化输出，从配置获取关系标签
                rel_labels = _CONFIG.get("RELATIONSHIP_LABELS", {})
                display_label = rel_labels.get(relationship.value, relationship.value)
                SoulDisplay.relationship_effect(display_label, changes_str)
                for emotion_name, delta in rel_effects.items():
                    self._adjust_emotion(emotion_name, delta)

        # 只有配置的主人才会触发额外的亲密情绪
        is_owner = False
        owner_id = _CONFIG.get("OWNER_USER_ID", "")
        if user_id and str(user_id) == owner_id:
            is_owner = True

        if relationship == ContextType.INTIMATE:
            if is_owner:
                self._adjust_emotion("爱意", 5)
            # 非主人用户不会触发额外爱意
        elif relationship == ContextType.COLD_WAR:
            self._adjust_emotion("不安", 10)
            self._adjust_emotion("委屈", 8)

    def _adjust_emotion(self, emotion_name: str, delta: float):
        """调整情绪值"""
        if emotion_name in self.emotions:
            emotion = self.emotions[emotion_name]
            new_value = max(0, min(100, emotion.value + delta))
            emotion.value = new_value
            emotion.timestamp = time.time()

    def _get_dominant_emotion(self) -> str:
        """获取当前主导情绪"""
        if not self.emotions:
            return "平静"

        max_emotion = max(self.emotions.values(), key=lambda e: e.value)
        return max_emotion.category.value

    def _get_emotion_summary(self) -> Dict[str, float]:
        """获取情绪摘要（多情绪）"""
        return {
            name: emp.value
            for name, emp in self.emotions.items()
            if emp.value > 20  # 只返回显著情绪
        }

    def _get_top_emotions(self, limit: int = 3) -> List[Dict[str, Any]]:
        """获取前N个显著情绪"""
        if not self.emotions:
            return [{"name": "平静", "value": 50}]

        sorted_emotions = sorted(self.emotions.items(), key=lambda x: x[1].value, reverse=True)
        return (
            [{"name": emo.category.value, "value": emo.value} for _, emo in sorted_emotions[:limit] if emo.value > 20][
                :limit
            ]
            if sorted_emotions
            else [{"name": "平静", "value": 50}]
        )

    def _check_pending_intents(self, context: Dict) -> Optional[str]:
        """检查待完成的意图"""
        if not self.pending_intents:
            return None

        # 从配置获取激活概率
        activation_chance = _CONFIG.get("INTENT_ACTIVATION_CHANCE", 0.4)

        # 检查是否可以激活
        for intent in self.pending_intents:
            if intent.can_activate():
                # 随机决定是否激活（避免每次都激活）
                if random.random() > (1 - activation_chance):
                    intent.record_attempt()
                    return f"对了，{intent.intent}"

        return None

    def add_pending_intent(self, intent: str, context: str, priority: int = 5):
        """添加待完成意图"""
        self.pending_intents.append(PendingIntent(intent=intent, context=context, priority=priority))
        logger.info(f"[灵魂发生器] 添加意图: {intent}")

    def _decay_emotions(self):
        """情绪衰减"""
        now = time.time()
        elapsed = now - self.last_update

        if elapsed < 10:  # 10秒内不衰减
            return

        decay_factor = elapsed / 60  # 每分钟衰减

        for emotion in self.emotions.values():
            if emotion.value > 30:  # 基础值以上才衰减
                decay = emotion.decay_rate * decay_factor * 10
                emotion.value = max(30, emotion.value - decay)

    def _generate_output(self, message: str, context: Dict, intent_response: Optional[str]) -> str:
        """生成输出"""
        # 如果有pending intent，优先输出
        if intent_response:
            return intent_response

        # 根据主导情绪生成不同风格回复
        dominant = self._get_dominant_emotion()

        # 从配置获取阈值
        high_threshold = _CONFIG.get("HIGH_EMOTION_THRESHOLD", 70)

        # 简化版：根据情绪值决定回复风格
        emotion_value = self.emotions.get(dominant, Emotion(EmotionCategory.PEACEFUL, 50)).value

        if emotion_value > high_threshold:
            # 高情绪 - 可能带有情绪表达
            if dominant in ["委屈", "不满", "傲娇", "赌气"]:
                # 傲娇反应 - 从配置获取
                responses = _CONFIG.get(
                    "HIGH_EMOTION_RESPONSES",
                    [
                        "哼~",
                        "好吧...",
                        "知道了啦~",
                    ],
                )
                return random.choice(responses)

        # 正常回复 - 不带明显情绪
        return ""  # 返回空字符串表示使用默认回复

    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            "dominant_emotion": self._get_dominant_emotion(),
            "emotions": self._get_emotion_summary(),
            "pending_intents": len(self.pending_intents),
            "cognitions": len(self.cognitions),
            "emotion_memories": len(self.emotion_memories),
        }


# 全局实例
_soul_generator: Optional[SoulGenerator] = None


def get_soul_generator() -> SoulGenerator:
    """获取全局灵魂发生器实例"""
    global _soul_generator
    if _soul_generator is None:
        _soul_generator = SoulGenerator()
    return _soul_generator


def init_soul_generator():
    """初始化灵魂发生器"""
    global _soul_generator
    _soul_generator = SoulGenerator()
    return _soul_generator
