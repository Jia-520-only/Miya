#!/usr/bin/env python3
"""
Slash Commands 系统 - Claude Code 风格的命令
支持 /git, /feature-dev 等命令组
从 text_config.json 加载配置
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _load_commands_from_config() -> Dict[str, Any]:
    """从 text_config.json 加载命令配置"""
    try:
        # 正确计算项目根目录路径
        script_dir = Path(__file__).resolve().parent
        # 从 core/skills/ 向上两级到项目根目录
        project_root = script_dir.parent.parent
        config_path = project_root / "config" / "text_config.json"

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("command_keywords", {})
    except Exception as e:
        print(f"Warning: Failed to load command config: {e}")
    return {}


_config = _load_commands_from_config()


@dataclass
class CommandDefinition:
    name: str
    description: str
    subcommands: Dict[str, "CommandDefinition"] = field(default_factory=dict)
    handler: Optional[Callable] = None
    usage: str = ""


class SlashCommandManager:
    """Slash 命令管理器"""

    def __init__(self):
        self.commands: Dict[str, CommandDefinition] = {}
        self._register_default_commands()

    def _register_default_commands(self):
        """注册默认命令 - 从配置加载 + 固定命令"""

        # Git命令组 (固定)
        self.register_command(
            "git",
            "Git 操作",
            [
                ("status", "查看仓库状态", "git status"),
                ("diff", "查看差异", "git diff"),
                ("log", "查看提交历史", "git log"),
                ("branch", "查看分支", "git branch"),
                ("commit", "提交更改", "git commit -m"),
                ("add", "添加文件", "git add"),
                ("push", "推送到远程", "git push"),
                ("pull", "从远程拉取", "git pull"),
                ("checkout", "切换分支", "git checkout"),
                ("stash", "暂存工作区", "git stash"),
                ("merge", "合并分支", "git merge"),
                ("rebase", "变基", "git rebase"),
                ("reset", "重置", "git reset"),
                ("fetch", "获取", "git fetch"),
            ],
        )

        self.register_command(
            "feature-dev",
            "功能开发工作流",
            [
                ("start", "开始新功能", None),
                ("plan", "规划功能", None),
                ("explore", "探索代码库", None),
                ("implement", "实现功能", None),
                ("review", "审查代码", None),
                ("test", "测试功能", None),
                ("finish", "完成开发", None),
            ],
        )

        self.register_command(
            "project",
            "项目操作",
            [
                ("analyze", "分析项目", None),
                ("tree", "查看项目结构", None),
                ("deps", "查看依赖", None),
                ("docs", "生成文档", None),
            ],
        )

        self.register_command(
            "code",
            "代码操作",
            [
                ("explore", "探索代码", None),
                ("review", "审查代码", None),
                ("architect", "架构设计", None),
                ("explain", "解释代码", None),
                ("format", "格式化代码", None),
            ],
        )

        # 从配置加载命令组
        self._register_config_commands()

    def _register_config_commands(self):
        """从配置加载命令组"""

        # stats 命令
        stats_config = _config.get("stats", {})
        if stats_config:
            subcommands = []
            for sub_name, sub_keywords in stats_config.get("subcommands", {}).items():
                desc = sub_keywords[0] if isinstance(sub_keywords, list) else sub_name
                subcommands.append((sub_name, desc, None))
            if subcommands:
                self.register_command("stats", "系统统计", subcommands)

        # admin 命令
        admin_config = _config.get("admin", {})
        if admin_config:
            subcommands = []
            for sub_name, sub_keywords in admin_config.get("subcommands", {}).items():
                desc = sub_keywords[0] if isinstance(sub_keywords, list) else sub_name
                subcommands.append((sub_name, desc, None))
            if subcommands:
                self.register_command("admin", "管理员操作", subcommands)

        # faq 命令
        faq_config = _config.get("faq", {})
        if faq_config:
            subcommands = []
            for sub_name, sub_keywords in faq_config.get("subcommands", {}).items():
                desc = sub_keywords[0] if isinstance(sub_keywords, list) else sub_name
                subcommands.append((sub_name, desc, None))
            if subcommands:
                self.register_command("faq", "FAQ管理", subcommands)

        # system 命令
        system_config = _config.get("system", {})
        if system_config:
            subcommands = []
            for sub_name, sub_keywords in system_config.get("subcommands", {}).items():
                desc = sub_keywords[0] if isinstance(sub_keywords, list) else sub_name
                subcommands.append((sub_name, desc, None))
            if subcommands:
                self.register_command("system", "系统操作", subcommands)

    def register_command(self, name: str, description: str, subcommands: List[tuple] = None):
        """注册命令"""
        cmd = CommandDefinition(name=name, description=description)
        if subcommands:
            for sub_name, sub_desc, _ in subcommands:
                cmd.subcommands[sub_name] = CommandDefinition(name=sub_name, description=sub_desc)
        self.commands[name] = cmd

    def parse(self, input_str: str) -> Optional[Dict[str, Any]]:
        """解析命令输入"""
        input_str = input_str.strip()
        if not input_str.startswith("/"):
            return None

        parts = input_str.split()
        cmd_name = parts[0][1:]

        if cmd_name not in self.commands:
            return None

        cmd = self.commands[cmd_name]
        result = {
            "command": cmd_name,
            "description": cmd.description,
            "subcommand": None,
            "args": parts[1:] if len(parts) > 1 else [],
        }

        if cmd.subcommands and len(parts) > 1:
            sub_name = parts[1]
            if sub_name in cmd.subcommands:
                result["subcommand"] = sub_name
                result["subcommand_description"] = cmd.subcommands[sub_name].description
                result["args"] = parts[2:]

        return result

    def get_help(self, command: str = None) -> str:
        """获取帮助信息"""
        if command:
            if command in self.commands:
                cmd = self.commands[command]
                lines = [f"## /{command} - {cmd.description}", ""]
                for sub in cmd.subcommands.items():
                    lines.append(f"- `/{command} {sub[0]}` - {sub[1].description}")
                return "\n".join(lines)
            return f"未知命令: /{command}"

        lines = ["## 可用 Slash Commands", ""]
        for name, cmd in self.commands.items():
            lines.append(f"- `/{name}` - {cmd.description}")
        return "\n".join(lines)


_command_manager = SlashCommandManager()


def parse_slash_command(input_str: str) -> Optional[Dict[str, Any]]:
    """解析 slash 命令"""
    return _command_manager.parse(input_str)


def get_command_help(command: str = None) -> str:
    """获取命令帮助"""
    return _command_manager.get_help(command)
