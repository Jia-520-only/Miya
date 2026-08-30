"""
吟美配置加载器 - 适配弥娅配置体系
支持从 config/yml or json 加载吟美特有配置
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class YinmeiConfig:
    """吟美虚拟主播配置"""

    _instance: Optional["YinmeiConfig"] = None
    _cache: Dict[str, Any] = {}

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "yinmei"
        self._config_path = config_path
        self._load_all()

    @classmethod
    def get_instance(cls) -> "YinmeiConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_all(self):
        self._load_yaml_config()
        self._load_json_config()
        self._load_from_env()

    def _load_yaml_config(self):
        yml_path = self._config_path / "yinmei.yml"
        if yml_path.exists():
            with open(yml_path, "r", encoding="utf-8") as f:
                self._cache.update(yaml.safe_load(f) or {})

    def _load_json_config(self):
        json_path = self._config_path / "yinmei.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                self._cache.update(json.load(f))

    def _load_from_env(self):
        from config.config_utils import get_api_key

        env_map = {
            "ai_name": "YINMEI_AI_NAME",
            "mode": "YINMEI_MODE",
            "port": "YINMEI_PORT",
            "obs_host": "YINMEI_OBS_HOST",
            "obs_port": "YINMEI_OBS_PORT",
            "obs_password": "YINMEI_OBS_PASSWORD",
            "obs_switch": "YINMEI_OBS_SWITCH",
            "obs_dance_path": "YINMEI_OBS_DANCE_PATH",
            "obs_emote_path": "YINMEI_OBS_EMOTE_PATH",
            "draw_url": "YINMEI_DRAW_URL",
            "sing_url": "YINMEI_SING_URL",
            "nsfw_server": "YINMEI_NSFW_SERVER",
            "tts_engine": "YINMEI_TTS_ENGINE",
            "tts_speaker": "YINMEI_TTS_SPEAKER",
            "bilibili_room_id": "YINMEI_BILI_ROOM_ID",
            "bilibili_access_key_id": "YINMEI_BILI_ACCESS_KEY_ID",
            "bilibili_access_key_secret": "YINMEI_BILI_ACCESS_KEY_SECRET",
            "bilibili_app_id": "YINMEI_BILI_APP_ID",
            "bilibili_auth_code": "YINMEI_BILI_AUTH_CODE",
            "bilibili_sessdata": "YINMEI_BILI_SESSDATA",
            "vtuber_auth_token": "YINMEI_VTUBER_AUTH_TOKEN",
            "public_sentiment_key": "YINMEI_PUBLIC_SENTIMENT_KEY",
        }
        for key, env_var in env_map.items():
            val = get_api_key(env_var)
            if val:
                self._cache[key] = val

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._cache[key]

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._cache)
