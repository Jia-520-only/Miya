"""
弥娅 LLM 记忆提取器 (LLM Extractor)

增强 Historian，从正则匹配升级为 LLM 语义理解。
参考 TencentDB Agent Memory 的 L0→L1 原子事实提取管线。

功能：
1. 从对话中提取原子事实 (L0 → L1)
2. 实体与关系抽取
3. 记忆重要性智能评分
4. 与现有 Historian 正则提取互补（正则快速预筛 + LLM 深度提取）
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from memory.models import MemoryLevel, MemorySource

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一个记忆提取器。从以下对话中提取需要记住的关键信息。

返回 JSON 数组，每条记忆包含：
- content: 简洁的事实陈述（一句话）
- category: 分类 (personal_info/preference/health/commitment/event/knowledge/emotion)
- importance: 重要性 0-1 (0=可忽略, 1=必须记住)
- tags: 标签列表

规则：
1. 提取用户陈述的事实、偏好、承诺、健康信息
2. 提取弥娅(助手)的承诺、观点、建议
3. 忽略日常寒暄和无关内容
4. importance >= 0.7 才算重要记忆
5. 无重要信息时返回空数组 []
6. 最多提取 5 条记忆

对话：
{conversation}

只返回 JSON 数组，不要其他内容。"""


class LLMExtractor:
    """
    LLM 驱动的记忆提取器

    与现有 Historian 正则提取互补：
    - 正则快速预筛 → LLM 深度语义提取
    - 正则保证低延迟覆盖常见模式
    - LLM 提升准确度和召回率
    """

    def __init__(self, llm_client=None, enabled: bool = True):
        self.llm_client = llm_client
        self.enabled = enabled
        self._config = self._load_config()
        self._extraction_count = 0
        self._last_extraction_time: Optional[datetime] = None

    def _load_config(self) -> Dict[str, Any]:
        try:
            config_path = Path(__file__).parent.parent / "config" / "memory_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return cfg.get("llm_extractor", {})
        except Exception:
            pass
        return {}

    @property
    def min_content_length(self) -> int:
        return self._config.get("min_content_length", 10)

    @property
    def max_extractions_per_call(self) -> int:
        return self._config.get("max_extractions_per_call", 5)

    @property
    def throttle_seconds(self) -> int:
        return self._config.get("throttle_seconds", 2)

    @property
    def importance_threshold(self) -> float:
        return self._config.get("importance_threshold", 0.7)

    async def extract(
        self,
        user_input: str,
        ai_response: str,
        user_id: str = "default",
        group_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        从对话中提取原子事实。

        Args:
            user_input: 用户输入
            ai_response: AI回复
            user_id: 用户ID
            group_id: 群组ID

        Returns:
            提取的记忆列表 [{content, category, importance, tags, level, source}, ...]
        """
        if not self.enabled or not self.llm_client:
            return []

        combined = f"用户: {user_input}\n助手: {ai_response}"
        if len(combined.strip()) < self.min_content_length:
            return []

        try:
            prompt = EXTRACTION_PROMPT.format(conversation=combined)
            response = await self._call_llm(prompt)
            if not response:
                return []

            extracted = self._parse_response(response)
            if not extracted:
                return []

            result = []
            for item in extracted:
                if item.get("importance", 0) < self.importance_threshold:
                    continue

                result.append(
                    {
                        "content": item.get("content", ""),
                        "category": item.get("category", "knowledge"),
                        "importance": min(1.0, max(0.0, item.get("importance", 0.5))),
                        "tags": item.get("tags", []),
                        "level": MemoryLevel.LONG_TERM,
                        "source": MemorySource.AUTO_EXTRACT,
                        "user_id": user_id,
                        "group_id": group_id,
                    }
                )

            self._extraction_count += 1
            self._last_extraction_time = datetime.now()

            if result:
                logger.info(f"[LLM Extractor] 从对话中提取了 {len(result)} 条原子事实")

            return result[: self.max_extractions_per_call]

        except Exception as e:
            logger.debug(f"[LLM Extractor] 提取失败: {e}")
            return []

    def _parse_response(self, response: str) -> List[Dict]:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "memories" in data:
                return data["memories"]
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass

        return []

    async def _call_llm(self, prompt: str) -> Optional[str]:
        if not self.llm_client:
            return None

        try:
            if hasattr(self.llm_client, "chat"):
                messages = [{"role": "user", "content": prompt}]
                result = await self.llm_client.chat(messages, temperature=0.1, max_tokens=512)
                if isinstance(result, dict):
                    return result.get("content", "")
                if isinstance(result, str):
                    return result
            elif hasattr(self.llm_client, "complete"):
                return await self.llm_client.complete(prompt)
            elif callable(self.llm_client):
                return await self.llm_client(prompt)
        except Exception as e:
            logger.debug(f"[LLM Extractor] LLM 调用失败: {e}")

        return None

    async def extract_entities(self, text: str) -> Tuple[List[str], List[Tuple[str, str, str]]]:
        """
        提取实体和关系三元组。

        Args:
            text: 输入文本

        Returns:
            (实体列表, [(主体, 关系, 客体), ...])
        """
        if not self.enabled or not self.llm_client:
            return [], []

        prompt = f"""从以下文本中提取关键实体和关系。

返回 JSON:
{{
  "entities": ["实体1", "实体2", ...],
  "relations": [["主体", "关系", "客体"], ...]
}}

文本:
{text}

只返回 JSON。"""

        try:
            response = await self._call_llm(prompt)
            if not response:
                return [], []

            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            data = json.loads(response)
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            return entities, relations
        except Exception as e:
            logger.debug(f"[LLM Extractor] 实体提取失败: {e}")
            return [], []

    def should_run(self) -> bool:
        """检查是否应该运行提取（节流控制）"""
        if not self.enabled:
            return False
        if self._last_extraction_time is None:
            return True
        elapsed = (datetime.now() - self._last_extraction_time).total_seconds()
        return elapsed >= self.throttle_seconds


_global_llm_extractor: Optional[LLMExtractor] = None


def get_llm_extractor(llm_client=None) -> LLMExtractor:
    global _global_llm_extractor
    if _global_llm_extractor is None:
        _global_llm_extractor = LLMExtractor(llm_client=llm_client)
    elif llm_client is not None:
        _global_llm_extractor.llm_client = llm_client
    return _global_llm_extractor
