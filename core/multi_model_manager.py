"""
多模型管理器 - 快速实现版
负责模型选择、负载均衡、成本优化
"""
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
import json
import re

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
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


class MultiModelManager:
    """多模型管理器"""

    def __init__(self, model_clients: Dict[str, 'BaseAIClient'], config_path: str = None):
        """
        初始化多模型管理器

        Args:
            model_clients: 模型客户端字典 {model_key: client}
            config_path: 配置文件路径
        """
        self.model_clients = model_clients
        self.usage_stats = {}  # 使用统计 {model_key: {requests: 0, cost: 0.0}}

        # 加载配置
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._load_default_config()

        logger.info(f"多模型管理器初始化完成，已加载 {len(model_clients)} 个模型客户端")

    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，使用默认配置")
            return self._load_default_config()

    def _load_default_config(self) -> Dict:
        """加载默认配置"""
        project_root = Path(__file__).parent.parent
        config_file = project_root / 'config' / 'multi_model_config.json'

        if config_file.exists():
            return self._load_config(str(config_file))

        # 返回空配置（降级到单一模型模式）
        return {
            "models": {},
            "routing_strategy": {},
            "budget_control": {},
            "performance_settings": {}
        }

    async def classify_task(self, user_input: str, context: Dict = None) -> TaskType:
        """
        分类任务类型（基于规则 + 轻量模型）

        Args:
            user_input: 用户输入
            context: 上下文信息

        Returns:
            任务类型
        """
        input_lower = user_input.lower()

        # 工具调用检测
        tool_keywords = ['执行', '运行', '打开', '关闭', '文件', '目录',
                        '搜索', '查找', '!', '>>', 'terminal']
        if any(kw in input_lower for kw in tool_keywords):
            return TaskType.TOOL_CALLING

        # 代码相关检测
        code_keywords = ['代码', '函数', '类', '编程', 'python', 'javascript',
                        '调试', 'bug', '解析', '实现', '理解代码']
        if any(kw in input_lower for kw in code_keywords):
            if '生成' in input_lower or '写' in input_lower:
                return TaskType.CODE_GENERATION
            return TaskType.CODE_ANALYSIS

        # 复杂推理检测
        reasoning_keywords = ['分析', '推理', '解释', '为什么', '如何',
                            '比较', '评估', '理解', '思考', '逻辑']
        complex_indicators = ['深入', '详细', '全面', '系统', '框架']
        if any(kw in input_lower for kw in reasoning_keywords + complex_indicators):
            return TaskType.COMPLEX_REASONING

        # 创意写作检测
        creative_keywords = ['写', '创作', '故事', '诗歌', '小说',
                           '创意', '想象', '生成', '设计']
        if any(kw in input_lower for kw in creative_keywords):
            return TaskType.CREATIVE_WRITING

        # 摘要总结检测
        summary_keywords = ['总结', '摘要', '概括', '归纳', '简述']
        if any(kw in input_lower for kw in summary_keywords):
            return TaskType.SUMMARIZATION

        # 任务规划检测
        planning_keywords = ['帮我', '任务', '计划', '规划', '步骤']
        if any(kw in input_lower for kw in planning_keywords):
            return TaskType.TASK_PLANNING

        # 中文理解
        # 如果主要是中文，优先使用中文优化模型
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', user_input))
        if chinese_chars > len(user_input) * 0.5:
            return TaskType.CHINESE_UNDERSTANDING

        # 默认为简单对话
        return TaskType.SIMPLE_CHAT

    async def select_model(
        self,
        task_type: TaskType,
        budget_constraint: float = None,
        latency_constraint: float = None
    ) -> Tuple[str, Optional['BaseAIClient']]:
        """
        选择最优模型

        Args:
            task_type: 任务类型
            budget_constraint: 预算约束（美元）
            latency_constraint: 延迟约束（秒）

        Returns:
            (model_key, client)
        """
        strategy = self.config.get('routing_strategy', {}).get(task_type.value, {})

        if not strategy:
            logger.warning(f"未找到任务类型 {task_type.value} 的路由策略，使用默认模型")
            return "fast", self.model_clients.get("fast")

        # 获取候选模型列表
        primary = strategy.get('primary')
        fallback = strategy.get('fallback')
        secondary = strategy.get('secondary')

        # 尝试主模型
        if primary and primary in self.model_clients:
            if self._check_constraints(primary, strategy, budget_constraint, latency_constraint):
                return primary, self.model_clients[primary]

        # 尝试次选模型
        if secondary and secondary in self.model_clients:
            if self._check_constraints(secondary, strategy, budget_constraint, latency_constraint):
                return secondary, self.model_clients[secondary]

        # 尝试回退模型
        if fallback and fallback in self.model_clients:
            return fallback, self.model_clients[fallback]

        # 如果都不可用，返回第一个可用的模型
        for key, client in self.model_clients.items():
            if client:
                logger.warning(f"所有策略模型都不可用，使用 {key}")
                return key, client

        logger.error("没有可用的模型客户端")
        return None, None

    def _check_constraints(
        self,
        model_key: str,
        strategy: Dict,
        budget_constraint: float = None,
        latency_constraint: float = None
    ) -> bool:
        """
        检查模型是否满足约束

        Args:
            model_key: 模型键
            strategy: 路由策略
            budget_constraint: 预算约束
            latency_constraint: 延迟约束

        Returns:
            是否满足约束
        """
        model_info = self.config.get('models', {}).get(model_key, {})
        if not model_info:
            return False

        # 预算约束
        if budget_constraint is not None:
            cost_priority = strategy.get('cost_priority', 1.0)
            # 如果成本优先级高且预算紧张，选择低成本模型
            if cost_priority > 0.8 and budget_constraint < 1.0:
                model_cost = model_info.get('cost_per_1k_tokens', {})
                if model_cost.get('input', 0) > 0.001:
                    return False

        # 延迟约束
        if latency_constraint is not None:
            latency = model_info.get('latency', 'medium')
            speed_priority = strategy.get('speed_priority', 1.0)
            # 如果速度优先级高且延迟要求严格，选择快速模型
            if speed_priority > 0.8 and latency_constraint < 2.0 and latency != 'fast':
                return False

        return True

    def record_usage(self, model_key: str, input_tokens: int, output_tokens: int):
        """
        记录模型使用情况

        Args:
            model_key: 模型键
            input_tokens: 输入token数
            output_tokens: 输出token数
        """
        if model_key not in self.usage_stats:
            self.usage_stats[model_key] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }

        stats = self.usage_stats[model_key]
        stats["requests"] += 1
        stats["input_tokens"] += input_tokens
        stats["output_tokens"] += output_tokens

        # 计算成本
        model_info = self.config.get('models', {}).get(model_key, {})
        pricing = model_info.get('cost_per_1k_tokens', {})
        cost = (input_tokens * pricing.get('input', 0) +
                output_tokens * pricing.get('output', 0)) / 1000
        stats["cost"] += cost

        logger.debug(f"模型 {model_key} 使用记录: 请求 #{stats['requests']}, 成本 ${cost:.6f}")

    def get_usage_stats(self) -> Dict:
        """获取使用统计"""
        return self.usage_stats

    def get_total_cost(self) -> float:
        """获取总成本"""
        return sum(stats['cost'] for stats in self.usage_stats.values())

    def reset_stats(self):
        """重置统计"""
        self.usage_stats = {}
        logger.info("模型使用统计已重置")
