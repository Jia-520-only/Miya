#!/usr/bin/env python3
"""
Provider 注册机制

参考 AstrBot 实现，支持动态注册和加载 Provider 适配器
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Type

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Provider 类型"""

    CHAT_COMPLETION = "chat_completion"
    TEXT_TO_SPEECH = "text_to_speech"
    SPEECH_TO_TEXT = "speech_to_text"
    EMBEDDING = "embedding"
    RERANK = "rerank"


@dataclass
class ProviderMeta:
    """Provider 元数据"""

    id: str
    type: str
    name: str
    provider_type: ProviderType
    cls_type: Optional[Type] = None
    description: str = ""
    supported_models: list = field(default_factory=list)
    capabilities: list = field(default_factory=list)


# Provider 注册表
_provider_cls_map: Dict[str, ProviderMeta] = {}


def register_provider_adapter(provider_type: str, description: str = ""):
    """Provider 适配器装饰器

    Args:
        provider_type: Provider 类型标识
        description: Provider 描述

    Usage:
        @register_provider_adapter("openai_chat_completion", "OpenAI API 适配器")
        class ProviderOpenAI:
            pass
    """

    def decorator(cls: Type) -> Type:
        meta = ProviderMeta(
            id=provider_type,
            type=provider_type,
            name=cls.__name__,
            provider_type=ProviderType.CHAT_COMPLETION,
            cls_type=cls,
            description=description,
        )
        _provider_cls_map[provider_type] = meta
        logger.debug(f"[ProviderRegistry] 注册 Provider: {provider_type} -> {cls.__name__}")
        return cls

    return decorator


def get_provider_meta(provider_type: str) -> Optional[ProviderMeta]:
    """获取 Provider 元数据"""
    return _provider_cls_map.get(provider_type)


def list_registered_providers() -> Dict[str, ProviderMeta]:
    """列出所有已注册的 Provider"""
    return _provider_cls_map.copy()


def clear_registry():
    """清空注册表（主要用于测试）"""
    _provider_cls_map.clear()


# 便捷函数：获取 Provider 类
def get_provider_cls(provider_type: str) -> Optional[Type]:
    """获取 Provider 类"""
    meta = _provider_cls_map.get(provider_type)
    return meta.cls_type if meta else None


# 便捷函数：获取 Provider 类型
def get_provider_type(provider_type: str) -> Optional[ProviderType]:
    """获取 Provider 类型枚举"""
    meta = _provider_cls_map.get(provider_type)
    return meta.provider_type if meta else None
