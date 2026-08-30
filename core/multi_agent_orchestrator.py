"""
多Agent协作系统
参考 AutoGen/MegaAgent 框架，支持多Agent协作
- 任务分配
- Agent通信
- 结果聚合
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import uuid

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentMessage:
    """Agent间消息"""
    message_id: str
    sender_id: str
    receiver_id: str
    content: Any
    message_type: str = "text"
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict = field(default_factory=dict)


@dataclass
class SubTask:
    """子任务"""
    task_id: str
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    input_data: Any = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class Agent:
    """基础Agent类"""

    def __init__(self, agent_id: str, config: Dict):
        self.agent_id = agent_id
        self.config = config
        self.name = config.get('name', agent_id)
        self.capabilities = config.get('capabilities', [])
        self.role = config.get('role', 'general')
        self.status = AgentStatus.IDLE
        self.current_task: Optional[str] = None
        self.execution_history: List[Dict] = []
        self.message_handler: Optional[Callable] = None
        
    def supports_capability(self, capability: str) -> bool:
        """检查是否支持某能力"""
        return capability in self.capabilities
    
    def supports_all_capabilities(self, capabilities: List[str]) -> bool:
        """检查是否支持所有能力"""
        return all(cap in self.capabilities for cap in capabilities)

    async def execute(self, task: Dict) -> Dict:
        """执行任务"""
        self.status = AgentStatus.BUSY
        self.current_task = task.get('id')
        
        try:
            # 调用实际的任务执行逻辑
            if self.message_handler:
                result = await self.message_handler(task)
            else:
                result = await self._execute_task(task)
            
            self.status = AgentStatus.IDLE
            self.current_task = None
            
            # 记录执行历史
            self.execution_history.append({
                'task_id': task.get('id'),
                'result': result,
                'timestamp': datetime.now().timestamp()
            })
            
            return {'result': result, 'success': True}
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"Agent {self.agent_id} 执行任务失败: {e}")
            return {'result': None, 'success': False, 'error': str(e)}

    async def _execute_task(self, task: Dict) -> Any:
        """子类实现具体任务执行逻辑"""
        return f"Agent {self.agent_id} executed: {task.get('description', '')}"
    
    async def send_message(self, receiver_id: str, content: Any, message_type: str = "text") -> AgentMessage:
        """发送消息给另一个Agent"""
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type
        )
        return message


class MultiAgentOrchestrator:
    """多Agent协调器
    
    功能：
    - 任务分配（基于能力和负载均衡）
    - Agent通信（消息队列）
    - 结果聚合
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.agents: Dict[str, Agent] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        
        # 任务管理
        self.tasks: Dict[str, SubTask] = {}
        self.task_results: Dict[str, Any] = {}
        
        # 负载均衡
        self.agent_loads: Dict[str, int] = {}
        
        # 消息处理
        self._message_handlers: Dict[str, asyncio.Queue] = {}
        
        # 聚合策略
        self.aggregation_strategy = self.config.get('aggregation_strategy', 'merge')

    async def register_agent(self, agent_id: str, config: Dict) -> str:
        """注册Agent"""
        agent = Agent(agent_id, config)
        self.agents[agent_id] = agent
        self.agent_loads[agent_id] = 0
        self._message_handlers[agent_id] = asyncio.Queue()
        logger.info(f"[MultiAgent] 注册Agent: {agent_id}, 能力: {agent.capabilities}")
        return agent_id

    async def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            del self.agent_loads[agent_id]
            del self._message_handlers[agent_id]
            logger.info(f"[MultiAgent] 注销Agent: {agent_id}")
            return True
        return False

    async def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """获取Agent状态"""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        return {
            'agent_id': agent.agent_id,
            'name': agent.name,
            'role': agent.role,
            'status': agent.status.value,
            'capabilities': agent.capabilities,
            'current_task': agent.current_task,
            'load': self.agent_loads.get(agent_id, 0)
        }

    async def list_agents(self) -> List[Dict]:
        """列出所有Agent"""
        return [await self.get_agent_status(agent_id) for agent_id in self.agents.keys()]

    # ==================== 任务分配 ====================

    async def coordinate_task(self, task: Dict) -> Dict:
        """协调多Agent完成任务"""
        task_id = task.get('id', str(uuid.uuid4()))
        
        logger.info(f"[MultiAgent] 开始协调任务: {task_id}")

        # 1. 任务分解
        subtasks = await self._decompose_task(task)
        logger.info(f"[MultiAgent] 任务分解为 {len(subtasks)} 个子任务")

        # 2. Agent分配
        assignments = await self._assign_agents(subtasks)
        logger.info(f"[MultiAgent] Agent分配: {assignments}")

        # 3. 并行执行
        results = await self._execute_parallel(assignments, subtasks)

        # 4. 结果聚合
        final_result = await self._aggregate_results(results, subtasks)
        
        logger.info(f"[MultiAgent] 任务完成: {task_id}, 成功: {final_result.get('success')}")
        
        return final_result

    async def _decompose_task(self, task: Dict) -> List[SubTask]:
        """任务分解 - 将复杂任务分解为子任务"""
        description = task.get('description', '')
        capabilities = task.get('required_capabilities', [])
        
        # 简单策略：按能力要求分解
        subtasks = []
        
        if not capabilities:
            # 无特殊能力要求，创建单个任务
            subtask = SubTask(
                task_id=str(uuid.uuid4()),
                description=description,
                required_capabilities=[],
                input_data=task.get('input_data')
            )
            subtasks.append(subtask)
        else:
            # 按能力分组
            capability_groups = self._group_capabilities(capabilities)
            for i, group in enumerate(capability_groups):
                subtask = SubTask(
                    task_id=f"{task.get('id', 'task')}_sub_{i}",
                    description=f"{description} (阶段{i+1})",
                    required_capabilities=group,
                    input_data=task.get('input_data')
                )
                subtasks.append(subtask)
        
        # 存储任务
        for subtask in subtasks:
            self.tasks[subtask.task_id] = subtask
            
        return subtasks

    def _group_capabilities(self, capabilities: List[str]) -> List[List[str]]:
        """将能力分组 - 简单实现：每组一个能力"""
        return [[cap] for cap in capabilities]

    async def _assign_agents(self, subtasks: List[SubTask]) -> Dict[str, str]:
        """Agent分配 - 基于能力和负载均衡"""
        assignments = {}
        
        for subtask in subtasks:
            best_agent = await self._find_best_agent(subtask)
            if best_agent:
                assignments[subtask.task_id] = best_agent
                subtask.assigned_agent = best_agent
                self.agent_loads[best_agent] = self.agent_loads.get(best_agent, 0) + 1
            else:
                logger.warning(f"[MultiAgent] 未找到合适的Agent: {subtask.task_id}")
                subtask.status = TaskStatus.FAILED
                subtask.error = "No suitable agent found"
        
        return assignments

    async def _find_best_agent(self, subtask: SubTask) -> Optional[str]:
        """查找最适合的Agent - 考虑能力和负载"""
        required = subtask.required_capabilities
        
        # 过滤出支持所需能力的Agent
        capable_agents = [
            (agent_id, self.agent_loads[agent_id])
            for agent_id, agent in self.agents.items()
            if agent.supports_all_capabilities(required) and agent.status != AgentStatus.OFFLINE
        ]
        
        if not capable_agents:
            # 如果没有完全匹配的，找至少支持部分能力的
            for agent_id, agent in self.agents.items():
                if any(cap in agent.capabilities for cap in required):
                    capable_agents.append((agent_id, self.agent_loads.get(agent_id, 0)))
        
        if not capable_agents:
            # 降级：返回任意可用Agent
            available = [
                (agent_id, self.agent_loads.get(agent_id, 0))
                for agent_id, agent in self.agents.items()
                if agent.status != AgentStatus.OFFLINE
            ]
            if available:
                available.sort(key=lambda x: x[1])
                return available[0][0]
            return None
        
        # 选择负载最低的
        capable_agents.sort(key=lambda x: x[1])
        return capable_agents[0][0]

    async def _execute_parallel(self, assignments: Dict[str, str], subtasks: List[SubTask]) -> Dict[str, Any]:
        """并行执行子任务"""
        subtask_dict = {st.task_id: st for st in subtasks}
        
        async def execute_single(subtask_id: str, agent_id: str):
            subtask = subtask_dict[subtask_id]
            agent = self.agents[agent_id]
            
            subtask.status = TaskStatus.RUNNING
            subtask.started_at = datetime.now().timestamp()
            
            task_data = {
                'id': subtask.task_id,
                'description': subtask.description,
                'input_data': subtask.input_data
            }
            
            try:
                result = await agent.execute(task_data)
                subtask.result = result.get('result')
                subtask.status = TaskStatus.COMPLETED if result.get('success') else TaskStatus.FAILED
                if not result.get('success'):
                    subtask.error = result.get('error')
            except Exception as e:
                subtask.error = str(e)
                subtask.status = TaskStatus.FAILED
                logger.error(f"[MultiAgent] 子任务执行失败: {subtask_id}, {e}")
            finally:
                subtask.completed_at = datetime.now().timestamp()
                # 减少负载
                self.agent_loads[agent_id] = max(0, self.agent_loads.get(agent_id, 1) - 1)
            
            return subtask_id, subtask
        
        # 并行执行所有子任务
        tasks = [
            execute_single(subtask_id, agent_id) 
            for subtask_id, agent_id in assignments.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 转换为字典
        result_dict = {}
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[MultiAgent] 执行异常: {r}")
            else:
                subtask_id, subtask = r
                result_dict[subtask_id] = subtask
        
        return result_dict

    # ==================== 结果聚合 ====================

    async def _aggregate_results(self, results: Dict[str, SubTask], subtasks: List[SubTask]) -> Dict:
        """结果聚合 - 根据策略合并多Agent结果"""
        successful_results = []
        failed_tasks = []
        
        for subtask_id, subtask in results.items():
            if subtask.status == TaskStatus.COMPLETED:
                successful_results.append({
                    'task_id': subtask_id,
                    'agent_id': subtask.assigned_agent,
                    'result': subtask.result
                })
            else:
                failed_tasks.append({
                    'task_id': subtask_id,
                    'error': subtask.error
                })
        
        # 根据策略聚合
        aggregated = await self._apply_aggregation_strategy(successful_results)
        
        return {
            'task_id': subtasks[0].task_id.split('_sub_')[0] if subtasks else 'unknown',
            'subtask_results': successful_results,
            'failed_tasks': failed_tasks,
            'aggregated_result': aggregated,
            'success': len(failed_tasks) == 0,
            'total_subtasks': len(subtasks),
            'completed': len(successful_results),
            'failed': len(failed_tasks)
        }

    async def _apply_aggregation_strategy(self, results: List[Dict]) -> Any:
        """应用聚合策略"""
        if not results:
            return None
            
        if self.aggregation_strategy == 'merge':
            # 合并所有结果
            merged = {}
            for r in results:
                if isinstance(r.get('result'), dict):
                    merged.update(r['result'])
                else:
                    merged[r['task_id']] = r['result']
            return merged
            
        elif self.aggregation_strategy == 'concat':
            # 拼接结果
            return [r['result'] for r in results]
            
        elif self.aggregation_strategy == 'first':
            # 返回第一个成功的结果
            return results[0].get('result')
            
        elif self.aggregation_strategy == 'last':
            # 返回最后一个结果
            return results[-1].get('result')
            
        else:
            # 默认返回列表
            return [r['result'] for r in results]

    # ==================== Agent通信 ====================

    async def send_message(self, sender_id: str, receiver_id: str, content: Any, 
                          message_type: str = "text") -> bool:
        """发送消息"""
        if sender_id not in self.agents or receiver_id not in self.agents:
            logger.warning(f"[MultiAgent] 发送消息失败: Agent不存在")
            return False
        
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type
        )
        
        # 放入接收者的消息队列
        await self._message_handlers[receiver_id].put(message)
        
        logger.info(f"[MultiAgent] 消息: {sender_id} -> {receiver_id}")
        return True

    async def receive_message(self, agent_id: str, timeout: float = 5.0) -> Optional[AgentMessage]:
        """接收消息"""
        try:
            return await asyncio.wait_for(
                self._message_handlers[agent_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    async def broadcast_message(self, sender_id: str, content: Any, 
                               message_type: str = "text") -> int:
        """广播消息给所有Agent"""
        count = 0
        for agent_id in self.agents:
            if agent_id != sender_id:
                if await self.send_message(sender_id, agent_id, content, message_type):
                    count += 1
        return count

    # ==================== 生命周期管理 ====================

    async def start(self):
        """启动协调器"""
        self.running = True
        logger.info("[MultiAgent] 多Agent协调器已启动")

    async def stop(self):
        """停止协调器"""
        self.running = False
        # 设置所有Agent为离线
        for agent in self.agents.values():
            agent.status = AgentStatus.OFFLINE
        logger.info("[MultiAgent] 多Agent协调器已停止")

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        subtasks = [st for st in self.tasks.values() 
                   if st.task_id.startswith(task_id) or st.task_id == task_id]
        if not subtasks:
            return None
        
        return {
            'task_id': task_id,
            'subtasks': [
                {
                    'id': st.task_id,
                    'status': st.status.value,
                    'assigned_agent': st.assigned_agent,
                    'result': st.result,
                    'error': st.error
                }
                for st in subtasks
            ]
        }
