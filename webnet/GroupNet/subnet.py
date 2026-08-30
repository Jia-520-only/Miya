"""
GroupNet - 群管理子网

直接代理 tools/ 中的群管理工具
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from webnet.tools.base import BaseTool


logger = logging.getLogger(__name__)


@dataclass
class GroupNetConfig:
    """群管理子网配置"""
    subnet_name: str = "GroupNet"
    subnet_id: str = "subnet.group"
    version: str = "1.0.0"
    onebot_client: Any = None


class GroupNet:
    """群管理子网"""

    def __init__(self, onebot_client=None):
        self.config = GroupNetConfig(onebot_client=onebot_client)
        self.tools: Dict[str, Any] = {}
        self._init_tools()
        logger.info(f"GroupNet 子网已启动，已加载 {len(self.tools)} 个工具")

    def _init_tools(self):
        """导入群管理工具"""
        from webnet.GroupNet.tools.get_member_list import GetMemberList
        from webnet.GroupNet.tools.get_member_info import GetMemberInfo
        from webnet.GroupNet.tools.find_member import FindMember
        from webnet.GroupNet.tools.filter_members import FilterMembers
        from webnet.GroupNet.tools.rank_members import RankMembers

        self.tools['get_member_list'] = GetMemberList()
        self.tools['get_member_info'] = GetMemberInfo()
        self.tools['find_member'] = FindMember()
        self.tools['filter_members'] = FilterMembers()
        self.tools['rank_members'] = RankMembers()

    async def execute_tool(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name not in self.tools:
            return f"❌ 工具不存在: {tool_name}"
        tool = self.tools[tool_name]
        from webnet.tools.base import ToolContext
        context = ToolContext(
            onebot_client=self.config.onebot_client,
            **kwargs
        )
        return await tool.execute(args, context)

    def get_tool_list(self) -> List[Dict[str, Any]]:
        return [
            {'name': name, 'config': tool.config, 'subnet': 'GroupNet'}
            for name, tool in self.tools.items()
        ]
