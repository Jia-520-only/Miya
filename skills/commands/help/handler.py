"""
/help 命令 — 从 config 读取用户消息
"""

from __future__ import annotations

import logging
from typing import Any, List

from config.config_utils import get_command_message

logger = logging.getLogger(__name__)


async def execute(args: List[str], context: Any) -> str:
    try:
        from core.command_system import get_command_registry

        registry = get_command_registry()
    except Exception:
        return get_command_message("system_not_ready")

    command_name = args[0] if args else ""
    permission = "public"
    if context.check_permission("superadmin"):
        permission = "superadmin"
    elif context.check_permission("admin"):
        permission = "admin"

    return registry.get_help(command_name, permission)
