"""
弥娅技能管理器 (SkillManager)

参考 TencentDB Agent Memory 的技能管理系统，为弥娅提供：
1. 技能存储 — JSON + SQLite 双后端
2. 技能提取 — 从对话中自动提取可复用工作流
3. 技能检索 — 按触发条件匹配，融合 RRF 排序
4. 技能版本化 — 迭代追踪，保留历史
5. 执行反馈 — 追踪成功率，质量评分
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from memory.skill_models import (
    Skill,
    SkillCategory,
    SkillSource,
    SkillStatus,
    SkillStep,
    SkillTrigger,
)

logger = logging.getLogger(__name__)

SKILL_EXTRACTION_PROMPT = """从以下对话中提取可复用的"做事方法"（技能）。

用户可能在教弥娅如何完成某个任务。如果有，提取为一个技能。
如果没有教会任何可复用的工作流，返回空列表。

返回 JSON 数组：
[{
    "name": "技能名称",
    "description": "简短描述这个技能做什么",
    "category": "coding/analysis/communication/automation/research/creative/troubleshooting/custom",
    "steps": [
        {"action": "步骤1动作", "description": "步骤1说明", "expected_outcome": "预期结果"},
        ...
    ],
    "triggers": ["触发关键词1", "触发关键词2"],
    "tags": ["标签1", "标签2"],
    "importance": 0.7
}]

对话：
{conversation}

只返回 JSON 数组。"""


class SkillManager:
    """
    弥娅技能管理器

    存储路径：data/skills/{skill_id}.json
    索引文件：data/skills/index.json
    """

    def __init__(self, data_dir: str = "data/skills"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "index.json"
        self._index: Dict[str, Dict] = {}
        self._cache: Dict[str, Skill] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._loaded = False
        self._config = self._load_config()
        self._llm_client = None
        self._load_index()

    def _load_config(self) -> Dict[str, Any]:
        try:
            config_path = Path(__file__).parent.parent / "config" / "memory_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return cfg.get("skill_manager", {})
        except Exception:
            pass
        return {}

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._index = data.get("skills", {})
                    tag_data = data.get("tag_index", {})
                    self._tag_index = {k: set(v) for k, v in tag_data.items()}
            except Exception as e:
                logger.warning(f"[SkillManager] 加载索引失败: {e}")

    def _save_index(self):
        try:
            data = {
                "skills": self._index,
                "tag_index": {k: list(v) for k, v in self._tag_index.items()},
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[SkillManager] 保存索引失败: {e}")

    def _skill_path(self, skill_id: str) -> Path:
        return self.data_dir / f"{skill_id}.json"

    async def initialize(self):
        if self._loaded:
            return
        self._load_index()
        self._loaded = True
        logger.info(f"[SkillManager] 初始化完成: {len(self._index)} 个技能")

    async def save(self, skill: Skill) -> str:
        try:
            file_path = self._skill_path(skill.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(skill.to_dict(), f, ensure_ascii=False, indent=2)

            self._index[skill.id] = {
                "name": skill.name,
                "category": skill.category.value,
                "current_version": skill.current_version,
                "status": skill.status.value,
                "success_rate": skill.success_rate,
                "tags": skill.tags,
                "user_id": skill.user_id,
            }

            for tag in skill.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(skill.id)

            self._save_index()
            self._cache[skill.id] = skill

            logger.info(f"[SkillManager] 保存技能: {skill.name} (v{skill.current_version})")
            return skill.id
        except Exception as e:
            logger.error(f"[SkillManager] 保存失败: {e}")
            return ""

    async def load(self, skill_id: str) -> Optional[Skill]:
        if skill_id in self._cache:
            return self._cache[skill_id]

        file_path = self._skill_path(skill_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            skill = Skill.from_dict(data)
            self._cache[skill_id] = skill
            return skill
        except Exception as e:
            logger.error(f"[SkillManager] 加载失败: {e}")
            return None

    async def delete(self, skill_id: str) -> bool:
        try:
            file_path = self._skill_path(skill_id)
            if file_path.exists():
                file_path.unlink()

            info = self._index.pop(skill_id, None)
            if info:
                for tag in info.get("tags", []):
                    if tag in self._tag_index:
                        self._tag_index[tag].discard(skill_id)

            self._cache.pop(skill_id, None)
            self._save_index()
            return True
        except Exception as e:
            logger.error(f"[SkillManager] 删除失败: {e}")
            return False

    async def query(
        self,
        name: str = "",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        sort_by: str = "success_rate",
    ) -> List[Skill]:
        results = []

        candidate_ids = set(self._index.keys())

        if tags:
            if tags[0] in self._tag_index:
                candidate_ids = candidate_ids & self._tag_index[tags[0]]

        for skill_id in candidate_ids:
            info = self._index.get(skill_id, {})

            if name and name.lower() not in info.get("name", "").lower():
                continue
            if category and info.get("category") != category:
                continue
            if user_id and info.get("user_id") != user_id:
                continue
            if status and info.get("status") != status:
                continue

            skill = await self.load(skill_id)
            if skill:
                results.append(skill)

        if sort_by == "success_rate":
            results.sort(key=lambda s: s.success_rate, reverse=True)
        elif sort_by == "execution_count":
            results.sort(key=lambda s: s.execution_count, reverse=True)
        elif sort_by == "updated_at":
            results.sort(key=lambda s: s.updated_at, reverse=True)

        return results[:limit]

    async def search(
        self,
        user_input: str,
        available_tools: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Tuple[Skill, float]]:
        """
        搜索最匹配的技能 — 触发条件匹配 + RRF 融合排序
        """
        candidates = await self.query(status="active", limit=100)

        if not candidates:
            return []

        scored = []
        for skill in candidates:
            trigger_score = skill.trigger.match_score(user_input, available_tools)

            text_score = 0.0
            input_lower = user_input.lower()
            for step in skill.steps:
                if any(w in input_lower for w in step.action.lower().split()):
                    text_score += 0.1
                if any(w in input_lower for w in step.description.lower().split()):
                    text_score += 0.05
            text_score = min(0.4, text_score)

            # 标签匹配
            tag_score = 0.0
            for tag in skill.tags:
                if tag.lower() in input_lower:
                    tag_score += 0.15
            tag_score = min(0.3, tag_score)

            # 成功率加成
            success_bonus = skill.success_rate * 0.15

            # 综合 RRF 融合
            combined = trigger_score * 0.40 + text_score * 0.25 + tag_score * 0.20 + success_bonus

            if combined >= skill.trigger.min_confidence:
                scored.append((skill, combined))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def extract_from_conversation(
        self,
        user_input: str,
        ai_response: str,
        user_id: str = "global",
        group_id: str = "",
    ) -> List[Skill]:
        """
        从对话中提取技能 — LLM 驱动。
        需要 llm_client 可用。
        """
        if not self._llm_client:
            return []

        combined = f"用户: {user_input}\n弥娅: {ai_response}"
        if len(combined.strip()) < 20:
            return []

        try:
            prompt = SKILL_EXTRACTION_PROMPT.format(conversation=combined)
            response = await self._call_llm(prompt)
            if not response:
                return []

            extracted = self._parse_skill_response(response)
            skills = []

            for item in extracted:
                if not item.get("name") or not item.get("steps"):
                    continue

                steps = [
                    SkillStep(
                        order=i + 1,
                        action=s.get("action", ""),
                        description=s.get("description", ""),
                        expected_outcome=s.get("expected_outcome", ""),
                    )
                    for i, s in enumerate(item.get("steps", []))
                ]

                trigger = SkillTrigger(
                    keywords=item.get("triggers", []),
                )

                skill = Skill(
                    name=item.get("name", "未命名技能"),
                    description=item.get("description", ""),
                    category=SkillCategory(item.get("category", "custom")),
                    trigger=trigger,
                    steps=steps,
                    tags=item.get("tags", []),
                    user_id=user_id,
                    group_id=group_id,
                    source=SkillSource.CONVERSATION_TEACHING,
                    status=SkillStatus.DRAFT,
                )

                skills.append(skill)

            if skills:
                logger.info(f"[SkillManager] 从对话提取了 {len(skills)} 个技能")

            return skills

        except Exception as e:
            logger.debug(f"[SkillManager] 技能提取失败: {e}")
            return []

    async def record_execution(self, skill_id: str, success: bool) -> bool:
        skill = await self.load(skill_id)
        if not skill:
            return False

        skill.record_execution(success)

        if skill.success_rate < 0.3 and skill.execution_count >= 3:
            skill.status = SkillStatus.DEPRECATED

        await self.save(skill)
        return True

    async def new_version(
        self,
        skill_id: str,
        new_ver: str,
        description: str,
        steps: List[Dict],
        changes: str = "",
    ) -> bool:
        skill = await self.load(skill_id)
        if not skill:
            return False

        new_steps = [
            SkillStep(
                order=s.get("order", i + 1),
                action=s.get("action", ""),
                description=s.get("description", ""),
                expected_outcome=s.get("expected_outcome", ""),
                validation=s.get("validation", ""),
                parameters=s.get("parameters", {}),
            )
            for i, s in enumerate(steps)
        ]

        skill.new_version(new_ver, description, new_steps, changes)
        await self.save(skill)
        return True

    async def search_and_inject(
        self,
        user_input: str,
        available_tools: Optional[List[str]] = None,
        limit: int = 3,
    ) -> str:
        """
        搜索匹配的技能并生成可注入 AI Prompt 的文本。
        """
        matches = await self.search(user_input, available_tools, limit)

        if not matches:
            return ""

        lines = ["## 弥娅已有技能（或许可复用）\n"]
        for skill, score in matches:
            lines.append(f"- **{skill.name}** (匹配度: {score:.0%}, 成功率: {skill.success_rate:.0%})")
            lines.append(f"  {skill.description[:120]}")

        return "\n".join(lines)

    async def get_stats(self) -> Dict[str, Any]:
        skills = await self.query(limit=1000)
        if not skills:
            return {"total": 0}

        by_category = {}
        by_status = {}
        total_executions = 0

        for s in skills:
            cat = s.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            st = s.status.value
            by_status[st] = by_status.get(st, 0) + 1

            total_executions += s.execution_count

        avg_success = sum(s.success_rate for s in skills) / len(skills) if skills else 0

        return {
            "total": len(skills),
            "by_category": by_category,
            "by_status": by_status,
            "total_executions": total_executions,
            "avg_success_rate": round(avg_success, 3),
        }

    def set_llm_client(self, client):
        self._llm_client = client

    def _parse_skill_response(self, response: str) -> List[Dict]:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:]) if not lines[-1].strip().startswith("```") else "\n".join(lines[1:-1])

        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass
        return []

    async def _call_llm(self, prompt: str) -> Optional[str]:
        if not self._llm_client:
            return None
        try:
            if hasattr(self._llm_client, "chat"):
                messages = [{"role": "user", "content": prompt}]
                result = await self._llm_client.chat(messages, temperature=0.1, max_tokens=1024)
                if isinstance(result, dict):
                    return result.get("content", "")
                if isinstance(result, str):
                    return result
            elif hasattr(self._llm_client, "complete"):
                return await self._llm_client.complete(prompt)
            elif callable(self._llm_client):
                return await self._llm_client(prompt)
        except Exception as e:
            logger.debug(f"[SkillManager] LLM 调用失败: {e}")
        return None


_global_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _global_skill_manager
    if _global_skill_manager is None:
        _global_skill_manager = SkillManager()
    return _global_skill_manager
