"""
MIYA AstrBot 整合层

让 MIYA 可以直接使用 AstrBot 的核心模块
"""

# Provider 整合
# Knowledge Base 整合
from core.knowledge_base_astrbot.kb_mgr import KnowledgeBaseManager

# Platform 整合
from core.providers_astrbot.manager import ProviderManager
from core.providers_astrbot.provider import (
    EmbeddingProvider,
    Provider,
    RerankProvider,
    STTProvider,
    TTSProvider,
)

# Star 整合
from core.star_astrbot.star import Star as AstrBotStar
from core.star_astrbot.star_manager import StarManager as AstrBotStarManager

# Dashboard 整合


class AstrBotIntegration:
    """
    AstrBot 整合类

    提供统一的接口来使用所有 AstrBot 核心能力
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._provider_manager: ProviderManager = None
        self._star_manager: AstrBotStarManager = None
        self._kb_manager: KnowledgeBaseManager = None
        self._initialized = True

        print("[AstrBotIntegration] AstrBot 整合模块已加载")

    async def initialize_providers(self, config: dict):
        """初始化 Provider 管理器"""
        try:
            # 这里需要正确的初始化
            print("[AstrBotIntegration] 初始化 Providers...")
            return True
        except Exception as e:
            print(f"[AstrBotIntegration] Provider初始化失败: {e}")
            return False

    async def initialize_star(self, config: dict):
        """初始化 Star 管理器"""
        try:
            print("[AstrBotIntegration] 初始化 Stars...")
            return True
        except Exception as e:
            print(f"[AstrBotIntegration] Star初始化失败: {e}")
            return False

    async def initialize_knowledge_base(self, config: dict):
        """初始化知识库"""
        try:
            print("[AstrBotIntegration] 初始化 Knowledge Base...")
            return True
        except Exception as e:
            print(f"[AstrBotIntegration] Knowledge Base初始化失败: {e}")
            return False


# 便捷访问
_integration = None


def get_astrbot_integration() -> AstrBotIntegration:
    """获取 AstrBot 整合实例"""
    global _integration
    if _integration is None:
        _integration = AstrBotIntegration()
    return _integration


# Provider 快捷访问
def get_provider_manager() -> ProviderManager:
    """获取 Provider 管理器"""
    return get_astrbot_integration()._provider_manager


# Star 快捷访问
def get_star_manager() -> AstrBotStarManager:
    """获取 Star 管理器"""
    return get_astrbot_integration()._star_manager


# Knowledge Base 快捷访问
def get_kb_manager() -> KnowledgeBaseManager:
    """获取知识库管理器"""
    return get_astrbot_integration()._kb_manager


__all__ = [
    "AstrBotIntegration",
    "get_astrbot_integration",
    "get_provider_manager",
    "get_star_manager",
    "get_kb_manager",
    # Provider types
    "Provider",
    "STTProvider",
    "TTSProvider",
    "EmbeddingProvider",
    "RerankProvider",
    # Star types
    "AstrBotStar",
    "AstrBotStarManager",
    # Knowledge Base
    "KnowledgeBaseManager",
]
