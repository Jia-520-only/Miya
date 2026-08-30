"""
技能保存工具 — 保存或更新技能
"""

import logging
from typing import Any, Dict, List

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class SkillSave(BaseTool):
    """保存一个可复用的技能/工作流"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "skill_save",
            "description": "保存一个可复用的技能流程。当弥娅学会了一个新的做事方法、发现了一个有效的工作流时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                    "description": {"type": "string", "description": "技能描述"},
                    "category": {
                        "type": "string",
                        "description": "分类: coding/analysis/communication/automation/research/creative/troubleshooting/custom",
                    },
                    "steps": {
                        "type": "array",
                        "description": "执行步骤列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "description": "步骤动作"},
                                "description": {"type": "string", "description": "步骤说明"},
                                "expected_outcome": {"type": "string", "description": "预期结果"},
                            },
                        },
                    },
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "触发条件关键词",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签",
                    },
                },
                "required": ["name", "description", "steps"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        name = args.get("name", "").strip()
        description = args.get("description", "").strip()
        category_str = args.get("category", "custom")
        steps_raw = args.get("steps", [])
        triggers = args.get("triggers", [])
        tags = args.get("tags", [])

        if not name or not steps_raw:
            return "技能名称和步骤不能为空"

        try:
            from memory.skill_manager import get_skill_manager
            from memory.skill_models import Skill, SkillCategory, SkillSource, SkillStep, SkillStatus, SkillTrigger

            manager = get_skill_manager()
            await manager.initialize()

            steps = [
                SkillStep(
                    order=i + 1,
                    action=s.get("action", f"步骤{i + 1}"),
                    description=s.get("description", ""),
                    expected_outcome=s.get("expected_outcome", ""),
                )
                for i, s in enumerate(steps_raw)
            ]

            trigger = SkillTrigger(keywords=triggers)

            skill = Skill(
                name=name,
                description=description,
                category=SkillCategory(category_str),
                trigger=trigger,
                steps=steps,
                tags=tags,
                source=SkillSource.MANUAL,
                status=SkillStatus.ACTIVE,
                user_id=str(context.user_id) if context.user_id else "global",
            )

            skill_id = await manager.save(skill)

            return (
                f"已保存技能「{name}」(v{skill.current_version})\n"
                f"ID: {skill_id}\n"
                f"类别: {category_str}\n"
                f"步骤数: {len(steps)}\n"
                f"触发词: {', '.join(triggers) if triggers else '无'}\n"
                f"标签: {', '.join(tags) if tags else '无'}"
            )

        except Exception as e:
            logger.error(f"[SkillSave] 失败: {e}")
            return f"技能保存失败: {e}"
