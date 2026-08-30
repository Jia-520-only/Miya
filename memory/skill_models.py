"""
弥娅技能系统数据模型

参考 TencentDB Agent Memory 的技能管理设计：
- 技能是版本化的可复用工作流
- 支持从对话中提取、版本迭代、按需检索
- 与 MiyaMemoryCore 统一记忆系统集成
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillCategory(Enum):
    CODING = "coding"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    AUTOMATION = "automation"
    RESEARCH = "research"
    CREATIVE = "creative"
    TROUBLESHOOTING = "troubleshooting"
    CUSTOM = "custom"


class SkillSource(Enum):
    MANUAL = "manual"
    AUTO_EXTRACTED = "auto_extracted"
    IMPORTED = "imported"
    CONVERSATION_TEACHING = "conversation_teaching"


class SkillStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class SkillStep:
    """技能执行步骤"""

    order: int
    action: str
    description: str
    expected_outcome: str = ""
    validation: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillTrigger:
    """技能触发条件"""

    keywords: List[str] = field(default_factory=list)
    context_patterns: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    min_confidence: float = 0.3

    def match_score(self, user_input: str, available_tools: List[str] = None) -> float:
        score = 0.0
        input_lower = user_input.lower()

        if self.keywords:
            matched = 0
            for kw in self.keywords:
                if kw.lower() in input_lower or any(w in input_lower for w in kw.lower().split()):
                    matched += 1
            keyword_score = min(1.0, matched / max(1, len(self.keywords)) * 1.2)
            score += keyword_score * 0.5

        if self.context_patterns:
            import re

            matched = sum(1 for p in self.context_patterns if re.search(p, user_input))
            pattern_score = matched / len(self.context_patterns)
            score += pattern_score * 0.3

        if self.required_tools and available_tools:
            available = set(available_tools)
            matched = sum(1 for t in self.required_tools if t in available)
            tool_score = matched / len(self.required_tools) if self.required_tools else 1.0
            score += tool_score * 0.2
        elif not self.required_tools:
            score += 0.2

        return min(1.0, score)


@dataclass
class SkillVersion:
    """技能版本记录"""

    version: str
    description: str
    changes: str = ""
    steps: List[SkillStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    success_rate: float = 0.0
    execution_count: int = 0


@dataclass
class Skill:
    """
    弥娅技能数据模型

    一个技能是一个版本化的、可复用的工作流，
    弥娅可以从对话中学到、沉淀、迭代并复用到新场景。
    """

    id: str = ""
    name: str = ""
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM

    trigger: SkillTrigger = field(default_factory=SkillTrigger)

    current_version: str = "1.0.0"
    steps: List[SkillStep] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)

    version_history: List[SkillVersion] = field(default_factory=list)

    status: SkillStatus = SkillStatus.ACTIVE

    success_rate: float = 0.0
    execution_count: int = 0
    last_executed: Optional[str] = None
    failure_count: int = 0

    source: SkillSource = SkillSource.MANUAL
    source_conversation_id: str = ""

    tags: List[str] = field(default_factory=list)
    user_id: str = "global"
    group_id: str = ""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def _generate_id(self) -> str:
        unique = f"{self.name}{self.user_id}{datetime.now().isoformat()}{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique.encode("utf-8")).hexdigest()[:16]

    def record_execution(self, success: bool):
        self.execution_count += 1
        self.last_executed = datetime.now().isoformat()
        if success:
            n = self.execution_count
            if n > 0:
                self.success_rate = (self.success_rate * (n - 1) + 1.0) / n
        else:
            self.failure_count += 1
            n = self.execution_count
            if n > 0:
                self.success_rate = (self.success_rate * (n - 1) + 0.0) / n

        if self.version_history:
            self.version_history[-1].execution_count = self.execution_count
            self.version_history[-1].success_rate = self.success_rate

    def new_version(
        self,
        new_ver: str,
        description: str,
        steps: List[SkillStep],
        changes: str = "",
    ):
        old_ver = SkillVersion(
            version=self.current_version,
            description=self.description,
            steps=list(self.steps),
        )
        self.version_history.append(old_ver)
        self.current_version = new_ver
        self.description = description
        self.steps = steps
        self.updated_at = datetime.now().isoformat()

        new_ver_record = SkillVersion(
            version=new_ver,
            description=description,
            steps=list(steps),
            changes=changes,
        )
        self.version_history.append(new_ver_record)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "trigger": {
                "keywords": self.trigger.keywords,
                "context_patterns": self.trigger.context_patterns,
                "required_tools": self.trigger.required_tools,
                "min_confidence": self.trigger.min_confidence,
            },
            "current_version": self.current_version,
            "steps": [
                {
                    "order": s.order,
                    "action": s.action,
                    "description": s.description,
                    "expected_outcome": s.expected_outcome,
                    "validation": s.validation,
                    "parameters": s.parameters,
                }
                for s in self.steps
            ],
            "resources": self.resources,
            "version_history": [
                {
                    "version": v.version,
                    "description": v.description,
                    "changes": v.changes,
                    "steps_count": len(v.steps),
                    "created_at": v.created_at,
                    "success_rate": v.success_rate,
                    "execution_count": v.execution_count,
                }
                for v in self.version_history
            ],
            "status": self.status.value,
            "success_rate": self.success_rate,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed,
            "failure_count": self.failure_count,
            "source": self.source.value,
            "source_conversation_id": self.source_conversation_id,
            "tags": self.tags,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Skill":
        trigger_data = data.get("trigger", {})
        trigger = SkillTrigger(
            keywords=trigger_data.get("keywords", []),
            context_patterns=trigger_data.get("context_patterns", []),
            required_tools=trigger_data.get("required_tools", []),
            min_confidence=trigger_data.get("min_confidence", 0.6),
        )

        steps = [
            SkillStep(
                order=s.get("order", i + 1),
                action=s.get("action", ""),
                description=s.get("description", ""),
                expected_outcome=s.get("expected_outcome", ""),
                validation=s.get("validation", ""),
                parameters=s.get("parameters", {}),
            )
            for i, s in enumerate(data.get("steps", []))
        ]

        version_history = [
            SkillVersion(
                version=v.get("version", ""),
                description=v.get("description", ""),
                changes=v.get("changes", ""),
                created_at=v.get("created_at", ""),
                success_rate=v.get("success_rate", 0.0),
                execution_count=v.get("execution_count", 0),
            )
            for v in data.get("version_history", [])
        ]

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=SkillCategory(data.get("category", "custom")),
            trigger=trigger,
            current_version=data.get("current_version", "1.0.0"),
            steps=steps,
            resources=data.get("resources", []),
            version_history=version_history,
            status=SkillStatus(data.get("status", "active")),
            success_rate=data.get("success_rate", 0.0),
            execution_count=data.get("execution_count", 0),
            last_executed=data.get("last_executed"),
            failure_count=data.get("failure_count", 0),
            source=SkillSource(data.get("source", "manual")),
            source_conversation_id=data.get("source_conversation_id", ""),
            tags=data.get("tags", []),
            user_id=data.get("user_id", "global"),
            group_id=data.get("group_id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )

    def to_prompt(self) -> str:
        """生成给 AI 看的技能提示"""
        steps_text = "\n".join(
            f"  {s.order}. {s.action}: {s.description}" + (f" → {s.expected_outcome}" if s.expected_outcome else "")
            for s in self.steps
        )
        return (
            f"## 技能: {self.name} (v{self.current_version})\n"
            f"{self.description}\n\n"
            f"步骤:\n{steps_text}\n\n"
            f"成功率: {self.success_rate:.0%} ({self.execution_count}次执行)\n"
            f"标签: {', '.join(self.tags) if self.tags else '无'}"
        )
