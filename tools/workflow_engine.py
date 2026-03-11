"""
工作流引擎
支持构建和执行复杂的工作流，包含条件分支、循环、并行等
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import uuid
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """节点类型"""
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"
    LOOP = "loop"


@dataclass
class NodeExecution:
    """节点执行记录"""
    node_id: str
    status: NodeStatus
    started_at: str
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class WorkflowNode:
    """工作流节点"""
    node_id: str
    name: str
    node_type: NodeType
    handler: Optional[Callable] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable] = None
    children: List['WorkflowNode'] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    max_retries: int = 0
    timeout: int = 300  # 超时时间（秒）
    enabled: bool = True
    on_failure: str = "continue"  # continue, stop, retry


@dataclass
class WorkflowExecution:
    """工作流执行"""
    execution_id: str
    workflow_id: str
    status: NodeStatus = NodeStatus.PENDING
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    node_executions: Dict[str, NodeExecution] = field(default_factory=dict)


class WorkflowEngine:
    """工作流引擎"""

    def __init__(self):
        """初始化工作流引擎"""
        self.workflows: Dict[str, 'Workflow'] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.running_executions: Dict[str, asyncio.Task] = {}

    def register_workflow(self, workflow: 'Workflow') -> None:
        """
        注册工作流

        Args:
            workflow: 工作流
        """
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"注册工作流: {workflow.name}")

    def execute_workflow(self, workflow_id: str,
                        variables: Dict[str, Any] = None) -> str:
        """
        执行工作流

        Args:
            workflow_id: 工作流ID
            variables: 初始变量

        Returns:
            执行ID
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")

        execution_id = str(uuid.uuid4())

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            variables=variables or {}
        )

        self.executions[execution_id] = execution

        # 启动异步执行
        task = asyncio.create_task(self._execute_workflow_async(execution))
        self.running_executions[execution_id] = task

        logger.info(f"启动工作流执行: {execution_id}")
        return execution_id

    async def _execute_workflow_async(self, execution: WorkflowExecution) -> None:
        """异步执行工作流"""
        workflow = self.workflows[execution.workflow_id]

        try:
            execution.status = NodeStatus.RUNNING

            # 执行起始节点
            for node in workflow.root_nodes:
                await self._execute_node(execution, node)

            # 检查所有节点是否完成
            if all(ne.status in [NodeStatus.COMPLETED, NodeStatus.SKIPPED]
                   for ne in execution.node_executions.values()):
                execution.status = NodeStatus.COMPLETED

        except Exception as e:
            execution.status = NodeStatus.FAILED
            logger.error(f"工作流执行失败: {execution.execution_id}, 错误: {e}")
        finally:
            execution.completed_at = datetime.now().isoformat()
            if execution.execution_id in self.running_executions:
                del self.running_executions[execution.execution_id]

    async def _execute_node(self, execution: WorkflowExecution,
                           node: WorkflowNode) -> Any:
        """
        执行节点

        Args:
            execution: 工作流执行
            node: 节点

        Returns:
            节点结果
        """
        if not node.enabled:
            execution.node_executions[node.node_id] = NodeExecution(
                node_id=node.node_id,
                status=NodeStatus.SKIPPED,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat()
            )
            return None

        # 检查依赖
        for dep_id in node.depends_on:
            if dep_id in execution.node_executions:
                dep_exec = execution.node_executions[dep_id]
                if dep_exec.status == NodeStatus.FAILED:
                    # 依赖失败
                    execution.node_executions[node.node_id] = NodeExecution(
                        node_id=node.node_id,
                        status=NodeStatus.SKIPPED,
                        started_at=datetime.now().isoformat(),
                        completed_at=datetime.now().isoformat()
                    )
                    return None

        # 创建节点执行记录
        node_execution = NodeExecution(
            node_id=node.node_id,
            status=NodeStatus.RUNNING,
            started_at=datetime.now().isoformat()
        )
        execution.node_executions[node.node_id] = node_execution

        try:
            # 根据节点类型执行
            if node.node_type == NodeType.TASK:
                result = await self._execute_task(execution, node)
            elif node.node_type == NodeType.CONDITION:
                result = await self._execute_condition(execution, node)
            elif node.node_type == NodeType.PARALLEL:
                result = await self._execute_parallel(execution, node)
            elif node.node_type == NodeType.SEQUENCE:
                result = await self._execute_sequence(execution, node)
            elif node.node_type == NodeType.LOOP:
                result = await self._execute_loop(execution, node)
            else:
                raise ValueError(f"不支持的节点类型: {node.node_type}")

            node_execution.status = NodeStatus.COMPLETED
            node_execution.result = result
            node_execution.completed_at = datetime.now().isoformat()

            # 更新工作流变量
            execution.variables.update(node.outputs)

            # 执行子节点
            for child in node.children:
                await self._execute_node(execution, child)

            return result

        except Exception as e:
            node_execution.status = NodeStatus.FAILED
            node_execution.error = str(e)
            node_execution.completed_at = datetime.now().isoformat()

            # 处理失败
            if node.on_failure == "retry" and node_execution.retry_count < node.max_retries:
                node_execution.retry_count += 1
                logger.info(f"重试节点: {node.node_id}, 第 {node_execution.retry_count} 次")
                await self._execute_node(execution, node)
            elif node.on_failure == "stop":
                raise e

            return None

    async def _execute_task(self, execution: WorkflowExecution,
                          node: WorkflowNode) -> Any:
        """执行任务节点"""
        if not node.handler:
            raise ValueError(f"任务节点缺少处理函数: {node.node_id}")

        # 合并输入和变量
        kwargs = {**execution.variables, **node.inputs}

        # 执行任务
        if asyncio.iscoroutinefunction(node.handler):
            result = await asyncio.wait_for(
                node.handler(**kwargs),
                timeout=node.timeout
            )
        else:
            result = await asyncio.to_thread(node.handler, **kwargs)

        # 更新输出
        if isinstance(result, dict):
            node.outputs.update(result)
        else:
            node.outputs['result'] = result

        return result

    async def _execute_condition(self, execution: WorkflowExecution,
                                node: WorkflowNode) -> Any:
        """执行条件节点"""
        if not node.condition:
            raise ValueError(f"条件节点缺少条件函数: {node.node_id}")

        # 执行条件
        if asyncio.iscoroutinefunction(node.condition):
            result = await node.condition(**execution.variables)
        else:
            result = node.condition(**execution.variables)

        node.outputs['condition_result'] = result

        return result

    async def _execute_parallel(self, execution: WorkflowExecution,
                               node: WorkflowNode) -> Any:
        """执行并行节点"""
        tasks = []
        for child in node.children:
            task = self._execute_node(execution, child)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def _execute_sequence(self, execution: WorkflowExecution,
                               node: WorkflowNode) -> Any:
        """执行序列节点"""
        results = []
        for child in node.children:
            result = await self._execute_node(execution, child)
            results.append(result)
        return results

    async def _execute_loop(self, execution: WorkflowExecution,
                           node: WorkflowNode) -> Any:
        """执行循环节点"""
        max_iterations = node.inputs.get('max_iterations', 10)
        iteration = 0

        results = []
        while iteration < max_iterations:
            # 执行循环体
            for child in node.children:
                result = await self._execute_node(execution, child)
                results.append(result)

            iteration += 1
            execution.variables['_loop_iteration'] = iteration

        return results

    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """
        获取执行状态

        Args:
            execution_id: 执行ID

        Returns:
            工作流执行
        """
        return self.executions.get(execution_id)

    def cancel_execution(self, execution_id: str) -> None:
        """
        取消执行

        Args:
            execution_id: 执行ID
        """
        if execution_id in self.running_executions:
            self.running_executions[execution_id].cancel()

        if execution_id in self.executions:
            self.executions[execution_id].status = NodeStatus.CANCELLED

        logger.info(f"取消工作流执行: {execution_id}")

    def list_executions(self, workflow_id: str = None) -> List[WorkflowExecution]:
        """
        列出执行记录

        Args:
            workflow_id: 工作流ID（可选）

        Returns:
            执行记录列表
        """
        if workflow_id:
            return [
                e for e in self.executions.values()
                if e.workflow_id == workflow_id
            ]
        return list(self.executions.values())


class Workflow:
    """工作流"""

    def __init__(self, workflow_id: str, name: str, description: str = ""):
        """
        初始化工作流

        Args:
            workflow_id: 工作流ID
            name: 工作流名称
            description: 描述
        """
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.root_nodes: List[WorkflowNode] = []

    def add_node(self, node: WorkflowNode) -> None:
        """
        添加节点

        Args:
            node: 工作流节点
        """
        self.nodes[node.node_id] = node

        # 如果没有依赖，作为根节点
        if not node.depends_on:
            self.root_nodes.append(node)

    def add_task(self, node_id: str, name: str, handler: Callable,
                inputs: Dict[str, Any] = None, depends_on: List[str] = None) -> WorkflowNode:
        """
        添加任务节点

        Args:
            node_id: 节点ID
            name: 节点名称
            handler: 处理函数
            inputs: 输入
            depends_on: 依赖的节点ID

        Returns:
            工作流节点
        """
        node = WorkflowNode(
            node_id=node_id,
            name=name,
            node_type=NodeType.TASK,
            handler=handler,
            inputs=inputs or {},
            depends_on=depends_on or []
        )
        self.add_node(node)
        return node

    def add_condition(self, node_id: str, name: str, condition: Callable,
                     true_child_id: str, false_child_id: str = None) -> WorkflowNode:
        """
        添加条件节点

        Args:
            node_id: 节点ID
            name: 节点名称
            condition: 条件函数
            true_child_id: 条件为真时的子节点ID
            false_child_id: 条件为假时的子节点ID

        Returns:
            工作流节点
        """
        node = WorkflowNode(
            node_id=node_id,
            name=name,
            node_type=NodeType.CONDITION,
            condition=condition,
            depends_on=[]
        )
        self.add_node(node)
        return node

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'nodes': {
                node_id: {
                    'node_id': node.node_id,
                    'name': node.name,
                    'node_type': node.node_type.value,
                    'depends_on': node.depends_on,
                    'enabled': node.enabled
                }
                for node_id, node in self.nodes.items()
            }
        }

    def save(self, path: str) -> None:
        """
        保存工作流

        Args:
            path: 文件路径
        """
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"工作流已保存: {path}")


class WorkflowBuilder:
    """工作流构建器"""

    def __init__(self, workflow_id: str, name: str, description: str = ""):
        """
        初始化构建器

        Args:
            workflow_id: 工作流ID
            name: 工作流名称
            description: 描述
        """
        self.workflow = Workflow(workflow_id, name, description)

    def task(self, node_id: str, name: str, handler: Callable,
             inputs: Dict[str, Any] = None, depends_on: List[str] = None) -> 'WorkflowBuilder':
        """添加任务节点"""
        self.workflow.add_task(node_id, name, handler, inputs, depends_on)
        return self

    def condition(self, node_id: str, name: str, condition: Callable,
                 true_child_id: str, false_child_id: str = None) -> 'WorkflowBuilder':
        """添加条件节点"""
        self.workflow.add_condition(node_id, name, condition, true_child_id, false_child_id)
        return self

    def build(self) -> Workflow:
        """构建工作流"""
        return self.workflow


# 便捷函数
def create_simple_workflow(name: str, tasks: List[Dict]) -> Workflow:
    """
    创建简单的工作流

    Args:
        name: 工作流名称
        tasks: 任务列表，每个任务包含id, name, handler, depends_on

    Returns:
        工作流
    """
    workflow_id = f"wf_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
    workflow = Workflow(workflow_id, name)

    for task_info in tasks:
        workflow.add_task(
            node_id=task_info['id'],
            name=task_info['name'],
            handler=task_info['handler'],
            inputs=task_info.get('inputs', {}),
            depends_on=task_info.get('depends_on', [])
        )

    return workflow


if __name__ == "__main__":
    # 示例使用
    engine = WorkflowEngine()

    # 定义任务函数
    def task1():
        print("执行任务1")
        return "task1_result"

    def task2():
        print("执行任务2")
        return "task2_result"

    def task3():
        print("执行任务3")
        return "task3_result"

    # 构建工作流
    builder = WorkflowBuilder("example_workflow", "示例工作流")

    builder.task("task1", "任务1", task1)
    builder.task("task2", "任务2", task2, depends_on=["task1"])
    builder.task("task3", "任务3", task3, depends_on=["task1"])

    workflow = builder.build()

    # 注册并执行工作流
    engine.register_workflow(workflow)
    execution_id = engine.execute_workflow("example_workflow")

    print(f"工作流执行ID: {execution_id}")

    import time
    time.sleep(1)

    # 查询状态
    execution = engine.get_execution_status(execution_id)
    print(f"执行状态: {execution.status}")
    print(f"节点执行记录: {execution.node_executions}")
