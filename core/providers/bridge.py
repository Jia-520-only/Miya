"""
AstrBot Provider 桥接模块

将 AstrBot 的 Provider 系统整合到 MIYA

支持的提供商类型（通过统一的接口）:
- Chat Completion: OpenAI, Anthropic, Google Gemini, DeepSeek, 智谱, Moonshot, Kimi, 阿里云百炼, Dify, Coze, Ollama, LM Studio 等
- STT: Whisper, SenseVoice, MiMo
- TTS: OpenAI TTS, Edge TTS, FishAudio, MiniMax, 火山引擎, Genie 等
- Embedding: OpenAI, Gemini
- Rerank: vLLM, Xinference, Bailian, Nvidia
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Provider类型枚举"""

    CHAT_COMPLETION = "chat_completion"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    EMBEDDING = "embedding"
    RERANK = "rerank"


@dataclass
class ProviderConfig:
    """Provider配置"""

    id: str
    type: str
    provider_type: ProviderType = ProviderType.CHAT_COMPLETION
    enable: bool = True
    name: str = ""
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatResponse:
    """聊天响应"""

    content: str
    tool_calls: Optional[List[Dict]] = None
    usage: Optional[Dict[str, int]] = None
    model: str = ""


@dataclass
class TTSResponse:
    """TTS响应"""

    audio_path: str


class BaseProvider:
    """Provider基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    async def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """聊天接口"""
        raise NotImplementedError

    async def chat_stream(self, messages: List[ChatMessage], **kwargs):
        """流式聊天接口"""
        raise NotImplementedError

    async def text_to_speech(self, text: str) -> TTSResponse:
        """文本转语音"""
        raise NotImplementedError

    async def speech_to_text(self, audio_path: str) -> str:
        """语音转文本"""
        raise NotImplementedError

    async def get_embedding(self, text: str) -> List[float]:
        """获取嵌入"""
        raise NotImplementedError

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入"""
        raise NotImplementedError


class AstrBotProviderBridge:
    """
    AstrBot Provider 桥接器

    提供统一的接口来调用多种模型服务
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

        self._providers: Dict[str, BaseProvider] = {}
        self._provider_configs: Dict[str, ProviderConfig] = {}
        self._initialized = True

        logger.info("[AstrBotProviderBridge] Provider桥接器初始化完成")

    def register_provider(self, provider_id: str, provider: BaseProvider, config: ProviderConfig):
        """注册Provider"""
        self._providers[provider_id] = provider
        self._provider_configs[provider_id] = config
        logger.info(f"[AstrBotProviderBridge] 已注册 Provider: {provider_id}")

    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """获取Provider"""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[str]:
        """列出所有Provider"""
        return list(self._providers.keys())

    async def chat(self, provider_id: str, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """发送聊天请求"""
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} 不存在")
        return await provider.chat(messages, **kwargs)

    async def chat_stream(self, provider_id: str, messages: List[ChatMessage], **kwargs):
        """流式聊天"""
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} 不存在")
        async for chunk in provider.chat_stream(messages, **kwargs):
            yield chunk

    def get_available_models(self) -> Dict[str, List[str]]:
        """获取可用模型列表"""
        models = {}
        for provider_id, config in self._provider_configs.items():
            if config.model:
                if provider_id not in models:
                    models[provider_id] = []
                models[provider_id].append(config.model)
        return models


def get_provider_bridge() -> AstrBotProviderBridge:
    """获取Provider桥接器实例"""
    return AstrBotProviderBridge()


# 支持的Provider类型映射（用于配置）
PROVIDER_TYPE_MAP = {
    # Chat Completion
    "openai_chat_completion": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "anthropic_chat_completion": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "googlegenai_chat_completion": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "deepseek_chat_completion": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "zhipu_chat_completion": {
        "name": "智谱AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "kimi_chat_completion": {
        "name": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "groq_chat_completion": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "openrouter_chat_completion": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "dashscope_chat_completion": {
        "name": "阿里云百炼",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    "ollama_chat_completion": {
        "name": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "type": ProviderType.CHAT_COMPLETION,
    },
    # TTS
    "openai_tts_api": {
        "name": "OpenAI TTS",
        "base_url": "https://api.openai.com/v1",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    "edge_tts": {
        "name": "Edge TTS",
        "base_url": "",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    "fishaudio_tts_api": {
        "name": "FishAudio TTS",
        "base_url": "https://api.fishaudio.com/v1",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    "minimax_tts_api": {
        "name": "MiniMax TTS",
        "base_url": "https://api.minimax.chat/v1",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    "volcengine_tts": {
        "name": "火山引擎 TTS",
        "base_url": "https://openspeech.bytedance.com/api/v2",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    "dashscope_tts": {
        "name": "阿里云百炼 TTS",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "type": ProviderType.TEXT_TO_SPEECH,
    },
    # STT
    "openai_whisper_api": {
        "name": "OpenAI Whisper",
        "base_url": "https://api.openai.com/v1",
        "type": ProviderType.SPEECH_TO_TEXT,
    },
    "sensevoice_stt_selfhost": {
        "name": "SenseVoice (自托管)",
        "base_url": "http://localhost:8080",
        "type": ProviderType.SPEECH_TO_TEXT,
    },
    "mimo_stt_api": {
        "name": "小米 MiMo STT",
        "base_url": "https://api.minimax.chat/v1",
        "type": ProviderType.SPEECH_TO_TEXT,
    },
    # Embedding
    "openai_embedding": {
        "name": "OpenAI Embedding",
        "base_url": "https://api.openai.com/v1",
        "type": ProviderType.EMBEDDING,
    },
    "gemini_embedding": {
        "name": "Google Gemini Embedding",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "type": ProviderType.EMBEDDING,
    },
    # Rerank
    "vllm_rerank": {
        "name": "vLLM Rerank",
        "base_url": "http://localhost:8000/v1",
        "type": ProviderType.RERANK,
    },
    "xinference_rerank": {
        "name": "Xinference Rerank",
        "base_url": "http://localhost:9997",
        "type": ProviderType.RERANK,
    },
}
