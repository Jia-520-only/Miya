"""
MIYA Provider 配置

从 model_pool_manager 获取配置
"""

from typing import Any, Dict

from core.model_pool_manager import get_model_pool


def get_default_providers() -> Dict[str, Dict[str, Any]]:
    """获取默认提供商配置"""
    pool = get_model_pool()
    models = pool.get_enabled()

    providers = {}
    for m in models:
        providers[m.id] = {
            "type": m.type,
            "model": m.name,
            "provider": m.provider,
            "api_key": pool.get_api_key(m.id),  # 可以获取密钥
            "api_base": m.base_url,
            "enabled": m.enabled,
            "priority": m.priority,
            "description": "",
        }
    return providers


__all__ = ["get_default_providers"]
