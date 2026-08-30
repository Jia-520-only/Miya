"""
功能开发工作流 (Feature Development Workflow)
遵循 Claude Code feature-dev 插件的 7 阶段开发流程
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class Phase(Enum):
    DISCOVERY = "discovery"  # 理解需求
    EXPLORATION = "exploration"  # 代码库探索
    CLARIFICATION = "clarification"  # 澄清问题
    PLANNING = "planning"  # 架构设计
    IMPLEMENTATION = "implementation"  # 实现
    REVIEW = "review"  # 审查
    COMPLETION = "completion"  # 完成


@dataclass
class FeatureContext:
    feature_name: str = ""
    description: str = ""
    current_phase: Phase = Phase.DISCOVERY
    findings: Dict[str, Any] = None
    questions: List[str] = None
    plan: str = ""
    implementation: str = ""

    def __post_init__(self):
        if self.findings is None:
            self.findings = {}
        if self.questions is None:
            self.questions = []


class FeatureDevWorkflow:
    """功能开发工作流"""

    def __init__(self):
        self.active_workflows: Dict[str, FeatureContext] = {}

    async def start(self, feature_request: str, context: Dict[str, Any] = None) -> str:
        """开始功能开发工作流"""
        session_id = context.get("session_id", "default") if context else "default"

        ctx = FeatureContext(feature_name=feature_request, current_phase=Phase.DISCOVERY)
        self.active_workflows[session_id] = ctx

        return self._format_discovery_phase(feature_request)

    def _format_discovery_phase(self, feature_request: str) -> str:
        """格式化发现阶段"""
        return f"""## Phase 1: Discovery

收到功能请求: **{feature_request}**

我需要确认一些细节:

1. **这个功能要解决什么问题？** 描述一下你想要实现的功能背景
2. **有什么特定的约束吗？** 比如性能要求、兼容性要求、依赖限制等
3. **你希望它如何工作？** 描述一下期望的行为
4. **有参考的实现吗？** 可以是类似的现有功能或者其他项目的实现

请回答这些问题，我会继续进行下一阶段。"""

    async def continue_workflow(self, user_response: str, context: Dict[str, Any] = None) -> str:
        """继续工作流"""
        session_id = context.get("session_id", "default") if context else "default"

        if session_id not in self.active_workflows:
            return "没有活跃的功能开发会话。请使用 /feature-dev start 来开始新功能开发。"

        ctx = self.active_workflows[session_id]

        if ctx.current_phase == Phase.DISCOVERY:
            ctx.description = user_response
            ctx.current_phase = Phase.EXPLORATION
            return self._format_exploration_phase(ctx)

        elif ctx.current_phase == Phase.EXPLORATION:
            ctx.findings["user_clarifications"] = user_response
            ctx.current_phase = Phase.CLARIFICATION
            return self._format_clarification_phase(ctx)

        elif ctx.current_phase == Phase.CLARIFICATION:
            ctx.questions.append(user_response)
            ctx.current_phase = Phase.PLANNING
            return self._format_planning_phase(ctx)

        elif ctx.current_phase == Phase.PLANNING:
            ctx.plan = user_response
            ctx.current_phase = Phase.IMPLEMENTATION
            return self._format_implementation_phase(ctx)

        elif ctx.current_phase == Phase.IMPLEMENTATION:
            ctx.implementation = user_response
            ctx.current_phase = Phase.REVIEW
            return self._format_review_phase(ctx)

        elif ctx.current_phase == Phase.REVIEW:
            ctx.findings["review_feedback"] = user_response
            ctx.current_phase = Phase.COMPLETION
            return self._format_completion_phase(ctx)

        return "工作流已完成"

    def _format_exploration_phase(self, ctx: FeatureContext) -> str:
        """格式化探索阶段"""
        return f"""## Phase 2: Exploration

正在探索代码库，寻找与「{ctx.feature_name}」相关的实现...

我将并行启动多个 code-explorer agents 来探索:
1. 寻找类似的现有功能
2. 映射相关架构和抽象
3. 分析相关功能的当前实现

探索完成后，我会呈现发现的关键文件和代码模式。请稍候... (待实现 Agent 调用)"""

    def _format_clarification_phase(self, ctx: FeatureContext) -> str:
        """格式化澄清阶段"""
        questions = [
            "这个功能有哪些边界情况需要处理？",
            "错误处理有什么特别要求吗？",
            "是否需要考虑向后兼容？",
            "性能目标是什么？（响应时间、并发数等）",
            "是否需要与其他系统或服务集成？",
        ]

        return f"""## Phase 3: Clarification

基于探索阶段的发现，我有一些问题需要澄清:

{chr(10).join(f"{i + 1}. {q}" for i, q in enumerate(questions))}

请回答这些问题，以便我进行架构设计。"""

    def _format_planning_phase(self, ctx: FeatureContext) -> str:
        """格式化规划阶段"""
        return """## Phase 4: Planning

基于你的回答，我现在将启动 code-architect agent 来设计架构...

设计将包括:
- 模块划分
- 数据流设计
- API 接口定义
- 关键实现细节

(待实现与 code_architect agent 的集成)"""

    def _format_implementation_phase(self, ctx: FeatureContext) -> str:
        """格式化实现阶段"""
        return """## Phase 5: Implementation

架构设计已完成。现在开始实现...

我将按照以下步骤:
1. 创建必要的文件结构
2. 实现核心功能
3. 添加单元测试
4. 更新相关文档

(待实现代码生成)"""

    def _format_review_phase(self, ctx: FeatureContext) -> str:
        """格式化审查阶段"""
        return """## Phase 6: Review

实现已完成。现在启动 code-reviewer agent 进行代码审查...

审查将检查:
- 代码质量
- 潜在的 bug
- 安全问题
- 性能问题
- 可维护性

(待实现与 code_reviewer agent 的集成)"""

    def _format_completion_phase(self, ctx: FeatureContext) -> str:
        """格式化完成阶段"""
        return f"""## Phase 7: Completion

功能开发工作流完成！

**功能**: {ctx.feature_name}
**描述**: {ctx.description}

下一步:
- 运行完整测试
- 提交代码
- 更新文档

感谢使用功能开发工作流！"""

    async def get_status(self, context: Dict[str, Any] = None) -> str:
        """获取当前工作流状态"""
        session_id = context.get("session_id", "default") if context else "default"

        if session_id not in self.active_workflows:
            return "没有活跃的功能开发会话"

        ctx = self.active_workflows[session_id]
        return f"""当前阶段: {ctx.current_phase.value}
功能: {ctx.feature_name}
描述: {ctx.description}"""

    async def cancel(self, context: Dict[str, Any] = None) -> str:
        """取消工作流"""
        session_id = context.get("session_id", "default") if context else "default"

        if session_id in self.active_workflows:
            del self.active_workflows[session_id]
            return "功能开发工作流已取消"

        return "没有活跃的工作流可取消"


_workflow = FeatureDevWorkflow()


async def start_feature_dev(feature_request: str, context: Dict[str, Any] = None) -> str:
    """开始功能开发"""
    return await _workflow.start(feature_request, context)


async def continue_feature_dev(user_response: str, context: Dict[str, Any] = None) -> str:
    """继续功能开发"""
    return await _workflow.continue_workflow(user_response, context)


async def get_feature_dev_status(context: Dict[str, Any] = None) -> str:
    """获取功能开发状态"""
    return await _workflow.get_status(context)


async def cancel_feature_dev(context: Dict[str, Any] = None) -> str:
    """取消功能开发"""
    return await _workflow.cancel(context)
