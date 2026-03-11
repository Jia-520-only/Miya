"""
智能终端编排器 - 弥娅V4.0核心模块

集成AI智能决策，自动分配和管理多终端任务
"""

import asyncio
import json
from typing import Dict, List, Optional
from .local_terminal_manager import LocalTerminalManager
from .terminal_types import TerminalType, CommandResult

class IntelligentTerminalOrchestrator:
    """智能终端编排器"""
    
    def __init__(self):
        self.terminal_manager = LocalTerminalManager()
        self.context = {}
    
    async def smart_execute(
        self,
        task: str,
        auto_create: bool = True
    ) -> Dict:
        """智能执行任务
        
        Args:
            task: 任务描述
            auto_create: 是否自动创建终端
            
        Returns:
            执行结果
        """
        
        # 1. 分析任务
        analysis = await self._analyze_task(task)
        
        # 2. 决策执行策略
        strategy = analysis.get('strategy', 'single')
        
        print(f"[弥娅思考中...]")
        print(f"  任务: {task}")
        print(f"  策略: {strategy}")
        
        if strategy == 'single':
            # 单终端执行
            session_id = analysis.get('target_session')
            
            if not session_id:
                session_id = await self._select_best_terminal(analysis)
            
            result = await self.terminal_manager.execute_command(
                session_id, analysis['command']
            )
            
            return {
                "strategy": "single",
                "session_id": session_id,
                "result": result.to_dict(),
                "session_name": self.terminal_manager.sessions.get(session_id, {}).name if session_id else "未知"
            }
        
        elif strategy == 'parallel':
            # 多终端并行执行
            results = await self.terminal_manager.execute_parallel(
                analysis['parallel_commands']
            )
            
            return {
                "strategy": "parallel",
                "results": {k: v.to_dict() for k, v in results.items()}
            }
        
        elif strategy == 'sequence':
            # 顺序执行
            session_id = analysis.get('target_session')
            commands = analysis.get('commands', [])
            
            results = await self.terminal_manager.execute_sequence(
                session_id, commands
            )
            
            return {
                "strategy": "sequence",
                "session_id": session_id,
                "results": [r.to_dict() for r in results]
            }
        
        return {"error": "无法执行任务"}
    
    async def auto_setup_workspace(
        self,
        project_type: str,
        project_dir: str
    ):
        """自动设置工作空间
        
        Args:
            project_type: 项目类型
            project_dir: 项目目录
        """
        
        # 分析项目类型
        analysis = await self._analyze_project_type(project_type)
        
        print(f"[弥娅] 正在设置工作空间...")
        print(f"  项目类型: {project_type}")
        print(f"  项目目录: {project_dir}")
        
        # 创建多个终端
        terminals_to_create = analysis.get('terminals', [])
        
        created_sessions = []
        for term_config in terminals_to_create:
            session_id = await self.terminal_manager.create_terminal(
                name=term_config['name'],
                terminal_type=TerminalType.from_string(term_config['type']),
                initial_dir=project_dir
            )
            created_sessions.append(session_id)
            print(f"  ✓ 创建终端: {term_config['name']}")
        
        # 在每个终端执行初始化命令
        init_commands = analysis.get('init_commands', {})
        
        for session_id, commands in init_commands.items():
            print(f"  初始化终端 {session_id}...")
            await self.terminal_manager.execute_sequence(
                session_id, commands
            )
        
        print(f"\n[弥娅] 已创建 {len(created_sessions)} 个终端并初始化")
        
        # 切换到主终端
        if created_sessions:
            await self.terminal_manager.switch_session(created_sessions[0])
    
    async def collaborative_task(
        self,
        task_description: str
    ):
        """多终端协同任务
        
        Args:
            task_description: 任务描述
        """
        
        # AI分析任务
        plan = await self._plan_collaborative_task(task_description)
        
        print(f"\n[弥娅] 协同任务规划")
        print(f"  目标: {task_description}")
        print(f"  步骤: {len(plan.get('steps', []))}")
        
        # 执行协同步骤
        steps = plan.get('steps', [])
        for i, step in enumerate(steps, 1):
            print(f"\n[步骤 {i}/{len(steps)}] {step.get('name', '')}")
            print(f"  描述: {step.get('description', '')}")
            
            # 确定执行方式
            if step.get('parallel'):
                # 并行执行
                results = await self.terminal_manager.execute_parallel(
                    step.get('commands', {})
                )
                
                print(f"  ✓ 并行执行完成")
            else:
                # 串行执行
                session_id = step.get('target_session')
                commands = step.get('commands', [])
                
                for cmd in commands:
                    result = await self.terminal_manager.execute_command(
                        session_id, cmd
                    )
                    
                    if result.success:
                        print(f"  ✓ {cmd}")
                    else:
                        print(f"  ✗ {cmd}: {result.error}")
            
            # 简单延时
            await asyncio.sleep(0.5)
        
        print(f"\n[弥娅] 协同任务完成!")
    
    async def _analyze_task(self, task: str) -> Dict:
        """分析任务
        
        Args:
            task: 任务描述
            
        Returns:
            分析结果
        """
        
        # 简化实现：根据关键词分析
        task_lower = task.lower()
        
        # 并行任务
        if '同时' in task_lower or '并行' in task_lower or '多终端' in task_lower:
            return {
                'strategy': 'parallel',
                'parallel_commands': self._get_default_parallel_commands()
            }
        
        # 顺序任务
        if '然后' in task_lower or '接着' in task_lower or '依次' in task_lower:
            return {
                'strategy': 'sequence',
                'target_session': self.terminal_manager.active_session_id,
                'commands': self._extract_commands(task)
            }
        
        # 默认单终端
        return {
            'strategy': 'single',
            'command': task,
            'target_session': self.terminal_manager.active_session_id
        }
    
    async def _select_best_terminal(
        self,
        analysis: Dict
    ) -> Optional[str]:
        """选择最合适的终端
        
        Args:
            analysis: 分析结果
            
        Returns:
            会话ID
        """
        
        # 获取所有终端状态
        all_status = self.terminal_manager.get_all_status()
        
        # 选择空闲的终端
        for session_id, status in all_status.items():
            if status['status'] == 'idle':
                return session_id
        
        # 没有空闲终端
        return list(all_status.keys())[0] if all_status else None
    
    async def _analyze_project_type(self, project_type: str) -> Dict:
        """分析项目类型
        
        Args:
            project_type: 项目类型
            
        Returns:
            项目配置
        """
        
        project_type_lower = project_type.lower()
        
        # Python项目
        if 'python' in project_type_lower:
            return {
                'terminals': [
                    {'name': '主终端', 'type': 'cmd'},
                    {'name': '虚拟环境', 'type': 'cmd'}
                ],
                'init_commands': {}
            }
        
        # Web项目
        elif 'web' in project_type_lower or '前端' in project_type_lower:
            return {
                'terminals': [
                    {'name': '开发终端', 'type': 'cmd'},
                    {'name': '测试终端', 'type': 'cmd'}
                ],
                'init_commands': {}
            }
        
        # 默认配置
        return {
            'terminals': [
                {'name': '主终端', 'type': 'cmd'}
            ],
            'init_commands': {}
        }
    
    async def _plan_collaborative_task(self, task: str) -> Dict:
        """规划协同任务
        
        Args:
            task: 任务描述
            
        Returns:
            任务计划
        """
        
        # 简化实现
        return {
            'steps': [
                {
                    'name': '准备阶段',
                    'description': '准备工作环境',
                    'parallel': False,
                    'target_session': self.terminal_manager.active_session_id,
                    'commands': ['echo "准备开始"']
                }
            ]
        }
    
    def _get_default_parallel_commands(self) -> Dict[str, str]:
        """获取默认并行命令"""
        
        commands = {}
        for session_id, session in self.terminal_manager.sessions.items():
            commands[session_id] = f"echo '在 {session.name} 中执行'"
        
        return commands
    
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
            if line and not line.startswith('#'):
                commands.append(line)
        
        return commands
