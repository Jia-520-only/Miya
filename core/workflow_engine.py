"""
自动化工作流引擎 - 弥娅V4.0

支持复杂自动化任务和工作流编排
"""

import asyncio
from typing import Dict, List, Optional, Callable
from enum import Enum
import json

class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class WorkflowStep:
    """工作流步骤"""
    
    def __init__(
        self,
        id: str,
        name: str,
        command: str,
        target_terminal: str = None,
        condition: str = None,
        on_success: List[str] = None,
        on_failure: List[str] = None,
        timeout: int = 60
    ):
        self.id = id
        self.name = name
        self.command = command
        self.target_terminal = target_terminal
        self.condition = condition
        self.on_success = on_success or []
        self.on_failure = on_failure or []
        self.timeout = timeout

class Workflow:
    """工作流"""
    
    def __init__(
        self,
        id: str,
        name: str,
        description: str = "",
        steps: List[WorkflowStep] = None,
        variables: Dict = None
    ):
        self.id = id
        self.name = name
        self.description = description
        self.steps = steps or []
        self.variables = variables or {}
        self.status = WorkflowStatus.PENDING
        self.current_step_index = 0
        self.execution_log = []
    
    def add_step(self, step: WorkflowStep):
        """添加步骤"""
        self.steps.append(step)
    
    def set_variable(self, name: str, value: any):
        """设置变量"""
        self.variables[name] = value
    
    def get_variable(self, name: str, default: any = None) -> any:
        """获取变量"""
        return self.variables.get(name, default)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "steps_count": len(self.steps),
            "status": self.status.value
        }

class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, terminal_manager):
        self.terminal_manager = terminal_manager
        self.workflows: Dict[str, Workflow] = {}
        self.running_workflows: Dict[str, Workflow] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
    
    def create_workflow(
        self,
        workflow_id: str,
        name: str,
        description: str = "",
        steps: List[WorkflowStep] = None
    ) -> Workflow:
        """创建工作流
        
        Args:
            workflow_id: 工作流ID
            name: 名称
            description: 描述
            steps: 步骤列表
            
        Returns:
            工作流对象
        """
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            steps=steps
        )
        
        self.workflows[workflow_id] = workflow
        
        return workflow
    
    async def execute_workflow(
        self,
        workflow_id: str,
        variables: Dict = None
    ) -> Dict:
        """执行工作流
        
        Args:
            workflow_id: 工作流ID
            variables: 初始变量
            
        Returns:
            执行结果
        """
        
        if workflow_id not in self.workflows:
            return {
                "success": False,
                "error": f"工作流不存在: {workflow_id}"
            }
        
        workflow = self.workflows[workflow_id]
        
        # 合并变量
        if variables:
            workflow.variables.update(variables)
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.current_step_index = 0
        self.running_workflows[workflow_id] = workflow
        
        # 触发开始事件
        await self._trigger_event('workflow_start', {
            "workflow_id": workflow_id,
            "name": workflow.name
        })
        
        results = {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "steps_executed": [],
            "steps_failed": [],
            "variables": {}
        }
        
        try:
            # 执行步骤
            while workflow.current_step_index < len(workflow.steps):
                step = workflow.steps[workflow.current_step_index]
                
                # 检查条件
                if not self._evaluate_condition(step.condition, workflow.variables):
                    workflow.current_step_index += 1
                    continue
                
                # 执行步骤
                step_result = await self._execute_step(step, workflow)
                
                results['steps_executed'].append({
                    "step_id": step.id,
                    "name": step.name,
                    "success": step_result['success']
                })
                
                if not step_result['success']:
                    results['steps_failed'].append(step.id)
                    
                    # 失败后处理
                    if step.on_failure:
                        await self._handle_branch(
                            step.on_failure,
                            workflow,
                            results
                        )
                    
                    workflow.status = WorkflowStatus.FAILED
                    break
                
                # 成功后处理
                if step.on_success:
                    await self._handle_branch(
                        step.on_success,
                        workflow,
                        results
                    )
                
                # 保存变量
                if 'variables' in step_result:
                    workflow.variables.update(step_result['variables'])
                
                workflow.current_step_index += 1
            
            if workflow.status != WorkflowStatus.FAILED:
                workflow.status = WorkflowStatus.COMPLETED
            
            results['success'] = True
            results['final_variables'] = workflow.variables
        
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            results['success'] = False
            results['error'] = str(e)
        
        finally:
            # 移除运行中的工作流
            if workflow_id in self.running_workflows:
                del self.running_workflows[workflow_id]
            
            # 触发完成事件
            await self._trigger_event('workflow_complete', {
                "workflow_id": workflow_id,
                "status": workflow.status.value
            })
        
        return results
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        workflow: Workflow
    ) -> Dict:
        """执行单个步骤
        
        Args:
            step: 工作流步骤
            workflow: 工作流
            
        Returns:
            执行结果
        """
        
        result = {
            "step_id": step.id,
            "success": False,
            "output": "",
            "variables": {}
        }
        
        try:
            # 替换变量
            command = self._substitute_variables(
                step.command,
                workflow.variables
            )
            
            # 确定目标终端
            target_terminal = step.target_terminal or self.terminal_manager.active_session_id
            
            if not target_terminal:
                target_terminal = list(self.terminal_manager.sessions.keys())[0]
            
            # 执行命令
            cmd_result = await self.terminal_manager.execute_command(
                target_terminal,
                command,
                timeout=step.timeout
            )
            
            result['success'] = cmd_result.success
            result['output'] = cmd_result.output
            
            # 解析输出为变量（简化版）
            if cmd_result.success:
                result['variables'] = self._parse_output_variables(
                    cmd_result.output
                )
        
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _handle_branch(
        self,
        branch: List[str],
        workflow: Workflow,
        results: Dict
    ):
        """处理分支
        
        Args:
            branch: 分支列表
            workflow: 工作流
            results: 结果
        """
        
        for step_id in branch:
            if step_id in self.workflows:
                # 执行另一个工作流
                branch_results = await self.execute_workflow(
                    step_id, workflow.variables
                )
                results['branch_results'] = results.get('branch_results', {})
                results['branch_results'][step_id] = branch_results
    
    def _evaluate_condition(
        self,
        condition: str,
        variables: Dict
    ) -> bool:
        """评估条件
        
        Args:
            condition: 条件表达式
            variables: 变量
            
        Returns:
            是否满足条件
        """
        
        if not condition:
            return True
        
        # 简化实现：支持基本的变量比较
        try:
            # 替换变量
            expr = self._substitute_variables(condition, variables)
            
            # 评估（简化版，实际应该用更安全的表达式求值器）
            if '==' in expr:
                parts = expr.split('==')
                return parts[0].strip() == parts[1].strip()
            
            return bool(expr)
        
        except:
            return False
    
    def _substitute_variables(
        self,
        text: str,
        variables: Dict
    ) -> str:
        """替换变量
        
        Args:
            text: 文本
            variables: 变量字典
            
        Returns:
            替换后的文本
        """
        
        result = text
        
        for name, value in variables.items():
            placeholder = f"${{{name}}}"
            result = result.replace(placeholder, str(value))
        
        return result
    
    def _parse_output_variables(
        self,
        output: str
    ) -> Dict:
        """从输出解析变量
        
        Args:
            output: 命令输出
            
        Returns:
            变量字典
        """
        
        # 简化实现：解析格式为 key=value 的行
        variables = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                parts = line.split('=', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                variables[key] = value
        
        return variables
    
    async def _trigger_event(
        self,
        event_name: str,
        event_data: Dict
    ):
        """触发事件
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
        """
        
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    await handler(event_data)
                except Exception as e:
                    print(f"[事件处理器错误] {e}")
    
    def register_event_handler(
        self,
        event_name: str,
        handler: Callable
    ):
        """注册事件处理器
        
        Args:
            event_name: 事件名称
            handler: 处理器函数
        """
        
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        
        self.event_handlers[event_name].append(handler)
    
    def save_workflow(
        self,
        workflow_id: str,
        workflow_data: Dict
    ):
        """保存工作流定义
        
        Args:
            workflow_id: 工作流ID
            workflow_data: 工作流数据
        """
        
        import os
        
        workflows_dir = "data/workflows"
        os.makedirs(workflows_dir, exist_ok=True)
        
        workflow_file = os.path.join(workflows_dir, f"{workflow_id}.json")
        
        with open(workflow_file, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, indent=2, ensure_ascii=False)
    
    def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """加载工作流
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流对象或None
        """
        
        import os
        
        workflows_dir = "data/workflows"
        workflow_file = os.path.join(workflows_dir, f"{workflow_id}.json")
        
        if not os.path.exists(workflow_file):
            return None
        
        with open(workflow_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 转换为步骤对象
        steps = []
        for step_data in data.get('steps', []):
            step = WorkflowStep(
                id=step_data['id'],
                name=step_data['name'],
                command=step_data['command'],
                target_terminal=step_data.get('target_terminal'),
                condition=step_data.get('condition'),
                on_success=step_data.get('on_success'),
                on_failure=step_data.get('on_failure'),
                timeout=step_data.get('timeout', 60)
            )
            steps.append(step)
        
        workflow = Workflow(
            id=workflow_id,
            name=data['name'],
            description=data.get('description', ''),
            steps=steps,
            variables=data.get('variables', {})
        )
        
        self.workflows[workflow_id] = workflow
        
        return workflow
