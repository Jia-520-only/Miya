"""
权限检查工具
"""

import json
import logging
from typing import Dict, Any

from webnet.tools.base import BaseTool
from ..permission_core import PermissionCore

logger = logging.getLogger(__name__)


class CheckPermissionTool(BaseTool):
    """检查权限工具"""

    def __init__(self):
        super().__init__()
        self.permission_core = PermissionCore()
        
        self._config = {
            'name': 'check_permission',
            'description': '检查用户是否有指定权限。用于在执行敏感操作前验证用户权限。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'string',
                        'description': '用户ID（格式: platform_id，如: qq_123, web_user456）'
                    },
                    'permission': {
                        'type': 'string',
                        'description': '权限节点（如: tool.web_search, agent.task.execute）'
                    },
                    'list_mode': {
                        'type': 'boolean',
                        'description': '是否返回所有权限列表（默认为False，只检查是否有权限）',
                        'default': False
                    }
                },
                'required': ['user_id', 'permission']
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行权限检查"""
        try:
            user_id = args.get('user_id')
            permission = args.get('permission')
            list_mode = args.get('list_mode', False)
            
            if not user_id or not permission:
                return json.dumps({
                    "success": False,
                    "error": "缺少user_id或permission参数"
                }, ensure_ascii=False)
            
            # 检查权限
            result = self.permission_core.check_permission(
                user_id=user_id,
                permission=permission,
                list_mode=list_mode
            )
            
            if list_mode:
                return json.dumps({
                    "success": True,
                    "result": result
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": True,
                    "allowed": result,
                    "message": "有权限" if result else "无权限"
                }, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
