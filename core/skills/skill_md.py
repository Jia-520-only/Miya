"""
弥娅技能系统 - SKILL.md 标准化格式

参考 AstrBot SKILL.md 格式，为 MIYA 创建统一的技能定义规范

SKILL.md 格式：
```markdown
# Skill Name
description: 技能描述

## Tools
- tool_name: 工具名称
  description: 工具描述
  parameters:
    - name: 参数名
      type: string
      description: 参数描述
      required: true/false

## Instructions
技能使用说明...

## Examples
示例1: ...
示例2: ...
```

作者: MIYA
日期: 2026-04-28
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== SKILL.md 解析器 ====================


@dataclass
class SkillTool:
    """技能工具定义"""

    name: str
    description: str
    parameters: List[Dict] = field(default_factory=list)


@dataclass
class SkillInfo:
    """标准化技能信息"""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tools: List[SkillTool] = field(default_factory=list)
    instructions: str = ""
    examples: List[str] = field(default_factory=list)
    enabled: bool = True
    path: str = ""
    loaded_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SkillMarkdownParser:
    """
    SKILL.md 解析器

    将 SKILL.md 文件解析为 SkillInfo 对象
    """

    @staticmethod
    def parse(skill_path: str | Path) -> Optional[SkillInfo]:
        """解析 SKILL.md 文件"""
        path = Path(skill_path)

        if not path.exists():
            logger.warning(f"[SkillParser] 文件不存在: {skill_path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"[SkillParser] 读取失败: {e}")
            return None

        return SkillMarkdownParser._parse_content(content, str(path))

    @staticmethod
    def _parse_content(content: str, path: str) -> Optional[SkillInfo]:
        """解析 SKILL.md 内容"""
        lines = content.split("\n")

        # 解析标题（Skill Name）
        name = ""
        description = ""

        for _i, line in enumerate(lines):
            line = line.strip()

            # 标题
            if line.startswith("# ") and not name:
                name = line[2:].strip()
                continue

            # 描述
            if line.startswith("description:"):
                description = line[12:].strip()
                continue

        if not name:
            name = Path(path).parent.name

        # 解析 Tools 章节
        tools = SkillMarkdownParser._parse_tools(content)

        # 解析 Instructions 章节
        instructions = SkillMarkdownParser._parse_section(content, "## Instructions")

        # 解析 Examples 章节
        examples = SkillMarkdownParser._parse_examples(content)

        return SkillInfo(
            name=name,
            description=description,
            tools=tools,
            instructions=instructions,
            examples=examples,
            path=path,
        )

    @staticmethod
    def _parse_tools(content: str) -> List[SkillTool]:
        """解析 Tools 章节"""
        tools = []

        # 提取 Tools 章节内容
        tools_match = re.search(r"## Tools\n(.*?)(?=##|$)", content, re.DOTALL)
        if not tools_match:
            return tools

        tools_text = tools_match.group(1)

        # 解析每个工具
        tool_pattern = r"- (\w+):\s*(.+?)(?=\n- |\n\n|$)"
        for match in re.finditer(tool_pattern, tools_text, re.DOTALL):
            tool_name = match.group(1)
            tool_desc = match.group(2).strip()

            # 解析参数
            params = []
            param_section = re.search(rf"{tool_name}.*?parameters:(.*?)(?=- \w+:|$)", tools_text, re.DOTALL)
            if param_section:
                params_text = param_section.group(1)
                for p in re.finditer(
                    r"- name: (\w+)\s+type: (\w+)\s+description: (.+?)(?:required: (true|false))?",
                    params_text,
                ):
                    params.append(
                        {
                            "name": p.group(1),
                            "type": p.group(2),
                            "description": p.group(3),
                            "required": p.group(4) == "true" if p.group(4) else False,
                        }
                    )

            tools.append(
                SkillTool(
                    name=tool_name,
                    description=tool_desc,
                    parameters=params,
                )
            )

        return tools

    @staticmethod
    def _parse_section(content: str, section_title: str) -> str:
        """解析章节内容"""
        match = re.search(rf"{section_title}\n(.*?)(?=##|$)", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _parse_examples(content: str) -> List[str]:
        """解析 Examples 章节"""
        examples = []
        match = re.search(r"## Examples\n(.*?)(?=##|$)", content, re.DOTALL)
        if match:
            example_text = match.group(1)
            for line in example_text.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    examples.append(line[1:].strip())
        return examples

    @staticmethod
    def to_openai_schema(tools: List[SkillTool]) -> List[Dict]:
        """转换为 OpenAI 工具格式"""
        result = []
        for tool in tools:
            params = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            for p in tool.parameters:
                params["properties"][p["name"]] = {
                    "type": p["type"],
                    "description": p["description"],
                }
                if p.get("required"):
                    params["required"].append(p["name"])

            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": params,
                    },
                }
            )
        return result


# ==================== 技能管理器 ====================


class SkillManager:
    """
    MIYA 技能管理器

    功能：
    - 扫描和加载 SKILL.md 技能
    - 技能启用/禁用
    - 技能搜索
    - 转换为工具
    """

    def __init__(self, skills_dir: str = "core/skills"):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, SkillInfo] = {}
        self._initialized = False

    async def initialize(self):
        """初始化技能管理器"""
        logger.info("[SkillManager] 初始化...")

        await self._scan_skills()

        self._initialized = True
        logger.info(f"[SkillManager] 已加载 {len(self._skills)} 个技能")

    async def _scan_skills(self):
        """扫描技能目录"""
        if not self.skills_dir.exists():
            logger.warning(f"[SkillManager] 技能目录不存在: {self.skills_dir}")
            return

        # 扫描所有 SKILL.md 文件
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            skill_dir = skill_file.parent

            # 跳过 __pycache__ 等目录
            if any(p.startswith("_") for p in skill_dir.parts):
                continue

            skill_info = SkillMarkdownParser.parse(skill_file)
            if skill_info:
                self._skills[skill_info.name] = skill_info
                logger.info(f"[SkillManager] 加载技能: {skill_info.name}")

    def get_skill(self, name: str) -> Optional[SkillInfo]:
        """获取技能"""
        return self._skills.get(name)

    def list_skills(self, enabled_only: bool = False) -> List[Dict]:
        """列出技能"""
        result = []
        for _name, skill in self._skills.items():
            if enabled_only and not skill.enabled:
                continue
            result.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "version": skill.version,
                    "tools_count": len(skill.tools),
                    "enabled": skill.enabled,
                    "path": skill.path,
                }
            )
        return result

    def enable_skill(self, name: str) -> bool:
        """启用技能"""
        if name in self._skills:
            self._skills[name].enabled = True
            logger.info(f"[SkillManager] 启用技能: {name}")
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        """禁用技能"""
        if name in self._skills:
            self._skills[name].enabled = False
            logger.info(f"[SkillManager] 禁用技能: {name}")
            return True
        return False

    def search_skills(self, query: str) -> List[SkillInfo]:
        """搜索技能"""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            if query in skill.name.lower() or query in skill.description.lower():
                results.append(skill)
        return results

    def get_tools_schema(self) -> List[Dict]:
        """获取所有技能工具的 Schema"""
        schema = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            schema.extend(SkillMarkdownParser.to_openai_schema(skill.tools))
        return schema

    def get_skill_tool(self, tool_name: str) -> Optional[SkillTool]:
        """获取指定的技能工具"""
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            for tool in skill.tools:
                if tool.name == tool_name:
                    return tool
        return None

    async def execute_skill_tool(self, tool_name: str, arguments: Dict, context: Dict) -> str:
        """执行技能工具"""
        # 查找工具所属技能
        for skill in self._skills.values():
            if not skill.enabled:
                continue

            for tool in skill.tools:
                if tool.name == tool_name:
                    # 构建执行上下文

                    # 这里可以调用实际的技能处理逻辑
                    return f"执行技能工具: {tool_name}\n技能: {skill.name}\n参数: {arguments}"

        return f"工具未找到: {tool_name}"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        enabled = sum(1 for s in self._skills.values() if s.enabled)
        total_tools = sum(len(s.tools) for s in self._skills.values())
        return {
            "total_skills": len(self._skills),
            "enabled_skills": enabled,
            "disabled_skills": len(self._skills) - enabled,
            "total_tools": total_tools,
        }


# ==================== 全局实例 ====================


_skill_manager: Optional[SkillManager] = None


def get_skill_manager(skills_dir: str = "core/skills") -> SkillManager:
    """获取技能管理器"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager(skills_dir)
    return _skill_manager


async def initialize_skill_manager(skills_dir: str = "core/skills") -> SkillManager:
    """初始化技能管理器"""
    manager = get_skill_manager(skills_dir)
    await manager.initialize()
    return manager


__all__ = [
    "SkillTool",
    "SkillInfo",
    "SkillMarkdownParser",
    "SkillManager",
    "get_skill_manager",
    "initialize_skill_manager",
]
