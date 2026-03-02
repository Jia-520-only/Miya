"""
故事分支管理工具
StoryBranch - 管理故事的不同分支和结局
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class StoryBranch:
    """故事分支"""
    branch_id: str
    name: str
    description: str
    parent_branch: str = ""
    choices: list = field(default_factory=list)
    created_at: str = ""


class StoryBranchManager:
    """故事分支管理器"""

    def __init__(self, data_path: str = "data/tavern_story_branches.json"):
        self.data_path = data_path
        self._branches: Dict[str, StoryBranch] = {}
        self._current_branches: Dict[str, str] = {}  # chat_id -> branch_id
        self._load()

    def _load(self):
        """加载分支数据"""
        if Path(self.data_path).exists():
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for branch_id, branch_data in data.get('branches', {}).items():
                        self._branches[branch_id] = StoryBranch(**branch_data)
                    self._current_branches = data.get('current_branches', {})
                    print(f"[StoryBranchManager] 加载了 {len(self._branches)} 个故事分支")
            except Exception as e:
                print(f"[StoryBranchManager] 加载失败: {e}")

    def _save(self):
        """保存分支数据"""
        try:
            Path(self.data_path).parent.mkdir(parents=True, exist_ok=True)
            data = {
                'branches': {
                    branch_id: {
                        'branch_id': branch.branch_id,
                        'name': branch.name,
                        'description': branch.description,
                        'parent_branch': branch.parent_branch,
                        'choices': branch.choices,
                        'created_at': branch.created_at
                    }
                    for branch_id, branch in self._branches.items()
                },
                'current_branches': self._current_branches
            }
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[StoryBranchManager] 保存失败: {e}")

    def create_branch(self, branch_id: str, name: str, description: str,
                      parent_branch: str = "") -> StoryBranch:
        """创建新分支"""
        branch = StoryBranch(
            branch_id=branch_id,
            name=name,
            description=description,
            parent_branch=parent_branch,
            created_at=datetime.now().isoformat()
        )
        self._branches[branch_id] = branch
        self._save()
        return branch

    def get_branch(self, branch_id: str) -> StoryBranch:
        """获取分支"""
        return self._branches.get(branch_id)

    def list_branches(self, root_branch: str = None) -> list:
        """列出分支"""
        if root_branch:
            # 返回指定分支的子分支
            return [
                b for b in self._branches.values()
                if b.parent_branch == root_branch
            ]
        return list(self._branches.values())

    def add_choice(self, branch_id: str, choice: str, leads_to: str):
        """添加选项"""
        if branch_id in self._branches:
            self._branches[branch_id].choices.append({
                'choice': choice,
                'leads_to': leads_to
            })
            self._save()

    def set_current_branch(self, chat_id: str, branch_id: str):
        """设置当前分支"""
        if branch_id in self._branches:
            self._current_branches[chat_id] = branch_id
            self._save()

    def get_current_branch(self, chat_id: str) -> StoryBranch:
        """获取当前分支"""
        branch_id = self._current_branches.get(chat_id)
        return self._branches.get(branch_id) if branch_id else None


# 单例模式
_branch_manager = None

def get_branch_manager() -> StoryBranchManager:
    """获取分支管理器单例"""
    global _branch_manager
    if _branch_manager is None:
        _branch_manager = StoryBranchManager()
    return _branch_manager


class CreateStoryBranch(BaseTool):
    """创建故事分支"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_story_branch",
            "description": "创建新的故事分支节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_id": {
                        "type": "string",
                        "description": "分支ID（唯一标识）"
                    },
                    "name": {
                        "type": "string",
                        "description": "分支名称"
                    },
                    "description": {
                        "type": "string",
                        "description": "分支描述/剧情概要"
                    },
                    "parent_branch": {
                        "type": "string",
                        "description": "父分支ID（如果是根分支则不填）",
                        "default": ""
                    }
                },
                "required": ["branch_id", "name", "description"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        branch_id = args.get("branch_id", "")
        name = args.get("name", "")
        description = args.get("description", "")
        parent_branch = args.get("parent_branch", "")

        if not branch_id or not name or not description:
            return "❌ 请填写完整的分支信息"

        from .story_branch import get_branch_manager

        manager = get_branch_manager()

        if branch_id in manager._branches:
            return f"❌ 分支ID '{branch_id}' 已存在"

        manager.create_branch(branch_id, name, description, parent_branch)

        return f"🌳 **创建故事分支成功**\n📖 {name}\n📝 {description}\n{'🔗 父分支: ' + parent_branch if parent_branch else '🌱 根分支'}"


class AddStoryChoice(BaseTool):
    """添加剧情选项"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "add_story_choice",
            "description": "为故事分支添加剧情选项",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_id": {
                        "type": "string",
                        "description": "分支ID"
                    },
                    "choice": {
                        "type": "string",
                        "description": "选项描述"
                    },
                    "leads_to": {
                        "type": "string",
                        "description": "该选项通向的分支ID"
                    }
                },
                "required": ["branch_id", "choice", "leads_to"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        branch_id = args.get("branch_id", "")
        choice = args.get("choice", "")
        leads_to = args.get("leads_to", "")

        if not branch_id or not choice or not leads_to:
            return "❌ 请填写完整的选项信息"

        from .story_branch import get_branch_manager

        manager = get_branch_manager()

        if branch_id not in manager._branches:
            return f"❌ 分支 '{branch_id}' 不存在"

        if leads_to not in manager._branches:
            return f"⚠️ 目标分支 '{leads_to}' 不存在（可能需要先创建）"

        manager.add_choice(branch_id, choice, leads_to)

        return f"✅ **添加选项成功**\n🔗 从 '{branch_id}' → '{leads_to}'\n📝 {choice}"


class ShowStoryTree(BaseTool):
    """显示故事树"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "show_story_tree",
            "description": "显示故事分支树状结构",
            "parameters": {
                "type": "object",
                "properties": {
                    "root_branch": {
                        "type": "string",
                        "description": "根分支ID（不填则显示所有）",
                        "default": ""
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        root_branch = args.get("root_branch", "")

        from .story_branch import get_branch_manager

        manager = get_branch_manager()

        branches = manager.list_branches(root_branch)

        if not branches:
            return "🌲 暂无故事分支"

        lines = ["🌲 **故事分支树**\n"]

        # 如果指定了根分支，显示子分支
        if root_branch:
            root = manager.get_branch(root_branch)
            if root:
                lines.append(f"📍 {root_branch}: {root.name}")
                lines.append(f"   {root.description}\n")

        # 显示所有分支
        for branch in branches:
            prefix = "  └─ " if root_branch else "🌱 "
            lines.append(f"{prefix}{branch.branch_id}: **{branch.name}**")
            lines.append(f"    {branch.description}")

            if branch.choices:
                lines.append("    选项:")
                for i, choice in enumerate(branch.choices, 1):
                    lines.append(f"      {i}. {choice['choice']} → {choice['leads_to']}")
            lines.append("")

        return "\n".join(lines)


class SelectStoryBranch(BaseTool):
    """选择故事分支"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "select_story_branch",
            "description": "选择并进入指定的故事分支",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_id": {
                        "type": "string",
                        "description": "分支ID"
                    }
                },
                "required": ["branch_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        branch_id = args.get("branch_id", "")
        chat_id = str(context.group_id or context.user_id)

        from .story_branch import get_branch_manager

        manager = get_branch_manager()

        branch = manager.get_branch(branch_id)
        if not branch:
            return f"❌ 分支 '{branch_id}' 不存在"

        manager.set_current_branch(chat_id, branch_id)

        from ..memory import TavernMemory
        memory = TavernMemory()
        memory.set_mode(chat_id, f"story_branch:{branch_id}")

        lines = [
            f"📍 **进入故事分支: {branch.name}**",
            f"",
            f"📝 {branch.description}",
            f"",
        ]

        if branch.choices:
            lines.append("可选择的路径:")
            for i, choice in enumerate(branch.choices, 1):
                lines.append(f"{i}. {choice['choice']}")

        return "\n".join(lines)
