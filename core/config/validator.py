"""
配置验证系统
基于Pydantic的配置验证和管理
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import yaml
from pydantic import BaseModel, Field, root_validator, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..error_handler import ConfigError
from ..types import ErrorCode, TerminalType


# ==================== 基础配置模型 ====================
class DatabaseConfig(BaseModel):
    """数据库配置"""

    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=6379, ge=1, le=65535, description="数据库端口")
    database: str = Field(default="miya", description="数据库名称")
    username: Optional[str] = Field(default=None, description="用户名")
    password: Optional[str] = Field(default=None, description="密码")
    pool_size: int = Field(default=10, ge=1, le=100, description="连接池大小")

    @validator("password")
    def validate_password(cls, v):
        """验证密码"""
        if v and len(v) < 8:
            raise ValueError("密码至少需要8个字符")
        return v

    @validator("host")
    def validate_host(cls, v):
        """验证主机地址"""
        if not v or len(v.strip()) == 0:
            raise ValueError("主机地址不能为空")
        return v.strip()


class AIConfig(BaseModel):
    """AI配置"""

    provider: str = Field(default="", description="AI服务提供商")
    api_key: str = Field(..., min_length=10, description="API密钥")
    model: str = Field(default="", description="模型名称")
    base_url: Optional[str] = Field(default=None, description="API基础URL")
    timeout: int = Field(default=30, ge=1, le=300, description="超时时间（秒）")
    max_tokens: int = Field(default=2000, ge=1, le=10000, description="最大令牌数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")

    @validator("provider")
    def validate_provider(cls, v):
        """验证提供商 - 所有提供商由 multi_model_config.json 定义"""
        return v.strip().lower() if v else ""

    @validator("api_key")
    def validate_api_key(cls, v):
        """验证API密钥"""
        if not v or len(v.strip()) == 0:
            raise ValueError("API密钥不能为空")
        return v.strip()


class TerminalConfig(BaseModel):
    """终端配置"""

    max_terminals: int = Field(default=10, ge=1, le=50, description="最大终端数")
    default_type: TerminalType = Field(default="cmd", description="默认终端类型")
    command_timeout: int = Field(default=30, ge=1, le=300, description="命令超时时间（秒）")
    auto_cleanup: bool = Field(default=True, description="自动清理空闲终端")
    max_history: int = Field(default=100, ge=1, le=1000, description="最大历史记录数")
    working_directory: str = Field(default=".", description="工作目录")

    @validator("working_directory")
    def validate_working_directory(cls, v):
        """验证工作目录"""
        try:
            path = Path(v).resolve()
            if not path.exists():
                raise ValueError(f"工作目录不存在: {v}")
            return str(path)
        except Exception as e:
            raise ValueError(f"无效的工作目录: {v} - {e}")


class MemoryConfig(BaseModel):
    """记忆配置"""

    tide_ttl: int = Field(default=3600, ge=60, le=86400, description="短期记忆TTL（秒）")
    dream_compression_threshold: int = Field(default=100, ge=10, le=1000, description="记忆压缩阈值")
    semantic_vector_dim: int = Field(default=768, ge=128, le=2048, description="语义向量维度")
    max_memories: int = Field(default=10000, ge=100, le=100000, description="最大记忆数")
    persist_interval: int = Field(default=300, ge=10, le=3600, description="持久化间隔（秒）")


class EmotionConfig(BaseModel):
    """情绪配置"""

    decay_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="情绪衰减率")
    coloring_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="染色阈值")
    max_intensity: float = Field(default=1.0, ge=0.0, le=2.0, description="最大强度")
    min_intensity: float = Field(default=0.0, ge=0.0, le=0.5, description="最小强度")


class WebConfig(BaseModel):
    """Web配置"""

    host: str = Field(default="0.0.0.0", description="监听主机")
    port: int = Field(default=8080, ge=1, le=65535, description="监听端口")
    debug: bool = Field(default=False, description="调试模式")
    cors_origins: List[str] = Field(default=["*"], description="CORS允许的源")
    api_prefix: str = Field(default="/api", description="API前缀")
    secret_key: str = Field(default="", description="密钥（必填，请通过环境变量 SECRET_KEY 设置）")
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440, description="访问令牌过期时间（分钟）")

    @validator("secret_key")
    def validate_secret_key(cls, v):
        """验证密钥"""
        if not v or v == "change-me-in-production":
            raise ValueError(
                "secret_key 未设置或使用了不安全默认值。请设置环境变量 SECRET_KEY（建议使用 openssl rand -hex 32 生成）"
            )
        return v


# ==================== 主配置模型 ====================
class AppConfig(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用基础配置
    app_name: str = Field(default="Miya", description="应用名称")
    app_version: str = Field(default="4.0.0", description="应用版本")
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # 各模块配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ai: AIConfig
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    emotion: EmotionConfig = Field(default_factory=EmotionConfig)
    web: WebConfig = Field(default_factory=WebConfig)

    # 可选配置
    qq_enabled: bool = Field(default=False, description="QQ机器人启用")
    desktop_enabled: bool = Field(default=True, description="桌面应用启用")
    iot_enabled: bool = Field(default=False, description="IoT启用")

    @root_validator(pre=True)
    def validate_all_configs(cls, values):
        """验证所有配置"""
        # 这里可以添加全局验证逻辑
        return values

    @classmethod
    def from_env(cls, env_file: Optional[Union[str, Path]] = None) -> "AppConfig":
        """
        从环境变量加载配置

        Args:
            env_file: .env文件路径

        Returns:
            配置实例
        """
        if env_file:
            if isinstance(env_file, str):
                env_file = Path(env_file)

            if not env_file.exists():
                raise ConfigError(
                    code=ErrorCode.CONFIG_NOT_FOUND,
                    message=f"配置文件不存在: {env_file}",
                )

            os.environ.setdefault("ENV_FILE", str(env_file))

        try:
            return cls()  # Pydantic会自动处理.env文件
        except Exception as e:
            raise ConfigError(
                code=ErrorCode.CONFIG_INVALID,
                message=f"配置加载失败: {e}",
                original_error=e,
            )

    @classmethod
    def from_file(cls, config_file: Union[str, Path]) -> "AppConfig":
        """
        从配置文件加载

        Args:
            config_file: 配置文件路径（JSON或YAML）

        Returns:
            配置实例
        """
        if isinstance(config_file, str):
            config_file = Path(config_file)

        if not config_file.exists():
            raise ConfigError(
                code=ErrorCode.CONFIG_NOT_FOUND,
                message=f"配置文件不存在: {config_file}",
            )

        try:
            # 根据文件扩展名选择加载方式
            if config_file.suffix.lower() in [".json", ".json5"]:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif config_file.suffix.lower() in [".yaml", ".yml"]:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                raise ValueError(f"不支持的配置文件格式: {config_file.suffix}")

            return cls(**data)
        except Exception as e:
            raise ConfigError(
                code=ErrorCode.CONFIG_INVALID,
                message=f"配置文件解析失败: {e}",
                original_error=e,
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()

    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return self.model_dump_json(indent=indent)

    def to_yaml(self) -> str:
        """转换为YAML字符串"""
        return yaml.dump(self.model_dump(), default_flow_style=False)

    def validate(self) -> bool:
        """
        验证配置

        Returns:
            验证是否通过
        """
        try:
            # Pydantic会自动验证，这里主要是额外的业务验证
            if self.ai.api_key == "your-api-key-here":
                raise ConfigError(code=ErrorCode.CONFIG_INVALID, message="请设置有效的AI API密钥")

            if self.web.secret_key == "change-me-in-production" and not self.debug:
                raise ConfigError(code=ErrorCode.CONFIG_INVALID, message="生产环境必须设置安全的密钥")

            return True
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(
                code=ErrorCode.CONFIG_INVALID,
                message=f"配置验证失败: {e}",
                original_error=e,
            )

    def update(self, **kwargs) -> "AppConfig":
        """
        更新配置

        Args:
            **kwargs: 要更新的配置项

        Returns:
            新的配置实例
        """
        data = self.model_dump()
        data.update(kwargs)
        return self.__class__(**data)


# ==================== 配置管理器 ====================
class ConfigManager:
    """配置管理器"""

    def __init__(self, config: Optional[AppConfig] = None):
        """
        Args:
            config: 配置实例，如果为None则从环境变量加载
        """
        self._config = config or AppConfig.from_env()
        self._observers: List[Callable[[AppConfig], None]] = []
        self._last_hash: Optional[str] = None

    @property
    def config(self) -> AppConfig:
        """获取当前配置"""
        return self._config

    def reload(self, source: Optional[Union[str, Path]] = None) -> None:
        """
        重新加载配置

        Args:
            source: 配置源（文件路径或None表示从环境变量加载）
        """
        old_config = self._config

        if source:
            if isinstance(source, str):
                source = Path(source)

            if source.suffix.lower() in [".json", ".yaml", ".yml", ".json5"]:
                self._config = AppConfig.from_file(source)
            else:
                # 假设是.env文件
                self._config = AppConfig.from_env(source)
        else:
            self._config = AppConfig.from_env()

        # 验证新配置
        self._config.validate()

        # 通知观察者
        if old_config != self._config:
            self._notify_observers()

    def register_observer(self, callback: Callable[[AppConfig], None]) -> None:
        """
        注册配置变更观察者

        Args:
            callback: 回调函数，接收新配置作为参数
        """
        self._observers.append(callback)

    def unregister_observer(self, callback: Callable[[AppConfig], None]) -> None:
        """取消注册观察者"""
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self) -> None:
        """通知所有观察者"""
        for callback in self._observers:
            try:
                callback(self._config)
            except Exception as e:
                import logging

                logging.error(f"配置变更通知失败: {e}", exc_info=True)

    def save_to_file(self, filepath: Union[str, Path], format: str = "json") -> None:
        """
        保存配置到文件

        Args:
            filepath: 文件路径
            format: 文件格式（json或yaml）
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == "json":
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(self._config.to_json())
            elif format.lower() in ["yaml", "yml"]:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(self._config.to_yaml())
            else:
                raise ValueError(f"不支持的格式: {format}")
        except Exception as e:
            raise ConfigError(
                code=ErrorCode.CONFIG_ENCRYPTION_ERROR,
                message=f"保存配置失败: {e}",
                original_error=e,
            )

    def get_subconfig(self, prefix: str) -> Dict[str, Any]:
        """
        获取子配置

        Args:
            prefix: 配置前缀（如"database."）

        Returns:
            子配置字典
        """
        data = self._config.to_dict()

        if not prefix.endswith("."):
            prefix = prefix + "."

        result = {}
        for key, value in data.items():
            if key.startswith(prefix):
                subkey = key[len(prefix) :]
                result[subkey] = value

        return result

    def check_for_changes(self) -> bool:
        """
        检查配置是否有变化

        Returns:
            是否有变化
        """
        current_hash = hash(str(self._config.to_dict()))

        if self._last_hash is None:
            self._last_hash = current_hash
            return False

        has_changed = current_hash != self._last_hash
        self._last_hash = current_hash
        return has_changed


# ==================== 默认配置 ====================
def get_default_config() -> AppConfig:
    """获取默认配置 - 所有模型由 multi_model_config.json 管理"""
    return AppConfig(
        ai=AIConfig(
            provider="",
            api_key="",
            model="",
        )
    )


def create_minimal_config(api_key: str) -> AppConfig:
    """
    创建最小化配置

    Args:
        api_key: AI API密钥

    Returns:
        最小化配置实例
    """
    return AppConfig(
        ai=AIConfig(provider="", api_key=api_key, model=""),
        debug=True,
        log_level="DEBUG",
    )


# ==================== 工具函数 ====================
def validate_config_file(filepath: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    验证配置文件

    Args:
        filepath: 配置文件路径

    Returns:
        (是否有效, 错误信息)
    """
    try:
        config = AppConfig.from_file(filepath)
        config.validate()
        return True, None
    except Exception as e:
        return False, str(e)


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置（深度合并）

    Args:
        base: 基础配置
        override: 覆盖配置

    Returns:
        合并后的配置
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


# ==================== 全局配置实例 ====================
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager()

    return _config_manager


def get_config() -> AppConfig:
    """获取全局配置"""
    return get_config_manager().config


def reload_config(source: Optional[Union[str, Path]] = None) -> None:
    """重新加载全局配置"""
    get_config_manager().reload(source)
