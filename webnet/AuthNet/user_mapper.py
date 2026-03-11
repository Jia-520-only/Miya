"""
用户身份映射 - 跨平台统一ID管理

功能：
- 将不同平台的用户ID统一格式化为: platform_id
- 支持QQ、Web、Desktop、Terminal等平台
- 提供用户创建、查询、映射功能
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class UserMapper:
    """用户身份映射器"""
    
    def __init__(self):
        self.users_file = Path("data/auth/users.json")
    
    def load_users(self) -> Dict[str, Any]:
        """加载用户数据"""
        if self.users_file.exists():
            import json
            return json.loads(self.users_file.read_text(encoding='utf-8', errors='replace'))
        return {"users": []}
    
    def save_users(self, users_data: Dict[str, Any]):
        """保存用户数据"""
        import json
        self.users_file.write_text(
            json.dumps(users_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
    
    def generate_user_id(self, platform: str, original_id: str) -> str:
        """
        生成统一格式的用户ID
        
        Args:
            platform: 平台名称 (qq, web, desktop, terminal)
            original_id: 平台原始ID
        
        Returns:
            统一格式ID: platform_original_id
        """
        return f"{platform}_{original_id}"
    
    def ensure_user_exists(
        self,
        platform: str,
        original_id: str,
        username: Optional[str] = None,
        permission_groups: Optional[list] = None
    ) -> str:
        """
        确保用户存在，如果不存在则创建
        
        Args:
            platform: 平台名称
            original_id: 平台原始ID
            username: 用户名（可选）
            permission_groups: 权限组列表（可选）
        
        Returns:
            统一格式用户ID
        """
        user_id = self.generate_user_id(platform, original_id)
        
        users_data = self.load_users()
        
        # 检查用户是否已存在
        for user in users_data.get("users", []):
            if user.get("user_id") == user_id:
                return user_id
        
        # 创建新用户
        new_user = {
            "user_id": user_id,
            "username": username or f"{platform}_user_{original_id}",
            "platform": platform,
            "original_id": original_id,
            "permission_groups": permission_groups or ["Default"],
            "permissions": [],
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        if "users" not in users_data:
            users_data["users"] = []
        
        users_data["users"].append(new_user)
        self.save_users(users_data)
        
        return user_id
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息
        
        Args:
            user_id: 统一格式用户ID
        
        Returns:
            用户信息或None
        """
        users_data = self.load_users()
        
        for user in users_data.get("users", []):
            if user.get("user_id") == user_id:
                return user
        
        return None
    
    def get_platform_user(self, platform: str, original_id: str) -> Optional[Dict[str, Any]]:
        """
        根据平台和原始ID获取用户信息
        
        Args:
            platform: 平台名称
            original_id: 平台原始ID
        
        Returns:
            用户信息或None
        """
        user_id = self.generate_user_id(platform, original_id)
        return self.get_user_info(user_id)
    
    def update_user_login(self, user_id: str):
        """
        更新用户最后登录时间
        
        Args:
            user_id: 用户ID
        """
        users_data = self.load_users()
        
        for user in users_data.get("users", []):
            if user.get("user_id") == user_id:
                user["last_login"] = datetime.now().isoformat()
                self.save_users(users_data)
                break
    
    def get_all_platform_users(self, platform: str) -> list:
        """
        获取某个平台的所有用户
        
        Args:
            platform: 平台名称
        
        Returns:
            用户列表
        """
        users_data = self.load_users()
        
        return [
            user for user in users_data.get("users", [])
            if user.get("platform") == platform
        ]
