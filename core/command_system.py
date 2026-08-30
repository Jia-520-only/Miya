"""
弥娅统一斜杠命令系统 — 所有用户消息从 config 读取
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.config_utils import get_command_message, get_text

logger = logging.getLogger(__name__)

COMMANDS_DIR = Path(__file__).resolve().parent.parent / "skills" / "commands"


@dataclass
class CommandContext:
    group_id: int = 0
    sender_id: int = 0
    user_id: str = ""
    args: List[str] = field(default_factory=list)
    raw_text: str = ""
    scope: str = "group"
    subcommand: str = ""
    onebot_client: Any = None
    send_group_message: Any = None
    send_private_message: Any = None
    cognitive_service: Any = None
    knowledge_store: Any = None
    config: Any = None
    ai_client: Any = None
    faq_storage: Any = None
    history_manager: Any = None
    bot_qq: int = 0
    superadmin_qq: int = 0
    admin_qq_list: List[int] = field(default_factory=list)

    def check_permission(self, required: str) -> bool:
        if required == "public":
            return True
        if required == "superadmin":
            return self.sender_id == self.superadmin_qq
        if required == "admin":
            return self.sender_id == self.superadmin_qq or self.sender_id in self.admin_qq_list
        return False


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, Dict[str, Any]] = {}
        self._rate_limits: Dict[str, Dict[str, float]] = {}
        self._loaded = False

    def load_commands(self) -> int:
        self._commands.clear()
        if not COMMANDS_DIR.exists():
            logger.warning(f"[Commands] 命令目录不存在: {COMMANDS_DIR}")
            return 0

        for cmd_dir in sorted(COMMANDS_DIR.iterdir()):
            if not cmd_dir.is_dir() or cmd_dir.name.startswith("_"):
                continue
            config_path = cmd_dir / "config.json"
            if not config_path.exists():
                continue
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                name = config.get("name", cmd_dir.name)
                self._commands[name] = {
                    "name": name,
                    "description": config.get("description", ""),
                    "permission": config.get("permission", "public"),
                    "allow_in_private": config.get("allow_in_private", False),
                    "aliases": config.get("aliases", []),
                    "rate_limit": config.get("rate_limit", {}),
                    "subcommands": config.get("subcommands", {}),
                    "inference": config.get("inference", {}),
                    "show_in_help": config.get("show_in_help", True),
                    "order": config.get("order", 100),
                    "handler_path": str(cmd_dir / "handler.py"),
                    "readme_path": str(cmd_dir / "README.md"),
                }
                handler_path = self._commands[name].get("handler_path")
                if handler_path and Path(handler_path).exists():
                    try:
                        spec = importlib.util.spec_from_file_location(f"miya_cmd_{name}", handler_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._commands[name]["handler"] = module.execute
                    except Exception as e:
                        logger.warning(f"[Commands] 加载 handler 失败: {name}: {e}")
            except Exception as e:
                logger.warning(f"[Commands] 加载命令失败 {cmd_dir.name}: {e}")

        self._loaded = True
        logger.info(f"[Commands] 已加载 {len(self._commands)} 个命令")
        return len(self._commands)

    def match(self, text: str) -> Optional[tuple[str, str, List[str]]]:
        if not self._loaded:
            self.load_commands()
        text = text.strip()
        if not text.startswith("/"):
            return None
        content = text[1:].strip()
        parts = content.split()
        if not parts:
            return None
        first = parts[0].lower()
        rest = parts[1:]
        for name, cmd in self._commands.items():
            if first == name.lower() or first in [a.lower() for a in cmd.get("aliases", [])]:
                subcommand = ""
                args = rest
                if rest and cmd.get("subcommands"):
                    sub = rest[0].lower()
                    if sub in cmd["subcommands"]:
                        subcommand = sub
                        args = rest[1:]
                    elif cmd.get("inference"):
                        inference = cmd["inference"]
                        rules = inference.get("rules", [])
                        import re

                        for rule in rules:
                            if re.match(rule.get("pattern", ""), rest[0]):
                                subcommand = rule.get("subcommand", "")
                                break
                        if not subcommand:
                            subcommand = inference.get("fallback", "")
                return (name, subcommand, args)
        return None

    def check_rate_limit(self, command_name: str, user_id: str, permission: str) -> tuple[bool, float]:
        cmd = self._commands.get(command_name, {})
        rate_limit = cmd.get("rate_limit", {})
        cooldown = rate_limit.get(permission, rate_limit.get("user", 0))
        if cooldown <= 0:
            return True, 0
        now = time.time()
        key = f"{command_name}:{user_id}"
        if key not in self._rate_limits:
            self._rate_limits[key] = {}
        last_used = self._rate_limits[key].get("last", 0)
        elapsed = now - last_used
        if elapsed < cooldown:
            return False, cooldown - elapsed
        self._rate_limits[key]["last"] = now
        return True, 0

    async def execute(self, command_name: str, subcommand: str, args: List[str], ctx: CommandContext) -> Optional[str]:
        cmd = self._commands.get(command_name)
        if not cmd:
            return None
        handler = cmd.get("handler")
        if not handler:
            handler_path = cmd.get("handler_path", "")
            if handler_path and Path(handler_path).exists():
                try:
                    spec = importlib.util.spec_from_file_location(f"miya_cmd_{command_name}", handler_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    handler = module.execute
                    cmd["handler"] = handler
                except Exception as e:
                    return get_command_message("load_failed", error=str(e))
            else:
                return get_command_message("not_implemented", name=command_name)
        ctx.subcommand = subcommand
        ctx.args = args
        ctx.raw_text = f"/{command_name} {subcommand} {' '.join(args)}".strip()
        try:
            return await handler(args, ctx)
        except Exception as e:
            logger.error(f"[Commands] 执行命令失败 /{command_name}: {e}", exc_info=True)
            return get_command_message("execute_failed", error=str(e)[:100])

    def get_help(self, command_name: str = "", permission: str = "public") -> str:
        if not self._loaded:
            self.load_commands()
        if command_name:
            cmd = self._commands.get(command_name)
            if not cmd:
                return get_command_message("help_unknown_command", name=command_name)
            lines = [get_command_message("help_header", name=command_name, description=cmd.get("description", ""))]
            aliases = cmd.get("aliases", [])
            if aliases:
                lines.append(get_command_message("help_aliases", aliases=", ".join("/" + a for a in aliases)))
            lines.append(get_command_message("help_permission", permission=cmd.get("permission", "public")))
            subcommands = cmd.get("subcommands", {})
            if subcommands:
                lines.append(get_command_message("help_subcommands"))
                for sname, sinfo in subcommands.items():
                    lines.append(f"  {sname}: {sinfo.get('description', '')}")
            return "\n".join(lines)

        cmds = sorted(
            [c for c in self._commands.values() if c.get("show_in_help", True)],
            key=lambda x: x.get("order", 100),
        )
        visible = []
        for c in cmds:
            perm = c.get("permission", "public")
            if perm == "superadmin" and permission != "superadmin":
                continue
            if perm == "admin" and permission not in ("admin", "superadmin"):
                continue
            visible.append(c)
        lines = [get_command_message("help_list_header")]
        for c in visible:
            aliases = c.get("aliases", [])
            alias_str = f" ({', '.join('/' + a for a in aliases)})" if aliases else ""
            lines.append(f"  /{c['name']}{alias_str} - {c.get('description', '')[:60]}")

        # 弥娅专属命令（由决策层直接处理）— 从配置读取，保证 /help 输出与实际命令一致
        builtin_items = get_text("builtin_commands", "items", default=[]) or []
        if builtin_items:
            lines.append("")
            lines.append(get_command_message("help_builtin_header"))
            for item in builtin_items:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    get_command_message(
                        "help_builtin_item",
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                    )
                )

        group_hint = get_text("builtin_commands", "group_hint", default="")
        if group_hint:
            lines.append("")
            lines.append(get_command_message("help_group_hint", hint=group_hint))
        return "\n".join(lines)

    def get_command_names(self) -> List[str]:
        if not self._loaded:
            self.load_commands()
        return list(self._commands.keys())


_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry
