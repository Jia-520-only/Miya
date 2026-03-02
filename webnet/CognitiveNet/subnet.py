"""
CognitiveNet - 认知子网

直接代理 tools/ 中的认知工具
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from webnet.tools.base import BaseTool


logger = logging.getLogger(__name__)


@dataclass
class CognitiveNetConfig:
    """认知子网配置"""
    subnet_name: str = "CognitiveNet"
    subnet_id: str = "subnet.cognitive"
    version: str = "1.0.0"
    onebot_client: Any = None


class CognitiveNet:
    """认知子网"""

    def __init__(self, onebot_client=None):
        self.config = CognitiveNetConfig(onebot_client=onebot_client)
        self.tools: Dict[str, Any] = {}
        self._init_tools()
        logger.info(f"CognitiveNet 子网已启动，已加载 {len(self.tools)} 个工具")

    def _init_tools(self):
        """导入认知工具"""
        from tools.tools.get_profile import GetProfile
        from tools.tools.search_profiles import SearchProfiles
        from tools.tools.search_events import SearchEvents

        self.tools['get_profile'] = GetProfile()
        self.tools['search_profiles'] = SearchProfiles()
        self.tools['search_events'] = SearchEvents()

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
            {'name': name, 'config': tool.config, 'subnet': 'CognitiveNet'}
            for name, tool in self.tools.items()
        ]
