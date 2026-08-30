"""
AstrBot Provider 桥接模块

将 AstrBot 的 Provider 系统整合到 MIYA

支持的提供商类型:
- Chat Completion: OpenAI, Anthropic, Google Gemini, DeepSeek, 智谱, Moonshot, Kimi, 阿里云, Ollama, LM Studio 等
- STT: Whisper, SenseVoice, MiMo
- TTS: OpenAI TTS, Edge TTS, FishAudio, MiniMax, 火山引擎等
- Embedding: OpenAI, Gemini
- Rerank: vLLM, Xinference, Bailian, Nvidia
"""

from .bridge import AstrBotProviderBridge, get_provider_bridge

__all__ = ["AstrBotProviderBridge", "get_provider_bridge"]
