"""
系统配置加载器
统一加载 system_constants.json 和 api_endpoints.json
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_config_cache: Dict[str, Any] = {}


def _get_config_dir() -> Path:
    """获取配置目录"""
    return Path(__file__).parent.parent / "config"


def _load_json_config(config_name: str) -> Dict[str, Any]:
    """加载JSON配置文件"""
    if config_name in _config_cache:
        return _config_cache[config_name]

    config_path = _get_config_dir() / f"{config_name}.json"

    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                _config_cache[config_name] = json.load(f)
                logger.info(f"加载配置 {config_name} 成功")
                return _config_cache[config_name]
        else:
            logger.warning(f"配置文件不存在: {config_path}")
            return {}
    except Exception as e:
        logger.error(f"加载配置 {config_name} 失败: {e}")
        return {}


def get_system_constants() -> Dict[str, Any]:
    """获取系统常量配置"""
    return _load_json_config("system_constants")


def get_api_endpoints() -> Dict[str, Any]:
    """获取API端点配置"""
    return _load_json_config("api_endpoints")


def get_constant(category: str, key: str, default: Any = None) -> Any:
    """获取指定常量值"""
    config = get_system_constants()
    return config.get(category, {}).get(key, default)


def get_api_url(service: str, path: str = "") -> str:
    """获取API URL"""
    config = get_api_endpoints()
    base = (
        config.get("ai_providers", {}).get(service, {}).get("base_url")
        or config.get("web_services", {}).get(service, {}).get("base_url")
        or config.get("internal_services", {}).get(service, {}).get("base_url")
        or config.get("internal_services", {}).get(service, {}).get("url", "")
    )
    return f"{base}{path}" if path else base


def reload_configs():
    """重新加载所有配置"""
    global _config_cache
    _config_cache = {}
    get_system_constants()
    get_api_endpoints()
    logger.info("配置已重新加载")
