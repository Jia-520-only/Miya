"""
Miya 访问控制模块 - 安全加强
================================

该模块提供基于API密钥的访问控制功能。
支持基于角色的访问控制(RBAC)和权限管理。

设计目标:
- API密钥认证和授权
- 基于角色的权限管理
- 请求限流和防护
- 安全审计和日志记录
"""

import asyncio
import hashlib
import logging
import secrets
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class Role(Enum):
    """角色枚举"""

    ADMIN = "admin"  # 管理员: 所有权限
    USER = "user"  # 用户: 基本权限
    GUEST = "guest"  # 访客: 只读权限
    SYSTEM = "system"  # 系统: 系统级权限


class Permission(Enum):
    """权限枚举"""

    # 配置管理
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    CONFIG_DELETE = "config:delete"

    # API管理
    API_READ = "api:read"
    API_WRITE = "api:write"

    # IoT管理
    IOT_READ = "iot:read"
    IOT_WRITE = "iot:write"
    IOT_CONTROL = "iot:control"

    # 系统管理
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"

    # 数据访问
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"


@dataclass
class APIKey:
    """API密钥"""

    key_id: str
    key_hash: str
    name: str
    role: Role
    permissions: Set[Permission]
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    rate_limit: int = 1000  # 每小时请求数限制
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessLog:
    """访问日志"""

    key_id: str
    endpoint: str
    method: str
    timestamp: datetime
    status_code: int
    response_time_ms: float
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class APIKeyManager:
    """API密钥管理器"""

    # 角色默认权限
    ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
        Role.ADMIN: {p for p in Permission},  # 管理员拥有所有权限
        Role.USER: {
            Permission.CONFIG_READ,
            Permission.API_READ,
            Permission.IOT_READ,
            Permission.DATA_READ,
            Permission.DATA_WRITE,
        },
        Role.GUEST: {Permission.CONFIG_READ, Permission.API_READ, Permission.IOT_READ, Permission.DATA_READ},
        Role.SYSTEM: {
            Permission.SYSTEM_ADMIN,
            Permission.SYSTEM_MONITOR,
            Permission.CONFIG_READ,
            Permission.CONFIG_WRITE,
            Permission.API_READ,
            Permission.API_WRITE,
        },
    }

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or "data/api_keys.json"
        self._api_keys: Dict[str, APIKey] = {}
        self._access_logs: List[AccessLog] = []
        self._rate_limit_counters: Dict[str, List[datetime]] = defaultdict(list)

        # 加载现有密钥
        self._load_keys()

        logger.info(f"[访问控制] 初始化完成, 存储路径={self.storage_path}")

    def _load_keys(self):
        """从存储加载API密钥"""
        try:
            import json
            from pathlib import Path

            storage_file = Path(self.storage_path)
            if storage_file.exists():
                with open(storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for key_data in data.get("keys", []):
                    api_key = APIKey(
                        key_id=key_data["key_id"],
                        key_hash=key_data["key_hash"],
                        name=key_data["name"],
                        role=Role(key_data["role"]),
                        permissions={Permission(p) for p in key_data["permissions"]},
                        created_at=datetime.fromisoformat(key_data["created_at"]),
                        expires_at=datetime.fromisoformat(key_data["expires_at"])
                        if key_data.get("expires_at")
                        else None,
                        is_active=key_data["is_active"],
                        rate_limit=key_data.get("rate_limit", 1000),
                        metadata=key_data.get("metadata", {}),
                    )
                    self._api_keys[api_key.key_id] = api_key

                logger.info(f"[访问控制] 加载了{len(self._api_keys)}个API密钥")

        except Exception as e:
            logger.error(f"[访问控制] 加载API密钥失败: {e}")

    def _save_keys(self):
        """保存API密钥到存储"""
        try:
            import json
            from pathlib import Path

            storage_file = Path(self.storage_path)
            storage_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "keys": [
                    {
                        "key_id": key.key_id,
                        "key_hash": key.key_hash,
                        "name": key.name,
                        "role": key.role.value,
                        "permissions": [p.value for p in key.permissions],
                        "created_at": key.created_at.isoformat(),
                        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                        "is_active": key.is_active,
                        "rate_limit": key.rate_limit,
                        "metadata": key.metadata,
                    }
                    for key in self._api_keys.values()
                ],
                "updated_at": datetime.now().isoformat(),
            }

            with open(storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("[访问控制] API密钥已保存")

        except Exception as e:
            logger.error(f"[访问控制] 保存API密钥失败: {e}")

    def generate_key(
        self,
        name: str,
        role: Role = Role.USER,
        permissions: Optional[Set[Permission]] = None,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000,
    ) -> Tuple[str, str]:
        """生成API密钥"""
        # 生成密钥ID和实际密钥
        key_id = secrets.token_hex(16)
        secret_key = secrets.token_urlsafe(32)

        # 计算密钥哈希（加盐 SHA-256）
        salt = secrets.token_bytes(16)
        key_hash = hashlib.sha256(salt + secret_key.encode()).hexdigest() + ":" + salt.hex()

        # 设置权限
        if permissions is None:
            permissions = self.ROLE_PERMISSIONS.get(role, set())

        # 设置过期时间
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        # 创建API密钥对象
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            role=role,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=expires_at,
            is_active=True,
            rate_limit=rate_limit,
        )

        # 保存密钥
        self._api_keys[key_id] = api_key
        self._save_keys()

        logger.info(f"[访问控制] 生成API密钥: {name} ({key_id})")
        return key_id, secret_key

    def validate_key(self, secret_key: str) -> Optional[APIKey]:
        """验证API密钥"""
        try:
            key_hash = hashlib.sha256(secret_key.encode()).hexdigest()

            for api_key in self._api_keys.values():
                if api_key.key_hash == key_hash:
                    # 检查密钥是否激活
                    if not api_key.is_active:
                        logger.warning(f"[访问控制] API密钥已禁用: {api_key.key_id}")
                        return None

                    # 检查密钥是否过期
                    if api_key.expires_at and datetime.now() > api_key.expires_at:
                        logger.warning(f"[访问控制] API密钥已过期: {api_key.key_id}")
                        return None

                    return api_key

            return None

        except Exception as e:
            logger.error(f"[访问控制] 验证API密钥失败: {e}")
            return None

    def revoke_key(self, key_id: str) -> bool:
        """撤销API密钥"""
        if key_id in self._api_keys:
            self._api_keys[key_id].is_active = False
            self._save_keys()
            logger.info(f"[访问控制] 撤销API密钥: {key_id}")
            return True
        return False

    def delete_key(self, key_id: str) -> bool:
        """删除API密钥"""
        if key_id in self._api_keys:
            del self._api_keys[key_id]
            self._save_keys()
            logger.info(f"[访问控制] 删除API密钥: {key_id}")
            return True
        return False

    def has_permission(self, api_key: APIKey, permission: Permission) -> bool:
        """检查API密钥是否有权限"""
        return permission in api_key.permissions

    def check_rate_limit(self, key_id: str) -> bool:
        """检查速率限制"""
        if key_id not in self._api_keys:
            return False

        api_key = self._api_keys[key_id]
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # 清理过期计数
        self._rate_limit_counters[key_id] = [ts for ts in self._rate_limit_counters[key_id] if ts > hour_ago]

        # 检查是否超过限制
        if len(self._rate_limit_counters[key_id]) >= api_key.rate_limit:
            logger.warning(f"[访问控制] 速率限制触发: {key_id}")
            return False

        # 记录请求
        self._rate_limit_counters[key_id].append(now)
        return True

    def log_access(
        self,
        key_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """记录访问日志"""
        log = AccessLog(
            key_id=key_id,
            endpoint=endpoint,
            method=method,
            timestamp=datetime.now(),
            status_code=status_code,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._access_logs.append(log)

        # 保持日志大小合理(最多保留10000条)
        if len(self._access_logs) > 10000:
            self._access_logs = self._access_logs[-10000:]

    def get_access_logs(self, key_id: Optional[str] = None, limit: int = 100) -> List[AccessLog]:
        """获取访问日志"""
        logs = self._access_logs

        if key_id:
            logs = [log for log in logs if log.key_id == key_id]

        return logs[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_requests = len(self._access_logs)
        successful_requests = sum(1 for log in self._access_logs if log.status_code < 400)

        # 平均响应时间
        if total_requests > 0:
            avg_response_time = sum(log.response_time_ms for log in self._access_logs) / total_requests
        else:
            avg_response_time = 0.0

        # 每个密钥的请求计数
        key_requests = defaultdict(int)
        for log in self._access_logs:
            key_requests[log.key_id] += 1

        return {
            "total_keys": len(self._api_keys),
            "active_keys": sum(1 for k in self._api_keys.values() if k.is_active),
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "avg_response_time_ms": avg_response_time,
            "key_requests": dict(key_requests),
        }

    def list_keys(self) -> List[Dict[str, Any]]:
        """列出所有API密钥(不含敏感信息)"""
        return [
            {
                "key_id": key.key_id,
                "name": key.name,
                "role": key.role.value,
                "permissions": [p.value for p in key.permissions],
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "is_active": key.is_active,
                "rate_limit": key.rate_limit,
            }
            for key in self._api_keys.values()
        ]


def require_permission(permission: Permission):
    """权限检查装饰器"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 从kwargs获取API密钥
            api_key = kwargs.get("api_key")
            if not api_key:
                raise PermissionError("需要API密钥认证")

            # 检查权限
            from core.access_control import get_global_key_manager

            key_manager = get_global_key_manager()
            if not key_manager.has_permission(api_key, permission):
                raise PermissionError(f"缺少权限: {permission.value}")

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 从kwargs获取API密钥
            api_key = kwargs.get("api_key")
            if not api_key:
                raise PermissionError("需要API密钥认证")

            # 检查权限
            from core.access_control import get_global_key_manager

            key_manager = get_global_key_manager()
            if not key_manager.has_permission(api_key, permission):
                raise PermissionError(f"缺少权限: {permission.value}")

            return func(*args, **kwargs)

        # 根据函数类型返回包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def check_rate_limit():
    """速率限制检查装饰器"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 从kwargs获取API密钥
            api_key = kwargs.get("api_key")
            if not api_key:
                raise PermissionError("需要API密钥认证")

            # 检查速率限制
            from core.access_control import get_global_key_manager

            key_manager = get_global_key_manager()
            if not key_manager.check_rate_limit(api_key.key_id):
                raise PermissionError("超过速率限制")

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 从kwargs获取API密钥
            api_key = kwargs.get("api_key")
            if not api_key:
                raise PermissionError("需要API密钥认证")

            # 检查速率限制
            from core.access_control import get_global_key_manager

            key_manager = get_global_key_manager()
            if not key_manager.check_rate_limit(api_key.key_id):
                raise PermissionError("超过速率限制")

            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 全局API密钥管理器
_global_key_manager: Optional[APIKeyManager] = None


def get_global_key_manager() -> APIKeyManager:
    """获取全局API密钥管理器"""
    global _global_key_manager
    if _global_key_manager is None:
        _global_key_manager = APIKeyManager()
    return _global_key_manager


def set_global_key_manager(manager: APIKeyManager):
    """设置全局API密钥管理器"""
    global _global_key_manager
    _global_key_manager = manager


# 示例使用
if __name__ == "__main__":
    # 创建API密钥管理器
    manager = APIKeyManager()

    # 生成API密钥
    key_id, secret_key = manager.generate_key(name="Test Key", role=Role.USER, expires_in_days=30)
    print(f"生成的密钥: {secret_key}")

    # 验证密钥
    api_key = manager.validate_key(secret_key)
    if api_key:
        print(f"验证成功: {api_key.name}")

        # 检查权限
        has_read = manager.has_permission(api_key, Permission.CONFIG_READ)
        print(f"有读取配置权限: {has_read}")

        # 检查速率限制
        for i in range(10):
            allowed = manager.check_rate_limit(key_id)
            print(f"请求 {i + 1}: {'允许' if allowed else '拒绝'}")

        # 记录访问
        manager.log_access(key_id=key_id, endpoint="/api/config", method="GET", status_code=200, response_time_ms=50.5)

        # 获取统计
        stats = manager.get_stats()
        print(f"统计: {stats}")

    # 撤销密钥
    manager.revoke_key(key_id)
    print("密钥已撤销")
