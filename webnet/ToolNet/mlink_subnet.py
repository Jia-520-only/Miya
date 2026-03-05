"""
M-Link兼容的工具子网架构

整合弥娅原生的蛛网式架构：
- 感知层（Perception Layer）
- M-Link传输层
- 工具执行层
- 记忆层

设计目标：
1. 工具执行接入感知层预处理
2. 通过M-Link五流传输
3. 保持向后兼容性
4. 支持热插拔子网
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.constants import LogLevel
from .registry import ToolRegistry, ToolContext, BaseTool


logger = logging.getLogger(__name__)


class FlowType(Enum):
    """M-Link五流类型"""
    DATA = "data_flow"  # 数据流
    CONTROL = "control_flow"  # 控制流
    EMOTION = "emotion_flow"  # 情绪流
    MEMORY = "memory_flow"  # 记忆流
    TRUST = "trust_flow"  # 信任流


@dataclass
class PerceptionResult:
    """感知层预处理结果"""
    passed: bool = False  # 是否通过
    emotion: Optional[str] = None  # 识别的情绪
    intent: Optional[str] = None  # 识别的意图
    risk_level: float = 0.0  # 风险等级 (0-1)
    context: Dict[str, Any] = field(default_factory=dict)  # 额外上下文
    message: str = ""  # 处理消息


@dataclass
class MLinkMessage:
    """M-Link消息"""
    flow_type: FlowType
    content: Dict[str, Any]
    source: str = "ToolNet"
    destination: Optional[str] = None
    priority: float = 0.5
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    status: str = "pending"


class PerceptionLayer:
    """
    感知层

    工具执行前的预处理：
    - 情绪识别
    - 意图分析
    - 风险评估
    - 上下文增强
    """

    def __init__(self, emotion_system=None):
        """
        初始化感知层

        Args:
            emotion_system: 情绪系统实例
        """
        self.emotion_system = emotion_system
        self.logger = logging.getLogger("PerceptionLayer")

    async def preprocess(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> PerceptionResult:
        """
        预处理工具请求

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 工具上下文

        Returns:
            感知结果
        """
        result = PerceptionResult(passed=True)

        try:
            # 情绪识别（安全处理）
            if self.emotion_system and context.emotion:
                try:
                    # 尝试获取当前情绪，支持多种情绪系统接口
                    if hasattr(context.emotion, 'current_emotion'):
                        current_emotion = context.emotion.current_emotion()
                        result.emotion = current_emotion
                        result.context['emotion'] = current_emotion
                    elif hasattr(context.emotion, 'get_current_emotion'):
                        current_emotion = context.emotion.get_current_emotion()
                        result.emotion = current_emotion
                        result.context['emotion'] = current_emotion
                    elif callable(context.emotion):
                        current_emotion = context.emotion()
                        result.emotion = current_emotion
                        result.context['emotion'] = current_emotion
                    else:
                        # emotion 是一个对象，直接使用
                        result.emotion = str(context.emotion)
                        result.context['emotion'] = result.emotion
                except Exception as emotion_error:
                    self.logger.warning(f"获取情绪信息失败: {emotion_error}")
                    # 不影响工具执行，继续处理

            # 意图分析（简化版）
            result.intent = self._analyze_intent(tool_name, args)

            # 风险评估
            result.risk_level = self._assess_risk(tool_name, args)

            # 上下文增强
            result.context.update({
                'tool_name': tool_name,
                'user_id': context.user_id,
                'group_id': context.group_id,
                'timestamp': datetime.now().isoformat()
            })

            # 检查是否通过
            result.passed = result.risk_level < 0.8  # 风险低于0.8则通过

            if not result.passed:
                result.message = f"⚠️ 工具执行被感知层拦截: 风险等级 {result.risk_level:.2f}"
                self.logger.warning(f"感知层拦截工具 {tool_name}: 风险 {result.risk_level:.2f}")

            self.logger.debug(f"感知层预处理完成: {tool_name}, 风险: {result.risk_level:.2f}")

        except Exception as e:
            self.logger.error(f"感知层预处理失败: {e}")
            result.passed = False
            result.message = f"❌ 感知层处理失败: {e}"

        return result

    def _analyze_intent(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        分析意图（简化版）

        Args:
            tool_name: 工具名称
            args: 参数

        Returns:
            意图类型
        """
        # 基于工具名的简单意图分类
        if 'memory' in tool_name.lower():
            return 'memory_operation'
        elif 'message' in tool_name.lower():
            return 'communication'
        elif 'search' in tool_name.lower():
            return 'query'
        elif 'trpg' in tool_name.lower() or 'tavern' in tool_name.lower():
            return 'entertainment'
        elif 'knowledge' in tool_name.lower():
            return 'knowledge_query'
        else:
            return 'general'

    def _assess_risk(self, tool_name: str, args: Dict[str, Any]) -> float:
        """
        评估风险等级（简化版）

        Args:
            tool_name: 工具名称
            args: 参数

        Returns:
            风险等级 (0-1)
        """
        risk = 0.0

        # 基于工具名的风险基础分
        dangerous_tools = ['delete', 'remove', 'clear', 'reset', 'python_interpreter']
        for dangerous in dangerous_tools:
            if dangerous in tool_name.lower():
                risk += 0.3
                break

        # 基于参数的风险加分
        if 'content' in args:
            content = str(args['content'])
            # 检查敏感词（简化）
            sensitive_words = ['删除', '清空', '密码', 'token']
            for word in sensitive_words:
                if word in content:
                    risk += 0.1

        return min(risk, 1.0)


class MLinkToolSubnet:
    """
    M-Link兼容的工具子网

    架构：
    1. 感知层（Perception Layer）
    2. M-Link传输层（MLink Transport Layer）
    3. 工具执行层（Tool Execution Layer）
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        emotion_system=None,
        memory_engine=None,
        enable_perception: bool = True,
        enable_mlink: bool = True
    ):
        """
        初始化M-Link工具子网

        Args:
            tool_registry: 工具注册表
            emotion_system: 情绪系统
            memory_engine: 记忆引擎
            enable_perception: 是否启用感知层
            enable_mlink: 是否启用M-Link
        """
        self.registry = tool_registry
        self.enable_perception = enable_perception
        self.enable_mlink = enable_mlink

        # 感知层
        self.perception_layer = PerceptionLayer(emotion_system) if enable_perception else None

        # 统计
        self.stats = {
            'total_calls': 0,
            'perception_blocked': 0,
            'perception_passed': 0,
            'mlink_sent': 0,
            'executed': 0,
            'failed': 0
        }

        self.logger = logging.getLogger("MLinkToolSubnet")
        self.logger.info("M-Link工具子网已启动")

        if enable_perception:
            self.logger.info("✅ 感知层已启用")
        if enable_mlink:
            self.logger.info("✅ M-Link传输已启用")

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext
    ) -> str:
        """
        执行工具（完整流程）

        流程：
        1. 感知层预处理
        2. M-Link传输（如果启用）
        3. 工具执行
        4. 结果处理

        Args:
            tool_name: 工具名称
            args: 工具参数
            context: 工具上下文

        Returns:
            执行结果
        """
        self.stats['total_calls'] += 1

        # 1. 感知层预处理
        if self.perception_layer:
            perception_result = await self.perception_layer.preprocess(
                tool_name,
                args,
                context
            )

            if not perception_result.passed:
                self.stats['perception_blocked'] += 1
                return perception_result.message

            self.stats['perception_passed'] += 1

            # 将感知结果注入上下文
            context.message_sent_this_turn = False
            context.__dict__.update(perception_result.context)

        # 2. M-Link传输
        if self.enable_mlink:
            # 创建M-Link消息
            mlink_message = MLinkMessage(
                flow_type=FlowType.DATA,
                content={
                    'tool_name': tool_name,
                    'args': args,
                    'context_data': {
                        'user_id': context.user_id,
                        'group_id': context.group_id,
                        'message_type': context.message_type
                    }
                },
                source="ToolNet",
                destination="ToolExecution"
            )

            self.stats['mlink_sent'] += 1
            self.logger.debug(f"M-Link消息已发送: {tool_name}")

        # 3. 执行工具
        try:
            result = await self.registry.execute_tool(tool_name, args, context)
            self.stats['executed'] += 1
            self.logger.info(f"工具执行成功: {tool_name}")
            return result

        except Exception as e:
            self.stats['failed'] += 1
            self.logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    async def execute_tool_batch(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ToolContext
    ) -> List[str]:
        """
        批量执行工具

        Args:
            tool_calls: 工具调用列表，每项包含 {tool_name, args}
            context: 工具上下文

        Returns:
            结果列表
        """
        results = []
        for call in tool_calls:
            tool_name = call.get('tool_name')
            args = call.get('args', {})
            result = await self.execute_tool(tool_name, args, context)
            results.append(result)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats['total_calls']
        return {
            'total_calls': total,
            'perception_blocked': self.stats['perception_blocked'],
            'perception_passed': self.stats['perception_passed'],
            'perception_rate': f"{(self.stats['perception_blocked'] / total * 100):.1f}%" if total > 0 else "0%",
            'mlink_sent': self.stats['mlink_sent'],
            'executed': self.stats['executed'],
            'failed': self.stats['failed'],
            'success_rate': f"{(self.stats['executed'] / total * 100):.1f}%" if total > 0 else "0%"
        }

    def health_check(self) -> bool:
        """健康检查"""
        return len(self.registry.tools) > 0

    async def shutdown(self):
        """关闭子网"""
        self.logger.info("M-Link工具子网正在关闭...")
        self.logger.info("M-Link工具子网已关闭")
