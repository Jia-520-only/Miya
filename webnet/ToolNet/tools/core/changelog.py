"""
更新日志查询工具

查询弥娅项目的更新日志。
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

CHANGELOG_PATH = os.environ.get("CHANGELOG_PATH", "CHANGELOG.md")


class ChangelogTool(BaseTool):
    """更新日志查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "changelog",
            "description": """更新日志查询工具。

当用户询问版本更新日志、查看新功能时使用此工具。
可以查询最新版本信息或历史版本列表。

示例:
- 查看: 更新日志
- 新版本: 有什么新功能""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型: latest(最新), list(列表), show(详情)",
                        "enum": ["latest", "list", "show"],
                        "default": "latest",
                    },
                    "version": {
                        "type": "string",
                        "description": "show操作时需要指定版本号",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "list操作时返回的条目数量，默认5",
                        "default": 5,
                    },
                },
                "required": [],
            },
        }

    def _get_changelog_path(self) -> Path:
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / CHANGELOG_PATH

    def _parse_changelog(self, content: str, action: str = "latest", version: str = None, limit: int = 5) -> str:
        lines = content.split("\n")
        entries = []
        current_entry = {}
        in_changes = False

        for line in lines:
            if line.startswith("## "):
                if current_entry:
                    entries.append(current_entry)
                current_entry = {
                    "version": line.replace("## ", "").strip(),
                    "changes": [],
                }
                in_changes = False
            elif line.startswith("### "):
                in_changes = True
                if "changes" not in current_entry:
                    current_entry["changes"] = []
            elif in_changes and line.strip().startswith(("- ", "* ", "+ ")):
                current_entry["changes"].append(line.strip()[2:])

        if current_entry:
            entries.append(current_entry)

        if action == "latest" or action == "show":
            if action == "show" and version:
                target_entry = None
                for e in entries:
                    if version in e.get("version", ""):
                        target_entry = e
                        break
                if not target_entry:
                    return f"未找到版本 {version} 的更新日志"
                entry = target_entry
            else:
                entry = entries[0] if entries else {}

            if not entry:
                return "未找到更新日志"

            result = f"【{entry.get('version', '未知版本')}】\n\n"
            changes = entry.get("changes", [])
            if changes:
                result += "更新内容:\n"
                for change in changes[:10]:
                    result += f"- {change}\n"
            else:
                result += "暂无更新内容"

            return result

        else:
            result = "【历史版本列表】\n\n"
            for i, entry in enumerate(entries[:limit], 1):
                version = entry.get("version", "未知版本")
                changes_count = len(entry.get("changes", []))
                result += f"{i}. {version} ({changes_count}条更新)\n"
            return result

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        action = args.get("action", "latest")
        version = args.get("version")
        limit = args.get("limit", 5)

        try:
            changelog_path = self._get_changelog_path()

            if not changelog_path.exists():
                return "未找到更新日志文件"

            content = changelog_path.read_text(encoding="utf-8")
            return self._parse_changelog(content, action, version, limit)

        except Exception as e:
            logger.exception(f"读取更新日志失败: {e}")
            return f"读取更新日志失败：{str(e)}"


def get_changelog_tool():
    return ChangelogTool()
