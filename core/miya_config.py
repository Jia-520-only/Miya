"""
弥娅系统 - 配置管理
"""

import json
import logging as _logging
import logging
from pathlib import Path
from typing import Any, Dict
import logging

from core.path_resolver import get_config_dir, get_data_dir, get_project_root
from core.version import VERSION

logger = _logging.getLogger("Miya.Config")


def get_miya_root() -> Path:
    return get_project_root()


def get_miya_data_dir() -> Path:
    return get_data_dir()


def get_miya_config_path() -> Path:
    return get_data_dir() / "config"


# 向后兼容别名
get_config_path = get_miya_config_path


# 默认配置
DEFAULT_CONFIG = {
    "version": VERSION,
    "dashboard": {
        "enable": False,
        "username": "miya",
        "password": "",
        "host": "127.0.0.1",
        "port": 6185,
    },
    "provider": [],
    "platform": [],
    "log_level": "INFO",
}


def get_miya_config() -> Dict[str, Any]:
    """获取弥娅配置"""
    config_path = get_config_path() / "config.json"

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取 {config_path} 失败，使用默认配置: {e}")

    return DEFAULT_CONFIG.copy()


def save_miya_config(config: Dict[str, Any]):
    """保存配置"""
    config_path = get_config_path() / "config.json"
    config_path.parent.mkdir(exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


__all__ = ["get_miya_config", "save_miya_config", "DEFAULT_CONFIG"]
