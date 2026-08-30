#!/usr/bin/env python3
"""
MIYA 配置加载器

统一从 .env 加载配置，自动注入到各 Provider
支持多配置源：
1. 环境变量 (.env)
2. JSON 配置文件
3. 默认值
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from core.path_resolver import get_config_dir

logger = logging.getLogger(__name__)

CONFIG_DIR = get_config_dir()

# 加载 .env
if not os.environ.get("_MIYA_DOTENV_LOADED"):
    env_path = get_config_dir() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        os.environ["_MIYA_DOTENV_LOADED"] = "1"


# ==================== 配置加载器 ====================


class ConfigLoader:
    """配置加载器 - 自动从环境变量加载"""

    _instance: Optional["ConfigLoader"] = None
    _cache: Dict[str, Any] = {}

    def __init__(self):
        self._load_all()

    @classmethod
    def get_instance(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_all(self):
        """加载所有配置"""
        self._load_ai_config()
        self._load_platform_config()

    def _load_ai_config(self):
        """加载 AI 配置"""
        self._cache["ai"] = {
            "max_tokens": int(os.getenv("AI_MAX_TOKENS", "2000")),
            "temperature": float(os.getenv("AI_TEMPERATURE", "0.7")),
            "max_retries": int(os.getenv("AI_REQUEST_MAX_RETRIES", "2")),
            "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "30")),
            "provider": os.getenv("AI_PROVIDER", "siliconflow"),
            # 密钥
            "siliconflow_api_key": read_env_key("SILICONFLOW_API_KEY"),
            "deepseek_api_key": read_env_key("DEEPSEEK_API_KEY"),
            "zhipu_api_key": read_env_key("ZHIPU_API_KEY"),
            "dashscope_api_key": read_env_key("DASHSCOPE_API_KEY"),
            "grok_api_key": read_env_key("GROK_API_KEY"),
            "anthropic_api_key": read_env_key("ANTHROPIC_API_KEY"),
            "openai_api_key": read_env_key("OPENAI_API_KEY"),
            # Base URLs
            "siliconflow_base_url": os.getenv(
                "SILICONFLOW_API_BASE",
                os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            ),
            "deepseek_base_url": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
            "zhipu_base_url": os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4"),
            "dashscope_base_url": os.getenv(
                "DASHSCOPE_API_BASE",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        }

    def _load_platform_config(self):
        """加载平台配置"""
        self._cache["platform"] = {
            "qq": {
                "onebot_ws_url": os.getenv("QQ_ONEBOT_WS_URL", "ws://localhost:3001"),
                "onebot_token": os.getenv("QQ_ONEBOT_TOKEN", ""),
                "bot_qq": os.getenv("QQ_BOT_QQ", ""),
                "superadmin_qq": os.getenv("QQ_SUPERADMIN_QQ", ""),
            },
            "telegram": {
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        # 尝试从嵌套键获取
        keys = key.split(".")
        value = self._cache
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_api_key(self, provider: str) -> str:
        """获取 Provider API 密钥"""
        from core.model_pool_manager import resolve_api_key_by_provider

        return resolve_api_key_by_provider(provider)

    def get_base_url(self, provider: str) -> str:
        """获取 Provider Base URL"""
        env_map = {
            "siliconflow": "SILICONFLOW_API_BASE",
            "deepseek": "DEEPSEEK_API_BASE",
            "zhipu": "ZHIPU_API_BASE",
            "dashscope": "DASHSCOPE_API_BASE",
        }
        env_key = env_map.get(provider.lower())
        primary = os.getenv(env_key, "") if env_key else ""
        if primary:
            return primary
        return os.getenv(f"{provider.upper()}_API_BASE", "") or os.getenv(f"{provider.upper()}_BASE_URL", "")


# ==================== 便捷函数 ====================


_config_loader: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """获取配置加载器"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def get_api_key(provider: str) -> str:
    """获取 API 密钥的便捷函数"""
    return get_config().get_api_key(provider)


def get_base_url(provider: str) -> str:
    """获取 Base URL 的便捷函数"""
    return get_config().get_base_url(provider)


# ==================== text_config.json 加载 (委托到 config.config_utils) ====================

from config.config_utils import get_api_key as read_env_key
from config.config_utils import get_section as shared_get_section
from config.config_utils import reload_config as shared_reload_config

# 委托 text_config 加载到统一的 config/config_utils
_text_config_loaded = False


def load_text_config(force_reload: bool = False) -> Dict[str, Any]:
    global _text_config_loaded
    if force_reload and _text_config_loaded:
        shared_reload_config()
    _text_config_loaded = True
    return shared_get_section() or {}


def get_text_config_value(key: str, default: Any = None) -> Any:
    """获取 text_config.json 中的配置值（支持点号分隔的嵌套键）"""
    from config.config_utils import get_text

    return get_text(*[part for part in key.split(".") if part], default=default) if key else default


def reload_text_config():
    shared_reload_config()
    global _text_config_loaded
    _text_config_loaded = False
    logger.info("已清除 text_config.json 缓存")


__all__ = [
    "ConfigLoader",
    "get_config",
    "get_api_key",
    "get_base_url",
    "load_text_config",
    "get_text_config_value",
    "reload_text_config",
]
