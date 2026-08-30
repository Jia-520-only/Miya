"""
TRPG 子网基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from webnet.tools.base import BaseTool, ToolContext
from core.mlink import MLink


class TRPGNet:
    """TRPG 跑团子网"""

    def __init__(self, mlink: MLink, ai_client=None, memory_engine=None):
        self.mlink = mlink
        self.ai_client = ai_client
        self.memory_engine = memory_engine
        self.tools = self._load_tools()

    def _load_tools(self) -> Dict[str, BaseTool]:
        """加载 TRPG 工具"""
        from .tools.roll_dice import RollDice
        from .tools.roll_secret import RollSecret
        from .tools.create_pc import CreatePC
        from .tools.show_pc import ShowPC
        from .tools.start_trpg import StartTRPG
        from .tools.update_pc import UpdatePC, DeletePC
        from .tools.skill_check import SkillCheck
        from .tools.kp_command import KPCommand
        from .tools.combat import Attack, CombatLog
        from .tools.rest import Rest
        from .tools.initiative_command import (StartCombat, AddInitiative,
                                                 NextTurn, ShowInitiative, EndCombat)

        return {
            'roll_dice': RollDice(),
            'roll_secret': RollSecret(),
            'create_pc': CreatePC(),
            'show_pc': ShowPC(),
            'start_trpg': StartTRPG(),
            'update_pc': UpdatePC(),
            'delete_pc': DeletePC(),
            'skill_check': SkillCheck(),
            'kp_command': KPCommand(),
            'attack': Attack(),
            'combat_log': CombatLog(),
            'rest': Rest(),
            'start_combat': StartCombat(),
            'add_initiative': AddInitiative(),
            'next_turn': NextTurn(),
            'show_initiative': ShowInitiative(),
            'end_combat': EndCombat()
        }

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """获取所有工具"""
        return self.tools

    async def handle_message(self, context: ToolContext, message: str) -> Optional[str]:
        """处理消息"""
        # 可以在这里添加消息预处理逻辑
        return None
