#!/usr/bin/env python3
"""
MIYA 统一模型池管理器 v7.0

功能：
- 从 multi_model_config.json 加载完整配置
- 任务分类 (LLM + 关键词)
- 高级路由策略 (primary/secondary/fallback)
- AI 客户端动态创建
- 使用统计和成本计算
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from config.config_utils import get_api_key

logger = logging.getLogger("model_pool_manager")

# 本地端点可用性探测缓存：{base_url: (时间戳, 是否可用)}
_LOCAL_PROBE_CACHE: Dict[str, Tuple[float, bool]] = {}
_LOCAL_PROBE_TTL = 10.0
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")

# 本地模型按需拉起（像云端 API 一样随叫随用）：{base_url: 上次尝试时间}
_LOCAL_AUTOSTART_ATTEMPT: Dict[str, float] = {}
_LOCAL_AUTOSTART_COOLDOWN = 120.0

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

if not os.environ.get("_MIYA_DOTENV_LOADED"):
    load_dotenv(CONFIG_DIR / ".env")


# ==================== 枚举定义 ====================


class TaskType(str, Enum):
    SIMPLE_CHAT = "simple_chat"
    COMPLEX_REASONING = "complex_reasoning"
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    TOOL_CALLING = "tool_calling"
    CREATIVE_WRITING = "creative_writing"
    CHINESE_UNDERSTANDING = "chinese_understanding"
    SUMMARIZATION = "summarization"
    MULTIMODAL = "multimodal"
    TASK_PLANNING = "task_planning"


class ModelType(str, Enum):
    TEXT = "text"
    VISION = "vision"
    OCR = "ocr"
    EMBEDDING = "embedding"
    MULTIMODAL = "multimodal"
    SAFETY = "safety"


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    ZHIPU = "zhipu"
    AZURE = "azure"
    LOCAL = "local"


PROVIDER_ENV_MAP = {
    "deepseek": "DEEPSEEK_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "openai": "OPENAI_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "grok": "GROK_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
}


def resolve_api_key_by_provider(provider: str, env_key: str = "") -> str:
    """根据 provider 名称解析 API Key（唯一真相源）
    - 优先使用显式指定的 env_key
    - 其次查 PROVIDER_ENV_MAP
    - 再次尝试全局兜底 MIYA_AI_KEY
    - 最后尝试 {provider.upper()}_API_KEY 命名约定
    - 返回空字符串表示未找到
    """
    if env_key:
        key = get_api_key(env_key)
        if key:
            return key
    mapped_key = PROVIDER_ENV_MAP.get(provider.lower(), "")
    if mapped_key:
        key = get_api_key(mapped_key)
        if key:
            return key
    global_key = get_api_key("MIYA_AI_KEY")
    if global_key:
        return global_key
    fallback_key = get_api_key(f"{provider.upper()}_API_KEY")
    if fallback_key:
        return fallback_key
    return ""


# ==================== 数据类 ====================


@dataclass
class Model:
    id: str
    name: str
    provider: str
    base_url: str
    env_key: str = ""
    api_key: str = ""
    type: str = "chat"
    capabilities: List[str] = field(default_factory=list)
    cost_input: float = 0.0
    cost_output: float = 0.0
    latency: str = "medium"
    quality: str = "good"
    priority: int = 5
    dimension: int = 0
    enabled: bool = False
    max_tokens: int = 4096
    description: str = ""
    temperature: Optional[float] = None


@dataclass
class ModelConfig:
    id: str
    name: str
    type: str
    provider: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    cost_per_1k_tokens: Optional[Dict[str, float]] = None
    latency: str = "medium"
    quality: str = "good"
    max_tokens: int = 4096


@dataclass
class ModelRoute:
    task_type: str = ""
    primary: str = ""
    secondary: str = ""
    third: str = ""
    fallback: str = ""


# ==================== 核心类 ====================


class ModelPoolManager:
    """
    统一模型池管理器
    """

    _instance: Optional["ModelPoolManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config: Dict = {}
        self._models: Dict[str, Model] = {}
        self._routes: Dict[str, ModelRoute] = {}
        self._task_classification: Dict = {}
        self._usage_stats: Dict[str, Dict] = {}

        self._initialized = True
        self._load_config()

    @classmethod
    def get_instance(cls) -> "ModelPoolManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self):
        """加载 multi_model_config.json"""
        json_path = CONFIG_DIR / "multi_model_config.json"

        if not json_path.exists():
            logger.error("[ModelPoolManager] multi_model_config.json 不存在")
            self._set_default_config()
            return

        try:
            with open(json_path, encoding="utf-8") as f:
                config = json.load(f)
            logger.info("[ModelPoolManager] 从 multi_model_config.json 加载配置")
            self._parse_config(config)
        except Exception as e:
            logger.error(f"[ModelPoolManager] 加载配置失败: {e}")
            self._set_default_config()

    def _parse_config(self, config: Dict):
        """解析配置"""
        # 解析路由
        routing_data = config.get("routing_strategy", {}) or config.get("routing", {})
        for task_type, route_data in routing_data.items():
            if isinstance(route_data, list):
                route = ModelRoute(
                    task_type=task_type,
                    primary=route_data[0] if len(route_data) > 0 else "",
                    secondary=route_data[1] if len(route_data) > 1 else "",
                    third=route_data[2] if len(route_data) > 2 else "",
                    fallback=route_data[-1] if route_data else "",
                )
            else:
                route = ModelRoute(
                    task_type=task_type,
                    primary=route_data.get("primary", ""),
                    secondary=route_data.get("secondary", ""),
                    third=route_data.get("third", ""),
                    fallback=route_data.get("fallback", ""),
                )
            self._routes[task_type] = route

        # 解析 @active 引用：将路由中的 "@active" 替换为当前激活模型
        active_model = config.get("active", "")
        if active_model:
            for route in self._routes.values():
                for field in ("primary", "secondary", "third", "fallback"):
                    if getattr(route, field) == "@active":
                        setattr(route, field, active_model)

            # 解析 system_defaults 中的 @active 引用
            sd = config.get("system_defaults", {})
            for key in ("default_model", "soul_model"):
                if sd.get(key) == "@active":
                    sd[key] = active_model

        # 解析模型
        models_data = config.get("models", {})
        for model_id, model_conf in models_data.items():
            api_key = model_conf.get("api_key", "")
            env_key = model_conf.get("env_key", "")
            if env_key and not api_key:
                api_key = os.getenv(env_key, "")

            priority = model_conf.get("priority", 5)
            if "model_defaults" in model_conf:
                priority = model_conf["model_defaults"].get("priority", 5)

            max_tokens = model_conf.get("max_tokens", 4096)
            if max_tokens == 4096 and "model_defaults" in model_conf:
                max_tokens = model_conf["model_defaults"].get("max_tokens", 4096)

            disabled = model_conf.get("disabled", False)
            provider = model_conf.get("provider", "openai")
            base_url = model_conf.get("base_url", "")
            # Local OpenAI-compatible servers often do not require a real API key.
            local_without_key = str(provider or "").lower() in {"local_llama", "ollama", "local"}
            if not local_without_key:
                try:
                    local_without_key = (urlparse(str(base_url).strip()).hostname or "").lower() in _LOCAL_HOSTS
                except Exception:
                    local_without_key = False
            model = Model(
                id=model_id,
                name=model_conf.get("name", ""),
                provider=provider,
                base_url=base_url,
                env_key=env_key,
                api_key=api_key,
                type=model_conf.get("type", "chat"),
                capabilities=model_conf.get("capabilities", []),
                cost_input=model_conf.get("cost_per_1k_tokens", {}).get("input", 0.0),
                cost_output=model_conf.get("cost_per_1k_tokens", {}).get("output", 0.0),
                latency=model_conf.get("latency", "medium"),
                quality=model_conf.get("quality", "good"),
                priority=priority,
                dimension=model_conf.get("dimension", 0),
                max_tokens=max_tokens,
                description=model_conf.get("description", ""),
                temperature=model_conf.get("temperature"),
                enabled=(bool(api_key) or local_without_key) and not disabled,
            )
            self._models[model_id] = model

        # 保存完整配置
        self._config = config

        # 加载任务分类
        try:
            task_config_path = CONFIG_DIR / "text_config.json"
            if task_config_path.exists():
                with open(task_config_path, encoding="utf-8") as f:
                    task_config = json.load(f)
                self._task_classification = task_config.get("task_classification", {})
        except Exception as e:
            logger.debug(f"[ModelPoolManager] 任务分类加载失败: {e}")

        logger.info(f"[ModelPoolManager] 加载完成: {len(self._models)} 模型, {len(self._routes)} 路由")

    def _set_default_config(self):
        pass

    # ==================== 公共 API ====================

    def get_all(self) -> List[Model]:
        return list(self._models.values())

    def get_model(self, model_id: str) -> Optional[Model]:
        return self._models.get(model_id)

    def get_enabled(self, model_type: str = None) -> List[Model]:
        result = []
        for model in self._models.values():
            if not model.enabled:
                continue
            if model_type and model.type != model_type:
                continue
            result.append(model)
        return sorted(result, key=lambda m: m.priority, reverse=True)

    def get_models_by_type(self, model_type: str) -> List[Model]:
        return [m for m in self._models.values() if m.type == model_type]

    def get_models_by_capability(self, capability: str) -> List[Model]:
        return [m for m in self._models.values() if capability in m.capabilities]

    def get_api_key(self, model_id: str) -> str:
        model = self._models.get(model_id)
        if model:
            if model.env_key:
                value = os.getenv(model.env_key, "")
                if value:
                    return value
            # 尝试从原始配置获取
            if model_id in self._config.get("models", {}):
                configured = self._config["models"][model_id].get("api_key", "")
                if configured:
                    return configured
            if model.api_key:
                return model.api_key
        return ""

    def get_route(self, task_type: str) -> Optional[ModelRoute]:
        return self._routes.get(task_type)

    @staticmethod
    def _is_local_model(model: Model) -> bool:
        if str(model.provider or "").lower() in {"local_llama", "ollama", "local"}:
            return True
        try:
            return (urlparse((model.base_url or "").strip()).hostname or "").lower() in _LOCAL_HOSTS
        except Exception:
            return False

    def _model_dict(self) -> Dict[str, Model]:
        return self._models

    def get_model_configs_for_manager(self) -> Dict[str, Model]:
        result = {}
        for model_id, model in self._models.items():
            if model.enabled and model.base_url:
                result[model_id] = model
        return result

    # ==================== 选择模型 ====================

    def select_model(self, task_type: str = "simple_chat") -> Optional[Model]:
        candidates = self._routes.get(task_type, ModelRoute())
        for model_id in [candidates.primary, candidates.secondary, candidates.third, candidates.fallback]:
            if model_id:
                model = self._models.get(model_id)
                if model and model.enabled and self._probe_local_endpoint(model):
                    return model
        # 避免无限递归：如果已经是 simple_chat 则直接返回 None
        if task_type == "simple_chat":
            return None
        return self.select_model("simple_chat")

    def _probe_local_endpoint(self, model: Model) -> bool:
        """验证本地 OpenAI 兼容端点已就绪；未就绪时由路由选择云端候选。

        通过 /models HTTP 接口确认服务可用，而不是仅判断端口正在监听。
        云端模型一律返回 True。探测结果缓存 10 秒，避免每个请求都建连。
        """
        base_url = (model.base_url or "").strip()
        if not self._is_local_model(model):
            return True
        if not base_url:
            return False

        now = time.time()
        cached = _LOCAL_PROBE_CACHE.get(base_url)
        if cached and (now - cached[0]) < _LOCAL_PROBE_TTL:
            return cached[1]

        ok = False
        try:
            parsed = urlparse(base_url)
            if not parsed.scheme or not parsed.hostname:
                raise ValueError("本地模型 base_url 无效")
            if parsed.path.rstrip("/").endswith("/models"):
                probe_url = base_url
            elif parsed.path.rstrip("/").endswith("/v1"):
                probe_url = base_url.rstrip("/") + "/models"
            else:
                probe_url = base_url.rstrip("/") + "/v1/models"
            request = Request(probe_url, headers={"Authorization": f"Bearer {model.api_key}"})
            with urlopen(request, timeout=0.5) as response:
                ok = 200 <= response.status < 300
        except Exception:
            ok = False

        _LOCAL_PROBE_CACHE[base_url] = (now, ok)
        if not ok:
            try:
                host = (urlparse(base_url).hostname or "").lower()
            except Exception:
                host = ""
            if host in _LOCAL_HOSTS:
                self._maybe_autostart_local(base_url)
            logger.warning("[ModelPoolManager] 本地端点不可用，自动回退: %s (%s)", model.id, base_url)
        return ok

    def _select_cloud_fallback(self, unavailable_model_id: str) -> Optional[Model]:
        """显式请求本地模型但它不可用时，优先取同路由云端候选。"""
        candidate_ids: List[str] = []
        for route in self._routes.values():
            route_ids = [route.primary, route.secondary, route.third, route.fallback]
            if unavailable_model_id in route_ids:
                candidate_ids.extend(
                    model_id for model_id in route_ids if model_id and model_id != unavailable_model_id
                )

        candidate_ids.extend(
            model.id
            for model in sorted(self._models.values(), key=lambda item: item.priority, reverse=True)
            if model.id != unavailable_model_id
        )
        seen = set()
        for model_id in candidate_ids:
            if model_id in seen:
                continue
            seen.add(model_id)
            model = self._models.get(model_id)
            if (
                model
                and model.enabled
                and not self._is_local_model(model)
                and self._probe_local_endpoint(model)
            ):
                logger.warning(
                    "[ModelPoolManager] 显式本地模型不可用，改用云端候选: %s -> %s",
                    unavailable_model_id,
                    model.id,
                )
                return model
        return None

    def _maybe_autostart_local(self, base_url: str) -> None:
        """本地服务没起时按需拉起（像接入云端 API 一样随叫随用）。

        配置（config/.env）：
          MIYA_LOCAL_LLM_AUTOSTART=false           是否自动拉起（默认关闭）
          MIYA_LOCAL_LLM_START_SCRIPT=...          启动脚本路径（默认 E:\\model\\start-llm.ps1）
          MIYA_LOCAL_LLM_IDLE_MINUTES=15           空闲多久自动卸载（0=不卸载）

        拉起是异步的：本次请求仍会回退云端，模型加载完后续请求就走本地。
        """
        if str(os.getenv("MIYA_LOCAL_LLM_AUTOSTART", "false")).strip().lower() not in ("1", "true", "yes", "on"):
            return

        now = time.time()
        last = _LOCAL_AUTOSTART_ATTEMPT.get(base_url, 0.0)
        if now - last < _LOCAL_AUTOSTART_COOLDOWN:
            return
        _LOCAL_AUTOSTART_ATTEMPT[base_url] = now

        script = os.getenv("MIYA_LOCAL_LLM_START_SCRIPT", "").strip()
        if not script:
            script = str(Path("E:/model/start-llm.ps1"))
        if not os.path.exists(script):
            logger.warning("[ModelPoolManager] 本地启动脚本不存在，无法自动拉起: %s", script)
            return

        idle = os.getenv("MIYA_LOCAL_LLM_IDLE_MINUTES", "15").strip() or "15"
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", script, "-IdleMinutes", idle,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            logger.info("[ModelPoolManager] 正在后台拉起本地模型服务（首次约 20~60 秒）: %s", script)
        except Exception as e:
            logger.warning("[ModelPoolManager] 自动拉起本地模型失败: %s", e)


    def select_model_for_task(
        self, task_type: str, endpoint: str = None, priority: str = "balanced"
    ) -> Optional[Model]:
        route = self.get_route(task_type)
        if not route:
            return self.select_model(task_type)

        candidates = []
        for model_id in [route.primary, route.secondary, route.third, route.fallback]:
            if not model_id:
                continue
            model = self._models.get(model_id)
            if model and model.enabled and self._probe_local_endpoint(model):
                weight = self._calculate_weight(model, priority)
                candidates.append((model_id, weight))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return self._models[candidates[0][0]]

    def _calculate_weight(self, model: Model, priority: str) -> float:
        base = model.priority / 10.0
        if priority == "cost":
            return base * (1.0 / (model.cost_input + model.cost_output + 0.0001) / 100)
        elif priority == "speed":
            return base * ({"fast": 1.0, "medium": 0.6, "slow": 0.3}.get(model.latency, 0.5))
        elif priority == "quality":
            return base * ({"excellent": 1.0, "good": 0.7, "fair": 0.4}.get(model.quality, 0.5))
        return base

    # ==================== AI 客户端 ====================

    def create_ai_client(self, model_id: str = None, task_type: str = None, endpoint: str = "qq", *, reuse: bool = True):
        try:
            model_config = None
            if model_id:
                model_config = self.get_model(model_id)
                if model_config and self._is_local_model(model_config) and not self._probe_local_endpoint(model_config):
                    model_config = self._select_cloud_fallback(model_id)
            elif task_type:
                model_config = self.select_model_for_task(task_type, endpoint)
            else:
                model_config = self.select_model("simple_chat")

            if not model_config:
                return None

            api_key = self.get_api_key(model_config.id)
            if not api_key and self._is_local_model(model_config):
                # llama.cpp/Ollama commonly run without authentication.
                api_key = "sk-local-no-auth"
            if not model_config.base_url or (not api_key and not self._is_local_model(model_config)):
                return None

            from core.ai_client import AIClientFactory

            client = AIClientFactory.create_client(
                provider=model_config.provider,
                api_key=api_key,
                model=model_config.name,
                base_url=model_config.base_url,
                reuse=reuse,
            )
            return client
        except Exception as e:
            logger.error(f"[ModelPoolManager] 创建AI客户端失败: {e}")
            return None

    # ==================== 任务分类 ====================

    def classify_task(self, user_input: str, context: Dict = None) -> TaskType:
        tc = self._task_classification
        if not isinstance(user_input, str) or not user_input:
            return TaskType.SIMPLE_CHAT

        input_lower = user_input.lower()

        if any(kw in input_lower for kw in tc.get("tool_calling", [])):
            return TaskType.TOOL_CALLING
        if any(kw in input_lower for kw in tc.get("code_keywords", [])):
            return (
                TaskType.CODE_GENERATION
                if any(kw in input_lower for kw in tc.get("code_generation_triggers", []))
                else TaskType.CODE_ANALYSIS
            )
        if any(kw in input_lower for kw in tc.get("complex_reasoning", [])):
            return TaskType.COMPLEX_REASONING
        if any(kw in input_lower for kw in tc.get("creative_writing", [])):
            return TaskType.CREATIVE_WRITING
        if any(kw in input_lower for kw in tc.get("summarization", [])):
            return TaskType.SUMMARIZATION

        return TaskType(tc.get("default_task", "simple_chat"))

    # ==================== 使用统计 ====================

    def record_usage(self, model_key: str, input_tokens: int, output_tokens: int):
        if model_key not in self._usage_stats:
            self._usage_stats[model_key] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
            }
        stats = self._usage_stats[model_key]
        stats["requests"] += 1
        stats["input_tokens"] += input_tokens
        stats["output_tokens"] += output_tokens
        model = self._models.get(model_key)
        if model:
            stats["cost"] += (input_tokens * model.cost_input + output_tokens * model.cost_output) / 1000

    def get_usage_stats(self) -> Dict:
        return self._usage_stats

    def get_total_cost(self) -> float:
        return sum(s["cost"] for s in self._usage_stats.values())

    def reset_stats(self):
        self._usage_stats = {}

    # ==================== 列表统计 ====================

    def list_all(self) -> List[Dict]:
        return [
            {
                "id": m.id,
                "name": m.name,
                "type": m.type,
                "provider": m.provider,
                "enabled": m.enabled,
                "priority": m.priority,
            }
            for m in self._models.values()
        ]

    def get_stats(self) -> Dict:
        enabled = sum(1 for m in self._models.values() if m.enabled)
        by_type = {}
        for model in self._models.values():
            if model.type not in by_type:
                by_type[model.type] = {"enabled": 0, "total": 0}
            by_type[model.type]["total"] += 1
            if model.enabled:
                by_type[model.type]["enabled"] += 1
        return {"total": len(self._models), "enabled": enabled, "by_type": by_type}


# ==================== 便捷函数 ====================

_instance: Optional[ModelPoolManager] = None


def get_model_pool() -> ModelPoolManager:
    global _instance
    if _instance is None:
        _instance = ModelPoolManager()
    return _instance


def get_model(model_id: str) -> Optional[Model]:
    return get_model_pool().get_model(model_id)


def select_model(task_type: str = "simple_chat") -> Optional[Model]:
    return get_model_pool().select_model(task_type)


def select_model_for_task(task_type: str, endpoint: str = None, priority: str = "balanced") -> Optional[Model]:
    return get_model_pool().select_model_for_task(task_type, endpoint, priority)


def get_enabled_models(model_type: str = None) -> List[Model]:
    return get_model_pool().get_enabled(model_type)


def get_api_key(model_id: str) -> str:
    return get_model_pool().get_api_key(model_id)


def get_qq_model(model_type: str = "simple_chat", priority: str = "balanced") -> Optional[Model]:
    return select_model_for_task(model_type, "qq", priority)


def create_ai_client(task_type: str = "simple_chat", endpoint: str = None):
    return get_model_pool().create_ai_client(task_type=task_type, endpoint=endpoint)


__all__ = [
    "ModelPoolManager",
    "Model",
    "ModelConfig",
    "ModelRoute",
    "TaskType",
    "ModelType",
    "ModelProvider",
    "PROVIDER_ENV_MAP",
    "resolve_api_key_by_provider",
    "get_model_pool",
    "get_model",
    "select_model",
    "select_model_for_task",
    "get_enabled_models",
    "get_api_key",
    "get_qq_model",
    "create_ai_client",
]
