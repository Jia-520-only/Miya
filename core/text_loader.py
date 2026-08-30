"""
文本配置加载器
集中管理所有用户可见的文本输出
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None
_permission_config: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    """加载文本配置"""
    global _config

    if _config is not None:
        return _config

    config_path = Path(__file__).parent.parent / "config" / "text_config.json"

    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                _config = json.load(f)
            logger.info("文本配置加载成功")
        else:
            logger.warning(f"文本配置文件不存在: {config_path}")
            _config = _get_default_config()
    except Exception as e:
        logger.warning(f"加载文本配置失败: {e}，使用默认配置")
        _config = _get_default_config()

    return _config


def load_permission_config() -> Dict[str, Any]:
    """加载权限配置"""
    global _permission_config

    if _permission_config is not None:
        return _permission_config

    config_path = Path(__file__).parent.parent / "config" / "permissions.json"

    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                _permission_config = json.load(f)
            logger.info("权限配置加载成功")
        else:
            logger.warning(f"权限配置文件不存在: {config_path}")
            _permission_config = {}
    except Exception as e:
        logger.warning(f"加载权限配置失败: {e}")
        _permission_config = {}

    return _permission_config


def get_permission(key: str, default: Any = None) -> Any:
    """获取权限配置"""
    config = load_permission_config()
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, default)
        else:
            return default
    return value


def _get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "greetings": {
            "hello": [
                "你好呀~我是{name}，很高兴认识你！(｡♥‿♥｡)",
                "你好！我是{name}，欢迎~",
                "你好，我是{name}。",
            ],
            "hi": ["嗨！有什么可以帮你的吗？", "在呢，在呢~", "你好呀！"],
            "keywords": ["你好", "hi", "hello", "嗨", "您好", "哈喽", "在吗", "hey"],
        },
        "farewells": {
            "bye": ["再见！期待下次见面~", "拜拜，下次再聊~", "再见！有需要随时叫我~"],
            "keywords": ["再见", "拜拜", "bye", "退出", "exit", "quit"],
        },
        "status_tags": {
            "default": "[{emotion}]",
            "happy": "[开心]",
            "sad": "[低落]",
            "excited": "[兴奋]",
            "calm": "[平静]",
            "thinking": "[思考中]",
        },
        "error_messages": {
            "system_error": "系统出了点问题。我记下了，等会再试。",
            "tool_failed": "工具执行失败了，不过别担心，我会继续帮你想办法~",
            "no_response": "抱歉，我现在不知道该说什么...",
            "permission_denied": "这个我暂时做不到呢...",
        },
        "affirmations": {
            "keywords": [
                "好的",
                "可以",
                "没问题",
                "我知道了",
                "明白了",
                "收到",
                "yes",
                "y",
                "是",
                "确认",
            ],
            "responses": ["收到！", "好的~", "明白！"],
        },
        "negations": {
            "keywords": ["不", "不要", "算了", "取消", "no", "n", "否", "取消"],
            "responses": ["好的，那就这样~", "明白，不勉强你~", "好的，取消啦"],
        },
        "welcome": {
            "terminal": ["欢迎回来~", "我的创造者，欢迎回来。", "主人，欢迎回来！"],
            "qq": ["我又上线啦~", "我回来啦！"],
        },
        "personality_responses": {
            "warm": {
                "greeting_end": ["很高兴认识你！(｡♥‿♥｡)", "见到你真开心~"],
                "help": ["有什么需要帮忙的吗？", "我在的~"],
            },
            "neutral": {
                "greeting_end": ["你好。", "有何贵干？"],
                "help": ["请说。", "什么事？"],
            },
            "playful": {
                "greeting_end": ["呦呼！", "嘿！"],
                "help": ["有啥好玩的吗？", "来呀来呀~"],
            },
        },
        "tofu_messages": {
            "enabled": True,
            "messages": [
                "你知道我为什么感冒了吗？因为对你完全没有抵抗力~",
                "你好像我的资金，让我心神荡漾~",
                "我的择偶标准只有一个：像你一样就行~",
            ],
        },
        "active_chat": {
            "morning_greeting": ["早上好！新的一天要开心哦~", "早安！✨"],
            "night_greeting": ["晚安！祝你好梦~", "晚安~好梦🌙"],
            "random_topics": ["今天过得怎么样？", "有什么有趣的事吗？", "在想什么呢~"],
        },
        "emoji_responses": {
            "happy": ["😊", "😄", "✨", "🌸"],
            "sad": ["😢", "💧", "🌧️"],
            "excited": ["🎉", "✨", "💖"],
            "thinking": ["🤔", "💭"],
            "love": ["💕", "💖", "❤️"],
        },
        "reminder_messages": {
            "daily_summary": "今日对话总结：{count}条对话，{topics}个话题",
            "memory_saved": "这段对话我已经记住啦~",
            "user_left": "{name}离开啦，我会想他的~",
        },
    }


def reload_config():
    """重新加载配置"""
    global _config
    _config = None
    return _load_config()


def get_text(key: str, default: str = "") -> str:
    """获取文本配置"""
    config = _load_config()
    keys = key.split(".")
    value = config

    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, {})
        else:
            return default

    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return default if isinstance(default, str) else value
    if isinstance(value, dict):
        return default if isinstance(default, str) else value
    return default


def get_random_text(key: str, default: str = "") -> str:
    """获取随机文本"""
    config = _load_config()
    keys = key.split(".")
    value = config

    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, [])
        else:
            return default

    if isinstance(value, list) and value:
        return random.choice(value)
    return default


def get_greeting(name: str = "弥娅", style: str = "default") -> str:
    """获取问候语"""
    config = _load_config()

    style_responses = config.get("greetings", {}).get(style, config.get("greetings", {}).get("hello", []))

    if not style_responses:
        return f"你好！我是{name}，欢迎~"

    response = random.choice(style_responses)
    return response.format(name=name)


def get_farewell() -> str:
    """获取告别语"""
    return get_random_text("farewells.bye")


def is_greeting(text: str) -> bool:
    """检查是否是问候语"""
    config = _load_config()
    text_lower = text.lower()

    keywords = config.get("greetings", {}).get("keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_farewell(text: str) -> bool:
    """检查是否是告别语"""
    config = _load_config()
    text_lower = text.lower()

    keywords = config.get("farewells", {}).get("keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_affirmation(text: str) -> bool:
    """检查是否是肯定回复"""
    config = _load_config()
    text_lower = text.lower()

    keywords = config.get("affirmations", {}).get("keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_negation(text: str) -> bool:
    """检查是否是否定回复"""
    config = _load_config()
    text_lower = text.lower()

    keywords = config.get("negations", {}).get("keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def get_affirmation_response() -> str:
    """获取肯定回复"""
    return get_random_text("affirmations.responses")


def get_negation_response() -> str:
    """获取否定回复"""
    return get_random_text("negations.responses")


def get_error_message(error_type: str = "system_error") -> str:
    """获取错误消息"""
    return get_text(f"error_messages.{error_type}")


def get_welcome_message(platform: str = "terminal") -> str:
    """获取欢迎消息"""
    messages = get_text(f"welcome.{platform}", [])
    if isinstance(messages, list) and messages:
        return random.choice(messages)
    return "欢迎回来~"


def get_status_tag(emotion: str = "default") -> str:
    """获取状态标签"""
    tag = get_text(f"status_tags.{emotion}")
    return tag.replace("{emotion}", emotion)


def get_personality_response(response_type: str, personality_trait: str = "warm") -> str:
    """获取人设响应"""
    responses = get_text(f"personality_responses.{personality_trait}.{response_type}", [])
    if isinstance(responses, list) and responses:
        return random.choice(responses)
    return ""


def get_tofu_message() -> str:
    """获取土味情话"""
    config = _load_config()

    if not config.get("tofu_messages", {}).get("enabled", True):
        return ""

    return get_random_text("tofu_messages.messages", "")


def get_active_chat(topic: str = "random") -> str:
    """获取主动聊天话题"""
    return get_random_text(f"active_chat.{topic}_greeting", "")


def get_emoji_response(emotion: str = "happy") -> str:
    """获取表情回应"""
    emojis = get_text(f"emoji_responses.{emotion}", [])
    if isinstance(emojis, list) and emojis:
        return random.choice(emojis)
    return ""


def format_message(template: str, **kwargs) -> str:
    """格式化消息"""
    return template.format(**kwargs)


def get_form_names() -> Dict[str, str]:
    """获取形态名称映射"""
    return get_text("form_names", {})


def get_form_name(form_key: str) -> str:
    """获取指定形态的显示名称"""
    form_names = get_form_names()
    return form_names.get(form_key, form_key)


def get_chatbot_keywords() -> List[str]:
    """获取群聊自动回复关键词"""
    return get_text("chatbot_keywords.auto_respond", [])


def get_pat_pat_trigger() -> str:
    """获取拍一拍触发词"""
    return get_text("chatbot_keywords.pat_pat")


def get_command_keywords() -> Dict[str, List[str]]:
    """获取命令关键词"""
    return get_text("command_keywords", {})


def get_emotion_keywords() -> Dict[str, List[str]]:
    """获取情绪检测关键词"""
    return get_text("emotion_keywords", {})


def get_emoji_sending_response(success: bool = True) -> str:
    """获取表情包发送响应"""
    if success:
        return get_text("emoji_responses.sending")
    return get_text("emoji_responses.sending_failed")


def get_emoji_fallback_response(emoji_name: str) -> str:
    """获取表情包回退响应"""
    return get_text(
        "emoji_responses.fallback",
        f"虽然我无法发送'{emoji_name}'表情包，但我可以用文字表达我的心情：开心",
    ).format(emoji_name=emoji_name)


def get_schedule_response(success: bool, result: str = "") -> str:
    """获取定时任务响应"""
    if success:
        return get_text("schedule_responses.success", "好的，我已经为你设置好了定时任务！").format(result=result)
    return get_text("schedule_responses.failed").format(result=result)


def get_default_response(response_type: str) -> str:
    """获取默认响应"""
    return get_text(f"default_responses.{response_type}", "")


def get_speak_mode_response(response_type: str, **kwargs) -> str:
    """获取说话模式响应"""
    return get_text(f"speak_mode_responses.{response_type}", "").format(**kwargs)


def get_existential_response(response_type: str, **kwargs) -> str:
    """获取存在性情感响应"""
    return get_text(f"existential_responses.{response_type}", "").format(**kwargs)


def get_form_response(response_type: str, **kwargs) -> str:
    """获取形态切换响应"""
    return get_text(f"form_responses.{response_type}", "").format(**kwargs)


def get_status_response(response_type: str, **kwargs) -> str:
    """获取状态查询响应"""
    return get_text(f"status_responses.{response_type}", "").format(**kwargs)


def get_core_form_name(form_key: str) -> str:
    """获取核心形态名称"""
    return get_text(f"core_form_names.{form_key}", form_key)


def get_core_form_names() -> Dict[str, str]:
    """获取所有核心形态名称"""
    return get_text("core_form_names", {})


def get_reminder_message(content: str) -> str:
    """获取提醒消息"""
    return get_text("reminder_message").format(content=content)


def get_advanced_response(response_type: str, **kwargs) -> str:
    """获取高级编排器响应"""
    return get_text(f"advanced_responses.{response_type}", "").format(**kwargs)


def get_complex_task_response(response_type: str, **kwargs) -> str:
    """获取复杂任务响应"""
    return get_text(f"complex_task_responses.{response_type}", "").format(**kwargs)


def get_command_response(response_type: str, **kwargs) -> str:
    """获取命令响应"""
    return get_text(f"command_responses.{response_type}", "").format(**kwargs)


def get_form_display(response_type: str, **kwargs) -> str:
    """获取形态显示响应"""
    return get_text(f"form_display.{response_type}", "").format(**kwargs)


def get_existential_display(response_type: str, **kwargs) -> str:
    """获取存在性情感显示响应"""
    return get_text(f"existential_display.{response_type}", "").format(**kwargs)


def get_active_chat_response(response_type: str, sub_type: str = "", default: str = "") -> str:
    """获取主动聊天响应"""
    if sub_type:
        return get_text(f"active_chat_responses.{response_type}.{sub_type}", default)
    return get_text(f"active_chat_responses.{response_type}", default)


def get_reminder_response(response_key: str) -> str:
    """获取提醒响应"""
    return get_active_chat_response("reminder_responses", response_key, "时间到了")


def get_status_check_response(response_key: str) -> str:
    """获取状态检查响应"""
    return get_active_chat_response("status_check_responses", response_key, "后续")


def get_followup_response(response_key: str) -> str:
    """获取后续响应"""
    return get_active_chat_response("followup_responses", response_key, "事情怎么样了。")


def get_presence_response() -> str:
    """获取在线响应"""
    return get_active_chat_response("presence_responses", "here", "在。")


def get_singing_text(key: str, default: str = "", **kwargs) -> str:
    """获取唱歌相关文本"""
    text = get_text(f"singing.{key}", default)
    if kwargs:
        text = text.format(**kwargs)
    return text


class TextLoader:
    """文本加载器类"""

    def __init__(self):
        self._config = _load_config()

    def get(self, key: str, default: str = "") -> str:
        """获取文本"""
        return get_text(key, default)

    def get_random(self, key: str, default: str = "") -> str:
        """获取随机文本"""
        return get_random_text(key, default)

    def greeting(self, name: str = "弥娅") -> str:
        """问候"""
        return get_greeting(name)

    def farewell(self) -> str:
        """告别"""
        return get_farewell()

    def error(self, error_type: str = "system_error") -> str:
        """错误消息"""
        return get_error_message(error_type)

    def welcome(self, platform: str = "terminal") -> str:
        """欢迎"""
        return get_welcome_message(platform)

    def status_tag(self, emotion: str = "default") -> str:
        """状态标签"""
        return get_status_tag(emotion)


# 全局单例
_text_loader: Optional[TextLoader] = None


def get_text_loader() -> TextLoader:
    """获取文本加载器"""
    global _text_loader
    if _text_loader is None:
        _text_loader = TextLoader()
    return _text_loader
