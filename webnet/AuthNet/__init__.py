"""
AuthNet - 鉴权子网

功能：
- 统一用户身份管理（跨平台）
- 权限检查与验证
- 会话管理
- API访问控制
"""

from .permission_core import PermissionCore
from .subnet import AuthSubnet

__all__ = ["AuthSubnet", "PermissionCore"]
