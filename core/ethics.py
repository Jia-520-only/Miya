"""
行为底线与权限
定义弥娅的行为边界和安全约束
"""
from typing import List, Set, Dict


class Ethics:
    """伦理约束系统"""

    def __init__(self):
        # 硬性禁止事项
        self.forbidden_actions = {
            'harm_user',
            'illegal_content',
            'discrimination',
            'privacy_breach',
            'malicious_code'
        }

        # 需要权限的操作
        self.permission_required = {
            'system_modification',
            'data_export',
            'external_api_call'
        }

        # 权限级别
        self.permission_levels = {
            'guest': set(),
            'user': {'external_api_call'},
            'admin': self.permission_required.copy()
        }

    def is_allowed(self, action: str, user_level: str = 'user') -> bool:
        """检查动作是否被允许"""
        # 检查是否在禁止列表中
        if action in self.forbidden_actions:
            return False

        # 检查是否需要权限
        if action in self.permission_required:
            return action in self.permission_levels.get(user_level, set())

        return True

    def add_forbidden(self, action: str) -> None:
        """添加禁止动作"""
        self.forbidden_actions.add(action)

    def grant_permission(self, action: str, user_level: str) -> bool:
        """授予权限"""
        if user_level not in self.permission_levels:
            return False

        self.permission_levels[user_level].add(action)
        return True

    def get_ethics_report(self) -> Dict:
        """获取伦理报告"""
        return {
            'forbidden_count': len(self.forbidden_actions),
            'protected_actions': len(self.permission_required),
            'permission_levels': {
                level: len(permissions)
                for level, permissions in self.permission_levels.items()
            }
        }
