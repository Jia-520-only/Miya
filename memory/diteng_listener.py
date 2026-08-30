"""
谛听 - 群聊消息监听与分层摘要系统

职责：
- 监听所有群消息（不触发大模型）
- 分层摘要：时间线概览 + 关键对话 + 当前话题
- 追踪活跃对话窗口
- 区分公开话题 vs 私密对话
- 消息策略分析（是否回复、回复策略、意图分类）
"""

import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MessageStrategy:
    """消息策略分析结果"""

    should_respond: bool = True  # 是否应该回复
    response_strategy: str = "full_reply"  # 响应策略: full_reply/brief_reply/emoji_only/ignore/like_only
    message_intent: str = "chat"  # 意图分类: greeting/chat/question/confession/complaint/share/casual
    confidence: float = 0.5  # 判断置信度
    reason: str = ""  # 判断理由
    suggested_reply_style: str = "normal"  # 建议回复风格: normal/casual/serious/playful
    max_messages: int = 1  # 本轮回复最多发几条消息


@dataclass
class MessageSnippet:
    """消息片段"""

    sender_id: str
    sender_name: str
    content: str
    timestamp: float
    is_at_bot: bool = False
    is_reply_to_bot: bool = False
    topic: str = ""  # 自动提取的话题标签


@dataclass
class TopicThread:
    """话题线程：追踪一个话题的完整对话"""

    topic: str
    participants: List[str] = field(default_factory=list)
    messages: List[MessageSnippet] = field(default_factory=list)
    start_time: float = 0.0
    last_active: float = 0.0
    is_active: bool = True

    def add_message(self, snippet: MessageSnippet):
        self.messages.append(snippet)
        self.last_active = snippet.timestamp
        if snippet.sender_name not in self.participants:
            self.participants.append(snippet.sender_name)

    def get_summary(self, max_messages: int = 5) -> str:
        """获取话题摘要"""
        recent = self.messages[-max_messages:]
        lines = []
        for s in recent:
            prefix = "@" if s.is_at_bot or s.is_reply_to_bot else ""
            lines.append(f"{prefix}{s.sender_name}: {s.content}")
        return "\n".join(lines)

    def get_timeline_entry(self) -> str:
        """获取时间线索目"""
        participants = "、".join(self.participants[:3])
        msg_count = len(self.messages)
        first_msg = self.messages[0].content[:30] if self.messages else ""
        return f"[{participants}] 聊了{msg_count}条: {first_msg}..."


class DiTingListener:
    """
    谛听监听器 - 分层摘要版

    功能：
    1. 监听所有群消息
    2. 分层摘要注入（时间线 + 关键对话 + 当前话题）
    3. 追踪活跃对话窗口
    4. 话题线程追踪
    """

    def __init__(
        self,
        max_snippets_per_group: int = 50,
        active_window_seconds: int = 300,
        active_message_threshold: int = 5,
        max_topic_threads: int = 5,
    ):
        self.max_snippets = max_snippets_per_group
        self.active_window = active_window_seconds
        self.active_threshold = active_message_threshold
        self.max_topic_threads = max_topic_threads

        # 群聊消息存储
        self._group_snippets: Dict[str, List[MessageSnippet]] = defaultdict(list)

        # 话题线程：{group_id: [TopicThread, ...]}
        self._topic_threads: Dict[str, List[TopicThread]] = defaultdict(list)

        # 活跃对话追踪：{group_id: {user_id: last_active_time}}
        self._active_conversations: Dict[str, Dict[str, float]] = defaultdict(dict)

        # 用户连续发言计数
        self._user_streaks: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        self._persist_file = Path("data/diting_state.json")
        self._persist_file.parent.mkdir(parents=True, exist_ok=True)
        self._loaded_from_disk = False

        self._load()
        self._loaded_from_disk = True

        logger.info("[谛听] 分层摘要监听器初始化完成")

    def _load(self):
        """从磁盘恢复谛听状态（分层时间衰减）"""
        if not self._persist_file.exists():
            return
        try:
            from memory.session_decay import SessionPhase, get_decay_config, get_phase

            config = get_decay_config()
            hot_seconds = config.get("hot_window_minutes", 30) * 60
            warm_seconds = config.get("warm_window_hours", 6) * 3600

            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()

            # 恢复群聊消息：HOT 保留，WARM 保留最后5条供摘要，COLD/DORMANT 丢弃
            for gid, snippets_raw in data.get("_group_snippets", {}).items():
                last_ts = max((s.get("timestamp", 0) for s in snippets_raw), default=0)
                elapsed = now - last_ts
                phase = get_phase(elapsed)

                if phase == SessionPhase.HOT:
                    snippets = [MessageSnippet(**s) for s in snippets_raw if now - s.get("timestamp", 0) < hot_seconds]
                    if snippets:
                        self._group_snippets[gid] = snippets
                elif phase == SessionPhase.WARM:
                    snippets = [
                        MessageSnippet(**s) for s in snippets_raw[-5:] if now - s.get("timestamp", 0) < warm_seconds
                    ]
                    if snippets:
                        self._group_snippets[gid] = snippets

            # 恢复活跃对话：HOT/WARM 保留
            for gid, users in data.get("_active_conversations", {}).items():
                valid_users = {}
                for uid, t in users.items():
                    elapsed = now - t
                    phase = get_phase(elapsed)
                    if phase in (SessionPhase.HOT, SessionPhase.WARM):
                        valid_users[uid] = t
                if valid_users:
                    self._active_conversations[gid] = valid_users

            # 恢复用户连续发言计数
            for gid, streaks in data.get("_user_streaks", {}).items():
                if gid in self._active_conversations:
                    self._user_streaks[gid] = defaultdict(int, streaks)

            # 恢复话题线程：HOT/WARM 保留
            for gid, threads_raw in data.get("_topic_threads", {}).items():
                threads = []
                for t in threads_raw:
                    last_active = t.get("last_active", 0)
                    elapsed = now - last_active
                    phase = get_phase(elapsed)
                    if phase in (SessionPhase.HOT, SessionPhase.WARM):
                        msgs = [MessageSnippet(**m) for m in t.get("messages", [])]
                        if msgs:
                            thread = TopicThread(
                                topic=t.get("topic", ""),
                                participants=t.get("participants", []),
                                messages=msgs,
                                start_time=t.get("start_time", 0),
                                last_active=last_active,
                                is_active=phase == SessionPhase.HOT,
                            )
                            threads.append(thread)
                if threads:
                    self._topic_threads[gid] = threads

            loaded_groups = len(self._group_snippets)
            loaded_active = sum(len(u) for u in self._active_conversations.values())
            if loaded_groups > 0 or loaded_active > 0:
                logger.info(f"[谛听] 从磁盘恢复状态: {loaded_groups} 群, {loaded_active} 活跃用户")
        except Exception as e:
            logger.warning(f"[谛听] 恢复状态失败: {e}")

    def save(self):
        """持久化谛听状态到磁盘"""
        try:
            data = {
                "max_age_hours": max(self.active_window // 3600, 1),
                "_group_snippets": {
                    gid: [asdict(s) for s in snippets[-30:]]
                    for gid, snippets in self._group_snippets.items()
                    if snippets
                },
                "_active_conversations": {
                    gid: dict(users) for gid, users in self._active_conversations.items() if users
                },
                "_user_streaks": {gid: dict(streaks) for gid, streaks in self._user_streaks.items() if streaks},
                "_topic_threads": {
                    gid: [
                        {
                            "topic": t.topic,
                            "participants": t.participants,
                            "messages": [asdict(m) for m in t.messages[-5:]],
                            "start_time": t.start_time,
                            "last_active": t.last_active,
                            "is_active": t.is_active,
                        }
                        for t in threads[-3:]
                    ]
                    for gid, threads in self._topic_threads.items()
                    if threads
                },
            }
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[谛听] 保存状态失败: {e}")

    def on_group_message(
        self,
        group_id: str,
        group_name: str,
        user_id: str,
        user_name: str,
        content: str,
        is_at_bot: bool = False,
        reply_to_bot: bool = False,
    ):
        """处理群消息"""
        snippet = MessageSnippet(
            sender_id=user_id,
            sender_name=user_name,
            content=content[:150],
            timestamp=time.time(),
            is_at_bot=is_at_bot,
            is_reply_to_bot=reply_to_bot,
        )

        # 存储消息
        snippets = self._group_snippets[group_id]
        snippets.append(snippet)
        if len(snippets) > self.max_snippets:
            self._group_snippets[group_id] = snippets[-self.max_snippets :]

        # 更新话题线程
        self._update_topic_thread(group_id, snippet)

        # 更新活跃对话状态
        if is_at_bot or reply_to_bot:
            self._active_conversations[group_id][user_id] = time.time()
            self._user_streaks[group_id][user_id] = 0
        else:
            last_active = self._active_conversations[group_id].get(user_id, 0)
            if time.time() - last_active < self.active_window:
                self._user_streaks[group_id][user_id] += 1
                if self._user_streaks[group_id][user_id] >= self.active_threshold:
                    self._active_conversations[group_id][user_id] = time.time()
            else:
                self._user_streaks[group_id][user_id] = 0

        # 每 5 条消息自动持久化
        self._save_counter = getattr(self, "_save_counter", 0) + 1
        if self._save_counter % 5 == 0:
            self.save()

    def _update_topic_thread(self, group_id: str, snippet: MessageSnippet):
        """更新话题线程"""
        threads = self._topic_threads[group_id]

        # 检查是否可以加入现有活跃线程
        for thread in threads:
            if not thread.is_active:
                continue
            # 5分钟内、有相同参与者、内容相关 → 加入同一线程
            if time.time() - thread.last_active < 300 and snippet.sender_name in thread.participants:
                thread.add_message(snippet)
                return

        # 创建新话题线程
        new_thread = TopicThread(
            topic=f"话题_{len(threads) + 1}",
            start_time=snippet.timestamp,
            last_active=snippet.timestamp,
        )
        new_thread.add_message(snippet)
        threads.append(new_thread)

        # 限制线程数量
        if len(threads) > self.max_topic_threads:
            self._topic_threads[group_id] = threads[-self.max_topic_threads :]

    def get_layered_context(self, group_id: str) -> str:
        """
        获取分层上下文（核心方法）

        返回三层信息：
        1. 时间线概览：谁在什么时间聊了什么
        2. 关键对话：与机器人相关的对话
        3. 当前话题：正在进行的讨论
        """
        snippets = self._group_snippets.get(group_id, [])
        threads = self._topic_threads.get(group_id, [])

        if not snippets:
            return ""

        layers = []

        # Layer 1: 时间线概览
        timeline_entries = []
        for thread in threads:
            entry = thread.get_timeline_entry()
            if entry:
                timeline_entries.append(entry)

        if timeline_entries:
            layers.append("【群聊时间线】")
            layers.extend(timeline_entries)

        # Layer 2: 关键对话（与机器人相关的）
        bot_interactions = [s for s in snippets if s.is_at_bot or s.is_reply_to_bot]
        if bot_interactions:
            layers.append("\n【与弥娅的对话】")
            for s in bot_interactions[-5:]:
                prefix = "@" if s.is_at_bot else "→"
                layers.append(f"{prefix}{s.sender_name}: {s.content}")

        # Layer 3: 当前话题（最近3条，去重）
        recent = snippets[-3:]
        if recent:
            layers.append("\n【当前对话】")
            seen_content = set()
            for s in recent:
                if s.content not in seen_content:
                    layers.append(f"{s.sender_name}: {s.content}")
                    seen_content.add(s.content)

        return "\n".join(layers)

    def get_group_context(self, group_id: str, max_snippets: int = 10) -> str:
        """兼容旧接口，返回分层上下文"""
        return self.get_layered_context(group_id)

    def is_user_active_with_bot(self, group_id: str, user_id: str) -> bool:
        """检查用户是否仍在与机器人活跃对话"""
        last_active = self._active_conversations.get(group_id, {}).get(user_id, 0)
        time_ok = (time.time() - last_active) < self.active_window

        if not time_ok:
            return False

        snippets = self._group_snippets.get(group_id, [])
        user_recent_messages = [s for s in snippets[-20:] if s.sender_id == user_id]
        min_messages = 3
        return len(user_recent_messages) >= min_messages

    def get_active_users(self, group_id: str) -> List[str]:
        """获取当前活跃用户列表"""
        cutoff = time.time() - self.active_window
        return [uid for uid, last_time in self._active_conversations.get(group_id, {}).items() if last_time > cutoff]

    def get_related_threads(self, group_id: str, query: str, max_threads: int = 3) -> str:
        """获取与查询相关的话题线程"""
        threads = self._topic_threads.get(group_id, [])
        query_lower = query.lower()

        relevant = []
        for thread in threads:
            # 检查线程中是否有与查询相关的内容
            for msg in thread.messages:
                if any(kw in msg.content.lower() for kw in query_lower.split()):
                    relevant.append(thread)
                    break

        if not relevant:
            return ""

        lines = ["【相关话题】"]
        for thread in relevant[:max_threads]:
            lines.append(f"\n{thread.get_summary()}")

        return "\n".join(lines)

    def compress_and_archive(self, group_id: str) -> Optional[Dict]:
        """
        压缩并归档群聊消息（方案 A：定期压缩归档）

        将内存中的原始消息压缩成摘要，返回摘要数据供外部存储到记忆系统。

        Returns:
            摘要字典，如果没有新消息则返回 None
        """
        snippets = self._group_snippets.get(group_id, [])
        if not snippets:
            return None

        # 提取关键信息
        senders = set(s.sender_name for s in snippets)
        msg_count = len(snippets)
        first_time = snippets[0].timestamp
        last_time = snippets[-1].timestamp
        duration = last_time - first_time

        # 提取关键词
        " ".join(s.content for s in snippets)
        keywords = set()
        for s in snippets:
            for word in s.content:
                if len(word) >= 2 and word not in "的了是在我你他她它有和或但而就也都这不":
                    keywords.add(word)

        # 生成摘要
        first_msg = snippets[0]
        last_msg = snippets[-1]
        summary = (
            f"[{first_time:.0f}-{last_time:.0f}] "
            f"群聊 {msg_count} 条消息，参与者：{', '.join(senders)}。"
            f"开始：{first_msg.sender_name}: {first_msg.content[:30]}... "
            f"最后：{last_msg.sender_name}: {last_msg.content[:30]}..."
        )

        result = {
            "group_id": group_id,
            "summary": summary,
            "message_count": msg_count,
            "senders": list(senders),
            "start_time": first_time,
            "end_time": last_time,
            "duration_seconds": duration,
            "keywords": list(keywords)[:20],
            "raw_snippets": [
                {"sender": s.sender_name, "content": s.content, "time": s.timestamp}
                for s in snippets[-10:]  # 保留最后 10 条原始消息供查询
            ],
        }

        logger.info(f"[谛听归档] group={group_id}, 压缩 {msg_count} 条消息 → 摘要")

        return result

    def cleanup_expired(self, max_age_seconds: int = 3600):
        """清理过期数据"""
        cutoff = time.time() - max_age_seconds

        # 清理过期群消息
        expired_groups = [
            gid for gid, snippets in self._group_snippets.items() if snippets and snippets[-1].timestamp < cutoff
        ]
        for gid in expired_groups:
            del self._group_snippets[gid]
            self._topic_threads.pop(gid, None)

        # 清理过期活跃对话
        for group_id in list(self._active_conversations.keys()):
            expired_users = [
                uid for uid, last_time in self._active_conversations[group_id].items() if last_time < cutoff
            ]
            for uid in expired_users:
                del self._active_conversations[group_id][uid]
                self._user_streaks[group_id].pop(uid, None)

        if expired_groups:
            logger.debug(f"[谛听] 清理了 {len(expired_groups)} 个过期群数据")

        self.save()

    async def analyze_message_strategy(
        self,
        content: str,
        user_id: str,
        group_id: Optional[str] = None,
        is_at_bot: bool = False,
        message_type: str = "group",
        recent_context: str = "",
    ) -> MessageStrategy:
        """
        分析消息策略 - AI判断是否回复及如何回复

        Args:
            content: 消息内容
            user_id: 发送者ID
            group_id: 群ID（私聊为None）
            is_at_bot: 是否@机器人
            message_type: 消息类型 group/private
            recent_context: 最近对话上下文

        Returns:
            MessageStrategy: 策略分析结果
        """
        # 加载配置
        config = self._load_strategy_config()

        if not config.get("enabled", True):
            # 如果未启用，返回默认策略
            return MessageStrategy(should_respond=True, response_strategy="full_reply")

        # 构建分析prompt
        prompt = self._build_strategy_prompt(
            content, user_id, group_id, is_at_bot, message_type, recent_context, config
        )

        try:
            # 调用AI分析 - 使用 ModelPool 获取客户端
            from core.model_pool_manager import get_qq_model

            model_config = get_qq_model("simple_chat", "balanced")
            if not model_config:
                logger.warning("[谛听-策略] 无法获取模型配置，使用默认策略")
                return MessageStrategy()

            # 从环境变量获取 API key
            import os

            from core.ai_client import AIClientFactory

            api_key = ""
            if hasattr(model_config, "env_key") and model_config.env_key:
                api_key = os.getenv(model_config.env_key, "")

            # 尝试从 model_config 的 api_key 属性获取（嵌入在 JSON 中的密钥）
            if not api_key and hasattr(model_config, "api_key"):
                api_key = model_config.api_key or ""

            # 如果没有 api_key，尝试从统一映射获取
            if not api_key:
                from core.model_pool_manager import resolve_api_key_by_provider

                api_key = resolve_api_key_by_provider(
                    model_config.provider.lower(), getattr(model_config, "env_key", "")
                )

            client = AIClientFactory.create_client(
                provider=model_config.provider,
                api_key=api_key,
                model=model_config.name,
                base_url=model_config.base_url,
                tool_context=None,
            )

            from core.ai_client import AIMessage

            messages = [AIMessage(role="user", content=prompt)]

            # 添加超时控制
            timeout = config.get("timeout", 10)
            response = await asyncio.wait_for(
                client.chat(messages=messages, tools=None, use_miya_prompt=False),
                timeout=timeout,
            )
            if not response:
                logger.warning("[谛听-策略] AI响应为空，使用默认策略")
                return MessageStrategy()

            # 解析AI返回的JSON
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if not json_match:
                logger.warning("[谛听-策略] AI返回非JSON，使用默认策略")
                return MessageStrategy()

            result = json.loads(json_match.group())

            # 从配置获取默认值
            max_responses = config.get("max_responses_per_turn", 3)
            default_max_messages = config.get("default_max_messages", 1)

            # 获取AI返回的max_messages并校验
            max_messages = result.get("max_messages", default_max_messages)
            if not isinstance(max_messages, int) or max_messages < 1:
                max_messages = default_max_messages
            if max_messages > max_responses:
                max_messages = max_responses

            # 转换为MessageStrategy
            return MessageStrategy(
                should_respond=result.get("should_respond", True),
                response_strategy=result.get("response_strategy", "full_reply"),
                message_intent=result.get("message_intent", "chat"),
                confidence=result.get("confidence", 0.5),
                reason=result.get("reason", ""),
                suggested_reply_style=result.get("suggested_reply_style", "normal"),
                max_messages=max_messages,
            )

        except asyncio.TimeoutError:
            logger.warning("[谛听-策略] 分析超时，使用默认策略")
            return MessageStrategy()
        except Exception as e:
            logger.warning(f"[谛听-策略] 分析失败: {e}，使用默认策略")
            return MessageStrategy()

    def _load_strategy_config(self) -> Dict:
        """加载策略配置 - 合并diteng_strategy_config和text_config的默认值"""
        try:
            # 加载策略配置
            config_path = Path(__file__).parent.parent / "config" / "diteng_strategy_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = {}

            # 加载默认值配置
            defaults_path = Path(__file__).parent.parent / "config" / "text_config.json"
            if defaults_path.exists():
                with open(defaults_path, "r", encoding="utf-8") as f:
                    text_config = json.load(f)
                    strategy_defaults = text_config.get("strategy_defaults", {})

                    # 合并默认值
                    if "max_responses_per_turn" not in config:
                        config["max_responses_per_turn"] = strategy_defaults.get("max_responses_per_turn", 3)
                    if "default_max_messages" not in config:
                        config["default_max_messages"] = strategy_defaults.get("default_max_messages", 1)

            return config
        except Exception:
            return {"max_responses_per_turn": 3, "default_max_messages": 1}

    def _build_strategy_prompt(
        self,
        content: str,
        user_id: str,
        group_id: Optional[str],
        is_at_bot: bool,
        message_type: str,
        recent_context: str,
        config: Dict,
    ) -> str:
        """构建策略分析prompt - 所有策略选项从配置文件读取"""

        # 从配置读取策略选项
        strategy_options = config.get("response_strategies", {})
        intent_options = config.get("intent_types", {})
        style_options = config.get("reply_styles", {})
        judge_rules = config.get("judge_rules", [])
        max_responses = config.get("max_responses_per_turn", 3)

        rules_text = "\n".join(f"{i + 1}. {rule}" for i, rule in enumerate(judge_rules))

        message_type_label = "群聊" if message_type == "group" else "私聊"
        at_bot_label = "是" if is_at_bot else "否"
        group_id_label = group_id or "私聊"
        recent_ctx = recent_context if recent_context else "无"

        strategy_json = json.dumps(strategy_options, ensure_ascii=False, indent=2)
        intent_json = json.dumps(intent_options, ensure_ascii=False, indent=2)
        style_json = json.dumps(style_options, ensure_ascii=False, indent=2)

        header = self._load_strategy_header()

        prompt = (
            f"{header}\n\n"
            f"【消息信息】\n"
            f"- 内容: {content}\n"
            f"- 发送者ID: {user_id}\n"
            f"- 类型: {message_type_label}\n"
            f"- 是否@机器人: {at_bot_label}\n"
            f"- 群ID: {group_id_label}\n"
            f"\n【最近上下文】\n"
            f"{recent_ctx}\n"
            f"\n【回复策略选项】\n"
            f"{strategy_json}\n"
            f"\n【意图类型选项】\n"
            f"{intent_json}\n"
            f"\n【回复风格选项】\n"
            f"{style_json}\n"
            f"\n【重要约束】本轮回复最多发 {max_responses} 条消息，超过会刷屏。\n"
            f"\n请直接返回JSON（不要其他内容）：\n"
            f"{{\n"
            f'  "should_respond": true/false,\n'
            f'  "response_strategy": "策略名",\n'
            f'  "message_intent": "意图类型",\n'
            f'  "confidence": 0.0-1.0,\n'
            f'  "reason": "判断理由",\n'
            f'  "suggested_reply_style": "风格",\n'
            f'  "max_messages": 1到{max_responses}之间的数字\n'
            f"}}\n"
            f"\n判断规则：\n"
            f"{rules_text}\n"
        )
        return prompt

    @staticmethod
    def _load_strategy_header() -> str:
        try:
            import json as _json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "text_config.json"
            with open(config_path, "r", encoding="utf-8") as _f:
                _cfg = _json.load(_f)
            return (
                _cfg.get("prompt_templates", {})
                .get("diteng_listener", {})
                .get("strategy_analysis_header", "你是弥娅的消息策略分析助手。根据以下信息判断如何响应这条消息。")
            )
        except Exception:
            return "你是弥娅的消息策略分析助手。根据以下信息判断如何响应这条消息。"


# 全局单例
_diting: Optional[DiTingListener] = None


def get_diting() -> DiTingListener:
    """获取谛听监听器单例"""
    global _diting
    if _diting is None:
        _diting = DiTingListener()
    return _diting
