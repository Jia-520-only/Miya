"""
命令链管理模块
支持多步骤命令执行流程，能够跟踪状态并智能判断下一步操作
"""
import logging
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    SKIPPED = "skipped"       # 跳过


@dataclass
class Step:
    """执行步骤"""
    id: str
    name: str
    command: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None

    def execute(self, executor: Callable[[str], Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """
        执行步骤

        Args:
            executor: 执行器函数
            context: 执行上下文

        Returns:
            是否执行成功
        """
        # 检查条件
        if self.condition and not self.condition(context):
            self.status = StepStatus.SKIPPED
            logger.info(f"[命令链] 步骤 {self.id} 被跳过（条件不满足）")
            return True

        # 检查依赖
        for dep_id in self.dependencies:
            dep_step = context.get('steps', {}).get(dep_id)
            if dep_step and dep_step.status != StepStatus.SUCCESS:
                self.status = StepStatus.FAILED
                self.error = f"依赖步骤 {dep_id} 失败"
                logger.error(f"[命令链] 步骤 {self.id} 失败：{self.error}")
                return False

        self.status = StepStatus.RUNNING
        logger.info(f"[命令链] 执行步骤 {self.id}: {self.name}")

        try:
            # 执行命令
            result = executor(self.command)

            self.output = result.get('stdout', '')
            self.error = result.get('stderr', '')
            self.execution_time = result.get('execution_time', 0.0)

            if result.get('success'):
                self.status = StepStatus.SUCCESS
                logger.info(f"[命令链] 步骤 {self.id} 成功（耗时 {self.execution_time:.2f}s）")
                return True
            else:
                self.status = StepStatus.FAILED
                logger.error(f"[命令链] 步骤 {self.id} 失败：{self.error}")
                return False

        except Exception as e:
            self.status = StepStatus.FAILED
            self.error = str(e)
            logger.error(f"[命令链] 步骤 {self.id} 异常：{e}")
            return False


@dataclass
class CommandChain:
    """命令链"""
    id: str
    name: str
    description: str = ""
    steps: List[Step] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    current_step_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: Step) -> 'CommandChain':
        """添加步骤"""
        self.steps.append(step)
        return self

    def get_next_step(self) -> Optional[Step]:
        """获取下一步骤"""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def execute_step(self, executor: Callable[[str], Dict[str, Any]]) -> bool:
        """
        执行当前步骤

        Args:
            executor: 执行器函数

        Returns:
            是否执行成功
        """
        step = self.get_next_step()
        if not step:
            logger.info(f"[命令链] {self.id} 所有步骤已完成")
            self.status = StepStatus.SUCCESS
            self.completed_at = datetime.now()
            return True

        if not self.started_at:
            self.started_at = datetime.now()
            self.status = StepStatus.RUNNING
            self.context['steps'] = {s.id: s for s in self.steps}

        success = step.execute(executor, self.context)

        if step.status == StepStatus.SUCCESS:
            # 成功，移动到下一步
            self.current_step_index += 1

            # 检查是否还有步骤
            if self.current_step_index >= len(self.steps):
                self.status = StepStatus.SUCCESS
                self.completed_at = datetime.now()
                logger.info(f"[命令链] {self.id} 全部完成")

        elif step.status == StepStatus.FAILED:
            # 失败，停止执行
            self.status = StepStatus.FAILED
            self.completed_at = datetime.now()
            logger.error(f"[命令链] {self.id} 执行失败于步骤 {step.id}")

        return success

    def execute_all(self, executor: Callable[[str], Dict[str, Any]]) -> bool:
        """
        执行所有步骤

        Args:
            executor: 执行器函数

        Returns:
            是否全部成功
        """
        while self.get_next_step() and self.status not in [StepStatus.SUCCESS, StepStatus.FAILED]:
            if not self.execute_step(executor):
                return False
        return self.status == StepStatus.SUCCESS

    def get_progress(self) -> Dict[str, Any]:
        """获取执行进度"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.SUCCESS)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'progress_percent': (completed / total * 100) if total > 0 else 0,
            'current_step': self.current_step_index,
            'status': self.status.value,
        }

    def get_report(self) -> str:
        """获取执行报告"""
        lines = [
            f"命令链: {self.name}",
            f"状态: {self.status.value}",
            f"进度: {self.get_progress()['progress_percent']:.1f}%",
            f"开始时间: {self.started_at}",
            f"完成时间: {self.completed_at}",
            "",
            "步骤详情:",
        ]

        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.SUCCESS: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }[step.status]

            lines.append(f"{status_icon} {i}. {step.name}")
            lines.append(f"   命令: {step.command}")
            if step.output:
                lines.append(f"   输出: {step.output[:100]}...")
            if step.error:
                lines.append(f"   错误: {step.error[:100]}...")

        return "\n".join(lines)


class CommandChainManager:
    """命令链管理器"""

    def __init__(self):
        self.chains: Dict[str, CommandChain] = {}
        self.templates: Dict[str, CommandChain] = {}

    def create_chain(self, id: str, name: str, description: str = "") -> CommandChain:
        """创建命令链"""
        chain = CommandChain(
            id=id,
            name=name,
            description=description
        )
        self.chains[id] = chain
        logger.info(f"[命令链管理器] 创建命令链: {id}")
        return chain

    def register_template(self, template: CommandChain) -> None:
        """注册命令链模板"""
        self.templates[template.id] = template
        logger.info(f"[命令链管理器] 注册模板: {template.id}")

    def get_template(self, id: str) -> Optional[CommandChain]:
        """获取命令链模板"""
        return self.templates.get(id)

    def get_chain(self, id: str) -> Optional[CommandChain]:
        """获取命令链"""
        return self.chains.get(id)

    def execute_chain(self, chain_id: str, executor: Callable[[str], Dict[str, Any]]) -> bool:
        """执行命令链"""
        chain = self.get_chain(chain_id)
        if not chain:
            logger.error(f"[命令链管理器] 命令链不存在: {chain_id}")
            return False

        logger.info(f"[命令链管理器] 开始执行命令链: {chain_id}")
        return chain.execute_all(executor)

    def list_chains(self) -> List[Dict[str, Any]]:
        """列出所有命令链"""
        return [
            {
                'id': chain.id,
                'name': chain.name,
                'status': chain.status.value,
                'progress': chain.get_progress(),
            }
            for chain in self.chains.values()
        ]
