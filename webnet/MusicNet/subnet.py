"""MusicNet 子网 — 弥娅音乐工作站"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MusicSubnet:
    """弥娅 MusicNet 子网"""

    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self._init_tools()

    def _init_tools(self):
        from .midi_tools import (
            MidiWriteTool,
            MidiDiffTool,
            MidiBatchEditTool,
            MidiQueryTool,
            MidiInspectTool,
            MidiPlayTool,
            MidiRenderTool,
        )

        self.register(MidiWriteTool())
        self.register(MidiDiffTool())
        self.register(MidiBatchEditTool())
        self.register(MidiQueryTool())
        self.register(MidiInspectTool())
        self.register(MidiPlayTool())
        self.register(MidiRenderTool())

        logger.info(f"MusicNet \u5df2\u52a0\u8f7d {len(self.tools)} \u4e2a MIDI \u5de5\u5177")

    def register(self, tool):
        name = tool.config.get("name", "")
        self.tools[name] = tool

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [tool.config for tool in self.tools.values()]

    def get_tool_names(self) -> List[str]:
        return list(self.tools.keys())

    async def execute_tool(self, name: str, args: Dict[str, Any], context=None) -> str:
        tool = self.tools.get(name)
        if not tool:
            return f"\u274c \u672a\u77e5\u5de5\u5177: {name}"
        try:
            return await tool.execute(args, context)
        except Exception as e:
            logger.error(f"\u6267\u884c MIDI \u5de5\u5177 {name} \u5931\u8d25: {e}", exc_info=True)
            return f"\u274c MIDI\u5de5\u5177\u6267\u884c\u5931\u8d25: {e}"

    def health_check(self) -> bool:
        return len(self.tools) > 0
