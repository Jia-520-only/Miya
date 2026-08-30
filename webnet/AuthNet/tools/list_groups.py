"""
列出权限组工具
"""

import json
import logging
from typing import Dict, Any

from webnet.tools.base import BaseTool
from ..permission_core import PermissionCore

logger = logging.getLogger(__name__)


class ListGroupsTool(BaseTool):
    """列出权限组工具"""

    def __init__(self):
        super().__init__()
        self.permission_core = PermissionCore()
        
        self._config = {
            'name': 'list_groups',
            'description': '列出所有可用的权限组及其权限。',
            'parameters': {
                'type': 'object',
                'properties': {}
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行权限组列表查询"""
        try:
            # 加载权限组数据
            groups_data = self.permission_core.load_groups()
            groups = groups_data.get("groups", {})
            
            # 格式化输出
            result = {}
            for group_name, group_info in groups.items():
                result[group_name] = {
                    "description": group_info.get("description", ""),
                    "permissions": group_info.get("permissions", [])
                }
            
            return json.dumps({
                "success": True,
                "groups": result
            }, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"列出权限组失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
