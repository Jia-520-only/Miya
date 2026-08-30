#!/usr/bin/env python3
"""
QQ配置加载器
负责加载和管理QQ相关配置
"""

import logging
import os
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class QQConfigLoader:
    """QQ配置加载器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化QQ配置加载器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config: Dict[str, Any] = {}
        self.initialized = False

    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        # 尝试多个可能的配置文件路径
        possible_paths = ["config/qq_config.yaml", "config/qq.yaml", "../config/qq_config.yaml", "./qq_config.yaml"]

        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)

        # 如果都不存在，使用项目根目录下的路径
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "qq_config.yaml")

    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"QQ配置文件不存在: {self.config_path}，使用默认配置")
                self.config = self._get_default_config()
                self.initialized = True
                return True

            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}

            # 应用默认值
            self.config = self._apply_defaults(self.config)

            logger.info(f"QQ配置加载成功: {self.config_path}")
            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"加载QQ配置失败: {e}")
            self.config = self._get_default_config()
            self.initialized = True
            return False

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置（仅为功能配置提供回退，不包含连接凭证）"""
        return {
            "qq": {
                "connection": {
                    "reconnect_interval": 5.0,
                    "ping_interval": 20,
                    "ping_timeout": 30,
                    "max_message_size": 104857600,
                },
                "multimedia": {
                    "image": {
                        "max_size": 10485760,
                        "allowed_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
                    },
                    "file": {
                        "max_size": 52428800,
                        "allowed_formats": {
                            "text": [".txt", ".log", ".md", ".json", ".xml", ".html", ".csv"],
                            "document": [".pdf", ".doc", ".docx"],
                        },
                    },
                },
            },
            "tools": {
                "qq_file_reader": {"enabled": True, "max_preview_length": 2000},
                "qq_image_analyzer": {"enabled": True, "ocr_engine": "auto"},
            },
        }

    def _apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """应用默认值到配置"""
        defaults = self._get_default_config()

        def _merge_dict(dest: Dict, src: Dict) -> Dict:
            for key, value in src.items():
                if key not in dest:
                    dest[key] = value
                elif isinstance(value, dict) and isinstance(dest.get(key), dict):
                    dest[key] = _merge_dict(dest[key], value)
            return dest

        return _merge_dict(config, defaults)

    @property
    def _initialized(self) -> bool:
        """兼容旧测试代码的初始化状态别名"""
        return self.initialized

    @_initialized.setter
    def _initialized(self, value: bool) -> None:
        self.initialized = value

    def get(self, key: str, default: Any = None) -> Any:
        """按点号路径读取完整配置，例如 ``qq.connection.ws_url``"""
        node: Any = self.get_config()
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def get_connection(self) -> Dict[str, Any]:
        """获取 QQ 连接配置"""
        return self.get("qq.connection", {})

    def get_multimedia(self) -> Dict[str, Any]:
        """获取多媒体配置"""
        return self.get("qq.multimedia", {})

    def get_tool(self, tool_name: str) -> Dict[str, Any]:
        """获取单个工具配置"""
        return self.get_tool_config(tool_name) or {}

    def validate(self) -> tuple[bool, list[str]]:
        """兼容旧测试代码的验证方法别名"""
        return self.validate_config()

    def reload(self) -> bool:
        """兼容旧测试代码的重载方法别名"""
        return self.reload_config()

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        if not self.initialized:
            self.load_config()
        return self.config

    def get_qq_config(self, key: Optional[str] = None) -> Any:
        """获取QQ特定配置"""
        config = self.get_config()
        qq_config = config.get("qq", {})

        if key is None:
            return qq_config

        # 支持点分路径，如 "onebot.ws_url"
        if "." in key:
            parts = key.split(".")
            value = qq_config
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, {})
                else:
                    return None
            return value
        else:
            return qq_config.get(key)

    def get_tool_config(self, tool_name: str, key: Optional[str] = None) -> Any:
        """获取工具配置"""
        config = self.get_config()
        tools_config = config.get("tools", {})
        tool_config = tools_config.get(tool_name, {})

        if key is None:
            return tool_config
        return tool_config.get(key)

    def validate_config(self) -> tuple[bool, list[str]]:
        """验证配置有效性（仅验证功能配置，不验证 .env 中的连接凭证）"""
        errors = []
        config = self.get_config()

        # 检查多媒体配置
        multimedia_config = config.get("multimedia", {})
        if multimedia_config.get("image", {}).get("max_size", 0) < 0:
            errors.append("图片最大大小配置不正确")
        if multimedia_config.get("file", {}).get("max_size", 0) < 0:
            errors.append("文件最大大小配置不正确")

        # 检查工具配置
        tools_config = config.get("tools", {})
        for tool_name, tool_config in tools_config.items():
            if isinstance(tool_config, dict) and tool_config.get("enabled", False):
                if tool_name.startswith("qq_"):
                    # 验证QQ相关工具的基础配置
                    pass

        return len(errors) == 0, errors

    def reload_config(self) -> bool:
        """重新加载配置"""
        self.initialized = False
        return self.load_config()

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """保存配置到文件"""
        try:
            if config is not None:
                self.config = config

            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            logger.info(f"QQ配置已保存到: {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"保存QQ配置失败: {e}")
            return False


# 全局配置加载器实例
_global_config_loader: Optional[QQConfigLoader] = None


def get_config_loader() -> QQConfigLoader:
    """获取全局配置加载器实例"""
    global _global_config_loader
    if _global_config_loader is None:
        _global_config_loader = QQConfigLoader()
        _global_config_loader.load_config()
    return _global_config_loader


def get_qq_config(key: Optional[str] = None) -> Any:
    """获取QQ配置（快捷函数）"""

    return get_config_loader().get_qq_config(key)


def get_connection_config() -> Dict[str, Any]:
    """获取 QQ 连接配置（兼容旧测试代码导入）"""

    return get_config_loader().get_connection()


def get_multimedia_config() -> Dict[str, Any]:
    """获取多媒体配置（兼容旧测试代码导入）"""
    return get_config_loader().get_multimedia()


def get_tool_config(tool_name: str, key: Optional[str] = None) -> Any:
    """获取工具配置（快捷函数）"""
    return get_config_loader().get_tool_config(tool_name, key)
