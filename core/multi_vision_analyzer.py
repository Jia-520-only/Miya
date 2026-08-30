"""
弥娅多模型图片分析系统
支持多个视觉模型API，实现自动故障转移和智能路由
"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 加载视觉配置
_vision_config = None


def _load_vision_config():
    """加载视觉配置 - 从 multi_model_config.json 加载"""
    global _vision_config
    if _vision_config is None:
        import json
        from pathlib import Path

        # 从 multi_model_config.json 加载视觉配置
        config_path = Path(__file__).parent.parent / "config" / "multi_model_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                full_config = json.load(f)
                _vision_config = full_config.get("vision_preferences", {})
                # 解析 @active_vision 引用
                active_vision = _vision_config.get("active_vision", "")
                if active_vision:
                    model_prefs = _vision_config.get("model_preferences", {})
                    for key in ("primary", "secondary", "fallback"):
                        if model_prefs.get(key) == "@active_vision":
                            model_prefs[key] = active_vision
                logger.info("[MultiVisionAnalyzer] 已从 multi_model_config.json 加载视觉配置")
        except Exception as e:
            logger.warning(f"[MultiVisionAnalyzer] 加载视觉配置失败: {e}, 使用默认配置")
            _vision_config = {}
    return _vision_config


def _get_vision_prompt(prompt_type: str = "image_analysis") -> str:
    """获取视觉提示词"""
    config = _load_vision_config()
    prompts = config.get("prompts", {})
    return prompts.get(prompt_type, "请详细描述这张图片的内容。")


class VisionModelType(Enum):
    """视觉模型类型枚举"""

    SILICONFLOW_VL = "siliconflow-vl"  # 硅基流动/通义千问等视觉模型
    ZHIPU_VL = "zhipu-vl"  # 智谱视觉模型
    SIMPLE_ANALYSIS = "simple-analysis"  # 本地简单分析


@dataclass
class VisionModelConfig:
    """视觉模型配置"""

    name: str
    model_type: VisionModelType
    provider: str
    api_base: str
    api_key: str = ""  # 直接存储API密钥
    api_key_env: str = ""  # 环境变量名（保留兼容）
    enabled: bool = True
    cost_per_call: float = 0.0
    max_tokens: int = 500
    timeout: int = 0  # 从配置文件加载，默认0表示使用配置
    priority: int = 1
    last_used: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0
    avg_response_time: float = 0.0


def _get_vision_model_defaults() -> dict:
    """从配置文件加载视觉模型默认配置"""
    config = _load_vision_config()
    return config.get(
        "model_defaults",
        {
            "enabled": True,
            "cost_per_call": 0.0,
            "max_tokens": 500,
            "priority": 1,
            "error_count": 0,
            "success_count": 0,
            "avg_response_time": 0.0,
        },
    )


@dataclass
class ImageAnalysisResult:
    """图片分析结果"""

    success: bool
    description: str
    labels: List[str]
    nsfw_score: float
    has_text: bool = False
    text: str = ""
    text_confidence: float = 0.0
    size_kb: float = 0.0
    format: str = ""
    model_used: str = ""
    provider: str = ""
    confidence: float = 0.0
    error_message: str = ""
    processing_time_ms: float = 0.0

    def to_context_dict(self) -> Dict[str, Any]:
        """转为可注入感知上下文的字典（平台适配器 / 决策层共用）"""
        return {
            "success": self.success,
            "description": self.description,
            "labels": self.labels,
            "model": self.model_used,
            "provider": self.provider,
            "nsfw_score": self.nsfw_score,
            "has_text": self.has_text,
            "text": self.text,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
        }


class MultiVisionAnalyzer:
    """
    多模型图片分析器
    支持多个视觉模型API，实现智能路由、故障转移和负载均衡
    """

    def __init__(self):
        config = _load_vision_config()
        http_timeout = config.get("http_client_timeout", 60)
        self.http_client = httpx.AsyncClient(timeout=float(http_timeout))
        self.models: Dict[str, VisionModelConfig] = {}
        self.model_stats: Dict[str, Dict] = {}
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        self._keyword_mapping = {}
        self._default_labels = []
        self._quality_settings = {}

        # 初始化时从配置加载

    async def initialize(self):
        """初始化多模型分析器 - 使用配置"""
        async with self._initialization_lock:
            if self._initialized:
                return

            logger.info("[MultiVisionAnalyzer] 初始化多模型图片分析系统...")

            # 加载配置
            config = _load_vision_config()
            model_prefs = config.get("model_preferences", {})
            vision_models_config = config.get("vision_models", {})
            disabled_models = model_prefs.get("disabled_models", [])
            quality_settings = config.get("quality_settings", {})
            # 加载模型默认配置
            defaults = _get_vision_model_defaults()

            # 获取模型池
            from core.model_pool_manager import get_model_pool

            model_pool = get_model_pool()
            pool_vision_models = model_pool.get_models_by_type("vision")

            self.models = {}
            available_models = []

            # 首先添加配置中的付费模型
            priority_map = {
                model_prefs.get("primary"): 1,
                model_prefs.get("secondary"): 2,
                model_prefs.get("fallback"): 3,
            }

            for model_id, model_cfg in vision_models_config.items():
                # 跳过非字典的配置项（如description）
                if not isinstance(model_cfg, dict):
                    continue
                if model_cfg.get("enabled", True) is False:
                    logger.info(f"[MultiVisionAnalyzer] {model_id} 已禁用")
                    continue

                # 从模型配置直接获取 API key（不再依赖环境变量）
                api_key = model_cfg.get("api_key", "")
                if not api_key:
                    logger.warning(f"[MultiVisionAnalyzer] {model_id} 无API密钥，跳过")
                    continue

                provider = model_cfg.get("provider", "siliconflow")
                api_base = model_cfg.get("base_url", "")
                if not api_base:
                    logger.warning(f"[MultiVisionAnalyzer] {model_id} 无 base_url，跳过")
                    continue

                # 选择模型类型
                model_name = model_cfg.get("name", "").lower()
                if any(kw in model_name for kw in ["qwen", "glm", "internvl", "llava", "kimi", "moonshot"]):
                    v_model_type = VisionModelType.ZHIPU_VL if "glm" in model_name else VisionModelType.SILICONFLOW_VL
                else:
                    v_model_type = VisionModelType.SIMPLE_ANALYSIS

                vision_config = VisionModelConfig(
                    name=model_cfg.get("name", model_id),
                    model_type=v_model_type,
                    provider=provider,
                    api_base=api_base,
                    api_key=api_key,
                    api_key_env="",
                    enabled=defaults.get("enabled", True),
                    cost_per_call=defaults.get("cost_per_call", 0.0),
                    max_tokens=model_cfg.get("max_tokens", defaults.get("max_tokens", 500)),
                    timeout=quality_settings.get("timeout_seconds", 0),  # 0 表示使用配置文件的 timeout
                    priority=priority_map.get(model_id) or defaults.get("priority", 1),
                )
                self.models[model_id] = vision_config
                available_models.append(model_id)
                logger.info(f"[MultiVisionAnalyzer] {model_cfg.get('name')} 已启用 (来自配置)")

            # 添加模型池中已有的视觉模型（排除禁用的）
            for model_config in pool_vision_models:
                model_id = model_config.id
                if model_id in disabled_models:
                    continue
                if model_id in self.models:
                    continue  # 已经从配置添加
                if not model_config.base_url:
                    logger.warning(f"[MultiVisionAnalyzer] {model_id} 无base_url，跳过")
                    continue
                # Model 类没有 api_key 字段，需要从 env_key 获取
                model_api_key = ""
                if hasattr(model_config, "api_key"):
                    model_api_key = model_config.api_key or ""
                elif hasattr(model_config, "env_key") and model_config.env_key:
                    from config.config_utils import get_api_key

                    model_api_key = get_api_key(model_config.env_key)
                if not model_api_key:
                    logger.warning(f"[MultiVisionAnalyzer] {model_id} 无API密钥，跳过")
                    continue

                provider_map = {
                    "zhipu": "zhipu",
                    "siliconflow": "siliconflow",
                    "openai": "openai",
                }
                provider = provider_map.get(model_config.provider, str(model_config.provider))

                model_name = model_config.name.lower()
                if "glm" in model_name:
                    v_model_type = VisionModelType.ZHIPU_VL
                elif any(kw in model_name for kw in ["qwen", "internvl", "llava", "kimi", "moonshot"]):
                    v_model_type = VisionModelType.SILICONFLOW_VL
                else:
                    v_model_type = VisionModelType.SIMPLE_ANALYSIS

                vision_config = VisionModelConfig(
                    name=model_config.name,
                    model_type=v_model_type,
                    provider=provider,
                    api_base=model_config.base_url,
                    api_key=model_api_key,
                    api_key_env="",
                    enabled=defaults.get("enabled", True),
                    cost_per_call=defaults.get("cost_per_call", 0.0),
                    max_tokens=model_config.max_tokens or defaults.get("max_tokens", 500),
                    timeout=0,  # 使用配置文件 timeout
                    priority=priority_map.get(model_id) or defaults.get("priority", 1),
                    error_count=defaults.get("error_count", 0),
                    success_count=defaults.get("success_count", 0),
                    avg_response_time=defaults.get("avg_response_time", 0.0),
                )
                self.models[model_id] = vision_config
                available_models.append(model_id)
                logger.info(f"[MultiVisionAnalyzer] {model_config.name} 已启用 (来自模型池)")

            # 添加简单分析作为兜底
            simple_defaults = config.get("simple_fallback", {})
            self.models["simple_analysis"] = VisionModelConfig(
                name="简单图片分析",
                model_type=VisionModelType.SIMPLE_ANALYSIS,
                provider="local",
                api_base="",
                api_key_env="",
                cost_per_call=0.0,
                max_tokens=0,
                timeout=simple_defaults.get("timeout", 5),
                priority=simple_defaults.get("priority", 99),
            )

            if not available_models:
                logger.warning("[MultiVisionAnalyzer] 没有可用的视觉模型API，将使用本地分析")

            self._initialized = True
            logger.info(f"[MultiVisionAnalyzer] 初始化完成，已启用 {len(available_models)} 个视觉模型")

    async def analyze_image(self, image_data: bytes, max_retries: int = 3) -> ImageAnalysisResult:
        """
        分析图片（多模型智能路由 + 协作模式）

        Args:
            image_data: 图片二进制数据
            max_retries: 最大重试次数

        Returns:
            ImageAnalysisResult 对象
        """
        start_time = time.time()

        if not self._initialized:
            await self.initialize()

        # 获取图片基本信息
        image_size_kb = len(image_data) / 1024
        image_format = self._detect_image_format(image_data)
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        logger.info(
            f"[MultiVisionAnalyzer] 开始分析图片, 大小: {image_size_kb:.1f}KB, 格式: {image_format}, 模型数: {len(self.models)}"
        )

        # 直接使用简单模式（禁用协作，减少超时）
        # 检查是否启用协作模式
        getattr(self, "_use_collaboration", True)

        # 传统模式：选择最佳模型
        selected_model = await self._select_best_model()

        # 尝试分析
        tried_models = set()
        for attempt in range(max_retries):
            try:
                # 每次重试都重新选择最佳模型（跳过已尝试的）
                selected_model = await self._select_best_model(exclude=tried_models)
                logger.info(
                    f"[MultiVisionAnalyzer] 使用 {selected_model.name} 分析图片 (尝试 {attempt + 1}/{max_retries})"
                )

                if selected_model.model_type == VisionModelType.SIMPLE_ANALYSIS:
                    # 简单分析（无API）
                    logger.info("[MultiVisionAnalyzer] 使用简单分析")
                    result = self._simple_image_analysis(image_data)
                else:
                    # API调用
                    logger.info(f"[MultiVisionAnalyzer] 调用API: {selected_model.name}")
                    result = await self._call_vision_api(selected_model, image_base64, image_format)
                    logger.info(f"[MultiVisionAnalyzer] API返回结果: {result.get('description', 'empty')[:50]}")

                # 更新模型统计
                self._update_model_stats(selected_model, success=True)

                # 计算处理时间
                processing_time_ms = (time.time() - start_time) * 1000

                return ImageAnalysisResult(
                    success=True,
                    description=result.get("description", ""),
                    labels=result.get("labels", []),
                    nsfw_score=result.get("nsfw_score", 0.0),
                    has_text=result.get("has_text", False),
                    text=result.get("text", ""),
                    text_confidence=result.get("text_confidence", 0.0),
                    size_kb=image_size_kb,
                    format=image_format,
                    model_used=selected_model.name,
                    provider=selected_model.provider,
                    confidence=result.get("confidence", 0.8),
                    processing_time_ms=processing_time_ms,
                )

            except Exception as e:
                logger.warning(f"[MultiVisionAnalyzer] {selected_model.name} 分析失败: {e}")

                # 更新模型统计
                self._update_model_stats(selected_model, success=False)
                tried_models.add(selected_model.name)

                # 强制选择下一个模型，跳过已尝试过的
                logger.info("[MultiVisionAnalyzer] 尝试选择备用模型...")
                fallback = await self._select_fallback_model(selected_model)

                if fallback and fallback.name not in tried_models:
                    selected_model = fallback
                    logger.info(f"[MultiVisionAnalyzer] 切换到备用模型: {selected_model.name}")
                    continue

                # 没有备用模型，直接返回简单分析
                logger.warning("[MultiVisionAnalyzer] 没有备用模型，使用简单分析")
                processing_time_ms = (time.time() - start_time) * 1000
                simple_result = self._simple_image_analysis(image_data)

                return ImageAnalysisResult(
                    success=True,
                    description=simple_result["description"],
                    labels=simple_result["labels"],
                    nsfw_score=simple_result["nsfw_score"],
                    size_kb=image_size_kb,
                    format=image_format,
                    model_used="简单分析",
                    provider="local",
                    confidence=0.3,
                    processing_time_ms=processing_time_ms,
                )

        # 所有模型重试完毕仍失败 → 回退到简单分析
        logger.warning("[MultiVisionAnalyzer] 所有 API 模型均已失败，回退到本地简单分析")
        processing_time_ms = (time.time() - start_time) * 1000
        simple_result = self._simple_image_analysis(image_data)
        return ImageAnalysisResult(
            success=True,
            description=simple_result["description"],
            labels=simple_result["labels"],
            nsfw_score=simple_result["nsfw_score"],
            size_kb=image_size_kb,
            format=image_format,
            model_used="简单分析(回退)",
            provider="local",
            confidence=0.2,
            processing_time_ms=processing_time_ms,
        )

    async def _select_best_model(self, exclude: Optional[set] = None) -> VisionModelConfig:
        """选择最佳模型（基于优先级、成本和可用性）"""
        available_models = [
            model
            for model in self.models.values()
            if model.enabled
            and model.model_type != VisionModelType.SIMPLE_ANALYSIS
            and (not exclude or model.name not in exclude)
        ]

        if not available_models:
            # 回退到简单分析
            logger.warning("[MultiVisionAnalyzer] 没有可用的视觉模型，使用简单分析")
            return self.models["simple_analysis"]

        # 先按优先级排序
        available_models.sort(key=lambda m: m.priority)

        # 记录所有可用模型供调试
        logger.info(
            f"[MultiVisionAnalyzer] 可用模型: {[(m.name, m.priority, m.error_count) for m in available_models]}"
        )

        # 选择优先级最高且最近错误最少的模型
        best_model = available_models[0]
        for model in available_models:
            if model.error_count < best_model.error_count:
                best_model = model

        logger.info(
            f"[MultiVisionAnalyzer] 选中模型: {best_model.name}, 优先级={best_model.priority}, 错误次数={best_model.error_count}"
        )
        return best_model

    async def _select_fallback_model(self, current_model: VisionModelConfig) -> Optional[VisionModelConfig]:
        """选择备用模型 - 简单轮换"""
        available_models = [
            model
            for model in self.models.values()
            if model.enabled and model != current_model and model.model_type != VisionModelType.SIMPLE_ANALYSIS
        ]

        if not available_models:
            return None

        # 按优先级排序，返回第一个
        available_models.sort(key=lambda m: m.priority)
        logger.info(f"[MultiVisionAnalyzer] 备用模型列表: {[m.name for m in available_models]}")

        return available_models[0]

    async def _analyze_with_collaboration(
        self,
        image_data: bytes,
        image_base64: str,
        image_format: str,
        image_size_kb: float,
        start_time: float,
    ) -> ImageAnalysisResult:
        """协作模式分析图片 - 使用链式或并行策略"""

        # 获取可用模型（排除简单分析）
        available_models = [
            model
            for model in self.models.values()
            if model.enabled and model.model_type != VisionModelType.SIMPLE_ANALYSIS
        ]

        if len(available_models) < 2:
            # 只有一个模型，回退到传统模式
            return await self._analyze_single_model(image_data, image_base64, image_format, image_size_kb, start_time)

        # 按优先级排序
        available_models.sort(key=lambda m: m.priority)

        # 链式协作：先语义理解，再深度分析
        logger.info("[MultiVisionAnalyzer] 使用链式协作模式")

        model_1 = available_models[0]
        model_2 = available_models[1] if len(available_models) > 1 else available_models[0]

        # 步骤1: 模型1语义理解
        logger.info(f"[MultiVisionAnalyzer] 步骤1: {model_1.name} 语义理解")

        result_1 = await self._call_vision_api(model_1, image_base64, image_format)
        understanding = result_1.get("description", "")[:100]

        # 步骤2: 模型2深度分析
        logger.info(f"[MultiVisionAnalyzer] 步骤2: {model_2.name} 深度分析")

        result_2 = await self._call_vision_api(model_2, image_base64, image_format)

        # 合并结果
        final_description = f"{understanding}\n\n详细分析：{result_2.get('description', '')}"
        final_labels = list(set(result_1.get("labels", []) + result_2.get("labels", [])))

        # 更新模型统计
        self._update_model_stats(model_1, success=True)
        self._update_model_stats(model_2, success=True)

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(f"[MultiVisionAnalyzer] 协作完成: {model_1.name} + {model_2.name}, 耗时{processing_time_ms:.0f}ms")

        return ImageAnalysisResult(
            success=True,
            description=final_description,
            labels=final_labels,
            nsfw_score=0.0,
            has_text=result_2.get("has_text", False),
            text=result_2.get("text", ""),
            text_confidence=result_2.get("text_confidence", 0.0),
            size_kb=image_size_kb,
            format=image_format,
            model_used=f"{model_1.name}+{model_2.name}",
            provider="collaboration",
            confidence=0.9,
            processing_time_ms=processing_time_ms,
        )

    async def _analyze_single_model(
        self,
        image_data: bytes,
        image_base64: str,
        image_format: str,
        image_size_kb: float,
        start_time: float,
    ) -> ImageAnalysisResult:
        """单模型分析（回退方法）"""
        selected_model = await self._select_best_model()

        logger.info(f"[MultiVisionAnalyzer] 单模型分析: {selected_model.name}")

        if selected_model.model_type == VisionModelType.SIMPLE_ANALYSIS:
            result = self._simple_image_analysis(image_data)
        else:
            result = await self._call_vision_api(selected_model, image_base64, image_format)

        self._update_model_stats(selected_model, success=True)

        processing_time_ms = (time.time() - start_time) * 1000

        return ImageAnalysisResult(
            success=True,
            description=result.get("description", ""),
            labels=result.get("labels", []),
            nsfw_score=result.get("nsfw_score", 0.0),
            size_kb=image_size_kb,
            format=image_format,
            model_used=selected_model.name,
            provider=selected_model.provider,
            confidence=result.get("confidence", 0.7),
            processing_time_ms=processing_time_ms,
        )

    async def _call_vision_api(
        self, model_config: VisionModelConfig, image_base64: str, image_format: str
    ) -> Dict[str, Any]:
        """调用视觉模型API"""
        logger.info(
            f"[MultiVisionAnalyzer] _call_vision_api: provider={model_config.provider}, name={model_config.name}, base={model_config.api_base}"
        )

        api_key = model_config.api_key
        if not api_key:
            raise ValueError(f"缺少 {model_config.name} 的API密钥")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        prompt = _get_vision_prompt("image_analysis")

        if model_config.provider == "zhipu":
            # 智谱API格式
            url = f"{model_config.api_base}/chat/completions"
            logger.info(f"[MultiVisionAnalyzer] 智谱API URL: {url}")
            payload = {
                "model": model_config.name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{image_format};base64,{image_base64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": model_config.max_tokens,
            }

        elif model_config.provider in ["openai", "deepseek", "siliconflow"]:
            # OpenAI兼容格式 - 使用model_config.name而非model_type.value
            url = f"{model_config.api_base}/chat/completions"
            payload = {
                "model": model_config.name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{image_format};base64,{image_base64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": model_config.max_tokens,
            }

        elif model_config.provider == "dashscope":
            # 通义千问格式 - 使用模型配置中的名称
            url = f"{model_config.api_base}/chat/completions"
            payload = {
                "model": model_config.name,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"text": prompt},
                                {"image": f"data:image/{image_format};base64,{image_base64}"},
                            ],
                        }
                    ]
                },
                "parameters": {"max_tokens": model_config.max_tokens},
            }

        else:
            raise ValueError(f"不支持的提供商: {model_config.provider}")

        # 使用配置文件的 timeout（如果 model_config.timeout 为 0）
        timeout_value = model_config.timeout if model_config.timeout > 0 else _load_vision_config().get("timeout", 60)

        try:
            response = await self.http_client.post(url, json=payload, headers=headers, timeout=timeout_value)

            if response.status_code == 200:
                result = response.json()

                # 提取分析结果
                if model_config.provider == "zhipu":
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                elif model_config.provider == "dashscope":
                    content = result.get("output", {}).get("text", "")
                else:
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                labels = self._extract_labels_from_description(content)

                return {
                    "description": content,
                    "labels": labels,
                    "nsfw_score": 0.0,
                    "confidence": 0.8,
                    "has_text": False,
                    "text": "",
                    "text_confidence": 0.0,
                }
            else:
                error_msg = f"API调用失败: HTTP {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text[:100]}"
                raise ValueError(error_msg)

        except httpx.TimeoutException:
            raise ValueError(f"{model_config.name} API调用超时")
        except Exception as e:
            raise ValueError(f"{model_config.name} API调用异常: {str(e)[:100]}")

    def _simple_image_analysis(self, image_data: bytes) -> Dict[str, Any]:
        """简单图片分析（无API）- 使用PIL进行本地分析"""
        try:
            import colorsys
            import io

            from PIL import Image

            image_format = self._detect_image_format(image_data)
            size_kb = len(image_data) / 1024

            image = Image.open(io.BytesIO(image_data))
            width, height = image.size
            aspect_ratio = width / height if height > 0 else 1

            # 缩小图片以加快分析
            small = image.resize((50, 50))
            pixels = list(small.getdata())

            # 颜色分析
            avg_r, avg_g, avg_b = 0, 0, 0
            bright_pixels = 0
            dark_pixels = 0
            warm_pixels = 0
            cool_pixels = 0
            for p in pixels:
                if isinstance(p, (tuple, list)) and len(p) >= 3:
                    r, g, b = p[:3]
                    avg_r += r
                    avg_g += g
                    avg_b += b
                    brightness = (r + g + b) / 3
                    if brightness > 180:
                        bright_pixels += 1
                    elif brightness < 80:
                        dark_pixels += 1
                    if r > g and r > b:
                        warm_pixels += 1
                    elif b > r and b > g:
                        cool_pixels += 1

            total = len(pixels)
            avg_r /= total
            avg_g /= total
            avg_b /= total

            # 判断色调
            hue = colorsys.rgb_to_hsv(avg_r, avg_g, avg_b)[0]
            if 0.0 <= hue < 0.15 or hue >= 0.85:
                tone = "红色调"
            elif 0.15 <= hue < 0.25:
                tone = "橙色调"
            elif 0.25 <= hue < 0.4:
                tone = "黄色调"
            elif 0.4 <= hue < 0.5:
                tone = "绿色调"
            elif 0.5 <= hue < 0.7:
                tone = "蓝色调"
            else:
                tone = "紫色调"

            # 判断亮度
            if bright_pixels / total > 0.5:
                brightness_desc = "明亮"
            elif dark_pixels / total > 0.5:
                brightness_desc = "暗淡"
            else:
                brightness_desc = "中等亮度"

            # 判断冷暖色
            color_temp = "暖色调" if warm_pixels > cool_pixels else "冷色调"

            # 判断形状
            if aspect_ratio > 1.5:
                shape_desc = "横向宽图"
            elif aspect_ratio < 0.67:
                shape_desc = "纵向长图"
            elif abs(aspect_ratio - 1.0) < 0.1:
                shape_desc = "正方形"
            else:
                shape_desc = "标准比例"

            # 判断是否可能是表情包
            is_emoji_like = (
                width <= 500 and height <= 500 and size_kb < 500 and (image_format == "gif" or image_format == "png")
            )

            # 判断是否可能是截图
            is_screenshot = width >= 800 and height >= 600 and image_format == "png" and avg_b > avg_r and avg_b > avg_g

            # 从配置加载模板
            config = _load_vision_config()
            simple_config = config.get("simple_analysis", {})
            simple_config.get("tags", {})
            content_tags = simple_config.get("content_tags", {})
            size_tags = simple_config.get("size_tags", {})
            desc_template = simple_config.get(
                "description_template",
                "这是一张{format}格式的图片，尺寸为{width}×{height}像素，大小约{size_kb:.1f}KB。",
            )

            # 生成描述
            description = desc_template.format(
                format=image_format.upper(),
                width=width,
                height=height,
                size_kb=size_kb,
                shape=shape_desc,
                brightness=brightness_desc,
                color_temp=color_temp,
            )

            if image_format == "gif":
                description += "，" + simple_config.get("gif_addon", "这是一张GIF动图")
            if is_emoji_like:
                description += "，" + simple_config.get("emoji_like_addon", "看起来像是一个表情包")
            if is_screenshot:
                description += "，" + simple_config.get("screenshot_addon", "可能是一张截图")

            # 生成标签
            labels = [image_format.upper()]
            if is_emoji_like:
                gif_tags = content_tags.get("gif", ["动图", "GIF"])
                emoji_tags = content_tags.get("emoji_like", ["表情包", "表情"])
                labels.extend(gif_tags if image_format == "gif" else emoji_tags)
            if is_screenshot:
                labels.append(content_tags.get("screenshot", ["截图"])[0])
            labels.append(brightness_desc)
            labels.append(color_temp)
            labels.append(tone)
            labels.append(shape_desc)

            if size_kb > 500:
                labels.append(size_tags.get("large", "大图"))
            elif size_kb < 50:
                labels.append(size_tags.get("small", "小图"))

            return {
                "description": description,
                "labels": list(dict.fromkeys(labels)),
                "nsfw_score": 0.0,
                "confidence": 0.4,
                "has_text": False,
                "text": "",
                "text_confidence": 0.0,
            }

        except Exception as e:
            logger.warning(f"简单图片分析失败: {e}")
            config = _load_vision_config()
            config.get("fallback", {})
            image_format = self._detect_image_format(image_data)
            size_kb = len(image_data) / 1024
            description = f"{image_format.upper()}格式图片，大小{size_kb:.1f}KB"
            return {
                "description": description,
                "labels": [image_format.upper(), "图片"],
                "nsfw_score": 0.0,
                "confidence": 0.3,
                "has_text": False,
                "text": "",
                "text_confidence": 0.0,
            }

    def _extract_labels_from_description(self, description: str) -> List[str]:
        """从描述中提取标签"""
        config = _load_vision_config()
        labels_config = config.get("labels", {})
        keyword_mapping = labels_config.get("keyword_mapping", {})

        if not keyword_mapping:
            return ["图片", "视觉内容"]

        labels = []
        description_lower = description.lower()

        for category, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword in description_lower:
                    labels.append(category)
                    break

        labels = list(set(labels))

        if not labels:
            labels = labels_config.get("default_labels", ["图片", "视觉内容"])

        return labels

    def _detect_image_format(self, image_data: bytes) -> str:
        """检测图片格式"""
        if len(image_data) < 8:
            return "unknown"

        if image_data.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        elif image_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        elif image_data.startswith(b"GIF87a") or image_data.startswith(b"GIF89a"):
            return "gif"
        elif image_data.startswith(b"BM"):
            return "bmp"
        elif image_data.startswith(b"RIFF") and image_data[8:12] == b"WEBP":
            return "webp"
        else:
            return "unknown"

    def _update_model_stats(self, model: VisionModelConfig, success: bool):
        """更新模型统计信息"""
        model_id = None
        for mid, m in self.models.items():
            if m == model:
                model_id = mid
                break

        if not model_id:
            return

        if model_id not in self.model_stats:
            self.model_stats[model_id] = {
                "total_calls": 0,
                "success_calls": 0,
                "error_calls": 0,
                "last_call_time": None,
                "avg_response_time": 0.0,
            }

        stats = self.model_stats[model_id]
        stats["total_calls"] += 1
        stats["last_call_time"] = datetime.now()

        if success:
            stats["success_calls"] += 1
            model.success_count += 1
            model.error_count = max(0, model.error_count - 1)  # 成功时减少错误计数
        else:
            stats["error_calls"] += 1
            model.error_count += 1

    def _create_error_result(self, error_message: str, processing_time_ms: float) -> ImageAnalysisResult:
        """创建错误结果"""
        return ImageAnalysisResult(
            success=False,
            description=error_message,
            labels=["错误", "分析失败"],
            nsfw_score=0.0,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_models": len(self.models),
            "enabled_models": sum(1 for m in self.models.values() if m.enabled),
            "model_stats": self.model_stats,
            "initialized": self._initialized,
        }

    async def close(self):
        """关闭资源"""
        await self.http_client.aclose()
        logger.info("[MultiVisionAnalyzer] 已关闭")


# 全局实例
_global_analyzer: Optional[MultiVisionAnalyzer] = None


async def get_vision_analyzer() -> MultiVisionAnalyzer:
    """获取全局多模型视觉分析器实例"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = MultiVisionAnalyzer()
        await _global_analyzer.initialize()
    return _global_analyzer


async def analyze_image_multi_model(image_data: bytes, max_retries: int = 3) -> ImageAnalysisResult:
    """
    使用多模型分析图片（便捷函数）

    Args:
        image_data: 图片二进制数据
        max_retries: 最大重试次数

    Returns:
        ImageAnalysisResult 对象
    """
    logger.info(f"[MultiVisionAnalyzer] analyze_image_multi_model 开始, max_retries={max_retries}")
    analyzer = await get_vision_analyzer()
    result = await analyzer.analyze_image(image_data, max_retries)
    logger.info(
        f"[MultiVisionAnalyzer] 最终结果: model_used={result.model_used}, success={result.success}, description长度={len(result.description) if result.description else 0}"
    )
    return result
