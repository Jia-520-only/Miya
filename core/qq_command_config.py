"""
QQ命令配置加载器
从统一的配置文件加载命令配置
注意：命令关键词从 text_config.json 读取，快捷响应从 text_config.json 读取
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    """从统一配置加载QQ命令配置"""
    global _config

    if _config is not None:
        return _config

    try:
        from core.text_loader import get_command_keywords, get_text

        _config = {
            "command_aliases": get_command_keywords(),
            "quick_responses": get_text("quick_responses", {}),
            "error_messages": get_text("error_messages", {}),
        }
        logger.info("QQ命令配置加载成功（从 text_config.json）")
    except Exception as e:
        logger.warning(f"加载QQ命令配置失败: {e}，使用空配置")
        _config = {}

    return _config


def reload_config():
    """重新加载配置"""
    global _config
    _config = None
    return _load_config()


def get_command_aliases(command_type: str) -> List[str]:
    """获取命令别名"""
    config = _load_config()
    return config.get("command_aliases", {}).get(command_type, [])


def match_command(content: str, command_type: str) -> bool:
    """检查内容是否匹配命令类型"""
    content_lower = content.lower().strip()

    aliases = get_command_aliases(command_type)
    for alias in aliases:
        alias_lower = alias.lower()
        if content_lower == alias_lower or content_lower.startswith(alias_lower):
            return True

    return False


def is_help_command(content: str) -> bool:
    """检查是否是帮助命令"""
    return match_command(content, "help")


def is_status_command(content: str) -> bool:
    """检查是否是状态命令"""
    return match_command(content, "status")


def is_form_command(content: str) -> bool:
    """检查是否是形态命令"""
    return match_command(content, "form")


def is_speak_command(content: str) -> bool:
    """检查是否是说话模式命令"""
    return match_command(content, "speak")


def is_exist_command(content: str) -> bool:
    """检查是否是存在性情感命令"""
    return match_command(content, "exist")


def is_voice_command(content: str) -> bool:
    """检查是否是语音切换命令"""
    return match_command(content, "voice")


def is_text_command(content: str) -> bool:
    """检查是否是文本切换命令"""
    return match_command(content, "text")


def is_memory_command(content: str) -> bool:
    """检查是否是记忆命令"""
    config = _load_config()
    memory_aliases = config.get("command_aliases", {}).get("memory", [])
    content_lower = content.lower().strip()

    return any(content_lower.startswith(alias.lower()) for alias in memory_aliases)


def get_quick_response_keywords(response_type: str) -> List[str]:
    """获取快速响应关键词"""
    config = _load_config()
    return config.get("quick_responses", {}).get(response_type, {}).get("keywords", [])


def is_greeting_keyword(content: str) -> bool:
    """检查是否是问候关键词"""
    return content.lower().strip() in [k.lower() for k in get_quick_response_keywords("greeting")]


def is_farewell_keyword(content: str) -> bool:
    """检查是否是告别关键词"""
    return content.lower().strip() in [k.lower() for k in get_quick_response_keywords("farewell")]


def get_error_message(error_type: str) -> str:
    """获取错误消息"""
    config = _load_config()
    return config.get("error_messages", {}).get(error_type, "命令执行失败")


class QQCommandConfig:
    """QQ命令配置类"""

    def __init__(self):
        self._config = _load_config()

    def match_command(self, content: str, command_type: str) -> bool:
        return match_command(content, command_type)

    def is_help(self, content: str) -> bool:
        return is_help_command(content)

    def is_status(self, content: str) -> bool:
        return is_status_command(content)

    def is_form(self, content: str) -> bool:
        return is_form_command(content)

    def is_speak(self, content: str) -> bool:
        return is_speak_command(content)

    def is_exist(self, content: str) -> bool:
        return is_exist_command(content)

    def is_voice(self, content: str) -> bool:
        return is_voice_command(content)

    def is_text(self, content: str) -> bool:
        return is_text_command(content)

    def is_memory(self, content: str) -> bool:
        return is_memory_command(content)

    def get_quick_keywords(self, response_type: str) -> List[str]:
        return get_quick_response_keywords(response_type)

    def is_greeting(self, content: str) -> bool:
        return is_greeting_keyword(content)

    def is_farewell(self, content: str) -> bool:
        return is_farewell_keyword(content)

    def get_error(self, error_type: str) -> str:
        return get_error_message(error_type)

    def reload(self):
        """重新加载"""
        reload_config()
        self._config = _load_config()


_command_config: Optional[QQCommandConfig] = None


def get_qq_command_config() -> QQCommandConfig:
    """获取QQ命令配置实例"""
    global _command_config
    if _command_config is None:
        _command_config = QQCommandConfig()
    return _command_config
