"""对话历史上下文管理器

负责对话历史的智能加载和上下文管理
新增：话题连续性检测、主动回忆机制、上下文压缩
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from core.token_utils import count_message_tokens

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """对话历史上下文管理器

    职责：
    - 智能判断是否需要加载历史对话
    - 根据Token限制动态调整上下文大小
    - 检测用户的"回忆"意图
    - 话题连续性检测
    - 主动回忆机制
    - 多轮对话流程追踪
    """

    _cog_engine = None  # V4.1.11: 缓存认知引擎引用

    # 话题关键词映射
    TOPIC_KEYWORDS = {
        "学习": [
            "上课",
            "学习",
            "考试",
            "作业",
            "学校",
            "老师",
            "同学",
            "补课",
            "自习",
            "复习",
            "预习",
        ],
        "吃饭": [
            "吃饭",
            "饿",
            "饱",
            "零食",
            "外卖",
            "餐厅",
            "食堂",
            "菜",
            "口味",
            "厨师",
        ],
        "休息": [
            "睡觉",
            "困",
            "累",
            "休息",
            "放假",
            "周末",
            "假期",
            "娱乐",
            "游戏",
            "动漫",
        ],
        "情绪": [
            "难过",
            "开心",
            "生气",
            "害怕",
            "担心",
            "焦虑",
            "压力",
            "烦恼",
            "郁闷",
        ],
        "社交": ["朋友", "同学", "家人", "聊天", "聚会", "社交", "联系人"],
    }

    def __init__(
        self,
        memory_net,
        enable_conversation_context: bool = True,
        conversation_context_max_count: int = 20,
        conversation_context_max_tokens: int = 6000,
    ):
        # 从配置文件加载配置
        config = self._load_config()
        self.conversation_context_config = config

        self.memory_net = memory_net
        self.enable_conversation_context = config.get("enabled", enable_conversation_context)
        self.conversation_context_max_count = config.get("max_count", conversation_context_max_count)
        self.conversation_context_max_tokens = config.get("max_tokens", conversation_context_max_tokens)

        # 从配置文件加载回忆关键词
        self.recall_patterns = config.get("recall_patterns", [])

        # 话题跟踪（用于多轮对话追踪）
        self._topic_history: Dict[str, List[str]] = defaultdict(list)  # session_id -> 话题列表
        self._last_topics: Dict[str, str] = {}  # session_id -> 最近话题
        self._conversation_turns: Dict[str, int] = defaultdict(int)  # session_id -> 对话轮次
        self._pending_intent: Dict[str, str] = {}  # session_id -> 未完成的意图

        from core.path_resolver import get_data_dir

        self._persist_file = get_data_dir() / "conversation_context_state.json"
        self._persist_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_topic_state()

    def _load_config(self) -> dict:
        """从 text_config.json 加载对话上下文配置"""
        try:
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    full_config = json.load(f)
                cc_config = full_config.get("conversation_context", {})
                cc_config["important_topic_keywords"] = full_config.get("important_topic_keywords", [])
                return cc_config
        except Exception as e:
            logger.warning(f"[对话上下文] 加载配置失败: {e}")
        return {}

    def _update_topic_tracking(self, session_id: str, user_input: str) -> str:
        """更新话题追踪，返回当前话题"""
        current_topic = self._detect_topic(user_input)

        important_keywords = self.conversation_context_config.get("important_topic_keywords", [])
        is_important = any(kw in user_input for kw in important_keywords)

        # 增量对话轮次
        self._conversation_turns[session_id] += 1

        if current_topic:
            if session_id not in self._topic_history:
                self._topic_history[session_id] = []
            self._topic_history[session_id].append(current_topic)
            max_history = 50 if is_important else 20
            if len(self._topic_history[session_id]) > max_history:
                self._topic_history[session_id] = self._topic_history[session_id][-max_history:]
            self._last_topics[session_id] = current_topic

        self._save_topic_state()

        return current_topic or ""

    def _load_topic_state(self):
        """从磁盘恢复话题追踪状态（含时间衰减过滤）"""
        if not self._persist_file.exists():
            return
        try:
            import json
            import time

            from memory.session_decay import SessionPhase, get_phase

            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()
            last_active_times = data.get("last_active_time", {})
            filtered_sessions = 0

            # 过滤休眠会话
            for session_id in list(data.get("last_topics", {}).keys()):
                last_time = last_active_times.get(session_id, 0)
                if last_time > 0:
                    elapsed = now - last_time
                    phase = get_phase(elapsed)
                    if phase == SessionPhase.DORMANT:
                        filtered_sessions += 1
                        continue

                self._last_topics[session_id] = data["last_topics"][session_id]

            for session_id in list(data.get("topic_history", {}).keys()):
                if session_id not in self._last_topics:
                    continue
                self._topic_history[session_id] = data["topic_history"][session_id]

            for session_id in list(data.get("conversation_turns", {}).keys()):
                if session_id not in self._last_topics:
                    continue
                self._conversation_turns[session_id] = data["conversation_turns"][session_id]

            self._pending_intent = {
                sid: v for sid, v in data.get("pending_intent", {}).items() if sid in self._last_topics
            }
            self._last_active_time = last_active_times

            loaded = len(self._last_topics)
            if loaded > 0 or filtered_sessions > 0:
                logger.info(f"[对话上下文] 恢复话题状态: {loaded} 个会话, 跳过 {filtered_sessions} 个休眠")
        except Exception as e:
            logger.warning(f"[对话上下文] 恢复话题状态失败: {e}")

    def _save_topic_state(self):
        """持久化话题追踪状态到磁盘"""
        try:
            import json

            now = __import__("time").time()
            self._last_active_time = getattr(self, "_last_active_time", {})
            for sid in self._conversation_turns:
                if sid not in self._last_active_time:
                    self._last_active_time[sid] = now

            data = {
                "topic_history": dict(self._topic_history),
                "last_topics": dict(self._last_topics),
                "conversation_turns": dict(self._conversation_turns),
                "pending_intent": dict(self._pending_intent),
                "last_active_time": dict(self._last_active_time),
            }
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[对话上下文] 保存话题状态失败: {e}")

    def _detect_topic(self, text: str) -> str:
        """检测当前输入的话题"""
        if not text:
            return ""
        text_lower = text.lower()
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return ""

    def get_topic_context(self, session_id: str) -> str:
        """获取话题上下文信息（含时间衰减状态）"""
        last_topic = self._last_topics.get(session_id, "")
        turns = self._conversation_turns.get(session_id, 0)
        if not last_topic:
            return ""

        last_active = self._last_active_time.get(session_id, 0)
        if last_active > 0:
            import time

            from memory.session_decay import (
                SessionPhase,
                get_phase,
                get_phase_description,
            )

            elapsed = time.time() - last_active
            phase = get_phase(elapsed)
            if phase != SessionPhase.HOT:
                desc = get_phase_description(phase, last_active_time=last_active)
                return f"[话题追踪] {desc} | 话题: {last_topic}"

        return f"[话题追踪] 当前话题: {last_topic}, 连续对话: {turns}轮"

    def check_needs_recall(self, user_input: str) -> bool:
        """检测用户是否在问关于过去的问题"""
        if not user_input:
            return False
        recall_patterns = [
            "你记得",
            "你还记得",
            "记得",
            "上次",
            "上次我们",
            "之前",
            "昨天",
            "前天",
            "以前",
            "我们聊过",
            "曾经",
            "回忆",
        ]
        return any(p in user_input for p in recall_patterns)

    async def get_conversation_context(self, session_id: str, user_id: str = "", current_input: str = "") -> List[Dict]:
        if not self.enable_conversation_context:
            return []

        conversation_history_ready = self.memory_net and self.memory_net.conversation_history

        if current_input:
            self._update_topic_tracking(session_id, current_input)

        needs_recall = self.check_needs_recall(current_input)
        is_deep_discussion = self._is_deep_discussion(current_input)
        base_limit = self.conversation_context_max_count

        if needs_recall:
            max_messages = max(base_limit * 2, 80)
            logger.info(f"[对话上下文] 用户正在回忆过去，加载{max_messages}条: {session_id}")
        elif is_deep_discussion:
            max_messages = max(base_limit * 2, 60)
            logger.debug(f"[对话上下文] 检测到深度讨论，加载{max_messages}条: {session_id}")
        else:
            max_messages = base_limit
            logger.debug(f"[对话上下文] 正常对话，加载{max_messages}条: {session_id}")

        context = []
        total_tokens = 0

        if conversation_history_ready:
            try:
                messages = await self.memory_net.conversation_history.get_history(session_id, limit=max_messages)

                if messages:
                    recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
                    logger.debug(f"[对话上下文] MemoryNet 加载对话历史: {len(recent_messages)} 条")

                    for msg in recent_messages:
                        token_estimate = count_message_tokens(msg.content)
                        if total_tokens + token_estimate > self.conversation_context_max_tokens:
                            break
                        context.append(
                            {
                                "role": msg.role,
                                "content": msg.content,
                                "timestamp": msg.timestamp,
                                "metadata": msg.metadata or {},
                            }
                        )
                        total_tokens += token_estimate
            except Exception as e:
                logger.debug(f"[对话上下文] MemoryNet 加载失败: {e}")

        # 回退: MiyaMemoryCore 统一记忆后端（SQLite+JSON，跨平台回溯）
        if not context and user_id:
            try:
                from memory import get_user_dialogue

                memories = await get_user_dialogue(user_id=user_id, limit=max_messages)
                if memories:
                    for m in memories:
                        content = getattr(m, "content", "")
                        token_estimate = count_message_tokens(content)
                        if total_tokens + token_estimate > self.conversation_context_max_tokens:
                            break
                        context.append(
                            {
                                "role": getattr(m, "role", "user"),
                                "content": content,
                                "timestamp": getattr(m, "created_at", ""),
                            }
                        )
                        total_tokens += token_estimate
                    logger.info(f"[对话上下文] MiyaMemoryCore 加载: user={user_id}, count={len(context)}")
            except Exception as e:
                logger.debug(f"[对话上下文] MiyaMemoryCore 加载失败: {e}")
                logger.error(f"[对话上下文] 获取对话历史失败: {e}")

        return context

    def _is_deep_discussion(self, user_input: str) -> bool:
        """
        检测是否是深度讨论

        Args:
            user_input: 用户输入

        Returns:
            是否是深度讨论
        """
        if not user_input or not isinstance(user_input, str):
            return False

        # 长消息通常是深度讨论
        if len(user_input) > 50:
            return True

        # 包含多个话题词（V4.1.11: 缓存引擎引用）
        if ConversationContextManager._cog_engine is None:
            from memory.cognitive_engine import get_cognitive_engine

            ConversationContextManager._cog_engine = get_cognitive_engine()
        engine = ConversationContextManager._cog_engine
        topic_count = 0
        for _topic, keywords in engine.topic_keywords.items():
            if any(kw in user_input for kw in keywords):
                topic_count += 1

        if topic_count >= 2:
            return True

        # 问题形式（包含多个问号或疑问词）
        if user_input.count("?") + user_input.count("？") >= 2:
            return True

        # 包含讨论相关词汇
        discussion_words = [
            "为什么",
            "怎么",
            "如何",
            "什么",
            "哪",
            "吗",
            "呢",
            "讨论",
            "分析",
            "解释",
        ]
        return bool(any(word in user_input for word in discussion_words) and len(user_input) > 20)

    async def get_lifebook_summary(self) -> str:
        """
        从记忆系统中获取 Lifebook 终端会话摘要

        Returns:
            摘要文本，如果没有则返回空字符串
        """
        try:
            if not self.memory_net:
                return ""

            # 搜索最近保存的终端会话记录
            if hasattr(self.memory_net, "memory_engine") and self.memory_net.memory_engine:
                results = self.memory_net.memory_engine.search_tides(query="终端会话", limit=3)
            else:
                return ""

            if results:
                summaries = []
                for result in results:
                    data = result.get("data", {})
                    if data.get("type") == "terminal_session":
                        content = data.get("content", "")
                        title = data.get("title", "")
                        summaries.append(f"## {title}\n{content[:500]}")

                if summaries:
                    return "\n\n".join(summaries)

            return ""
        except Exception as e:
            logger.debug(f"[对话上下文] 获取 Lifebook 摘要失败: {e}")
            return ""
