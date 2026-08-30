"""
弥娅历史记录员 (Historian) v3.0 - 星璇记忆系统

自动分析对话并提取需要记忆的内容：
- 用户信息、习惯、承诺等
- 弥娅自记忆：承诺、观点、建议、情感表达、自我认知
- 群聊中有价值的讨论主题提取
- 与 CognitiveEngine 配合实现智能记忆
- 支持记忆自动升级机制
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from memory import MemoryLevel, MemorySource, get_memory_core
from memory.cognitive_engine import get_cognitive_engine

logger = logging.getLogger(__name__)


def _load_historian_config() -> Dict[str, Any]:
    """从 memory_config.json 加载 Historian 配置"""
    try:
        from memory import load_memory_config

        config = load_memory_config()
        hist = config.get("historian", {})
        if hist:
            return hist
    except Exception:
        pass

    try:
        config_dir = Path(__file__).parent.parent / "config"
        text_config_path = config_dir / "text_config.json"
        if text_config_path.exists():
            with open(text_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("historian", {})
    except Exception as e:
        logger.debug(f"[Historian] 加载配置失败: {e}")
    return {}


def _parse_patterns(raw: List) -> List[Tuple[str, str]]:
    """将配置中的 [[pattern, label], ...] 转为 [(pattern, label), ...]"""
    return [(p[0], p[1]) for p in raw if isinstance(p, list) and len(p) >= 2]


def _parse_group_patterns(raw: Dict) -> Dict[str, List[Tuple[str, str]]]:
    """解析群聊讨论模式"""
    result = {}
    for category, patterns in raw.items():
        result[category] = _parse_patterns(patterns)
    return result


# 从配置加载（回退到内置默认值）
_config = _load_historian_config()

# 加载弥娅自记忆配置
_assistant_self_config = {}
try:
    _config_path = Path(__file__).parent.parent / "config" / "memory_config.json"
    if _config_path.exists():
        with open(_config_path, "r", encoding="utf-8") as _f:
            _full_config = json.load(_f)
            _assistant_self_config = _full_config.get("historian", {}).get("assistant_self", {})
    if not _assistant_self_config:
        # 回退到 text_config.json
        _fallback_path = Path(__file__).parent.parent / "config" / "text_config.json"
        if _fallback_path.exists():
            with open(_fallback_path, "r", encoding="utf-8") as _f:
                _fallback_config = json.load(_f)
                _assistant_self_config = _fallback_config.get("assistant_self", {})
except Exception:
    pass

IGNORE_PATTERNS = _config.get(
    "ignore_patterns",
    [
        r"^[嗯哦啊哈嘿诶]{1,3}[。\.!?]*$",
        r"^[好是知道行可以]{1,2}[。\.!?]*$",
        r"^[干嘛怎么了啥事?]*$",
        r"^[哈哈哈?]+[。!]*$",
        r"^\[表情\]$",
        r"^[\(]?图片[照片]?[\)]?$",
        r"^[/@].*",
        r"^!{3,}$",
        r"^[~～]{3,}$",
    ],
)

IMPORTANT_PATTERNS = _parse_group_patterns(
    _config.get(
        "important_patterns",
        {
            "personal_info": [
                [r"我(今年|今年多大|多大了|几岁)", "个人年龄"],
                [r"我(身高|多高)", "个人身高"],
                [r"我(生日|哪天|什么日子)", "个人生日"],
                [r"我是(.+?)(学生|工作|上班)", "身份"],
                [r"我住在(.+?)(家|宿舍|学校)", "住址"],
            ],
            "preference": [
                [r"我喜欢(.+)", "喜欢"],
                [r"我讨厌(.+)", "讨厌"],
                [r"我最爱(.+)", "最爱"],
                [r"我不喜欢(.+)", "不喜欢"],
            ],
            "health": [
                [r"我有(.+?)病", "健康"],
                [r"我(.+?)不舒服", "健康"],
                [r"(.+?)先天性", "健康"],
                [r"身体(.+?)不好", "健康"],
            ],
            "commitment": [
                [r"答应你(.+)", "承诺"],
                [r"会记住(.+)", "承诺"],
                [r"下次(.+)", "承诺"],
            ],
        },
    )
)

GROUP_DISCUSSION_PATTERNS = _parse_group_patterns(
    _config.get(
        "group_discussion_patterns",
        {
            "knowledge": [
                [r"(三体|阶梯计划|云天明|二向箔|曲率|黑洞|光速飞船)", "科幻讨论"],
                [r"(群星|战锤|蜂巢|超级个体|进化方向)", "科幻哲学"],
                [r"(饕餮|深水王子|针眼画师|童话)", "三体童话"],
                [r"(计划的一部分|面壁者|执剑人)", "三体概念"],
            ],
            "opinion": [
                [r"(我认为|我觉得|我的看法|我的看法是)", "观点表达"],
                [r"(你怎么看|你怎么想|你的看法)", "征求意见"],
            ],
            "event": [
                [r"(今天|明天|昨天|下周|下周)(去|要|准备|打算)", "计划安排"],
                [r"(终于|总算|结束了|完成了)", "事件完成"],
            ],
        },
    )
)


def _load_assistant_self_patterns() -> Dict[str, Any]:
    """从 text_config.json 加载弥娅自记忆模式"""
    patterns = {}
    base_importance = {}

    cfg_patterns = _assistant_self_config.get("patterns", {})
    cfg_importance = _assistant_self_config.get("base_importance", {})

    for category, pattern_list in cfg_patterns.items():
        patterns[category] = []
        for item in pattern_list:
            if isinstance(item, list) and len(item) >= 2:
                patterns[category].append((item[0], item[1]))
        base_importance[category] = cfg_importance.get(category, 0.5)

    return {"patterns": patterns, "base_importance": base_importance}


_ASSISTANT_SELF_CONFIG = _load_assistant_self_patterns()


class Historian:
    """历史记录员 v3.0 - 星璇记忆系统

    职责：
    - 分析对话内容
    - 提取用户重要信息
    - 提取弥娅自记忆（承诺、观点、建议、情感、自我认知）
    - 群聊中有价值讨论的提取
    - 记忆自动升级机制
    - 自动保存到记忆存储
    """

    def __init__(self):
        """初始化历史记录员"""
        self.memory_core = None
        self._memory_core_initialized = False
        self.cognitive_engine = get_cognitive_engine()
        self._recent_memory_hashes: Set[str] = set()
        self._max_recent_hashes = 100

    async def _ensure_memory_core_initialized(self):
        """确保内存核心已初始化"""
        if not self._memory_core_initialized:
            if self.memory_core is None:
                self.memory_core = await get_memory_core()
            await self.memory_core.initialize()
            self._memory_core_initialized = True

    def _content_hash(self, text: str) -> str:
        """生成内容哈希用于去重"""
        import hashlib

        normalized = re.sub(r"[^\w\u4e00-\u9fff]", "", text[:50])
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]

    def _is_duplicate(self, text: str) -> bool:
        """检查是否是重复内容"""
        h = self._content_hash(text)
        if h in self._recent_memory_hashes:
            return True
        self._recent_memory_hashes.add(h)
        if len(self._recent_memory_hashes) > self._max_recent_hashes:
            to_remove = list(self._recent_memory_hashes)[: self._max_recent_hashes // 2]
            for item in to_remove:
                self._recent_memory_hashes.discard(item)
        return False

    def _is_meaningful(self, text: str) -> bool:
        """判断内容是否有意义"""
        if not text or len(text.strip()) < 4:
            return False

        return all(not re.match(pattern, text.strip()) for pattern in IGNORE_PATTERNS)

    def _extract_important_info(self, text: str) -> List[Tuple[str, str, List[str]]]:
        """提取用户重要信息

        Returns:
            [(内容, 类型, 标签), ...]
        """
        results = []

        for category, patterns in IMPORTANT_PATTERNS.items():
            for pattern, info_type in patterns:
                match = re.search(pattern, text)
                if match:
                    content = match.group(0)
                    if len(content) > 3:
                        tags = [category]
                        for topic, keywords in self.cognitive_engine.topic_keywords.items():
                            if any(kw in text for kw in keywords):
                                tags.append(topic)

                        results.append((content, info_type, tags))

        return results

    def _extract_assistant_self_memory(self, ai_response: str) -> List[Tuple[str, str, float, List[str]]]:
        """从弥娅的回复中提取自记忆

        模式从 text_config.json 的 assistant_self.patterns 加载

        Returns:
            [(内容, 类型, 重要性, 标签), ...]
        """
        results = []
        patterns = _ASSISTANT_SELF_CONFIG["patterns"]
        base_importance = _ASSISTANT_SELF_CONFIG["base_importance"]

        for category, category_patterns in patterns.items():
            for pattern, info_type in category_patterns:
                match = re.search(pattern, ai_response)
                if match:
                    content = match.group(0).strip()
                    if len(content) < 5:
                        continue

                    importance = base_importance.get(category, 0.5)

                    tags = ["弥娅自记忆", category]
                    for topic, keywords in self.cognitive_engine.topic_keywords.items():
                        if any(kw in ai_response for kw in keywords):
                            tags.append(topic)

                    results.append((content, info_type, importance, tags))

        return results

    def _extract_group_discussion(self, text: str) -> Optional[Tuple[str, float, List[str]]]:
        """提取群聊中有价值的讨论内容

        Returns:
            (内容, 重要性, 标签) 或 None
        """
        for category, patterns in GROUP_DISCUSSION_PATTERNS.items():
            for pattern, info_type in patterns:
                if re.search(pattern, text):
                    importance = 0.7
                    tags = [category, info_type]
                    for topic, keywords in self.cognitive_engine.topic_keywords.items():
                        if any(kw in text for kw in keywords):
                            tags.append(topic)
                    return text[:150], importance, tags
        return None

    def _extract_fact_from_conversation(
        self, user_input: str, ai_response: str
    ) -> Optional[Tuple[str, float, List[str]]]:
        """从对话中提取需要记忆的事实

        Returns:
            (记忆内容, 重要性, 标签) 或 None
        """
        combined = user_input + " " + ai_response

        # 1. 提取用户重要信息
        important_infos = self._extract_important_info(user_input)
        if important_infos:
            content, info_type, tags = important_infos[0]
            importance = 0.8 if info_type in ["personal_info", "health"] else 0.6
            return content, importance, tags

        # 2. 检查群聊有价值讨论
        group_discussion = self._extract_group_discussion(user_input)
        if group_discussion:
            return group_discussion

        # 3. 检查触发词
        importance = 0.3
        tags = []

        for category, triggers in self.cognitive_engine.memory_triggers.items():
            for trigger in triggers:
                if trigger in combined:
                    if category == "important_info":
                        importance = 0.9
                    elif category == "commitment":
                        importance = 0.8
                    elif category == "emotion_change":
                        importance = 0.7
                    elif category == "habit":
                        importance = 0.6
                    break

        for topic, keywords in self.cognitive_engine.topic_keywords.items():
            if any(kw in user_input for kw in keywords):
                tags.append(topic)

        if importance > 0.3 and len(user_input) > 5:
            return user_input[:100], importance, tags

        return None

    async def _store_assistant_self_memory(
        self,
        content: str,
        info_type: str,
        importance: float,
        tags: List[str],
        user_id: str,
        group_id: str,
        message_type: str,
    ) -> bool:
        """【新增】存储弥娅自记忆到 LONG_TERM 层级

        弥娅的承诺、观点、建议等重要话语会自动升级为长期记忆
        """
        try:
            await self._ensure_memory_core_initialized()

            # 自记忆默认存储为 LONG_TERM
            level = MemoryLevel.LONG_TERM

            # 承诺类记忆额外提升重要性
            if "commitment" in tags:
                importance = min(1.0, importance + 0.1)
                level = MemoryLevel.LONG_TERM

            # 情感类记忆也提升重要性
            if "emotion" in tags:
                importance = min(1.0, importance + 0.05)

            # 构建记忆内容（带上上下文）
            memory_content = f"[弥娅说] {content}"

            memory_uuid = await self.memory_core.store(
                content=memory_content,
                level=level,
                priority=importance,
                tags=tags,
                source=MemorySource.ASSISTANT_SELF,
                role="assistant",
                user_id=user_id,
                group_id=group_id,
                emotional_tone="弥娅自记忆",
                significance=importance,
            )

            if memory_uuid:
                logger.info(
                    f"[星璇·自记忆] {info_type}: {content[:30]}... (importance={importance}, level={level.value})"
                )
                return True
        except Exception as e:
            logger.error(f"[星璇·自记忆] 保存失败: {e}")

        return False

    async def process_conversation(
        self,
        user_input: str,
        ai_response: str,
        user_id: str = "default",
        group_id: str = "",
        message_type: str = "",
    ) -> bool:
        """处理对话并自动记忆

        Args:
            user_input: 用户输入
            ai_response: AI回复
            user_id: 用户ID
            group_id: 群组ID
            message_type: 消息类型 (group/private)

        Returns:
            是否成功记忆
        """
        if not self._is_meaningful(user_input):
            return False

        if self._is_duplicate(user_input):
            return False

        memory_data = self._extract_fact_from_conversation(user_input, ai_response)

        if not memory_data:
            logger.debug("[Historian] 对话无重要内容，跳过记忆")
            return False

        content, importance, tags = memory_data

        if message_type == "group" and len(user_input) > 20:
            importance = min(1.0, importance + 0.1)

        try:
            await self._ensure_memory_core_initialized()

            memory_uuid = await self.memory_core.store(
                content=content,
                priority=importance,
                tags=tags,
                source=MemorySource.AUTO_EXTRACT,
                user_id=user_id,
                group_id=group_id,
            )

            if memory_uuid:
                logger.info(f"[Historian] 已记忆: {content[:30]}... (importance={importance}, group={group_id})")
                return True
        except Exception as e:
            logger.error(f"[Historian] 保存记忆失败: {e}")

        return False

    async def process_after_response(
        self,
        user_input: str,
        ai_response: str,
        user_id: str = "default",
        group_id: str = "",
        message_type: str = "",
    ) -> None:
        """在生成回复后调用，自动处理记忆

        包含：
        1. 用户重要信息提取（原有逻辑）
        2. 【新增】弥娅自记忆提取（承诺、观点、建议、情感、自我认知）
        """
        # === 原有逻辑：用户信息提取 ===
        (
            should_remember,
            content,
            importance,
        ) = await self.cognitive_engine.should_remember(user_input, ai_response)

        if should_remember and content:
            if self._is_duplicate(content):
                return

            topics = self.cognitive_engine.extract_topics(user_input)

            if message_type == "group":
                group_discussion = self._extract_group_discussion(user_input)
                if group_discussion:
                    _, _, discussion_tags = group_discussion
                    topics.extend(discussion_tags)
                    importance = min(1.0, importance + 0.1)

            try:
                await self._ensure_memory_core_initialized()

                await self.memory_core.store(
                    content=content,
                    priority=importance,
                    tags=topics,
                    source=MemorySource.AUTO_EXTRACT,
                    user_id=user_id,
                    group_id=group_id,
                )
                logger.info(f"[Historian] 自动记住: {content[:30]}...")
            except Exception as e:
                logger.error(f"[Historian] 自动记忆失败: {e}")

        # === 【新增】弥娅自记忆提取 ===
        if ai_response and len(ai_response.strip()) >= 5:
            assistant_memories = self._extract_assistant_self_memory(ai_response)

            for content, info_type, importance, tags in assistant_memories:
                if self._is_duplicate(content):
                    continue

                if message_type == "group":
                    importance = max(0.3, importance - 0.1)

                await self._store_assistant_self_memory(
                    content=content,
                    info_type=info_type,
                    importance=importance,
                    tags=tags,
                    user_id=user_id,
                    group_id=group_id,
                    message_type=message_type,
                )

        # === 【新增】LLM 驱动的深度记忆提取 (L0→L1) ===
        try:
            await self._llm_extract(user_input, ai_response, user_id, group_id)
        except Exception as e:
            logger.debug(f"[Historian] LLM 提取失败 (不影响主流程): {e}")

        # 【新增】短期记忆自动归档机制
        try:
            await self._auto_archive_short_term(user_id)
        except Exception as e:
            logger.debug(f"[Historian] 自动归档失败: {e}")

    async def _llm_extract(
        self,
        user_input: str,
        ai_response: str,
        user_id: str,
        group_id: str,
    ) -> None:
        """LLM 驱动的深度记忆提取，作为正则提取的语义增强层"""
        try:
            from memory.llm_extractor import get_llm_extractor

            extractor = get_llm_extractor()
            if not extractor.should_run():
                return

            if extractor.llm_client is None:
                try:
                    from core.embedding_client import get_embedding_client

                    emb_client = await get_embedding_client()
                    if emb_client and hasattr(emb_client, "client"):
                        extractor.llm_client = emb_client.client
                except Exception:
                    pass

            if extractor.llm_client is None:
                return

            facts = await extractor.extract(
                user_input=user_input,
                ai_response=ai_response,
                user_id=user_id,
                group_id=group_id,
            )

            for fact in facts:
                if self._is_duplicate(fact["content"]):
                    continue

                await self._ensure_memory_core_initialized()

                await self.memory_core.store(
                    content=f"[LLM提取] {fact['content']}",
                    level=MemoryLevel.LONG_TERM,
                    priority=fact.get("importance", 0.7),
                    tags=["llm_extracted", fact.get("category", "")] + fact.get("tags", []),
                    source=MemorySource.AUTO_EXTRACT,
                    user_id=fact.get("user_id", user_id),
                    group_id=fact.get("group_id", group_id),
                    significance=fact.get("importance", 0.7),
                )

            if facts:
                logger.info(f"[Historian] LLM 深度提取了 {len(facts)} 条原子事实")

        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[Historian] LLM 提取异常: {e}")

    async def _auto_archive_short_term(self, user_id: str) -> None:
        """短期记忆自动归档机制

        检查短期记忆，将重要记忆自动升级为长期记忆
        避免短期记忆过期丢失。

        仅处理创建时间超过 30 分钟的短期记忆，
        避免刚创建的短期记忆被立即升级。
        """
        try:
            await self._ensure_memory_core_initialized()

            # 查询短期记忆
            from datetime import timedelta

            from memory import MemoryLevel

            short_term_memories = await self.memory_core.retrieve(
                query="",
                level=MemoryLevel.SHORT_TERM,
                limit=100,
            )

            cutoff = datetime.now() - timedelta(minutes=30)
            upgraded_count = 0

            for mem in short_term_memories:
                # 跳过刚创建不到 30 分钟的短期记忆
                try:
                    created = datetime.fromisoformat(mem.created_at)
                    if created > cutoff:
                        continue
                except Exception:
                    pass

                # 升级条件：高优先级(>=0.7) 或 手动标记的记忆
                priority = getattr(mem, "priority", 0)
                source = getattr(mem, "source", None)
                source_val = source.value if hasattr(source, "value") else str(source) if source else ""

                if priority >= 0.7 or source_val == "manual":
                    # 升级为长期记忆
                    mem.level = MemoryLevel.LONG_TERM
                    # 使用正确的 update 方法调用
                    await self.memory_core.update(
                        str(mem.id),
                        content=mem.content,
                        tags=mem.tags,
                        priority=mem.priority,
                        is_pinned=mem.is_pinned,
                        is_archived=mem.is_archived,
                    )
                    # 更新缓存中的记忆
                    mem.updated_at = datetime.now().isoformat()
                    upgraded_count += 1

            if upgraded_count > 0:
                logger.info(f"[Historian] 自动归档: 升级了 {upgraded_count} 条短期记忆为长期记忆")

        except Exception as e:
            logger.debug(f"[Historian] 自动归档执行失败: {e}")


# 单例实例
_historian: Optional[Historian] = None


def get_historian() -> Historian:
    """获取历史记录员单例实例"""
    global _historian
    if _historian is None:
        _historian = Historian()
    return _historian
