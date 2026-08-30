#!/usr/bin/env python3
"""
统一QQ配置加载器
主数据源: config/.env（连接配置）+ qq_config.yaml（功能配置）
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class UnifiedQQConfig:
    """统一QQ配置管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config = None
        self._settings = None
        self._initialized = True

    def initialize(self):
        """初始化配置"""
        self._load_dotenv()

        try:
            from config.settings import Settings

            self._settings = Settings()
            self._config = self._build_config()
            logger.info(
                f"[UnifiedQQConfig] 配置加载: ws_url={self._config.get('ws_url')}, bot_qq={self._config.get('bot_qq')}"
            )
        except ImportError:
            self._config = self._build_config()
        except Exception as e:
            logger.error(f"[UnifiedQQConfig] 配置初始化失败: {e}")
            self._config = {}

    def _load_dotenv(self):
        """加载 .env 文件"""
        try:
            from dotenv import load_dotenv

            env_path = os.path.join(project_root, "config", ".env")
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)
            else:
                alt = os.path.join(project_root, ".env")
                if os.path.exists(alt):
                    load_dotenv(alt, override=True)
        except Exception:
            pass

    def _build_config(self) -> Dict[str, Any]:
        """从 .env 构建基础配置，从 qq_config.yaml 补充功能配置"""
        config = {
            # --- 连接配置 (.env) ---
            "ws_url": os.getenv("QQ_ONEBOT_WS_URL", ""),
            "token": os.getenv("QQ_ONEBOT_TOKEN", ""),
            "bot_qq": int(os.getenv("QQ_BOT_QQ", 0) or 0),
            "superadmin_qq": int(os.getenv("QQ_SUPERADMIN_QQ", 0) or 0),
            "reconnect_interval": float(os.getenv("QQ_RECONNECT_INTERVAL", "5.0")),
            "ping_interval": int(os.getenv("QQ_PING_INTERVAL", "20")),
            "ping_timeout": int(os.getenv("QQ_PING_TIMEOUT", "30")),
            "max_message_size": int(os.getenv("QQ_MAX_MESSAGE_SIZE", "104857600")),
            # --- 功能开关 (.env) ---
            "ocr_enabled": os.getenv("QQ_OCR_ENABLED", "true").lower() == "true",
            "active_chat_enabled": os.getenv("QQ_ACTIVE_CHAT_ENABLED", "true").lower() == "true",
        }

        # 从 qq_config.yaml 补充功能配置
        yaml_qq = self._load_yaml_qq_section()
        config["multimedia"] = yaml_qq.get("multimedia", {})
        config["image_recognition"] = yaml_qq.get("image_recognition", {})
        config["access_control"] = yaml_qq.get("access_control", {})
        config["features"] = yaml_qq.get("features", {})
        config["task_scheduler"] = yaml_qq.get("task_scheduler", {})
        config["commands"] = yaml_qq.get("commands", {})
        config["performance"] = yaml_qq.get("performance", {})
        config["logging"] = yaml_qq.get("logging", {})
        config["message_parsing"] = yaml_qq.get("message_parsing", {})
        config["forward"] = yaml_qq.get("forward", {})
        config["message_batching"] = yaml_qq.get("message_batching", {})
        config["message_queue"] = yaml_qq.get("message_queue", {})
        config["debug"] = yaml_qq.get("debug", {})

        return config

    def _load_yaml_qq_section(self) -> Dict[str, Any]:
        """从 qq_config.yaml 加载 qq 段"""
        try:
            import yaml

            yaml_path = os.path.join(project_root, "config", "qq_config.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("qq", {})
        except Exception:
            pass
        return {}

    def get_config(self) -> Dict[str, Any]:
        if self._config is None:
            self.initialize()
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        config = self.get_config()
        if "." in key:
            parts = key.split(".")
            value = config
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, {})
                else:
                    return default
            return value if value != {} else default
        return config.get(key, default)

    def get_connection_config(self) -> Dict[str, Any]:
        return {
            "ws_url": self.get("ws_url"),
            "token": self.get("token"),
            "bot_qq": self.get("bot_qq"),
            "superadmin_qq": self.get("superadmin_qq"),
            "reconnect_interval": self.get("reconnect_interval"),
            "ping_interval": self.get("ping_interval"),
            "ping_timeout": self.get("ping_timeout"),
            "max_message_size": self.get("max_message_size"),
        }

    def get_multimedia_config(self) -> Dict[str, Any]:
        return self.get("multimedia", {})

    def get_image_recognition_config(self) -> Dict[str, Any]:
        return self.get("image_recognition", {})

    def get_active_chat_config(self) -> Dict[str, Any]:
        return self.get("features", {})

    def get_task_scheduler_config(self) -> Dict[str, Any]:
        return self.get("task_scheduler", {})

    def validate_config(self) -> tuple[bool, list[str]]:
        errors = []
        config = self.get_config()

        if not config.get("ws_url"):
            errors.append("QQ_ONEBOT_WS_URL 未在 .env 中配置, 例如: QQ_ONEBOT_WS_URL=ws://localhost:3001")
        elif not config["ws_url"].startswith(("ws://", "wss://")):
            errors.append("WebSocket 地址格式不正确，必须以 ws:// 或 wss:// 开头")

        return len(errors) == 0, errors

    def reload(self) -> bool:
        try:
            self._load_dotenv()
            if self._settings:
                self._settings.reload()
            self._config = self._build_config()
            logger.info("[UnifiedQQConfig] 配置重新加载成功")
            return True
        except Exception as e:
            logger.error(f"[UnifiedQQConfig] 配置重新加载失败: {e}")
            return False


_global_unified_config: Optional[UnifiedQQConfig] = None


def get_unified_config() -> UnifiedQQConfig:
    global _global_unified_config
    if _global_unified_config is None:
        _global_unified_config = UnifiedQQConfig()
        _global_unified_config.initialize()
    return _global_unified_config


def get_qq_config(key: Optional[str] = None, default: Any = None) -> Any:
    config = get_unified_config()
    if key is None:
        return config.get_config()
    return config.get(key, default)


def get_connection_config() -> Dict[str, Any]:
    return get_unified_config().get_connection_config()


def get_multimedia_config() -> Dict[str, Any]:
    return get_unified_config().get_multimedia_config()


def validate_config() -> tuple[bool, list[str]]:
    return get_unified_config().validate_config()
