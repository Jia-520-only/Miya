"""
人格命令配置加载器
动态加载形态、说话模式等人格相关命令配置
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None


def _get_personality_dir() -> Path:
    """获取人格配置目录"""
    return Path(__file__).parent.parent / "config" / "personalities"


def _load_all_forms() -> Dict[str, Any]:
    """加载所有形态配置"""
    forms = {}
    personality_dir = _get_personality_dir()

    if not personality_dir.exists():
        return forms

    for yaml_file in personality_dir.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue

        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                form_data = yaml.safe_load(f)
                if form_data and "name" in form_data:
                    forms[yaml_file.stem] = form_data
        except Exception as e:
            logger.warning(f"加载形态配置失败 {yaml_file}: {e}")

    return forms


def _load_base_config() -> Dict[str, Any]:
    """加载基础配置"""
    base_file = _get_personality_dir() / "_base.yaml"

    if base_file.exists():
        try:
            with open(base_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"加载基础配置失败: {e}")

    return {}


def _load_default_form() -> Dict[str, Any]:
    """加载默认形态配置"""
    default_file = _get_personality_dir() / "normal.yaml"

    if default_file.exists():
        try:
            with open(default_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"加载默认形态失败: {e}")

    return {}


def get_available_forms() -> List[str]:
    """获取所有可用形态"""
    forms = _load_all_forms()
    return list(forms.keys())


def get_available_core_forms() -> List[str]:
    """获取所有可用核心形态"""
    base = _load_base_config()
    core_traits = base.get("core_traits", {})
    return list(core_traits.keys())


def get_available_speak_modes() -> List[str]:
    """获取所有可用说话模式"""
    base = _load_base_config()
    speak_modes = base.get("speaking_modes", {})
    return list(speak_modes.keys()) if speak_modes else ["casual", "catching", "confiding"]


def get_form_info(form_name: str) -> Optional[Dict[str, Any]]:
    """获取形态详细信息"""
    forms = _load_all_forms()
    return forms.get(form_name)


def get_form_description(form_name: str) -> str:
    """获取形态描述"""
    form_info = get_form_info(form_name)
    if form_info:
        return form_info.get("description", "")
    return ""


def get_form_speaking_style(form_name: str) -> str:
    """获取形态的说话风格"""
    form_info = get_form_info(form_name)
    if form_info:
        return form_info.get("speaking", {}).get("style", "")
    return ""


def format_forms_list() -> str:
    """格式化形态列表为字符串"""
    forms = get_available_forms()
    if not forms:
        return "暂无可用形态"
    return ", ".join(forms)


def format_core_forms_list() -> str:
    """格式化核心形态列表为字符串"""
    forms = get_available_core_forms()
    if not forms:
        return "暂无可用核心形态"
    return ", ".join(forms)


def format_speak_modes_list() -> str:
    """格式化说话模式列表为字符串"""
    modes = get_available_speak_modes()
    if not modes:
        return "casual闲聊/catching捕捉/confiding倾诉"

    descriptions = {"casual": "闲聊", "catching": "捕捉", "confiding": "倾诉"}

    return "/".join([f"{m}{descriptions.get(m, '')}" for m in modes])


def is_valid_form(form_name: str) -> bool:
    """检查是否是有效形态"""
    return form_name in get_available_forms()


def is_valid_core_form(form_name: str) -> bool:
    """检查是否是有效核心形态"""
    return form_name in get_available_core_forms()


def is_valid_speak_mode(mode: str) -> bool:
    """检查是否是有效说话模式"""
    return mode in get_available_speak_modes()


def get_current_form_info(personality_profile: Dict) -> Dict[str, str]:
    """从人格配置中获取当前形态信息"""
    current_form = personality_profile.get("current_form", "normal")
    form_info = personality_profile.get("form_info", {})
    current_core_form = personality_profile.get("current_core_form", "")

    return {
        "current_form": current_form,
        "form_name": form_info.get("name", "常态"),
        "form_description": form_info.get("description", ""),
        "current_core_form": current_core_form,
    }


class PersonalityCommandConfig:
    """人格命令配置类"""

    def __init__(self):
        self._forms = _load_all_forms()
        self._base = _load_base_config()
        self._default = _load_default_form()

    def get_forms(self) -> List[str]:
        return list(self._forms.keys())

    def get_core_forms(self) -> List[str]:
        return list(self._base.get("core_traits", {}).keys())

    def get_speak_modes(self) -> List[str]:
        return list(self._base.get("speaking_modes", {}).keys()) or [
            "casual",
            "catching",
            "confiding",
        ]

    def format_forms(self) -> str:
        return format_forms_list()

    def format_core_forms(self) -> str:
        return format_core_forms_list()

    def format_speak_modes(self) -> str:
        return format_speak_modes_list()

    def is_valid_form(self, name: str) -> bool:
        return is_valid_form(name)

    def is_valid_core_form(self, name: str) -> bool:
        return is_valid_core_form(name)

    def is_valid_speak_mode(self, mode: str) -> bool:
        return is_valid_speak_mode(mode)

    def get_form_description(self, name: str) -> str:
        return get_form_description(name)

    def reload(self):
        """重新加载配置"""
        self._forms = _load_all_forms()
        self._base = _load_base_config()
        self._default = _load_default_form()


_command_config: Optional[PersonalityCommandConfig] = None


def get_personality_command_config() -> PersonalityCommandConfig:
    """获取人格命令配置实例"""
    global _command_config
    if _command_config is None:
        _command_config = PersonalityCommandConfig()
    return _command_config
