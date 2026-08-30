"""
列出权限工具
"""

import json
import logging
from typing import Dict, Any

from webnet.tools.base import BaseTool
from ..permission_core import PermissionCore

logger = logging.getLogger(__name__)


class ListPermissionsTool(BaseTool):
    """列出权限工具"""

    def __init__(self):
        super().__init__()
        self.permission_core = PermissionCore()
        
        self._config = {
            'name': 'list_permissions',
            'description': '列出用户的所有权限详情。包括权限组、直接权限和有效权限。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'string',
                        'description': '用户ID（格式: platform_id，如: qq_123, web_user456）'
                    }
                },
                'required': ['user_id']
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行权限列表查询"""
        try:
            user_id = args.get('user_id')
            
            if not user_id:
                return json.dumps({
                    "success": False,
                    "error": "缺少user_id参数"
                }, ensure_ascii=False)
            
            # 查询权限详情
            result = self.permission_core.list_user_permissions(user_id)
            
            if "error" in result:
                return json.dumps({
                    "success": False,
                    "error": result["error"]
                }, ensure_ascii=False)
            
            return json.dumps({
                "success": True,
                "permissions": result
            }, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"列出权限失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
