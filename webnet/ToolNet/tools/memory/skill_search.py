"""
技能查询工具 — 搜索可复用的技能
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class SkillSearch(BaseTool):
    """根据当前任务搜索匹配的技能"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "skill_search",
            "description": "搜索弥娅已学会的技能。当需要完成某个任务时，先搜索是否有可复用的技能流程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "任务描述，用于匹配技能"},
                    "category": {
                        "type": "string",
                        "description": "技能分类过滤: coding/analysis/communication/automation/research/creative/troubleshooting/custom",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        query = args.get("query", "")
        _category = args.get("category")
        limit = args.get("limit", 5)

        if not query:
            return "请输入任务描述来搜索匹配的技能"

        try:
            from memory.skill_manager import get_skill_manager

            manager = get_skill_manager()
            await manager.initialize()

            matches = await manager.search(query, limit=limit)

            if not matches:
                return f"未找到与「{query}」匹配的技能"

            lines = [f"找到 {len(matches)} 个匹配技能：\n"]
            for skill, score in matches:
                steps_preview = " → ".join(s.action for s in skill.steps[:3])
                lines.append(f"### {skill.name} (匹配度: {score:.0%})")
                lines.append(
                    f"版本: v{skill.current_version} | 成功率: {skill.success_rate:.0%} ({skill.execution_count}次)"
                )
                lines.append(f"描述: {skill.description}")
                lines.append(f"步骤: {steps_preview}")
                lines.append(f"标签: {', '.join(skill.tags) if skill.tags else '无'}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[SkillSearch] 失败: {e}")
            return f"技能搜索失败: {e}"
