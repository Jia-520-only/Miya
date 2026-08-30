"""
配置加载
"""

import os
from typing import Any, Dict

from dotenv import load_dotenv

from core.path_resolver import get_config_dir
from core.version import VERSION


class Settings:
    """配置管理类"""

    def __init__(self, env_file: str = ""):
        if env_file:
            self.env_file = env_file
        else:
            self.env_file = str(get_config_dir() / ".env")
        self._config = {}
        self._load_env()

    def _load_env(self) -> None:
        """加载环境变量"""
        # 加载.env文件
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)

        # 基础配置
        self._config = {
            # 应用配置
            "app": {
                "name": "Miya",
                "version": VERSION,
                "debug": os.getenv("DEBUG", "false").lower() == "true",
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
            },
            # Redis配置
            "redis": {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", 6379)),
                "db": int(os.getenv("REDIS_DB", 0)),
                "password": os.getenv("REDIS_PASSWORD"),
            },
            # Milvus配置
            "milvus": {
                "host": os.getenv("MILVUS_HOST", "localhost"),
                "port": int(os.getenv("MILVUS_PORT", 19530)),
                "collection_name": os.getenv("MILVUS_COLLECTION", "miya_memory"),
            },
            # Neo4j配置
            "neo4j": {
                "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                "user": os.getenv("NEO4J_USER", "neo4j"),
                "password": os.getenv("NEO4J_PASSWORD"),
            },
            # 人格配置
            "personality": {
                "warmth": float(os.getenv("PERSONALITY_WARMTH", 0.8)),
                "logic": float(os.getenv("PERSONALITY_LOGIC", 0.7)),
                "creativity": float(os.getenv("PERSONALITY_CREATIVITY", 0.6)),
                "empathy": float(os.getenv("PERSONALITY_EMPATHY", 0.75)),
                "resilience": float(os.getenv("PERSONALITY_RESILIENCE", 0.7)),
            },
            # 情绪配置
            "emotion": {
                "decay_rate": float(os.getenv("EMOTION_DECAY_RATE", 0.1)),
                "coloring_threshold": float(os.getenv("EMOTION_COLORING_THRESHOLD", 0.7)),
            },
            # 信任配置
            "trust": {
                "decay_rate": float(os.getenv("TRUST_DECAY_RATE", 0.05)),
                "initial_score": float(os.getenv("TRUST_INITIAL_SCORE", 0.5)),
                "high_threshold": float(os.getenv("TRUST_HIGH_THRESHOLD", 0.7)),
                "low_threshold": float(os.getenv("TRUST_LOW_THRESHOLD", 0.3)),
            },
            # 记忆配置
            "memory": {
                "tide_ttl": int(os.getenv("MEMORY_TIDE_TTL", 3600)),
                "dream_compression_threshold": int(os.getenv("MEMORY_DREAM_THRESHOLD", 100)),
            },
            # 感知配置
            "perception": {
                "activation_rate": float(os.getenv("PERCEPTION_ACTIVATION_RATE", 0.3)),
                "intensity_threshold": float(os.getenv("PERCEPTION_INTENSITY_THRESHOLD", 0.5)),
            },
            # 检测配置
            "detection": {
                "time_loop_threshold": int(os.getenv("DETECTION_TIME_THRESHOLD", 3600)),
                "space_distance_threshold": float(os.getenv("DETECTION_SPACE_THRESHOLD", 1.0)),
            },
            # 演化配置
            "evolution": {
                "sandbox_enabled": os.getenv("SANDBOX_ENABLED", "true").lower() == "true",
                "ab_test_enabled": os.getenv("AB_TEST_ENABLED", "true").lower() == "true",
            },
            # 对话上下文配置
            "conversation": {
                "enable_conversation_context": os.getenv("CONVERSATION_CONTEXT_ENABLED", "true").lower() == "true",
                "context_max_count": int(os.getenv("CONVERSATION_CONTEXT_MAX_COUNT", "10")),
                "context_max_tokens": int(os.getenv("CONVERSATION_CONTEXT_MAX_TOKENS", "2000")),
                "response_thresholds": {
                    "high_empathy": float(os.getenv("RESPONSE_THRESHOLD_HIGH_EMPATHY", "0.8")),
                    "high_warmth": float(os.getenv("RESPONSE_THRESHOLD_HIGH_WARMTH", "0.8")),
                },
            },
            # 聊天机器人关键词配置（从text_config.json加载，此处保留环境变量回退）
            "chatbot_keywords": {
                "auto_respond_keywords": os.getenv("CHATBOT_AUTO_RESPOND_KEYWORDS", "").split(",")
                if os.getenv("CHATBOT_AUTO_RESPOND_KEYWORDS")
                else [],
                "pat_pat_trigger": os.getenv("CHATBOT_PAT_PAT_TRIGGER", ""),
            },
            # 终端任务关键词配置
            "terminal_task_keywords": {
                "think_keywords": os.getenv(
                    "TERMINAL_TASK_THINK_KEYWORDS",
                    "打开,运行,执行,创建,删除,查看,启动,安装,卸载,配置,帮我,请,能不能",
                ).split(","),
            },
            # QQ机器人配置
            "qq": self._get_qq_config(),
            # LifeBook 记忆管理配置
            "lifebook": {
                "enabled": os.getenv("LIFEBOOK_ENABLED", "true").lower() == "true",
                "base_dir": os.getenv("LIFEBOOK_BASE_DIR", "data/lifebook"),
                "auto_summary_enabled": os.getenv("LIFEBOOK_AUTO_SUMMARY", "false").lower() == "true",
                "default_months_back": int(os.getenv("LIFEBOOK_DEFAULT_MONTHS_BACK", 1)),
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点分隔的嵌套键，如 'redis.host'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def reload(self) -> None:
        """重新加载配置"""
        self._load_env()

    def get_all(self) -> Dict:
        """获取所有配置"""
        return self._config.copy()

    def update_from_dict(self, config_dict: Dict) -> None:
        """从字典更新配置"""
        for key, value in config_dict.items():
            self.set(key, value)

    def _get_qq_config(self) -> Dict:
        """获取QQ配置 - 使用统一的 QQConfigLoader"""
        try:
            from webnet.qq.config_loader import get_config_loader

            loader = get_config_loader()
            return loader.get_config()
        except Exception as e:
            print(f"[Settings] 加载QQ配置失败: {e}，使用默认配置")
            return self._get_default_qq_config()

    def _get_default_qq_config(self) -> Dict:
        """获取默认QQ配置"""
        return {
            "onebot_ws_url": "ws://localhost:3001",
            "onebot_token": "",
            "bot_qq": 0,
            "superadmin_qq": 0,
            "connection": {
                "reconnect_interval": 5.0,
                "ping_interval": 20,
                "ping_timeout": 30,
                "max_message_size": 104857600,
            },
            "access_control": {
                "enabled": False,
                "group_whitelist": [],
                "group_blacklist": [],
                "user_whitelist": [],
                "user_blacklist": [],
            },
            "multimedia": {
                "image": {
                    "max_size": 10485760,
                    "allowed_formats": [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".gif",
                        ".bmp",
                        ".webp",
                    ],
                },
                "file": {
                    "max_size": 52428800,
                },
            },
            "image_recognition": {
                "ocr": {
                    "enabled": True,
                    "engine": "auto",
                }
            },
            "active_chat": {
                "enabled": True,
                "limits": {
                    "max_daily_messages": 10,
                    "min_interval": 300,
                },
            },
            "task_scheduler": {
                "enabled": True,
            },
        }
