"""
Provider 配置加载器

从多种格式加载Provider配置，支持:
- MIYA 原生格式 (multi_model_config.json)
- AstrBot 格式 (provider + provider_sources)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bridge import (
    ProviderConfig,
    ProviderType,
    get_provider_bridge,
)

logger = logging.getLogger(__name__)


class ProviderConfigLoader:
    """Provider配置加载器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._bridge = get_provider_bridge()
        self._configs: Dict[str, ProviderConfig] = {}

    def load_from_miya_config(self, config_path: str = "config/multi_model_config.json") -> Dict[str, ProviderConfig]:
        """从MIYA原生配置加载"""
        try:
            path = Path(config_path)
            if not path.exists():
                logger.warning(f"[ProviderConfigLoader] 配置不存在: {config_path}")
                return {}

            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)

            models = config.get("models", {})
            for model_id, model_config in models.items():
                if not model_config.get("enabled", True):
                    continue

                # 确定provider类型
                provider_name = model_config.get("provider", "").lower()

                # 获取默认值
                base_url = model_config.get("base_url", "https://api.openai.com/v1")
                api_key = model_config.get("api_key", "")
                model_name = model_config.get("name", "")

                # 映射到AstrBot类型
                provider_type = self._map_to_astrbot_type(provider_name)

                pc = ProviderConfig(
                    id=model_id,
                    type=provider_type,
                    provider_type=ProviderType(provider_type),
                    enable=True,
                    name=model_config.get("description", ""),
                    base_url=base_url,
                    api_key=api_key,
                    model=model_name,
                    extra=model_config,
                )
                self._configs[model_id] = pc

            logger.info(f"[ProviderConfigLoader] 从MIYA配置加载了 {len(self._configs)} 个模型")
            return self._configs

        except Exception as e:
            logger.error(f"[ProviderConfigLoader] 加载配置失败: {e}")
            return {}

    def load_from_astrbot_config(
        self, provider_config: List[Dict], provider_sources: Optional[List[Dict]] = None
    ) -> Dict[str, ProviderConfig]:
        """从AstrBot格式配置加载"""
        try:
            source_map = {}
            if provider_sources:
                for source in provider_sources:
                    source_id = source.get("id", "")
                    if source_id:
                        source_map[source_id] = source

            for config in provider_config:
                provider_id = config.get("id", "")
                provider_type = config.get("type", "")

                if not config.get("enable", True):
                    continue

                # 合并source配置
                source_id = config.get("provider_source_id", "")
                merged_config = dict(config)
                if source_id in source_map:
                    merged_config = {**source_map[source_id], **config}
                    merged_config["id"] = provider_id

                # 获取API配置
                keys = merged_config.get("key", [""])
                api_key = (keys[0] if keys else "") if isinstance(keys, list) else keys

                pc = ProviderConfig(
                    id=provider_id,
                    type=provider_type,
                    provider_type=ProviderType.CHAT_COMPLETION,
                    enable=True,
                    name=merged_config.get("name", ""),
                    base_url=merged_config.get("base_url", ""),
                    api_key=api_key,
                    model=merged_config.get("model", ""),
                    extra=merged_config,
                )
                self._configs[provider_id] = pc

            logger.info(f"[ProviderConfigLoader] 从AstrBot配置加载了 {len(provider_config)} 个模型")
            return self._configs

        except Exception as e:
            logger.error(f"[ProviderConfigLoader] 加载AstrBot配置失败: {e}")
            return {}

    def _map_to_astrbot_type(self, provider_name: str) -> str:
        """将MIYA provider名称映射到AstrBot类型"""
        mapping = {
            "openai": "openai_chat_completion",
            "anthropic": "anthropic_chat_completion",
            "deepseek": "deepseek_chat_completion",
            "siliconflow": "openai_chat_completion",
            "zhipu": "zhipu_chat_completion",
            "kimi": "kimi_chat_completion",
            "groq": "groq_chat_completion",
            "gemini": "googlegenai_chat_completion",
            "azure": "azure_chat_completion",
            "ollama": "ollama_chat_completion",
        }
        return mapping.get(provider_name.lower(), "openai_chat_completion")

    def get_config(self, model_id: str) -> Optional[ProviderConfig]:
        """获取指定配置"""
        return self._configs.get(model_id)

    def list_models(self, provider_type: Optional[ProviderType] = None) -> List[str]:
        """列出可用模型"""
        models = []
        for model_id, config in self._configs.items():
            if provider_type and config.provider_type != provider_type:
                continue
            if config.enable:
                models.append(model_id)
        return models

    def to_multi_model_format(self) -> Dict[str, Any]:
        """转换为MIYA格式"""
        models = {}
        for model_id, config in self._configs.items():
            models[model_id] = {
                "name": config.model,
                "provider": self._map_to_miya_provider(config.type),
                "base_url": config.base_url,
                "api_key": config.api_key,
                "description": config.name,
                **config.extra,
            }
        return {"models": models}

    def _map_to_miya_provider(self, astrbot_type: str) -> str:
        """将AstrBot类型映射到MIYA provider名称"""
        mapping = {
            "openai_chat_completion": "openai",
            "anthropic_chat_completion": "anthropic",
            "deepseek_chat_completion": "deepseek",
            "zhipu_chat_completion": "zhipu",
            "kimi_chat_completion": "kimi",
            "groq_chat_completion": "groq",
            "googlegenai_chat_completion": "gemini",
        }
        return mapping.get(astrbot_type, "openai")


def get_provider_config_loader() -> ProviderConfigLoader:
    """获取配置加载器实例"""
    return ProviderConfigLoader()


# 支持的模型列表（参考AstrBot）
AVAILABLE_MODELS = {
    "openai": {
        "chat": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "embedding": ["text-embedding-3-small", "text-embedding-ada-002"],
        "tts": ["tts-1", "tts-1-hd"],
    },
    "anthropic": {
        "chat": ["claude-sonnet-4-20250514", "claude-haiku-3-20240307"],
    },
    "deepseek": {
        "chat": ["deepseek-chat", "deepseek-coder"],
    },
    "zhipu": {
        "chat": ["glm-4", "glm-4-flash", "glm-4v", "glm-4.6v"],
    },
    "kimi": {
        "chat": ["kimi-chat"],
    },
    "groq": {
        "chat": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
    },
    "gemini": {
        "chat": ["gemini-1.5-pro", "gemini-1.5-flash"],
        "embedding": ["text-embedding-004"],
    },
}
