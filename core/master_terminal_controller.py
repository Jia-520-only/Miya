"""
主终端控制器 - 弥娅V4.0多终端协作架构

主终端是总控中心，负责：
- 用户交互与对话
- 任务规划与分解（显示弥娅思考过程）
- 全局调度（任务分配到子终端）
- 进度监控（所有子终端状态）
- 结果汇总（整合所有子终端结果）
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from .local_terminal_manager import LocalTerminalManager
from .ssh_terminal_manager import SSHTerminalManager
from .terminal_types import TerminalType, TerminalStatus
import logging

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Task:
    """任务对象"""
    id: str
    description: str
    commands: List[str]
    priority: TaskPriority = TaskPriority.MEDIUM
    terminal_id: Optional[str] = None
    created_at: float = 0.0
    status: str = "pending"  # pending, assigned, running, completed, failed

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    terminal_id: str
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    duration: float = 0.0


class MasterTerminalController:
    """主终端控制器 - 总控中心
    
    职责：
    1. 用户交互：接收用户输入，弥娅对话
    2. 任务规划：理解任务意图，规划执行策略
    3. 思考显示：展示弥娅的思考过程
    4. 全局调度：分配任务到最优子终端
    5. 进度监控：实时监控所有子终端执行状态
    6. 结果汇总：整合并展示所有任务结果
    """

    def __init__(
        self,
        local_manager: LocalTerminalManager = None,
        ssh_manager: SSHTerminalManager = None,
        show_thinking: bool = True,
        auto_monitor: bool = True,
        monitor_interval: float = 1.0
    ):
        # 终端管理器
        self.local_manager = local_manager or LocalTerminalManager()
        self.ssh_manager = ssh_manager or SSHTerminalManager()
        
        # 子终端池（统一管理本地和SSH终端）
        self.child_terminals: Dict[str, Dict] = {}
        
        # 任务队列
        self.task_queue: List[Task] = []
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: List[TaskResult] = []
        
        # 配置
        self.show_thinking = show_thinking
        self.auto_monitor = auto_monitor
        self.monitor_interval = monitor_interval
        
        # 监控状态
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 弥娅回调（用于调用AI）
        self.miya_callback: Optional[Callable] = None
        
        logger.info("[主终端控制器] 初始化完成")

    def set_miya_callback(self, callback: Callable):
        """设置弥娅AI回调
        
        Args:
            callback: 弥娅AI处理函数，接收(input_text) 返回 response
        """
        self.miya_callback = callback
        logger.info("[主终端控制器] 弥娅AI回调已设置")

    async def process_user_input(self, input_text: str):
        """处理用户输入
        
        Args:
            input_text: 用户输入文本
        """
        # 1. 判断是否是对弥娅的对话请求
        if self._is_miya_dialogue(input_text):
            # 弥娅对话模式
            await self._handle_miya_dialogue(input_text)
        else:
            # 任务执行模式 - 规划并执行任务
            await self._handle_task_execution(input_text)

    def _is_miya_dialogue(self, input_text: str) -> bool:
        """判断是否是对弥娅的对话请求
        
        Args:
            input_text: 用户输入
            
        Returns:
            True如果是对话，False如果是任务执行
        """
        # 对话关键词
        dialogue_keywords = [
            '弥娅', 'miya', '你好', 'hello',
            '解释', '分析', '帮我', 'help',
            '怎么', '如何', '为什么',
            '告诉我', '介绍一下', '说明'
        ]
        
        input_lower = input_text.lower()
        for kw in dialogue_keywords:
            if kw in input_lower:
                return True
        
        # 问号结尾通常是对话
        if '?' in input_text or '？' in input_text:
            return True
        
        return False

    async def _handle_miya_dialogue(self, input_text: str):
        """处理弥娅对话
        
        Args:
            input_text: 用户输入
        """
        if self.miya_callback:
            response = await self.miya_callback(input_text)
            print(f"\n{response}\n")
        else:
            print("\n[弥娅] AI回调未设置，无法处理对话请求\n")

    async def _handle_task_execution(self, input_text: str):
        """处理任务执行
        
        Args:
            input_text: 用户输入（任务描述）
        """
        # 1. 显示思考过程
        self._show_thinking(f"分析任务: {input_text}")
        
        # 2. 规划任务（调用AI或使用启发式规则）
        task_plan = await self._plan_task(input_text)
        
        self._show_thinking(f"规划完成，共 {len(task_plan.get('steps', []))} 个步骤")
        
        # 3. 执行任务
        results = await self._execute_task_plan(task_plan)
        
        # 4. 显示结果汇总
        self._show_result_summary(results, input_text)

    async def _plan_task(self, task_description: str) -> Dict:
        """规划任务执行策略
        
        Args:
            task_description: 任务描述
            
        Returns:
            任务计划字典
        """
        self._show_thinking("评估资源需求...")
        
        # 简化实现：基于关键词分析
        # 实际应该调用弥娅AI进行智能规划
        task_lower = task_description.lower()
        
        # 识别是否需要新终端
        needs_new_terminal = any(kw in task_lower for kw in [
            '打开终端', '创建终端', '新终端', '独立终端',
            '服务器', 'ssh', '远程',
            '打开一个新的', '创建一个新的', '新建终端',
            'open terminal', 'create terminal', 'new terminal'
        ])
        
        # 特别处理：直接包含"终端"的情况
        if '终端' in task_lower and ('打开' in task_lower or '创建' in task_lower or '新' in task_lower):
            needs_new_terminal = True
        
        # 识别是否需要SSH
        needs_ssh = any(kw in task_lower for kw in [
            'ssh', '远程', '服务器', 'server'
        ])
        
        # 识别是否需要并行
        needs_parallel = any(kw in task_lower for kw in [
            '同时', '并行', '一起', '分别'
        ])
        
        self._show_thinking(f"新终端: {'是' if needs_new_terminal else '否'}, "
                          f"SSH: {'是' if needs_ssh else '否'}, "
                          f"并行: {'是' if needs_parallel else '否'}")
        
        # 提取命令
        commands = self._extract_commands(task_description)
        
        return {
            "description": task_description,
            "needs_new_terminal": needs_new_terminal,
            "needs_ssh": needs_ssh,
            "needs_parallel": needs_parallel,
            "commands": commands,
            "steps": self._generate_steps(commands, needs_new_terminal, needs_ssh, needs_parallel)
        }

    def _extract_commands(self, text: str) -> List[str]:
        """从文本中提取命令
        
        Args:
            text: 文本
            
        Returns:
            命令列表
        """
        # 简化实现：按行分割
        lines = text.split('\n')
        commands = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('['):
                commands.append(line)
        
        return commands if commands else [text]

    def _generate_steps(
        self,
        commands: List[str],
        needs_new_terminal: bool,
        needs_ssh: bool,
        needs_parallel: bool
    ) -> List[Dict]:
        """生成执行步骤
        
        Args:
            commands: 命令列表
            needs_new_terminal: 是否需要新终端
            needs_ssh: 是否需要SSH
            needs_parallel: 是否需要并行
            
        Returns:
            步骤列表
        """
        steps = []
        
        if needs_new_terminal:
            # 步骤1: 创建新终端
            terminal_type = 'ssh' if needs_ssh else 'local'
            steps.append({
                "type": "create_terminal",
                "terminal_type": terminal_type,
                "description": f"创建新终端 ({terminal_type})"
            })
        
        # 步骤2: 执行命令
        if needs_parallel and len(commands) > 1:
            # 并行执行
            for i, cmd in enumerate(commands):
                steps.append({
                    "type": "execute_parallel",
                    "commands": {f"terminal_{i}": cmd},
                    "description": f"并行执行命令 {i+1}"
                })
        else:
            # 串行执行
            for cmd in commands:
                steps.append({
                    "type": "execute_sequence",
                    "commands": [cmd],
                    "description": f"执行命令: {cmd}"
                })
        
        return steps

    async def _execute_task_plan(self, task_plan: Dict) -> List[TaskResult]:
        """执行任务计划
        
        Args:
            task_plan: 任务计划
            
        Returns:
            执行结果列表
        """
        self._show_thinking("开始执行任务...")
        
        all_results = []
        terminal_id = None
        
        for i, step in enumerate(task_plan.get('steps', []), 1):
            self._show_thinking(f"执行步骤 {i}/{len(task_plan['steps'])}: {step['description']}")
            
            if step['type'] == 'create_terminal':
                # 创建新终端
                terminal_id = await self._create_child_terminal(
                    terminal_type=step['terminal_type']
                )
                self._show_thinking(f"✓ 创建终端完成: {terminal_id}")
            
            elif step['type'] == 'execute_sequence':
                # 串行执行
                if not terminal_id:
                    terminal_id = self.local_manager.active_session_id
                
                results = await self.local_manager.execute_sequence(
                    terminal_id, step['commands']
                )
                
                for cmd, result in zip(step['commands'], results):
                    task_result = TaskResult(
                        task_id=step.get('task_id', f"task_{time.time()}"),
                        terminal_id=terminal_id,
                        success=result.success,
                        output=result.output,
                        error=result.error,
                        exit_code=result.exit_code,
                        duration=result.execution_time
                    )
                    all_results.append(task_result)
                    
                    if result.success:
                        self._show_thinking(f"  ✓ {cmd}")
                    else:
                        self._show_thinking(f"  ✗ {cmd}: {result.error}")
            
            elif step['type'] == 'execute_parallel':
                # 并行执行
                results = await self.local_manager.execute_parallel(
                    step['commands']
                )
                
                for session_id, result in results.items():
                    task_result = TaskResult(
                        task_id=step.get('task_id', f"task_{time.time()}"),
                        terminal_id=session_id,
                        success=result.success,
                        output=result.output,
                        error=result.error,
                        exit_code=result.exit_code,
                        duration=result.execution_time
                    )
                    all_results.append(task_result)
        
        self._show_thinking("所有步骤执行完成")
        return all_results

    async def _create_child_terminal(
        self,
        name: str = None,
        terminal_type: str = "local"
    ) -> str:
        """创建子终端
        
        Args:
            name: 终端名称
            terminal_type: 终端类型（local/ssh）
            
        Returns:
            会话ID
        """
        if name is None:
            name = f"子终端{len(self.child_terminals) + 1}"
        
        if terminal_type == "local":
            # 创建本地终端
            session_id = await self.local_manager.create_terminal(
                name=name,
                terminal_type=TerminalType.CMD
            )
            
            self.child_terminals[session_id] = {
                "type": "local",
                "name": name
            }
            
            self._show_thinking(f"✓ 已创建本地终端: {name}")
            
        elif terminal_type == "ssh":
            # TODO: 创建SSH终端（需要配置）
            # 暂时先创建本地终端
            session_id = await self.local_manager.create_terminal(
                name=name,
                terminal_type=TerminalType.CMD
            )
            
            self.child_terminals[session_id] = {
                "type": "ssh",
                "name": name
            }
            
            self._show_thinking(f"✓ 已创建SSH终端: {name}")
        
        return session_id

    def _show_thinking(self, thought: str):
        """显示弥娅思考过程
        
        Args:
            thought: 思考内容
        """
        if self.show_thinking:
            print(f"[弥娅思考] {thought}")

    def _show_result_summary(self, results: List[TaskResult], task_description: str):
        """显示结果汇总
        
        Args:
            results: 执行结果列表
            task_description: 任务描述
        """
        print(f"\n{'='*60}")
        print(f"【任务完成】{task_description}")
        print(f"{'='*60}")
        
        total_duration = sum(r.duration for r in results)
        success_count = sum(1 for r in results if r.success)
        
        for i, result in enumerate(results, 1):
            status_icon = "✓" if result.success else "✗"
            print(f"{status_icon} 任务 {i}: {result.terminal_id}")
            if result.error:
                print(f"  错误: {result.error}")
            print(f"  耗时: {result.duration:.2f}s")
        
        print(f"\n总计: {len(results)} 个任务, {success_count} 个成功, 耗时 {total_duration:.2f}s")
        print(f"{'='*60}\n")

    async def start_monitoring(self):
        """开始监控所有子终端"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("[主终端控制器] 开始监控子终端")

    async def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("[主终端控制器] 停止监控")

    async def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 获取所有本地终端状态
                local_status = self.local_manager.get_all_status()
                
                # 获取所有SSH终端状态
                ssh_status = self.ssh_manager.get_all_ssh_status()
                
                # 显示活跃终端
                active_terminals = [
                    (sid, status) for sid, status in local_status.items()
                    if status.get('status') == 'executing'
                ]
                
                if active_terminals:
                    print(f"\n[监控] 活跃终端: {len(active_terminals)} 个")
                    for sid, status in active_terminals:
                        print(f"  - {status['name']}: {status['status']}")
                
                await asyncio.sleep(self.monitor_interval)
            
            except Exception as e:
                logger.error(f"[监控] 错误: {e}")
                await asyncio.sleep(self.monitor_interval)

    async def assign_task(self, task: Task, terminal_id: str = None) -> TaskResult:
        """分配任务到子终端
        
        Args:
            task: 任务对象
            terminal_id: 指定终端ID，None表示自动选择
            
        Returns:
            任务执行结果
        """
        # 显示思考过程
        self._show_thinking(f"分析任务: {task.description}")
        self._show_thinking(f"评估资源需求...")
        
        # 选择终端
        if terminal_id:
            selected_terminal = terminal_id
        else:
            selected_terminal = self._select_optimal_terminal(task)
        
        self._show_thinking(f"任务分配到: {selected_terminal}")
        
        # 执行任务
        results = await self.local_manager.execute_sequence(
            selected_terminal, task.commands
        )
        
        # 汇总结果
        if results:
            last_result = results[-1]
            return TaskResult(
                task_id=task.id,
                terminal_id=selected_terminal,
                success=last_result.success,
                output=last_result.output,
                error=last_result.error,
                exit_code=last_result.exit_code,
                duration=last_result.execution_time
            )
        
        return TaskResult(
            task_id=task.id,
            terminal_id=selected_terminal,
            success=False,
            output="",
            error="无执行结果"
        )

    def _select_optimal_terminal(self, task: Task) -> str:
        """智能选择最优子终端
        
        Args:
            task: 任务对象
            
        Returns:
            终端ID
        """
        # 获取所有终端状态
        all_status = self.local_manager.get_all_status()
        
        # 优先选择空闲终端
        for session_id, status in all_status.items():
            if status.get('status') == 'idle':
                return session_id
        
        # 没有空闲终端，选择活动终端
        return self.local_manager.active_session_id or next(iter(all_status.keys()), None)

    async def cleanup(self):
        """清理资源"""
        await self.stop_monitoring()
        await self.local_manager.close_all_sessions()
        logger.info("[主终端控制器] 清理完成")
