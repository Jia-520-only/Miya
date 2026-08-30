#!/usr/bin/env python3
"""
弥娅陪伴插件 - Miya Companion
专属技能：情感陪伴、倾听、鼓励
从 YAML 配置文件加载回应消息
"""

import random
import time
from typing import Any, Dict


class MiyaCompanion:
    """弥娅陪伴技能 - 情感支持"""

    def __init__(self):
        self.name = "miya_companion"
        self.description = "弥娅陪伴 - 情感支持、倾听、鼓励"

        self._config = self._load_config()

    def _load_config(self) -> Dict:
        """从 personality loader 获取配置"""
        try:
            from core.personality_loader import get_personality_loader

            loader = get_personality_loader()
            config = loader.load("_default")
            return config
        except Exception:
            return {}

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """处理陪伴请求"""
        action = tool_call.get("action", "")
        message = tool_call.get("message", "")
        tool_call.get("emotion", "")

        if action == "comfort":
            return self._comfort(message)
        elif action == "encourage":
            return self._encourage()
        elif action == "listen":
            return self._listen(message)
        elif action == "check_in":
            return self._check_in()
        else:
            return self._default_response(message)

    def _comfort(self, message: str) -> str:
        """安慰"""
        responses = self._config.get("comfort_responses", [])
        if not responses:
            return ""  # 动态生成将处理空响应
        return random.choice(responses)

    def _encourage(self) -> str:
        """鼓励"""
        responses = self._config.get("encourage_responses", [])
        if not responses:
            return ""  # 动态生成将处理空响应
        return random.choice(responses)

    def _listen(self, message: str) -> str:
        """倾听"""
        responses = self._config.get("listen_responses", [])
        if not responses:
            return ""  # 动态生成将处理空响应
        return random.choice(responses)

    def _check_in(self) -> str:
        """日常关怀"""
        hour = time.localtime().tm_hour
        check_in = self._config.get("check_in_responses", {})
        if hour >= 22 or hour < 6:
            response = check_in.get("night", "")
        elif 6 <= hour < 12:
            response = check_in.get("morning", "")
        else:
            response = check_in.get("day", "")

        if not response:
            return ""  # 动态生成将处理空响应
        return response

    def _default_response(self, message: str) -> str:
        """默认响应"""
        responses = self._config.get("default_responses", [])
        if not responses:
            return ""  # 动态生成将处理空响应
        return random.choice(responses)


skill = MiyaCompanion()
