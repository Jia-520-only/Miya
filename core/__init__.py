"""
弥娅内核 - 灵魂锚点

核心子系统通过公开属性按需加载，减少轻量模块导入时的依赖耦合。
"""

_LAZY = {
    "Arbitrator": ("core.arbitrator", "Arbitrator"),
    "Entropy": ("core.entropy", "Entropy"),
    "Ethics": ("core.ethics", "Ethics"),
    "Identity": ("core.identity", "Identity"),
    "Personality": ("core.personality", "Personality"),
    "PromptManager": ("core.prompt_manager", "PromptManager"),
    "ToolAdapter": ("core.tool_adapter", "ToolAdapter"),
    "get_tool_adapter": ("core.tool_adapter", "get_tool_adapter"),
    "set_tool_adapter": ("core.tool_adapter", "set_tool_adapter"),
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
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
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
