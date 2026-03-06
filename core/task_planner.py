"""
任务规划模块
负责将复杂任务分解为可执行的子任务，并管理任务依赖关系
"""
import logging
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime等特殊类型"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    description: str
    tool_name: Optional[str] = None  # 需要调用的工具
    tool_params: Dict = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)  # 依赖的任务ID
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # 优先级，数字越大优先级越高
    max_retries: int = 3
    retry_count: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'tool_name': self.tool_name,
            'tool_params': self.tool_params,
            'dependencies': list(self.dependencies),
            'status': self.status.value,
            'priority': self.priority,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        """从字典创建"""
        dependencies = set(data.get('dependencies', []))
        task = cls(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            tool_name=data.get('tool_name'),
            tool_params=data.get('tool_params', {}),
            dependencies=dependencies,
            status=TaskStatus(data.get('status', 'pending')),
            priority=data.get('priority', 0),
            max_retries=data.get('max_retries', 3),
            retry_count=data.get('retry_count', 0),
            result=data.get('result'),
            error=data.get('error'),
            metadata=data.get('metadata', {})
        )
        
        if data.get('created_at'):
            task.created_at = datetime.fromisoformat(data['created_at'])
        if data.get('started_at'):
            task.started_at = datetime.fromisoformat(data['started_at'])
        if data.get('completed_at'):
            task.completed_at = datetime.fromisoformat(data['completed_at'])
        
        return task


class TaskPlanner:
    """
    任务规划器
    
    功能：
    1. 使用LLM将复杂任务分解为子任务
    2. 构建任务依赖图
    3. 管理任务执行顺序
    4. 支持任务优先级调度
    5. 任务状态持久化
    """
    
    def __init__(self, ai_client=None, storage_path: Optional[str] = None):
        """
        初始化任务规划器
        
        Args:
            ai_client: AI客户端（用于任务分解）
            storage_path: 任务存储路径
        """
        self.ai_client = ai_client
        self.storage_path = storage_path
        self.tasks: Dict[str, Task] = {}
        self._task_id_counter = 0
        
    def _generate_task_id(self) -> str:
        """生成任务ID"""
        self._task_id_counter += 1
        return f"task_{self._task_id_counter}"
    
    async def decompose_task(
        self,
        goal: str,
        context: Optional[Dict] = None,
        tools: Optional[List[Dict]] = None
    ) -> List[Task]:
        """
        使用AI将目标分解为子任务
        
        Args:
            goal: 用户目标
            context: 上下文信息
            tools: 可用工具列表
            
        Returns:
            子任务列表
        """
        if not self.ai_client:
            # 如果没有AI客户端，创建一个单任务
            task = Task(
                id=self._generate_task_id(),
                name="主任务",
                description=goal,
                priority=0
            )
            return [task]
        
        # 构建任务分解提示词
        prompt = self._build_decomposition_prompt(goal, context, tools)
        
        try:
            # 调用AI进行任务分解
            response = await self.ai_client.chat_with_system_prompt(
                system_prompt="""你是一个任务规划专家。你需要将用户的复杂目标分解为一系列可执行的子任务。

任务分解规则：
1. 每个子任务应该是独立的、可执行的
2. 子任务之间可以有依赖关系（例如：任务B需要等待任务A完成）
3. 使用提供的工具来完成子任务
4. 如果没有合适的工具，使用 natural_language 模式（让AI生成自然语言回复）

输出格式（JSON）：
{
  "tasks": [
    {
      "name": "任务名称",
      "description": "详细描述",
      "tool_name": "工具名称（或 'natural_language'）",
      "tool_params": {"参数名": "参数值"},
      "dependencies": ["依赖的任务ID"],
      "priority": 优先级（0-10，数字越大优先级越高）
    }
  ]
}""",
                user_message=prompt
            )
            
            # 解析AI返回的任务列表
            return self._parse_tasks_from_ai(response)
            
        except Exception as e:
            logger.error(f"任务分解失败: {e}")
            # 降级：创建一个单任务
            task = Task(
                id=self._generate_task_id(),
                name="主任务",
                description=goal,
                priority=0
            )
            return [task]
    
    def _build_decomposition_prompt(
        self,
        goal: str,
        context: Optional[Dict],
        tools: Optional[List[Dict]]
    ) -> str:
        """构建任务分解提示词"""
        prompt_parts = [f"用户目标: {goal}\n"]
        
        if tools:
            prompt_parts.append("\n可用工具:")
            for tool in tools:
                name = tool.get('function', {}).get('name', 'unknown')
                desc = tool.get('function', {}).get('description', '')
                prompt_parts.append(f"- {name}: {desc}")
        
        if context:
            prompt_parts.append(f"\n上下文信息: {json.dumps(context, ensure_ascii=False, cls=CustomJSONEncoder)}")
        
        return "\n".join(prompt_parts)
    
    def _parse_tasks_from_ai(self, response: str) -> List[Task]:
        """从AI响应解析任务列表"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError("未找到JSON格式的任务列表")
            
            data = json.loads(json_match.group())
            tasks_data = data.get('tasks', [])
            
            tasks = []
            for i, task_data in enumerate(tasks_data):
                task = Task(
                    id=self._generate_task_id(),
                    name=task_data.get('name', f'任务{i+1}'),
                    description=task_data.get('description', ''),
                    tool_name=task_data.get('tool_name'),
                    tool_params=task_data.get('tool_params', {}),
                    dependencies=set(task_data.get('dependencies', [])),
                    priority=task_data.get('priority', 0)
                )
                tasks.append(task)
            
            # 修正依赖关系中的任务ID
            task_id_map = {task.name: task.id for task in tasks}
            for task in tasks:
                new_deps = set()
                for dep_name in task.dependencies:
                    if dep_name in task_id_map:
                        new_deps.add(task_id_map[dep_name])
                task.dependencies = new_deps
            
            return tasks
            
        except Exception as e:
            logger.error(f"解析任务列表失败: {e}")
            raise
    
    def add_tasks(self, tasks: List[Task]) -> None:
        """添加任务到规划器"""
        for task in tasks:
            self.tasks[task.id] = task
        
        # 更新任务状态
        self._update_task_statuses()
        
        logger.info(f"添加了 {len(tasks)} 个任务")
    
    def _update_task_statuses(self) -> None:
        """更新所有任务的状态"""
        for task in self.tasks.values():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]:
                continue
            
            # 检查依赖是否都已满足
            pending_deps = []
            for dep_id in task.dependencies:
                dep_task = self.tasks.get(dep_id)
                if not dep_task:
                    logger.warning(f"任务 {task.id} 的依赖 {dep_id} 不存在")
                    continue
                
                if dep_task.status != TaskStatus.COMPLETED:
                    pending_deps.append(dep_id)
            
            if pending_deps:
                task.status = TaskStatus.BLOCKED
            elif task.status == TaskStatus.BLOCKED:
                task.status = TaskStatus.READY
    
    def get_ready_tasks(self) -> List[Task]:
        """获取可以执行的任务（按优先级排序）"""
        ready_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.READY
        ]
        return sorted(ready_tasks, key=lambda t: (-t.priority, t.created_at))
    
    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行的任务"""
        ready_tasks = self.get_ready_tasks()
        return ready_tasks[0] if ready_tasks else None
    
    def mark_task_started(self, task_id: str) -> None:
        """标记任务为开始执行"""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            logger.info(f"任务 {task_id} 开始执行")
    
    def mark_task_completed(self, task_id: str, result: str) -> None:
        """标记任务为完成"""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            logger.info(f"任务 {task_id} 完成")
            
            # 更新被阻塞的任务
            self._update_task_statuses()
    
    def mark_task_failed(self, task_id: str, error: str) -> None:
        """标记任务为失败"""
        task = self.tasks.get(task_id)
        if task:
            task.retry_count += 1
            task.error = error
            
            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                logger.error(f"任务 {task_id} 失败（达到最大重试次数）")
                
                # 将依赖此任务的其他任务标记为跳过
                self._mark_dependent_tasks_skipped(task_id)
            else:
                task.status = TaskStatus.READY  # 允许重试
                logger.warning(f"任务 {task_id} 失败，将重试（{task.retry_count}/{task.max_retries}）")
    
    def _mark_dependent_tasks_skipped(self, failed_task_id: str) -> None:
        """标记依赖失败任务的所有任务为跳过"""
        for task in self.tasks.values():
            if failed_task_id in task.dependencies and task.status == TaskStatus.BLOCKED:
                task.status = TaskStatus.SKIPPED
                task.error = f"依赖任务 {failed_task_id} 失败"
                logger.info(f"任务 {task.id} 被标记为跳过（依赖失败）")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_task_graph(self) -> Dict:
        """获取任务图（用于可视化）"""
        nodes = []
        edges = []
        
        for task in self.tasks.values():
            nodes.append({
                'id': task.id,
                'label': task.name,
                'status': task.status.value,
                'priority': task.priority
            })
            
            for dep_id in task.dependencies:
                edges.append({
                    'from': dep_id,
                    'to': task.id
                })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def is_complete(self) -> bool:
        """检查是否所有任务都已完成"""
        for task in self.tasks.values():
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]:
                return False
        return True
    
    def get_summary(self) -> Dict:
        """获取任务执行摘要"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for task in self.tasks.values()
                if task.status == status
            )
        
        return {
            'total': len(self.tasks),
            'completed': status_counts['completed'],
            'failed': status_counts['failed'],
            'skipped': status_counts['skipped'],
            'running': status_counts['running'],
            'ready': status_counts['ready'],
            'blocked': status_counts['blocked'],
            'pending': status_counts['pending'],
            'is_complete': self.is_complete()
        }
    
    def save_to_file(self, path: Optional[str] = None) -> bool:
        """保存任务到文件"""
        save_path = path or self.storage_path
        if not save_path:
            return False
        
        try:
            data = {
                'tasks': [task.to_dict() for task in self.tasks.values()],
                'task_id_counter': self._task_id_counter
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"任务已保存到 {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            return False
    
    def load_from_file(self, path: Optional[str] = None) -> bool:
        """从文件加载任务"""
        load_path = path or self.storage_path
        if not load_path:
            return False
        
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.tasks = {}
            for task_data in data.get('tasks', []):
                task = Task.from_dict(task_data)
                self.tasks[task.id] = task
            
            self._task_id_counter = data.get('task_id_counter', 0)
            
            # 更新任务状态
            self._update_task_statuses()
            
            logger.info(f"从 {load_path} 加载了 {len(self.tasks)} 个任务")
            return True
            
        except Exception as e:
            logger.error(f"加载任务失败: {e}")
            return False
    
    def clear(self) -> None:
        """清空所有任务"""
        self.tasks.clear()
        self._task_id_counter = 0
        logger.info("任务已清空")
