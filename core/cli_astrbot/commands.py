"""CLI Commands"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class CLICommand:
    name: str
    description: str
    handler: Callable
    args: List[str] = None


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CLICommand] = {}

    def register(self, cmd: CLICommand):
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> CLICommand:
        return self._commands.get(name)

    def list_commands(self) -> List[str]:
        return list(self._commands.keys())


class CLIRunner:
    def __init__(self):
        self.registry = CommandRegistry()

    async def run(self, cmd_name: str, args: List[str] = None) -> Any:
        cmd = self.registry.get(cmd_name)
        if not cmd:
            return f"命令不存在: {cmd_name}"
        return await cmd.handler(args or [])

    def add_command(self, name: str, description: str, handler: Callable):
        self.registry.register(CLICommand(name, description, handler))
