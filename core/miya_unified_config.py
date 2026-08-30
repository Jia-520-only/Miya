#!/usr/bin/env python3
"""
MIYA 统一配置入口

整合所有核心配置，提供统一访问
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


# ==================== 统一配置 ====================


@dataclass
class MIYAConfig:
    """MIYA 统一配置"""

    # 基础路径
    project_root: Path
    config_dir: Path

    # AI 配置
    ai_provider: str = "siliconflow"
    ai_max_tokens: int = 2000
    ai_temperature: float = 0.7

    # 运行时
    debug: bool = False
    log_level: str = "INFO"

    # 端口
    api_port: int = 8765
    web_port: int = 8000


# ==================== 配置加载器 ====================


class Config:
    """MIYA 统一配置类"""

    _instance: Optional["Config"] = None
    _config: Optional[MIYAConfig] = None

    def __init__(self):
        self._load_all()

    @classmethod
    def get_instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_all(self):
        """加载所有配置"""
        # 从 system_config 加载
        try:
            from core.system_config import get_constant

            self._config = MIYAConfig(
                project_root=PROJECT_ROOT,
                config_dir=CONFIG_DIR,
                ai_provider=get_constant("AI_PROVIDER", "siliconflow"),
                ai_max_tokens=int(get_constant("AI_MAX_TOKENS", "2000")),
                ai_temperature=float(get_constant("AI_TEMPERATURE", "0.7")),
                debug=get_constant("DEBUG", "false").lower() == "true",
                log_level=get_constant("LOG_LEVEL", "INFO"),
                api_port=int(get_constant("API_PORT", "8765")),
                web_port=int(get_constant("WEB_PORT", "8000")),
            )
        except Exception:
            # 使用默认值
            self._config = MIYAConfig(
                project_root=PROJECT_ROOT,
                config_dir=CONFIG_DIR,
            )

    @property
    def providers(self):
        """获取模型提供商"""
        from core.providers_config import get_default_providers

        return get_default_providers()

    @property
    def platforms(self):
        """获取平台配置"""
        from core.platforms_config import get_default_platforms

        return get_default_platforms()

    @property
    def models(self):
        """获取模型池"""
        from core.model_pool_manager import get_model_pool

        return get_model_pool()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if self._config and hasattr(self._config, key):
            return getattr(self._config, key)
        return default


# ==================== 便捷函数 ====================


def get_config() -> Config:
    """获取配置"""
    return Config.get_instance()


# 兼容旧 API
def get_miya_config():
    """获取 MIYA 配置 (兼容)"""
    return Config.get_instance()


__all__ = [
    "MIYAConfig",
    "Config",
    "get_config",
    "get_miya_config",
]
