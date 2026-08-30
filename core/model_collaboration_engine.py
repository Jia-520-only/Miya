"""
弥娅模型协作引擎 (Model Collaboration Engine)

设计目标:
1. 复用原有 ModelPool 的所有功能（配置加载、任务分类、模型选择）
2. 在之上叠加智能协作层，实现多模型联动
3. 根据任务复杂度自动选择协作模式
4. 兼顾 QQ 模式和终端模式的模型调度
5. 高性能与低 Token 消耗兼顾
6. 零硬编码，所有值均从配置文件加载

协作模式:
- SINGLE: 单模型处理（简单任务，最低 token）
- CHAIN: 链式协作（中等任务，2-3 模型串联）
- PARALLEL: 并行投票（重要决策，多模型并行 + 共识）
- ROLE: 角色分工（复杂任务，分析师+创作者+审核员）
"""

import asyncio
import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.model_pool_manager import (
    ModelConfig,
)
from core.model_pool_manager import (
    ModelPoolManager as ModelPool,  # 别名，保持兼容性
)
from core.terminal_formatter import TerminalFormatter

logger = logging.getLogger(__name__)


def _get_api_key(model_config) -> str:
    api_key = getattr(model_config, "api_key", None)
    if api_key:
        return api_key

    provider = getattr(model_config, "provider", "")
    if not isinstance(provider, str):
        provider = provider.value.lower() if hasattr(provider, "value") else ""

    env_key = getattr(model_config, "env_key", "")
    from core.model_pool_manager import resolve_api_key_by_provider

    return resolve_api_key_by_provider(provider.lower(), env_key)


class CollaborationMode(str, Enum):
    SINGLE = "single"
    CHAIN = "chain"
    PARALLEL = "parallel"
    ROLE = "role"


class ComplexityLevel(int, Enum):
    TRIVIAL = 1
    SIMPLE = 2
    MODERATE = 3
    COMPLEX = 4
    ADVANCED = 5


class CollaborationResult:
    def __init__(
        self,
        response: str,
        mode: CollaborationMode,
        complexity: ComplexityLevel,
        models_used: List[str],
        token_estimate: int = 0,
        reasoning: str = "",
        thinking: str = "",
    ):
        self.response = response
        self.mode = mode
        self.complexity = complexity
        self.models_used = models_used
        self.token_estimate = token_estimate
        self.reasoning = reasoning
        self.thinking = thinking

    def to_dict(self) -> Dict:
        return {
            "response": self.response,
            "mode": self.mode.value,
            "complexity": self.complexity.value,
            "models_used": self.models_used,
            "token_estimate": self.token_estimate,
            "reasoning": self.reasoning,
            "thinking": self.thinking,
        }


def _load_collaboration_config() -> Dict:
    try:
        config_path = Path(__file__).parent.parent / "config" / "multi_model_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("collaboration", {})
    except Exception as e:
        logger.warning(f"[协作引擎] 加载配置失败: {e}")
    return {}


class ModelCollaborationEngine:
    """
    模型协作引擎 - 零硬编码，所有配置从 multi_model_config.json 加载
    """

    def __init__(
        self,
        model_pool: ModelPool,
        config: Optional[Dict] = None,
        personality=None,
        soul_generator=None,
    ):
        self.model_pool = model_pool
        self.personality = personality
        self.soul_generator = soul_generator
        raw_config = config or {}
        self.config = raw_config.get("collaboration") or _load_collaboration_config()

        # 【优化】AI Client 缓存 - 避免每次调用创建新的 HTTP 连接
        self._client_cache: Dict[str, Any] = {}

        # 开关
        self.enabled = self.config.get("enabled", True)

        # 阈值
        thresholds = self.config.get("complexity_thresholds", {})
        self.threshold_single = thresholds.get("single_max", 2)
        self.threshold_chain = thresholds.get("chain_max", 3)
        self.threshold_parallel = thresholds.get("parallel_max", 4)

        # Token 预算
        budget = self.config.get("token_budget", {})
        self.max_tokens_single = budget.get("single", 2000)
        self.max_tokens_chain = budget.get("chain", 6000)
        self.max_tokens_parallel = budget.get("parallel", 10000)
        self.max_tokens_role = budget.get("role", 15000)

        # 复杂度评估
        ca = self.config.get("complexity_assessment", {})
        self.length_thresholds = ca.get("length_thresholds", {})
        self.task_weights = ca.get("task_weights", {})
        self.complex_keywords = ca.get("complex_keywords", [])
        self.multi_intent = ca.get("multi_intent", {})
        self.score_range = ca.get("score_range", {})

        # 平台配置
        po = self.config.get("platform_overrides", {})
        self.terminal_config = po.get("terminal", {})
        self.qq_config = po.get("qq", {})

        # 角色分工
        rc = self.config.get("role_collaboration", {})
        self.role_mapping = rc.get("role_mapping", {})
        self.default_role_assignment = rc.get("default_role_assignment", {})
        self.role_prompts = rc.get("role_prompts", {})
        self.role_user_templates = rc.get("role_user_templates", {})
        self.role_skip_messages = rc.get("skip_messages", {})

        # 解析 @active 引用
        active_model = self.model_pool._config.get("active", "")
        if active_model:
            self.role_mapping = {
                task: {role: active_model if mid == "@active" else mid for role, mid in roles.items()}
                for task, roles in self.role_mapping.items()
            }
            self.default_role_assignment = {
                role: active_model if mid == "@active" else mid for role, mid in self.default_role_assignment.items()
            }

        # 链式协作 - 三阶段：思考 → 推理 → 输出
        cc = self.config.get("chain_collaboration", {})
        self.chain_enabled = cc.get("enabled", True)
        self.thinking_system_prompt = cc.get("thinking_system_prompt", "")
        self.thinking_prompt_template = cc.get("thinking_prompt_template", "")
        self.reasoning_system_prompt = cc.get("reasoning_system_prompt", "")
        self.reasoning_prompt_template = cc.get("reasoning_prompt_template", "")
        self.output_system_prompt = cc.get("output_system_prompt", "")
        self.output_prompt_template = cc.get("output_prompt_template", "")
        self.max_thinking_words = cc.get("max_thinking_words", 200)
        self.max_reasoning_words = cc.get("max_reasoning_words", 150)

        # 并行投票
        pv = self.config.get("parallel_voting", {})
        self.similarity_threshold = pv.get("similarity_threshold", 0.7)
        self.arbiter_task = pv.get("arbiter_task", "summarization")
        self.arbiter_priority = pv.get("arbiter_priority", "speed")
        self.arbiter_system_prompt = pv.get("arbiter_system_prompt", "")
        self.arbiter_user_template = pv.get("arbiter_user_template", "")
        self.parallel_output_prompt_template = pv.get("output_prompt_template", "")
        self.comparison_separator = pv.get("comparison_separator", "\n\n---\n\n")
        self.comparison_format = pv.get("comparison_format", "[{model_id}]: {response}")

        # Endpoint
        self.endpoint_map = self.config.get("endpoint_map", {})
        self.default_endpoint = self.config.get("default_endpoint", "qq")

        # 消息文本
        msgs = self.config.get("messages", {})
        self.msg_error_client_unavailable = msgs.get("error_client_unavailable", "[错误] AI 客户端不可用")
        self.msg_error_call_failed = msgs.get("error_call_failed", "[AI 调用失败: {error}]")
        self.msg_empty_response = msgs.get("empty_response", "[空响应]")
        self.msg_fallback_analysis = msgs.get("fallback_analysis", "分析阶段跳过（无可用模型）")
        self.msg_fallback_creation = msgs.get("fallback_creation", "创作阶段跳过（无可用模型）")
        self.msg_reasoning_single = msgs.get("reasoning_single", "单模型处理: {model_id}")
        self.msg_reasoning_chain = msgs.get("reasoning_chain", "链式协作: {models}")
        self.msg_reasoning_parallel = msgs.get("reasoning_parallel", "并行投票: {models}")
        self.msg_reasoning_role = msgs.get("reasoning_role", "角色分工: {models}")
        self.msg_reasoning_degraded = msgs.get("reasoning_degraded", "降级: {error}")

        # 执行参数
        exe = self.config.get("execution", {})
        self.single_priority = exe.get("single_priority", "balanced")
        self.token_estimate_divisor = exe.get("token_estimate_divisor", 2)
        self.similarity_ngram_size = exe.get("similarity_ngram_size", 3)

        # 复杂度分数映射
        self.complexity_scores = self.config.get(
            "complexity_scores",
            {
                "single": 2,
                "chain": 3,
                "parallel": 4,
                "role": 5,
            },
        )

        # 平台关键词
        self.platform_keywords = self.config.get("platform_keywords", {})

        # 统计
        self.stats = {
            "total_calls": 0,
            "mode_distribution": {m.value: 0 for m in CollaborationMode},
            "avg_complexity": 0.0,
            "total_token_estimate": 0,
        }

        logger.info(
            f"[协作引擎] 初始化完成, enabled={self.enabled}, "
            f"thresholds: single<={self.threshold_single}, "
            f"chain<={self.threshold_chain}, "
            f"parallel<={self.threshold_parallel}"
        )

    def _get_persona_info(self) -> Dict[str, str]:
        """获取当前人格信息，用于协作引擎的提示词"""
        if not self.personality:
            return {
                "persona_name": "弥娅",
                "persona_description": "弥娅的默认人格",
                "persona_prompt": "",
            }

        try:
            form_info = self.personality.get_current_form()
            name = form_info.get("name", "弥娅")
            description = form_info.get("description", "")
            prompt = form_info.get("prompt", "")

            return {
                "persona_name": name,
                "persona_description": description,
                "persona_prompt": prompt,
            }
        except Exception as e:
            logger.warning(f"[协作引擎] 获取人格信息失败: {e}")
            return {
                "persona_name": "弥娅",
                "persona_description": "弥娅的默认人格",
                "persona_prompt": "",
            }

    async def _generate_emotion_context(self, message: str, context: Optional[Dict]) -> str:
        """
        生成情绪上下文（统一方法，消除重复代码）

        优先使用从decision_hub传入的emotion_context，
        如果没有则在协作引擎内部调用灵魂发生器生成。

        Args:
            message: 用户消息
            context: 上下文信息

        Returns:
            情绪上下文字符串（可能为空）
        """
        # 优先使用从decision_hub传入的
        ai_emotion_context = context.get("emotion_context", "") if context else ""

        # 如果没有传入，则在协作引擎内部生成
        if ai_emotion_context or not self.soul_generator:
            return ai_emotion_context

        try:
            history = context.get("history", []) if context else []

            # 构建用户信息
            user_info = None
            if context:
                user_info = {
                    "user_id": context.get("user_id"),
                    "group_id": context.get("group_id"),
                    "is_group": (context.get("message_type") == "group"),
                }

            # 获取认知记忆上下文
            cognitive_memory = context.get("cognitive_memory", "") if context else ""

            soul_result = await self.soul_generator.process(
                message, history, None, user_info, cognitive_memory=cognitive_memory
            )
            if not soul_result:
                return ""

            # 用户情绪
            dominant = soul_result.get("dominant_emotion", "平静")
            intensity = soul_result.get("emotions", {}).get(dominant, 50)

            # 弥娅自己的情绪
            miya_emotions = soul_result.get("emotions", {})
            if miya_emotions:
                miya_dominant = max(miya_emotions, key=miya_emotions.get)
                miya_intensity = miya_emotions[miya_dominant]
            else:
                miya_dominant = "平静"
                miya_intensity = 40

            logger.info(
                f"[协作-灵魂] 用户: {dominant} | 弥娅: {miya_dominant}({miya_intensity}%) | 情绪池: {miya_emotions}"
            )

            # 获取AI生成的内心独白
            inner_thought = ""
            if soul_result.get("analysis"):
                inner_thought = soul_result["analysis"].get("reflection", "")

            # 注入情绪上下文
            ai_emotion_context = (
                f"\n\n【情感指引】\n"
                f"- 用户情绪: {dominant} ({intensity}%)\n"
                f"- 你的情绪: {miya_dominant} ({miya_intensity}%)\n"
            )

            # 注入内心独白作为背景（标记为内部思考，不要直接输出）
            if inner_thought:
                ai_emotion_context += f"- 你的内心独白: {inner_thought}\n"

            ai_emotion_context += (
                "请根据上述情感自然回应，展现你真实的情感。\n"
                "注意：内心独白仅供你参考理解自己的感受，请不要在回复中直接引用或输出内心独白内容。\n"
                "禁止在回复中使用小括号()描述动作，如（微笑）、（点头）等。"
            )

            return ai_emotion_context

        except Exception as e:
            logger.debug(f"[协作-灵魂] 处理失败: {e}")
            return ""

    async def process(
        self,
        message: str,
        task_type: str,
        platform: str = "qq",
        context: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        tools: Optional[List] = None,
        ai_client_factory=None,
    ) -> CollaborationResult:
        from core.terminal_formatter import TerminalFormatter

        self.stats["total_calls"] += 1
        start_time = time.time()

        logger.debug(
            f"[协作引擎] process接收到的 context type: {type(context)}, keys: {list(context.keys()) if context else 'None'}"
        )

        if not self.enabled:
            return await self._fallback_to_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                ai_client_factory,
            )

        complexity = await self._assess_complexity(message, task_type, platform)
        mode = self._select_mode(complexity, task_type, platform)

        # 终端输出：协作开始
        print(TerminalFormatter.separator("协作引擎"))
        print(TerminalFormatter.collaboration_start(mode.value, complexity.value))
        print(f"{TerminalFormatter.DIM}  任务: {task_type} | 平台: {platform}{TerminalFormatter.RESET}")

        try:
            if mode == CollaborationMode.SINGLE:
                result = await self._execute_single(
                    message,
                    task_type,
                    platform,
                    context,
                    system_prompt,
                    user_prompt,
                    tools,
                    ai_client_factory,
                )
            elif mode == CollaborationMode.CHAIN:
                result = await self._execute_chain(
                    message,
                    task_type,
                    platform,
                    context,
                    system_prompt,
                    user_prompt,
                    tools,
                    ai_client_factory,
                )
            elif mode == CollaborationMode.PARALLEL:
                result = await self._execute_parallel(
                    message,
                    task_type,
                    platform,
                    context,
                    system_prompt,
                    user_prompt,
                    tools,
                    ai_client_factory,
                )
            else:
                result = await self._execute_role(
                    message,
                    task_type,
                    platform,
                    context,
                    system_prompt,
                    user_prompt,
                    tools,
                    ai_client_factory,
                )
        except Exception as e:
            logger.info(f"[协作引擎] 协作执行失败，降级为单模型: {e}")
            result = await self._fallback_to_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                ai_client_factory,
            )
            result.reasoning = self.msg_reasoning_degraded.format(error=str(e))

        elapsed = time.time() - start_time
        self.stats["mode_distribution"][result.mode.value] += 1
        self.stats["total_token_estimate"] += result.token_estimate

        # 终端输出：协作结果
        from core.terminal_formatter import TerminalFormatter

        print(
            TerminalFormatter.result(
                result.mode.value,
                result.models_used,
                result.token_estimate,
                result.reasoning,
            )
        )
        print(TerminalFormatter.separator())

        logger.info(
            f"[协作引擎] 处理完成 | 模式={result.mode.value} | "
            f"复杂度={result.complexity} | "
            f"模型={','.join(result.models_used)} | "
            f"耗时={elapsed:.2f}s | "
            f"Token≈{result.token_estimate}"
        )

        return result

    async def _assess_complexity(self, message: str, task_type: str, platform: str) -> ComplexityLevel:
        score = 1

        msg_len = len(message) if message else 0
        level_1 = self.length_thresholds.get("level_1", 200)
        level_2 = self.length_thresholds.get("level_2", 500)
        if msg_len > level_1:
            score += 1
        if msg_len > level_2:
            score += 1

        score += self.task_weights.get(task_type, 1)

        if any(kw in message.lower() for kw in self.complex_keywords):
            score += 1

        terminal_kw = self.terminal_config.get("complex_keywords", [])
        if platform in self.platform_keywords.get("terminal", ["terminal"]):
            if terminal_kw and any(kw in message.lower() for kw in terminal_kw):
                score += 1

        question_count = message.count("?") + message.count("？")
        q_threshold = self.multi_intent.get("question_threshold", 3)
        if question_count >= q_threshold:
            score += 1

        connectors = self.multi_intent.get("connectors", [])
        q_with_conn = self.multi_intent.get("question_with_connectors", 2)
        if connectors and any(c in message for c in connectors) and question_count >= q_with_conn:
            score += 1

        score_min = self.score_range.get("min", 1)
        score_max = self.score_range.get("max", 5)
        score = max(score_min, min(score_max, score))
        return ComplexityLevel(score)

    def _select_mode(self, complexity: ComplexityLevel, task_type: str, platform: str) -> CollaborationMode:
        terminal_keys = self.platform_keywords.get("terminal", ["terminal"])
        qq_keys = self.platform_keywords.get("qq", ["qq"])

        if platform in terminal_keys:
            overrides = self.terminal_config.get("mode_overrides", {})
        elif platform in qq_keys:
            overrides = self.qq_config.get("mode_overrides", {})
        else:
            overrides = {}

        if task_type in overrides:
            return CollaborationMode(overrides[task_type])

        if complexity.value <= self.threshold_single:
            return CollaborationMode.SINGLE
        elif complexity.value <= self.threshold_chain:
            return CollaborationMode.CHAIN
        elif complexity.value <= self.threshold_parallel:
            return CollaborationMode.PARALLEL
        else:
            return CollaborationMode.ROLE

    async def _execute_single(
        self,
        message,
        task_type,
        platform,
        context,
        system_prompt,
        user_prompt,
        tools,
        factory,
    ) -> CollaborationResult:
        endpoint = self._get_endpoint(platform)
        model_config = self.model_pool.select_model_for_task(
            task_type,
            endpoint,
            self.single_priority,
        )

        if not model_config or not _get_api_key(model_config):
            return await self._fallback_to_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        client = self._create_client(model_config, factory, tools, context)

        # 【灵魂发生器】获取情绪上下文（统一方法）
        ai_emotion_context = await self._generate_emotion_context(message, context)

        # 思考过程
        from core.terminal_formatter import TerminalFormatter

        # 仅在终端模式下显示详细步骤，QQ等其他平台不显示
        if platform == "terminal":
            print(TerminalFormatter.chain_step(1, model_config.id, "思考分析"))
            print(TerminalFormatter.chain_step(2, model_config.id, "生成回复"))

        # 注入情绪上下文到 user_prompt
        final_user_prompt = user_prompt
        if ai_emotion_context and user_prompt:
            final_user_prompt = user_prompt + ai_emotion_context
        elif ai_emotion_context:
            final_user_prompt = ai_emotion_context

        # 正式回复
        response = await self._call_client(client, system_prompt or "", final_user_prompt, tools)

        # 获取AI的思考过程
        ai_thinking = ""
        if hasattr(client, "last_reasoning_content") and client.last_reasoning_content:
            ai_thinking = client.last_reasoning_content

        return CollaborationResult(
            response=response,
            mode=CollaborationMode.SINGLE,
            complexity=ComplexityLevel.SIMPLE,
            models_used=[model_config.id],
            token_estimate=self._estimate_tokens(message, response),
            reasoning=self.msg_reasoning_single.format(model_id=model_config.id),
            thinking=ai_thinking,
        )

    async def _execute_chain(
        self,
        message,
        task_type,
        platform,
        context,
        system_prompt,
        user_prompt,
        tools,
        factory,
    ) -> CollaborationResult:
        if not self.chain_enabled:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        route = self.model_pool.get_route(task_type)
        if not route:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        chain_models = self._collect_chain_models(route)
        if len(chain_models) < 2:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        # 三阶段链式协作：思考 → 推理 → 输出
        thinking_result = await self._chain_phase_thinking(
            chain_models[0],
            message,
            task_type,
            platform,
            context,
            factory,
        )
        if not thinking_result or thinking_result in [
            self.msg_error_client_unavailable,
            self.msg_empty_response,
        ]:
            logger.debug("[协作引擎] 第一阶段思考结果为空，回退到单模型")
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        reasoning_result, output_model = await self._chain_phase_reasoning(
            chain_models,
            thinking_result,
            message,
            task_type,
            platform,
            context,
            factory,
        )

        ai_emotion_context = await self._generate_emotion_context(message, context)
        response = await self._chain_phase_output(
            output_model,
            reasoning_result,
            system_prompt,
            user_prompt or message,
            ai_emotion_context,
            tools,
            platform,
            context,
            factory,
        )

        response = self._clean_thinking_content(response)

        models_used = [m.id for m in chain_models[:3]] if len(chain_models) >= 3 else [m.id for m in chain_models]
        return CollaborationResult(
            response=response,
            mode=CollaborationMode.CHAIN,
            complexity=ComplexityLevel.MODERATE,
            models_used=models_used,
            token_estimate=self._estimate_tokens(message, response, reasoning_result),
            reasoning=self.msg_reasoning_chain.format(
                models=" → ".join(models_used),
            ),
        )

    def _collect_chain_models(self, route) -> list:
        """收集链式协作的可用模型"""
        chain_model_ids = [route.primary, route.secondary, route.third]
        chain_models = []
        for model_id in chain_model_ids:
            if model_id and model_id in self.model_pool._models:
                config = self.model_pool._models[model_id]
                if _get_api_key(config) and config.base_url:
                    chain_models.append(config)
        return chain_models

    async def _chain_phase_thinking(
        self,
        model_1,
        message,
        task_type,
        platform,
        context,
        factory,
    ) -> str:
        """阶段1：思考——使用当前人格的视角进行分析"""
        client_1 = self._create_client(model_1, factory, None, context)
        persona_info = self._get_persona_info()
        thinking_system_prompt = f"你是{persona_info['persona_name']}。{persona_info['persona_description']}"
        thinking_prompt = self.thinking_prompt_template.format(
            task_type=task_type,
            message=message,
            persona_name=persona_info["persona_name"],
            persona_prompt=persona_info["persona_prompt"][:500] if persona_info["persona_prompt"] else "",
        )

        # v7.0: 注入情绪上下文到思考阶段，让思考模型理解当前情感基调
        emotion_ctx = context.get("emotion_context", "") if context else ""
        if emotion_ctx:
            thinking_prompt += f"\n\n【当前情感上下文】\n{emotion_ctx}"

        if platform == "terminal":
            print(TerminalFormatter.chain_step(1, model_1.id, f"思考分析({persona_info['persona_name']})"))

        return await self._call_client(
            client_1,
            system_prompt=thinking_system_prompt,
            user_prompt=thinking_prompt,
            tools=None,
        )

    async def _chain_phase_reasoning(
        self,
        chain_models,
        thinking_result,
        message,
        task_type,
        platform,
        context,
        factory,
    ) -> tuple[str, object]:
        """阶段2：推理——对思考结果进行深度推理"""
        if len(chain_models) >= 3:
            model_2 = chain_models[1]
            client_2 = self._create_client(model_2, factory, None, context)
            reasoning_prompt = self.reasoning_prompt_template.format(thinking_result=thinking_result, message=message)
            if platform == "terminal":
                print(TerminalFormatter.chain_step(2, model_2.id, "推理揣摩"))
            reasoning_result = await self._call_client(
                client_2,
                system_prompt=self.reasoning_system_prompt,
                user_prompt=reasoning_prompt,
                tools=None,
            )
            if not reasoning_result or reasoning_result in [
                self.msg_error_client_unavailable,
                self.msg_empty_response,
            ]:
                logger.debug("[协作引擎] 第二阶段推理结果为空，使用思考结果")
                reasoning_result = thinking_result
            return reasoning_result, chain_models[2]
        else:
            return thinking_result, chain_models[1]

    async def _chain_phase_output(
        self,
        output_model,
        reasoning_result,
        system_prompt,
        user_prompt,
        ai_emotion_context,
        tools,
        platform,
        context,
        factory,
    ) -> str:
        """阶段3：输出——生成最终回复"""
        try:
            client_output = self._create_client(output_model, factory, tools, context)

            try:
                base_output_prompt = self.output_prompt_template.format(
                    reasoning_result=reasoning_result, message=user_prompt
                )
            except (KeyError, ValueError) as fmt_err:
                logger.warning(
                    "[协作引擎] Prompt格式化失败: %s..., 错误: %s",
                    self.output_prompt_template[:100],
                    fmt_err,
                )
                base_output_prompt = f"推理结果：{reasoning_result}\n\n用户问题：{user_prompt}"

            output_prompt = (
                ai_emotion_context + "\n\n" + base_output_prompt if ai_emotion_context else base_output_prompt
            )
            response = await self._call_client(
                client_output,
                system_prompt=system_prompt,
                user_prompt=output_prompt,
                tools=tools,
            )

            if not response or response in [
                self.msg_error_client_unavailable,
                self.msg_empty_response,
            ]:
                logger.debug("[协作引擎] 第三阶段模型响应为空，使用推理结果")
                response = reasoning_result if reasoning_result else self.msg_empty_response

            return response
        except Exception as e:
            logger.error("[协作引擎] 第三阶段执行失败: %s", e)
            return reasoning_result if reasoning_result else self.msg_error_call_failed.format(error=e)

    async def _execute_parallel(
        self,
        message,
        task_type,
        platform,
        context,
        system_prompt,
        user_prompt,
        tools,
        factory,
    ) -> CollaborationResult:
        route = self.model_pool.get_route(task_type)
        if not route:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        parallel_models = []
        for model_id in [route.primary, route.secondary, route.fallback]:
            if model_id and model_id in self.model_pool._models:
                config = self.model_pool._models[model_id]
                if _get_api_key(config) and config.base_url:
                    parallel_models.append(config)
                    if len(parallel_models) >= 2:
                        break

        if len(parallel_models) < 2:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        parallel_model_ids = [m.id for m in parallel_models]
        print(TerminalFormatter.parallel_step(parallel_model_ids))

        # Phase 1: 仅调用思考模型（模型[0]），输出模型在 Phase 2 单独调用
        tasks = []
        think_model = parallel_models[0]
        client_0 = self._create_client(think_model, factory, None, context)
        task_0 = self._call_client(client_0, system_prompt, user_prompt, None)
        tasks.append((think_model.id, task_0))

        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        model_responses = []
        models_used = []
        for i, (model_id, _) in enumerate(tasks):
            resp = results[i]
            if isinstance(resp, Exception):
                logger.warning(f"[协作引擎] 模型 {model_id} 调用失败: {resp}")
                continue
            model_responses.append((model_id, resp))
            models_used.append(model_id)

        if not model_responses:
            return await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        # 【思考-输出分离模式】
        # 第一个模型负责思考，第二个模型负责生成最终回复
        if model_responses:
            thinking_result = model_responses[0][1]  # 模型[0]的思考结果

            # 显示思考过程到终端
            try:
                print(TerminalFormatter.thinking_block(thinking_result[:300]))
            except Exception as e:
                logger.debug(f"[协作引擎] 显示思考过程失败: {e}")

        # 【灵魂发生器】获取情绪上下文（统一方法）
        ai_emotion_context = await self._generate_emotion_context(message, context)

        # 用模型2根据思考结果生成最终回复
        output_model = parallel_models[1]
        output_client = self._create_client(output_model, factory, tools, context)

        base_output_prompt = self.parallel_output_prompt_template.format(
            thinking_result=thinking_result, message=message
        )
        # 注入情绪上下文
        output_prompt = ai_emotion_context + "\n\n" + base_output_prompt if ai_emotion_context else base_output_prompt

        final_response = await self._call_client(
            output_client,
            system_prompt=system_prompt,
            user_prompt=output_prompt,
            tools=tools,
        )

        # 清理可能残留的思考过程
        if "<think>" in final_response:
            parts = final_response.split("")
            final_response = parts[-1].strip()

        final_response = self._clean_thinking_content(final_response)

        return CollaborationResult(
            response=final_response,
            mode=CollaborationMode.PARALLEL,
            complexity=ComplexityLevel.COMPLEX,
            models_used=[parallel_model_ids[0], parallel_model_ids[1]],
            token_estimate=self._estimate_tokens(message, thinking_result + final_response),
            reasoning=f"思考-输出分离: {parallel_model_ids[0]}思考 → {parallel_model_ids[1]}输出",
            thinking=thinking_result,
        )

    async def _execute_role(
        self,
        message,
        task_type,
        platform,
        context,
        system_prompt,
        user_prompt,
        tools,
        factory,
    ) -> CollaborationResult:
        roles = self._get_role_models(task_type, platform)
        if len(roles) < 2:
            return await self._execute_chain(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )

        analyst_prompt = self.role_prompts.get("analyst", "")
        creator_prompt_text = self.role_prompts.get("creator", "")
        reviewer_prompt_text = self.role_prompts.get("reviewer", "")

        analyst_template = self.role_user_templates.get("analyst", "{message}")
        creator_template = self.role_user_templates.get("creator", "{user_prompt}")
        reviewer_template = self.role_user_templates.get("reviewer", "{message}")

        skip_analysis = self.role_skip_messages.get("analyst", "")
        skip_creation = self.role_skip_messages.get("creator", "")

        # 阶段 1: 分析师
        analyst_config = roles.get("analyst")
        if analyst_config and _get_api_key(analyst_config):
            print(TerminalFormatter.role_step("analyst", analyst_config.id))
            analyst_client = self._create_client(analyst_config, factory, None, context)
            analysis = await self._call_client(
                analyst_client,
                system_prompt=analyst_prompt,
                user_prompt=analyst_template.format(
                    task_type=task_type,
                    message=message,
                ),
                tools=None,
            )
        else:
            analysis = skip_analysis

        # 阶段 2: 创作者
        creator_config = roles.get("creator")
        if creator_config and _get_api_key(creator_config):
            print(TerminalFormatter.role_step("creator", creator_config.id))
            creator_client = self._create_client(creator_config, factory, tools, context)
            draft = await self._call_client(
                creator_client,
                system_prompt=system_prompt or creator_prompt_text,
                user_prompt=creator_template.format(
                    user_prompt=user_prompt or "",
                    analysis=analysis,
                ),
                tools=None,
            )
        else:
            draft = skip_creation

        # 阶段 3: 审核员
        # 【灵魂发生器】获取情绪上下文（统一方法）
        ai_emotion_context = await self._generate_emotion_context(message, context)

        reviewer_config = roles.get("reviewer")
        if reviewer_config and _get_api_key(reviewer_config):
            print(TerminalFormatter.role_step("reviewer", reviewer_config.id))
            reviewer_client = self._create_client(reviewer_config, factory, None, context)
            base_reviewer_prompt = reviewer_template.format(
                message=message,
                draft=draft,
            )
            # 注入情绪上下文
            final_reviewer_prompt = (
                ai_emotion_context + "\n\n" + base_reviewer_prompt if ai_emotion_context else base_reviewer_prompt
            )
            final_response = await self._call_client(
                reviewer_client,
                system_prompt=reviewer_prompt_text,
                user_prompt=final_reviewer_prompt,
                tools=None,
            )
        else:
            final_response = draft

        models_used = [
            config.id for config in [analyst_config, creator_config, reviewer_config] if config and _get_api_key(config)
        ]

        return CollaborationResult(
            response=final_response,
            mode=CollaborationMode.ROLE,
            complexity=ComplexityLevel.ADVANCED,
            models_used=models_used,
            token_estimate=self._estimate_tokens(
                message,
                final_response,
                analysis,
                draft,
            ),
            reasoning=self.msg_reasoning_role.format(
                models=" → ".join(models_used),
            ),
        )

    async def _consensus_decision(
        self,
        model_responses: List[Tuple[str, str]],
        message: str,
        task_type: str,
        platform: str,
        system_prompt: str,
        factory,
        context=None,
    ) -> str:
        if len(model_responses) == 2:
            resp_1 = model_responses[0][1]
            resp_2 = model_responses[1][1]

            if self._similarity(resp_1, resp_2) > self.similarity_threshold:
                return resp_1 if len(resp_1) >= len(resp_2) else resp_2

            return resp_1 if len(resp_1) >= len(resp_2) else resp_2

        arbiter_config = self.model_pool.select_model_for_task(
            self.arbiter_task,
            self._get_endpoint(platform),
            self.arbiter_priority,
        )

        if not arbiter_config or not _get_api_key(arbiter_config):
            return model_responses[0][1]

        arbiter_client = self._create_client(arbiter_config, factory, None, context)

        comparison_text = self.comparison_separator.join(
            self.comparison_format.format(model_id=mid, response=resp) for mid, resp in model_responses
        )

        arbiter_prompt = self.arbiter_user_template.format(
            message=message,
            comparison_text=comparison_text,
        )

        return await self._call_client(
            arbiter_client,
            system_prompt=self.arbiter_system_prompt,
            user_prompt=arbiter_prompt,
            tools=None,
        )

    async def _fallback_to_single(
        self,
        message,
        task_type,
        platform,
        context,
        system_prompt,
        user_prompt,
        tools,
        factory,
    ) -> CollaborationResult:
        if not hasattr(self, "_fallback_depth"):
            self._fallback_depth = 0
        self._fallback_depth += 1
        if self._fallback_depth > 3:
            max_depth = self._fallback_depth
            self._fallback_depth = 0
            return CollaborationResult(
                response="抱歉，我暂时无法处理这个消息。请稍后再试~",
                mode=CollaborationMode.SINGLE,
                complexity=ComplexityLevel.SIMPLE,
                models_used=["fallback_error"],
                token_estimate=0,
                reasoning=f"递归保护：回退深度超限 ({max_depth})",
            )
        try:
            result = await self._execute_single(
                message,
                task_type,
                platform,
                context,
                system_prompt,
                user_prompt,
                tools,
                factory,
            )
            self._fallback_depth = 0
            return result
        except Exception as e:
            self._fallback_depth = 0
            return CollaborationResult(
                response="抱歉，我暂时无法处理这个消息。请稍后再试~",
                mode=CollaborationMode.SINGLE,
                complexity=ComplexityLevel.SIMPLE,
                models_used=["fallback_error"],
                token_estimate=0,
                reasoning=f"回退单模型失败: {str(e)[:100]}",
            )

    def _get_role_models(self, task_type: str, platform: str) -> Dict[str, Optional[ModelConfig]]:
        mapping = self.role_mapping.get(task_type, self.default_role_assignment)

        roles = {}
        for role_name, model_id in mapping.items():
            config = self.model_pool._models.get(model_id)
            if config and _get_api_key(config) and config.base_url:
                roles[role_name] = config
            else:
                roles[role_name] = None

        return roles

    def _get_endpoint(self, platform: str) -> str:
        return self.endpoint_map.get(platform, self.default_endpoint)

    def _create_client(self, model_config: ModelConfig, factory=None, tools=None, context=None):
        # 【优化】使用缓存避免重复创建 HTTP 连接
        cache_key = f"{model_config.provider}:{model_config.name}:{model_config.base_url}"
        if cache_key in self._client_cache:
            client = self._client_cache[cache_key]
            if tools:
                client.set_tool_registry(lambda tools=tools: tools)
            return client

        kwargs = dict(
            provider=model_config.provider,
            api_key=_get_api_key(model_config) or "",
            model=model_config.name,
            base_url=model_config.base_url,
            tool_context=context,
            max_tokens=getattr(model_config, "max_tokens", 2000) or 2000,
        )
        if getattr(model_config, "temperature", None) is not None:
            kwargs["temperature"] = model_config.temperature

        if factory:
            client = factory.create_client(**kwargs)
        else:
            from core.ai_client import AIClientFactory

            client = AIClientFactory.create_client(**kwargs)

        if client:
            self._client_cache[cache_key] = client
            if tools:
                client.set_tool_registry(lambda tools=tools: tools)

        return client

    async def _call_client(
        self,
        client,
        system_prompt: str,
        user_prompt: str,
        tools,
    ) -> str:
        if not client:
            return self.msg_error_client_unavailable

        try:
            if tools:
                response = await client.chat_with_system_prompt(
                    system_prompt=system_prompt,
                    user_message=user_prompt,
                    tools=tools,
                    tool_choice="auto",
                )
            else:
                response = await client.chat_with_system_prompt(
                    system_prompt=system_prompt,
                    user_message=user_prompt,
                )

            # 处理可能的非字符串返回值
            if response is None:
                return self.msg_empty_response
            if not isinstance(response, str):
                return str(response)
            return response
        except Exception as e:
            logger.error(f"[协作引擎] AI 调用失败: {e}")
            return self.msg_error_call_failed.format(error=e)

    def _strip_code_prefixes(self, response: str) -> str:
        """移除回复开头的英文/代码风格前缀（DeepSeek 推理残留如 [Paste..., [Write... 等）"""
        import re

        lines = response.split("\n")
        if not lines:
            return response

        first_line = lines[0].strip()
        # 检测英文/代码风格前缀：以 [ 开头且不含中文
        if (
            first_line.startswith("[")
            and not re.search(r"[\u4e00-\u9fff]", first_line)
            or re.match(r"^[A-Za-z][a-z]+\s", first_line)
            and not re.search(r"[\u4e00-\u9fff]", first_line)
            or re.match(r"^[`#/\-]+", first_line)
            and not re.search(r"[\u4e00-\u9fff]", first_line)
        ):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)

        result = "\n".join(lines).strip()
        return result if result else response

    def _clean_thinking_content(self, response: str) -> str:
        """清理回复中的思考过程，只保留最终回复 - 保守版"""
        if not response:
            return response

        import re

        # 移除明显的 thinking 块
        patterns = [
            r"<think>[\s\S]*?",  # OpenAI格式
            r"\[think\][\s\S]*?\[/think\]",  # 其他格式
        ]

        for pattern in patterns:
            response = re.sub(pattern, "", response)

        # 如果响应已经很短（小于50字符），直接返回
        if len(response) < 50:
            return response.strip()

        # v4.5.1: 移除开头的英文/代码风格前缀（如 [Paste..., [Write..., etc）
        response = self._strip_code_prefixes(response)

        # 尝试找到回复部分的开始 - 常见回复开头
        reply_markers = [
            "好的，",
            "好的\n",
            "明白了，",
            "明白了\n",
            "知道了，",
            "知道啦",
            "嗯~",
            "嗯...\n",
            "这个嘛",
            "其实",
            "对我来说",
            "我最喜欢",
            "最喜欢",
            "我最喜欢称呼你为",
            "指挥官",
            "\n\n好的",
            "\n好的",
            "\n明白了",
            "\n所以",
            "\n根据",
            "\n综上",
            "\n总结",
            "\n回复",
            "好的",
            "明白了",
            "所以，",
            "根据分析",
            "综上",
            "总结：",
        ]

        for marker in reply_markers:
            idx = response.find(marker)
            if idx >= 0:
                # 确保找到的是有意义的回复开头
                result = response[idx:].strip()
                if len(result) > 10:
                    return result

        # 如果没找到明确的回复开头，但内容看起来是正常的（没有大量分析内容）
        # 就直接返回原内容，保留有用的信息
        lines = response.split("\n")
        cleaned_lines = []
        for line in lines:
            # 跳过明显的分析标题
            if re.match(r"^#{1,3}\s*分析|^#\s*思考|^###", line):
                continue
            # 跳过过长的行（可能是分析内容）
            if len(line) > 300:
                continue
            cleaned_lines.append(line)

        result = "\n".join(cleaned_lines).strip()

        # 如果清理后太短，返回原始响应
        if len(result) < 20 and len(response) > 20:
            return response.strip()

        return result if result else response.strip()

    def _estimate_tokens(self, *texts: str) -> int:
        from core.token_utils import count_tokens

        return sum(count_tokens(t) for t in texts if t)

    def _similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        n = self.similarity_ngram_size

        def get_ngrams(text):
            return set(text[i : i + n] for i in range(len(text) - n + 1))

        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        return len(intersection) / len(union) if union else 0.0

    def get_stats(self) -> Dict:
        total = self.stats["total_calls"]
        if total > 0:
            self.stats["avg_complexity"] = (
                sum(
                    self.complexity_scores.get(mode, 1) * count
                    for mode, count in self.stats["mode_distribution"].items()
                )
                / total
            )

        return self.stats.copy()
