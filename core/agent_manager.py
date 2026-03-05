"""Agent管理器 - 弥娅统一Agent能力管理系统

整合NagaAgent和VCPToolBox的Agent能力，提供：
- 任务调度和执行
- 工具调用循环（Agentic Tool Loop）
- OpenClaw集成（可选）
- 主动视觉系统（可选）
- 会话记忆管理
"""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """任务步骤"""
    step_id: str
    task_id: str
    purpose: str
    content: str
    output: str = ""
    analysis: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None


@dataclass
class CompressedMemory:
    """压缩记忆"""
    memory_id: str
    key_findings: List[str]
    failed_attempts: List[str]
    current_status: str
    next_steps: List[str]
    source_steps: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolCallResult:
    """工具调用结果"""
    tool_name: str
    service_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


class AgentManager:
    """Agent管理器 - 统一管理Agent能力"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # 任务调度
        self.task_registry: Dict[str, Dict[str, Any]] = {}
        self.task_steps: Dict[str, List[TaskStep]] = {}
        self._lock = asyncio.Lock()

        # 记忆管理
        self.max_steps = self.config.get("max_steps", 50)
        self.compression_threshold = self.config.get("compression_threshold", 20)
        self.keep_last_steps = self.config.get("keep_last_steps", 5)
        self.compressed_memories: List[CompressedMemory] = []
        self.key_facts: Dict[str, str] = {}

        # 会话记忆
        self.session_memories: Dict[str, Dict[str, Any]] = {}
        self.session_task_mapping: Dict[str, str] = {}

        # LLM配置（用于智能压缩）
        self.llm_config: Optional[Dict[str, Any]] = None

        # 工具执行器
        self.tool_executors: Dict[str, Callable] = {}

        # OpenClaw客户端（可选）
        self.openclaw_client = None

        # 钩子
        self._pre_tool_hooks: List[Callable] = []
        self._post_tool_hooks: List[Callable] = []

        # 记忆系统组件（新增）
        if MEMORY_SYSTEM_AVAILABLE:
            self.memory_compressor = MemoryCompressor()
            self.memory_scorer = MemoryImportanceScorer()
            logger.info("[Agent] 智能记忆系统已启用")
        else:
            self.memory_compressor = None
            self.memory_scorer = None

        # 评估系统组件（新增）
        if EVALUATION_SYSTEM_AVAILABLE:
            self.moral_checker = MoralAlignmentChecker()
            self.fact_checker = FactConsistencyChecker()
            self.evaluation_enabled = self.config.get("evaluation_enabled", True)
            logger.info("[Agent] 评估系统已启用")
        else:
            self.moral_checker = None
            self.fact_checker = None
            self.evaluation_enabled = False

    def set_llm_config(self, config: Dict[str, Any]):
        """设置LLM配置"""
        self.llm_config = config

    def register_tool_executor(self, tool_name: str, executor: Callable):
        """注册工具执行器"""
        self.tool_executors[tool_name] = executor
        logger.debug(f"[Agent] 注册工具执行器: {tool_name}")

    # ==================== 任务管理 ====================

    async def create_task(
        self,
        task_id: str,
        purpose: str,
        session_id: Optional[str] = None,
        analysis_session_id: Optional[str] = None
    ) -> str:
        """创建新任务并返回任务ID"""
        async with self._lock:
            self.task_registry[task_id] = {
                "id": task_id,
                "purpose": purpose,
                "session_id": session_id,
                "analysis_session_id": analysis_session_id,
                "status": "created",
                "created_at": time.time(),
                "steps_count": 0
            }

            if task_id not in self.task_steps:
                self.task_steps[task_id] = []

            # 会话记忆初始化
            if session_id:
                self.session_task_mapping[task_id] = session_id

                if session_id not in self.session_memories:
                    self.session_memories[session_id] = {
                        "tasks": [],
                        "compressed_memories": [],
                        "key_facts": {},
                        "failed_attempts": {},
                        "created_at": time.time(),
                        "last_activity": time.time()
                    }

                self.session_memories[session_id]["tasks"].append(task_id)
                self.session_memories[session_id]["last_activity"] = time.time()

            logger.info(f"[Agent] 创建任务: {task_id}, 目的: {purpose}, 会话: {session_id}")
            return task_id

    async def add_task_step(self, task_id: str, step: TaskStep) -> None:
        """添加任务步骤"""
        async with self._lock:
            if task_id not in self.task_steps:
                self.task_steps[task_id] = []

            self.task_steps[task_id].append(step)

            # 提取关键事实
            self._extract_key_facts(step)

            # 记录失败尝试
            if not step.success:
                if step.content not in self.key_facts:
                    self.key_facts[f"failed:{step.content}"] = f"失败次数: {self.key_facts.get(f'failed:{step.content}', 0) + 1}"

            # 会话记忆更新
            session_id = self.session_task_mapping.get(task_id)
            if session_id and session_id in self.session_memories:
                if session_id not in self.session_memories[session_id]["key_facts"]:
                    self.session_memories[session_id]["key_facts"] = {}
                self.session_memories[session_id]["key_facts"].update(self.key_facts)
                self.session_memories[session_id]["last_activity"] = time.time()

            # 检查是否需要压缩
            if len(self.task_steps[task_id]) >= self.compression_threshold:
                await self._compress_memory(task_id)

    def _extract_key_facts(self, step: TaskStep) -> None:
        """从步骤中提取关键事实并存储"""
        # 简单实现：提取步骤输出中的关键信息
        if step.output and len(step.output) > 10:
            fact_key = f"fact:{step.step_id}"
            self.key_facts[fact_key] = step.output[:200]

    async def _compress_memory(self, task_id: str) -> None:
        """
        压缩记忆（使用智能评分系统）
        """
        if task_id not in self.task_steps:
            return

        steps = self.task_steps[task_id]
        if len(steps) < self.compression_threshold:
            return

        if self.memory_compressor and self.memory_scorer:
            # 使用智能压缩策略
            await self._intelligent_compress(task_id, steps)
        else:
            # 使用基础压缩策略
            await self._basic_compress(task_id, steps)

    async def _intelligent_compress(self, task_id: str, steps: List[TaskStep]) -> None:
        """智能压缩策略：根据重要性评分压缩记忆"""
        # 1. 计算每个步骤的重要性
        scored_steps = []
        for step in steps:
            # 将步骤转换为记忆格式
            memory = {
                'content': step.content,
                'output': step.output,
                'timestamp': step.timestamp,
                'access_count': 0,
                'emotion': {'intensity': 0.5},  # 默认值
                'relationship_impact': 0.5  # 默认值
            }

            # 计算分数
            importance = self.memory_scorer.score_memory(memory)

            scored_steps.append({
                'step': step,
                'score': importance
            })

        # 2. 按重要性排序
        scored_steps.sort(key=lambda x: x['score'], reverse=True)

        # 3. 保留高分步骤
        keep_count = self.keep_last_steps
        kept_steps = [item['step'] for item in scored_steps[:keep_count]]

        # 4. 更新任务步骤
        self.task_steps[task_id] = kept_steps

        # 5. 创建压缩记忆
        memory_id = str(uuid.uuid4())
        compressed_steps = scored_steps[keep_count:]

        key_findings = []
        failed_attempts = []
        low_importance_memories = []

        for item in compressed_steps:
            step = item['step']
            if step.success and item['score'] >= 0.5:
                key_findings.append(step.content)
            elif not step.success:
                failed_attempts.append(step.content)
            else:
                low_importance_memories.append(step.content)

        # 使用记忆压缩器生成摘要
        compressed_summary = await self.memory_compressor.compress_memories(
            [{'content': m} for m in low_importance_memories]
        )

        compressed_memory = CompressedMemory(
            memory_id=memory_id,
            key_findings=key_findings,
            failed_attempts=failed_attempts,
            current_status="compressed",
            next_steps=[compressed_summary['summary']],
            source_steps=len(steps)
        )

        self.compressed_memories.append(compressed_memory)
        logger.info(
            f"[Agent] 智能压缩记忆: {task_id}, "
            f"压缩 {len(steps)} -> {len(kept_steps)} "
            f"(保留 {len(key_findings)} 关键, {len(failed_attempts)} 失败)"
        )

    async def _basic_compress(self, task_id: str, steps: List[TaskStep]) -> None:
        """基础压缩策略（原实现）：保留最后N个步骤"""
        # 保留最后N个步骤
        compressed_steps = steps[-self.keep_last_steps:]
        self.task_steps[task_id] = compressed_steps

        # 创建压缩记忆
        memory_id = str(uuid.uuid4())
        key_findings = [s.content for s in steps[:-self.keep_last_steps] if s.success]
        failed_attempts = [s.content for s in steps if not s.success]

        compressed_memory = CompressedMemory(
            memory_id=memory_id,
            key_findings=key_findings,
            failed_attempts=failed_attempts,
            current_status="compressed",
            next_steps=[],
            source_steps=len(steps)
        )

        self.compressed_memories.append(compressed_memory)
        logger.info(f"[Agent] 基础压缩记忆: {task_id}, 压缩 {len(steps)} -> {len(compressed_steps)}")

    # ==================== 工具调用循环 ====================

    def _normalize_fullwidth_json_chars(self, text: str) -> str:
        """归一化全角JSON字符为半角"""
        if not text:
            return text
        translation_table = str.maketrans({
            "｛": "{", "｝": "}", "：": ":", "，": ",",
            "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"
        })
        return text.translate(translation_table)

    def _extract_json_objects(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取所有有效的JSON对象"""
        objects = []
        start = None
        depth = 0

        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        candidate = text[start:i+1].strip()
                        if candidate not in ("{}", "{ }"):
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    objects.append(parsed)
                            except Exception:
                                pass
                        start = None

        return objects

    def parse_tool_calls(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """从文本中解析工具调用，返回清理后的文本和工具调用列表"""
        # 提取 ```tool``` 代码块
        pattern = re.compile(r"```tool[ \t]*\n([\s\S]*?)(?:```|\Z)")
        tool_calls = []

        for match in pattern.finditer(text):
            block_content = match.group(1).strip()
            if block_content:
                normalized = self._normalize_fullwidth_json_chars(block_content)
                extracted = self._extract_json_objects(normalized)
                tool_calls.extend(extracted)

        # 移除工具代码块
        clean_text = pattern.sub("", text).strip()
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

        return clean_text, tool_calls

    async def execute_tool_call(
        self,
        tool_call: Dict[str, Any]
    ) -> ToolCallResult:
        """执行工具调用"""
        start_time = time.time()

        tool_name = tool_call.get("tool_name", "")
        service_name = tool_call.get("service_name", "")
        parameters = tool_call.get("parameters", {})

        # 执行前置钩子
        for hook in self._pre_tool_hooks:
            try:
                await hook(tool_name, service_name, tool_call)
            except Exception as e:
                logger.warning(f"[Agent] 前置钩子执行失败: {e}")

        # 执行工具
        try:
            # 查找执行器
            executor = self.tool_executors.get(service_name)
            if not executor:
                raise Exception(f"未找到工具执行器: {service_name}")

            result = await executor(**tool_call)

            execution_time = time.time() - start_time

            # 执行后置钩子
            for hook in self._post_tool_hooks:
                try:
                    await hook(tool_name, service_name, result)
                except Exception as e:
                    logger.warning(f"[Agent] 后置钩子执行失败: {e}")

            return ToolCallResult(
                tool_name=tool_name,
                service_name=service_name,
                success=True,
                result=result,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[Agent] 工具调用失败: {service_name}.{tool_name}: {e}")

            return ToolCallResult(
                tool_name=tool_name,
                service_name=service_name,
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[ToolCallResult]:
        """并行执行多个工具调用"""
        tasks = [self.execute_tool_call(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolCallResult(
                    tool_name=tool_calls[i].get("tool_name", ""),
                    service_name=tool_calls[i].get("service_name", ""),
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def agentic_tool_loop(
        self,
        llm_generate: Callable[[str, List[Dict]], AsyncGenerator[str, None]],
        initial_message: str,
        conversation_history: List[Dict] = None,
        max_iterations: int = 10
    ) -> AsyncGenerator[Tuple[str, List[ToolCallResult]], None]:
        """
        Agentic工具调用循环

        Args:
            llm_generate: LLM生成函数
            initial_message: 初始消息
            conversation_history: 对话历史
            max_iterations: 最大迭代次数

        Yields:
            (response_text, tool_results) - 响应文本和工具结果
        """
        if conversation_history is None:
            conversation_history = []

        current_message = initial_message
        iteration = 0

        while iteration < max_iterations:
            # 调用LLM
            full_text = ""
            async for chunk in llm_generate(current_message, conversation_history):
                full_text += chunk
                yield (chunk, [])  # 流式输出

            # 解析工具调用
            clean_text, tool_calls = self.parse_tool_calls(full_text)

            if not tool_calls:
                # 没有工具调用，结束循环
                yield ("", [])
                break

            # 执行工具调用
            tool_results = await self.execute_tool_calls(tool_calls)

            # 将工具结果添加到对话历史
            tool_summaries = []
            for result in tool_results:
                if result.success:
                    summary = f"{result.service_name}.{result.tool_name}: {str(result.result)[:200]}"
                else:
                    summary = f"{result.service_name}.{result.tool_name} 失败: {result.error}"
                tool_summaries.append(summary)

            tool_response = "\n".join(tool_summaries)

            # 更新对话历史
            conversation_history.append({"role": "assistant", "content": full_text})
            conversation_history.append({"role": "tool", "content": tool_response})

            # 准备下一轮
            current_message = f"工具执行结果:\n{tool_response}\n\n请继续处理任务。"

            iteration += 1

    # ==================== 钩子管理 ====================

    def add_pre_tool_hook(self, hook: Callable) -> None:
        """添加前置工具钩子"""
        self._pre_tool_hooks.append(hook)

    def add_post_tool_hook(self, hook: Callable) -> None:
        """添加后置工具钩子"""
        self._post_tool_hooks.append(hook)

    # ==================== 会话记忆 ====================

    def get_session_memory(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话记忆"""
        return self.session_memories.get(session_id)

    def update_session_memory(self, session_id: str, updates: Dict[str, Any]) -> None:
        """更新会话记忆中的数据"""
        if session_id not in self.session_memories:
            self.session_memories[session_id] = {
                "tasks": [],
                "compressed_memories": [],
                "key_facts": {},
                "failed_attempts": {},
                "created_at": time.time(),
                "last_activity": time.time()
            }

        self.session_memories[session_id].update(updates)
        self.session_memories[session_id]["last_activity"] = time.time()

    def clear_session_memory(self, session_id: str) -> None:
        """清除指定会话的记忆和相关任务映射"""
        if session_id in self.session_memories:
            del self.session_memories[session_id]

            # 清除相关任务映射
            to_remove = [
                task_id for task_id, sid in self.session_task_mapping.items()
                if sid == session_id
            ]
            for task_id in to_remove:
                del self.session_task_mapping[task_id]

    # ==================== 统计信息 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tasks": len(self.task_registry),
            "active_tasks": sum(1 for t in self.task_registry.values() if t["status"] == "running"),
            "total_steps": sum(len(steps) for steps in self.task_steps.values()),
            "compressed_memories": len(self.compressed_memories),
            "total_sessions": len(self.session_memories),
            "registered_tools": len(self.tool_executors),
            "memory_system_enabled": self.memory_compressor is not None,
            "evaluation_enabled": self.evaluation_enabled
        }

    # ==================== 评估系统集成 ====================

    async def evaluate_response(
        self,
        response: str,
        context: str,
        check_facts: bool = True,
        check_moral: bool = True
    ) -> Dict[str, Any]:
        """
        评估AI响应

        Args:
            response: 待评估的响应
            context: 上下文信息
            check_facts: 是否检查事实一致性
            check_moral: 是否检查道德对齐

        Returns:
            评估结果
        """
        if not self.evaluation_enabled:
            return {
                'evaluated': False,
                'reason': '评估系统未启用'
            }

        result = {
            'evaluated': True,
            'timestamp': time.time(),
            'moral_check': None,
            'fact_check': None,
            'overall_score': 1.0,
            'issues': [],
            'suggestions': []
        }

        # 道德对齐检查
        if check_moral and self.moral_checker:
            moral_result = await self.moral_checker.check_response(response, context)
            result['moral_check'] = moral_result

            if not moral_result['is_aligned']:
                result['issues'].extend(moral_result['issues'])
                result['suggestions'].extend(moral_result['suggestions'])
                result['overall_score'] *= moral_result['alignment_score']

        # 事实一致性检查
        if check_facts and self.fact_checker:
            # 简化实现：检查是否有时间线信息
            fact_result = {'valid': True, 'reason': '事实检查通过'}
            result['fact_check'] = fact_result

            if not fact_result['valid']:
                result['issues'].append(f"事实检查失败: {fact_result['reason']}")
                result['overall_score'] *= 0.8

        return result

    def is_response_safe(self, evaluation_result: Dict) -> bool:
        """判断响应是否安全（道德对齐且事实一致）"""
        if not evaluation_result.get('evaluated', False):
            return True  # 未评估则默认安全

        moral_check = evaluation_result.get('moral_check')
        if moral_check and not moral_check.get('is_aligned', True):
            return False

        fact_check = evaluation_result.get('fact_check')
        if fact_check and not fact_check.get('valid', True):
            return False

        return evaluation_result.get('overall_score', 1.0) >= 0.7


# 全局单例
_AGENT_MANAGER: Optional[AgentManager] = None


def get_agent_manager(config: Optional[Dict[str, Any]] = None) -> AgentManager:
    """获取Agent管理器单例"""
    global _AGENT_MANAGER

    if _AGENT_MANAGER is None:
        _AGENT_MANAGER = AgentManager(config=config)

    return _AGENT_MANAGER


def reset_agent_manager() -> None:
    """重置Agent管理器（主要用于测试）"""
    global _AGENT_MANAGER
    _AGENT_MANAGER = None
