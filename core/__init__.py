"""
弥娅内核 - 灵魂锚点

核心子系统始终立即加载；AI 客户端类按需懒加载，减少启动开销。
"""

from .arbitrator import Arbitrator
from .entropy import Entropy
from .ethics import Ethics
from .identity import Identity
from .personality import Personality
from .prompt_manager import PromptManager
from .tool_adapter import ToolAdapter, get_tool_adapter, set_tool_adapter

_LAZY = {
    "AIClientFactory": ("core.ai_client", "AIClientFactory"),
    "AIMessage": ("core.ai_client", "AIMessage"),
    "AnthropicClient": ("core.ai_client", "AnthropicClient"),
    "DeepSeekClient": ("core.ai_client", "DeepSeekClient"),
    "OpenAIClient": ("core.ai_client", "OpenAIClient"),
    "ZhipuAIClient": ("core.ai_client", "ZhipuAIClient"),
}


def __getattr__(name):
    if name in _LAZY:
        mod_path, attr_name = _LAZY[name]
        import importlib

        module = importlib.import_module(mod_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Personality",
    "Ethics",
    "Identity",
    "Arbitrator",
    "Entropy",
    "PromptManager",
    "AIClientFactory",
    "OpenAIClient",
    "DeepSeekClient",
    "AnthropicClient",
    "ZhipuAIClient",
    "AIMessage",
    "get_tool_adapter",
    "set_tool_adapter",
    "ToolAdapter",
]
