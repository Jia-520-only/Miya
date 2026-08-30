"""
MIYA 模型池兼容层 v7.0

新系统API:
- core.model_pool_manager.ModelPoolManager (统一系统)
- core.model_pool_manager.get_model_pool()

本模块提供旧系统向后兼容
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("model_pool_compat")

# 使用新的统一系统
from core.model_pool_manager import (
    Model,
    ModelProvider,
    ModelRoute,
    ModelType,
    TaskType,
)
from core.model_pool_manager import (
    get_model_pool as _get_new_pool,
)

# ==================== 兼容函数 ====================


def get_model_pool():
    """获取模型池 (兼容旧API)"""
    return _get_new_pool()


def select_model(task: str) -> Optional[Model]:
    """根据任务选择模型"""
    return _get_new_pool().select_model(task)


def select_model_by_task(task: str) -> Optional[Model]:
    """根据任务选择模型 (兼容)"""
    return select_model(task)


def select_model_for_task(task_type: str, endpoint_id: str = None, priority: str = "balanced") -> Optional[Model]:
    """为任务选择模型"""
    return _get_new_pool().select_model_for_task(task_type, endpoint_id, priority)


def get_enabled_models(model_type: str = None) -> List[Model]:
    """获取启用的模型"""
    return _get_new_pool().get_enabled(model_type)


def get_api_key(model_id: str) -> str:
    """获取 API 密钥"""
    return _get_new_pool().get_api_key(model_id)


def get_models() -> Dict[str, Model]:
    """获取所有模型字典"""
    return _get_new_pool()._model_dict


def get_qq_model() -> Optional[Model]:
    """获取QQ模型"""
    return select_model("simple_chat")


def create_ai_client(task_type: str = "simple_chat", endpoint: str = None):
    """创建 AI 客户端 (兼容旧API)"""
    return _get_new_pool().create_ai_client(task_type=task_type, endpoint=endpoint)


# ==================== 旧系统兼容类 ====================


@dataclass
class ModelConfig:
    """模型配置 (兼容)"""

    id: str
    name: str
    type: ModelType
    provider: ModelProvider
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    cost_per_1k_tokens: Optional[Dict[str, float]] = None
    latency: str = "medium"
    quality: str = "good"
    max_tokens: int = 4096
    enabled: bool = True
    temperature: Optional[float] = None

    @classmethod
    def from_model(cls, model: Model) -> "ModelConfig":
        """从新 Model 创建兼容 ModelConfig"""
        return cls(
            id=model.id,
            name=model.name,
            type=ModelType(model.type) if model.type else ModelType.TEXT,
            provider=ModelProvider(model.provider) if model.provider else ModelProvider.OPENAI,
            base_url=model.base_url,
            api_key=get_api_key(model.id),
            description=model.description,
            capabilities=model.capabilities,
            latency=model.latency,
            quality=model.quality,
            max_tokens=model.max_tokens,
            temperature=model.temperature if hasattr(model, "temperature") else None,
            enabled=model.enabled,
        )


__all__ = [
    "get_model_pool",
    "select_model",
    "select_model_by_task",
    "select_model_for_task",
    "get_enabled_models",
    "get_api_key",
    "get_models",
    "get_qq_model",
    "create_ai_client",
    "Model",
    "ModelConfig",
    "ModelRoute",
    "TaskType",
    "ModelType",
    "ModelProvider",
]
