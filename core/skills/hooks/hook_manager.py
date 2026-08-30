"""
Hooks 系统 - 事件钩子
支持 PreToolUse, PostToolUse, SessionStart, SessionStop 等事件
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Miya.Hooks")


class EventType(Enum):
    PRE_TOOL_USE = "PreToolUse"  # 工具执行前
    POST_TOOL_USE = "PostToolUse"  # 工具执行后
    SESSION_START = "SessionStart"  # 会话开始
    SESSION_STOP = "SessionStop"  # 会话停止
    STOP = "stop"  # 停止尝试


class ActionType(Enum):
    WARN = "warn"  # 警告但允许执行
    BLOCK = "block"  # 阻止执行
    ALLOW = "allow"  # 允许执行


@dataclass
class HookRule:
    name: str
    enabled: bool = True
    event: str = "all"
    pattern: str = ""
    action: ActionType = ActionType.WARN
    message: str = ""
    conditions: List[Dict] = field(default_factory=list)


class HookManager:
    """Hook 管理器"""

    def __init__(self):
        self.rules: List[HookRule] = []
        self._load_default_rules()
        self._load_project_rules()

    def _load_default_rules(self):
        """加载默认安全规则"""
        self.rules = [
            HookRule(
                name="block-dangerous-rm",
                event="bash",
                pattern=r"rm\s+-rf\s+/|rm\s+-rf\s+\*",
                action=ActionType.BLOCK,
                message="🛑 危险命令！此操作可能导致数据丢失",
            ),
            HookRule(
                name="warn-dangerous-commands",
                event="bash",
                pattern=r"dd\s+if=|mkfs|format",
                action=ActionType.WARN,
                message="⚠️ 危险命令！此操作可能破坏数据",
            ),
            HookRule(
                name="warn-sensitive-files",
                event="file",
                pattern=r"\.env$|credentials|secrets",
                action=ActionType.WARN,
                message="🔐 检测到敏感文件修改，请确保不提交硬编码的凭证",
            ),
            HookRule(
                name="warn-hardcoded-secrets",
                event="file",
                pattern=r"(API_KEY|SECRET|TOKEN|PASSWORD)\s*=\s*['\"]",
                action=ActionType.WARN,
                message="🔐 检测到可能的硬编码密钥，请使用环境变量",
            ),
        ]

    def _load_project_rules(self):
        """加载项目级规则"""
        hook_dir = Path(".") / ".miya" / "hooks"
        if not hook_dir.exists():
            return

        for rule_file in hook_dir.glob("*.md"):
            try:
                rule = self._parse_rule_file(rule_file)
                if rule:
                    self.rules.append(rule)
                    logger.info(f"[Hooks] 加载规则: {rule.name}")
            except Exception as e:
                logger.warning(f"[Hooks] 加载规则失败 {rule_file}: {e}")

    def _parse_rule_file(self, file_path: Path) -> Optional[HookRule]:
        """解析规则文件"""
        content = file_path.read_text(encoding="utf-8")

        frontmatter = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                fm_text = content[3:end].strip()
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        frontmatter[key.strip()] = val.strip().strip('"')

        return HookRule(
            name=frontmatter.get("name", file_path.stem),
            enabled=frontmatter.get("enabled", "true").lower() == "true",
            event=frontmatter.get("event", "all"),
            pattern=frontmatter.get("pattern", ""),
            action=ActionType.BLOCK if frontmatter.get("action") == "block" else ActionType.WARN,
            message=content[content.find("---", 3) + 3 :] if "---" in content[3:] else "",
        )

    def check(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """检查规则匹配

        Returns:
            {"allowed": bool, "message": str, "rule": HookRule}
        """
        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.event != "all" and rule.event != event:
                continue

            matched = False

            if rule.pattern:
                for field_name in ["command", "file_path", "new_text", "user_prompt"]:
                    if field_name in context and re.search(rule.pattern, str(context[field_name])):
                        matched = True
                        break

            if matched:
                return {
                    "allowed": rule.action != ActionType.BLOCK,
                    "message": rule.message or f"规则 {rule.name} 触发",
                    "rule": rule,
                }

        return {"allowed": True, "message": "", "rule": None}

    def add_rule(self, rule: HookRule):
        """添加规则"""
        self.rules.append(rule)

    def remove_rule(self, name: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.name != name]

    def list_rules(self) -> List[Dict]:
        """列出所有规则"""
        return [
            {
                "name": r.name,
                "enabled": r.enabled,
                "event": r.event,
                "action": r.action.value,
            }
            for r in self.rules
        ]

    def create_rule_file(
        self,
        name: str,
        event: str,
        pattern: str,
        action: str,
        message: str,
        path: str = ".miya/hooks",
    ):
        """创建规则文件"""
        hook_dir = Path(path)
        hook_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{name}.md"
        content = f"""---
name: {name}
enabled: true
event: {event}
pattern: {pattern}
action: {action}
---

{message}
"""

        (hook_dir / filename).write_text(content, encoding="utf-8")


_hook_manager = HookManager()


def check_hook(event: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """检查 hook"""
    return _hook_manager.check(event, context)


def add_hook_rule(name: str, event: str, pattern: str, action: str = "warn", message: str = ""):
    """添加 hook 规则"""
    rule = HookRule(
        name=name,
        event=event,
        pattern=pattern,
        action=ActionType.BLOCK if action == "block" else ActionType.WARN,
        message=message,
    )
    _hook_manager.add_rule(rule)


def list_hooks() -> List[Dict]:
    """列出所有 hooks"""
    return _hook_manager.list_rules()
