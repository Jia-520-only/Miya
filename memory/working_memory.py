"""
工作记忆管理器 (WorkingMemoryManager)

职责：
- 工作记忆 (Working Memory)：给 AI 看的 Prompt，只保留当前正在聊的 3-5 条消息
- 话题折叠：旧话题折叠成一句话总结，不删除但降权
- 话题趋势检测 (Topic Drift Detection)：自动判断话题是否切换
- 低信息量输入检测：识别"不是"、"对的对的"等短消息
"""

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _load_working_memory_config() -> dict:
    """从 memory_config.json 加载工作记忆配置，回退到 text_config.json"""
    try:
        from memory import load_memory_config

        config = load_memory_config()
        wm = config.get("working_memory", {})
        if wm:
            return wm
    except Exception:
        pass

    try:
        import json
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config"
        text_config_path = config_dir / "text_config.json"
        if text_config_path.exists():
            with open(text_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("working_memory", {})
    except Exception as e:
        logger.warning(f"[工作记忆] 配置加载失败: {e}")
    return {}


@dataclass
class TopicSegment:
    """话题片段"""

    topic_id: str
    keywords: List[str]
    messages: List[str]  # 原始消息列表
    summary: str = ""  # 折叠后的总结
    start_time: float = 0.0
    last_active: float = 0.0
    message_count: int = 0
    is_active: bool = True  # 是否是当前活跃话题
    weight: float = 1.0  # 话题权重 (0.0-1.0)


@dataclass
class WorkingMemoryState:
    """工作记忆状态"""

    current_topic: Optional[TopicSegment] = None
    background_topics: List[TopicSegment] = field(default_factory=list)
    recent_messages: List[str] = field(default_factory=list)
    recent_senders: Dict[int, str] = field(default_factory=dict)
    topic_switch_count: int = 0
    last_update: float = 0.0
    media_analysis: List[Dict[str, str]] = field(default_factory=list)
    # 上次持久化的活跃时间（用于重启后检测间隔）
    last_persisted_active: float = 0.0


class TopicDriftDetector:
    """话题漂移检测器"""

    def __init__(self, drift_threshold: float = 0.4, window_size: int = 3):
        self.drift_threshold = drift_threshold
        self.window_size = window_size
        self._keyword_history: Dict[str, List[Set[str]]] = defaultdict(list)
        self._stopwords: Set[str] = set()
        self._load_stopwords()

    def _load_stopwords(self):
        """从配置加载停用词"""
        config = _load_working_memory_config()
        self._stopwords = set(config.get("stopwords", []))
        # 默认停用词（配置为空时使用）
        if not self._stopwords:
            self._stopwords = {
                "的",
                "了",
                "是",
                "在",
                "我",
                "你",
                "他",
                "她",
                "它",
                "有",
                "和",
                "与",
                "或",
                "但",
                "而",
                "就",
                "都",
                "也",
                "不",
                "没",
                "很",
                "太",
                "最",
                "更",
                "还",
                "又",
                "这",
                "那",
                "什么",
                "怎么",
                "为什么",
                "呢",
                "啊",
                "吧",
                "（",
                "）",
                "(",
                ")",
                "【",
                "】",
                "[",
                "]",
                "！",
                "!",
                "？",
                "?",
                "。",
                ".",
                "，",
                ",",
                "…",
                "一个",
                "一些",
                "一下",
                "一直",
                "一起",
                "一样",
                "对的对的",
                "不是",
                "是的",
                "嗯嗯",
                "哈哈",
                "呵呵",
            }

    def extract_keywords(self, text: str) -> Set[str]:
        """提取文本关键词（从配置加载停用词）"""
        words = []
        i = 0
        while i < len(text):
            for length in range(4, 1, -1):
                if i + length <= len(text):
                    word = text[i : i + length]
                    if word not in self._stopwords and not word.isdigit() and len(word.strip()) > 0:
                        words.append(word)
                        i += length - 1
                        break
            i += 1
        return set(words)

    def calculate_similarity(self, set1: set, set2: set) -> float:
        """计算两个关键词集合的 Jaccard 相似度"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def detect_drift(self, group_id: str, new_message: str) -> Tuple[bool, float]:
        """
        检测话题是否漂移

        Returns:
            (是否漂移, 相似度分数)
        """
        new_keywords = self.extract_keywords(new_message)
        history = self._keyword_history[group_id]

        if len(history) < self.window_size:
            history.append(new_keywords)
            return False, 1.0

        # 计算新消息与历史窗口的平均相似度
        window = history[-self.window_size :]
        similarities = [self.calculate_similarity(new_keywords, kw) for kw in window]
        avg_similarity = sum(similarities) / len(similarities)

        # 添加新关键词到历史
        history.append(new_keywords)
        if len(history) > self.window_size * 2:
            self._keyword_history[group_id] = history[-self.window_size :]

        is_drift = avg_similarity < self.drift_threshold
        if is_drift:
            logger.info(
                f"[话题漂移] group={group_id}, 相似度={avg_similarity:.2f} < {self.drift_threshold}, 判定为话题切换"
            )

        return is_drift, avg_similarity

    def get_current_topic_keywords(self, group_id: str) -> set:
        """获取当前话题关键词"""
        history = self._keyword_history.get(group_id, [])
        if not history:
            return set()
        # 合并最近窗口的关键词
        all_keywords = set()
        for kw in history[-self.window_size :]:
            all_keywords.update(kw)
        return all_keywords

    def reset(self, group_id: str):
        """重置某个群的话题历史"""
        self._keyword_history.pop(group_id, None)


class WorkingMemoryManager:
    """
    工作记忆管理器

    架构：
    ┌─────────────────────────────────────────────────────────────┐
    │                    工作记忆管理器                            │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │  ┌─────────────────────┐  ┌─────────────────────┐          │
    │  │   工作记忆           │  │   背景记忆           │          │
    │  │   (Working Memory)  │  │   (Background Memory)│          │
    │  │                     │  │                     │          │
    │  │ - 当前 3-5 条消息    │  │ - 折叠的旧话题       │          │
    │  │ - 当前活跃话题       │  │ - 话题摘要           │          │
    │  │ - 高权重            │  │ - 低权重            │          │
    │  └─────────────────────┘  └─────────────────────┘          │
    │           │                          │                      │
    │           ▼                          ▼                      │
    │  ┌─────────────────────────────────────────────┐          │
    │  │              Prompt 注入                     │          │
    │  │  [当前对话] + [背景摘要] + [话题切换提示]    │          │
    │  └─────────────────────────────────────────────┘          │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        max_recent_messages: int = 15,
        max_background_topics: int = 5,
        topic_decay_rate: float = 0.3,
        topic_switch_threshold: int = 3,
        drift_threshold: float = 0.2,
        min_messages_before_fold: int = 5,
    ):
        self.max_recent = max_recent_messages
        self.max_background = max_background_topics
        self.decay_rate = topic_decay_rate
        self.switch_threshold = topic_switch_threshold
        self.min_messages_before_fold = min_messages_before_fold

        self.drift_detector = TopicDriftDetector(drift_threshold=drift_threshold)
        self._states: Dict[str, WorkingMemoryState] = {}
        self._message_counts: Dict[str, int] = defaultdict(int)

        self._persist_file = Path("data/working_memory.json")
        self._ensure_data_dir()
        self._load()

        # 批量刷盘优化
        self._dirty: bool = False
        self._last_save: float = time.time()
        self._save_interval: float = 5.0  # 5秒批量写入一次
        self._save_threshold: int = 10  # 或累积10条消息写一次

        logger.info("[工作记忆] 管理器初始化完成 (批量刷盘模式)")

    def _get_state(self, group_id: str) -> WorkingMemoryState:
        if group_id not in self._states:
            self._states[group_id] = WorkingMemoryState()
        return self._states[group_id]

    def add_message(
        self,
        group_id: str,
        sender: str,
        content: str,
        is_at_bot: bool = False,
        sender_id: int = 0,
    ) -> Dict:
        """
        添加消息并更新工作记忆状态

        Args:
            group_id: 群ID或会话ID
            sender: 发送者名字
            content: 消息内容
            is_at_bot: 是否@机器人
            sender_id: 发送者ID（用于区分同名用户）【新增】
        Returns:
            包含话题状态信息的字典
        """
        state = self._get_state(group_id)
        self._message_counts[group_id] += 1

        # 1. 检测话题漂移
        is_drift, similarity = self.drift_detector.detect_drift(group_id, content)

        # 2. 检测低信息量输入
        is_low_info = self._is_low_info(content)

        # 3. 更新工作记忆
        # 【修复】消息格式中加入发送者ID，用于区分同名用户
        if sender_id:
            message_with_id = f"{sender}[{sender_id}]: {content}"
            state.recent_senders[sender_id] = sender
            # 记录最近活跃时间（用于时间感知矫正）
            now = time.time()
            if state.last_update < now:
                state.last_active_time = now
        else:
            message_with_id = f"{sender}: {content}"
        state.recent_messages.append(message_with_id)
        if len(state.recent_messages) > self.max_recent:
            state.recent_messages = state.recent_messages[-self.max_recent :]

        # 4. 如果话题漂移且消息数足够，折叠旧话题
        if is_drift and state.current_topic and self._message_counts[group_id] >= self.min_messages_before_fold:
            self._fold_current_topic(state)
            state.topic_switch_count += 1

        # 5. 更新或创建当前话题
        # 【修复】话题消息也加入发送者ID
        topic_msg = f"{sender}[{sender_id}]: {content}" if sender_id else f"{sender}: {content}"
        if is_drift or state.current_topic is None:
            state.current_topic = self._create_new_topic(group_id, sender, content, sender_id)
        else:
            state.current_topic.messages.append(topic_msg)
            state.current_topic.last_active = time.time()
            state.current_topic.message_count += 1
            # 更新关键词
            state.current_topic.keywords = list(self.drift_detector.get_current_topic_keywords(group_id))

        state.last_update = time.time()

        # 批量刷盘：标记脏数据，延迟写入
        self._dirty = True
        self._maybe_flush()

        return {
            "is_drift": is_drift,
            "similarity": similarity,
            "is_low_info": is_low_info,
            "current_topic": state.current_topic.summary if state.current_topic else "",
            "recent_messages": state.recent_messages.copy(),
            "background_topics": [{"summary": t.summary, "weight": t.weight} for t in state.background_topics[-3:]],
            "media_analysis": state.media_analysis.copy(),
        }

    def add_media_analysis(
        self,
        group_id: str,
        analysis_type: str,
        description: str,
        labels: str = "",
        source: str = "",
    ):
        """添加图片/文件分析结果到专门记忆区块"""
        state = self._get_state(group_id)
        analysis_record = {
            "type": analysis_type,  # image, file, etc
            "description": description[:500],  # 限制长度
            "labels": labels[:200] if labels else "",
            "source": source,
            "timestamp": time.time(),
        }
        state.media_analysis.append(analysis_record)
        # 只保留最近5条分析记录
        if len(state.media_analysis) > 5:
            state.media_analysis = state.media_analysis[-5:]
        # 更新最后活跃时间
        state.last_update = time.time()
        # 批量刷盘
        self._dirty = True
        self._maybe_flush()

    def _is_low_info(self, content: str) -> bool:
        """检测是否为低信息量输入（从配置加载）"""
        content = content.strip()
        # 短消息检测
        if len(content) <= 3:
            return True
        # 低信息量词汇检测（从配置加载）
        config = _load_working_memory_config()
        low_info_words = config.get("low_info_words", [])
        return any(content == word for word in low_info_words)

    def _create_new_topic(self, group_id: str, sender: str, content: str, sender_id: int = 0) -> TopicSegment:
        """创建新话题"""
        topic_id = hashlib.md5(f"{group_id}_{time.time()}".encode()).hexdigest()[:8]
        keywords = list(self.drift_detector.get_current_topic_keywords(group_id))
        # 【修复】新话题消息也加入发送者ID
        first_msg = f"{sender}[{sender_id}]: {content}" if sender_id else f"{sender}: {content}"

        return TopicSegment(
            topic_id=topic_id,
            keywords=keywords,
            messages=[first_msg],
            summary=f"[新话题] {sender}: {content[:30]}...",
            start_time=time.time(),
            last_active=time.time(),
            message_count=1,
            is_active=True,
            weight=1.0,
        )

    def _fold_current_topic(self, state: WorkingMemoryState):
        """折叠当前话题到背景记忆"""
        if not state.current_topic:
            return

        old_topic = state.current_topic
        old_topic.is_active = False

        # 生成折叠摘要
        if old_topic.message_count > 2:
            first_msg = old_topic.messages[0] if old_topic.messages else ""
            last_msg = old_topic.messages[-1] if old_topic.messages else ""
            old_topic.summary = f"[背景] 之前聊到：{first_msg[:30]}... 最后提到：{last_msg[:30]}..."
        else:
            old_topic.summary = f"[背景] {' | '.join(old_topic.messages[:2])}"

        # 降低权重
        old_topic.weight = max(0.1, old_topic.weight - self.decay_rate)

        # 移入背景记忆
        state.background_topics.append(old_topic)

        # 限制背景记忆数量
        if len(state.background_topics) > self.max_background:
            state.background_topics = state.background_topics[-self.max_background :]

        logger.info(f"[话题折叠] 旧话题已折叠: {old_topic.summary[:50]}..., 权重={old_topic.weight:.2f}")

    def build_prompt_context(self, group_id: str) -> str:
        """
        构建 Prompt 上下文（分层记忆架构 + 时间衰减恢复）

        分层策略：
        1. 即时层（最近3条）：完整原文，让AI理解当前对话
        2. 摘要层（4-15条）：一句话摘要，保留话题脉络
        3. 话题层（15+条）：话题标签+关键词，提供背景

        时间衰减恢复（重启后）：
        - HOT：完整恢复，无缝接续
        - WARM：注入摘要 + 提示自然接续
        - COLD：注入标签 + 最后1-2条原文
        - DORMANT：不注入
        """
        state = self._get_state(group_id)

        # === 时间衰减恢复上下文 ===
        recovery_context = self._build_recovery_context(group_id, state)

        if not state.recent_messages and not state.background_topics and not recovery_context:
            return ""

        lines = []

        # 恢复上下文优先插入
        if recovery_context:
            lines.append(recovery_context)

        total_msgs = len(state.recent_messages)

        # === 第1层：即时层（最近3条完整原文）===
        recent_count = min(3, total_msgs)
        if recent_count > 0:
            lines.append("【当前对话】")
            for msg in state.recent_messages[-recent_count:]:
                lines.append(msg)

        # === 第2层：摘要层（4-15条压缩摘要）===
        if total_msgs > 3:
            older_msgs = state.recent_messages[:-recent_count]
            summary_msgs = []
            for i in range(0, len(older_msgs), 3):
                chunk = older_msgs[i : i + 3]
                if len(chunk) == 1:
                    summary_msgs.append(chunk[0])
                else:
                    senders = []
                    keywords = []
                    for msg in chunk:
                        if ":" in msg:
                            sender, content = msg.split(":", 1)
                            senders.append(sender.strip())
                            words = [w for w in content.strip().split() if len(w) > 1]
                            keywords.extend(words[:2])
                    unique_senders = list(dict.fromkeys(senders))
                    unique_keywords = list(dict.fromkeys(keywords))[:5]
                    if unique_senders and unique_keywords:
                        summary = f"{'/'.join(unique_senders)} 讨论了 {'/'.join(unique_keywords)}"
                    elif unique_senders:
                        summary = f"{'/'.join(unique_senders)} 聊了几句"
                    else:
                        summary = "几条短消息"
                    summary_msgs.append(f"[摘要] {summary}")

            if summary_msgs:
                lines.append("\n【近期话题】")
                lines.extend(summary_msgs[-5:])

        # === 第3层：话题层（背景话题）===
        if state.background_topics:
            active_topics = [t for t in state.background_topics[-3:] if t.weight > 0.15]
            if active_topics:
                lines.append("\n【之前聊过的话题】")
                for topic in active_topics:
                    lines.append(f"  - {topic.summary}")

        # === 话题关键词提示 ===
        if state.recent_messages:
            current_keywords = self.drift_detector.get_current_topic_keywords(group_id)
            if current_keywords:
                kw_str = "、".join(list(current_keywords)[:5])
                lines.append(f"\n[当前话题关键词] {kw_str}")

        # === 媒体分析记忆区块（图片/文件分析结果）===
        if state.media_analysis:
            lines.append("\n【已识别内容】")
            for analysis in state.media_analysis[-3:]:
                type_emoji = "🖼️" if analysis.get("type") == "image" else "📄"
                desc = analysis.get("description", "")[:100]
                labels = analysis.get("labels", "")
                lines.append(f"  {type_emoji} {desc}")
                if labels:
                    lines.append(f"     标签: {labels}")

        return "\n".join(lines)

    def _build_recovery_context(self, group_id: str, state: WorkingMemoryState) -> str:
        """构建时间衰减恢复上下文（重启后首次对话时注入）"""
        from memory.session_decay import (
            SessionPhase,
            generate_cold_summary,
            generate_topic_summary,
            get_phase,
            get_phase_description,
        )

        recovery_prompts = _load_working_memory_config().get("recovery_prompts", {})
        yesterday_context = recovery_prompts.get(
            "yesterday_context", "这是昨天的对话内容，已经过去一天了，请以今天的新对话为主"
        )
        yesterday_bare = recovery_prompts.get("yesterday_bare", "这是昨天的对话，已经是新的一天了")
        warm_hint = recovery_prompts.get("warm_hint", "以上为上次对话摘要，请自然接续")

        now = time.time()

        # 用持久化的活跃时间（不受 add_message 重置影响）
        persisted_active = state.last_persisted_active
        if persisted_active <= 0:
            persisted_active = self._get_last_message_time_from_disk(group_id)

        if persisted_active <= 0:
            return ""

        elapsed = now - persisted_active
        phase = get_phase(elapsed)

        if phase == SessionPhase.DORMANT:
            return ""

        phase_desc = get_phase_description(phase, last_active_time=persisted_active)
        extra_messages = self._load_conversation_history_messages(group_id)

        if phase == SessionPhase.HOT:
            if extra_messages and not state.recent_messages:
                state.recent_messages = extra_messages[-self.max_recent :]
            return ""

        elif phase == SessionPhase.WARM:
            topic_history = self._get_topic_history_for(group_id)
            messages_for_summary = state.recent_messages[-10:] if state.recent_messages else extra_messages[-10:]
            summary = generate_topic_summary(messages_for_summary) if messages_for_summary else ""
            topic_tags = ""
            if topic_history:
                unique = list(dict.fromkeys(topic_history))[:3]
                topic_tags = f"【{'、'.join(unique)}】"
            return f"【{phase_desc}】{topic_tags}{summary}\n[提示] {warm_hint}"

        elif phase == SessionPhase.COLD:
            topic_history = self._get_topic_history_for(group_id)
            messages_for_summary = state.recent_messages if state.recent_messages else extra_messages[-5:]
            summary = generate_cold_summary(messages_for_summary, topic_history)
            if summary:
                return f"【{phase_desc}】{summary}"
            return ""

        elif phase == SessionPhase.YESTERDAY:
            topic_history = self._get_topic_history_for(group_id)
            messages_for_summary = state.recent_messages[-3:] if state.recent_messages else extra_messages[-3:]
            summary = generate_cold_summary(messages_for_summary, topic_history)
            if summary:
                return f"【{phase_desc}】{summary}\n[提示] {yesterday_context}"
            return f"【{phase_desc}】[提示] {yesterday_bare}"

        return ""

    def _load_conversation_history_messages(self, group_id: str) -> list:
        """从 conversation history 文件中加载原始消息（含模糊匹配）"""
        try:
            messages = self._try_load_history(group_id)
            if messages:
                return messages

            user_id = group_id.split("_")[-1] if "_" in group_id else group_id
            if user_id.isdigit():
                session_id = self._find_session_file_for_user(user_id)
                if session_id:
                    return self._try_load_history(session_id)
        except Exception as e:
            logger.debug(f"[工作记忆] 加载历史消息失败 ({group_id}): {e}")
        return []

    def _try_load_history(self, session_id: str) -> list:
        """精确加载某个 session_id 的历史消息"""
        try:
            import json
            from pathlib import Path

            data_dir = Path("data/conversations")
            hash_obj = __import__("hashlib").md5(session_id.encode("utf-8"))
            file_path = data_dir / f"session_{hash_obj.hexdigest()[:16]}.json"

            if not file_path.exists():
                return []

            with open(file_path, "r", encoding="utf-8") as f:
                messages = json.load(f)

            result = []
            for m in messages:
                role = m.get("role", "")
                content = m.get("content", "")
                if not content:
                    continue
                sender = m.get("metadata", {}).get("sender_name", role)
                if sender == "user":
                    sender = ""
                result.append(f"{sender}: {content[:80]}" if sender else content[:80])

            return result
        except Exception:
            return []

    def _get_topic_history_for(self, group_id: str) -> list:
        """从持久化的话题追踪文件获取话题历史"""
        try:
            import json
            from pathlib import Path

            topic_file = Path("data/conversation_context_state.json")
            if not topic_file.exists():
                return []
            with open(topic_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("topic_history", {}).get(group_id, [])
        except Exception:
            return []

    def _get_last_message_time_from_disk(self, group_id: str) -> float:
        """从 conversation history 文件推断最后活跃时间（含模糊匹配）"""
        try:
            result = self._try_get_time_from_disk(group_id)
            if result > 0:
                return result

            # 精确匹配失败 → 从 key 中提取 user_id 做模糊搜索
            user_id = group_id.split("_")[-1] if "_" in group_id else group_id
            if user_id.isdigit():
                result = self._scan_sessions_for_user(user_id)
                if result > 0:
                    return result
        except Exception:
            pass
        return 0.0

    def _try_get_time_from_disk(self, session_id: str) -> float:
        """精确匹配某个 session_id 的最后消息时间"""
        try:
            import json
            from pathlib import Path

            data_dir = Path("data/conversations")
            hash_obj = __import__("hashlib").md5(session_id.encode("utf-8"))
            file_path = data_dir / f"session_{hash_obj.hexdigest()[:16]}.json"

            if not file_path.exists():
                return 0.0

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                if messages:
                    last_ts = messages[-1].get("timestamp", "")
                    if last_ts:
                        from datetime import datetime

                        return datetime.fromisoformat(last_ts).timestamp()
            except Exception:
                pass

            return file_path.stat().st_mtime
        except Exception:
            return 0.0

    def _scan_sessions_for_user(self, user_id: str) -> float:
        """扫描所有会话文件，找到包含指定 user_id 的会话，返回最后时间"""
        try:
            import json
            from pathlib import Path

            data_dir = Path("data/conversations")
            best_time = 0.0

            for file_path in data_dir.glob("session_*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        messages = json.load(f)
                    if not messages:
                        continue

                    sid = messages[0].get("session_id", "")
                    is_private = sid.endswith(f"_{user_id}") or sid.endswith(f"_用户-{user_id}")
                    if not is_private:
                        continue

                    last_ts = messages[-1].get("timestamp", "")
                    if last_ts:
                        from datetime import datetime

                        t = datetime.fromisoformat(last_ts).timestamp()
                        if t > best_time:
                            best_time = t
                except Exception:
                    continue

            return best_time
        except Exception:
            return 0.0

    def _find_session_file_for_user(self, user_id: str) -> str:
        """找到包含指定 user_id 的会话文件路径，返回 session_id"""
        try:
            import json
            from pathlib import Path

            data_dir = Path("data/conversations")

            for file_path in data_dir.glob("session_*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        messages = json.load(f)
                    if not messages:
                        continue

                    sid = messages[0].get("session_id", "")
                    if sid.endswith(f"_{user_id}") or sid.endswith(f"_用户-{user_id}"):
                        return sid
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def get_full_context(self, group_id: str) -> Dict:
        """获取完整上下文（用于调试或特殊查询）"""
        state = self._get_state(group_id)
        return {
            "recent_messages": state.recent_messages.copy(),
            "current_topic": {
                "summary": state.current_topic.summary if state.current_topic else "",
                "keywords": state.current_topic.keywords if state.current_topic else [],
                "message_count": state.current_topic.message_count if state.current_topic else 0,
            }
            if state.current_topic
            else None,
            "background_topics": [
                {
                    "summary": t.summary,
                    "weight": t.weight,
                    "message_count": t.message_count,
                }
                for t in state.background_topics
            ],
            "topic_switch_count": state.topic_switch_count,
        }

    def cleanup_expired(self, max_age_seconds: int = 3600):
        """清理过期的工作记忆"""
        cutoff = time.time() - max_age_seconds
        expired_groups = [gid for gid, state in self._states.items() if state.last_update < cutoff]
        for gid in expired_groups:
            del self._states[gid]
            self.drift_detector.reset(gid)
            self._message_counts.pop(gid, None)

        if expired_groups:
            logger.debug(f"[工作记忆] 清理了 {len(expired_groups)} 个过期群记忆")

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        self._persist_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """从文件加载工作记忆（含分层时间衰减恢复）"""
        if not self._persist_file.exists():
            return
        try:
            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()
            loaded = 0

            for gid, state_data in data.get("states", {}).items():
                media = state_data.get("media_analysis", [])
                recent_msgs = state_data.get("recent_messages", [])
                recent_senders_raw = state_data.get("recent_senders", {})
                last_active = state_data.get("last_active_time", 0)

                # 旧数据没有时间戳 → 用文件修改时间作为近似
                if last_active <= 0 and self._persist_file.exists():
                    last_active = self._persist_file.stat().st_mtime
                elif last_active <= 0:
                    last_active = now

                state = WorkingMemoryState()
                state.media_analysis = media
                state.recent_messages = recent_msgs[-self.max_recent :] if recent_msgs else []
                state.recent_senders = (
                    {int(k) if k.isdigit() else k: v for k, v in recent_senders_raw.items()}
                    if recent_senders_raw
                    else {}
                )
                state.last_update = last_active
                state.last_persisted_active = last_active

                # 恢复话题状态
                topic_data = state_data.get("current_topic")
                if topic_data:
                    state.current_topic = TopicSegment(
                        topic_id=topic_data.get("topic_id", ""),
                        keywords=topic_data.get("keywords", []),
                        messages=[],
                        summary=topic_data.get("summary", ""),
                        start_time=topic_data.get("start_time", 0),
                        last_active=topic_data.get("last_active", last_active),
                        message_count=topic_data.get("message_count", 0),
                        is_active=topic_data.get("is_active", False),
                        weight=max(0.1, topic_data.get("weight", 1.0) - self.decay_rate),
                    )

                bg_data = state_data.get("background_topics", [])
                for bt in bg_data:
                    state.background_topics.append(
                        TopicSegment(
                            topic_id=bt.get("topic_id", ""),
                            keywords=bt.get("keywords", []),
                            messages=[],
                            summary=bt.get("summary", ""),
                            start_time=bt.get("start_time", 0),
                            last_active=bt.get("last_active", last_active),
                            message_count=bt.get("message_count", 0),
                            is_active=False,
                            weight=max(0.1, bt.get("weight", 1.0) - self.decay_rate * 2),
                        )
                    )

                state.topic_switch_count = state_data.get("topic_switch_count", 0)

                self._states[gid] = state
                loaded += 1

            # 不在这里过滤休眠状态——phase 判断在 build_prompt_context 时进行
            if loaded > 0:
                logger.info(f"[工作记忆] 加载了 {loaded} 个会话状态")
        except Exception as e:
            logger.warning(f"[工作记忆] 加载失败: {e}")

    def save(self):
        """立即保存工作记忆到文件（强制落盘）"""
        self._do_save()
        self._dirty = False
        self._last_save = time.time()

    def _maybe_flush(self):
        """批量刷盘：满足时间间隔或累积阈值时写入"""
        total_messages = sum(self._message_counts.values())
        elapsed = time.time() - self._last_save
        if self._dirty and (elapsed >= self._save_interval or total_messages >= self._save_threshold):
            self._do_save()
            self._dirty = False
            self._last_save = time.time()

    def _do_save(self):
        """实际写入磁盘"""
        try:
            data = {
                "states": {
                    gid: {
                        "media_analysis": state.media_analysis,
                        "recent_messages": state.recent_messages,
                        "recent_senders": {str(k): v for k, v in state.recent_senders.items()},
                        "last_active_time": state.last_update,
                        "current_topic": {
                            "topic_id": state.current_topic.topic_id,
                            "keywords": state.current_topic.keywords,
                            "summary": state.current_topic.summary,
                            "start_time": state.current_topic.start_time,
                            "last_active": state.current_topic.last_active,
                            "message_count": state.current_topic.message_count,
                            "is_active": state.current_topic.is_active,
                            "weight": state.current_topic.weight,
                        }
                        if state.current_topic
                        else None,
                        "background_topics": [
                            {
                                "topic_id": t.topic_id,
                                "keywords": t.keywords,
                                "summary": t.summary,
                                "start_time": t.start_time,
                                "last_active": t.last_active,
                                "message_count": t.message_count,
                                "is_active": t.is_active,
                                "weight": t.weight,
                            }
                            for t in state.background_topics[-self.max_background :]
                        ],
                        "topic_switch_count": state.topic_switch_count,
                    }
                    for gid, state in self._states.items()
                    if state.media_analysis or state.recent_messages
                }
            }
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[工作记忆] 已保存 {len(data['states'])} 个群的上下文")
        except Exception as e:
            logger.warning(f"[工作记忆] 保存失败: {e}")


# 全局单例
_working_memory: Optional[WorkingMemoryManager] = None


def get_working_memory(**kwargs) -> WorkingMemoryManager:
    """获取工作记忆管理器单例"""
    global _working_memory
    if _working_memory is None:
        _working_memory = WorkingMemoryManager(**kwargs)
    return _working_memory
